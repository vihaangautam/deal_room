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
