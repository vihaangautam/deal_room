import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_admin, require_password_set
from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderRead, FolderReorder, FolderUpdate

router = APIRouter(prefix="/folders", tags=["folders"])

# Statuses that count as "a document still references this folder" for
# PRD F4's delete-block rule — pending counts too (§10 edge cases:
# "Folder deleted while pending uploads exist. Blocked.").
BLOCKING_DOCUMENT_STATUSES = ("uploading", "pending", "active", "delete_requested", "archived")


async def _folders_with_counts(db: AsyncSession) -> list[FolderRead]:
    """One grouped subquery rather than a count per folder. The count uses
    BLOCKING_DOCUMENT_STATUSES so it matches what delete_folder would
    refuse on — a folder reading "0 files" is exactly one that can be
    deleted."""
    counts = (
        select(Document.folder_id, func.count(Document.id).label("files"))
        .where(Document.status.in_(BLOCKING_DOCUMENT_STATUSES))
        .group_by(Document.folder_id)
        .subquery()
    )
    rows = await db.execute(
        select(FolderTemplate, func.coalesce(counts.c.files, 0))
        .outerjoin(counts, counts.c.folder_id == FolderTemplate.id)
        .order_by(FolderTemplate.display_order)
    )
    return [
        FolderRead(
            id=folder.id,
            name=folder.name,
            display_order=folder.display_order,
            file_count=file_count,
            created_at=folder.created_at,
        )
        for folder, file_count in rows
    ]


@router.get("", response_model=list[FolderRead])
async def list_folders(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[FolderRead]:
    return await _folders_with_counts(db)


@router.post("", response_model=FolderRead, status_code=201)
async def create_folder(
    body: FolderCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)
) -> FolderTemplate:
    existing = await db.scalar(select(FolderTemplate).where(FolderTemplate.name == body.name))
    if existing:
        raise HTTPException(status_code=409, detail="A folder with this name already exists")

    max_order = await db.scalar(select(func.max(FolderTemplate.display_order)))
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
    folders = list(await db.scalars(select(FolderTemplate)))
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
        clash = await db.scalar(select(FolderTemplate).where(FolderTemplate.name == body.name))
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
