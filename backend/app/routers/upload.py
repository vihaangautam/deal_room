"""Chunked upload mechanics (init -> chunk -> complete), split from
documents.py per CLAUDE.md §4's module layout. CLAUDE.md §5.6: chunks
buffer to a temp dir and get reassembled into a single S3 PUT at
complete() — this is NOT S3 multipart upload, just HTTP chunking to avoid
one huge request body through the Cloudflare Tunnel (ARCHITECTURE.md §4).
"""

import hashlib
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import check_folder_access, require_password_set
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate
from app.models.user import User
from app.schemas.document import (
    ALLOWED_MIME_EXTENSIONS,
    DocumentCompleteResponse,
    DocumentInitRequest,
    DocumentInitResponse,
)
from app.storage import put_object

router = APIRouter(tags=["upload"])

CHUNK_DIR = Path(tempfile.gettempdir()) / "lilkis_uploads"
MAX_CHUNK_SIZE = 32 * 1024 * 1024  # CLAUDE.md §5.6
UPLOAD_STATUSES_BLOCKING_DEDUP = ("uploading", "pending", "active", "delete_requested")


async def resolve_upload_slot(
    db: AsyncSession, deal_id: uuid.UUID, sha256: str, user: User
) -> Document | None:
    """Dedup (PRD F5), checked before any bytes transfer rather than left
    to the DB's partial unique index at complete() time.

    Returns a row to resume into, or None to create a fresh one, and
    raises 409 when the file is genuinely already in the deal. The resume
    case is why Retry works at all: init writes a row with status
    'uploading', and a failed chunk or complete() leaves it that way —
    which is one of the statuses this check blocks on, so a second init
    for the same file used to answer "Already in Bank documents as
    'x.pdf'" and PRD F5's "Retry resumes only that file" could never
    happen. Only the same uploader's own stalled upload is resumable;
    anyone else, or any further-along status, is a real duplicate.
    """
    dup_row = (
        await db.execute(
            select(Document, FolderTemplate.name)
            .join(FolderTemplate, FolderTemplate.id == Document.folder_id)
            .where(
                Document.deal_id == deal_id,
                Document.sha256 == sha256,
                Document.status.in_(UPLOAD_STATUSES_BLOCKING_DEDUP),
            )
            .limit(1)
        )
    ).first()
    if dup_row is None:
        return None

    doc, folder_name = dup_row
    if doc.status == "uploading" and doc.uploaded_by == user.id:
        return doc
    raise HTTPException(status_code=409, detail=f"Already in {folder_name} as '{doc.display_name}'")


@router.post("/deals/{deal_id}/documents/init", response_model=DocumentInitResponse)
async def init_upload(
    deal_id: uuid.UUID,
    body: DocumentInitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> DocumentInitResponse:
    await check_folder_access(db, user, body.folder_id, "contribute")

    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.stage in ("successful", "dropped") and not deal.allow_uploads_when_closed:
        raise HTTPException(status_code=403, detail="This deal is closed. Files can't be uploaded.")

    ext = Path(body.filename).suffix.lower()
    if ext not in ALLOWED_MIME_EXTENSIONS:
        raise HTTPException(
            status_code=422, detail=f"Not allowed: {ext} files can't be uploaded."
        )

    resumable = await resolve_upload_slot(db, deal_id, body.sha256, user)
    if resumable is not None:
        (CHUNK_DIR / str(resumable.id)).mkdir(parents=True, exist_ok=True)
        return DocumentInitResponse(doc_id=resumable.id)

    doc = Document(
        deal_id=deal_id,
        folder_id=body.folder_id,
        display_name=body.filename,
        original_name=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size,
        sha256=body.sha256,
        object_key="",  # set below once doc.id exists
        status="uploading",
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()  # assigns doc.id
    doc.object_key = f"deals/{deal_id}/{doc.id}"  # ARCHITECTURE.md §9 layout
    await db.commit()

    (CHUNK_DIR / str(doc.id)).mkdir(parents=True, exist_ok=True)
    return DocumentInitResponse(doc_id=doc.id)


@router.post("/upload/{doc_id}/chunk")
async def upload_chunk(
    doc_id: uuid.UUID,
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    data: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> dict[str, bool]:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.uploaded_by != user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    if doc.status != "uploading":
        raise HTTPException(status_code=409, detail="This upload is no longer in progress")

    chunk_bytes = await data.read()
    if len(chunk_bytes) > MAX_CHUNK_SIZE:
        raise HTTPException(status_code=413, detail="Chunk too large")

    chunk_dir = CHUNK_DIR / str(doc_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / f"chunk_{chunk_index:06d}").write_bytes(chunk_bytes)

    return {"received": True}


@router.post("/upload/{doc_id}/complete", response_model=DocumentCompleteResponse)
async def complete_upload(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> DocumentCompleteResponse:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.uploaded_by != user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    if doc.status != "uploading":
        raise HTTPException(status_code=409, detail="This upload was already completed")

    chunk_dir = CHUNK_DIR / str(doc_id)
    chunk_files = sorted(chunk_dir.glob("chunk_*"))
    if not chunk_files:
        raise HTTPException(status_code=400, detail="No chunks were received")

    # Assembled on disk and streamed to S3, never held in memory. PRD F5
    # allows 2 GB per file, and the previous bytearray — plus the
    # bytes(assembled) copy handed to boto3 — peaked at roughly 4 GB of
    # RSS per concurrent upload, which the VM in ARCHITECTURE.md §4 does
    # not have. Hashing happens in the same pass, so this reads each
    # chunk once either way.
    assembled_path = chunk_dir / "assembled"  # not matched by glob("chunk_*")
    hasher = hashlib.sha256()
    with assembled_path.open("wb") as out:
        for chunk_file in chunk_files:
            with chunk_file.open("rb") as src:
                while block := src.read(1024 * 1024):
                    hasher.update(block)
                    out.write(block)

    # Chunks are only deleted after everything below succeeds (put_object
    # + commit) — if either fails, the client can retry POST .../complete
    # without re-uploading. Deleting first (as an earlier version of this
    # function did) throws the chunks away even when put_object fails,
    # leaving no way to retry short of starting the whole upload over.
    if hasher.hexdigest() != doc.sha256:
        # PRD §10: flagged for approvers, who can only reject it — never
        # an automatic rejection (CLAUDE.md #7: the system flags, humans
        # decide). Nothing is written to storage in this branch.
        doc.integrity_check_failed = True
    else:
        with assembled_path.open("rb") as body:
            put_object(doc.object_key, body, doc.mime_type)

    if user.can_approve and not doc.integrity_check_failed:
        # PRD F5: an approver's own uploads are auto-approved — but a hash
        # mismatch overrides that. Auto-approving a flagged upload marked
        # it 'active' with nothing behind its object_key and never created
        # an approval request, so the file was permanently undownloadable
        # and no human ever saw the flag PRD §10 raises it for.
        doc.status = "active"
        doc.approved_by = user.id
        db.add(
            AuditLog(
                actor_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=str(doc.id),
                detail={
                    "name": doc.display_name,
                    "deal_id": str(doc.deal_id),
                    "folder_id": str(doc.folder_id),
                    "auto_approved": True,
                },
            )
        )
    else:
        doc.status = "pending"
        db.add(
            ApprovalRequest(
                type="document_upload", document_id=doc.id, requested_by=user.id
            )
        )
        db.add(
            AuditLog(
                actor_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=str(doc.id),
                detail={
                    "name": doc.display_name,
                    "deal_id": str(doc.deal_id),
                    "folder_id": str(doc.folder_id),
                },
            )
        )

    await db.commit()
    shutil.rmtree(chunk_dir, ignore_errors=True)
    return DocumentCompleteResponse(doc_id=doc.id, status=doc.status)
