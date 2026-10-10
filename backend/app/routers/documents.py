import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import (
    accessible_folder_ids,
    check_folder_access,
    require_open_deal,
    require_password_set,
)
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DeleteRequestBody, DocumentRead, RenameRequest
from app.storage import presigned_download_url

router = APIRouter(prefix="/deals/{deal_id}/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> list[DocumentRead]:
    folder_ids = await accessible_folder_ids(db, user)

    # archived lives in the Archive (PRD F10); purged and failed have no
    # object behind them any more, so a row for either in the deal's file
    # table would only offer a download that 404s.
    conditions = [
        Document.deal_id == deal_id,
        Document.status.notin_(("archived", "purged", "failed")),
    ]
    if folder_ids is not None:
        conditions.append(Document.folder_id.in_(folder_ids))

    # PRD F5: pending/uploading/rejected documents are visible only to
    # their uploader and to approvers — active/delete_requested are
    # visible to anyone with folder access (a requested-but-undecided
    # deletion stays live and visible until approved, PRD §10).
    if not (user.role == "admin" or user.can_approve):
        conditions.append(
            or_(
                Document.status.in_(["active", "delete_requested"]),
                Document.uploaded_by == user.id,
            )
        )

    rows = await db.execute(
        select(Document, User.display_name)
        .join(User, User.id == Document.uploaded_by)
        .where(*conditions)
        .order_by(Document.created_at.desc())
    )
    return [
        DocumentRead(
            id=doc.id,
            folder_id=doc.folder_id,
            display_name=doc.display_name,
            size_bytes=doc.size_bytes,
            mime_type=doc.mime_type,
            status=doc.status,
            uploaded_by_name=uploader_name,
            created_at=doc.created_at,
        )
        for doc, uploader_name in rows
    ]


@router.get("/{doc_id}/download")
async def download_document(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> RedirectResponse:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Nothing is stored for these any more (PRD §8).
    if doc.status in ("purged", "failed"):
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "archived":
        # PRD F10: admin downloads from the Archive, and folder access
        # doesn't apply there since the Archive is already admin-only.
        if user.role != "admin":
            raise HTTPException(status_code=404, detail="Document not found")
    else:
        if doc.status in ("pending", "rejected"):
            # DESIGN.md §5.8 on the approvals queue: "without it Samir
            # cannot inspect a file before deciding, which makes the whole
            # screen a guess." Approving a document sight-unseen is the
            # failure mode; this is the fix. Narrowed to the same people
            # who can see the row at all (PRD F5): approvers, and the
            # uploader for their own file.
            if not (user.role == "admin" or user.can_approve or doc.uploaded_by == user.id):
                raise HTTPException(status_code=404, detail="Document not found")
        await check_folder_access(db, user, doc.folder_id, "view")

    if doc.integrity_check_failed:
        # upload.py never wrote an object for these — the hash did not
        # match, so there is nothing behind object_key. A presigned URL
        # would be a link to a 404 at the storage provider.
        raise HTTPException(
            status_code=409,
            detail="This file failed its integrity check and was never stored. It can only be rejected.",
        )

    url = presigned_download_url(doc.object_key, doc.display_name)
    return RedirectResponse(url, status_code=302)


@router.patch("/{doc_id}", response_model=DocumentRead)
async def rename_document(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    body: RenameRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> DocumentRead:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "active":
        raise HTTPException(status_code=409, detail="Only active documents can be renamed")

    await require_open_deal(db, deal_id)  # PRD F3
    await check_folder_access(db, user, doc.folder_id, "contribute")

    ext = Path(doc.display_name).suffix  # locked — PRD F5
    old_name = doc.display_name
    doc.display_name = f"{body.base_name}{ext}"

    db.add(
        AuditLog(
            actor_id=user.id,
            action="document.renamed",
            entity_type="document",
            entity_id=str(doc.id),
            detail={"from": old_name, "to": doc.display_name},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    await db.refresh(doc)
    uploader = await db.get(User, doc.uploaded_by)
    return DocumentRead(
        id=doc.id,
        folder_id=doc.folder_id,
        display_name=doc.display_name,
        size_bytes=doc.size_bytes,
        mime_type=doc.mime_type,
        status=doc.status,
        uploaded_by_name=uploader.display_name if uploader else "",
        created_at=doc.created_at,
    )


@router.delete("/{doc_id}", status_code=200)
async def request_delete(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    body: DeleteRequestBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> dict[str, str]:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "active":
        raise HTTPException(status_code=409, detail="Only active documents can be deleted")

    await require_open_deal(db, deal_id)  # PRD F3
    await check_folder_access(db, user, doc.folder_id, "contribute")

    ip = request.client.host if request.client else None

    if user.role == "admin" or user.can_approve:
        # PRD §7 permission matrix: admin/approver deletes directly to
        # Archive, no approval request needed.
        doc.status = "archived"
        db.add(
            AuditLog(
                actor_id=user.id,
                action="document.archived",
                entity_type="document",
                entity_id=str(doc.id),
                detail={"reason": body.reason, "direct": True},
                ip_address=ip,
            )
        )
        await db.commit()
        return {"status": "archived"}

    existing = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.type == "document_delete",
            ApprovalRequest.document_id == doc.id,
            ApprovalRequest.status == "pending",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A deletion request is already pending")

    doc.status = "delete_requested"
    db.add(
        ApprovalRequest(
            type="document_delete",
            document_id=doc.id,
            requested_by=user.id,
            requester_note=body.reason,
        )
    )
    db.add(
        AuditLog(
            actor_id=user.id,
            action="document.delete_requested",
            entity_type="document",
            entity_id=str(doc.id),
            detail={"reason": body.reason},
            ip_address=ip,
        )
    )
    await db.commit()
    return {"status": "delete_requested"}
