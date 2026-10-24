# Lilkis Deal Room — running it locally

The commands below are the ones that work **on this machine**. They differ
from the generic ones in CLAUDE.md §14 in three places, each for a reason
noted under [Why these commands differ](#why-these-commands-differ).

Everything runs from the repo root: `C:\Users\ASUS\OneDrive\Desktop\Lilkis Deal Room`.

---

## Start it

```powershell
.\start.ps1
```

That is the whole thing. It starts Docker if it is down, waits for
Postgres and storage, applies any pending migration, repairs the seeded
files, starts the API and the frontend, and then signs in to prove the app
actually works before telling you it is ready. Takes about a minute cold,
seconds warm, and is safe to run twice.

```powershell
.\start.ps1 -Reset   # destroy the data and rebuild from the seed
.\start.ps1 -Stop    # stop the servers and the containers
```

Logs land in `logs\`. If a step fails the script prints the last lines of
the relevant one rather than leaving you to find it.

### Doing it by hand

Only needed if the script fails and you want to see where.

```powershell
docker compose up -d
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002
```

and in a second terminal:

```powershell
cd frontend
npm run dev
```

Three things differ from the generic commands in CLAUDE.md §14, each for a
reason given under [Why these commands differ](#why-these-commands-differ).

---

## Sign in

Password for all three is `changeme123`.

| Email | Role | Sees |
|---|---|---|
| `samir@lilkis.in` | Admin, approver | Everything, including Approvals, Folders, Users, Archive, Activity |
| `rohan@lilkis.in` | Member | Contribute on every folder **except Borrower details**, which is locked |
| `meera@lilkis.in` | Member | View everywhere, Contribute on Bank documents |

Seeded users skip the forced password change so the demo does not open on
that screen. A user Samir creates in the app still gets it.

---

## What is seeded

Four deals, one per stage, each with its stage-history reason:

| Deal | Stage | Shows off |
|---|---|---|
| `PTXL` Patel Textiles | New | A deal before work starts — no Tasks tab (PRD F8) |
| `SHRM` Sharma Infra | Running | The working deal: 9 visible files, 6 tasks, comments |
| `MEHT` Mehta Logistics | Successful | Read-only — download works, nothing can be changed |
| `OBRT` Oberoi Textiles | Dropped | Same, and reopenable from the stage dialog |

On **SHRM**:

- Files across six folders, including one in Borrower details that Rohan
  cannot see and one **pending** upload from Meera that only approvers see
- One file with a **deletion requested** — still downloadable, request waiting
- Six tasks covering every status, plus a **Needs attention** flag and an
  **overdue** due date
- A comment thread with a reply, and a deal-level comment on the Activity tab

**Approvals** has one of each type waiting: an upload, a deletion and a
reassignment. **Archive** has one file with its reason and approver.

### The one chain worth demoing

`SHRM-2 Verify hypothecation deed registration` is **Awaiting approval**
because its attachment is Meera's pending upload. Approving that single
document in **Approvals** moves the task to **Done** by itself — that is
PRD F8's rule, and it is the only part of the app where two screens visibly
talk to each other.

---

## Resetting between runs

To get back to a clean seeded state:

```powershell
docker compose down -v
docker compose up -d
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

`-v` drops the volumes, so this deletes everything including uploaded files.

---

## The purge job

Not scheduled. Nothing in the demo depends on it, but it is what enforces
the Archive retention setting and clears abandoned uploads.

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.jobs.purge --dry-run   # report only
.\.venv\Scripts\python.exe -m app.jobs.purge             # do it
```

To run it daily, add a Task Scheduler entry:

- **Program:** `C:\Users\ASUS\OneDrive\Desktop\Lilkis Deal Room\backend\.venv\Scripts\python.exe`
- **Arguments:** `-m app.jobs.purge`
- **Start in:** `C:\Users\ASUS\OneDrive\Desktop\Lilkis Deal Room\backend`

---

## Checks before a demo

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q      # 47 tests
cd ..\frontend
npm run typecheck                            # must print nothing
```

`npm run typecheck` runs `tsc -b`. Plain `tsc --noEmit` checks **nothing**
here — the root tsconfig is the solution file (`"files": []` plus project
references), so it resolves zero inputs and exits 0 whatever is broken.

---

## Why these commands differ

**Postgres is on 5433, not 5432.** A native Windows Postgres service owns
`0.0.0.0:5432` on this machine and shadowed Docker's forwarded port, so
connections silently reached the wrong server. `docker-compose.yml` maps to
5433 and `.env` matches.

**The API runs on 8002 without `--reload`.** Ports 8000 and 8001 have ghost
listeners here, and `--reload` with this event-loop policy on Windows leaves
a worker holding the port after a restart.

**`npm`, not `pnpm`.** corepack's pnpm shim fails signature verification on
this machine; pnpm is installed through npm instead.

**Fonts need internet.** Inter loads from the Google Fonts CDN
(`frontend/src/index.css:4`). Offline, the app falls back to system-ui and
stops matching the design. Self-host the woff2 before relying on a venue's
network.

---

## If something will not start

| Symptom | Cause | Fix |
|---|---|---|
| `/health` says `"db":"error"` | Postgres container not up yet, or the native 5432 service is interfering | `docker ps`; confirm `.env` points at 5433 |
| API exits immediately with an address-in-use error | A previous uvicorn still holds 8002 | `netstat -ano \| findstr :8002`, then `taskkill /PID <pid> /F` |
| Login returns 400 with correct credentials | Five failed attempts in 15 minutes locked that email (PRD F1) | Wait it out, or use another account |
| Pages load but every request 401s | The session cookie expired (12 hours) | Sign in again |
| Uploads fail against storage | The s3mock container restarted and lost its bucket | Restart the API; it recreates the bucket at startup |

## Going to production

See **GUIDE.md** — the full path from here to a running deployment,
written for someone who hasn't done it before.

Two commands from it that do not exist anywhere else:

```bash
# Check real object storage behaves the way the app expects, BEFORE
# deploying on top of it. Exits non-zero if not.
python -m app.checks.storage_check

# Create the first account on a fresh production database. Makes exactly
# one admin/owner and refuses if any user already exists.
python -m app.bootstrap
```

**Never run `python -m app.seed` in production.** It is the demo seed:
three accounts, password `changeme123`, no forced password change.
