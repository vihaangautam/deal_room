"""The Archive is this app's Recently Deleted, so a row has to say how
long is left on it.

Restore and permanent delete were already here; what was missing is the
deadline. It is computed server-side from the same setting and the same
timestamp jobs/purge.purge_archived sweeps on, because a browser working
it out from archive_retention_days is a second definition of the
deadline, free to drift from the job that actually enforces it.
"""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from conftest import create_deal, create_folder, create_user, login


async def _archived(db: AsyncSession, deal_id, folder_id, uploader_id, days_ago: int) -> Document:
    doc = Document(
        deal_id=deal_id,
        folder_id=folder_id,
        display_name=f"superseded-{days_ago}.pdf",
        original_name="superseded.pdf",
        mime_type="application/pdf",
        size_bytes=11,
        sha256=f"{days_ago:064d}",
        object_key=f"deals/{deal_id}/old-{days_ago}",
        status="archived",
        uploaded_by=uploader_id,
        updated_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(doc)
    await db.commit()
    return doc


async def test_keep_forever_means_no_deadline(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "KEEP", admin.id)
    folder = await create_folder(db, "Legal", admin.id)
    await _archived(db, deal.id, folder.id, admin.id, days_ago=400)

    await login(client, "admin@lilkis.in")
    rows = (await client.get("/admin/archive")).json()
    assert len(rows) == 1
    # The default (PRD F11) destroys nothing, so the row cannot claim a
    # date the purge job will never act on.
    assert rows[0]["purge_after"] is None


async def test_the_deadline_matches_what_the_job_would_sweep(
    client: AsyncClient, db: AsyncSession
) -> None:
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "DUE", admin.id)
    folder = await create_folder(db, "Legal", admin.id)
    fresh = await _archived(db, deal.id, folder.id, admin.id, days_ago=2)
    stale = await _archived(db, deal.id, folder.id, admin.id, days_ago=40)

    await login(client, "admin@lilkis.in")
    await client.patch("/admin/settings", json={"archive_retention_days": 30})

    rows = {r["display_name"]: r for r in (await client.get("/admin/archive")).json()}
    deadlines = {
        name: datetime.fromisoformat(row["purge_after"]) for name, row in rows.items()
    }
    assert deadlines[fresh.display_name] == fresh.updated_at + timedelta(days=30)
    # Already past: the job hasn't run yet, so the row is still here and
    # still recoverable, and the UI says "Due for deletion".
    assert deadlines[stale.display_name] < datetime.now(timezone.utc)

    # and the job agrees about which one goes
    from app.jobs.purge import PurgeReport, purge_archived

    report = PurgeReport()
    await purge_archived(db, report, dry_run=True)
    assert report.purged_archived == 1


async def test_restoring_clears_the_deadline(client: AsyncClient, db: AsyncSession) -> None:
    """Recover takes a file out of the window entirely — the point of
    having one."""
    admin = await create_user(db, "admin@lilkis.in", role="admin")
    deal = await create_deal(db, "BACK", admin.id)
    folder = await create_folder(db, "Legal", admin.id)
    doc = await _archived(db, deal.id, folder.id, admin.id, days_ago=5)

    await login(client, "admin@lilkis.in")
    await client.patch("/admin/settings", json={"archive_retention_days": 30})
    assert len((await client.get("/admin/archive")).json()) == 1

    assert (await client.post(f"/admin/archive/{doc.id}/restore")).status_code == 200
    assert (await client.get("/admin/archive")).json() == []

    from app.jobs.purge import PurgeReport, purge_archived

    report = PurgeReport()
    await purge_archived(db, report, dry_run=True)
    assert report.purged_archived == 0
