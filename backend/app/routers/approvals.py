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
from app.models.comment import Comment
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


# What the decision was about, for the sentence posted to the thread.
DECISION_SUBJECT = {
    "document_upload": "the upload of",
    "document_delete": "the deletion of",
    "task_reassign": "the reassignment of",
    "task_delete": "the deletion of",
}


async def _post_decision_note(
    db: AsyncSession,
    approval: ApprovalRequest,
    action: str,
    note: str,
    reviewer: User,
    deal_id: uuid.UUID,
    task_id: uuid.UUID | None,
    item_name: str,
) -> None:
    """Put the reviewer's note where the person who asked will find it.

    review_note has been written on every decision since the beginning and
    read by nothing, so the reject dialog's "Reason (shown to the
    requester)" was a promise the app didn't keep: the file went red and
    nobody was told why.

    A comment rather than a field on the row, because the reply is the
    start of a conversation — "missing the board resolution" wants
    "re-uploaded, please look again" under it — and a string on a table
    cell is a dead end. It also costs no new screen: the thread is built,
    it has an unread-ish count in the tab bar, and everyone on the deal
    can see it, which is the nearest thing to a notification in an app
    whose PRD puts email in Phase 3.

    Only when there is something to say. A bare approval posts nothing —
    the file going active is the message, and PRD F7 wants forty of them
    to go through in one action without forty announcements.

    It goes to the task's thread when the request came from a task, so
    the answer lands beside the work; otherwise to the deal's.
    """
    verb = "Approved" if action == "approve" else "Rejected"
    db.add(
        Comment(
            deal_id=deal_id,
            task_id=task_id,
            author_id=reviewer.id,
            body=f"{verb} {DECISION_SUBJECT[approval.type]} '{item_name}' — {note.strip()}",
        )
    )


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

    # Filled in by whichever branch below runs, for the note comment.
    deal_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    item_name = ""

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
        deal_id, item_name = doc.deal_id, doc.display_name
        # An upload made from a task is answered in that task's thread.
        linked = await _linked_task_ids(db, doc.id)
        task_id = linked[0] if linked else None

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
        deal_id, item_name = doc.deal_id, doc.display_name
        linked = await _linked_task_ids(db, doc.id)
        task_id = linked[0] if linked else None

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
        deal_id, task_id, item_name = task.deal_id, task.id, task.title

    elif approval.type == "task_delete":
        task = await db.get(Task, approval.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="The item this approval refers to is gone")
        if action == "approve":
            task.deleted = True
        deal_id, item_name = task.deal_id, task.title
        # An approved deletion takes the thread with it, so the answer
        # goes to the deal instead — "deleted SHRM-4, it was a duplicate"
        # is exactly the note someone will go looking for, and a comment
        # inside a deleted task is a comment nobody can reach.
        task_id = None if action == "approve" else task.id

    if note and note.strip() and deal_id is not None:
        await _post_decision_note(
            db, approval, action, note, reviewer, deal_id, task_id, item_name
        )

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
            # A reply typed on the row beats the batch's shared reason.
            note = body.notes.get(approval_id) or body.note
            await _apply_decision(db, approval, body.action, note, reviewer)
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
