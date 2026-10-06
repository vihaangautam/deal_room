# ARCHITECTURE.md — Lilkis Deal Room

Technical specification and system design. Read this alongside `PRD.md` (what we're building) and `CLAUDE.md` (how to build it). Every decision here has a reason; do not swap components without understanding the tradeoff first.

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────┐
│  Browser (deals.lilkis.in — Cloudflare Pages)            │
│  React 18 + Vite + TypeScript + Tailwind + shadcn/ui     │
└────────────────────┬─────────────────────────────────────┘
                     │  HTTPS (REST + multipart upload)
                     ▼
┌──────────────────────────────────────────────────────────┐
│  api.lilkis.in (Cloudflare Tunnel → OCI VM port 8000)    │
│  FastAPI + uvicorn (2 workers) + Pydantic v2             │
│  fastapi-users (argon2, httpOnly cookie sessions)        │
│  boto3 (OCI S3-Compat) + procrastinate (job queue)       │
└───────────┬─────────────────────┬────────────────────────┘
            │                     │
            ▼                     ▼
┌───────────────────┐  ┌──────────────────────────────────┐
│  PostgreSQL 16    │  │  OCI Object Storage              │
│  Docker on VM     │  │  S3-Compat API                   │
│  2 OCPU / 12 GB  │  │  Bucket: lilkis-deals            │
│  self-hosted      │  │  No CORS config possible         │
└───────────────────┘  └──────────────────────────────────┘
```

**Why self-hosted Postgres:** OCI managed PostgreSQL minimum cost is ~$273/month. Self-hosted in Docker on the Always Free VM is $0.

**Why proxy uploads through API:** OCI Object Storage bucket CORS headers are fixed and cannot be configured (Oracle documentation confirmed). Direct browser PUT to presigned URL will be blocked by the browser. All uploads route through the API in 32 MB chunks.

**Why Cloudflare Tunnel:** Zero open inbound ports on the VM. The tunnel establishes an outbound connection to Cloudflare, routing traffic to the local FastAPI process. No firewall rules, no static IP, no SSL cert management on the VM.

---

## 2. Database Schema

### 2.1 Schema — full DDL

```sql
-- ─────────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- ─────────────────────────────────────────
-- USERS
-- ─────────────────────────────────────────
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    hashed_pw     TEXT NOT NULL,                   -- argon2id via fastapi-users
    role          TEXT NOT NULL DEFAULT 'member'   -- 'admin' | 'member'
                  CHECK (role IN ('admin','member')),
    can_approve   BOOLEAN NOT NULL DEFAULT FALSE,  -- admins always approve; members may be granted
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- SESSIONS (fastapi-users manages cookie tokens; this table is for audit only)
-- ─────────────────────────────────────────
CREATE TABLE access_tokens (
    token         TEXT PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX access_tokens_user_id_idx ON access_tokens(user_id);

-- ─────────────────────────────────────────
-- FOLDER TEMPLATES (global master list — not per-deal)
-- ─────────────────────────────────────────
CREATE TABLE folder_templates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,            -- e.g. "Term Sheet", "Legal Docs"
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- USER FOLDER PERMISSIONS
-- Access level per (user × folder_template).
-- 'none' | 'view' | 'contribute'
-- Absent row = 'none' (deny by default).
-- Admin sees everything; this table governs members only.
-- ─────────────────────────────────────────
CREATE TABLE user_folder_permissions (
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id     UUID NOT NULL REFERENCES folder_templates(id) ON DELETE CASCADE,
    access_level  TEXT NOT NULL DEFAULT 'view'
                  CHECK (access_level IN ('none','view','contribute')),
    granted_by    UUID NOT NULL REFERENCES users(id),
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, folder_id)
);

-- ─────────────────────────────────────────
-- DEALS
-- ─────────────────────────────────────────
CREATE TABLE deals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    borrower      TEXT NOT NULL,                   -- company name
    stage         TEXT NOT NULL DEFAULT 'new'
                  CHECK (stage IN ('new','running','successful','dropped')),
    amount_cr     NUMERIC(12,2),                   -- loan amount in crore INR (nullable at creation)
    notes         TEXT,
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX deals_stage_idx ON deals(stage);
CREATE INDEX deals_created_at_idx ON deals(created_at DESC);

-- ─────────────────────────────────────────
-- DEAL STAGE HISTORY (append-only)
-- ─────────────────────────────────────────
CREATE TABLE deal_stage_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id       UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    from_stage    TEXT,                            -- NULL on creation
    to_stage      TEXT NOT NULL,
    changed_by    UUID NOT NULL REFERENCES users(id),
    reason        TEXT,                            -- required when moving to dropped
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX deal_stage_history_deal_idx ON deal_stage_history(deal_id, changed_at DESC);

-- ─────────────────────────────────────────
-- DOCUMENTS
-- ─────────────────────────────────────────
CREATE TABLE documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id          UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    folder_id        UUID NOT NULL REFERENCES folder_templates(id),
    display_name     TEXT NOT NULL,               -- shown in UI; can be renamed
    original_name    TEXT NOT NULL,               -- original filename at upload time
    mime_type        TEXT NOT NULL,
    size_bytes       BIGINT NOT NULL,
    sha256           TEXT NOT NULL,               -- hex; used for dedup
    object_key       TEXT NOT NULL UNIQUE,        -- OCI key: deals/{deal_id}/{doc_id}
    status           TEXT NOT NULL DEFAULT 'uploading'
                     CHECK (status IN (
                       'uploading',    -- upload in progress
                       'pending',      -- upload done, awaiting approval
                       'active',       -- approved and visible to permitted users
                       'delete_requested',  -- deletion pending approval
                       'deleted',      -- soft-deleted after approval
                       'rejected'      -- upload rejected; object cleaned up
                     )),
    version          INTEGER NOT NULL DEFAULT 1,  -- increments on re-upload to same slot
    uploaded_by      UUID NOT NULL REFERENCES users(id),
    approved_by      UUID REFERENCES users(id),
    approved_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX documents_deal_folder_idx ON documents(deal_id, folder_id);
CREATE INDEX documents_status_idx ON documents(status);

-- Dedup: prevent two active/pending uploads of the same bytes to the same deal
CREATE UNIQUE INDEX documents_dedup_uq ON documents (deal_id, sha256)
    WHERE status IN ('uploading','pending','active','delete_requested');

-- ─────────────────────────────────────────
-- TASKS
-- ─────────────────────────────────────────
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'todo'
                    CHECK (status IN (
                      'todo',
                      'in_progress',
                      'awaiting_approval',    -- submitted; pending attachment approvals
                      'done',                 -- all attachments approved
                      'needs_attention'       -- one or more attachments rejected
                    )),
    priority        TEXT NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low','medium','high')),
    assigned_to     UUID REFERENCES users(id),
    due_date        DATE,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX tasks_deal_idx ON tasks(deal_id);
CREATE INDEX tasks_assigned_idx ON tasks(assigned_to);
CREATE INDEX tasks_status_idx ON tasks(status);

-- ─────────────────────────────────────────
-- TASK ATTACHMENTS
-- Documents attached to a task at completion.
-- A task moves to 'done' only when all its attachments are 'active'.
-- ─────────────────────────────────────────
CREATE TABLE task_attachments (
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    attached_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, document_id)
);

-- ─────────────────────────────────────────
-- COMMENTS
-- On deals (deal_id set, task_id null) or tasks (both set).
-- Thread replies: parent_id references another comment row.
-- ─────────────────────────────────────────
CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    task_id         UUID REFERENCES tasks(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES comments(id) ON DELETE CASCADE,
    author_id       UUID NOT NULL REFERENCES users(id),
    body            TEXT NOT NULL,
    edited          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX comments_deal_idx ON comments(deal_id, created_at DESC);
CREATE INDEX comments_task_idx ON comments(task_id, created_at DESC);

-- ─────────────────────────────────────────
-- APPROVAL REQUESTS
-- One pending approval per (type × target) enforced by partial unique index.
-- ─────────────────────────────────────────
CREATE TABLE approval_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL
                    CHECK (type IN (
                      'document_upload',
                      'document_delete',
                      'task_reassign',
                      'task_delete'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected')),
    -- targets (one of these is non-null depending on type):
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    task_id         UUID REFERENCES tasks(id) ON DELETE CASCADE,
    -- for task_reassign: new assignee
    proposed_assignee UUID REFERENCES users(id),
    -- context:
    requested_by    UUID NOT NULL REFERENCES users(id),
    reviewed_by     UUID REFERENCES users(id),
    review_note     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ
);

-- Only one pending approval per document/task (prevent duplicates)
CREATE UNIQUE INDEX approval_one_pending_doc  ON approval_requests (type, document_id) WHERE status = 'pending';
CREATE UNIQUE INDEX approval_one_pending_task ON approval_requests (type, task_id)     WHERE status = 'pending';

CREATE INDEX approval_status_idx ON approval_requests(status, created_at DESC);

-- ─────────────────────────────────────────
-- SETTINGS (key-value store; admin-editable)
-- ─────────────────────────────────────────
CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Seed defaults
INSERT INTO settings (key, value) VALUES
  ('archive_retention_days', 'null'),           -- null = keep forever
  ('email_notifications',    'true'),
  ('default_lead_days',      '14');

-- ─────────────────────────────────────────
-- AUDIT LOG (append-only)
-- The app role has INSERT + SELECT only; no UPDATE or DELETE ever.
-- ─────────────────────────────────────────
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        UUID REFERENCES users(id),    -- null = system action
    action          TEXT NOT NULL,                -- e.g. 'document.uploaded', 'task.done'
    entity_type     TEXT NOT NULL,                -- 'deal' | 'document' | 'task' | 'user' | ...
    entity_id       TEXT NOT NULL,                -- UUID as text (flexible)
    detail          JSONB,                        -- free-form context
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX audit_log_entity_idx  ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX audit_log_actor_idx   ON audit_log(actor_id, created_at DESC);
CREATE INDEX audit_log_created_idx ON audit_log(created_at DESC);

-- ─────────────────────────────────────────
-- PERMISSIONS FOR APP ROLE
-- ─────────────────────────────────────────
-- (Run after creating role 'lilkis_app')
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM lilkis_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    users, access_tokens, folder_templates, user_folder_permissions,
    deals, deal_stage_history, documents, tasks, task_attachments,
    comments, approval_requests, settings
    TO lilkis_app;
GRANT USAGE ON SEQUENCE audit_log_id_seq TO lilkis_app;
-- audit_log: INSERT and SELECT only — never UPDATE or DELETE
GRANT INSERT, SELECT ON audit_log TO lilkis_app;

-- ─────────────────────────────────────────
-- TRIGGER: updated_at auto-refresh
-- ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$ DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['users','deals','documents','tasks','comments','approval_requests'] LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END; $$;
```

### 2.2 Authorization Model

| Who | What they can see/do |
|-----|----------------------|
| Admin | All deals, all folders, all documents and tasks; bulk approve/reject; manage users, folders, permissions; purge deleted docs; view audit log |
| Member (contribute on folder F) | All deals; documents in folder F; upload to folder F (pending approval); create tasks; submit tasks with attachments in folders they can contribute to |
| Member (view on folder F) | All deals; read documents in folder F; read tasks; cannot upload or create tasks |
| Member (none on folder F) | Folder F is invisible — not shown in the deal document tree |

Authorization is enforced at the **API layer** using dependency injection. The UI hides inaccessible controls, but the API rejects unauthorised requests regardless of what the frontend sends.

```python
# Every protected route dependency:
async def require_folder_access(
    folder_id: UUID,
    level: Literal["view", "contribute"],
    current_user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    if current_user.role == "admin":
        return
    permission = await db.scalar(
        select(UserFolderPermission.access_level)
        .where(
            UserFolderPermission.user_id == current_user.id,
            UserFolderPermission.folder_id == folder_id
        )
    )
    if permission is None or permission == "none":
        raise HTTPException(403)
    if level == "contribute" and permission == "view":
        raise HTTPException(403)
```

---

## 3. REST API

### 3.1 Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Email + password → sets httpOnly cookie `lilkis_session` |
| POST | `/auth/logout` | Invalidates session |
| GET | `/auth/me` | Returns current user (id, email, display_name, role, can_approve) |

### 3.2 Deals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/deals` | Any | List all deals (id, name, borrower, stage, amount_cr, created_at). Optional filter: `?stage=running` |
| POST | `/deals` | Admin | Create deal |
| GET | `/deals/{id}` | Any | Deal detail + current stage |
| PATCH | `/deals/{id}` | Admin | Update name, borrower, amount_cr, notes |
| POST | `/deals/{id}/stage` | Admin | Change stage (body: `{to_stage, reason?}`) — appends to deal_stage_history |

### 3.3 Folders

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/folders` | Any | List all folder templates (id, name, display_order) |
| POST | `/folders` | Admin | Create folder template |
| PATCH | `/folders/{id}` | Admin | Rename or reorder |
| DELETE | `/folders/{id}` | Admin | Delete template (fails if any active documents reference it) |

### 3.4 Documents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/deals/{deal_id}/documents` | Any (folder-filtered) | All documents in this deal visible to the caller (respects folder permissions). Groups by folder. |
| POST | `/deals/{deal_id}/documents/init` | Contribute on folder | Initiate upload: returns `{doc_id, upload_url}` (upload_url is an internal path `/upload/{doc_id}`) |
| POST | `/upload/{doc_id}/chunk` | Uploader | Stream chunk (multipart; body: `{chunk_index, total_chunks, data: binary}`) |
| POST | `/upload/{doc_id}/complete` | Uploader | Finalize upload; creates approval request if needed |
| GET | `/deals/{deal_id}/documents/{doc_id}/download` | View on folder | Verify permission → generate 10-min presigned GET URL → 302 redirect |
| PATCH | `/deals/{deal_id}/documents/{doc_id}` | Admin or uploader | Rename display_name only |
| DELETE | `/deals/{deal_id}/documents/{doc_id}` | Admin or uploader | Request deletion (creates approval request) |

### 3.5 Tasks

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/deals/{deal_id}/tasks` | Any | All tasks for deal. Optional `?assigned_to=me` |
| POST | `/deals/{deal_id}/tasks` | Any | Create task |
| GET | `/tasks` | Any | My tasks across all deals (`?assigned_to=me`) |
| GET | `/deals/{deal_id}/tasks/{task_id}` | Any | Task detail + attachments + comments |
| PATCH | `/deals/{deal_id}/tasks/{task_id}` | Assignee or Admin | Update title, description, due_date, priority |
| POST | `/deals/{deal_id}/tasks/{task_id}/submit` | Assignee | Mark as awaiting_approval (attaches documents if provided) |
| POST | `/deals/{deal_id}/tasks/{task_id}/reassign` | Any | Request reassignment (creates approval if not admin) |
| DELETE | `/deals/{deal_id}/tasks/{task_id}` | Admin or creator | Request delete (creates approval if not admin) |

### 3.6 Comments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/deals/{deal_id}/comments` | Any | Deal-level comments |
| POST | `/deals/{deal_id}/comments` | Any | Add comment (body: `{body, parent_id?}`) |
| GET | `/deals/{deal_id}/tasks/{task_id}/comments` | Any | Task comments |
| POST | `/deals/{deal_id}/tasks/{task_id}/comments` | Any | Add task comment |
| PATCH | `/comments/{id}` | Author | Edit comment body |

### 3.7 Approvals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/approvals` | can_approve | All pending approvals (newest first) |
| POST | `/approvals/bulk` | can_approve | Approve or reject multiple (body: `{ids: UUID[], action: "approve" \| "reject", note?}`) |
| POST | `/approvals/{id}/approve` | can_approve | Single approve |
| POST | `/approvals/{id}/reject` | can_approve | Single reject (body: `{note}`) |

**Approval side-effects (server-side, transactional):**
- `document_upload` approved → `documents.status = 'active'`; check if parent task can move to 'done'
- `document_upload` rejected → `documents.status = 'rejected'`; parent task status = 'needs_attention'
- `document_delete` approved → `documents.status = 'deleted'`; schedule OCI object deletion via background job
- `task_reassign` approved → `tasks.assigned_to = proposed_assignee`
- `task_delete` approved → hard delete task row (tasks are not sensitive financial records; only audit_log entry survives)

### 3.8 Permissions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/permissions` | Admin | Full permission matrix: all users × all folders |
| PUT | `/admin/permissions/{user_id}/{folder_id}` | Admin | Set access level |

### 3.9 Users / Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/users` | Admin | List all users |
| POST | `/admin/users` | Admin | Invite user (creates account, sends email) |
| PATCH | `/admin/users/{id}` | Admin | Update role, can_approve, is_active |
| GET | `/admin/audit-log` | Admin | Query audit log (`?entity_id=&entity_type=&from=&to=&limit=50`) |
| GET | `/admin/archive` | Admin | List deleted documents |
| POST | `/admin/archive/{doc_id}/purge` | Admin | Permanently delete from OCI (irreversible) |

### 3.10 Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{status: "ok", db: "ok", storage: "ok"}`. Used by Cloudflare Tunnel health check. |

---

## 4. Upload Flow

```
Browser                     FastAPI                    OCI Object Storage
  │                            │                              │
  │  POST /deals/{id}/docs/init│                              │
  │  {filename, size, sha256,  │                              │
  │   mime_type, folder_id}    │                              │
  │──────────────────────────►│                              │
  │                            │ INSERT documents(status=uploading)
  │                            │ generate object_key = deals/{deal_id}/{doc_id}
  │◄──────────────────────────│                              │
  │  {doc_id, upload_path}     │                              │
  │                            │                              │
  │  [for each 32MB chunk]     │                              │
  │  POST /upload/{doc_id}/chunk                              │
  │  multipart: chunk_index,   │                              │
  │  total_chunks, data        │                              │
  │──────────────────────────►│                              │
  │                            │ buffer chunk, PUT to OCI     │
  │                            │─────────────────────────────►│
  │◄──────────────────────────│                              │
  │  {received: true}          │                              │
  │                            │                              │
  │  POST /upload/{doc_id}/complete                           │
  │──────────────────────────►│                              │
  │                            │ verify SHA256 against stored │
  │                            │ check dedup constraint       │
  │                            │ UPDATE documents(status=pending)
  │                            │ INSERT approval_requests(document_upload)
  │◄──────────────────────────│                              │
  │  {doc_id, status: pending} │                              │
```

**Dedup check:** Before inserting, query `documents` for `(deal_id, sha256)` where status is active/pending/uploading. If found, return `{duplicate: true, existing_doc_id}`. Client shows warning before proceeding.

**Auto-approve path:** If uploader has `can_approve = true`, skip approval request and set status directly to `active`.

---

## 5. Download Flow

```
Browser                     FastAPI                    OCI Object Storage
  │                            │                              │
  │  GET /deals/{id}/docs/{doc_id}/download                   │
  │──────────────────────────►│                              │
  │                            │ check user permission on folder
  │                            │ check document.status == 'active'
  │                            │                              │
  │                            │ boto3.generate_presigned_url(
  │                            │   'get_object',
  │                            │   Params={
  │                            │     'Bucket': BUCKET,
  │                            │     'Key': doc.object_key,
  │                            │     'ResponseContentDisposition':
  │                            │       f'attachment; filename="{doc.display_name}"'
  │                            │   },
  │                            │   ExpiresIn=600
  │                            │ )
  │◄──────────────────────────│                              │
  │  302 redirect to presigned URL                            │
  │                            │                              │
  │  GET presigned URL         │                              │
  │─────────────────────────────────────────────────────────►│
  │◄─────────────────────────────────────────────────────────│
  │  file download             │                              │
```

The browser follows the redirect automatically. No CORS issue here — the redirect happens at the HTTP level, not a JS fetch.

---

## 6. Approval Queue Flow

```
Admin (Samir)               FastAPI                    Background Jobs
  │                            │                              │
  │  GET /approvals            │                              │
  │──────────────────────────►│                              │
  │◄──────────────────────────│                              │
  │  [{id, type, document{     │                              │
  │    deal.name, folder.name, │                              │
  │    display_name, size,     │                              │
  │    uploaded_by, created_at │                              │
  │  }}, ...]                  │                              │
  │                            │                              │
  │  [select checkboxes]       │                              │
  │                            │                              │
  │  POST /approvals/bulk      │                              │
  │  {ids: [...], action: "approve"}                          │
  │──────────────────────────►│                              │
  │                            │ BEGIN transaction             │
  │                            │ for each id:                  │
  │                            │   UPDATE approval_requests(approved)
  │                            │   apply side-effect:          │
  │                            │     doc → status=active       │
  │                            │     check task auto-complete  │
  │                            │   INSERT audit_log            │
  │                            │ COMMIT                        │
  │◄──────────────────────────│                              │
  │  {approved: N, errors: []} │                              │
```

---

## 7. Auth and Session Design

**Provider:** `fastapi-users` with `httpOnly` cookie transport.

```python
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import CookieTransport, AuthenticationBackend
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pwdlib.hashers.argon2 import Argon2Hasher

cookie_transport = CookieTransport(
    cookie_name="lilkis_session",
    cookie_max_age=86400 * 7,   # 7 days
    cookie_secure=True,          # HTTPS only
    cookie_httponly=True,        # No JS access
    cookie_samesite="lax",       # CSRF mitigation
)
```

**Why httpOnly cookie (not JWT in localStorage):**
- localStorage is readable by JS; a single XSS bug compromises all sessions
- httpOnly cookie is invisible to JS even after XSS
- SameSite=lax blocks CSRF on state-mutating requests from cross-origin navigations

**CORS config (FastAPI):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://deals.lilkis.in"],
    allow_credentials=True,         # required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Session expiry:** 7-day sliding window. Activity extends the cookie. Idle > 7 days → re-login.

---

## 8. Background Jobs (procrastinate)

procrastinate uses PostgreSQL as its backing store. No Redis, no external queue, no n8n. The worker runs as a separate process in the same Docker Compose stack.

| Job name | Trigger | What it does |
|----------|---------|--------------|
| `send_notification_email` | After approval_request created | Sends email to admin(s) with `can_approve=true` |
| `send_task_reminder` | Daily at 08:00 IST | Finds tasks with `due_date = today + 1` and emails assignee |
| `purge_object` | After `document_delete` approved | Calls `s3.delete_object(Bucket, Key)`; logs to audit_log. Note: app key has no delete permission by default; this job uses a separate admin-only key stored in env |
| `check_archive_retention` | Weekly on Sunday | If `archive_retention_days` setting is not null, hard-deletes documents where `approved_at < now() - interval` |

```python
import procrastinate

app_procrastinate = procrastinate.App(
    connector=procrastinate.SyncPsycopg2Connector(
        json_dumps=lambda x: json.dumps(x, default=str)
    )
)

@app_procrastinate.task(queue="default", retry=3)
def send_notification_email(to: str, subject: str, body: str) -> None:
    ...
```

**Idempotency:** Every job checks its target state before acting. If a document is already `active` when `purge_object` runs, it logs a warning and exits cleanly. Scheduled reminder jobs use `lock` parameter to prevent duplicate sends.

---

## 9. Storage Layout

```
OCI Bucket: lilkis-deals
├── deals/
│   └── {deal_id}/          ← one "directory" per deal
│       └── {document_id}   ← filename is UUID, no extension
```

**Object metadata (stored in OCI object metadata, not in key):**
- `original-name`: original filename with extension
- `mime-type`: MIME type
- `uploaded-by`: user UUID

**Versioning:** OCI Object Storage versioning enabled on the bucket. Previous versions are retained and recoverable by admin via OCI console.

**Access policy:** App credential (`lilkis_app_key`) has:
- `OBJECT_READ` (GET, presigned GET)
- `OBJECT_CREATE` (PUT, multipart)
- No `OBJECT_DELETE`

Deletions go through a separate `lilkis_admin_key` used only by the `purge_object` background job. This key is stored as a separate env var (`OCI_ADMIN_ACCESS_KEY_ID`, `OCI_ADMIN_SECRET_ACCESS_KEY`) and never used for anything else.

---

## 10. Docker Compose

```yaml
# /opt/lilkis/docker-compose.yml
# Deploy: docker compose -f docker-compose.yml up -d

version: "3.9"

services:
  postgres:
    image: postgres:16-bookworm
    platform: linux/arm64
    container_name: lilkis-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: lilkis_admin
      POSTGRES_PASSWORD: ${POSTGRES_ADMIN_PASSWORD}
      POSTGRES_DB: lilkis
    volumes:
      - pg_data:/var/lib/postgresql/data
    command: >
      postgres
        -c shared_buffers=2GB
        -c effective_cache_size=6GB
        -c maintenance_work_mem=256MB
        -c max_connections=50
        -c work_mem=16MB
        -c wal_level=replica
        -c checkpoint_completion_target=0.9
        -c random_page_cost=1.1
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lilkis_admin -d lilkis"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  api:
    image: ghcr.io/lilkis/api:${API_VERSION:-latest}
    platform: linux/arm64
    container_name: lilkis-api
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://lilkis_app:${POSTGRES_APP_PASSWORD}@postgres/lilkis
      SECRET_KEY: ${SECRET_KEY}
      OCI_ENDPOINT_URL: ${OCI_ENDPOINT_URL}
      OCI_BUCKET: ${OCI_BUCKET}
      OCI_ACCESS_KEY_ID: ${OCI_ACCESS_KEY_ID}
      OCI_SECRET_ACCESS_KEY: ${OCI_SECRET_ACCESS_KEY}
      OCI_ADMIN_ACCESS_KEY_ID: ${OCI_ADMIN_ACCESS_KEY_ID}
      OCI_ADMIN_SECRET_ACCESS_KEY: ${OCI_ADMIN_SECRET_ACCESS_KEY}
      SMTP_HOST: ${SMTP_HOST}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USER: ${SMTP_USER}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      EMAIL_FROM: ${EMAIL_FROM:-noreply@lilkis.in}
      ENVIRONMENT: production
    ports:
      - "8000:8000"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - internal
      - external

  worker:
    image: ghcr.io/lilkis/api:${API_VERSION:-latest}
    platform: linux/arm64
    container_name: lilkis-worker
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://lilkis_app:${POSTGRES_APP_PASSWORD}@postgres/lilkis
      # (all same env vars as api)
    command: procrastinate --app=app.jobs.procrastinate_app worker
    networks:
      - internal

  cloudflared:
    image: cloudflare/cloudflared:latest
    platform: linux/arm64
    container_name: lilkis-tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - api
    networks:
      - external

volumes:
  pg_data:
    driver: local

networks:
  internal:
    driver: bridge
  external:
    driver: bridge
```

**Note on memory:** 2 GB `shared_buffers` + 2 uvicorn workers + 1 procrastinate worker + cloudflared on 12 GB RAM is safe. Do not run more than 2 uvicorn workers without testing OOM first.

---

## 11. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://lilkis_app:{password}@postgres/lilkis` |
| `SECRET_KEY` | Yes | 64+ char random string; used for HMAC signatures |
| `OCI_ENDPOINT_URL` | Yes | `https://{namespace}.compat.objectstorage.ap-mumbai-1.oraclecloud.com` |
| `OCI_BUCKET` | Yes | `lilkis-deals` |
| `OCI_ACCESS_KEY_ID` | Yes | App key (no delete permission) |
| `OCI_SECRET_ACCESS_KEY` | Yes | App key secret |
| `OCI_ADMIN_ACCESS_KEY_ID` | Yes | Admin key (delete permission; purge job only) |
| `OCI_ADMIN_SECRET_ACCESS_KEY` | Yes | Admin key secret |
| `SMTP_HOST` | Yes | Mail server hostname |
| `SMTP_PORT` | No | Default 587 |
| `SMTP_USER` | Yes | SMTP username |
| `SMTP_PASSWORD` | Yes | SMTP password |
| `EMAIL_FROM` | No | Default `noreply@lilkis.in` |
| `ENVIRONMENT` | No | `production` or `development` (controls debug logging) |
| `POSTGRES_ADMIN_PASSWORD` | Yes | Admin Postgres password (for postgres container) |
| `POSTGRES_APP_PASSWORD` | Yes | App Postgres user password |
| `CLOUDFLARE_TUNNEL_TOKEN` | Yes | Cloudflare Tunnel credential |
| `API_VERSION` | No | Docker image tag; defaults to `latest` |

All secrets stored on VM at `/opt/lilkis/.env`, permissions `600`, owned by deploy user. Never committed to git.

---

## 12. Security Checklist

| Item | Implementation |
|------|----------------|
| Session tokens | httpOnly + Secure + SameSite=lax cookie only |
| Passwords | argon2id via fastapi-users (memory=64MB, iterations=3, parallelism=2) |
| HTTPS | Enforced by Cloudflare Tunnel (TLS 1.2+) |
| CORS | Allowlist: `https://deals.lilkis.in` only |
| Authorization | Every API endpoint checks role + folder permission via dependency |
| Audit log integrity | DB role cannot UPDATE or DELETE audit_log rows |
| File storage | Object key is UUID (never filename); presigned URLs expire in 10 min |
| File delete | App key has no delete permission; purge uses separate admin key |
| Input validation | Pydantic v2 on all request bodies; strict mode |
| SQL injection | SQLAlchemy parameterized queries; no raw string interpolation |
| Rate limiting | `slowapi` on `/auth/login` (5 requests/minute per IP) |
| Sensitive data in logs | Mask passwords, secrets in structured logging |
| Backup encryption | pg_dump piped through `gpg --encrypt` before uploading to OCI |
| Secrets on VM | `.env` at `600`; deploy user only; not in Docker image |

---

## 13. Observability

**Structured logging (JSON):**
```python
import structlog
log = structlog.get_logger()
log.info("document.uploaded", doc_id=str(doc_id), deal_id=str(deal_id), size=size_bytes)
```

**Health check endpoint:** `GET /health` — called by Cloudflare Tunnel every 30 seconds. Checks DB connectivity and OCI reachability (HEAD request to bucket). Returns 503 if either is down; Cloudflare stops routing traffic to the origin.

**Metrics (later):** When OCI load justifies it, add Prometheus metrics via `prometheus-fastapi-instrumentator`. For now, structured logs are sufficient.

---

## 14. Backups

```bash
# /opt/lilkis/backup.sh — runs daily via crontab
#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/lilkis_${TIMESTAMP}.sql.gz.gpg"

# Dump, compress, encrypt
docker exec lilkis-postgres pg_dump \
    -U lilkis_admin \
    -d lilkis \
    --no-password \
    | gzip \
    | gpg --batch --yes --symmetric --passphrase "${BACKUP_PASSPHRASE}" \
    > "${BACKUP_FILE}"

# Upload to OCI (separate backup bucket)
aws s3 cp "${BACKUP_FILE}" \
    "s3://${BACKUP_BUCKET}/postgres/${TIMESTAMP}.sql.gz.gpg" \
    --endpoint-url "${OCI_ENDPOINT_URL}"

rm "${BACKUP_FILE}"
echo "Backup complete: ${TIMESTAMP}"
```

**Retention:** 30 daily backups kept in the backup bucket. OCI Lifecycle Policy auto-deletes objects older than 30 days.

**Restore test:** Run the restore procedure manually once a month:
```bash
# Pull latest backup
aws s3 cp s3://${BACKUP_BUCKET}/postgres/LATEST.sql.gz.gpg /tmp/restore.sql.gz.gpg \
    --endpoint-url "${OCI_ENDPOINT_URL}"

gpg --decrypt --passphrase "${BACKUP_PASSPHRASE}" /tmp/restore.sql.gz.gpg \
    | gunzip \
    | docker exec -i lilkis-postgres psql -U lilkis_admin -d lilkis_restore
```

---

## 15. Cost Model

| Component | Service | Monthly Cost |
|-----------|---------|-------------|
| Compute (2 OCPU, 12 GB) | OCI A1 ARM (Always Free) | $0 |
| Block storage 50 GB | OCI Always Free | $0 |
| Object storage < 10 GB | OCI Always Free | $0 |
| Object storage > 10 GB | OCI PAYG (~$0.0255/GB/month) | < $1 |
| Egress < 10 TB/month | OCI Always Free | $0 |
| Cloudflare Pages | Cloudflare Free | $0 |
| Cloudflare Tunnel | Cloudflare Free | $0 |
| Email (SMTP) | Gmail SMTP or Mailgun Flex | $0–3 |
| Backups (< 10 GB encrypted) | OCI Always Free | $0 |
| **Total** | | **$0–4/month** |

**Always Free caveat:** OCI may reclaim Always Free VMs that remain idle for 7+ days. Workaround: upgrade the account to Pay-As-You-Go (PAYG). PAYG enables the Always Free resource tier with no idle-reclaim risk. A1 Flex costs nothing unless you exceed the free tier; actual compute charges are ~$0.01/OCPU-hour if you did exceed.

---

## 16. OCI Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Idle VM reclaimed after 7 days | Upgrade to Pay-As-You-Go to prevent reclaim; configure health check pings |
| A1 capacity unavailable in ap-mumbai-1 at creation time | Retry next day; OCI A1 availability is sporadic. Alternative: ap-hyderabad-1 |
| OCI CORS fixed headers blocking direct browser PUT | All uploads proxy through API — this is the default design, no CORS dependency |
| OCI managed Postgres cost | Already resolved: self-hosted Postgres in Docker on VM |
| Tunnel outage (Cloudflare) | Health check will fail; Cloudflare will surface error page. OCI has no alternative inbound unless we open a port. Acceptable for internal tool. |
| VM disk full | Monitor `/var/lib/docker` (postgres data volume) + OCI object storage. PG data compresses well; 50 GB block storage is plenty for months. |

---

## 17. AWS Migration Runbook

When ready to move to AWS (more reliability, managed services, team grows):

| Step | Action |
|------|--------|
| 1 | Provision RDS PostgreSQL 16 (db.t4g.small ~$25/month) in ap-south-1 |
| 2 | Create S3 bucket `lilkis-deals` in ap-south-1; enable versioning |
| 3 | Create IAM role for app (no delete permission on S3) |
| 4 | Copy OCI bucket to S3: `rclone copy oci:lilkis-deals s3:lilkis-deals` (OCI egress is free up to 10 TB) |
| 5 | Dump Postgres: `pg_dump | gzip` → upload to S3 → `pg_restore` into RDS |
| 6 | Update `.env`: swap `OCI_ENDPOINT_URL`, `OCI_BUCKET` → `AWS_REGION`, keep same `boto3` client calls |
| 7 | Swap Cloudflare Tunnel target from OCI VM to ECS/EC2 |
| 8 | Test all nine Day-1 spikes against new infra |
| 9 | Cut DNS (`api.lilkis.in`) to new tunnel |

**Why this migration is easy:** The backend uses `boto3` with `endpoint_url` for OCI. Removing `endpoint_url` makes `boto3` route to AWS S3. All S3 API calls (presigned URLs, PUT, GET) work identically. No OCI SDK anywhere in the codebase.

---

## 18. Nine Day-1 Spike Tests

Run these before writing any feature code. Each spike should take under 30 minutes. If any spike fails, the architecture must change — not the spike.

| ID | Spike | Pass Criteria |
|----|-------|--------------|
| S1 | Provision A1 ARM (2 OCPU, 12 GB) in ap-mumbai-1 | VM boots, SSH in, `uname -m` returns `aarch64` |
| S2 | Create OCI bucket, generate presigned PUT URL via boto3, attempt `fetch(url, {method:'PUT', body: file})` from the browser | Either succeeds (good, CORS is fine) or fails with CORS error (expected — confirms proxy-upload is required) |
| S3 | Try S3 POST policy browser upload (browser POSTs directly to OCI with form fields) | Same as S2 — confirms or denies direct browser upload path |
| S4 | Generate presigned GET URL with `ResponseContentDisposition`, open URL in browser | File downloads with correct filename (not UUID) |
| S5 | With app credential only, attempt `s3.delete_object(Bucket, Key)` via boto3 | Returns 403 Forbidden — confirms app key has no delete permission |
| S6 | Stream a 300 MB file through Cloudflare Tunnel to FastAPI in 32 MB chunks | Completes without timeout or truncation; Cloudflare 100 MB body limit does not apply to chunked streams |
| S7 | Frontend on Cloudflare Pages (`deals.lilkis.in`) makes `fetch` with `credentials: 'include'` to API (`api.lilkis.in`) | Cookie is set and sent on subsequent requests — confirms cross-origin cookie flow works |
| S8 | `pg_dump` on VM → upload to OCI bucket → `pg_restore` into a fresh database | Restore completes; spot-check 3 tables for row count parity |
| S9 | Build Docker image with `buildx --platform linux/arm64`, push to GHCR, pull on VM, run | Container runs without segfault or architecture error |

---

## 19. Repo Structure

```
lilkis-deal-room/
├── backend/
│   ├── AGENTS.md               ← backend-specific agent context
│   ├── app/
│   │   ├── main.py             ← FastAPI app init, middleware, router includes
│   │   ├── database.py         ← SQLAlchemy async engine + session factory
│   │   ├── models/             ← SQLAlchemy ORM models (one file per table group)
│   │   ├── schemas/            ← Pydantic v2 request/response schemas
│   │   ├── routers/            ← FastAPI routers (auth, deals, documents, tasks, approvals, admin)
│   │   ├── services/           ← Business logic (approval_service, document_service, task_service)
│   │   ├── jobs/               ← procrastinate tasks (notifications, reminders, purge, retention)
│   │   ├── storage.py          ← boto3 wrapper (upload chunk, presign get, delete)
│   │   └── auth.py             ← fastapi-users setup
│   ├── alembic/                ← database migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── AGENTS.md               ← frontend-specific agent context
│   ├── src/
│   │   ├── api/                ← TanStack Query hooks (useDeals, useDocuments, useTasks, ...)
│   │   ├── components/         ← shadcn/ui + custom components
│   │   ├── pages/              ← route-level components
│   │   ├── stores/             ← Zustand (auth state only)
│   │   └── main.tsx
│   ├── public/
│   │   └── fonts/              ← Inter woff2 self-hosted
│   └── package.json
├── AGENTS.md                   ← root agent context (this file's companion)
├── PRD.md                      ← what we're building
├── ARCHITECTURE.md             ← this file
├── CLAUDE.md                   ← how to build it
├── DESIGN.md                   ← how it looks
├── docker-compose.yml
└── .env.example
```
