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
the app connects as. Create it once against the running container before
`alembic upgrade head`:

```sql
CREATE ROLE lilkis_app WITH LOGIN PASSWORD 'localdevpassword';
```

Then run the GRANT statements from ARCHITECTURE.md §2.1 (they're part of the
same migration/DDL block — the Alembic migration should include them, not
just the CREATE TABLE statements).

## Running
```
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
procrastinate --app=app.jobs.app worker
pytest -x -v
```
