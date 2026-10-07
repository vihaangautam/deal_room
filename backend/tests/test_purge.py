"""PRD §8's back half: the transitions nothing but the clock performs.

    uploading --(24h stale)--> failed
    rejected  --(30d)-------->  purged
    archived  --(retention)-->  purged

Every one of these deletes a stored file or strands one, so each gets a
test for the transition firing *and* for it not firing early.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# The module, not the value: conftest redirects CHUNK_DIR so a test run
# can't delete the chunks of an upload happening outside the tests.
from app.jobs import purge as purge_job
from app.jobs.purge import run_all
from app.models.deal import Deal
from app.models.document import Document
from app.models.folder import FolderTemplate
from app.models.settings import Setting
from app.models.user import User
from conftest import create_deal, create_folder, create_user


async def _document(
    db: AsyncSession, status: str, *, age_days: float = 0, sha: str = "a", integrity_failed: bool = False
) -> Document:
    """Each test gets its own documents but shares one deal, folder and
    uploader — none of which the sweeps look at."""
    admin = await db.scalar(select(User)) or await create_user(db, "admin@lilkis.in", role="admin")
    deal = await db.scalar(select(Deal)) or await create_deal(db, "PURG", admin.id)
    folder = await db.scalar(select(FolderTemplate)) or await create_folder(db, "Legal", admin.id)

    # The age goes in at INSERT. trg_documents_updated_at is BEFORE
    # UPDATE, so ageing a row by updating it just resets updated_at to now
    # and the sweep finds nothing.
    moment = datetime.now(timezone.utc) - timedelta(days=age_days) if age_days else None

    doc = Document(
        deal_id=deal.id,
        folder_id=folder.id,
        display_name=f"{sha}.pdf",
        original_name=f"{sha}.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256=sha * 64,
        object_key=f"deals/{deal.id}/{sha}",
        status=status,
        integrity_check_failed=integrity_failed,
        uploaded_by=admin.id,
        **({"created_at": moment, "updated_at": moment} if moment else {}),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def test_stale_upload_fails_and_loses_its_chunks(db: AsyncSession) -> None:
    doc = await _document(db, "uploading", age_days=2, sha="b")
    chunk_dir = purge_job.CHUNK_DIR / str(doc.id)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "chunk_000000").write_bytes(b"half an upload")

    report = await run_all(db=db)

    await db.refresh(doc)
    assert doc.status == "failed"
    assert not chunk_dir.exists()
    assert report.failed_uploads == 1


async def test_a_fresh_upload_is_left_alone(db: AsyncSession) -> None:
    """The window is 24 hours; someone uploading a 2 GB file over a slow
    line must not have it swept out from under them."""
    doc = await _document(db, "uploading", sha="c")
    report = await run_all(db=db)

    await db.refresh(doc)
    assert doc.status == "uploading"
    assert report.failed_uploads == 0


async def test_rejected_upload_is_purged_after_the_window(db: AsyncSession) -> None:
    old = await _document(db, "rejected", age_days=31, sha="d")
    recent = await _document(db, "rejected", age_days=5, sha="e")

    report = await run_all(db=db)

    await db.refresh(old)
    await db.refresh(recent)
    assert old.status == "purged"
    assert recent.status == "rejected"  # PRD F5: visible to its uploader for 30 days
    assert report.purged_rejected == 1
    assert report.errors == []


async def test_keep_forever_means_the_archive_is_never_touched(db: AsyncSession) -> None:
    """archive_retention_days is null by default — PRD F11's "Keep
    forever" — and these are legal documents, so a sweep that ignored that
    would be the worst bug in the system."""
    doc = await _document(db, "archived", age_days=4000, sha="f")

    report = await run_all(db=db)

    await db.refresh(doc)
    assert doc.status == "archived"
    assert report.purged_archived == 0


async def test_archive_retention_purges_once_set(db: AsyncSession) -> None:
    db.add(Setting(key="archive_retention_days", value=365))
    await db.commit()
    old = await _document(db, "archived", age_days=400, sha="g")
    recent = await _document(db, "archived", age_days=100, sha="h")

    report = await run_all(db=db)

    await db.refresh(old)
    await db.refresh(recent)
    assert old.status == "purged"
    assert recent.status == "archived"
    assert report.purged_archived == 1


async def test_dry_run_changes_nothing(db: AsyncSession) -> None:
    doc = await _document(db, "rejected", age_days=31, sha="i")

    report = await run_all(dry_run=True, db=db)

    await db.refresh(doc)
    assert doc.status == "rejected"
    assert report.purged_rejected == 1  # it still reports what it would do


async def test_integrity_failed_document_purges_without_a_stored_object(db: AsyncSession) -> None:
    """A document that failed its hash check never had an object written
    (routers/upload.py), so asking storage to delete one would raise and
    strand the row at 'rejected' forever."""
    doc = await _document(db, "rejected", age_days=31, sha="j", integrity_failed=True)

    report = await run_all(db=db)

    await db.refresh(doc)
    assert doc.status == "purged"
    assert report.errors == []
