"""PRD F3: "Old deals (Successful or Dropped) are read-only. Upload,
rename, delete request, task create, task edit and comment are disabled.
Download still works."

Before this suite existed the rule was enforced in upload.py only, so the
API happily renamed documents, accepted deletion requests, edited tasks and
posted comments on a closed deal — the UI hid the buttons, which CLAUDE.md
§2.3 explicitly rules out as a security model.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from conftest import create_deal, create_folder, create_user, login


async def _closed_deal_with_content(db: AsyncSession, stage: str) -> tuple[str, str, str]:
    """A deal that was Running long enough to grow a task and a document,
    then closed — the only way this state is reachable in the product."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "SHUT", admin.id)
    folder = await create_folder(db, "Legal", admin.id)

    doc = Document(
        deal_id=deal.id,
        folder_id=folder.id,
        display_name="deed.pdf",
        original_name="deed.pdf",
        mime_type="application/pdf",
        size_bytes=11,
        sha256="a" * 64,
        object_key=f"deals/{deal.id}/deed",
        status="active",
        uploaded_by=admin.id,
    )
    db.add(doc)
    await db.commit()

    from app.models.task import Task

    task = Task(
        deal_id=deal.id, sequence_number=1, title="Collect the deed", created_by=admin.id
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    deal.stage = stage
    await db.commit()
    return str(deal.id), str(task.id), str(doc.id)


async def test_closed_deal_rejects_every_write(client: AsyncClient, db: AsyncSession) -> None:
    deal_id, task_id, doc_id = await _closed_deal_with_content(db, "successful")
    await login(client, "admin@lilkis.in")

    writes = [
        client.patch(f"/deals/{deal_id}/documents/{doc_id}", json={"base_name": "renamed"}),
        client.request(
            "DELETE",
            f"/deals/{deal_id}/documents/{doc_id}",
            json={"reason": "no longer needed"},
        ),
        client.post(f"/deals/{deal_id}/comments", json={"body": "a late thought"}),
        client.post(f"/deals/{deal_id}/tasks/{task_id}/comments", json={"body": "a late thought"}),
        client.patch(f"/deals/{deal_id}/tasks/{task_id}", json={"title": "Renamed"}),
        client.post(f"/deals/{deal_id}/tasks/{task_id}/status", json={"status": "in_progress"}),
        client.post(f"/deals/{deal_id}/tasks/{task_id}/submit"),
        client.request("DELETE", f"/deals/{deal_id}/tasks/{task_id}"),
    ]
    for coro in writes:
        resp = await coro
        assert resp.status_code == 403, f"{resp.request.method} {resp.request.url} → {resp.text}"


async def test_dropped_deal_is_also_read_only(client: AsyncClient, db: AsyncSession) -> None:
    """A Dropped deal can be reopened, so it stays editable-looking in the
    UI in a way Successful doesn't — worth asserting separately."""
    deal_id, task_id, _ = await _closed_deal_with_content(db, "dropped")
    await login(client, "admin@lilkis.in")

    resp = await client.patch(f"/deals/{deal_id}/tasks/{task_id}", json={"title": "Renamed"})
    assert resp.status_code == 403


async def test_closed_deal_still_reads(client: AsyncClient, db: AsyncSession) -> None:
    """"Download still works" — and so must every read around it, or the
    guard has been pushed one layer too far."""
    deal_id, task_id, doc_id = await _closed_deal_with_content(db, "successful")
    await login(client, "admin@lilkis.in")

    assert (await client.get(f"/deals/{deal_id}/documents")).status_code == 200
    assert (await client.get(f"/deals/{deal_id}/tasks/{task_id}")).status_code == 200
    assert (await client.get(f"/deals/{deal_id}/comments")).status_code == 200

    download = await client.get(
        f"/deals/{deal_id}/documents/{doc_id}/download", follow_redirects=False
    )
    assert download.status_code == 302
