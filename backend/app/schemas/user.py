import uuid

from pydantic import BaseModel, ConfigDict, Field


class UserMe(BaseModel):
    """GET /auth/me response — ARCHITECTURE.md §3.1: id, email,
    display_name, role, can_approve. No is_superuser/is_verified; this app
    doesn't use fastapi-users' built-in schema base (see auth.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    can_approve: bool
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    # Optional: not required for the forced first-login flow (DESIGN.md
    # §6.1 — logging in with the temp password already proves identity).
    # Required when the account is already set up (must_change_password is
    # already False) — enforced in the route, not here, since that check
    # needs the current user's state.
    current_password: str | None = None
    new_password: str = Field(min_length=10)
