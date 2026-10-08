-- The restricted role the application connects as (ARCHITECTURE.md §2.1).
-- The migration GRANTs to it but cannot create it: a role is cluster-wide,
-- not part of a database's schema, and Alembic runs as lilkis_admin inside
-- the database that already exists.
--
-- Postgres runs everything in /docker-entrypoint-initdb.d once, when the
-- data volume is first initialised. Without this, `docker compose down -v`
-- destroys the role and the next `alembic upgrade head` fails on
-- "role lilkis_app does not exist" — which is what the manual CREATE ROLE
-- step in backend/AGENTS.md was papering over.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lilkis_app') THEN
        CREATE ROLE lilkis_app WITH LOGIN PASSWORD 'localdevpassword';
    END IF;
END
$$;
