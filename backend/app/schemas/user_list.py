import uuid

from pydantic import BaseModel, ConfigDict


class UserListItem(BaseModel):
    """Minimal — not UserRead/UserAdmin from schemas/admin.py, which also
    exposes role, can_approve and last_login_at. Any logged-in user can
    list co-workers to pick a task assignee from (PRD F8: "Anyone can
    create and assign"); only admin sees the fuller admin fields.

    is_active is here because PRD §10 tags a deactivated user
    "(deactivated)" wherever their name appears — on assignments, in
    comments, in history — and this is the one list every page can reach.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    is_active: bool
