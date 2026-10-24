"""The approver's note reaches the person who asked.

review_note was written on every decision from the start and read by
nothing, so the reject dialog's "Reason (shown to the requester)" was a
promise the app didn't keep — a file turned red and nobody was told why.
It is posted to the thread the request came from: the task's, when there
is one, otherwise the deal's.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.document import Document
from app.models.task import Task, TaskAttachment
from conftest import create_deal, create_folder, create_user, grant_access, login


async def _pending_upload(
    db: AsyncSession, deal_id, folder_id, uploader_id, *, on_task: Task | None = None
) -> ApprovalRequest:
    # documents_dedup_uq is (deal_id, sha256): two pending files in one
    # deal need two digests.
    unique = uuid.uuid4().hex
    doc = Document(
        deal_id=deal_id,
        folder_id=folder_id,
        display_name="KYC pack.pdf",
        original_name="KYC pack.pdf",
        mime_type="application/pdf",
        size_bytes=11,
        sha256=(unique * 2)[:64],
        object_key=f"deals/{deal_id}/kyc-{unique}",
        status="pending",
        uploaded_by=uploader_id,
    )
    db.add(doc)
    await db.flush()
    if on_task is not None:
        db.add(TaskAttachment(task_id=on_task.id, document_id=doc.id))
    approval = ApprovalRequest(
        type="document_upload", document_id=doc.id, requested_by=uploader_id
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def test_a_rejection_note_lands_in_the_deal_thread(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    meera = await create_user(db, "meera@lilkis.in")
    deal = await create_deal(db, "NOTE", admin.id)
    folder = await create_folder(db, "Bank documents", admin.id)
    await grant_access(db, meera.id, folder.id, "contribute", admin.id)
    approval = await _pending_upload(db, deal.id, folder.id, meera.id)

    await login(client, "admin@lilkis.in")
    resp = await client.post(
        "/approvals/bulk",
        json={
            "ids": [str(approval.id)],
            "action": "reject",
            "notes": {str(approval.id): "Missing the updated board resolution."},
        },
    )
    assert resp.json()["rejected"] == 1, resp.text

    # Meera, who asked, reads the answer where she already talks about
    # this deal — she is not an approver and never sees the queue.
    await login(client, "meera@lilkis.in")
    comments = (await client.get(f"/deals/{deal.id}/comments")).json()
    assert len(comments) == 1
    assert comments[0]["body"] == (
        "Rejected the upload of 'KYC pack.pdf' — Missing the updated board resolution."
    )
    assert comments[0]["author_name"] == admin.display_name


async def test_a_note_about_a_task_upload_lands_on_that_task(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Beside the work, not in the deal's general thread."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    meera = await create_user(db, "meera@lilkis.in")
    deal = await create_deal(db, "TSK", admin.id)
    folder = await create_folder(db, "Bank documents", admin.id)
    await grant_access(db, meera.id, folder.id, "contribute", admin.id)
    task = Task(deal_id=deal.id, sequence_number=1, title="Collect KYC", created_by=admin.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    approval = await _pending_upload(db, deal.id, folder.id, meera.id, on_task=task)

    await login(client, "admin@lilkis.in")
    await client.post(
        "/approvals/bulk",
        json={
            "ids": [str(approval.id)],
            "action": "reject",
            "notes": {str(approval.id): "Wrong borrower."},
        },
    )

    assert (await client.get(f"/deals/{deal.id}/comments")).json() == []
    on_task = (await client.get(f"/deals/{deal.id}/tasks/{task.id}/comments")).json()
    assert len(on_task) == 1
    assert on_task[0]["body"] == "Rejected the upload of 'KYC pack.pdf' — Wrong borrower."


async def test_a_bare_approval_says_nothing(client: AsyncClient, db: AsyncSession) -> None:
    """PRD F7 wants forty uploads approved in one action. Forty comments
    saying nothing is not a feature."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    meera = await create_user(db, "meera@lilkis.in")
    deal = await create_deal(db, "QUIET", admin.id)
    folder = await create_folder(db, "Bank documents", admin.id)
    await grant_access(db, meera.id, folder.id, "contribute", admin.id)
    approval = await _pending_upload(db, deal.id, folder.id, meera.id)

    await login(client, "admin@lilkis.in")
    resp = await client.post(
        "/approvals/bulk", json={"ids": [str(approval.id)], "action": "approve"}
    )
    assert resp.json()["approved"] == 1
    assert (await client.get(f"/deals/{deal.id}/comments")).json() == []

    # whitespace is nothing to say either
    second = await _pending_upload(db, deal.id, folder.id, admin.id)
    await client.post(
        "/approvals/bulk",
        json={"ids": [str(second.id)], "action": "approve", "notes": {str(second.id): "   "}},
    )
    assert (await client.get(f"/deals/{deal.id}/comments")).json() == []


async def test_a_row_reply_beats_the_batch_reason(client: AsyncClient, db: AsyncSession) -> None:
    """Rejecting twelve for one reason, but telling one person something
    of their own, is a single pass down the queue."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    meera = await create_user(db, "meera@lilkis.in")
    deal = await create_deal(db, "MIX", admin.id)
    folder = await create_folder(db, "Bank documents", admin.id)
    await grant_access(db, meera.id, folder.id, "contribute", admin.id)
    shared = await _pending_upload(db, deal.id, folder.id, meera.id)
    singled_out = await _pending_upload(db, deal.id, folder.id, admin.id)

    await login(client, "admin@lilkis.in")
    await client.post(
        "/approvals/bulk",
        json={
            "ids": [str(shared.id), str(singled_out.id)],
            "action": "reject",
            "note": "Stale as of the new sanction letter.",
            "notes": {str(singled_out.id): "This one is the wrong borrower entirely."},
        },
    )

    bodies = sorted(c["body"] for c in (await client.get(f"/deals/{deal.id}/comments")).json())
    assert bodies == [
        "Rejected the upload of 'KYC pack.pdf' — Stale as of the new sanction letter.",
        "Rejected the upload of 'KYC pack.pdf' — This one is the wrong borrower entirely.",
    ]


async def test_a_note_on_an_approved_task_deletion_goes_to_the_deal(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The approval takes the task's thread with it, so a note left there
    would be one nobody can reach."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    rohan = await create_user(db, "rohan@lilkis.in")
    deal = await create_deal(db, "DEL", admin.id)
    task = Task(deal_id=deal.id, sequence_number=4, title="Duplicate", created_by=rohan.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    approval = ApprovalRequest(type="task_delete", task_id=task.id, requested_by=rohan.id)
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    await login(client, "admin@lilkis.in")
    await client.post(
        "/approvals/bulk",
        json={
            "ids": [str(approval.id)],
            "action": "approve",
            "notes": {str(approval.id): "Agreed, SHRM-2 covers it."},
        },
    )

    bodies = [c["body"] for c in (await client.get(f"/deals/{deal.id}/comments")).json()]
    assert bodies == ["Approved the deletion of 'Duplicate' — Agreed, SHRM-2 covers it."]
