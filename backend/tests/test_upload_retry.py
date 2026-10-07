"""PRD F5 acceptance: "Failing one does not affect the rest; Retry
resumes only that file."

Retry re-runs init with the same hash. init writes a row with status
'uploading', and a failed chunk or complete() leaves it there — which is
one of the statuses the duplicate check blocks on, so Retry used to answer
409 "Already in Legal as 'deed.pdf'" and could never succeed.
"""

import hashlib

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_folder, create_user, grant_access, login

CONTENT = b"a signed deed"
SHA = hashlib.sha256(CONTENT).hexdigest()


def _init_body(folder_id: str) -> dict:
    return {
        "filename": "deed.pdf",
        "size": len(CONTENT),
        "sha256": SHA,
        "mime_type": "application/pdf",
        "folder_id": folder_id,
    }


async def _setup(db: AsyncSession) -> tuple[str, str]:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "RTRY", admin.id)
    folder = await create_folder(db, "Legal", admin.id)
    await grant_access(db, member.id, folder.id, "contribute", admin.id)
    return str(deal.id), str(folder.id)


async def test_retry_resumes_the_same_upload(client: AsyncClient, db: AsyncSession) -> None:
    deal_id, folder_id = await _setup(db)
    await login(client, "member@lilkis.in")

    first = await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))
    assert first.status_code == 200, first.text

    # No chunk sent: this is the stalled upload a Retry starts from.
    retry = await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))
    assert retry.status_code == 200, retry.text
    assert retry.json()["doc_id"] == first.json()["doc_id"]

    # And the retried upload goes on to complete normally.
    doc_id = retry.json()["doc_id"]
    await client.post(
        f"/upload/{doc_id}/chunk",
        data={"chunk_index": 0, "total_chunks": 1},
        files={"data": ("deed.pdf", CONTENT, "application/pdf")},
    )
    done = await client.post(f"/upload/{doc_id}/complete")
    assert done.json()["status"] == "pending"


async def test_a_real_duplicate_is_still_refused(client: AsyncClient, db: AsyncSession) -> None:
    """The resume path must not swallow the duplicate rule it sits in."""
    deal_id, folder_id = await _setup(db)
    await login(client, "member@lilkis.in")

    init = await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))
    doc_id = init.json()["doc_id"]
    await client.post(
        f"/upload/{doc_id}/chunk",
        data={"chunk_index": 0, "total_chunks": 1},
        files={"data": ("deed.pdf", CONTENT, "application/pdf")},
    )
    await client.post(f"/upload/{doc_id}/complete")

    again = await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))
    assert again.status_code == 409
    assert "Legal" in again.json()["detail"]


async def test_another_users_stalled_upload_is_a_duplicate(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Only your own stalled upload is resumable — otherwise one user's
    abandoned upload would hand its row to the next person to pick the
    same file."""
    deal_id, folder_id = await _setup(db)
    await login(client, "member@lilkis.in")
    await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))

    await login(client, "admin@lilkis.in")
    other = await client.post(f"/deals/{deal_id}/documents/init", json=_init_body(folder_id))
    assert other.status_code == 409
