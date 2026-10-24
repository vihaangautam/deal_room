import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    # None on a root — the global folder every deal shows. Set on a
    # subfolder, which belongs to one deal and nests without limit.
    parent_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    # How far in to indent it, and which root's permission governs it.
    depth: int = 0
    root_id: uuid.UUID | None = None
    display_order: int
    # DESIGN.md §6.8's table columns. file_count is every status that
    # blocks deletion (PRD F4), so the number an admin reads is the same
    # number the delete error would quote back at them.
    file_count: int = 0
    created_at: datetime | None = None


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # PRD F4: admin picks the default access level for current members
    # when creating a folder. New folders start from 'none' by default
    # so admin explicitly configures access per member in Users & permissions.
    default_access: str = Field(default="none", pattern="^(none|view)$")


class SubfolderCreate(BaseModel):
    """A folder inside another, on one deal. parent_id is any folder in
    that deal's tree — a root, or another subfolder."""

    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = None


class FolderReorder(BaseModel):
    """Every folder id, in the order they should appear. Partial lists are
    rejected in the router rather than silently reordering a subset."""

    folder_ids: list[uuid.UUID] = Field(min_length=1)
