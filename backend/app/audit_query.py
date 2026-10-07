"""Reading the audit log, shared by the admin Activity page (PRD F10) and
a deal's own Activity tab (DESIGN.md §6.3).

Both need the same two things the raw table can't give them: who the actor
was by name, and which deal the row belongs to. Only `deal` rows carry a
deal id in entity_id — a document or task row carries its own id, so the
deal has to be resolved through that row. Doing it in one query here is
what keeps either caller from looping.
"""

import uuid
from datetime import datetime

from sqlalchemy import Select, Text, cast, func, or_, select
from sqlalchemy.orm import aliased

from app.models.audit import AuditLog
from app.models.deal import Deal
from app.models.document import Document
from app.models.task import Task
from app.models.user import User

MAX_ROWS = 200


def audit_query(
    *,
    deal_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
) -> Select:
    """Rows as (AuditLog, actor_name, deal_id, deal_name), newest first.

    entity_id is TEXT and does not always hold a UUID — a failed login
    writes the email that was typed — so the joins cast the UUID column to
    text rather than the other way round. Casting entity_id to uuid looks
    tidier and raises "invalid input syntax for type uuid" the moment one
    login row is in range, because the join condition is evaluated for
    every row regardless of the entity_type test beside it. Neither
    direction uses an index, which is fine at this table's size and under
    a LIMIT, but it is the first thing to look at if the log ever grows
    into the millions.
    """
    DealDirect = aliased(Deal)
    DealOfDocument = aliased(Deal)
    DealOfTask = aliased(Deal)

    query = (
        select(
            AuditLog,
            User.display_name,
            # The deal this row belongs to, whichever way it is reachable.
            func.coalesce(DealDirect.id, DealOfDocument.id, DealOfTask.id),
            func.coalesce(DealDirect.name, DealOfDocument.name, DealOfTask.name),
        )
        .outerjoin(User, User.id == AuditLog.actor_id)
        .outerjoin(
            DealDirect,
            (AuditLog.entity_type == "deal") & (cast(DealDirect.id, Text) == AuditLog.entity_id),
        )
        .outerjoin(
            Document,
            (AuditLog.entity_type == "document")
            & (cast(Document.id, Text) == AuditLog.entity_id),
        )
        .outerjoin(DealOfDocument, DealOfDocument.id == Document.deal_id)
        .outerjoin(
            Task,
            (AuditLog.entity_type == "task") & (cast(Task.id, Text) == AuditLog.entity_id),
        )
        .outerjoin(DealOfTask, DealOfTask.id == Task.deal_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(min(limit, MAX_ROWS))
    )

    if deal_id:
        query = query.where(
            or_(
                DealDirect.id == deal_id,
                DealOfDocument.id == deal_id,
                DealOfTask.id == deal_id,
            )
        )
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if action:
        query = query.where(AuditLog.action == action)
    if since:
        query = query.where(AuditLog.created_at >= since)
    if until:
        query = query.where(AuditLog.created_at <= until)

    return query


def to_audit_item(log: AuditLog, actor_name, deal_id, deal_name):
    """audit_query returns tuples; this is the one place that knows their
    shape. Imported lazily to keep app.schemas out of this module's import
    cycle with the routers."""
    from app.schemas.admin import AuditLogItem

    return AuditLogItem(
        id=log.id,
        actor_id=log.actor_id,
        actor_name=actor_name,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        detail=log.detail,
        deal_id=deal_id,
        deal_name=deal_name,
        created_at=log.created_at,
    )
