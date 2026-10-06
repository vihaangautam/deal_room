"""Login/logout/session plumbing only. We deliberately do NOT mount
fastapi-users' registration router — PRD F1 says accounts are created by
the admin (POST /admin/users, see routers/admin.py), never self-signup.
That narrows the whole fastapi-users integration down to one thing: making
authenticate() work, which only ever touches user.hashed_password (a
property on the User model — see models/user.py) and user.is_active
(already a real column). We never need is_superuser or is_verified."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import AccessToken, User


class UserDatabase(SQLAlchemyUserDatabase[User, uuid.UUID]):
    """The one write-side translation: when authenticate() upgrades a
    stored hash (e.g. after an Argon2 parameter change), it calls
    user_db.update(user, {"hashed_password": new_hash}) — translate that
    key to our real column name before delegating."""

    async def update(self, user: User, update_dict: dict) -> User:
        if "hashed_password" in update_dict:
            update_dict["hashed_pw"] = update_dict.pop("hashed_password")
        return await super().update(user, update_dict)


async def get_user_db(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[UserDatabase, None]:
    yield UserDatabase(session, User)


async def get_access_token_db(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase[AccessToken], None]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key


async def get_user_manager(
    user_db: UserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


cookie_transport = CookieTransport(
    cookie_name="lilkis_session",
    cookie_max_age=60 * 60 * 12,  # 12 hours — PRD F1
    # Secure requires HTTPS; the local dev server is plain HTTP, so a
    # Secure cookie would silently never be set/sent and login would look
    # broken. ARCHITECTURE.md's own code sample has this same dev/prod
    # split baked in via ENVIRONMENT.
    cookie_secure=settings.environment == "production",
    cookie_httponly=True,
    # PRD F1 says "SameSite=Strict" explicitly; ARCHITECTURE.md §7's code
    # sample says "lax". Going with PRD (the requirements doc) since the
    # two docs disagree — Strict still works fine here because
    # deals.lilkis.in and api.lilkis.in share the same registrable domain
    # (lilkis.in), which is what SameSite actually keys on.
    cookie_samesite="strict",
)


def get_database_strategy(
    access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken] = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=60 * 60 * 12)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
