"""Folders inside folders. PRD F4 said "No subfolders" until it didn't.

A root is the global template it always was — one row, shown in every
deal, and the thing the permission matrix has a column for. A subfolder
hangs off one and belongs to a single deal, so Sharma's "March 2026"
under Minutes is not a folder Patel ever sees. Nesting is unlimited, and
access is never set on a subfolder: it is whatever the viewer has on the
root of its tree.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from conftest import create_deal, create_folder, create_user, grant_access, login


async def _sub(client: AsyncClient, deal_id, parent_id, name: str) -> dict:
    resp = await client.post(
        f"/deals/{deal_id}/folders", json={"name": name, "parent_id": str(parent_id)}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_subfolders_nest_without_limit_and_carry_their_root(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "NEST", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await login(client, "admin@lilkis.in")

    march = await _sub(client, deal.id, minutes.id, "March 2026")
    week1 = await _sub(client, deal.id, march["id"], "Week 1")
    monday = await _sub(client, deal.id, week1["id"], "Monday")

    # root_id is stamped at creation at every depth, which is what keeps
    # the permission lookup one join instead of a walk.
    assert march["root_id"] == week1["root_id"] == monday["root_id"] == str(minutes.id)
    assert monday["depth"] == 3

    tree = (await client.get(f"/deals/{deal.id}/folders")).json()
    assert [(f["name"], f["depth"]) for f in tree] == [
        ("Minutes of the meeting", 0),
        ("March 2026", 1),
        ("Week 1", 2),
        ("Monday", 3),
    ]


async def test_a_subfolder_belongs_to_one_deal(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    sharma = await create_deal(db, "SHRM", admin.id)
    patel = await create_deal(db, "PTXL", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await login(client, "admin@lilkis.in")

    march = await _sub(client, sharma.id, minutes.id, "March 2026")

    # Patel sees the root and not Sharma's subfolder…
    patel_tree = (await client.get(f"/deals/{patel.id}/folders")).json()
    assert [f["name"] for f in patel_tree] == ["Minutes of the meeting"]

    # …and can have its own folder of the same name under the same root.
    await _sub(client, patel.id, minutes.id, "March 2026")

    # but not a second one, and not one nested under Sharma's.
    dupe = await client.post(
        f"/deals/{patel.id}/folders", json={"name": "March 2026", "parent_id": str(minutes.id)}
    )
    assert dupe.status_code == 409
    cross = await client.post(
        f"/deals/{patel.id}/folders", json={"name": "Week 1", "parent_id": march["id"]}
    )
    assert cross.status_code == 404


async def test_access_is_inherited_from_the_root(client: AsyncClient, db: AsyncSession) -> None:
    """The matrix has columns for roots only, so a subfolder has to take
    the root's level — and a new one inside a locked folder has to be
    born locked, not published to everyone."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    rohan = await create_user(db, "rohan@lilkis.in")
    deal = await create_deal(db, "INHR", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    borrower = await create_folder(db, "Borrower details", admin.id)
    await grant_access(db, rohan.id, minutes.id, "contribute", admin.id)
    # nothing granted on Borrower details: Rohan has none

    await login(client, "admin@lilkis.in")
    march = await _sub(client, deal.id, minutes.id, "March 2026")
    secret = await _sub(client, deal.id, borrower.id, "Promoter PAN")

    await login(client, "rohan@lilkis.in")
    levels = (await client.get("/auth/my-permissions")).json()
    assert levels[march["id"]] == "contribute"
    assert levels[secret["id"]] == "none"

    # and the API agrees, not just the map the sidebar reads
    allowed = await client.post(
        f"/deals/{deal.id}/documents/init",
        json={
            "folder_id": march["id"],
            "filename": "notes.pdf",
            "mime_type": "application/pdf",
            "size": 10,
            "sha256": "c" * 64,
        },
    )
    assert allowed.status_code == 200, allowed.text
    refused = await client.post(
        f"/deals/{deal.id}/documents/init",
        json={
            "folder_id": secret["id"],
            "filename": "pan.pdf",
            "mime_type": "application/pdf",
            "size": 10,
            "sha256": "d" * 64,
        },
    )
    assert refused.status_code == 403


async def test_documents_in_a_subfolder_are_visible_to_the_root_holder(
    client: AsyncClient, db: AsyncSession
) -> None:
    """accessible_folder_ids used to list only the granted rows, which
    would have hidden every file filed one level in."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    meera = await create_user(db, "meera@lilkis.in")
    deal = await create_deal(db, "VIS", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await grant_access(db, meera.id, minutes.id, "view", admin.id)

    await login(client, "admin@lilkis.in")
    march = await _sub(client, deal.id, minutes.id, "March 2026")

    db.add(
        Document(
            deal_id=deal.id,
            folder_id=uuid.UUID(march["id"]),
            display_name="board minutes.pdf",
            original_name="board minutes.pdf",
            mime_type="application/pdf",
            size_bytes=11,
            sha256="e" * 64,
            object_key=f"deals/{deal.id}/minutes",
            status="active",
            uploaded_by=admin.id,
        )
    )
    await db.commit()

    await login(client, "meera@lilkis.in")
    names = [d["display_name"] for d in (await client.get(f"/deals/{deal.id}/documents")).json()]
    assert names == ["board minutes.pdf"]


async def test_a_folder_with_subfolders_cannot_be_deleted(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "DEL", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await login(client, "admin@lilkis.in")
    march = await _sub(client, deal.id, minutes.id, "March 2026")

    blocked = await client.delete(f"/folders/{minutes.id}")
    assert blocked.status_code == 409
    assert "subfolder" in blocked.json()["detail"]

    # innermost first works
    assert (await client.delete(f"/folders/{march['id']}")).status_code == 204
    assert (await client.delete(f"/folders/{minutes.id}")).status_code == 204


async def test_the_admin_folder_list_stays_roots_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The permission matrix draws a column per row of GET /folders. A
    subfolder appearing there would offer access that is never read."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "ROOT", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await login(client, "admin@lilkis.in")
    await _sub(client, deal.id, minutes.id, "March 2026")

    assert [f["name"] for f in (await client.get("/folders")).json()] == [
        "Minutes of the meeting"
    ]


async def test_a_subfolder_id_from_another_deal_is_refused_on_upload(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The sidebar wouldn't offer it, which CLAUDE.md §2.3 says is not a
    security model."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    sharma = await create_deal(db, "SHRM", admin.id)
    patel = await create_deal(db, "PTXL", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    await login(client, "admin@lilkis.in")
    march = await _sub(client, sharma.id, minutes.id, "March 2026")

    resp = await client.post(
        f"/deals/{patel.id}/documents/init",
        json={
            "folder_id": march["id"],
            "filename": "stray.pdf",
            "mime_type": "application/pdf",
            "size": 10,
            "sha256": "f" * 64,
        },
    )
    assert resp.status_code == 404


async def test_a_subfolder_name_is_hidden_from_people_locked_out_of_its_root(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A root is listed locked (PRD F5) because its name is global and
    everyone knows it. "Promoter PAN" under Borrower details is not: the
    name itself says something about the borrower."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    rohan = await create_user(db, "rohan@lilkis.in")
    deal = await create_deal(db, "HIDE", admin.id)
    minutes = await create_folder(db, "Minutes of the meeting", admin.id)
    borrower = await create_folder(db, "Borrower details", admin.id)
    await grant_access(db, rohan.id, minutes.id, "view", admin.id)

    await login(client, "admin@lilkis.in")
    await _sub(client, deal.id, minutes.id, "March 2026")
    await _sub(client, deal.id, borrower.id, "Promoter PAN")

    await login(client, "rohan@lilkis.in")
    names = [f["name"] for f in (await client.get(f"/deals/{deal.id}/folders")).json()]
    assert "March 2026" in names  # he can see Minutes
    assert "Borrower details" in names  # the root still shows, to be locked
    assert "Promoter PAN" not in names
