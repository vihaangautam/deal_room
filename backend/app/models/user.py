import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin','member')", name="users_role_check"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    hashed_pw: Mapped[str]
    role: Mapped[str] = mapped_column(server_default="member")
    can_approve: Mapped[bool] = mapped_column(server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # Not in ARCHITECTURE.md §2.1's DDL, but PRD F1 requires it: a new user
    # must change their temp password before any other request succeeds.
    must_change_password: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    @property
    def hashed_password(self) -> str:
        """fastapi-users' internals (authenticate(), password rehash on
        login) read/write this exact attribute name. Our column is
        hashed_pw per ARCHITECTURE.md §2.1 — this property bridges the two
        without renaming the migrated column. See app/auth.py UserDatabase
        for the corresponding write-side translation."""
        return self.hashed_pw

    @hashed_password.setter
    def hashed_password(self, value: str) -> None:
        self.hashed_pw = value


class AccessToken(Base):
    """fastapi-users session store (DatabaseStrategy) — also the audit trail
    of who logged in when. See ARCHITECTURE.md §2.1."""

    __tablename__ = "access_tokens"

    token: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
