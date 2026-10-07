"""Test DB lifecycle, FastAPI dependency override, and auth helpers.
CLAUDE.md §9: a separate DB, not the dev one — tests truncate every table
before each test, which would otherwise wipe dev data on every run.

The test DB's schema comes from the same UPGRADE_SQL the real migration
runs (loaded by file path — the module's filename starts with a revision
hash, so it can't be `import`ed normally), not from re-running Alembic's
own bookkeeping, which doesn't matter for a throwaway test database.
"""

import asyncio
import importlib.util
import sys
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.jobs import purge as purge_job
from app.routers import upload as upload_router

# asyncpg + Windows' default ProactorEventLoop don't close cleanly
# together (a harmless but noisy AttributeError during connection
# teardown) — the documented fix is the Selector policy instead.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from app.database import get_db
from app.main import app
from app.models.deal import Deal
from app.models.folder import FolderTemplate, UserFolderPermission
from app.models.user import User

TEST_DB_NAME = "lilkis_test"


def _swap_db(url: str, dbname: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + dbname


def _to_psycopg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


MAINTENANCE_DSN = _to_psycopg(_swap_db(settings.database_url_admin, "postgres"))
TEST_ADMIN_DSN = _to_psycopg(_swap_db(settings.database_url_admin, TEST_DB_NAME))
TEST_APP_URL = _swap_db(settings.database_url, TEST_DB_NAME)

TABLES_TO_TRUNCATE = (
    "audit_log, approval_requests, comments, task_attachments, tasks, documents, "
    "deal_stage_history, deals, user_folder_permissions, folder_templates, "
    "access_tokens, users"
)


def _load_upgrade_sql() -> str:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "5b520526179f_initial_schema.py"
    )
    spec = importlib.util.spec_from_file_location("initial_schema", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UPGRADE_SQL


@pytest.fixture(scope="session")
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """Session-scoped to match test_engine/admin_engine below — those are
    created once at import time, so every test must run on the same loop
    they were created on. pytest-asyncio's default is function-scoped,
    which breaks pooled asyncpg connections on the second test ("Event
    loop is closed")."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database() -> AsyncGenerator[None, None]:
    conn = await asyncpg.connect(dsn=MAINTENANCE_DSN)
    await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    await conn.close()

    # UPGRADE_SQL's trigger DO block has "%%s" (see the migration's own
    # comment) because psycopg's DBAPI — what the real migration runs
    # under — treats a literal %s as ITS OWN parameter placeholder.
    # asyncpg (used here) does no such client-side %-interpretation at
    # all, so the doubled %% is wrong for it and breaks Postgres's
    # format() call; un-escape it back to plain %s for this driver.
    schema_conn = await asyncpg.connect(dsn=TEST_ADMIN_DSN)
    await schema_conn.execute(_load_upgrade_sql().replace("%%", "%"))
    await schema_conn.close()

    yield

    # Dispose pooled connections first — DROP DATABASE fails while
    # test_engine/admin_engine still hold open connections to it.
    await test_engine.dispose()
    await admin_engine.dispose()
    conn = await asyncpg.connect(dsn=MAINTENANCE_DSN)
    await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    await conn.close()


test_engine = create_async_engine(TEST_APP_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

# audit_log is INSERT+SELECT only for lilkis_app by design (CLAUDE.md #1 —
# append-only); TRUNCATE needs the admin connection instead.
admin_engine = create_async_engine(_swap_db(settings.database_url_admin, TEST_DB_NAME))


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables() -> AsyncGenerator[None, None]:
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {TABLES_TO_TRUNCATE} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def create_user(
    db: AsyncSession,
    email: str,
    password: str = "testpassword123",
    role: str = "member",
    can_approve: bool = False,
    must_change_password: bool = False,
) -> User:
    user = User(
        email=email,
        display_name=email.split("@")[0].title(),
        hashed_pw=PasswordHelper().hash(password),
        role=role,
        can_approve=can_approve,
        must_change_password=must_change_password,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(client: AsyncClient, email: str, password: str = "testpassword123") -> None:
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 204, response.text


async def create_folder(db: AsyncSession, name: str, created_by: uuid.UUID) -> FolderTemplate:
    folder = FolderTemplate(name=name, created_by=created_by)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def grant_access(
    db: AsyncSession, user_id: uuid.UUID, folder_id: uuid.UUID, level: str, granted_by: uuid.UUID
) -> None:
    db.add(
        UserFolderPermission(
            user_id=user_id, folder_id=folder_id, access_level=level, granted_by=granted_by
        )
    )
    await db.commit()


async def create_deal(
    db: AsyncSession, short_code: str, created_by: uuid.UUID, stage: str = "running"
) -> Deal:
    deal = Deal(
        name=f"{short_code} Test Deal",
        short_code=short_code,
        borrower="Test Borrower",
        summary="Test summary",
        stage=stage,
        created_by=created_by,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


@pytest.fixture(autouse=True, scope="session")
def _isolate_chunk_dir(tmp_path_factory: pytest.TempPathFactory) -> Generator[None, None, None]:
    """Upload chunks stage in the system temp directory, which the dev
    server on this machine is also using. Without this, the purge job's
    orphan sweep — run for real by test_purge.py — deletes the chunks of
    whatever upload is in flight outside the tests, because those document
    ids aren't in the test database.
    """
    chunk_dir = tmp_path_factory.mktemp("lilkis_chunks")
    original_upload, original_purge = upload_router.CHUNK_DIR, purge_job.CHUNK_DIR
    # Patched in both modules: purge.py imported the value, not the module.
    upload_router.CHUNK_DIR = chunk_dir
    purge_job.CHUNK_DIR = chunk_dir
    yield
    upload_router.CHUNK_DIR = original_upload
    purge_job.CHUNK_DIR = original_purge
