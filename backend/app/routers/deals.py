import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_admin, require_password_set
from app.models.audit import AuditLog
from app.models.deal import Deal, DealStageHistory
from app.models.document import Document
from app.models.folder import UserFolderPermission
from app.models.task import Task
from app.models.user import User
from app.schemas.deal import (
    DealCreate,
    DealDetail,
    DealListItem,
    DealStageHistoryItem,
    DealUpdate,
    StageChangeRequest,
)

router = APIRouter(prefix="/deals", tags=["deals"])

# PRD §8's deal stage state machine. 'dropped' isn't here — reopening from
# dropped is handled separately below, since its target isn't a free
# choice, it's whatever the latest history row's from_stage was.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"running", "dropped"},
    "running": {"successful", "dropped"},
    "successful": set(),
}


async def _accessible_folder_ids(db: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """None means "every folder" (admin). Otherwise only folders with a
    non-'none' access_level row — matches ARCHITECTURE.md §2.2's
    resolution order."""
    if user.role == "admin":
        return None
    result = await db.scalars(
        select(UserFolderPermission.folder_id).where(
            UserFolderPermission.user_id == user.id,
            UserFolderPermission.access_level != "none",
        )
    )
    return list(result)


@router.get("", response_model=list[DealListItem])
async def list_deals(
    stage: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_password_set),
) -> list[DealListItem]:
    accessible_folder_ids = await _accessible_folder_ids(db, user)

    doc_count_filters = [Document.status == "active"]
    if accessible_folder_ids is not None:
        # Empty list is correct, not a bug: a member with no folder access
        # at all should see zero documents, and folder_id.in_([]) matches
        # nothing, which is exactly that.
        doc_count_filters.append(Document.folder_id.in_(accessible_folder_ids))

    doc_counts = (
        select(Document.deal_id, func.count(Document.id).label("cnt"))
        .where(*doc_count_filters)
        .group_by(Document.deal_id)
        .subquery()
    )
    task_counts = (
        select(
            Task.deal_id,
            func.count(Task.id).label("total"),
            func.sum(case((Task.status == "done", 1), else_=0)).label("done"),
        )
        .group_by(Task.deal_id)
        .subquery()
    )

    query = (
        select(
            Deal,
            func.coalesce(doc_counts.c.cnt, 0),
            func.coalesce(task_counts.c.done, 0),
            func.coalesce(task_counts.c.total, 0),
        )
        .outerjoin(doc_counts, doc_counts.c.deal_id == Deal.id)
        .outerjoin(task_counts, task_counts.c.deal_id == Deal.id)
    )
    if stage:
        query = query.where(Deal.stage == stage)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Deal.name.ilike(pattern),
                Deal.short_code.ilike(pattern),
                Deal.borrower.ilike(pattern),
            )
        )
    # "last activity" = deals.updated_at for now (bumped by the row's own
    # trigger). Not yet bumped by document/task/comment activity on the
    # deal, since those routers don't exist yet — revisit once they do.
    query = query.order_by(Deal.updated_at.desc())

    rows = await db.execute(query)
    return [
        DealListItem(
            id=deal.id,
            name=deal.name,
            short_code=deal.short_code,
            borrower=deal.borrower,
            stage=deal.stage,
            created_at=deal.created_at,
            updated_at=deal.updated_at,
            document_count=doc_count,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
        )
        for deal, doc_count, tasks_done, tasks_total in rows
    ]


@router.post("", response_model=DealDetail, status_code=201)
async def create_deal(
    body: DealCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Deal:
    short_code = body.short_code.upper()
    existing = await db.scalar(select(Deal).where(Deal.short_code == short_code))
    if existing:
        raise HTTPException(status_code=409, detail="A deal with this short code already exists")

    # Stage starts at New with no deal_stage_history row — a row only ever
    # records a *transition* (PRD F3), and the reason column is NOT NULL,
    # which creation has no equivalent field for.
    deal = Deal(
        name=body.name,
        short_code=short_code,
        borrower=body.borrower,
        summary=body.summary,
        created_by=admin.id,
    )
    db.add(deal)
    await db.flush()

    db.add(
        AuditLog(
            actor_id=admin.id,
            action="deal.created",
            entity_type="deal",
            entity_id=str(deal.id),
            detail={"name": deal.name, "short_code": deal.short_code},
            ip_address=request.client.host if request.client else None,
        )
    )
    await db.commit()
    await db.refresh(deal)
    return deal


@router.get("/{deal_id}", response_model=DealDetail)
async def get_deal(
    deal_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> Deal:
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealDetail)
async def update_deal(
    deal_id: uuid.UUID,
    body: DealUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Deal:
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(deal, field, value)

    await db.commit()
    await db.refresh(deal)
    return deal


@router.get("/{deal_id}/stage-history", response_model=list[DealStageHistoryItem])
async def get_stage_history(
    deal_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_password_set)
) -> list[DealStageHistory]:
    result = await db.scalars(
        select(DealStageHistory)
        .where(DealStageHistory.deal_id == deal_id)
        .order_by(DealStageHistory.changed_at.desc())
    )
    return list(result)


@router.post("/{deal_id}/stage", response_model=DealDetail)
async def change_stage(
    deal_id: uuid.UUID,
    body: StageChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Deal:
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.stage == "dropped":
        # Reopen: the only valid target is the stage recorded as from_stage
        # on the latest history row (PRD §8/F3's own wording — not a free
        # choice of New or Running).
        latest = await db.scalar(
            select(DealStageHistory)
            .where(DealStageHistory.deal_id == deal_id)
            .order_by(DealStageHistory.changed_at.desc())
            .limit(1)
        )
        if latest is None or body.to_stage != latest.from_stage:
            raise HTTPException(status_code=422, detail="invalid_transition")
    else:
        allowed = ALLOWED_TRANSITIONS.get(deal.stage, set())
        if body.to_stage not in allowed:
            raise HTTPException(status_code=422, detail="invalid_transition")

    from_stage = deal.stage
    deal.stage = body.to_stage
    db.add(
        DealStageHistory(
            deal_id=deal.id,
            from_stage=from_stage,
            to_stage=body.to_stage,
            changed_by=admin.id,
            reason=body.reason,
        )
    )
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="deal.stage_changed",
            entity_type="deal",
            entity_id=str(deal.id),
            detail={"from_stage": from_stage, "to_stage": body.to_stage, "reason": body.reason},
            ip_address=request.client.host if request.client else None,
        )
    )

    await db.commit()
    await db.refresh(deal)
    return deal
