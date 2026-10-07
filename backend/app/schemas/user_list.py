import uuid

from pydantic import BaseModel, ConfigDict


class UserListItem(BaseModel):
    """Minimal — not UserRead/UserAdmin from schemas/admin.py, which also
    exposes role/can_approve/is_active. Any logged-in user can list
    co-workers to pick a task assignee from (PRD F8: "Anyone can create
    and assign"); only admin can see the fuller admin fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    is_active: bool
