# Backend AGENTS.md — Lilkis Deal Room

Root context: /CLAUDE.md
Architecture: /ARCHITECTURE.md
PRD: /PRD.md

## Stack
Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async, Alembic, fastapi-users, boto3, procrastinate

## Key rules
- Authorization dependency on every protected route
- Every mutation writes to audit_log in the same transaction
- Use AsyncSession; never sync SQLAlchemy
- Pydantic v2 strict mode on all schemas
- Files go to OCI via storage.py; never in DB
- boto3 only; no OCI SDK

## Local dev setup (before first migration)
`docker-compose.yml` at the repo root only creates the Postgres superuser
(`lilkis_admin`). ARCHITECTURE.md §2.1 defines a separate restricted
`lilkis_app` role (no UPDATE/DELETE on `audit_log`, full CRUD elsewhere) that
the app connects as.

It is created automatically: `db-init/01-app-role.sql` is mounted into the
Postgres container's `/docker-entrypoint-initdb.d`, which runs once when the
data volume is first initialised. The GRANTs live in the Alembic migration,
which can issue them but cannot create the role — a role is cluster-wide
rather than part of a database's schema.

So a full reset is just:

```powershell
docker compose down -v
docker compose up -d
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

## Running
```
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --port 8002
procrastinate --app=app.jobs.app worker
pytest -x -v
```
Port 8002, not 8000 — a stale Windows socket handle on this dev machine
permanently shadows 8000 after any ungraceful process kill, and the same
thing happened on 8001. VITE_API_URL in .env already points at 8002.

No `--reload`: WatchFiles' reloader subprocess model triggers the same
ghost-listener issue on this machine (the owning PID reports as a live
LISTENer but no longer exists). Restart uvicorn manually after changes
instead — annoying but reliable. If a later Python/WatchFiles version or
a venv rebuild fixes it, --reload is safe to bring back.
