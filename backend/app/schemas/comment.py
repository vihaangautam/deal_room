import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    author_id: uuid.UUID
    author_name: str
    body: str
    edited: bool
    deleted: bool
    created_at: datetime
