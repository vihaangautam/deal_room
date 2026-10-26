#!/bin/bash
# The restricted role the application connects as (ARCHITECTURE.md §2.1).
# The migration GRANTs to it but cannot create it: a role is cluster-wide,
# not part of a database's schema, and Alembic runs as lilkis_admin inside
# the database that already exists.
#
# Postgres runs everything in /docker-entrypoint-initdb.d once, when the
# data volume is first initialised. Without this, `docker compose down -v`
# destroys the role and the next `alembic upgrade head` fails on
# "role lilkis_app does not exist".
#
# A .sh rather than the .sql this used to be, because .sql cannot read the
# environment and so had the password written into it. That meant the real
# one lived as a local modification to a tracked file on the server —
# conflicting with every git pull, one `git checkout` away from being
# replaced by the placeholder, and needing the "change it in two places"
# warning in GUIDE.md Phase 5.1. It now comes from the same variable the
# API connects with, so the two cannot disagree.
set -euo pipefail

: "${POSTGRES_APP_PASSWORD:?set POSTGRES_APP_PASSWORD - the API connects as this role}"

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lilkis_app') THEN
        CREATE ROLE lilkis_app WITH LOGIN PASSWORD '${POSTGRES_APP_PASSWORD}';
    END IF;
END
\$\$;
SQL

echo "lilkis_app role ready"
