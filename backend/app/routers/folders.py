import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_admin, require_password_set
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderRead, FolderUpdate

router = APIRouter(prefix="/folders", tags=["folders"])

# Statuses that count as "a document still references this folder" for
# PRD F4's delete-block rule — pending counts too (§10 edge cases:
# "Folder deleted while pending uploads exist. Blocked.").
BLOCKING_DOCUMENT_STATUSES = ("uploading", "pending", "active", "delete_requested", "archived")


@router.get("", response_model=list[FolderRead])
async def list_folders(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[FolderTemplate]:
    result = await db.scalars(select(FolderTemplate).order_by(FolderTemplate.display_order))
    return list(result)


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


@router.patch("/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> FolderTemplate:
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
        folder.name = body.name
    if body.display_order is not None:
        folder.display_order = body.display_order

    await db.commit()
    await db.refresh(folder)
    return folder


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
