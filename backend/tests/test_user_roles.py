"""PRD F9: the owner can make other admins; nobody can unmake the owner.

An admin is a grant that comes and goes with the people in the firm. The
owner is the fund sponsor the deal room belongs to — the one account that
has to still work tomorrow. Before this, PATCH /admin/users/{id} took
role, is_active and can_approve from any admin about any user, so a
promoted admin could demote or deactivate Samir and lock him out of his
own regulated document room.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from conftest import create_user, login


async def _cast(db: AsyncSession) -> tuple[User, User, User]:
    """Samir (owner), a second admin he promoted, and a member."""
    samir = await create_user(db, "samir@lilkis.in", role="admin")
    samir.is_owner = True
    samir.can_approve = True
    deputy = await create_user(db, "deputy@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    await db.commit()
    return samir, deputy, member


async def test_owner_can_promote_and_demote(client: AsyncClient, db: AsyncSession) -> None:
    _, _, member = await _cast(db)
    await login(client, "samir@lilkis.in")

    up = await client.patch(f"/admin/users/{member.id}", json={"role": "admin"})
    assert up.status_code == 200, up.text
    assert up.json()["role"] == "admin"

    down = await client.patch(f"/admin/users/{member.id}", json={"role": "member"})
    assert down.status_code == 200
    assert down.json()["role"] == "member"

    # and it is findable in the log as a role change, not buried in
    # user.updated rows
    actions = {r["action"] for r in (await client.get("/admin/audit-log")).json()}
    assert "user.role_changed" in actions


async def test_nobody_can_take_the_owners_access(client: AsyncClient, db: AsyncSession) -> None:
    samir, _, _ = await _cast(db)
    await login(client, "deputy@lilkis.in")

    for patch in ({"role": "member"}, {"is_active": False}, {"can_approve": False}):
        resp = await client.patch(f"/admin/users/{samir.id}", json=patch)
        assert resp.status_code == 403, f"{patch} was allowed: {resp.text}"

    await db.refresh(samir)
    assert (samir.role, samir.is_active, samir.can_approve) == ("admin", True, True)


async def test_the_owner_cannot_do_it_to_himself_either(
    client: AsyncClient, db: AsyncSession
) -> None:
    """No route to it at all — otherwise "nobody can" is only true of
    people who aren't holding the mouse."""
    samir, _, _ = await _cast(db)
    await login(client, "samir@lilkis.in")

    assert (await client.patch(f"/admin/users/{samir.id}", json={"role": "member"})).status_code == 403
    assert (
        await client.patch(f"/admin/users/{samir.id}", json={"is_active": False})
    ).status_code == 403


async def test_a_promoted_admin_cannot_mint_more_admins(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Both doors: promoting an existing member, and creating a new user
    who is an admin from the start."""
    _, _, member = await _cast(db)
    await login(client, "deputy@lilkis.in")

    promote = await client.patch(f"/admin/users/{member.id}", json={"role": "admin"})
    assert promote.status_code == 403

    created = await client.post(
        "/admin/users",
        json={"display_name": "Back Door", "email": "back@lilkis.in", "role": "admin"},
    )
    assert created.status_code == 403

    # everything else about managing users stays open to them (PRD §7)
    ok = await client.post(
        "/admin/users", json={"display_name": "Priya Nair", "email": "priya@lilkis.in"}
    )
    assert ok.status_code == 201, ok.text
    assert (await client.post(f"/admin/users/{member.id}/reset-password")).status_code == 200
    assert (
        await client.patch(f"/admin/users/{member.id}", json={"is_active": False})
    ).status_code == 200


async def test_an_admin_cannot_lock_themselves_out(client: AsyncClient, db: AsyncSession) -> None:
    _, deputy, _ = await _cast(db)
    await login(client, "deputy@lilkis.in")

    assert (
        await client.patch(f"/admin/users/{deputy.id}", json={"is_active": False})
    ).status_code == 403


async def test_without_an_owner_role_changes_work_as_before(
    client: AsyncClient, db: AsyncSession
) -> None:
    """A database seeded before the column existed has no owner. That has
    to degrade to the old behaviour, not lock role changes away from
    everyone with no way to set one."""
    await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    await login(client, "admin@lilkis.in")

    resp = await client.patch(f"/admin/users/{member.id}", json={"role": "admin"})
    assert resp.status_code == 200, resp.text


async def test_the_database_allows_only_one_owner(db: AsyncSession) -> None:
    """The app never writes is_owner, so the rule lives in the schema —
    which means a test has to reach past the API to prove it is really
    there and not just a comment."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    samir, _, _ = await _cast(db)
    second = await create_user(db, "pretender@lilkis.in", role="admin")
    second.is_owner = True

    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_an_admin_cannot_reset_the_owners_password(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The side door in the owner rules.

    Blocking role, is_active and can_approve on the owner is worth
    nothing if another admin can reset his password, read the temporary
    one off the response, and sign in as him — which is the account that
    makes and unmakes admins.
    """
    samir, _, _ = await _cast(db)
    await login(client, "deputy@lilkis.in")

    blocked = await client.post(f"/admin/users/{samir.id}/reset-password")
    assert blocked.status_code == 403, blocked.text

    # and the deputy can still reset an ordinary member's, which is the
    # part of the job that should keep working
    member = await create_user(db, "someone@lilkis.in")
    assert (await client.post(f"/admin/users/{member.id}/reset-password")).status_code == 200
