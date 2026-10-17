"""The reason given for a stage change opens the deal's comment thread.

It used to land in deal_stage_history and the audit log and nowhere else,
both of which are admin-only (PRD §7) — so the one sentence explaining why
a deal had started was invisible to the people doing the work.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_user, login


async def test_stage_reason_becomes_the_first_comment(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "KICK", admin.id, stage="new")
    await login(client, "admin@lilkis.in")

    assert (await client.get(f"/deals/{deal.id}/comments")).json() == []

    resp = await client.post(
        f"/deals/{deal.id}/stage",
        json={"to_stage": "running", "reason": "Sanction letter received, drawdown on the 15th."},
    )
    assert resp.status_code == 200, resp.text

    # A member, who cannot open the history at all, reads it in the thread.
    await login(client, "member@lilkis.in")
    comments = (await client.get(f"/deals/{deal.id}/comments")).json()
    assert len(comments) == 1
    assert comments[0]["body"] == (
        "Moved to Running — Sanction letter received, drawdown on the 15th."
    )
    assert comments[0]["author_name"] == admin.display_name


async def test_closing_a_deal_still_posts_its_reason(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The close happens before the thread goes read-only (PRD F3), so the
    direct insert has to bypass the open-deal guard that /comments uses."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "SHUT", admin.id, stage="new")
    await login(client, "admin@lilkis.in")

    await client.post(f"/deals/{deal.id}/stage", json={"to_stage": "running", "reason": "Started."})
    await client.post(
        f"/deals/{deal.id}/stage", json={"to_stage": "dropped", "reason": "Promoter withdrew."}
    )

    bodies = [c["body"] for c in (await client.get(f"/deals/{deal.id}/comments")).json()]
    assert bodies == ["Moved to Running — Started.", "Moved to Dropped — Promoter withdrew."]

    # and the thread is now closed to anything new
    posted = await client.post(f"/deals/{deal.id}/comments", json={"body": "one more thought"})
    assert posted.status_code == 403
