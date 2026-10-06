import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FolderTemplate(Base):
    """Global master folder list — not per-deal. Every deal shows every
    folder (ARCHITECTURE.md §2.1)."""

    __tablename__ = "folder_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(unique=True)
    display_order: Mapped[int] = mapped_column(server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class UserFolderPermission(Base):
    """Access level per (user × folder_template). Absent row = 'none'
    (deny by default). Admin bypasses this table entirely."""

    __tablename__ = "user_folder_permissions"
    __table_args__ = (
        CheckConstraint(
            "access_level IN ('none','view','contribute')",
            name="user_folder_permissions_access_level_check",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folder_templates.id", ondelete="CASCADE"), primary_key=True
    )
    access_level: Mapped[str] = mapped_column(server_default="view")
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
