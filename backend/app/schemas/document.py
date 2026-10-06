import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# PRD F5: exactly these six types.
ALLOWED_MIME_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


class DocumentInitRequest(BaseModel):
    filename: str = Field(min_length=1)
    size: int = Field(gt=0, le=MAX_FILE_SIZE_BYTES)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    mime_type: str
    folder_id: uuid.UUID


class DocumentInitResponse(BaseModel):
    doc_id: uuid.UUID
    total_chunks_expected: int | None = None


class DocumentCompleteResponse(BaseModel):
    doc_id: uuid.UUID
    status: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folder_id: uuid.UUID
    display_name: str
    size_bytes: int
    mime_type: str
    status: str
    uploaded_by_name: str
    created_at: datetime


class RenameRequest(BaseModel):
    # Base name only — the extension is locked and re-appended server-side
    # (PRD F5: "Extension is locked").
    base_name: str = Field(min_length=1, max_length=200)


class DeleteRequestBody(BaseModel):
    reason: str | None = None
