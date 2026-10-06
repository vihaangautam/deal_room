import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

DEAL_STAGES = ("new", "running", "successful", "dropped")


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint(
            f"stage IN ({', '.join(repr(s) for s in DEAL_STAGES)})", name="deals_stage_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str]
    short_code: Mapped[str] = mapped_column(unique=True)
    borrower: Mapped[str]
    summary: Mapped[str]
    stage: Mapped[str] = mapped_column(server_default="new")
    amount_cr: Mapped[Decimal | None]
    allow_uploads_when_closed: Mapped[bool] = mapped_column(server_default=text("false"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DealStageHistory(Base):
    """Append-only. One row per stage transition. No row for the initial
    New stage at creation — see routers/deals.py."""

    __tablename__ = "deal_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE")
    )
    from_stage: Mapped[str | None]
    to_stage: Mapped[str]
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reason: Mapped[str]
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
