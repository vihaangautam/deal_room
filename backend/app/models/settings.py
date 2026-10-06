import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Setting(Base):
    """Key-value store, admin-editable. Seeded defaults:
    archive_retention_days, email_notifications, default_lead_days
    (ARCHITECTURE.md §2.1)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
