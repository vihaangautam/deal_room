"""Demo content: documents, tasks, comments and a populated approval
queue. Split from seed.py so it can land on a database that already has
the base cast — seed.py's guard skips everything once Samir exists, which
would mean an already-seeded machine never got any of this.

PRD §11: "Dummy documents only. Never real borrower files." Every file
here is a few bytes of generated placeholder text, named like the real
thing so the screens read correctly.

Each deal is seeded to demonstrate one thing:

  SHRM (Running)    the working deal — files in most folders, a pending
                    upload awaiting approval, a deletion request, six
                    tasks covering every status, comments with a reply
  MEHT (Successful) read-only: files that can be downloaded, not changed
  OBRT (Dropped)    the same, reopenable
  PTXL (New)        one early document, no tasks (PRD F8)

It also leaves one archived document so the Archive page and its
retention control have something to show.
"""

import asyncio
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.comment import Comment
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate
from app.models.task import Task, TaskAttachment
from app.models.user import User
from app.storage import ensure_bucket, put_object

NOW = datetime.now(timezone.utc)
TODAY = date.today()


def _dummy_pdf(label: str) -> bytes:
    """Small enough to seed instantly, shaped enough that a browser offers
    it as a PDF download rather than refusing to save it."""
    return f"%PDF-1.4\n% Lilkis Deal Room demo placeholder\n% {label}\n%%EOF\n".encode()


# (deal short_code, folder name, filename, status, uploader email, days ago)
DOCUMENTS: list[tuple[str, str, str, str, str, int]] = [
    # SHRM — the Running deal the demo spends most of its time in
    ("SHRM", "Minutes of the meeting", "Credit committee minutes 12 Sep.pdf", "active", "samir@lilkis.in", 26),
    ("SHRM", "Bank documents", "HDFC statement Apr 2026.pdf", "active", "rohan@lilkis.in", 21),
    ("SHRM", "Bank documents", "HDFC statement May 2026.pdf", "active", "rohan@lilkis.in", 14),
    ("SHRM", "Agreements", "Facility agreement executed.pdf", "active", "samir@lilkis.in", 12),
    ("SHRM", "Agreements", "Charge annexure.docx", "active", "rohan@lilkis.in", 11),
    ("SHRM", "Legal documents", "Legal opinion on security.pdf", "active", "samir@lilkis.in", 9),
    ("SHRM", "Borrower details", "KYC pack.pdf", "active", "samir@lilkis.in", 8),
    # pending: sits in the approval queue, and Rohan cannot see it (PRD F5)
    ("SHRM", "Security documents", "Hypothecation deed signed.pdf", "pending", "meera@lilkis.in", 1),
    # delete_requested: still downloadable, with a request waiting (PRD §10)
    ("SHRM", "Agreements", "Charge annexure superseded.docx", "delete_requested", "rohan@lilkis.in", 10),
    # archived: gives the Archive page a row
    ("SHRM", "Miscellaneous", "Site visit photos old.pdf", "archived", "rohan@lilkis.in", 30),
    # MEHT — closed successfully, everything read-only
    ("MEHT", "Agreements", "Facility agreement executed.pdf", "active", "samir@lilkis.in", 240),
    ("MEHT", "Bank documents", "Final repayment advice.pdf", "active", "rohan@lilkis.in", 95),
    ("MEHT", "Legal documents", "Security release letter.pdf", "active", "samir@lilkis.in", 90),
    # OBRT — dropped, reopenable
    ("OBRT", "Minutes of the meeting", "Initial evaluation note.pdf", "active", "samir@lilkis.in", 160),
    ("OBRT", "Borrower details", "Borrower profile.pdf", "active", "rohan@lilkis.in", 158),
    # PTXL — brand new, one early file
    ("PTXL", "Borrower details", "Inventory valuation draft.pdf", "active", "samir@lilkis.in", 3),
]

# (title, status, assignee email or None, assigned_by email or None,
#  priority, due in N days from today or None, needs_attention)
TASKS: list[tuple[str, str, str | None, str | None, str, int | None, bool]] = [
    ("Collect executed facility agreement", "done", "rohan@lilkis.in", "samir@lilkis.in", "high", -9, False),
    # submitted: its attachment is the pending upload, so approving that
    # upload moves this task to Done on its own (PRD F8)
    ("Verify hypothecation deed registration", "submitted", "meera@lilkis.in", "samir@lilkis.in", "high", 2, False),
    ("Chase HDFC for the May statement", "in_progress", "meera@lilkis.in", "samir@lilkis.in", "medium", 4, False),
    # needs_attention: a rejected attachment sent this one back
    ("Update the borrower KYC pack", "in_progress", "rohan@lilkis.in", "samir@lilkis.in", "medium", -2, True),
    ("Draft the security release checklist", "not_started", None, None, "low", 9, False),
    # Assigned to Samir so My Tasks is not empty for the account the
    # demo signs in with.
    ("Reconcile the sanction letter against drawdowns", "in_progress", "samir@lilkis.in", "samir@lilkis.in", "low", None, False),
]


async def _lookup(db: AsyncSession) -> tuple[dict[str, User], dict[str, Deal], dict[str, FolderTemplate]]:
    users = {u.email: u for u in await db.scalars(select(User))}
    deals = {d.short_code: d for d in await db.scalars(select(Deal))}
    folders = {f.name: f for f in await db.scalars(select(FolderTemplate))}
    return users, deals, folders


async def seed_content(db: AsyncSession) -> None:
    if await db.scalar(select(Document).limit(1)):
        print("Content already seeded — skipping documents, tasks and comments.")
        return

    users, deals, folders = await _lookup(db)
    if not users or not deals:
        print("No base seed found — run the base seed first.")
        return

    samir = users["samir@lilkis.in"]
    rohan = users["rohan@lilkis.in"]
    meera = users["meera@lilkis.in"]

    ensure_bucket()

    # ---------------------------------------------------------- documents
    created: dict[tuple[str, str], Document] = {}
    for code, folder_name, filename, status, uploader_email, days_ago in DOCUMENTS:
        deal, folder = deals[code], folders[folder_name]
        uploader = users[uploader_email]
        body = _dummy_pdf(f"{code} / {folder_name} / {filename}")
        moment = NOW - timedelta(days=days_ago)

        # The id is generated here rather than by the DB default, because
        # object_key is UNIQUE and derives from it: staging sixteen rows
        # with a placeholder key collides on the second one.
        doc_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            deal_id=deal.id,
            folder_id=folder.id,
            display_name=filename,
            original_name=filename,
            mime_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if filename.endswith(".docx")
                else "application/pdf"
            ),
            size_bytes=len(body),
            # Unique per deal, which the dedup index requires.
            sha256=hashlib.sha256(f"{code}:{filename}".encode()).hexdigest(),
            object_key=f"deals/{deal.id}/{doc_id}",
            status=status,
            uploaded_by=uploader.id,
            created_at=moment,
            updated_at=moment,
        )
        if status in ("active", "delete_requested", "archived"):
            doc.approved_by = samir.id
            doc.approved_at = moment
        db.add(doc)
        created[(code, filename)] = doc

    await db.flush()

    for (code, filename), doc in created.items():
        # The object has to exist or Download 404s against storage.
        put_object(doc.object_key, _dummy_pdf(f"{code} / {filename}"), doc.mime_type)
        db.add(
            AuditLog(
                actor_id=doc.uploaded_by,
                action="document.uploaded",
                entity_type="document",
                entity_id=str(doc.id),
                detail={"name": doc.display_name, "deal_id": str(doc.deal_id)},
                created_at=doc.created_at,
            )
        )

    pending_doc = created[("SHRM", "Hypothecation deed signed.pdf")]
    delete_doc = created[("SHRM", "Charge annexure superseded.docx")]
    archived_doc = created[("SHRM", "Site visit photos old.pdf")]

    # -------------------------------------------------------------- tasks
    sharma = deals["SHRM"]
    tasks: list[Task] = []
    for index, (title, status, assignee_email, assigned_by_email, priority, due_in, attention) in enumerate(
        TASKS, start=1
    ):
        task = Task(
            deal_id=sharma.id,
            sequence_number=index,
            title=title,
            status=status,
            priority=priority,
            needs_attention=attention,
            created_by=samir.id,
            due_date=(TODAY + timedelta(days=due_in)) if due_in is not None else None,
            created_at=NOW - timedelta(days=12 - index),
            updated_at=NOW - timedelta(days=max(0, 6 - index)),
        )
        if assignee_email:
            task.assigned_to = users[assignee_email].id
            task.assigned_by = users[assigned_by_email or "samir@lilkis.in"].id
        db.add(task)
        tasks.append(task)

    await db.flush()

    for task in tasks:
        db.add(
            AuditLog(
                actor_id=samir.id,
                action="task.created",
                entity_type="task",
                entity_id=str(task.id),
                detail={"title": task.title, "deal_id": str(sharma.id)},
                created_at=task.created_at,
            )
        )

    # The submitted task waits on the pending upload — approving that one
    # document in the queue is what moves this task to Done.
    db.add(TaskAttachment(task_id=tasks[1].id, document_id=pending_doc.id))
    # The done task has the executed agreement attached, already active.
    db.add(TaskAttachment(task_id=tasks[0].id, document_id=created[("SHRM", "Facility agreement executed.pdf")].id))
    # The needs-attention task points at the KYC pack it has to replace.
    db.add(TaskAttachment(task_id=tasks[3].id, document_id=created[("SHRM", "KYC pack.pdf")].id))

    # ----------------------------------------------------------- comments
    thread_root = Comment(
        deal_id=sharma.id,
        task_id=tasks[2].id,
        author_id=meera.id,
        body="HDFC say the May statement will be issued on the 3rd. I'll upload it the same day.",
        created_at=NOW - timedelta(days=2),
    )
    db.add(thread_root)
    await db.flush()
    db.add(
        Comment(
            deal_id=sharma.id,
            task_id=tasks[2].id,
            parent_id=thread_root.id,
            author_id=samir.id,
            body="Thanks — flag it to me if it slips past the 5th.",
            created_at=NOW - timedelta(days=2, hours=-3),
        )
    )
    db.add(
        Comment(
            deal_id=sharma.id,
            task_id=tasks[3].id,
            author_id=samir.id,
            body="The KYC pack is missing the updated board resolution. Please re-upload.",
            created_at=NOW - timedelta(days=1),
        )
    )
    # A deal-level comment, which is what the Activity tab's thread shows.
    db.add(
        Comment(
            deal_id=sharma.id,
            task_id=None,
            author_id=samir.id,
            body="Drawdown is scheduled for the 15th. Everything in Agreements needs to be final by then.",
            created_at=NOW - timedelta(days=4),
        )
    )

    # -------------------------------------------------- approval requests
    db.add(
        ApprovalRequest(
            type="document_upload",
            document_id=pending_doc.id,
            requested_by=meera.id,
            created_at=pending_doc.created_at,
        )
    )
    db.add(
        ApprovalRequest(
            type="document_delete",
            document_id=delete_doc.id,
            requested_by=rohan.id,
            requester_note="Superseded by the executed deed",
            created_at=NOW - timedelta(days=1, hours=6),
        )
    )
    db.add(
        ApprovalRequest(
            type="task_reassign",
            task_id=tasks[2].id,
            proposed_assignee=rohan.id,
            requested_by=rohan.id,
            created_at=NOW - timedelta(hours=20),
        )
    )
    # The archived document got there through an approved request, which is
    # what the Archive page reads its reason and approver from.
    db.add(
        ApprovalRequest(
            type="document_delete",
            document_id=archived_doc.id,
            requested_by=rohan.id,
            requester_note="Superseded by the September site visit report",
            status="approved",
            reviewed_by=samir.id,
            reviewed_at=NOW - timedelta(days=28),
            created_at=NOW - timedelta(days=29),
        )
    )

    await db.commit()
    print(
        f"Seeded content: {len(DOCUMENTS)} documents, {len(TASKS)} tasks on SHRM, "
        "4 comments (one a reply), 3 pending approvals, 1 archived file."
    )


async def main() -> None:
    from app.database import async_session_factory

    async with async_session_factory() as db:
        await seed_content(db)


if __name__ == "__main__":
    asyncio.run(main())
