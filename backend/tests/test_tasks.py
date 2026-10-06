"""PRD F8: the task status machine and attachment-driven auto-complete
(CLAUDE.md §9)."""

import hashlib

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_folder, create_user, grant_access, login


async def _upload_attachment(
    client: AsyncClient, deal_id: str, task_id: str, folder_id: str, content: bytes
) -> str:
    sha = hashlib.sha256(content).hexdigest()
    init = await client.post(
        f"/deals/{deal_id}/tasks/{task_id}/attachments/upload-init",
        json={
            "filename": "attach.pdf",
            "size": len(content),
            "sha256": sha,
            "mime_type": "application/pdf",
            "folder_id": folder_id,
        },
    )
    assert init.status_code == 200, init.text
    doc_id = init.json()["doc_id"]
    await client.post(
        f"/upload/{doc_id}/chunk",
        data={"chunk_index": 0, "total_chunks": 1},
        files={"data": ("attach.pdf", content, "application/pdf")},
    )
    await client.post(f"/upload/{doc_id}/complete")
    return doc_id


async def test_tasks_disabled_on_non_running_deal(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "TEST", admin.id, stage="new")

    await login(client, "admin@lilkis.in")
    resp = await client.get(f"/deals/{deal.id}/tasks")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "tasks_disabled_for_stage"


async def test_task_key_is_short_code_plus_sequence(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "KRSN", admin.id)

    await login(client, "admin@lilkis.in")
    first = await client.post(f"/deals/{deal.id}/tasks", json={"title": "First"})
    second = await client.post(f"/deals/{deal.id}/tasks", json={"title": "Second"})
    assert first.json()["key"] == "KRSN-1"
    assert second.json()["key"] == "KRSN-2"


async def test_assigning_unassigned_task_is_immediate(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)

    await login(client, "member@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    resp = await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(member.id)}
    )
    assert resp.json()["assignee_name"] is not None
    assert resp.json()["assigned_by_name"] == "Member"


async def test_reassigning_assigned_task_needs_approval_unless_approver(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member_a = await create_user(db, "a@lilkis.in")
    member_b = await create_user(db, "b@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)

    await login(client, "admin@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(member_a.id)}
    )

    await login(client, "a@lilkis.in")
    resp = await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(member_b.id)}
    )
    body = resp.json()
    # PRD F8: "the task stays with the current assignee until approved."
    assert body["assignee_name"] != "B"
    assert body["pending_reassignment_to"] == "B"

    await login(client, "admin@lilkis.in")
    approval_id = (await client.get("/approvals")).json()[0]["id"]
    await client.post(f"/approvals/{approval_id}/approve")

    detail = (await client.get(f"/deals/{deal.id}/tasks/{task['id']}")).json()
    assert detail["assignee_name"] == "B"
    # PRD F8: "the requester becomes 'assigned by'".
    assert detail["assigned_by_name"] == "A"


async def test_submit_with_no_attachments_is_immediately_done(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "TEST", admin.id)

    await login(client, "admin@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    resp = await client.post(f"/deals/{deal.id}/tasks/{task['id']}/submit")
    assert resp.json()["status"] == "done"


async def test_submit_with_pending_attachment_is_submitted(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(admin.id)}
    )
    await _upload_attachment(client, str(deal.id), task["id"], str(folder.id), b"content a")

    resp = await client.post(f"/deals/{deal.id}/tasks/{task['id']}/submit")
    assert resp.json()["status"] == "submitted"


async def test_two_pending_attachments_both_must_approve_before_done(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The exact acceptance criterion from PRD F8."""
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(admin.id)}
    )
    # Approver's own upload auto-approves, so use a member to keep both
    # attachments genuinely pending.
    member = await create_user(db, "member@lilkis.in")
    await grant_access(db, member.id, folder.id, "contribute", admin.id)
    await login(client, "member@lilkis.in")
    await _upload_attachment(client, str(deal.id), task["id"], str(folder.id), b"content a")
    await _upload_attachment(client, str(deal.id), task["id"], str(folder.id), b"content b")

    await login(client, "admin@lilkis.in")
    submit = await client.post(f"/deals/{deal.id}/tasks/{task['id']}/submit")
    assert submit.json()["status"] == "submitted"

    approvals = (await client.get("/approvals?type=document_upload")).json()
    assert len(approvals) == 2

    await client.post(f"/approvals/{approvals[0]['id']}/approve")
    still_submitted = (await client.get(f"/deals/{deal.id}/tasks/{task['id']}")).json()
    assert still_submitted["status"] == "submitted"

    await client.post(f"/approvals/{approvals[1]['id']}/approve")
    now_done = (await client.get(f"/deals/{deal.id}/tasks/{task['id']}")).json()
    assert now_done["status"] == "done"


async def test_rejected_attachment_returns_task_to_in_progress_with_flag(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "admin@lilkis.in")
    task = (await client.post(f"/deals/{deal.id}/tasks", json={"title": "T"})).json()
    await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(member.id)}
    )

    await login(client, "member@lilkis.in")
    await _upload_attachment(client, str(deal.id), task["id"], str(folder.id), b"bad content")
    await client.post(f"/deals/{deal.id}/tasks/{task['id']}/submit")

    await login(client, "admin@lilkis.in")
    approval_id = (await client.get("/approvals?type=document_upload")).json()[0]["id"]
    await client.post(f"/approvals/{approval_id}/reject", json={"note": "wrong doc"})

    detail = (await client.get(f"/deals/{deal.id}/tasks/{task['id']}")).json()
    assert detail["status"] == "in_progress"
    assert detail["needs_attention"] is True


async def test_reopening_done_task_needs_reporter_assigned_by_or_admin(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    reporter = await create_user(db, "reporter@lilkis.in")
    doer = await create_user(db, "doer@lilkis.in")
    bystander = await create_user(db, "bystander@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)

    await login(client, "reporter@lilkis.in")
    task = (
        await client.post(
            f"/deals/{deal.id}/tasks", json={"title": "T", "assignee_id": str(doer.id)}
        )
    ).json()

    await login(client, "doer@lilkis.in")
    submit = await client.post(f"/deals/{deal.id}/tasks/{task['id']}/submit")
    assert submit.json()["status"] == "done"

    await login(client, "bystander@lilkis.in")
    denied = await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/status", json={"status": "in_progress"}
    )
    assert denied.status_code == 403

    # Reporter is NOT the assignee here — PRD F8 grants reopen power to
    # the reporter regardless, distinct from the assignee/assigned-by
    # rule that governs ordinary status changes.
    await login(client, "reporter@lilkis.in")
    allowed = await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/status", json={"status": "in_progress"}
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "in_progress"
