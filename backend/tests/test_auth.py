"""PRD F1: forced password change on first login, and the login lockout."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_user, login


async def test_new_user_must_change_password_before_anything_else(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_user(db, "new@lilkis.in", must_change_password=True)
    await login(client, "new@lilkis.in")

    # /auth/me stays reachable (the frontend needs it to detect this state)...
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    # ...but every other endpoint is gated.
    deals = await client.get("/deals")
    assert deals.status_code == 403
    assert deals.json()["detail"] == "password_change_required"


async def test_change_password_clears_the_gate(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "new@lilkis.in", must_change_password=True)
    await login(client, "new@lilkis.in")

    # Forced first-login change needs no current_password.
    resp = await client.post(
        "/auth/change-password", json={"new_password": "brandnewpassword123"}
    )
    assert resp.status_code == 200

    deals = await client.get("/deals")
    assert deals.status_code == 200


async def test_voluntary_password_change_requires_current_password(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_user(db, "set@lilkis.in", must_change_password=False)
    await login(client, "set@lilkis.in")

    missing = await client.post(
        "/auth/change-password", json={"new_password": "brandnewpassword123"}
    )
    assert missing.status_code == 400

    wrong = await client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "brandnewpassword123"},
    )
    assert wrong.status_code == 400

    correct = await client.post(
        "/auth/change-password",
        json={"current_password": "testpassword123", "new_password": "brandnewpassword123"},
    )
    assert correct.status_code == 200


async def test_lockout_after_five_failed_attempts(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "locktest@lilkis.in")

    for _ in range(5):
        resp = await client.post(
            "/auth/login", data={"username": "locktest@lilkis.in", "password": "wrong"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["locked"] is False

    sixth = await client.post(
        "/auth/login", data={"username": "locktest@lilkis.in", "password": "wrong"}
    )
    assert sixth.status_code == 400
    assert sixth.json()["detail"]["locked"] is True

    # Locked out even with the correct password.
    correct = await client.post(
        "/auth/login", data={"username": "locktest@lilkis.in", "password": "testpassword123"}
    )
    assert correct.status_code == 400
    assert correct.json()["detail"]["locked"] is True


async def test_deactivated_user_cannot_log_in(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db, "gone@lilkis.in")
    user.is_active = False
    await db.commit()

    resp = await client.post(
        "/auth/login", data={"username": "gone@lilkis.in", "password": "testpassword123"}
    )
    assert resp.status_code == 400
