import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    temporary_password: str | None = Field(default=None, min_length=10)
    role: str = Field(default="member", pattern="^(admin|member)$")
    can_approve: bool = False
    # PRD F9: "initial folder levels" — {folder_id: access_level}. Omitted
    # folders default to 'none' (deny by default, matches
    # ARCHITECTURE.md §2.2's resolution order).
    folder_levels: dict[uuid.UUID, str] = {}


class UserCreateResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str
    temporary_password: str  # shown once, at creation — DESIGN.md §6.9


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    can_approve: bool | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str
    role: str
    can_approve: bool
    is_active: bool
    created_at: datetime


class ResetPasswordResponse(BaseModel):
    temporary_password: str


class PermissionMatrixEntry(BaseModel):
    user_id: uuid.UUID
    user_name: str
    folder_id: uuid.UUID
    folder_name: str
    access_level: str


class SetPermissionRequest(BaseModel):
    access_level: str = Field(pattern="^(none|view|contribute)$")


class ArchiveItem(BaseModel):
    id: uuid.UUID
    display_name: str
    deal_id: uuid.UUID
    deal_name: str
    folder_name: str
    deleted_by_name: str | None
    approved_by_name: str | None
    deleted_at: datetime
    reason: str | None


class AuditLogItem(BaseModel):
    """DESIGN.md §6.11 renders a sentence — "Meera Shah uploaded 'SBI
    sanction letter.pdf' to Bank documents in Krishna Steel." — so the row
    has to carry the actor's name and the deal, neither of which is on the
    audit_log table itself. actor_id stays for filtering; actor_name is
    None only for rows with no actor, which today means a failed login."""

    id: int
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str
    detail: dict | list | str | int | float | bool | None
    deal_id: uuid.UUID | None
    deal_name: str | None
    created_at: datetime


class SettingsRead(BaseModel):
    archive_retention_days: int | None
    rejected_upload_purge_days: int


class SettingsUpdate(BaseModel):
    archive_retention_days: int | None = None
