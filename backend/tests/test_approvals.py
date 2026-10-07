"""PRD F7: bulk approve/reject and idempotency (CLAUDE.md §9)."""

import hashlib

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_folder, create_user, grant_access, login


async def _create_pending_upload(
    client: AsyncClient, deal_id: str, folder_id: str, content: bytes
) -> None:
    sha = hashlib.sha256(content).hexdigest()
    init = await client.post(
        f"/deals/{deal_id}/documents/init",
        json={
            "filename": f"{sha[:8]}.pdf",
            "size": len(content),
            "sha256": sha,
            "mime_type": "application/pdf",
            "folder_id": folder_id,
        },
    )
    doc_id = init.json()["doc_id"]
    await client.post(
        f"/upload/{doc_id}/chunk",
        data={"chunk_index": 0, "total_chunks": 1},
        files={"data": ("f.pdf", content, "application/pdf")},
    )
    await client.post(f"/upload/{doc_id}/complete")


async def test_bulk_approve_multiple_items(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    for i in range(3):
        await _create_pending_upload(client, str(deal.id), str(folder.id), f"file {i}".encode())

    await login(client, "admin@lilkis.in")
    ids = [a["id"] for a in (await client.get("/approvals")).json()]
    assert len(ids) == 3

    result = await client.post("/approvals/bulk", json={"ids": ids, "action": "approve"})
    body = result.json()
    assert body["approved"] == 3
    assert body["already_handled"] == 0

    assert (await client.get("/approvals")).json() == []


async def test_bulk_reject_with_note(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    await _create_pending_upload(client, str(deal.id), str(folder.id), b"reject me")

    await login(client, "admin@lilkis.in")
    ids = [a["id"] for a in (await client.get("/approvals")).json()]
    result = await client.post(
        "/approvals/bulk", json={"ids": ids, "action": "reject", "note": "not needed"}
    )
    assert result.json()["rejected"] == 1

    await login(client, "member@lilkis.in")
    docs = (await client.get(f"/deals/{deal.id}/documents")).json()
    assert docs[0]["status"] == "rejected"


async def test_one_already_decided_item_does_not_fail_the_rest(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PRD F7: "11 approved, 1 already handled" — a batch partially
    overlapping with an earlier decision still processes everything else."""
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    await _create_pending_upload(client, str(deal.id), str(folder.id), b"one")
    await _create_pending_upload(client, str(deal.id), str(folder.id), b"two")

    await login(client, "admin@lilkis.in")
    ids = [a["id"] for a in (await client.get("/approvals")).json()]

    # Decide the first one directly, then bulk-approve both — the first
    # id is already handled by the time the bulk call processes it.
    await client.post(f"/approvals/{ids[0]}/approve")

    result = await client.post("/approvals/bulk", json={"ids": ids, "action": "approve"})
    body = result.json()
    assert body["approved"] == 1
    assert body["already_handled"] == 1


async def test_single_approve_twice_returns_already_handled(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    await _create_pending_upload(client, str(deal.id), str(folder.id), b"content")

    await login(client, "admin@lilkis.in")
    approval_id = (await client.get("/approvals")).json()[0]["id"]

    first = await client.post(f"/approvals/{approval_id}/approve")
    assert first.status_code == 200

    second = await client.post(f"/approvals/{approval_id}/approve")
    assert second.status_code == 409
    assert second.json()["detail"] == "already_handled"


async def test_non_approver_cannot_see_or_decide_approvals(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")  # not an approver
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    await _create_pending_upload(client, str(deal.id), str(folder.id), b"content")

    list_resp = await client.get("/approvals")
    assert list_resp.status_code == 403


async def test_queue_lists_task_approvals_with_deal_filter(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The task half of the queue — reassignment sublabel and the deal_id
    filter. Both are built from outer joins to users that are NULL for an
    unassigned task or a task_delete request, which is exactly where a
    join rewrite goes wrong quietly.
    """
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    other = await create_user(db, "other@lilkis.in")
    deal = await create_deal(db, "AAA", admin.id)
    unrelated = await create_deal(db, "BBB", admin.id)

    await login(client, "admin@lilkis.in")
    task = (
        await client.post(
            f"/deals/{deal.id}/tasks", json={"title": "Chase the deed", "assignee_id": str(other.id)}
        )
    ).json()
    elsewhere = (
        await client.post(f"/deals/{unrelated.id}/tasks", json={"title": "Not this one"})
    ).json()

    # A member can't reassign or delete directly, so both land in the queue.
    await login(client, "member@lilkis.in")
    reassign = await client.post(
        f"/deals/{deal.id}/tasks/{task['id']}/assign", json={"assignee_id": str(member.id)}
    )
    assert reassign.status_code == 200, reassign.text
    assert (await client.request("DELETE", f"/deals/{unrelated.id}/tasks/{elsewhere['id']}")).json()[
        "status"
    ] == "delete_requested"

    await login(client, "admin@lilkis.in")
    queue = (await client.get("/approvals")).json()
    assert {item["type"] for item in queue} == {"task_reassign", "task_delete"}

    by_type = {item["type"]: item for item in queue}
    assert by_type["task_reassign"]["item_label"] == "AAA-1 Chase the deed"
    assert by_type["task_reassign"]["item_sublabel"] == "Other -> Member"
    assert by_type["task_reassign"]["deal_name"] == deal.name
    assert by_type["task_delete"]["item_sublabel"] is None

    filtered = (await client.get(f"/approvals?deal_id={deal.id}")).json()
    assert [item["type"] for item in filtered] == ["task_reassign"]
