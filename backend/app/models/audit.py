import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Append-only (CLAUDE.md §2.1 — never UPDATE or DELETE a row). The
    lilkis_app DB role only has INSERT + SELECT on this table; the REVOKE
    of UPDATE/DELETE lives in the migration, not here."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    detail: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
