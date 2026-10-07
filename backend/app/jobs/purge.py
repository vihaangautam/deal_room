"""The sweeps that move documents through the back half of PRD §8's state
machine, and the only thing that makes the retention setting mean anything.

    uploading --(24h stale)--> failed
    rejected  --(30d)-------->  purged
    archived  --(retention)-->  purged

`purged` keeps the row and deletes the object (PRD §8). Rows are never
deleted — PRD G5 — so nothing here issues a DELETE against the database.

Run it:

    python -m app.jobs.purge            # do the work
    python -m app.jobs.purge --dry-run  # say what it would do

ARCHITECTURE.md §8 puts these under procrastinate. That buys retries and a
worker process for what is three periodic queries on a timer — all of them
idempotent, none of them triggered by an event — so this is a plain script
for cron or Task Scheduler instead, and nothing stops a later
`@app_procrastinate.task` from calling run_all() when the event-driven jobs
in that section (the notification emails) actually get built.
"""

import argparse
import asyncio
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.settings import Setting
from app.routers.upload import CHUNK_DIR
from app.storage import delete_object

STALE_UPLOAD_HOURS = 24  # PRD §8: "uploading --(24h stale)--> failed"
DEFAULT_REJECTED_PURGE_DAYS = 30  # PRD F11, fixed in v1


@dataclass
class PurgeReport:
    failed_uploads: int = 0
    purged_rejected: int = 0
    purged_archived: int = 0
    chunk_dirs_removed: int = 0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"stale uploads marked failed: {self.failed_uploads}\n"
            f"rejected uploads purged:     {self.purged_rejected}\n"
            f"archived files purged:       {self.purged_archived}\n"
            f"chunk directories removed:   {self.chunk_dirs_removed}\n"
            + (f"errors:\n  " + "\n  ".join(self.errors) if self.errors else "errors: none")
        )


async def _setting(db: AsyncSession, key: str, default: int | None) -> int | None:
    row = await db.get(Setting, key)
    if row is None or row.value is None:
        return default
    return int(row.value)  # JSONB, so it comes back as whatever was stored


def _drop_chunks(doc_id) -> bool:
    chunk_dir = CHUNK_DIR / str(doc_id)
    if not chunk_dir.exists():
        return False
    shutil.rmtree(chunk_dir, ignore_errors=True)
    return True


def _audit(doc: Document, action: str, detail: dict) -> AuditLog:
    """actor_id is None: nobody did this, the clock did. Every sweep still
    leaves a row, because the audit log is how an admin finds out a file
    they were looking for is gone (CLAUDE.md §2.4)."""
    return AuditLog(
        actor_id=None,
        action=action,
        entity_type="document",
        entity_id=str(doc.id),
        detail=detail,
    )


async def fail_stale_uploads(db: AsyncSession, report: PurgeReport, dry_run: bool) -> None:
    """An upload that never reached complete() holds a row at 'uploading'
    and a directory of chunks. It also blocks a fresh upload of the same
    file by the same person forever, since 'uploading' counts for dedup."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_UPLOAD_HOURS)
    stale = await db.scalars(
        select(Document).where(Document.status == "uploading", Document.created_at < cutoff)
    )
    for doc in stale:
        report.failed_uploads += 1
        if dry_run:
            continue
        if _drop_chunks(doc.id):
            report.chunk_dirs_removed += 1
        doc.status = "failed"
        db.add(_audit(doc, "document.upload_failed", {"reason": "abandoned", "after_hours": STALE_UPLOAD_HOURS}))


async def purge_rejected(db: AsyncSession, report: PurgeReport, dry_run: bool) -> None:
    """PRD F5: "the uploader sees 'Rejected' with reason for 30 days,
    then the file is purged."

    updated_at is the clock here, and it is right because nothing updates
    a rejected row: rename requires 'active', and rejection is terminal
    until this sweep. The same holds for archived below — restore and
    purge both move it out of the status. If a future change starts
    touching rows in either status, this silently becomes "30 days since
    anyone last touched it" and needs a real status_changed_at column.
    """
    days = await _setting(db, "rejected_upload_purge_days", DEFAULT_REJECTED_PURGE_DAYS)
    if not days:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.scalars(
        select(Document).where(Document.status == "rejected", Document.updated_at < cutoff)
    )
    for doc in rows:
        if await _purge_object(doc, report, dry_run):
            report.purged_rejected += 1
            if not dry_run:
                db.add(_audit(doc, "document.purged", {"reason": "rejected", "after_days": days}))


async def purge_archived(db: AsyncSession, report: PurgeReport, dry_run: bool) -> None:
    """PRD F11: archive_retention_days is "Keep forever" by default, which
    is stored as null — and null means this sweep does nothing at all."""
    days = await _setting(db, "archive_retention_days", None)
    if not days:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.scalars(
        select(Document).where(Document.status == "archived", Document.updated_at < cutoff)
    )
    for doc in rows:
        if await _purge_object(doc, report, dry_run):
            report.purged_archived += 1
            if not dry_run:
                db.add(_audit(doc, "document.purged", {"reason": "retention", "after_days": days}))


async def _purge_object(doc: Document, report: PurgeReport, dry_run: bool) -> bool:
    """Deletes the stored object and moves the row to 'purged'. One
    document's storage error must not abandon the rest of the sweep, so it
    is recorded and the row is left alone to be retried next run."""
    if dry_run:
        return True
    try:
        # A document flagged by its integrity check never had an object
        # written (routers/upload.py), so there is nothing to delete.
        if not doc.integrity_check_failed:
            delete_object(doc.object_key)
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        report.errors.append(f"{doc.id} ({doc.display_name}): {exc}")
        return False
    doc.status = "purged"
    return True


def remove_orphan_chunk_dirs(db_ids: set[str], report: PurgeReport, dry_run: bool) -> None:
    """Chunk directories whose document is no longer mid-upload. Normally
    complete() removes its own, but a crash between the S3 PUT and the
    rmtree leaves one behind, and those are pure waste on disk."""
    if not CHUNK_DIR.exists():
        return
    for path in CHUNK_DIR.iterdir():
        if not path.is_dir() or path.name in db_ids:
            continue
        report.chunk_dirs_removed += 1
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)


async def _sweep(db: AsyncSession, report: PurgeReport, dry_run: bool) -> None:
    await fail_stale_uploads(db, report, dry_run)
    await purge_rejected(db, report, dry_run)
    await purge_archived(db, report, dry_run)
    if not dry_run:
        await db.commit()

    # After the commit, so a row that just became 'failed' no longer
    # protects its chunk directory.
    in_progress = await db.scalars(select(Document.id).where(Document.status == "uploading"))
    remove_orphan_chunk_dirs({str(i) for i in in_progress}, report, dry_run)


async def run_all(dry_run: bool = False, db: AsyncSession | None = None) -> PurgeReport:
    """db is for the tests, which run against their own database — without
    it this opens its own session, which is what the command line wants."""
    report = PurgeReport()
    if db is not None:
        await _sweep(db, report, dry_run)
        return report
    async with async_session_factory() as session:
        await _sweep(session, report, dry_run)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without changing anything")
    args = parser.parse_args()
    report = asyncio.run(run_all(dry_run=args.dry_run))
    print("DRY RUN — nothing changed\n" if args.dry_run else "")
    print(report)


if __name__ == "__main__":
    main()
