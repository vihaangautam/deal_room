"""PRD F4: folders appear in the same fixed order in every deal, so the
order is a property of the list, not of one folder."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_folder, create_user, login


async def test_reorder_rewrites_the_whole_list(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    first = await create_folder(db, "Bank documents", admin.id)
    second = await create_folder(db, "Legal documents", admin.id)
    third = await create_folder(db, "Agreements", admin.id)

    await login(client, "admin@lilkis.in")
    assert [f["name"] for f in (await client.get("/folders")).json()] == [
        "Bank documents",
        "Legal documents",
        "Agreements",
    ]

    resp = await client.post(
        "/folders/order", json={"folder_ids": [str(third.id), str(first.id), str(second.id)]}
    )
    assert resp.status_code == 200, resp.text
    assert [f["name"] for f in resp.json()] == ["Agreements", "Bank documents", "Legal documents"]
    # and the list endpoint agrees, so display_order really was written
    assert [f["name"] for f in (await client.get("/folders")).json()] == [
        "Agreements",
        "Bank documents",
        "Legal documents",
    ]


async def test_a_stale_list_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """A list missing a folder would quietly drop it to the bottom, which
    is what happens when the page was loaded before someone else added
    one."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    first = await create_folder(db, "Bank documents", admin.id)
    await create_folder(db, "Legal documents", admin.id)

    await login(client, "admin@lilkis.in")
    resp = await client.post("/folders/order", json={"folder_ids": [str(first.id)]})
    assert resp.status_code == 409


async def test_members_cannot_reorder(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    folder = await create_folder(db, "Bank documents", admin.id)
    await create_user(db, "member@lilkis.in")

    await login(client, "member@lilkis.in")
    resp = await client.post("/folders/order", json={"folder_ids": [str(folder.id)]})
    assert resp.status_code == 403
