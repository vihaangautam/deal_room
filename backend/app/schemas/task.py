import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assignee_id: uuid.UUID | None = None  # PRD F8: anyone can create AND assign in one step
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> "TaskCreate":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("due_date must not be before start_date")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    start_date: date | None = None
    due_date: date | None = None


class AssignRequest(BaseModel):
    assignee_id: uuid.UUID


class StatusChangeRequest(BaseModel):
    status: str = Field(pattern="^(not_started|in_progress)$")  # done goes through /submit


class AttachLinkRequest(BaseModel):
    document_id: uuid.UUID


class TaskListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    title: str
    status: str
    needs_attention: bool
    priority: str
    assignee_name: str | None
    reporter_name: str
    due_date: date | None
    deal_id: uuid.UUID
    deal_name: str | None = None  # populated only for the cross-deal My Tasks view


class TaskAttachmentItem(BaseModel):
    """PRD F6: a document the viewer can't see renders as a lock icon
    plus "Restricted document" — no name, size or link. restricted=True
    means every other field here is a placeholder, not real data."""

    document_id: uuid.UUID
    restricted: bool
    display_name: str | None = None
    folder_name: str | None = None
    status: str | None = None


class TaskDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    deal_id: uuid.UUID
    title: str
    description: str | None
    status: str
    needs_attention: bool
    priority: str
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    reporter_id: uuid.UUID
    reporter_name: str
    assigned_by_id: uuid.UUID | None
    assigned_by_name: str | None
    start_date: date | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    pending_reassignment_to: str | None = None
    attachments: list[TaskAttachmentItem] = []
