import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select, true as True_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import (
    accessible_folder_ids,
    require_admin,
    require_open_deal,
    require_password_set,
)
from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User
from app.schemas.folder import (
    FolderCreate,
    FolderRead,
    FolderReorder,
    FolderUpdate,
    SubfolderCreate,
)

router = APIRouter(prefix="/folders", tags=["folders"])

# Statuses that count as "a document still references this folder" for
# PRD F4's delete-block rule — pending counts too (§10 edge cases:
# "Folder deleted while pending uploads exist. Blocked.").
BLOCKING_DOCUMENT_STATUSES = ("uploading", "pending", "active", "delete_requested", "archived")


def _read(folder: FolderTemplate, file_count: int, depth: int = 0) -> FolderRead:
    return FolderRead(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        deal_id=folder.deal_id,
        root_id=folder.root_id,
        depth=depth,
        display_order=folder.display_order,
        file_count=file_count,
        created_at=folder.created_at,
    )


async def _counts(db: AsyncSession) -> dict[uuid.UUID, int]:
    """One grouped query rather than a count per folder. It counts
    BLOCKING_DOCUMENT_STATUSES so the number matches what delete_folder
    would refuse on — a folder reading "0 files" is exactly one that can
    be deleted."""
    rows = await db.execute(
        select(Document.folder_id, func.count(Document.id))
        .where(Document.status.in_(BLOCKING_DOCUMENT_STATUSES))
        .group_by(Document.folder_id)
    )
    return {folder_id: count for folder_id, count in rows}


async def _folders_with_counts(db: AsyncSession) -> list[FolderRead]:
    """The global roots. Subfolders belong to a deal and are listed by
    deal_folders below, so the admin's Folders page and the permission
    matrix keep showing exactly the columns access is granted on."""
    counts = await _counts(db)
    folders = await db.scalars(
        select(FolderTemplate)
        .where(FolderTemplate.parent_id.is_(None))
        .order_by(FolderTemplate.display_order)
    )
    return [_read(folder, counts.get(folder.id, 0)) for folder in folders]


@router.get("", response_model=list[FolderRead])
async def list_folders(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[FolderRead]:
    return await _folders_with_counts(db)


@router.post("", response_model=FolderRead, status_code=201)
async def create_folder(
    body: FolderCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
) -> FolderTemplate:
    existing = await db.scalar(
        select(FolderTemplate).where(
            FolderTemplate.name == body.name, FolderTemplate.parent_id.is_(None)
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A folder with this name already exists")

    max_order = await db.scalar(
        select(func.max(FolderTemplate.display_order)).where(FolderTemplate.parent_id.is_(None))
    )
    folder = FolderTemplate(
        name=body.name, display_order=(max_order or 0) + 1, created_by=admin.id
    )
    db.add(folder)
    await db.flush()

    # PRD F4: new folder's default access applies to every current member
    # immediately. Admin rows aren't needed — admin bypasses this table.
    member_ids = await db.scalars(select(User.id).where(User.role == "member"))
    db.add_all(
        UserFolderPermission(
            user_id=member_id,
            folder_id=folder.id,
            access_level=body.default_access,
            granted_by=admin.id,
        )
        for member_id in member_ids
    )

    await db.commit()
    await db.refresh(folder)
    return folder


@router.post("/order", response_model=list[FolderRead])
async def reorder_folders(
    body: FolderReorder, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[FolderRead]:
    """PRD F4: folders appear in a fixed order in every deal, so reordering
    them is a single list, not a field on one row. One request and one
    transaction rather than a PATCH per folder, because a reorder that
    half-applies leaves every deal's folder list scrambled.
    """
    # Roots only — a subfolder's order is its own deal's business, and
    # including them here would make the stale-list check below fire
    # whenever any deal gained one.
    folders = list(
        await db.scalars(select(FolderTemplate).where(FolderTemplate.parent_id.is_(None)))
    )
    by_id = {folder.id: folder for folder in folders}

    if set(body.folder_ids) != set(by_id) or len(body.folder_ids) != len(folders):
        # A stale list means someone added or deleted a folder in another
        # tab; applying it would drop the missing one to the bottom.
        raise HTTPException(
            status_code=409, detail="The folder list changed. Reload the page and try again."
        )

    for position, folder_id in enumerate(body.folder_ids, start=1):
        by_id[folder_id].display_order = position

    await db.commit()
    return await _folders_with_counts(db)


@router.patch("/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> FolderRead:
    """A folder is a global template, so renaming one renames it inside
    every deal including closed ones — the files themselves never move,
    because documents reference folder_id and the stored object key is
    deals/{deal_id}/{doc_id} with no folder name in it. That blast radius
    is precisely why the rename is audited: deletion is blocked while
    files exist (PRD F4), so rename is the only way an admin can change
    what a historical deal's folder is called, and CLAUDE.md §2.4 wants a
    record of who did that and when.
    """
    folder = await db.get(FolderTemplate, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")

    if body.name is not None and body.name != folder.name:
        # folder_templates.name is UNIQUE, so without this the rename
        # surfaced as an IntegrityError 500 instead of the same 409
        # create_folder returns.
        # Siblings, matching the two partial unique indexes: root names
        # are globally unique, a subfolder's only among its siblings.
        clash = await db.scalar(
            select(FolderTemplate).where(
                FolderTemplate.name == body.name,
                FolderTemplate.parent_id.is_(None)
                if folder.parent_id is None
                else FolderTemplate.parent_id == folder.parent_id,
                FolderTemplate.deal_id == folder.deal_id
                if folder.deal_id is not None
                else FolderTemplate.deal_id.is_(None),
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail="A folder with this name already exists")
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="folder.renamed",
                entity_type="folder",
                entity_id=str(folder.id),
                detail={"from": folder.name, "to": body.name},
                ip_address=request.client.host if request.client else None,
            )
        )
        folder.name = body.name
    if body.display_order is not None:
        folder.display_order = body.display_order

    await db.commit()
    await db.refresh(folder)
    file_count = await db.scalar(
        select(func.count(Document.id)).where(
            Document.folder_id == folder.id,
            Document.status.in_(BLOCKING_DOCUMENT_STATUSES),
        )
    )
    return FolderRead(
        id=folder.id,
        name=folder.name,
        display_order=folder.display_order,
        file_count=file_count or 0,
        created_at=folder.created_at,
    )


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    folder = await db.get(FolderTemplate, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")

    children = await db.scalar(
        select(func.count(FolderTemplate.id)).where(FolderTemplate.parent_id == folder_id)
    )
    if children:
        # ON DELETE is RESTRICT by default on parent_id, so without this
        # the attempt surfaces as a 500 IntegrityError instead of
        # something an admin can act on.
        raise HTTPException(
            status_code=409,
            detail=(
                f"{folder.name} has {children} subfolder"
                f"{'' if children == 1 else 's'} inside it. Delete those first."
            ),
        )

    # Per-deal counts for the error message (PRD F4: "Error lists counts
    # per deal").
    rows = await db.execute(
        select(Deal.name, func.count(Document.id))
        .join(Document, Document.deal_id == Deal.id)
        .where(
            Document.folder_id == folder_id,
            Document.status.in_(BLOCKING_DOCUMENT_STATUSES),
        )
        .group_by(Deal.name)
    )
    per_deal = {name: count for name, count in rows}

    if per_deal:
        total_files = sum(per_deal.values())
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"{folder.name} can't be deleted. {total_files} files in "
                    f"{len(per_deal)} deals are in this folder. Move or delete "
                    "those files first."
                ),
                "per_deal": per_deal,
            },
        )

    await db.delete(folder)
    await db.commit()


# ---------------------------------------------------------------- per-deal
# Subfolders belong to one deal, so they hang off the deal's URL rather
# than /folders. A root is still global and still lives above.
deal_router = APIRouter(prefix="/deals/{deal_id}/folders", tags=["folders"])


async def _tree(db: AsyncSession, deal_id: uuid.UUID, user: User) -> list[FolderRead]:
    """Every global root, plus this deal's own subfolders, already in the
    order they should be drawn and carrying the depth to indent by.

    Flat rather than nested: the sidebar draws a list of rows, and a list
    of rows is what it should be handed. It also keeps the shape identical
    to GET /folders, so everything that already consumes a folder list —
    the upload dialog, the permission lookups — needed no changes.

    Roots are always listed, locked or not: PRD F5 wants a folder you
    can't open to still show with a lock, and their names are global and
    known to everyone anyway. Subfolder names are not. "Promoter PAN"
    under Borrower details tells you something about the borrower whether
    or not you can open it, so a subtree the viewer has no access to is
    left out rather than listed locked.
    """
    counts = await _counts(db)
    allowed = await accessible_folder_ids(db, user)
    folders = list(
        await db.scalars(
            select(FolderTemplate)
            .where(
                or_(FolderTemplate.parent_id.is_(None), FolderTemplate.deal_id == deal_id),
                True_() if allowed is None else or_(
                    FolderTemplate.parent_id.is_(None),
                    FolderTemplate.id.in_(allowed),
                ),
            )
            .order_by(FolderTemplate.display_order, FolderTemplate.name)
        )
    )
    children: dict[uuid.UUID | None, list[FolderTemplate]] = {}
    for folder in folders:
        children.setdefault(folder.parent_id, []).append(folder)

    ordered: list[FolderRead] = []

    def walk(parent_id: uuid.UUID | None, depth: int) -> None:
        for folder in children.get(parent_id, []):
            ordered.append(_read(folder, counts.get(folder.id, 0), depth))
            walk(folder.id, depth + 1)

    walk(None, 0)
    return ordered


@deal_router.get("", response_model=list[FolderRead])
async def list_deal_folders(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> list[FolderRead]:
    return await _tree(db, deal_id, user)


@deal_router.post("", response_model=FolderRead, status_code=201)
async def create_subfolder(
    deal_id: uuid.UUID,
    body: SubfolderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> FolderRead:
    """PRD F4/§7 keep folder management with the admin, subfolders
    included. No access rows are written: a subfolder is governed by the
    root of its tree (deps.permission_folder_id), so one created inside
    Borrower details is born as locked as Borrower details is.
    """
    await require_open_deal(db, deal_id)  # PRD F3: nothing is added to a closed deal

    parent = await db.get(FolderTemplate, body.parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    # A root belongs to every deal; a subfolder to exactly one, and
    # nesting under another deal's folder would file this deal's
    # documents under a folder it cannot see.
    if parent.deal_id is not None and parent.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Siblings in this deal. Two deals hanging a "March 2026" off the
    # same global root are not a clash — that is the point of per-deal.
    clash = await db.scalar(
        select(FolderTemplate).where(
            FolderTemplate.parent_id == parent.id,
            FolderTemplate.deal_id == deal_id,
            FolderTemplate.name == body.name,
        )
    )
    if clash:
        raise HTTPException(
            status_code=409, detail=f"{parent.name} already has a folder called '{body.name}'"
        )

    max_order = await db.scalar(
        select(func.max(FolderTemplate.display_order)).where(
            FolderTemplate.parent_id == parent.id
        )
    )
    folder = FolderTemplate(
        name=body.name,
        parent_id=parent.id,
        deal_id=deal_id,
        # A root is its own root, so a child of one points at the parent.
        root_id=parent.root_id or parent.id,
        display_order=(max_order or 0) + 1,
        created_by=admin.id,
    )
    db.add(folder)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="folder.created",
            entity_type="folder",
            entity_id=str(folder.id),
            detail={"name": folder.name, "parent": parent.name, "deal_id": str(deal_id)},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    await db.refresh(folder)

    # Walk to the root for the depth rather than storing it: it is read
    # once, here, and a stored copy is another field to keep true.
    depth, node = 1, parent
    while node.parent_id is not None:
        node = await db.get(FolderTemplate, node.parent_id)
        if node is None:
            break
        depth += 1
    return _read(folder, 0, depth)
