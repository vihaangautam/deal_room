import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
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
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate
from app.models.task import Task, TaskAttachment
from app.models.user import User
from app.schemas.document import (
    ALLOWED_MIME_EXTENSIONS,
    DocumentInitRequest,
    DocumentInitResponse,
)
from app.routers.upload import resolve_upload_slot
from app.schemas.task import (
    AssignRequest,
    AttachLinkRequest,
    StatusChangeRequest,
    TaskAttachmentItem,
    TaskCreate,
    TaskDetail,
    TaskListItem,
    TaskUpdate,
)

router = APIRouter(tags=["tasks"])


async def _get_running_deal(db: AsyncSession, deal_id: uuid.UUID) -> Deal:
    """PRD F8: tasks only exist on Running deals — ARCHITECTURE.md §3.5's
    exact acceptance criterion is a 404 tasks_disabled_for_stage, not 403,
    on every deal that isn't Running."""
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.stage != "running":
        raise HTTPException(status_code=404, detail="tasks_disabled_for_stage")
    return deal


async def _get_open_task(db: AsyncSession, deal_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    """Every task write path needs the same three checks: the task exists,
    it belongs to this deal, and the deal is still open — PRD F3 names
    "task edit" among the things a Successful or Dropped deal disables, and
    none of these handlers enforced that before. Keeping it here rather
    than in each handler is why a closed deal can't be edited through any
    of them. Reads (get_task, list) deliberately don't call this: F3 makes
    a closed deal read-only, not invisible."""
    task = await db.get(Task, task_id)
    if task is None or task.deleted or task.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Task not found")
    await require_open_deal(db, deal_id)
    return task


@router.get("/deals/{deal_id}/tasks", response_model=list[TaskListItem])
async def list_tasks(
    deal_id: uuid.UUID,
    assigned_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> list[TaskListItem]:
    deal = await _get_running_deal(db, deal_id)

    Assignee = User.__table__.alias("assignee")
    query = (
        select(Task, User.display_name, Assignee.c.display_name)
        .join(User, User.id == Task.created_by)
        .outerjoin(Assignee, Assignee.c.id == Task.assigned_to)
        .where(Task.deal_id == deal_id, Task.deleted.is_(False))
        .order_by(Task.sequence_number)
    )
    if assigned_to == "me":
        query = query.where(Task.assigned_to == user.id)

    rows = await db.execute(query)
    return [
        TaskListItem(
            id=task.id,
            key=f"{deal.short_code}-{task.sequence_number}",
            title=task.title,
            status=task.status,
            needs_attention=task.needs_attention,
            priority=task.priority,
            assignee_name=assignee_name,
            reporter_name=reporter_name,
            due_date=task.due_date,
            deal_id=task.deal_id,
            updated_at=task.updated_at,
        )
        for task, reporter_name, assignee_name in rows
    ]


@router.get("/tasks", response_model=list[TaskListItem])
async def my_tasks(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_password_set)
) -> list[TaskListItem]:
    """PRD F8 My Tasks: every task assigned to me across Running deals."""
    Assignee = User.__table__.alias("assignee")
    rows = await db.execute(
        select(Task, Deal.short_code, Deal.name, User.display_name, Assignee.c.display_name)
        .join(Deal, Deal.id == Task.deal_id)
        .join(User, User.id == Task.created_by)
        .outerjoin(Assignee, Assignee.c.id == Task.assigned_to)
        .where(Task.assigned_to == user.id, Task.deleted.is_(False), Deal.stage == "running")
        .order_by(Task.due_date.is_(None), Task.due_date)
    )
    return [
        TaskListItem(
            id=task.id,
            key=f"{short_code}-{task.sequence_number}",
            title=task.title,
            status=task.status,
            needs_attention=task.needs_attention,
            priority=task.priority,
            assignee_name=assignee_name,
            reporter_name=reporter_name,
            due_date=task.due_date,
            deal_id=task.deal_id,
            updated_at=task.updated_at,
            deal_name=deal_name,
        )
        for task, short_code, deal_name, reporter_name, assignee_name in rows
    ]


@router.post("/deals/{deal_id}/tasks", response_model=TaskDetail, status_code=201)
async def create_task(
    deal_id: uuid.UUID,
    body: TaskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    await _get_running_deal(db, deal_id)

    next_seq = (
        await db.scalar(
            select(func.coalesce(func.max(Task.sequence_number), 0) + 1).where(
                Task.deal_id == deal_id
            )
        )
    ) or 1

    task = Task(
        deal_id=deal_id,
        sequence_number=next_seq,
        title=body.title,
        description=body.description,
        priority=body.priority,
        start_date=body.start_date,
        due_date=body.due_date,
        created_by=user.id,
    )
    if body.assignee_id:
        # PRD F8: "Anyone can create and assign" — no approval needed,
        # this is an initial assignment, not a reassignment.
        task.assigned_to = body.assignee_id
        task.assigned_by = user.id

    db.add(task)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=user.id,
            action="task.created",
            entity_type="task",
            entity_id=str(task.id),
            detail={"deal_id": str(deal_id), "title": task.title},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    return await _task_detail(db, task.id, user)


async def _task_detail(db: AsyncSession, task_id: uuid.UUID, user: User) -> TaskDetail:
    task = await db.get(Task, task_id)
    if task is None or task.deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    deal = await db.get(Deal, task.deal_id)
    reporter = await db.get(User, task.created_by)
    assignee = await db.get(User, task.assigned_to) if task.assigned_to else None
    assigned_by = await db.get(User, task.assigned_by) if task.assigned_by else None

    pending_reassignment_to = None
    pending = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.type == "task_reassign",
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.status == "pending",
        )
    )
    if pending:
        target = await db.get(User, pending.proposed_assignee)
        pending_reassignment_to = target.display_name if target else None

    # PRD F6: an attachment in a folder the viewer can't see renders as
    # "Restricted document" — no name, size or link.
    folder_ids = await accessible_folder_ids(db, user)
    attachments: list[TaskAttachmentItem] = []
    attachment_rows = await db.execute(
        select(
            Document.id,
            Document.display_name,
            Document.folder_id,
            Document.status,
            FolderTemplate.name,
        )
        .join(TaskAttachment, TaskAttachment.document_id == Document.id)
        .join(FolderTemplate, FolderTemplate.id == Document.folder_id)
        .where(TaskAttachment.task_id == task_id)
    )
    for doc_id, display_name, folder_id, status, folder_name in attachment_rows:
        if folder_ids is not None and folder_id not in folder_ids:
            attachments.append(TaskAttachmentItem(document_id=doc_id, restricted=True))
            continue
        attachments.append(
            TaskAttachmentItem(
                document_id=doc_id,
                restricted=False,
                display_name=display_name,
                folder_name=folder_name,
                status=status,
            )
        )

    return TaskDetail(
        id=task.id,
        key=f"{deal.short_code}-{task.sequence_number}",
        deal_id=task.deal_id,
        title=task.title,
        description=task.description,
        status=task.status,
        needs_attention=task.needs_attention,
        priority=task.priority,
        assignee_id=task.assigned_to,
        assignee_name=assignee.display_name if assignee else None,
        reporter_id=task.created_by,
        reporter_name=reporter.display_name if reporter else "",
        assigned_by_id=task.assigned_by,
        assigned_by_name=assigned_by.display_name if assigned_by else None,
        start_date=task.start_date,
        due_date=task.due_date,
        created_at=task.created_at,
        updated_at=task.updated_at,
        pending_reassignment_to=pending_reassignment_to,
        attachments=attachments,
    )


@router.get("/deals/{deal_id}/tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    return await _task_detail(db, task_id, user)


def _can_edit_description(task: Task, user: User) -> bool:
    """PRD F8: anyone while unassigned; once assigned, only the
    assigned-by user and admin. Applied to the whole PATCH, not just the
    description field — PRD gives no separate rule for title/dates/
    priority, and gating only one field of one endpoint would be an
    inconsistent surface."""
    if user.role == "admin":
        return True
    if task.assigned_to is None:
        return True
    return task.assigned_by == user.id


@router.patch("/deals/{deal_id}/tasks/{task_id}", response_model=TaskDetail)
async def update_task(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    task = await _get_open_task(db, deal_id, task_id)
    if not _can_edit_description(task, user):
        raise HTTPException(
            status_code=403,
            detail="Only the person who assigned this task or an admin can edit it",
        )

    updates = body.model_dump(exclude_unset=True)
    new_start = updates.get("start_date", task.start_date)
    new_due = updates.get("due_date", task.due_date)
    if new_start and new_due and new_due < new_start:
        raise HTTPException(status_code=422, detail="due_date must not be before start_date")

    for field, value in updates.items():
        setattr(task, field, value)

    await db.commit()
    return await _task_detail(db, task_id, user)


@router.post("/deals/{deal_id}/tasks/{task_id}/assign", response_model=TaskDetail)
async def assign_task(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: AssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    task = await _get_open_task(db, deal_id, task_id)

    ip = request.client.host if request.client else None

    if task.assigned_to is None:
        # PRD F8: assigning an unassigned task (including self-assign)
        # never needs approval.
        task.assigned_to = body.assignee_id
        task.assigned_by = user.id
        db.add(
            AuditLog(
                actor_id=user.id,
                action="task.assigned",
                entity_type="task",
                entity_id=str(task.id),
                detail={"assignee_id": str(body.assignee_id)},
                ip_address=ip,
            )
        )
        await db.commit()
        return await _task_detail(db, task_id, user)

    if task.assigned_to == body.assignee_id:
        raise HTTPException(status_code=409, detail="Already assigned to this person")

    if user.role == "admin" or user.can_approve:
        # PRD F8: "Approvers reassign directly."
        task.assigned_to = body.assignee_id
        task.assigned_by = user.id
        db.add(
            AuditLog(
                actor_id=user.id,
                action="task.reassigned",
                entity_type="task",
                entity_id=str(task.id),
                detail={"assignee_id": str(body.assignee_id), "direct": True},
                ip_address=ip,
            )
        )
        await db.commit()
        return await _task_detail(db, task_id, user)

    existing = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.type == "task_reassign",
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.status == "pending",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A reassignment request is already pending")

    # PRD F8: "the task stays with the current assignee until approved."
    db.add(
        ApprovalRequest(
            type="task_reassign",
            task_id=task.id,
            proposed_assignee=body.assignee_id,
            requested_by=user.id,
        )
    )
    db.add(
        AuditLog(
            actor_id=user.id,
            action="task.reassignment_requested",
            entity_type="task",
            entity_id=str(task.id),
            detail={"assignee_id": str(body.assignee_id)},
            ip_address=ip,
        )
    )
    await db.commit()
    return await _task_detail(db, task_id, user)


def _can_change_status(task: Task, user: User, to_status: str) -> bool:
    if user.role == "admin":
        return True
    if task.status == "done" and to_status == "in_progress":
        # PRD F8 reopen: "Reporter, assigned by user or admin."
        return user.id in (task.created_by, task.assigned_by)
    # PRD F8: "The assignee, the assigned by user and admin."
    return user.id in (task.assigned_to, task.assigned_by)


@router.post("/deals/{deal_id}/tasks/{task_id}/status", response_model=TaskDetail)
async def change_status(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    task = await _get_open_task(db, deal_id, task_id)
    if not _can_change_status(task, user, body.status):
        raise HTTPException(status_code=403, detail="Access denied")

    task.status = body.status
    await db.commit()
    return await _task_detail(db, task_id, user)


@router.post("/deals/{deal_id}/tasks/{task_id}/submit", response_model=TaskDetail)
async def submit_task(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    """The single "Mark as done" / "Submit for approval" button (DESIGN.md
    §5.7) — the system decides which, per PRD F8's exact rule."""
    task = await _get_open_task(db, deal_id, task_id)
    if user.id not in (task.assigned_to, task.assigned_by) and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    statuses = await db.scalars(
        select(Document.status)
        .join(TaskAttachment, TaskAttachment.document_id == Document.id)
        .where(TaskAttachment.task_id == task_id)
    )
    statuses = list(statuses)
    has_pending = any(s in ("uploading", "pending") for s in statuses)

    task.status = "submitted" if has_pending else "done"
    task.needs_attention = False
    await db.commit()
    return await _task_detail(db, task_id, user)


@router.delete("/deals/{deal_id}/tasks/{task_id}")
async def request_delete_task(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> dict[str, str]:
    task = await _get_open_task(db, deal_id, task_id)

    ip = request.client.host if request.client else None

    if user.role == "admin" or user.can_approve:
        task.deleted = True
        db.add(
            AuditLog(
                actor_id=user.id,
                action="task.deleted",
                entity_type="task",
                entity_id=str(task.id),
                detail={"direct": True},
                ip_address=ip,
            )
        )
        await db.commit()
        return {"status": "deleted"}

    existing = await db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.type == "task_delete",
            ApprovalRequest.task_id == task_id,
            ApprovalRequest.status == "pending",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A deletion request is already pending")

    db.add(ApprovalRequest(type="task_delete", task_id=task.id, requested_by=user.id))
    db.add(
        AuditLog(
            actor_id=user.id,
            action="task.delete_requested",
            entity_type="task",
            entity_id=str(task.id),
            ip_address=ip,
        )
    )
    await db.commit()
    return {"status": "delete_requested"}


@router.post("/deals/{deal_id}/tasks/{task_id}/attachments/link", response_model=TaskDetail)
async def link_attachment(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: AttachLinkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> TaskDetail:
    await _get_open_task(db, deal_id, task_id)

    doc = await db.get(Document, body.document_id)
    if doc is None or doc.deal_id != deal_id or doc.status != "active":
        raise HTTPException(status_code=404, detail="Document not found")

    # PRD §7: linking needs View or Contribute on the document's folder.
    await check_folder_access(db, user, doc.folder_id, "view")

    existing = await db.scalar(
        select(TaskAttachment).where(
            TaskAttachment.task_id == task_id, TaskAttachment.document_id == doc.id
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already attached")

    db.add(TaskAttachment(task_id=task_id, document_id=doc.id))
    await db.commit()
    return await _task_detail(db, task_id, user)


@router.post(
    "/deals/{deal_id}/tasks/{task_id}/attachments/upload-init", response_model=DocumentInitResponse
)
async def init_attachment_upload(
    deal_id: uuid.UUID,
    task_id: uuid.UUID,
    body: DocumentInitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> DocumentInitResponse:
    """PRD F8 "Upload new": same rules as a normal upload (Contribute on
    the target folder) plus the resulting document is linked to the task
    immediately — "linked automatically". Chunk/complete are the same
    endpoints as a normal upload (routers/upload.py); they don't need to
    know about tasks at all, only this init step does."""
    await _get_open_task(db, deal_id, task_id)

    await check_folder_access(db, user, body.folder_id, "contribute")

    ext = Path(body.filename).suffix.lower()
    if ext not in ALLOWED_MIME_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Not allowed: {ext} files can't be uploaded.")

    resumable = await resolve_upload_slot(db, deal_id, body.sha256, user)
    if resumable is not None:
        # Same resume-vs-duplicate rule as a plain upload, so Retry works
        # here too. The attachment row may already exist from the first
        # attempt, hence the existence check below.
        link = await db.scalar(
            select(TaskAttachment).where(
                TaskAttachment.task_id == task_id, TaskAttachment.document_id == resumable.id
            )
        )
        if link is None:
            db.add(TaskAttachment(task_id=task_id, document_id=resumable.id))
            await db.commit()
        return DocumentInitResponse(doc_id=resumable.id)

    doc = Document(
        deal_id=deal_id,
        folder_id=body.folder_id,
        display_name=body.filename,
        original_name=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size,
        sha256=body.sha256,
        object_key="",
        status="uploading",
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    doc.object_key = f"deals/{deal_id}/{doc.id}"
    db.add(TaskAttachment(task_id=task_id, document_id=doc.id))
    await db.commit()
    return DocumentInitResponse(doc_id=doc.id)
