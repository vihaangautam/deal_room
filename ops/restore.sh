#!/usr/bin/env bash
#
# Restore the database from a backup.
#
#   ops/restore.sh                     # list what is available
#   ops/restore.sh lilkis_2026...gpg   # restore that one
#
# Written at the same time as backup.sh, deliberately. A restore script
# improvised during an outage is written by someone frightened, at speed,
# against a system they cannot currently see. This one gets rehearsed
# first (GUIDE.md Phase 7.3) so the real thing is a command you have
# already run rather than a procedure you are inventing.
#
# It will not run without you typing the name of the database back. That
# is not ceremony: this drops every table before it loads anything, and
# the one way it can make things worse is being run by accident.

set -euo pipefail

LILKIS_DIR="${LILKIS_DIR:-/opt/lilkis}"
COMPOSE="docker compose -f ${LILKIS_DIR}/docker-compose.prod.yml"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

fail() { echo "RESTORE FAILED: $*" >&2; exit 1; }
say()  { echo "[$(date -u +%H:%M:%SZ)] $*"; }

[ -f "${LILKIS_DIR}/.env" ] || fail "no ${LILKIS_DIR}/.env"
set -a; . "${LILKIS_DIR}/.env"; set +a
: "${BACKUP_BUCKET:?set BACKUP_BUCKET in .env}"
: "${BACKUP_PASSPHRASE:?set BACKUP_PASSPHRASE in .env}"

if [ -n "${BACKUP_ACCESS_KEY_ID:-}" ]; then
    export AWS_ACCESS_KEY_ID="${BACKUP_ACCESS_KEY_ID}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_SECRET_ACCESS_KEY}"
else
    export AWS_ACCESS_KEY_ID="${OCI_ADMIN_ACCESS_KEY_ID}"
    export AWS_SECRET_ACCESS_KEY="${OCI_ADMIN_SECRET_ACCESS_KEY}"
fi
export AWS_DEFAULT_REGION="${AWS_REGION:-ap-south-1}"

# ── No argument: show what there is ──────────────────────────────────
if [ $# -eq 0 ]; then
    echo "Backups in s3://${BACKUP_BUCKET}/db/ (newest last):"
    aws s3 ls "s3://${BACKUP_BUCKET}/db/" --human-readable | sort
    echo
    echo "Restore one with:  $0 <filename>"
    exit 0
fi

NAME="$(basename "$1")"
say "restoring ${NAME}"

# ── Fetch and decrypt before touching anything ───────────────────────
# In that order on purpose. If the passphrase is wrong or the object is
# corrupt, that is discovered while the running database is still intact.
aws s3 cp "s3://${BACKUP_BUCKET}/db/${NAME}" "${WORK}/${NAME}" --only-show-errors \
    || fail "could not download ${NAME}"

say "decrypting"
gpg --batch --yes --quiet --decrypt \
    --passphrase "${BACKUP_PASSPHRASE}" \
    --output "${WORK}/dump.sql.gz" "${WORK}/${NAME}" \
    || fail "decryption failed - wrong BACKUP_PASSPHRASE?"

gzip -t "${WORK}/dump.sql.gz" || fail "decrypted file is not valid gzip"
SIZE=$(stat -c%s "${WORK}/dump.sql.gz")
say "decrypted ${SIZE} bytes, looks like a real dump"

# ── Confirm ──────────────────────────────────────────────────────────
cat <<WARNING

  This REPLACES the current contents of the 'lilkis' database on
  $(hostname) with the contents of ${NAME}.

  Everything added since that backup was taken will be gone: documents
  uploaded, approvals decided, comments written. Files already in S3 stay
  in S3, but the database rows that know what they are will be whatever
  the backup says.

WARNING
read -r -p "  Type the database name (lilkis) to go ahead: " TYPED
[ "${TYPED}" = "lilkis" ] || { echo "  Stopped. Nothing changed."; exit 1; }

# ── Restore ──────────────────────────────────────────────────────────
# The API keeps connections open and would write during the load; stop it
# first and bring it back after, so nothing races the restore.
say "stopping the API"
${COMPOSE} stop api >/dev/null

say "loading"
if gunzip -c "${WORK}/dump.sql.gz" \
    | ${COMPOSE} exec -T -e PGPASSWORD="${POSTGRES_ADMIN_PASSWORD}" postgres \
        psql -U lilkis_admin -d lilkis -v ON_ERROR_STOP=1 >/dev/null
then
    say "loaded"
else
    say "load failed - starting the API again so the site is not left down"
    ${COMPOSE} start api >/dev/null
    fail "psql rejected the dump"
fi

say "starting the API"
${COMPOSE} start api >/dev/null

# ── Check it is actually usable ──────────────────────────────────────
sleep 5
USERS=$(${COMPOSE} exec -T -e PGPASSWORD="${POSTGRES_ADMIN_PASSWORD}" postgres \
    psql -U lilkis_admin -d lilkis -tAc 'select count(*) from users' 2>/dev/null || echo "?")
DEALS=$(${COMPOSE} exec -T -e PGPASSWORD="${POSTGRES_ADMIN_PASSWORD}" postgres \
    psql -U lilkis_admin -d lilkis -tAc 'select count(*) from deals' 2>/dev/null || echo "?")

say "restored: ${USERS} users, ${DEALS} deals"
echo
echo "Now sign in through the browser and open a deal. A row count proves"
echo "the load ran; only signing in proves the restore worked."
