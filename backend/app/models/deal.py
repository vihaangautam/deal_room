import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('new','running','successful','dropped')", name="deals_stage_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str]
    borrower: Mapped[str]
    stage: Mapped[str] = mapped_column(server_default="new")
    amount_cr: Mapped[Decimal | None]
    notes: Mapped[str | None]
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class DealStageHistory(Base):
    """Append-only. One row per stage transition, including creation
    (from_stage is NULL on the first row)."""

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
    reason: Mapped[str | None]
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
