"""Authorization primitives. ARCHITECTURE.md §2.2 sketches a single
require_folder_access(folder_id, level, ...) dependency that FastAPI would
auto-extract folder_id from the URL path for. That shape doesn't actually
fit this API: per ARCHITECTURE.md §3.4, no document/task route has
folder_id in its path — it's either in the request body (upload) or has to
be looked up from the document/task row itself (rename, download, delete,
attach). So check_folder_access is a plain function, called explicitly
inside each handler once it knows which folder_id is actually in play, not
a magic Depends(). require_admin has no such wrinkle — it only ever needs
the current user — so it stays a normal dependency.
"""

from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_user
from app.models.deal import Deal
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User


async def require_password_set(user: User = Depends(current_active_user)) -> User:
    """PRD F1: every endpoint except /auth/me and change-password returns
    403 password_change_required until a new user sets a real password.
    This is the dependency routers should use for "just give me the
    logged-in user" — current_active_user itself stays ungated so /auth/me
    and the change-password endpoint keep working for a user in this
    state."""
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="password_change_required")
    return user


def require_admin(user: User = Depends(require_password_set)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def permission_folder_id(db: AsyncSession, folder_id: UUID) -> UUID:
    """The folder whose permission row governs this one.

    Access is granted on roots — those are the columns in the admin's
    matrix. A subfolder takes whatever the viewer has on the root of its
    tree, at any depth, because folder_templates.root_id is stamped at
    creation: the alternative is walking parent_id up the chain on every
    file listing, which is a query per level for an answer that cannot
    change.

    Inheriting rather than granting per subfolder is also the safe
    default. A subfolder nobody has configured yet resolves to its root,
    so creating one inside Borrower details does not quietly publish it
    to everyone; it is as locked as the folder it sits in.
    """
    root = await db.scalar(select(FolderTemplate.root_id).where(FolderTemplate.id == folder_id))
    return root or folder_id


async def check_folder_access(
    db: AsyncSession,
    user: User,
    folder_id: UUID,
    level: Literal["view", "contribute"],
    deal_id: UUID | None = None,
) -> None:
    """ARCHITECTURE.md §2.2's resolution order: admin -> Contribute on
    every folder; otherwise the user_folder_permissions row; otherwise
    None (deny). Raises 403 — callers don't need to branch on the result,
    just call this before touching the document/folder.

    Pass deal_id wherever the folder came from the request body rather
    than from a document row. A root folder is global and fits any deal,
    but a subfolder belongs to one, and a Sharma subfolder id posted at
    the Patel deal would otherwise file a Patel document under a folder
    nobody looking at Patel can see. It lives here, in the call both
    upload paths already make, rather than in each of them.
    """
    if deal_id is not None:
        folder_deal = await db.scalar(
            select(FolderTemplate.deal_id).where(FolderTemplate.id == folder_id)
        )
        if folder_deal is not None and folder_deal != deal_id:
            raise HTTPException(status_code=404, detail="Folder not found")

    if user.role == "admin":
        return

    permission = await db.scalar(
        select(UserFolderPermission.access_level).where(
            UserFolderPermission.user_id == user.id,
            UserFolderPermission.folder_id == await permission_folder_id(db, folder_id),
        )
    )
    if permission is None or permission == "none":
        raise HTTPException(status_code=403, detail="Access denied")
    if level == "contribute" and permission == "view":
        raise HTTPException(status_code=403, detail="Access denied")


async def require_open_deal(db: AsyncSession, deal_id: UUID) -> Deal:
    """PRD F3: "Old deals (Successful or Dropped) are read-only. Upload,
    rename, delete request, task create, task edit and comment are
    disabled. Download still works."

    This was previously enforced only in upload.py, so the API accepted
    renames, deletion requests and comments on a closed deal even though
    the UI hid the controls — exactly the "the frontend won't let them"
    non-model CLAUDE.md §2.3 rules out. Call this in every write path on
    a deal-scoped resource.

    allow_uploads_when_closed deliberately does NOT exempt these: PRD F3
    scopes that flag to uploads only, so upload.py keeps its own check.
    """
    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.stage in ("successful", "dropped"):
        raise HTTPException(
            status_code=403, detail="This deal is closed. Files can be downloaded but not changed."
        )
    return deal


async def accessible_folder_ids(db: AsyncSession, user: User) -> list[UUID] | None:
    """None means "every folder" (admin). Otherwise only folders with a
    non-'none' access_level row. Shared by any list/count query that must
    filter by what the viewer can see — deals.py's document counts and
    documents.py's list both use this."""
    if user.role == "admin":
        return None
    granted = (
        select(UserFolderPermission.folder_id)
        .where(
            UserFolderPermission.user_id == user.id,
            UserFolderPermission.access_level != "none",
        )
        .scalar_subquery()
    )
    # The granted roots themselves, plus every subfolder hanging off one.
    # Listing only the roots would hide every document filed in a
    # subfolder from the people who can see the folder it is in.
    result = await db.scalars(
        select(FolderTemplate.id).where(
            or_(
                FolderTemplate.id.in_(granted),
                FolderTemplate.root_id.in_(granted),
            )
        )
    )
    return list(result)
