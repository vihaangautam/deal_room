# CLAUDE.md — Lilkis Deal Room

Build rules for AI coding agents. Read this before touching any file. Read `PRD.md` and `ARCHITECTURE.md` first if you haven't.

---

## 1. What You Are Building

A private internal deal room for Lilkis Capital AIF Trust. Not a compliance dashboard (that scope was dropped). Not a public product. A secure internal tool for ~10 users.

Three things it does:
1. Document management per deal (folder structure, upload, approval, download)
2. Task tracking per deal (assign, submit with attachments, approve)
3. Communication (comments on deals and tasks)

If a feature idea is not in PRD.md, it does not exist for this build. Do not add features.

---

## 2. Non-Negotiables

These rules apply everywhere and always. No exceptions.

1. **Audit log is append-only.** Never `UPDATE` or `DELETE` rows in `audit_log`. The DB role is `REVOKE`'d from doing so. If you find yourself wanting to edit an audit entry, you are wrong.

2. **Files are never stored in the database.** `documents.object_key` is an OCI path. The file lives in OCI Object Storage. If bytes show up in a DB column, you have made an error.

3. **Authorization at the API layer, always.** The UI hides inaccessible controls, but every single endpoint must verify permissions via a FastAPI dependency. "The frontend won't let them" is not a security model.

4. **Every mutation is attributed.** Every state change must record who did it and when. If a write doesn't produce an `audit_log` entry, ask why not.

5. **No sensitive data in client storage.** No investor data, no file content, no session tokens in `localStorage` or `sessionStorage`. Session cookie only (httpOnly).

6. **Use S3 API only (boto3).** Never import OCI SDK. Never reference OCI-specific constructs. This keeps the AWS migration trivial.

7. **The system flags; humans decide.** No automated compliance verdicts. No auto-approve based on content analysis. Approvals are always a human action.

---

## 3. Tech Stack (exact versions — do not upgrade without reason)

### Backend
```
python                3.12
fastapi               0.115.x
uvicorn[standard]     0.30.x
pydantic              2.x (strict mode)
sqlalchemy            2.0.x (async)
alembic               1.13.x
fastapi-users[sqlalchemy]  13.x
argon2-cffi           23.x
boto3                 1.35.x
procrastinate         2.x
slowapi               0.1.x      # rate limiting
structlog             24.x       # structured JSON logging
httpx                 0.27.x     # async HTTP (for health checks)
pytest                8.x
pytest-asyncio        0.23.x
httpx                 (also used as AsyncClient in tests)
```

### Frontend
```
react                 18.x
typescript            5.x (strict)
vite                  5.x
tailwindcss           3.x
shadcn/ui             (copy-paste component library — not installed as package)
@tanstack/react-query 5.x
react-router-dom      6.x
react-hook-form       7.x
zod                   3.x
lucide-react          latest
```

---

## 4. Repo Layout

```
lilkis-deal-room/
├── backend/
│   ├── AGENTS.md
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── config.py           ← pydantic-settings BaseSettings; reads .env
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── deal.py
│   │   │   ├── document.py
│   │   │   ├── task.py
│   │   │   ├── comment.py
│   │   │   ├── approval.py
│   │   │   └── audit.py
│   │   ├── schemas/
│   │   │   ├── deal.py
│   │   │   ├── document.py
│   │   │   ├── task.py
│   │   │   ├── comment.py
│   │   │   ├── approval.py
│   │   │   └── user.py
│   │   ├── routers/
│   │   │   ├── deals.py
│   │   │   ├── documents.py
│   │   │   ├── upload.py
│   │   │   ├── tasks.py
│   │   │   ├── comments.py
│   │   │   ├── approvals.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── approval_service.py    ← side-effect logic after approve/reject
│   │   │   ├── document_service.py    ← dedup check, status transitions
│   │   │   └── task_service.py        ← auto-complete logic
│   │   ├── jobs/
│   │   │   ├── __init__.py
│   │   │   ├── app.py                 ← procrastinate App instance
│   │   │   ├── notifications.py
│   │   │   ├── reminders.py
│   │   │   └── purge.py
│   │   ├── storage.py
│   │   └── auth.py
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_documents.py
│   │   ├── test_tasks.py
│   │   └── test_approvals.py
│   └── pyproject.toml
├── frontend/
│   ├── AGENTS.md
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts           ← fetch wrapper with base URL + credentials
│   │   │   ├── deals.ts
│   │   │   ├── documents.ts
│   │   │   ├── tasks.ts
│   │   │   ├── comments.ts
│   │   │   └── approvals.ts
│   │   ├── components/
│   │   │   ├── ui/                 ← shadcn copies (Button, Dialog, Table, etc.)
│   │   │   ├── AppShell.tsx
│   │   │   ├── DealCard.tsx
│   │   │   ├── DocumentRow.tsx
│   │   │   ├── FolderSection.tsx
│   │   │   ├── MultiFileUpload.tsx
│   │   │   ├── TaskRow.tsx
│   │   │   ├── ApprovalQueue.tsx
│   │   │   ├── PermissionMatrix.tsx
│   │   │   ├── StatusPill.tsx
│   │   │   └── ConfirmDialog.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── DealsHome.tsx
│   │   │   ├── DealDocuments.tsx
│   │   │   ├── DealTasks.tsx
│   │   │   ├── TaskDetail.tsx
│   │   │   ├── MyTasks.tsx
│   │   │   └── admin/
│   │   │       ├── Approvals.tsx
│   │   │       ├── Folders.tsx
│   │   │       ├── Users.tsx
│   │   │       ├── Archive.tsx
│   │   │       └── Activity.tsx
│   │   ├── hooks/
│   │   │   └── useUpload.ts        ← chunked upload logic
│   │   ├── stores/
│   │   │   └── auth.ts             ← Zustand: current user, logout
│   │   ├── lib/
│   │   │   └── utils.ts            ← cn(), formatDate(), formatBytes()
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   │   └── fonts/                  ← Inter-Regular.woff2, Inter-Medium.woff2, Inter-SemiBold.woff2
│   ├── index.html
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── AGENTS.md
├── PRD.md
├── ARCHITECTURE.md
├── CLAUDE.md
├── DESIGN.md
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## 5. Backend Conventions

### 5.1 Database access
```python
# Always use async sessions via dependency injection
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

@router.get("/deals")
async def list_deals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deal).order_by(Deal.created_at.desc()))
    return result.scalars().all()
```

### 5.2 Models
- All models inherit from a `Base` declarative class with the UUID primary key pattern
- `created_at` and `updated_at` via the DB trigger (see ARCHITECTURE.md §2.1) — do not set `updated_at` in Python
- Use `Mapped[Optional[...]]` for nullable columns (SQLAlchemy 2.0 style)
- Never use `relationship()` with `lazy='select'` — use explicit `joinedload` or separate queries

### 5.3 Schemas (Pydantic)
```python
from pydantic import BaseModel, ConfigDict

class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    borrower: str
    stage: DealStage
    # ...
```
- Always define separate `Create`, `Update`, and `Read` schemas
- `Update` schemas use `Optional` for every field (partial updates)
- No `model_config = ConfigDict(extra='allow')` — reject unknown fields

### 5.4 Audit logging
```python
# In every service function that mutates state:
from app.models.audit import AuditLog

db.add(AuditLog(
    actor_id=current_user.id,
    action="document.uploaded",
    entity_type="document",
    entity_id=str(doc.id),
    detail={"deal_id": str(doc.deal_id), "folder_id": str(doc.folder_id)},
    ip_address=request.client.host,
))
await db.commit()
```

### 5.5 Error handling
```python
from fastapi import HTTPException

# 403 when permission denied (not 401 — user is logged in, just not allowed)
raise HTTPException(status_code=403, detail="Access denied")

# 409 when duplicate detected
raise HTTPException(status_code=409, detail="Document with identical content already exists")

# 422 is automatic via Pydantic — do not catch and re-raise
```

### 5.6 File uploads
- Max chunk size: 32 MB
- API must enforce `Content-Length` check per chunk
- Store chunks to `/tmp/lilkis_uploads/{doc_id}/chunk_{n}` during assembly; clean up after S3 PUT succeeds
- SHA256 of the complete file is verified after assembly before calling `upload_complete`

### 5.7 Transactions
- Use `async with db.begin()` for any operation that touches multiple tables
- Approval side-effects (update document + check task auto-complete + write audit log) must be a single transaction

---

## 6. Frontend Conventions

### 6.1 API calls
```typescript
// src/api/client.ts
const BASE = import.meta.env.VITE_API_URL  // https://api.lilkis.in

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",   // always send cookie
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }))
    throw new APIError(res.status, error.detail)
  }
  return res.json()
}
```

### 6.2 TanStack Query
```typescript
// src/api/deals.ts
export function useDeals(stage?: DealStage) {
  return useQuery({
    queryKey: ["deals", stage],
    queryFn: () => apiFetch<Deal[]>(`/deals${stage ? `?stage=${stage}` : ""}`),
  })
}

export function useMarkTaskDone(dealId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) =>
      apiFetch(`/deals/${dealId}/tasks/${taskId}/submit`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks", dealId] })
    },
  })
}
```

- Every API call goes through `apiFetch`. No raw `fetch` calls in components.
- `queryKey` must uniquely identify the data: `["deals"]`, `["deals", dealId]`, `["tasks", dealId]`, etc.
- Use `onSuccess` to invalidate related queries after mutations.

### 6.3 TypeScript
```typescript
// tsconfig.json — strict mode enforced
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```
- No `any` — use `unknown` and narrow it
- No `!` non-null assertions — handle undefined explicitly
- All component props have explicit interfaces

### 6.4 Components
- All styling via Tailwind classes — no inline styles, no CSS modules
- Use shadcn/ui primitives (Dialog, Table, Button, Badge, etc.) — do not re-build
- Custom components go in `src/components/` — not inline in page files
- All user-facing strings go through a `copy.ts` module — no string literals scattered in JSX

### 6.5 File upload (chunked)
```typescript
// src/hooks/useUpload.ts
const CHUNK_SIZE = 32 * 1024 * 1024  // 32 MB

export function useUpload() {
  const upload = async (file: File, dealId: string, folderId: string) => {
    const sha256 = await computeSHA256(file)

    // Init
    const { doc_id } = await apiFetch<{doc_id: string}>(`/deals/${dealId}/documents/init`, {
      method: "POST",
      body: JSON.stringify({ filename: file.name, size: file.size, sha256, folder_id: folderId, mime_type: file.type }),
    })

    // Chunks
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    for (let i = 0; i < totalChunks; i++) {
      const chunk = file.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE)
      const form = new FormData()
      form.append("chunk_index", String(i))
      form.append("total_chunks", String(totalChunks))
      form.append("data", chunk)
      await apiFetch(`/upload/${doc_id}/chunk`, { method: "POST", body: form, headers: {} })
    }

    // Complete
    await apiFetch(`/upload/${doc_id}/complete`, { method: "POST" })
    return doc_id
  }

  return { upload }
}
```

---

## 7. Commands

### Backend
```bash
cd backend

# Install
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Run dev server
uvicorn app.main:app --reload --port 8000

# Run worker
procrastinate --app=app.jobs.app worker

# Run tests
pytest -x -v

# Type check
mypy app/
```

### Frontend
```bash
cd frontend

# Install
pnpm install

# Dev server
pnpm dev

# Build
pnpm build

# Type check
pnpm tsc --noEmit

# Lint
pnpm eslint src/
```

### Docker
```bash
# Build and run everything
docker compose up -d

# View logs
docker compose logs -f api

# Apply migrations in container
docker compose exec api alembic upgrade head

# Manual backup
docker compose exec postgres pg_dump -U lilkis_admin lilkis | gzip > backup.sql.gz
```

---

## 8. Four-Day Build Order

### Day 1 — October 6 — Foundation

**Morning: Infrastructure spikes (S1, S7, S8, S9)**
- Provision OCI VM; SSH in; install Docker + Docker Compose
- Confirm aarch64; run docker buildx spike (S9)
- Set up Cloudflare Tunnel; route `api.lilkis.in` to port 8000
- Deploy postgres container; confirm connection from host
- Test cross-origin cookie spike (S7)
- Run pg_dump/restore spike (S8)

**Afternoon: Backend skeleton**
- Scaffold FastAPI app with config, database, auth
- Run Alembic initial migration with full schema from ARCHITECTURE.md
- Implement auth endpoints (`/auth/login`, `/auth/logout`, `/auth/me`)
- Create first admin user via CLI script
- Add `/health` endpoint
- Confirm API reachable at `api.lilkis.in/health`

**End of Day 1 deliverable:** API running on OCI, auth works, `/health` returns 200.

---

### Day 2 — October 7 — Core Features (Backend + Storage)

**Morning: Storage spikes + upload pipeline**
- Run OCI CORS spike (S2/S3) — confirm proxy-upload is required
- Run presigned GET with filename spike (S4)
- Run app-key delete-blocked spike (S5)
- Implement `storage.py` (init upload, put chunk, complete upload, presign download, delete)
- Implement `/deals/{id}/documents/init`, `/upload/{doc_id}/chunk`, `/upload/{doc_id}/complete`
- Implement `GET /deals/{id}/documents/{doc_id}/download` (presigned GET redirect)
- 300 MB upload through tunnel spike (S6)

**Afternoon: Deals, tasks, approvals**
- Implement all Deals endpoints
- Implement all Tasks endpoints
- Implement Approval endpoints (including bulk)
- Implement approval side-effects in `approval_service.py` (transactional)
- Add `audit_log` writes to all services
- Set up procrastinate; implement `send_notification_email` job

**End of Day 2 deliverable:** All backend endpoints working; can upload a file and approve it via API.

---

### Day 3 — October 8 — Frontend

**Morning: Shell + Deals home**
- Scaffold React app with Vite, TypeScript, Tailwind, shadcn/ui
- Configure `VITE_API_URL`, `credentials: include` in fetch
- Implement `AppShell.tsx` (sidebar nav, top bar)
- Implement `Login.tsx` (email + password form → cookie set)
- Implement `DealsHome.tsx` (list of deals, stage tabs: Active / Closed; create deal button for admin)

**Afternoon: Document and task views**
- Implement `DealDocuments.tsx` (folder tree, document rows, upload button → `MultiFileUpload.tsx`)
- Implement `MultiFileUpload.tsx` (drag-and-drop, chunked upload with progress bar)
- Implement `DealTasks.tsx` (task list, create task button)
- Implement `TaskDetail.tsx` (task status machine, submit with attachment, comments)
- Implement `MyTasks.tsx` (cross-deal task list filtered to current user)

**End of Day 3 deliverable:** End-to-end flow works in browser: log in → see deals → open deal → upload doc → create task → submit task.

---

### Day 4 — October 9 — Admin + Polish

**Morning: Admin views**
- Implement `admin/Approvals.tsx` (bulk checkbox queue — this is the hero screen for Samir)
- Implement `admin/Folders.tsx` (create, rename, reorder folders)
- Implement `admin/Users.tsx` (invite user, set role, can_approve)
- Implement `admin/Activity.tsx` (audit log viewer)
- Implement `PermissionMatrix.tsx` (users × folders grid with dropdowns)

**Afternoon: Polish for demo**
- Empty states for all list views ("No deals yet. Create one." etc.)
- Error states (toast notifications for API errors)
- Loading skeletons for all data-fetching components
- Test full Samir journey from PRD.md §7 User Journeys
- Test full employee journey
- Fix any blocking bugs found during walkthrough

**End of Day 4 deliverable:** Demo-ready. All nine spike tests passed. Full journey works without errors. Samir can use it on October 10.

---

## 9. Testing Expectations

### Backend
Every service function that implements business logic must have a test:
- `test_documents.py`: upload flow, dedup rejection, approval approval/rejection side-effects
- `test_tasks.py`: status machine transitions (todo → in_progress → awaiting_approval → done), auto-complete logic
- `test_approvals.py`: bulk approve, bulk reject, side-effects, idempotency

Use `pytest-asyncio` + `httpx.AsyncClient` against a test database (separate DB created in `conftest.py`).

Do not write tests for CRUD endpoints that contain no business logic.

### Frontend
No unit tests required for the demo build. Manual testing against the full journey is sufficient.

---

## 10. DO NOT

- Do not add n8n, Celery, Redis, or any job queue other than procrastinate
- Do not add a RAG pipeline or vector database
- Do not add OCI SDK imports — boto3 only
- Do not store file bytes in PostgreSQL (even temporarily)
- Do not add a compliance dashboard, SEBI filing tracker, or anything from the original PRD
- Do not add "real-time" features (WebSockets, SSE) — polling on page focus is sufficient for v1
- Do not add analytics, telemetry, or third-party tracking scripts
- Do not add more than 2 uvicorn workers without testing memory pressure first
- Do not generate presigned URLs with expiry > 10 minutes
- Do not send the admin key (`OCI_ADMIN_ACCESS_KEY_ID`) to the frontend or log it
- Do not make compliance determinations in code — the system flags, humans decide
- Do not add features not in PRD.md without explicit approval from the client

---

## 11. Agent Context for Subdirectories

Create `/backend/AGENTS.md` and `/frontend/AGENTS.md` with directory-specific context before starting work in each directory. Templates below.

### /backend/AGENTS.md template
```markdown
# Backend AGENTS.md — Lilkis Deal Room

Root context: /AGENTS.md and /CLAUDE.md
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

## Running
uvicorn app.main:app --reload --port 8000
procrastinate --app=app.jobs.app worker
alembic upgrade head
pytest -x -v
```

### /frontend/AGENTS.md template
```markdown
# Frontend AGENTS.md — Lilkis Deal Room

Root context: /AGENTS.md and /CLAUDE.md
Design spec: /DESIGN.md
PRD: /PRD.md

## Stack
React 18, TypeScript 5 strict, Vite 5, Tailwind 3, shadcn/ui, TanStack Query 5, React Router 6, react-hook-form + zod, lucide-react

## Key rules
- All API calls through src/api/client.ts (credentials: include)
- TanStack Query for all server state; Zustand for auth state only
- No inline styles; Tailwind only
- No string literals in JSX; use copy.ts
- Chunked upload via src/hooks/useUpload.ts
- TypeScript strict; no any, no !

## Running
pnpm dev          # dev server
pnpm build        # production build
pnpm tsc --noEmit # type check
```
