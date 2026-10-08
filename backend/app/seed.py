"""Local dev / demo data. Run with: python -m app.seed

Matches PRD §11's demo cast exactly: Samir (admin, approver), Rohan
(Contribute everywhere except Borrower details = None), Meera (View
everywhere, Contribute on Bank documents), and four deals — one per
stage — each with a stage-history reason, per §11's "four seeded deals:
New, Running, Successful, Dropped — each with reasons in its stage
history." Deal names match the ones already shown in the uiux/ mockups.

Seeded users skip the forced-password-change flow (must_change_password
set False directly) so the demo isn't gated behind a change-password
screen — a real admin-created user still gets the normal forced-change
behavior from PRD F1, this is seed data only.
"""

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.deal import Deal, DealStageHistory
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User
from app.seed_content import seed_content

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
            print("Base already seeded — skipping users, deals and folders.")
            # Not a bare return: the content seed has its own guard, and a
            # machine seeded before the content existed still needs it.
            await seed_content(db)
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
        await db.flush()

        # New: no history row (a deal starts at New with nothing to
        # record yet — see routers/deals.py create_deal).
        patel = Deal(
            name="Patel Textiles Ltd",
            short_code="PTXL",
            borrower="Patel Textiles Pvt Ltd",
            summary="Last-mile funding against finished-goods inventory",
            created_by=samir.id,
        )
        # Running: one transition, New -> Running.
        sharma = Deal(
            name="Sharma Infra Ltd",
            short_code="SHRM",
            borrower="Sharma & Co Infra",
            summary="Interim finance against receivables",
            stage="running",
            created_by=samir.id,
        )
        # Successful: New -> Running -> Successful.
        mehta = Deal(
            name="Mehta Logistics",
            short_code="MEHT",
            borrower="Mehta Logistics Pvt Ltd",
            summary="ARC co-investment, secured facility",
            stage="successful",
            created_by=samir.id,
        )
        # Dropped: New -> Running -> Dropped.
        oberoi = Deal(
            name="Oberoi Textiles",
            short_code="OBRT",
            borrower="Oberoi Textiles LLP",
            summary="IBC interim finance, under evaluation",
            stage="dropped",
            created_by=samir.id,
        )
        db.add_all([patel, sharma, mehta, oberoi])
        await db.flush()

        db.add_all(
            [
                DealStageHistory(
                    deal_id=sharma.id,
                    from_stage="new",
                    to_stage="running",
                    changed_by=samir.id,
                    reason="Term sheet signed, work begins",
                ),
                DealStageHistory(
                    deal_id=mehta.id,
                    from_stage="new",
                    to_stage="running",
                    changed_by=samir.id,
                    reason="Term sheet signed, work begins",
                ),
                DealStageHistory(
                    deal_id=mehta.id,
                    from_stage="running",
                    to_stage="successful",
                    changed_by=samir.id,
                    reason="Facility fully repaid, security released",
                ),
                DealStageHistory(
                    deal_id=oberoi.id,
                    from_stage="new",
                    to_stage="running",
                    changed_by=samir.id,
                    reason="Term sheet signed, work begins",
                ),
                DealStageHistory(
                    deal_id=oberoi.id,
                    from_stage="running",
                    to_stage="dropped",
                    changed_by=samir.id,
                    reason="Borrower withdrew application",
                ),
            ]
        )

        await db.commit()
        print("Seeded: samir@lilkis.in, rohan@lilkis.in, meera@lilkis.in (password: changeme123)")
        print("Seeded deals: PTXL (new), SHRM (running), MEHT (successful), OBRT (dropped)")
        await seed_content(db)


if __name__ == "__main__":
    asyncio.run(seed())
