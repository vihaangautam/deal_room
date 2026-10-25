"""Create the first account on a fresh production database.

    docker compose -f docker-compose.prod.yml exec api python -m app.bootstrap

Until this existed there was no way into a production deployment at all:
the only account-creating code was app.seed, which makes three demo users
with the password 'changeme123' and must_change_password already False.
Running that on a public server publishes three accounts with a known
password and no forced change, so the honest state of the deploy path was
"either run the demo seed, or nobody can log in".

It creates exactly one user — admin, owner — and refuses to run if the
users table has anything in it. That refusal is the whole safety
property: it cannot be used to add a quiet second admin later, and
running it twice by accident does nothing the second time.

The password is read from a prompt that does not echo, or from
LILKIS_BOOTSTRAP_PASSWORD for an unattended install. It is never a
command-line argument: argv is visible to every process on the box
through `ps`, and it lands in the shell history file.
"""

import asyncio
import os
import sys

from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.folder import FolderTemplate
from app.models.user import User

# The one list, so production and the demo seed cannot drift apart on
# what Lilkis's folders are called.
from app.seed import FOLDER_NAMES

MIN_PASSWORD = 10  # matches ChangePasswordRequest in schemas/user.py


def _ask(prompt: str, env_var: str) -> str:
    value = os.environ.get(env_var)
    if value:
        return value.strip()
    if not sys.stdin.isatty():
        raise SystemExit(f"No terminal to ask on. Set {env_var}, or run with `exec -it`.")
    return input(prompt).strip()


def _ask_password() -> str:
    from getpass import getpass

    value = os.environ.get("LILKIS_BOOTSTRAP_PASSWORD")
    if value:
        return value
    if not sys.stdin.isatty():
        raise SystemExit(
            "No terminal to ask on. Set LILKIS_BOOTSTRAP_PASSWORD, or run with `exec -it`."
        )
    while True:
        first = getpass("Temporary password (not shown): ")
        if len(first) < MIN_PASSWORD:
            print(f"  Too short — {MIN_PASSWORD} characters or more.")
            continue
        if getpass("Again: ") != first:
            print("  Those don't match.")
            continue
        return first


async def create_owner(db: AsyncSession) -> None:
    """Takes the session rather than opening one, the same way
    seed_content does. The first version opened its own through
    async_session_factory, so the tests could not hand it the test
    database — it went straight at the development one instead, demo data
    and all."""
    existing = await db.scalar(select(func.count(User.id)))
    if existing:
        # Not an error to handle — a deliberate dead end. Adding the
        # second admin is something the running app does, with an audit
        # row and the owner's say-so (routers/admin).
        raise SystemExit(
            f"This database already has {existing} user(s). "
            "Bootstrap only ever creates the first one.\n"
            "Add more from Users & permissions, signed in as the owner."
        )

    print("Creating the first account. This person is the owner:")
    print("  - admin, and the only one who can make other admins")
    print("  - nobody, including them, can remove their access\n")

    display_name = _ask("Full name (e.g. Samir Biyani): ", "LILKIS_BOOTSTRAP_NAME")
    email = _ask("Email: ", "LILKIS_BOOTSTRAP_EMAIL").lower()
    if not display_name or "@" not in email:
        raise SystemExit("Need a name and a real email address.")

    password = _ask_password()

    owner = User(
        email=email,
        display_name=display_name,
        hashed_pw=PasswordHelper().hash(password),
        role="admin",
        is_owner=True,
        can_approve=True,
        # PRD F1. Unlike the demo seed, which skips this so the demo
        # isn't gated behind a password screen, a real first admin
        # changes the password you just read out to them.
        must_change_password=True,
    )
    db.add(owner)
    await db.flush()

    # PRD F4's global folders — Lilkis's actual filing structure, from the
    # PRD and the mockups, not demo content. They only existed in app.seed,
    # which must never run in production because it also creates three
    # accounts with a known password. So the first production deployment
    # came up with no folders at all: sign in, make a deal, and there is
    # nowhere to put a document.
    #
    # No permission rows. Admin bypasses that table, and there are no
    # members yet — the first one gets their access set when they are
    # added, which is deny-by-default until someone chooses otherwise.
    existing_folders = await db.scalar(select(func.count(FolderTemplate.id)))
    if not existing_folders:
        db.add_all(
            FolderTemplate(name=name, display_order=i, created_by=owner.id)
            for i, name in enumerate(FOLDER_NAMES)
        )

    await db.commit()

    print(f"\nCreated {display_name} <{email}>.")
    print("They are asked to choose a new password at first sign-in.")
    print("Give them this one directly. Don't email it.")


async def bootstrap() -> None:
    async with async_session_factory() as db:
        await create_owner(db)


if __name__ == "__main__":
    asyncio.run(bootstrap())
