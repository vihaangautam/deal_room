#!/usr/bin/env bash
#
# Set a new temporary password for the owner, and force them to change
# it at next sign-in.
#
#   /opt/lilkis/ops/reset-owner-password.sh
#
# This exists because the UI deliberately cannot do it. Another admin
# resetting the owner's password would be able to read the temporary one
# and sign in as him — which is the account that makes and unmakes
# admins, so every other protection on it would be worth nothing. The
# API refuses, and the recovery path is this: a shell on the server,
# which is the right bar for taking over the account that owns
# everything.
#
# Use it when:
#   - the owner's password has been exposed and must be replaced
#   - the owner is locked out and nobody else can help them
#
# It prints the new password once, on this terminal. Read it to them
# directly. Do not paste it into chat, email or a ticket — that is how
# the first one leaked.

set -euo pipefail

LILKIS_DIR="${LILKIS_DIR:-/opt/lilkis}"
COMPOSE="docker compose -f ${LILKIS_DIR}/docker-compose.prod.yml"

${COMPOSE} exec -T api python - <<'PY'
import asyncio
import secrets

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User


async def main() -> None:
    async with async_session_factory() as db:
        owner = await db.scalar(select(User).where(User.is_owner.is_(True)))
        if owner is None:
            raise SystemExit("No owner in this database. Run app.bootstrap first.")

        # 16 chars from the same alphabet the add-user dialog uses: no
        # 0/O/1/l/I, because this gets read down a phone line.
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        temp = "".join(secrets.choice(alphabet) for _ in range(16))

        owner.hashed_pw = PasswordHelper().hash(temp)
        # The point of the exercise: whatever is printed below stops
        # working the moment they choose their own.
        owner.must_change_password = True
        await db.commit()

        print()
        print(f"  {owner.display_name} <{owner.email}>")
        print(f"  Temporary password:  {temp}")
        print()
        print("  They must change it at first sign-in. Read it to them;")
        print("  do not send it in writing.")
        print()


asyncio.run(main())
PY
