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


async def _seed_document(db, deal, folder, uploader, name, mime):
    """A document row plus its stored object, without going through the
    chunked upload — these tests only care about the download headers."""
    from app.models.document import Document
    from app.seed_content import _dummy_pdf
    from app.storage import put_object
    import hashlib, uuid as _uuid

    doc_id = _uuid.uuid4()
    doc = Document(
        id=doc_id,
        deal_id=deal.id,
        folder_id=folder.id,
        display_name=name,
        original_name=name,
        mime_type=mime,
        size_bytes=10,
        sha256=hashlib.sha256(name.encode()).hexdigest(),
        object_key=f"deals/{deal.id}/{doc_id}",
        status="active",
        uploaded_by=uploader.id,
    )
    db.add(doc)
    await db.commit()
    put_object(doc.object_key, _dummy_pdf(name), mime)
    return doc


async def test_pdfs_can_open_in_the_browser_but_other_types_cannot(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Clicking a filename should open a PDF in a tab rather than land it
    in Downloads. That is the Content-Disposition, not a viewer: PRD §3
    rules out in-browser preview, which the roadmap scopes as "PDF.js
    range requests" — an app-built viewer. This is the absence of one.

    A .docx asked for inline must still download, because a browser
    renders it as binary noise.
    """
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "VIEW", admin.id)
    folder = await create_folder(db, "Legal", admin.id)
    await login(client, "admin@lilkis.in")

    pdf = await _seed_document(db, deal, folder, admin, "deed.pdf", "application/pdf")
    docx = await _seed_document(
        db,
        deal,
        folder,
        admin,
        "annexure.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    base = f"/deals/{deal.id}/documents"

    # default stays a download, so the Download menu item still saves
    resp = await client.get(f"{base}/{pdf.id}/download", follow_redirects=False)
    assert "response-content-disposition=attachment" in resp.headers["location"].lower()

    resp = await client.get(f"{base}/{pdf.id}/download?inline=true", follow_redirects=False)
    assert "response-content-disposition=inline" in resp.headers["location"].lower()

    # a .docx cannot be displayed, so inline is ignored for it
    resp = await client.get(f"{base}/{docx.id}/download?inline=true", follow_redirects=False)
    assert "response-content-disposition=attachment" in resp.headers["location"].lower()


async def test_move_document_success_and_audit_log(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "MOVD", admin.id)
    folder1 = await create_folder(db, "Folder A", admin.id)
    folder2 = await create_folder(db, "Folder B", admin.id)
    await login(client, "admin@lilkis.in")

    doc = await _seed_document(db, deal, folder1, admin, "contract.pdf", "application/pdf")

    # Move doc from folder1 to folder2
    resp = await client.patch(
        f"/deals/{deal.id}/documents/{doc.id}/move",
        json={"folder_id": str(folder2.id)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["folder_id"] == str(folder2.id)

    # Check audit log in deal activity
    act_resp = await client.get(f"/deals/{deal.id}/activity")
    assert act_resp.status_code == 200
    activities = act_resp.json()
    move_act = next((a for a in activities if a["action"] == "document.moved"), None)
    assert move_act is not None
    assert move_act["detail"]["name"] == "contract.pdf"
    assert move_act["detail"]["from_folder"] == "Folder A"
    assert move_act["detail"]["to_folder"] == "Folder B"


async def test_move_document_rejects_same_folder(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "SAME", admin.id)
    folder1 = await create_folder(db, "Folder A", admin.id)
    await login(client, "admin@lilkis.in")

    doc = await _seed_document(db, deal, folder1, admin, "contract.pdf", "application/pdf")

    resp = await client.patch(
        f"/deals/{deal.id}/documents/{doc.id}/move",
        json={"folder_id": str(folder1.id)},
    )
    assert resp.status_code == 422
    assert "already in this folder" in resp.json()["detail"].lower()


async def test_archive_document_audit_log_includes_name(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "ARCH", admin.id)
    folder1 = await create_folder(db, "Folder A", admin.id)
    await login(client, "admin@lilkis.in")

    doc = await _seed_document(db, deal, folder1, admin, "secret_notes.pdf", "application/pdf")

    # Admin delete moves directly to archive
    resp = await client.request(
        "DELETE",
        f"/deals/{deal.id}/documents/{doc.id}",
        json={"reason": "cleanup test"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Activity log should show document.archived with name
    act_resp = await client.get(f"/deals/{deal.id}/activity")
    assert act_resp.status_code == 200
    activities = act_resp.json()
    arch_act = next((a for a in activities if a["action"] == "document.archived"), None)
    assert arch_act is not None
    assert arch_act["detail"]["name"] == "secret_notes.pdf"
    assert arch_act["detail"]["reason"] == "cleanup test"


