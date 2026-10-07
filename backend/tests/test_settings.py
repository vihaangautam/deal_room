"""PRD F11's two settings, and the round trip the Archive's retention
control makes.

"Keep forever" is the default and is stored as null, which the settings
table originally forbade — so the one choice an admin is most likely to
make was the one that returned a 500.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_user, login


async def test_retention_round_trips_through_every_choice(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_user(db, "admin@lilkis.in", role="admin")
    await login(client, "admin@lilkis.in")

    for days in (30, 365, 2555, None):  # PRD F11, ending on "Keep forever"
        resp = await client.patch("/admin/settings", json={"archive_retention_days": days})
        assert resp.status_code == 200, resp.text
        assert resp.json()["archive_retention_days"] == days
        # and it survives a reload, rather than only looking right in the
        # response the PATCH built from the object in memory
        assert (await client.get("/admin/settings")).json()["archive_retention_days"] == days


async def test_rejected_purge_window_is_fixed(client: AsyncClient, db: AsyncSession) -> None:
    """PRD F11: rejected_upload_purge_days is "30, fixed in v1" — readable
    so the UI can state it, with no way to change it."""
    await create_user(db, "admin@lilkis.in", role="admin")
    await login(client, "admin@lilkis.in")

    assert (await client.get("/admin/settings")).json()["rejected_upload_purge_days"] == 30

    await client.patch("/admin/settings", json={"rejected_upload_purge_days": 5})
    assert (await client.get("/admin/settings")).json()["rejected_upload_purge_days"] == 30


async def test_settings_are_admin_only(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "member@lilkis.in")
    await login(client, "member@lilkis.in")

    assert (await client.get("/admin/settings")).status_code == 403
    assert (
        await client.patch("/admin/settings", json={"archive_retention_days": 30})
    ).status_code == 403


async def test_new_user_can_be_given_a_password_and_copied_access(
    client: AsyncClient, db: AsyncSession
) -> None:
    """DESIGN §6.9's add-user dialog generates the temporary password in
    the browser so the admin can copy it before the user exists, and can
    seed folder access from an existing colleague. Both fields were
    accepted by the API long before anything sent them."""
    from conftest import create_folder

    admin = await create_user(db, "admin@lilkis.in", role="admin")
    legal = await create_folder(db, "Legal", admin.id)
    bank = await create_folder(db, "Bank documents", admin.id)
    await login(client, "admin@lilkis.in")

    resp = await client.post(
        "/admin/users",
        json={
            "display_name": "Priya Nair",
            "email": "priya@lilkis.in",
            "role": "member",
            "can_approve": False,
            "temporary_password": "dXjBY6yx7YNPw6",
            "folder_levels": {str(legal.id): "view", str(bank.id): "contribute"},
        },
    )
    assert resp.status_code == 201, resp.text
    # echoed back verbatim: the admin already read this one out
    assert resp.json()["temporary_password"] == "dXjBY6yx7YNPw6"

    # and it is the password that actually works, after the forced change
    await login(client, "priya@lilkis.in", "dXjBY6yx7YNPw6")
    assert (await client.get("/auth/me")).json()["must_change_password"] is True

    levels = (await client.get("/auth/my-permissions")).json()
    assert levels[str(legal.id)] == "view"
    assert levels[str(bank.id)] == "contribute"
