import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_query import audit_query, to_audit_item
from app.database import get_db
from app.deps import require_admin
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.settings import Setting
from app.models.user import User
from app.schemas.admin import (
    ArchiveItem,
    AuditLogItem,
    PermissionMatrixEntry,
    ResetPasswordResponse,
    SetPermissionRequest,
    SettingsRead,
    SettingsUpdate,
    UserCreate,
    UserCreateResponse,
    UserRead,
    UserUpdate,
)
from app.storage import delete_object

router = APIRouter(prefix="/admin", tags=["admin"])


def _generate_temp_password() -> str:
    # 14 chars, matches PRD F9 / DESIGN.md §6.9's add-user dialog.
    return secrets.token_urlsafe(11)[:14]


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.display_name)))


@router.post("/users", response_model=UserCreateResponse, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserCreateResponse:
    from fastapi_users.password import PasswordHelper

    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    temp_password = body.temporary_password or _generate_temp_password()
    user = User(
        email=body.email,
        display_name=body.display_name,
        hashed_pw=PasswordHelper().hash(temp_password),
        role=body.role,
        can_approve=body.can_approve,
        must_change_password=True,  # PRD F1/F9: forced on first login
    )
    db.add(user)
    await db.flush()

    db.add_all(
        UserFolderPermission(
            user_id=user.id, folder_id=folder_id, access_level=level, granted_by=admin.id
        )
        for folder_id, level in body.folder_levels.items()
    )
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.created",
            entity_type="user",
            entity_id=str(user.id),
            detail={"email": user.email, "role": user.role},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return UserCreateResponse(
        id=user.id, display_name=user.display_name, email=user.email, temporary_password=temp_password
    )


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)

    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.updated",
            entity_type="user",
            entity_id=str(user.id),
            detail=updates,
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ResetPasswordResponse:
    from fastapi_users.password import PasswordHelper

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = _generate_temp_password()
    user.hashed_pw = PasswordHelper().hash(temp_password)
    user.must_change_password = True
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="user.password_reset",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return ResetPasswordResponse(temporary_password=temp_password)


@router.get("/permissions", response_model=list[PermissionMatrixEntry])
async def get_permission_matrix(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[PermissionMatrixEntry]:
    rows = await db.execute(
        select(UserFolderPermission, User.display_name, FolderTemplate.name)
        .join(User, User.id == UserFolderPermission.user_id)
        .join(FolderTemplate, FolderTemplate.id == UserFolderPermission.folder_id)
    )
    return [
        PermissionMatrixEntry(
            user_id=perm.user_id,
            user_name=user_name,
            folder_id=perm.folder_id,
            folder_name=folder_name,
            access_level=perm.access_level,
        )
        for perm, user_name, folder_name in rows
    ]


@router.put("/permissions/{user_id}/{folder_id}", response_model=PermissionMatrixEntry)
async def set_permission(
    user_id: uuid.UUID,
    folder_id: uuid.UUID,
    body: SetPermissionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PermissionMatrixEntry:
    target_user = await db.get(User, user_id)
    folder = await db.get(FolderTemplate, folder_id)
    if target_user is None or folder is None:
        raise HTTPException(status_code=404, detail="User or folder not found")

    perm = await db.get(UserFolderPermission, (user_id, folder_id))
    old_level = perm.access_level if perm else "none"
    if perm is None:
        perm = UserFolderPermission(
            user_id=user_id, folder_id=folder_id, access_level=body.access_level, granted_by=admin.id
        )
        db.add(perm)
    else:
        perm.access_level = body.access_level
        perm.granted_by = admin.id

    db.add(
        AuditLog(
            actor_id=admin.id,
            action="permission.changed",
            entity_type="user_folder_permission",
            entity_id=f"{user_id}:{folder_id}",
            detail={"from": old_level, "to": body.access_level, "folder": folder.name},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return PermissionMatrixEntry(
        user_id=user_id,
        user_name=target_user.display_name,
        folder_id=folder_id,
        folder_name=folder.name,
        access_level=body.access_level,
    )


@router.get("/archive", response_model=list[ArchiveItem])
async def list_archive(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[ArchiveItem]:
    # One query, not five per row. The reason comes from the
    # approval_requests row that archived it (ARCHITECTURE.md's documents
    # table has no reason column) — a lateral subquery picks the latest
    # one per document, since a file can be delete-requested, restored and
    # delete-requested again.
    Uploader = aliased(User)
    Approver = aliased(User)
    latest_reason = (
        select(ApprovalRequest.requester_note)
        .where(
            ApprovalRequest.type == "document_delete",
            ApprovalRequest.document_id == Document.id,
        )
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
        .correlate(Document)
        .scalar_subquery()
    )
    rows = await db.execute(
        select(Document, Deal.name, FolderTemplate.name, Uploader.display_name, Approver.display_name, latest_reason)
        .join(Deal, Deal.id == Document.deal_id)
        .join(FolderTemplate, FolderTemplate.id == Document.folder_id)
        .join(Uploader, Uploader.id == Document.uploaded_by)
        .outerjoin(Approver, Approver.id == Document.approved_by)
        .where(Document.status == "archived")
        .order_by(Document.updated_at.desc())
    )
    return [
        ArchiveItem(
            id=doc.id,
            display_name=doc.display_name,
            deal_id=doc.deal_id,
            deal_name=deal_name,
            folder_name=folder_name,
            deleted_by_name=uploader_name,
            approved_by_name=approver_name,
            deleted_at=doc.updated_at,
            reason=reason,
        )
        for doc, deal_name, folder_name, uploader_name, approver_name, reason in rows
    ]


@router.post("/archive/{doc_id}/restore")
async def restore_document(
    doc_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.status != "archived":
        raise HTTPException(status_code=404, detail="Archived document not found")

    doc.status = "active"
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="document.restored",
            entity_type="document",
            entity_id=str(doc.id),
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return {"status": "active"}


@router.post("/archive/{doc_id}/purge")
async def purge_document(
    doc_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    """Irreversible — removes the object from storage. The DB row stays
    (CLAUDE.md #2: files are never stored in the DB, but the row itself
    is never deleted either — PRD Goal G5)."""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.status != "archived":
        raise HTTPException(status_code=404, detail="Archived document not found")

    delete_object(doc.object_key)
    # PRD §8 names this state: "purged means the database row is kept and
    # the object deleted". It used to write 'rejected', the closest value
    # the CHECK constraint then allowed, which dropped the file out of the
    # Archive and back into the deal's document list as an ordinary row
    # whose object_key no longer resolved.
    doc.status = "purged"
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="document.purged",
            entity_type="document",
            entity_id=str(doc.id),
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return {"status": "purged"}


@router.get("/audit-log", response_model=list[AuditLogItem])
async def get_audit_log(
    deal_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AuditLogItem]:
    """PRD F10: "filterable log by deal, user, action type and date range,
    read-only." Deal and date range had no filter at all before, so the
    page could only ever show the newest 50 rows of everything."""
    rows = await db.execute(
        audit_query(
            deal_id=deal_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            since=since,
            until=until,
            limit=limit,
        )
    )
    return [to_audit_item(*row) for row in rows]


@router.get("/audit-log/actions", response_model=list[str])
async def list_audit_actions(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> list[str]:
    """Populates the Action filter from what has actually happened, rather
    than a hand-kept list that drifts every time an action is added."""
    return list(await db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)))


async def _read_settings(db: AsyncSession) -> SettingsRead:
    retention = await db.get(Setting, "archive_retention_days")
    purge_days = await db.get(Setting, "rejected_upload_purge_days")
    return SettingsRead(
        archive_retention_days=(retention.value if retention else None),
        rejected_upload_purge_days=(purge_days.value if purge_days else 30),
    )


@router.get("/settings", response_model=SettingsRead)
async def get_settings(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> SettingsRead:
    return await _read_settings(db)


@router.patch("/settings", response_model=SettingsRead)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SettingsRead:
    if "archive_retention_days" in body.model_fields_set:
        setting = await db.get(Setting, "archive_retention_days")
        if setting is None:
            setting = Setting(key="archive_retention_days")
            db.add(setting)
        setting.value = body.archive_retention_days
        setting.updated_by = admin.id
    await db.commit()
    return await _read_settings(db)
