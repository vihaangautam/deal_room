import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FolderTemplate(Base):
    """A folder, in one of two shapes.

    A **root** is the global master folder it always was (ARCHITECTURE.md
    §2.1): parent_id, deal_id and root_id all NULL, shown in every deal,
    and the thing the permission matrix has a column for.

    A **subfolder** hangs off one folder and belongs to one deal, so the
    "March 2026" under Minutes in Sharma Infra is not a folder Patel ever
    sees. Nesting is unlimited; root_id short-circuits the depth.

    Access is never set on a subfolder: it is whatever the viewer has on
    the root of its tree. See deps.permission_folder_id.
    """

    __tablename__ = "folder_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Unique among its siblings, not globally — two deals can each have a
    # "March 2026" under Minutes. Held by two partial indexes in the
    # migration, which is why there is no unique=True here.
    name: Mapped[str]
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folder_templates.id")
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE")
    )
    # The root this subtree hangs off; NULL on a root, which is its own.
    # Set once at creation — nothing re-parents a folder — so permission
    # lookup is one indexed join however deep the folder sits.
    root_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folder_templates.id")
    )
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
