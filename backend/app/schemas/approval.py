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
    note: str | None = None


class BulkActionResult(BaseModel):
    approved: int = 0
    rejected: int = 0
    already_handled: int = 0
    errors: list[str] = []
