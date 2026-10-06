import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    short_code: str = Field(pattern="^[A-Za-z]{2,6}$")
    borrower: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=280)


class DealUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    borrower: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, min_length=1, max_length=280)
    amount_cr: Decimal | None = None
    allow_uploads_when_closed: bool | None = None


class StageChangeRequest(BaseModel):
    to_stage: str = Field(pattern="^(new|running|successful|dropped)$")
    # PRD F3: 5-1000 chars, required on every transition, not only Dropped.
    reason: str = Field(min_length=5, max_length=1000)


class DealListItem(BaseModel):
    """One row on the Deals home table — DESIGN.md §6.2."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    short_code: str
    borrower: str
    stage: str
    created_at: datetime
    updated_at: datetime  # stand-in for "last activity" — see routers/deals.py
    document_count: int = 0
    tasks_done: int = 0
    tasks_total: int = 0


class DealDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    short_code: str
    borrower: str
    summary: str
    stage: str
    amount_cr: Decimal | None
    allow_uploads_when_closed: bool
    created_at: datetime
    updated_at: datetime


class DealStageHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_stage: str | None
    to_stage: str
    reason: str
    changed_at: datetime
