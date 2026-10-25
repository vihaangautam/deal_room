#!/usr/bin/env bash
#
# Nightly database backup: dump, encrypt, upload, prune, verify.
#
#   /opt/lilkis/ops/backup.sh
#
# The documents themselves live in S3 and are not in here — they are
# backed up separately by sync-documents.sh, to a different provider.
# This is the database: who everyone is, which deal each file belongs to,
# the permission matrix, the tasks, the comments and the audit log.
# Without it the bucket is a pile of UUIDs with no meaning.
#
# Every step is checked. A backup job that fails quietly is worse than no
# backup job, because it also removes the worry that would have made
# someone look.
#
# Restoring: ops/restore.sh. Do it once before go-live, not for the first
# time in an emergency — see GUIDE.md Phase 7.3.

set -euo pipefail

LILKIS_DIR="${LILKIS_DIR:-/opt/lilkis}"
COMPOSE="docker compose -f ${LILKIS_DIR}/docker-compose.prod.yml"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
# The schema's table count. Bump it when a migration adds a table; a
# dump with fewer than this did not finish.
EXPECT_TABLES="${BACKUP_EXPECT_TABLES:-13}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
DUMP="${WORK}/lilkis_${STAMP}.sql.gz"
ENCRYPTED="${DUMP}.gpg"

trap 'rm -rf "${WORK}"' EXIT

fail() { echo "BACKUP FAILED: $*" >&2; exit 1; }
say()  { echo "[$(date -u +%H:%M:%SZ)] $*"; }

# ── Configuration ────────────────────────────────────────────────────
# Read from the same .env the stack uses, so there is one place where
# credentials live and one place to rotate them.
[ -f "${LILKIS_DIR}/.env" ] || fail "no ${LILKIS_DIR}/.env"
set -a; . "${LILKIS_DIR}/.env"; set +a

: "${POSTGRES_ADMIN_PASSWORD:?missing in .env}"
: "${BACKUP_BUCKET:?set BACKUP_BUCKET in .env - a DIFFERENT bucket from the documents}"
: "${BACKUP_PASSPHRASE:?set BACKUP_PASSPHRASE in .env - and keep a copy somewhere else}"

# Dedicated credentials if they exist, otherwise the purge key. A backup
# written with a key that can also delete the live documents is weaker
# than it looks: one stolen credential reaches both the originals and the
# copies. Worth fixing, not worth blocking tonight's backup over.
if [ -n "${BACKUP_ACCESS_KEY_ID:-}" ]; then
    export AWS_ACCESS_KEY_ID="${BACKUP_ACCESS_KEY_ID}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_SECRET_ACCESS_KEY}"
else
    say "WARNING: no BACKUP_ACCESS_KEY_ID; falling back to the purge key."
    say "         Create a backup-only IAM user - GUIDE.md Phase 7.1."
    export AWS_ACCESS_KEY_ID="${OCI_ADMIN_ACCESS_KEY_ID}"
    export AWS_SECRET_ACCESS_KEY="${OCI_ADMIN_SECRET_ACCESS_KEY}"
fi
export AWS_DEFAULT_REGION="${AWS_REGION:-ap-south-1}"

command -v aws >/dev/null || fail "aws CLI missing. Run: sudo apt install -y awscli"
command -v gpg >/dev/null || fail "gpg missing. Run: sudo apt install -y gnupg"

# ── Dump ─────────────────────────────────────────────────────────────
say "dumping"
# --clean --if-exists so the restore can run against a database that
# already has objects in it, which is the realistic case.
${COMPOSE} exec -T -e PGPASSWORD="${POSTGRES_ADMIN_PASSWORD}" postgres \
    pg_dump -U lilkis_admin -d lilkis --clean --if-exists \
    | gzip -9 > "${DUMP}" \
    || fail "pg_dump"

# A dump of an empty or half-connected database still produces a valid
# gzip. Check what is IN it, not how big it is: a freshly deployed room
# with two users and no documents dumps to a couple of KB, while a year
# of real use dumps to megabytes, so no single size threshold is right
# for both. A truncated dump, which is the failure worth catching, is
# missing tables at any size.
gzip -t "${DUMP}" || fail "dump is not valid gzip"
TABLES=$(gunzip -c "${DUMP}" | grep -c '^CREATE TABLE' || true)
[ "${TABLES}" -ge "${EXPECT_TABLES}" ]     || fail "dump has ${TABLES} CREATE TABLE statements, expected ${EXPECT_TABLES} - it is truncated"
SIZE=$(stat -c%s "${DUMP}")
say "dumped ${SIZE} bytes, ${TABLES} tables"

# ── Encrypt ──────────────────────────────────────────────────────────
# It holds every email address, the whole audit trail and the permission
# matrix for a SEBI-regulated room. It does not travel in the clear.
say "encrypting"
gpg --batch --yes --symmetric --cipher-algo AES256 \
    --passphrase "${BACKUP_PASSPHRASE}" \
    --output "${ENCRYPTED}" "${DUMP}" \
    || fail "gpg"

# ── Upload ───────────────────────────────────────────────────────────
KEY="db/$(basename "${ENCRYPTED}")"
say "uploading s3://${BACKUP_BUCKET}/${KEY}"
aws s3 cp "${ENCRYPTED}" "s3://${BACKUP_BUCKET}/${KEY}" --only-show-errors \
    || fail "upload"

# Read it back. An upload that reported success and left nothing behind
# is exactly the failure this whole script exists to prevent.
REMOTE=$(aws s3api head-object --bucket "${BACKUP_BUCKET}" --key "${KEY}" \
    --query ContentLength --output text 2>/dev/null) || fail "uploaded object not found"
LOCAL=$(stat -c%s "${ENCRYPTED}")
[ "${REMOTE}" = "${LOCAL}" ] || fail "uploaded ${LOCAL} bytes, bucket has ${REMOTE}"
say "verified ${REMOTE} bytes in the bucket"

# ── Prune ────────────────────────────────────────────────────────────
# Only ever after a verified upload, so a run that fails early never
# deletes the older backup that is currently the good one.
CUTOFF=$(date -u -d "${KEEP_DAYS} days ago" +%Y-%m-%d)
say "pruning anything before ${CUTOFF}"
aws s3api list-objects-v2 --bucket "${BACKUP_BUCKET}" --prefix "db/" \
    --query "Contents[?LastModified<'${CUTOFF}'].Key" --output text 2>/dev/null \
    | tr '\t' '\n' | grep -v '^None$' | grep . \
    | while read -r old; do
        say "  removing ${old}"
        aws s3 rm "s3://${BACKUP_BUCKET}/${old}" --only-show-errors
      done || true   # nothing to prune is not a failure

say "OK - ${KEY}"
