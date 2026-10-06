"""Local dev / demo data. Run with: python -m app.seed

Matches PRD §11's demo cast exactly: Samir (admin, approver), Rohan
(Contribute everywhere except Borrower details = None), Meera (View
everywhere, Contribute on Bank documents). Deals/tasks are seeded
separately once their routers exist (Phase 1 steps 4+) — this script only
needs what auth and folder permissions depend on: users and folders.

Seeded users skip the forced-password-change flow (must_change_password
set False directly) so the demo isn't gated behind a change-password
screen — a real admin-created user still gets the normal forced-change
behavior from PRD F1, this is seed data only.
"""

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User

FOLDER_NAMES = [
    "Minutes of the meeting",
    "Bank documents",
    "Security documents",
    "Legal documents",
    "Agreements",
    "Government regulation special to the case",
    "Miscellaneous",
    "Borrower details",
]


async def seed() -> None:
    from fastapi_users.password import PasswordHelper

    password_helper = PasswordHelper()

    async with async_session_factory() as db:
        existing = await db.scalar(select(User).where(User.email == "samir@lilkis.in"))
        if existing:
            print("Already seeded — skipping.")
            return

        samir = User(
            email="samir@lilkis.in",
            display_name="Samir Biyani",
            hashed_pw=password_helper.hash("changeme123"),
            role="admin",
            can_approve=True,
            must_change_password=False,
        )
        rohan = User(
            email="rohan@lilkis.in",
            display_name="Rohan Kapoor",
            hashed_pw=password_helper.hash("changeme123"),
            role="member",
            must_change_password=False,
        )
        meera = User(
            email="meera@lilkis.in",
            display_name="Meera Shah",
            hashed_pw=password_helper.hash("changeme123"),
            role="member",
            must_change_password=False,
        )
        db.add_all([samir, rohan, meera])
        await db.flush()  # assigns ids without committing yet

        folders = {
            name: FolderTemplate(name=name, display_order=i, created_by=samir.id)
            for i, name in enumerate(FOLDER_NAMES)
        }
        db.add_all(folders.values())
        await db.flush()

        permissions = []
        for name, folder in folders.items():
            rohan_level = "none" if name == "Borrower details" else "contribute"
            permissions.append(
                UserFolderPermission(
                    user_id=rohan.id, folder_id=folder.id, access_level=rohan_level, granted_by=samir.id
                )
            )
            meera_level = "contribute" if name == "Bank documents" else "view"
            permissions.append(
                UserFolderPermission(
                    user_id=meera.id, folder_id=folder.id, access_level=meera_level, granted_by=samir.id
                )
            )
        db.add_all(permissions)

        await db.commit()
        print("Seeded: samir@lilkis.in, rohan@lilkis.in, meera@lilkis.in (password: changeme123)")


if __name__ == "__main__":
    asyncio.run(seed())
