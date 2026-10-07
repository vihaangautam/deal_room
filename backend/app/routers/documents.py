import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import accessible_folder_ids, check_folder_access, require_password_set
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

    conditions = [Document.deal_id == deal_id, Document.status != "archived"]
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
    # PRD F10: admin can download from the Archive too — folder access
    # doesn't apply there since Archive is already admin-only.
    if doc.status == "archived":
        if user.role != "admin":
            raise HTTPException(status_code=404, detail="Document not found")
    elif doc.status not in ("active", "delete_requested"):
        raise HTTPException(status_code=404, detail="Document not found")
    else:
        await check_folder_access(db, user, doc.folder_id, "view")

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
