"""initial schema

Copied verbatim from ARCHITECTURE.md §2.1 — raw SQL, not op.create_table(),
because the schema uses Postgres features (partial unique indexes, a
plpgsql trigger function, dynamic DDL in a DO block, REVOKE/GRANT) that
don't map cleanly onto Alembic's table-builder API. This is the single
source of truth for the schema; app/models/ mirrors it for the ORM layer.

Revision ID: 5b520526179f
Revises:
Create Date: 2026-10-07 00:14:15.478224

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5b520526179f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
-- EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- USERS
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    hashed_pw     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'member'
                  CHECK (role IN ('admin','member')),
    can_approve   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- SESSIONS (fastapi-users manages cookie tokens; this table is for audit too)
CREATE TABLE access_tokens (
    token         TEXT PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX access_tokens_user_id_idx ON access_tokens(user_id);

-- FOLDER TEMPLATES (global master list — not per-deal)
CREATE TABLE folder_templates (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- USER FOLDER PERMISSIONS
CREATE TABLE user_folder_permissions (
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id     UUID NOT NULL REFERENCES folder_templates(id) ON DELETE CASCADE,
    access_level  TEXT NOT NULL DEFAULT 'view'
                  CHECK (access_level IN ('none','view','contribute')),
    granted_by    UUID NOT NULL REFERENCES users(id),
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, folder_id)
);

-- DEALS
CREATE TABLE deals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    borrower      TEXT NOT NULL,
    stage         TEXT NOT NULL DEFAULT 'new'
                  CHECK (stage IN ('new','running','successful','dropped')),
    amount_cr     NUMERIC(12,2),
    notes         TEXT,
    created_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX deals_stage_idx ON deals(stage);
CREATE INDEX deals_created_at_idx ON deals(created_at DESC);

-- DEAL STAGE HISTORY (append-only)
CREATE TABLE deal_stage_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id       UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    from_stage    TEXT,
    to_stage      TEXT NOT NULL,
    changed_by    UUID NOT NULL REFERENCES users(id),
    reason        TEXT,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX deal_stage_history_deal_idx ON deal_stage_history(deal_id, changed_at DESC);

-- DOCUMENTS
CREATE TABLE documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id          UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    folder_id        UUID NOT NULL REFERENCES folder_templates(id),
    display_name     TEXT NOT NULL,
    original_name    TEXT NOT NULL,
    mime_type        TEXT NOT NULL,
    size_bytes       BIGINT NOT NULL,
    sha256           TEXT NOT NULL,
    object_key       TEXT NOT NULL UNIQUE,
    status           TEXT NOT NULL DEFAULT 'uploading'
                     CHECK (status IN (
                       'uploading', 'pending', 'active',
                       'delete_requested', 'deleted', 'rejected'
                     )),
    version          INTEGER NOT NULL DEFAULT 1,
    uploaded_by      UUID NOT NULL REFERENCES users(id),
    approved_by      UUID REFERENCES users(id),
    approved_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX documents_deal_folder_idx ON documents(deal_id, folder_id);
CREATE INDEX documents_status_idx ON documents(status);

CREATE UNIQUE INDEX documents_dedup_uq ON documents (deal_id, sha256)
    WHERE status IN ('uploading','pending','active','delete_requested');

-- TASKS
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id         UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'todo'
                    CHECK (status IN (
                      'todo', 'in_progress', 'awaiting_approval',
                      'done', 'needs_attention'
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

-- TASK ATTACHMENTS
CREATE TABLE task_attachments (
    task_id         UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    attached_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, document_id)
);

-- COMMENTS
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

-- APPROVAL REQUESTS
CREATE TABLE approval_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL
                    CHECK (type IN (
                      'document_upload', 'document_delete',
                      'task_reassign', 'task_delete'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected')),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    task_id         UUID REFERENCES tasks(id) ON DELETE CASCADE,
    proposed_assignee UUID REFERENCES users(id),
    requested_by    UUID NOT NULL REFERENCES users(id),
    reviewed_by     UUID REFERENCES users(id),
    review_note     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ
);

CREATE UNIQUE INDEX approval_one_pending_doc  ON approval_requests (type, document_id) WHERE status = 'pending';
CREATE UNIQUE INDEX approval_one_pending_task ON approval_requests (type, task_id)     WHERE status = 'pending';
CREATE INDEX approval_status_idx ON approval_requests(status, created_at DESC);

-- SETTINGS (key-value store; admin-editable)
CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO settings (key, value) VALUES
  ('archive_retention_days', 'null'),
  ('email_notifications',    'true'),
  ('default_lead_days',      '14');

-- AUDIT LOG (append-only). The app role has INSERT + SELECT only.
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        UUID REFERENCES users(id),
    action          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    detail          JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX audit_log_entity_idx  ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX audit_log_actor_idx   ON audit_log(actor_id, created_at DESC);
CREATE INDEX audit_log_created_idx ON audit_log(created_at DESC);

-- PERMISSIONS FOR APP ROLE (role itself created manually — see backend/AGENTS.md)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM lilkis_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    users, access_tokens, folder_templates, user_folder_permissions,
    deals, deal_stage_history, documents, tasks, task_attachments,
    comments, approval_requests, settings
    TO lilkis_app;
GRANT USAGE ON SEQUENCE audit_log_id_seq TO lilkis_app;
GRANT INSERT, SELECT ON audit_log TO lilkis_app;

-- TRIGGER: updated_at auto-refresh
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
            'CREATE TRIGGER trg_%%s_updated_at BEFORE UPDATE ON %%s
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END; $$;
"""
# Note: %%s above (not %s) — psycopg's DBAPI driver treats a literal %s in
# any string passed to cursor.execute() as ITS OWN parameter placeholder,
# even though this %s is actually an argument to Postgres's own format()
# function, one level down. %% escapes it to a literal % for psycopg,
# which Postgres's format() then sees as the %s it expects.

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS settings CASCADE;
DROP TABLE IF EXISTS approval_requests CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS task_attachments CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS deal_stage_history CASCADE;
DROP TABLE IF EXISTS deals CASCADE;
DROP TABLE IF EXISTS user_folder_permissions CASCADE;
DROP TABLE IF EXISTS folder_templates CASCADE;
DROP TABLE IF EXISTS access_tokens CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP FUNCTION IF EXISTS set_updated_at CASCADE;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE_SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE_SQL)
