from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    UserManager,
    auth_backend,
    current_active_user,
    fastapi_users,
    get_database_strategy,
    get_user_manager,
)
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserMe

router = APIRouter(prefix="/auth", tags=["auth"])

# Only /auth/logout from fastapi-users' own router — its /login doesn't
# support the lockout + identical-error-message requirements in PRD F1, so
# login is fully custom below. Filtering routes rather than mounting the
# whole router avoids registering two competing POST /auth/login handlers.
_library_auth_router = fastapi_users.get_auth_router(auth_backend)
router.routes.extend(r for r in _library_auth_router.routes if r.path.endswith("/logout"))

FAILED_LOGIN_WINDOW = timedelta(minutes=15)
FAILED_LOGIN_THRESHOLD = 5


@router.post("/login")
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    db: AsyncSession = Depends(get_db),
    strategy: DatabaseStrategy = Depends(get_database_strategy),
):
    email = credentials.username
    ip = request.client.host if request.client else None

    window_start = datetime.now(timezone.utc) - FAILED_LOGIN_WINDOW
    recent_failures = await db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "auth.login_failed",
            AuditLog.entity_type == "login",
            AuditLog.entity_id == email,
            AuditLog.created_at >= window_start,
        )
    )
    locked = recent_failures >= FAILED_LOGIN_THRESHOLD

    # Skip authenticate() entirely when locked — no point hashing/verifying
    # a password for an account we're about to reject regardless.
    user = None if locked else await user_manager.authenticate(credentials)

    if user is None or locked:
        db.add(
            AuditLog(
                action="auth.login_failed",
                entity_type="login",
                entity_id=email,
                ip_address=ip,
            )
        )
        await db.commit()
        # Same body for unknown email, wrong password AND lockout (PRD
        # F1) — `locked` is the one extra bit the frontend needs, to
        # append "Try again in 15 minutes." (DESIGN.md §6.1). The
        # rendered text itself stays identical either way.
        raise HTTPException(
            status_code=400, detail={"message": "LOGIN_BAD_CREDENTIALS", "locked": locked}
        )

    db.add(
        AuditLog(
            actor_id=user.id,
            action="auth.login_succeeded",
            entity_type="login",
            entity_id=email,
            ip_address=ip,
        )
    )
    await db.commit()

    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    return response


@router.get("/me", response_model=UserMe)
async def me(user: User = Depends(current_active_user)) -> User:
    return user


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
) -> dict[str, str]:
    # Forced first-login change needs no current_password — logging in
    # with the temp password already proved identity (DESIGN.md §6.1). A
    # voluntary change on an already-set-up account must re-verify it, so
    # a left-open session can't be used to silently take over the account.
    if not user.must_change_password:
        if body.current_password is None:
            raise HTTPException(status_code=400, detail="current_password is required")
        verified, _ = user_manager.password_helper.verify_and_update(
            body.current_password, user.hashed_password
        )
        if not verified:
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = user_manager.password_helper.hash(body.new_password)
    await user_manager.user_db.update(
        user, {"hashed_password": new_hash, "must_change_password": False}
    )
    return {"status": "ok"}
