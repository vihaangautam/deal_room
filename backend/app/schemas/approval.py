import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ApprovalItem(BaseModel):
    id: uuid.UUID
    type: str
    deal_id: uuid.UUID
    deal_name: str
    item_label: str
    item_sublabel: str | None
    # Set for document_upload and document_delete, so the queue can link
    # the filename to its download (DESIGN.md §5.8). None for the task
    # types, which have nothing to download.
    document_id: uuid.UUID | None = None
    requested_by_name: str
    requested_at: datetime
    note: str | None


class BulkActionRequest(BaseModel):
    ids: list[uuid.UUID]
    action: Literal["approve", "reject"]
    # One reason for the whole batch — what the reject dialog collects.
    note: str | None = None
    # A reply typed against one row, which wins over the batch note for
    # that row. The queue is a table, and "approve these twelve, but tell
    # Meera why the KYC pack is going back" is one action to the person
    # doing it, not twelve.
    notes: dict[uuid.UUID, str] = {}


class BulkActionResult(BaseModel):
    approved: int = 0
    rejected: int = 0
    already_handled: int = 0
    errors: list[str] = []
