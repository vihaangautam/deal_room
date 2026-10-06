import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

APPROVAL_TYPES = ("document_upload", "document_delete", "task_reassign", "task_delete")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "cancelled", "superseded")


class ApprovalRequest(Base):
    """One pending approval per (type, target) — enforced in the DB by a
    partial unique index (ARCHITECTURE.md §2.1), not here in the ORM."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in APPROVAL_TYPES)})",
            name="approval_requests_type_check",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in APPROVAL_STATUSES)})",
            name="approval_requests_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    type: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="pending")

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE")
    )
    proposed_assignee: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    review_note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    reviewed_at: Mapped[datetime | None]
