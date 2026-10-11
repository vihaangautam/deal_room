"""Filtering and searching a deal's history.

audit_query accepted actor/action/date from the day it was written and
the deal endpoint dropped them, so a history could only be read by
scrolling. Keyword search is the genuinely new part: the other filters
need you to remember who acted and what they did, and nobody does — they
remember "the sanction letter".
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from conftest import create_deal, create_user, login


async def _history(client: AsyncClient, deal_id, **params) -> list[dict]:
    resp = await client.get(f"/deals/{deal_id}/activity", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_history_filters_narrow_and_combine(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    member = await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "HIST", admin.id)
    await login(client, "admin@lilkis.in")

    await client.post(f"/deals/{deal.id}/tasks", json={"title": "Chase the sanction letter"})
    await client.post(f"/deals/{deal.id}/tasks", json={"title": "File the charge annexure"})
    await client.post(
        f"/deals/{deal.id}/stage", json={"to_stage": "successful", "reason": "Closed out cleanly"}
    )

    everything = await _history(client, deal.id)
    assert len(everything) >= 3

    by_action = await _history(client, deal.id, action="task.created")
    assert {r["action"] for r in by_action} == {"task.created"}
    assert len(by_action) == 2

    # the member did nothing on this deal
    assert await _history(client, deal.id, actor_id=str(member.id)) == []

    # filters compose rather than replace one another
    combined = await _history(client, deal.id, action="task.created", actor_id=str(admin.id))
    assert len(combined) == 2


async def test_keyword_search_finds_what_people_remember(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "FIND", admin.id)
    await login(client, "admin@lilkis.in")

    await client.post(f"/deals/{deal.id}/tasks", json={"title": "Chase the sanction letter"})
    await client.post(f"/deals/{deal.id}/tasks", json={"title": "File the charge annexure"})
    await client.post(
        f"/deals/{deal.id}/stage",
        json={"to_stage": "successful", "reason": "Security released by the bank"},
    )

    # a task title, which lives in the detail blob
    hits = await _history(client, deal.id, q="sanction")
    assert len(hits) == 1
    assert "sanction" in str(hits[0]["detail"]).lower()

    # case-insensitive
    assert len(await _history(client, deal.id, q="SANCTION")) == 1

    # a stage-change reason, also in the detail blob
    assert len(await _history(client, deal.id, q="Security released")) == 1

    # the actor's name, which is on a joined table rather than the row
    assert len(await _history(client, deal.id, q="Samir")) == 0  # not this deal's admin
    assert len(await _history(client, deal.id, q=admin.display_name)) >= 3

    # the action itself
    assert len(await _history(client, deal.id, q="task.created")) == 2

    assert await _history(client, deal.id, q="nothing matches this") == []

    # blank search is not a filter
    assert len(await _history(client, deal.id, q="   ")) == len(await _history(client, deal.id))


async def test_search_does_not_cross_deals(client: AsyncClient, db: AsyncSession) -> None:
    """The deal scope must survive the keyword condition — otherwise one
    deal's history leaks into another's tab."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    mine = await create_deal(db, "MINE", admin.id)
    other = await create_deal(db, "OTHR", admin.id)
    await login(client, "admin@lilkis.in")

    await client.post(f"/deals/{mine.id}/tasks", json={"title": "Shared keyword here"})
    await client.post(f"/deals/{other.id}/tasks", json={"title": "Shared keyword here"})

    assert len(await _history(client, mine.id, q="Shared keyword")) == 1
    assert len(await _history(client, other.id, q="Shared keyword")) == 1
    # and the global log sees both
    both = (await client.get("/admin/audit-log", params={"q": "Shared keyword"})).json()
    assert len(both) == 2


async def test_history_is_admin_only(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    await create_user(db, "member@lilkis.in")
    deal = await create_deal(db, "PRIV", admin.id)

    await login(client, "member@lilkis.in")
    assert (await client.get(f"/deals/{deal.id}/activity")).status_code == 403
    assert (await client.get(f"/deals/{deal.id}/activity", params={"q": "x"})).status_code == 403
