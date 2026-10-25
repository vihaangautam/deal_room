"""The first account on a fresh production database.

The deploy path had no way to create one: app.seed makes three demo
users with a known password, and nothing else created users at all. So
these check the two properties that make app.bootstrap safe to put in a
runbook — it makes an owner, and it will not make a second one.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap import create_owner
from app.models.user import User
from conftest import create_user


async def test_bootstrap_creates_one_owner_who_must_change_the_password(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILKIS_BOOTSTRAP_NAME", "Samir Biyani")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_EMAIL", "Samir@Lilkis.in")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_PASSWORD", "a-real-one-not-changeme")

    await create_owner(db)

    user = await db.scalar(select(User))
    assert user is not None
    assert user.display_name == "Samir Biyani"
    assert user.email == "samir@lilkis.in"  # lowercased: login looks it up by email
    assert (user.role, user.is_owner, user.can_approve) == ("admin", True, True)
    # PRD F1 — the password you read down the phone is not the one that
    # stays on the account.
    assert user.must_change_password is True
    assert "changeme" not in user.hashed_pw


async def test_bootstrap_refuses_once_anyone_exists(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dead end is the safety property: it cannot be used to add a
    quiet second admin, and running it twice does nothing the second
    time."""
    await create_user(db, "someone@lilkis.in")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_NAME", "Back Door")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_EMAIL", "back@lilkis.in")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_PASSWORD", "a-real-one-not-changeme")

    with pytest.raises(SystemExit):
        await create_owner(db)

    assert len((await db.scalars(select(User))).all()) == 1


async def test_bootstrap_creates_the_standard_folders(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PRD F4's folders only existed in app.seed, which must never run in
    production. So the first real deployment came up with none at all:
    sign in, make a deal, and there is nowhere to put a document."""
    from app.models.folder import FolderTemplate
    from app.seed import FOLDER_NAMES

    monkeypatch.setenv("LILKIS_BOOTSTRAP_NAME", "Samir Biyani")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_EMAIL", "samir@lilkis.in")
    monkeypatch.setenv("LILKIS_BOOTSTRAP_PASSWORD", "a-real-one-not-changeme")

    await create_owner(db)

    folders = (await db.scalars(select(FolderTemplate).order_by(FolderTemplate.display_order))).all()
    assert [f.name for f in folders] == FOLDER_NAMES
    # Roots, so the permission matrix has a column for each.
    assert all(f.parent_id is None and f.deal_id is None for f in folders)
