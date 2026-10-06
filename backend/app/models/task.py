import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TASK_STATUSES = ("todo", "in_progress", "awaiting_approval", "done", "needs_attention")
TASK_PRIORITIES = ("low", "medium", "high")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in TASK_STATUSES)})", name="tasks_status_check"
        ),
        CheckConstraint(
            f"priority IN ({', '.join(repr(p) for p in TASK_PRIORITIES)})",
            name="tasks_priority_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE")
    )
    title: Mapped[str]
    description: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default="todo")
    priority: Mapped[str] = mapped_column(server_default="medium")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    due_date: Mapped[date | None]
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class TaskAttachment(Base):
    """Documents attached to a task. A task can reach 'done' only once all
    its attachments are 'active' (ARCHITECTURE.md §2.1)."""

    __tablename__ = "task_attachments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    attached_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
