#!/usr/bin/env bash
#
# Wipe everything and hand over a clean room.
#
#   /opt/lilkis/ops/reset-for-handover.sh
#
# For exactly one moment in this system's life: after you have tested it
# properly — uploads, approvals, deletions, permissions, the lot — and
# before the client puts anything real in. Test data in a document room
# is not untidiness, it is a folder of files nobody can tell apart from
# the real ones six months later.
#
# RUN THIS BEFORE HANDOVER, NEVER AFTER. There is no way to delete your
# test uploads and keep someone else's real ones; this removes every
# document and every row. Afterwards the room is as empty as the day it
# was built, with one owner account and nothing else.
#
# It takes a backup first, so even this is recoverable for 30 days.
#
# What it does:
#   1. backup.sh, and refuses to go on if that fails
#   2. deletes every object and every version from the documents bucket
#   3. drops the database and re-applies the schema
#   4. re-creates the owner, interactively
#
# The app's own key cannot delete anything (that is the point of it), so
# step 2 uses the purge key.

set -euo pipefail

LILKIS_DIR="${LILKIS_DIR:-/opt/lilkis}"
COMPOSE="docker compose -f ${LILKIS_DIR}/docker-compose.prod.yml"

fail() { echo "RESET FAILED: $*" >&2; exit 1; }
say()  { echo "[$(date -u +%H:%M:%SZ)] $*"; }

[ -f "${LILKIS_DIR}/.env" ] || fail "no ${LILKIS_DIR}/.env"
set -a; . "${LILKIS_DIR}/.env"; set +a
: "${OCI_BUCKET:?missing in .env}"

export AWS_ACCESS_KEY_ID="${OCI_ADMIN_ACCESS_KEY_ID}"
export AWS_SECRET_ACCESS_KEY="${OCI_ADMIN_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION="${AWS_REGION:-ap-south-1}"

command -v aws >/dev/null || fail "aws CLI missing. Run: sudo apt install -y awscli"

# ── Show what is about to go ─────────────────────────────────────────
PG="${COMPOSE} exec -T -e PGPASSWORD=${POSTGRES_ADMIN_PASSWORD} postgres psql -U lilkis_admin -d lilkis -tAc"
DEALS=$(${PG} 'select count(*) from deals' 2>/dev/null || echo '?')
DOCS=$(${PG} 'select count(*) from documents' 2>/dev/null || echo '?')
USERS=$(${PG} 'select count(*) from users' 2>/dev/null || echo '?')
OBJECTS=$(aws s3 ls "s3://${OCI_BUCKET}/" --recursive --summarize 2>/dev/null \
    | awk '/Total Objects:/ {print $3}' || echo '?')

cat <<WARNING

  ────────────────────────────────────────────────────────────────
   This DESTROYS everything in the Lilkis Deal Room on $(hostname).

     deals in the database      ${DEALS}
     documents in the database  ${DOCS}
     user accounts              ${USERS}
     objects in ${OCI_BUCKET}   ${OBJECTS}

   All of it goes: every document, every version of it, every deal,
   task, comment, approval and audit row, and every account.

   Only do this if those numbers are YOUR TEST DATA. If a client has
   put anything real in, stop now — nothing here can separate their
   files from yours.

   A backup is taken first and kept for 30 days, so this is
   recoverable with ops/restore.sh. The documents are not: deleting
   every version is final.
  ────────────────────────────────────────────────────────────────

WARNING

read -r -p "  Type the bucket name (${OCI_BUCKET}) to go ahead: " TYPED
[ "${TYPED}" = "${OCI_BUCKET}" ] || { echo "  Stopped. Nothing changed."; exit 1; }
read -r -p "  Last check — type DESTROY: " TYPED2
[ "${TYPED2}" = "DESTROY" ] || { echo "  Stopped. Nothing changed."; exit 1; }

# ── 1. Backup first ──────────────────────────────────────────────────
say "taking a backup before touching anything"
"${LILKIS_DIR}/ops/backup.sh" || fail "backup failed - refusing to destroy anything without one"

# ── 2. Empty the bucket, versions and all ────────────────────────────
# Versioning is on, so a plain delete leaves markers and every old
# version behind. For test data that is just clutter you pay to store.
say "emptying s3://${OCI_BUCKET}"
while :; do
    BATCH=$(aws s3api list-object-versions --bucket "${OCI_BUCKET}" --max-keys 500 \
        --query '{Objects: [].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps(d) if d.get("Objects") else "")' || true)
    [ -z "${BATCH}" ] && break
    echo "${BATCH}" > /tmp/lilkis_delete_batch.json
    aws s3api delete-objects --bucket "${OCI_BUCKET}" \
        --delete "file:///tmp/lilkis_delete_batch.json" >/dev/null || fail "delete-objects"
    say "  removed a batch"
done
rm -f /tmp/lilkis_delete_batch.json
say "bucket empty"

# ── 3. Fresh database ────────────────────────────────────────────────
# down -v drops the named volume, which is the only way to be sure
# nothing survives - a DELETE leaves sequences, and any row a later
# migration added.
say "destroying and rebuilding the database"
${COMPOSE} down -v >/dev/null || fail "compose down"
${COMPOSE} up -d >/dev/null || fail "compose up"

say "waiting for postgres"
for _ in $(seq 1 30); do
    ${COMPOSE} exec -T postgres pg_isready -U lilkis_admin -d lilkis >/dev/null 2>&1 && break
    sleep 2
done

say "applying the schema"
${COMPOSE} exec -T api python -m alembic upgrade head >/dev/null || fail "alembic"

# ── 4. The owner, again ──────────────────────────────────────────────
echo
say "creating the owner account"
echo
${COMPOSE} exec api python -m app.bootstrap

echo
say "done - clean room, one owner, nothing else"
echo
echo "  Sign in once yourself to confirm it works, then hand over."
echo "  Do not run this again after the client has added anything."
