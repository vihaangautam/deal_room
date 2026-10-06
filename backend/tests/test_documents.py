"""Upload flow, dedup rejection, and approval side-effects (CLAUDE.md §9)."""

import hashlib

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_folder, create_user, grant_access, login

FILE_BYTES = b"test file content for document upload tests"
SHA256 = hashlib.sha256(FILE_BYTES).hexdigest()


async def _upload(
    client: AsyncClient, deal_id: str, folder_id: str, filename: str = "test.pdf"
) -> dict:
    init = await client.post(
        f"/deals/{deal_id}/documents/init",
        json={
            "filename": filename,
            "size": len(FILE_BYTES),
            "sha256": SHA256,
            "mime_type": "application/pdf",
            "folder_id": folder_id,
        },
    )
    assert init.status_code == 200, init.text
    doc_id = init.json()["doc_id"]

    chunk = await client.post(
        f"/upload/{doc_id}/chunk",
        data={"chunk_index": 0, "total_chunks": 1},
        files={"data": (filename, FILE_BYTES, "application/pdf")},
    )
    assert chunk.status_code == 200, chunk.text

    complete = await client.post(f"/upload/{doc_id}/complete")
    assert complete.status_code == 200, complete.text
    return complete.json()


async def test_member_upload_goes_to_pending_and_creates_approval(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)

    await login(client, "member@lilkis.in")
    result = await _upload(client, str(deal.id), str(folder.id))
    assert result["status"] == "pending"

    await login(client, "admin@lilkis.in")
    approvals = await client.get("/approvals")
    assert len(approvals.json()) == 1
    assert approvals.json()[0]["type"] == "document_upload"


async def test_approver_own_upload_is_auto_approved(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    result = await _upload(client, str(deal.id), str(folder.id))
    assert result["status"] == "active"

    approvals = await client.get("/approvals")
    assert approvals.json() == []


async def test_duplicate_sha256_in_same_deal_is_refused(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    await _upload(client, str(deal.id), str(folder.id), filename="first.pdf")

    dup = await client.post(
        f"/deals/{deal.id}/documents/init",
        json={
            "filename": "second.pdf",
            "size": len(FILE_BYTES),
            "sha256": SHA256,
            "mime_type": "application/pdf",
            "folder_id": str(folder.id),
        },
    )
    assert dup.status_code == 409
    assert "first.pdf" in dup.json()["detail"]


async def test_duplicate_sha256_in_different_deal_is_allowed(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    deal_a = await create_deal(db, "AAAA", admin.id)
    deal_b = await create_deal(db, "BBBB", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    await _upload(client, str(deal_a.id), str(folder.id), filename="a.pdf")
    result = await _upload(client, str(deal_b.id), str(folder.id), filename="b.pdf")
    assert result["status"] == "active"


async def test_approving_upload_makes_it_active_and_visible(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    uploader = await create_user(db, "uploader@lilkis.in")
    viewer = await create_user(db, "viewer@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, uploader.id, folder.id, "contribute", admin.id)
    await grant_access(db, viewer.id, folder.id, "view", admin.id)

    await login(client, "uploader@lilkis.in")
    await _upload(client, str(deal.id), str(folder.id))

    await login(client, "admin@lilkis.in")
    approval_id = (await client.get("/approvals")).json()[0]["id"]
    approve = await client.post(f"/approvals/{approval_id}/approve")
    assert approve.status_code == 200

    # A view-only member (not the uploader) can now see the (formerly
    # hidden, pending) file.
    await login(client, "viewer@lilkis.in")
    docs = (await client.get(f"/deals/{deal.id}/documents")).json()
    assert len(docs) == 1
    assert docs[0]["status"] == "active"


async def test_rejecting_upload_marks_it_rejected_and_hides_it(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin", can_approve=True)
    member = await create_user(db, "member@lilkis.in")
    other_member = await create_user(db, "other@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)
    await grant_access(db, other_member.id, folder.id, "view", admin.id)

    await login(client, "member@lilkis.in")
    await _upload(client, str(deal.id), str(folder.id))

    await login(client, "admin@lilkis.in")
    approval_id = (await client.get("/approvals")).json()[0]["id"]
    reject = await client.post(f"/approvals/{approval_id}/reject", json={"note": "wrong file"})
    assert reject.status_code == 200

    # Rejected: visible to the uploader, not to another member.
    await login(client, "member@lilkis.in")
    own_docs = (await client.get(f"/deals/{deal.id}/documents")).json()
    assert own_docs[0]["status"] == "rejected"

    await login(client, "other@lilkis.in")
    other_docs = (await client.get(f"/deals/{deal.id}/documents")).json()
    assert other_docs == []


async def test_view_only_user_cannot_upload(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "TEST", admin.id)
    folder = await create_folder(db, "Agreements", admin.id)
    await grant_access(db, member.id, folder.id, "view", admin.id)

    await login(client, "member@lilkis.in")
    init = await client.post(
        f"/deals/{deal.id}/documents/init",
        json={
            "filename": "x.pdf",
            "size": 10,
            "sha256": "a" * 64,
            "mime_type": "application/pdf",
            "folder_id": str(folder.id),
        },
    )
    assert init.status_code == 403
