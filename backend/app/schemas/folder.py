import uuid

from pydantic import BaseModel, ConfigDict, Field


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_order: int


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # PRD F4: admin picks the default access level for current members
    # when creating a folder. New folders start from 'none' by default
    # so admin explicitly configures access per member in Users & permissions.
    default_access: str = Field(default="none", pattern="^(none|view)$")


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = None


class FolderReorder(BaseModel):
    """Every folder id, in the order they should appear. Partial lists are
    rejected in the router rather than silently reordering a subset."""

    folder_ids: list[uuid.UUID] = Field(min_length=1)
