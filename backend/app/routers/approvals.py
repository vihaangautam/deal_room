import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_password_set
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate
from app.models.task import Task, TaskAttachment
from app.models.user import User
from app.schemas.approval import ApprovalItem, BulkActionRequest, BulkActionResult

router = APIRouter(prefix="/approvals", tags=["approvals"])


def require_approver(user: User = Depends(require_password_set)) -> User:
    if not (user.role == "admin" or user.can_approve):
        raise HTTPException(status_code=403, detail="Approver access required")
    return user


class RejectRequest(BaseModel):
    note: str | None = None


async def _linked_task_ids(db: AsyncSession, document_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.scalars(
        select(TaskAttachment.task_id).where(TaskAttachment.document_id == document_id)
    )
    return list(result)


async def _check_task_auto_complete(db: AsyncSession, document_id: uuid.UUID) -> None:
    """PRD F8: "All pending attachments approved -> moves to Done
    automatically." Only a task already in 'submitted' is eligible —
    this fires once per approved attachment, and the task stays
    'submitted' until every attachment on it is active."""
    for task_id in await _linked_task_ids(db, document_id):
        task = await db.get(Task, task_id)
        if task is None or task.status != "submitted":
            continue
        statuses = await db.scalars(
            select(Document.status)
            .join(TaskAttachment, TaskAttachment.document_id == Document.id)
            .where(TaskAttachment.task_id == task_id)
        )
        if all(s == "active" for s in statuses):
            task.status = "done"


async def _mark_tasks_needs_attention(db: AsyncSession, document_id: uuid.UUID) -> None:
    """PRD F8: "Any attachment rejected -> returns to In progress with
    Needs attention: attachment rejected." regardless of the task's
    current status."""
    for task_id in await _linked_task_ids(db, document_id):
        task = await db.get(Task, task_id)
        if task is not None:
            task.status = "in_progress"
            task.needs_attention = True


async def _apply_decision(
    db: AsyncSession,
    approval: ApprovalRequest,
    action: str,
    note: str | None,
    reviewer: User,
) -> None:
    approval.status = "approved" if action == "approve" else "rejected"
    approval.reviewed_by = reviewer.id
    approval.review_note = note
    approval.reviewed_at = datetime.now(timezone.utc)

    if approval.type == "document_upload":
        doc = await db.get(Document, approval.document_id)
        if doc is None:
            # Not a silent skip: returning here would commit
            # approval.status without ever reaching the AuditLog below,
            # and CLAUDE.md §2.4 wants an audit row for every decision.
            raise HTTPException(status_code=404, detail="The item this approval refers to is gone")
        if action == "approve":
            if doc.integrity_check_failed:
                # PRD §10: a flagged document can only be rejected.
                raise HTTPException(
                    status_code=422,
                    detail="This file failed its integrity check and can only be rejected",
                )
            doc.status = "active"
            doc.approved_by = reviewer.id
            doc.approved_at = datetime.now(timezone.utc)
            await _check_task_auto_complete(db, doc.id)
        else:
            doc.status = "rejected"
            await _mark_tasks_needs_attention(db, doc.id)

    elif approval.type == "document_delete":
        doc = await db.get(Document, approval.document_id)
        if doc is None:
            # Not a silent skip: returning here would commit
            # approval.status without ever reaching the AuditLog below,
            # and CLAUDE.md §2.4 wants an audit row for every decision.
            raise HTTPException(status_code=404, detail="The item this approval refers to is gone")
        # PRD §8 document state machine: approve -> archived, reject ->
        # back to active (the file was live the whole time it was
        # delete_requested).
        doc.status = "archived" if action == "approve" else "active"

    elif approval.type == "task_reassign":
        task = await db.get(Task, approval.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="The item this approval refers to is gone")
        if action == "approve":
            task.assigned_to = approval.proposed_assignee
            # PRD F8: "the requester becomes 'assigned by'".
            task.assigned_by = approval.requested_by
        # Reject: task stays exactly as it was (PRD: "stays with the
        # current assignee until approved").

    elif approval.type == "task_delete":
        task = await db.get(Task, approval.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="The item this approval refers to is gone")
        if action == "approve":
            task.deleted = True

    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=f"approval.{approval.status}",
            entity_type="approval_request",
            entity_id=str(approval.id),
            detail={"type": approval.type, "note": note},
        )
    )


@router.get("", response_model=list[ApprovalItem])
async def list_approvals(
    deal_id: uuid.UUID | None = None,
    requested_by: uuid.UUID | None = None,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_approver),
) -> list[ApprovalItem]:
    # Two queries total. This used to run roughly five per pending row
    # (requester, document or task, deal, folder or both assignees), and
    # the deal_id filter was applied in Python afterwards, so a filtered
    # view still paid for every row in the queue.
    base = [ApprovalRequest.status == "pending"]
    if requested_by:
        base.append(ApprovalRequest.requested_by == requested_by)
    if type:
        base.append(ApprovalRequest.type == type)

    Requester = aliased(User)
    doc_query = (
        select(
            ApprovalRequest,
            Requester.display_name,
            Document.display_name,
            Deal.id,
            Deal.name,
            FolderTemplate.name,
        )
        .join(Requester, Requester.id == ApprovalRequest.requested_by)
        .join(Document, Document.id == ApprovalRequest.document_id)
        .join(Deal, Deal.id == Document.deal_id)
        .join(FolderTemplate, FolderTemplate.id == Document.folder_id)
        .where(*base, ApprovalRequest.type.in_(("document_upload", "document_delete")))
    )
    if deal_id:
        doc_query = doc_query.where(Deal.id == deal_id)

    items: list[ApprovalItem] = [
        ApprovalItem(
            id=approval.id,
            type=approval.type,
            deal_id=d_id,
            deal_name=deal_name,
            item_label=doc_name,
            item_sublabel=folder_name,
            document_id=approval.document_id,
            requested_by_name=requester_name,
            requested_at=approval.created_at,
            note=approval.requester_note,
        )
        for approval, requester_name, doc_name, d_id, deal_name, folder_name in await db.execute(
            doc_query
        )
    ]

    Current = aliased(User)
    Proposed = aliased(User)
    task_query = (
        select(
            ApprovalRequest,
            Requester.display_name,
            Deal.id,
            Deal.name,
            Deal.short_code,
            Task.sequence_number,
            Task.title,
            Current.display_name,
            Proposed.display_name,
        )
        .join(Requester, Requester.id == ApprovalRequest.requested_by)
        .join(Task, Task.id == ApprovalRequest.task_id)
        .join(Deal, Deal.id == Task.deal_id)
        .outerjoin(Current, Current.id == Task.assigned_to)
        .outerjoin(Proposed, Proposed.id == ApprovalRequest.proposed_assignee)
        .where(*base, ApprovalRequest.type.in_(("task_reassign", "task_delete")))
    )
    if deal_id:
        task_query = task_query.where(Deal.id == deal_id)

    for (
        approval,
        requester_name,
        d_id,
        deal_name,
        short_code,
        sequence_number,
        title,
        current_name,
        proposed_name,
    ) in await db.execute(task_query):
        items.append(
            ApprovalItem(
                id=approval.id,
                type=approval.type,
                deal_id=d_id,
                deal_name=deal_name,
                item_label=f"{short_code}-{sequence_number} {title}",
                item_sublabel=(
                    f"{current_name or 'Unassigned'} -> {proposed_name or ''}"
                    if approval.type == "task_reassign"
                    else None
                ),
                requested_by_name=requester_name,
                requested_at=approval.created_at,
                note=approval.requester_note,
            )
        )

    items.sort(key=lambda item: item.requested_at, reverse=True)
    return items


@router.post("/bulk", response_model=BulkActionResult)
async def bulk_action(
    body: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    reviewer: User = Depends(require_approver),
) -> BulkActionResult:
    result = BulkActionResult()
    for approval_id in body.ids:
        approval = await db.get(ApprovalRequest, approval_id)
        if approval is None or approval.status != "pending":
            # PRD F7: "11 approved, 1 already handled" — one already-
            # decided item doesn't fail the rest of the batch.
            result.already_handled += 1
            continue
        try:
            await _apply_decision(db, approval, body.action, body.note, reviewer)
            await db.commit()
            if body.action == "approve":
                result.approved += 1
            else:
                result.rejected += 1
        except HTTPException as e:
            await db.rollback()
            result.errors.append(f"{approval_id}: {e.detail}")
    return result


@router.post("/{approval_id}/approve")
async def approve_one(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    reviewer: User = Depends(require_approver),
) -> dict[str, str]:
    approval = await db.get(ApprovalRequest, approval_id)
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=409, detail="already_handled")
    await _apply_decision(db, approval, "approve", None, reviewer)
    await db.commit()
    return {"status": "approved"}


@router.post("/{approval_id}/reject")
async def reject_one(
    approval_id: uuid.UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    reviewer: User = Depends(require_approver),
) -> dict[str, str]:
    approval = await db.get(ApprovalRequest, approval_id)
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=409, detail="already_handled")
    await _apply_decision(db, approval, "reject", body.note, reviewer)
    await db.commit()
    return {"status": "rejected"}
