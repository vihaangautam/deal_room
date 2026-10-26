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
# < /dev/null on each: ${PG} runs `docker compose exec -T`, which reads
# stdin. Without it these three swallow the answers to the two prompts
# below when the script is driven from a pipe, and the confirmation
# silently never arrives.
DEALS=$(${PG} 'select count(*) from deals' < /dev/null 2>/dev/null || echo '?')
DOCS=$(${PG} 'select count(*) from documents' < /dev/null 2>/dev/null || echo '?')
USERS=$(${PG} 'select count(*) from users' < /dev/null 2>/dev/null || echo '?')
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
# Versioning is on, so a plain delete leaves a marker and every old
# version behind. For test data that is clutter you pay to store, and
# the point of the reset is that none of it is there afterwards.
#
# The first version of this asked the AWS CLI for
#   --query '{Objects: [].{Key:Key,VersionId:VersionId}}'
# which projects [] over the RESPONSE OBJECT — whose keys are Versions,
# DeleteMarkers, IsTruncated — not over a list. It matched nothing, the
# loop broke on its first pass, and the script said "bucket empty" over
# 204 surviving objects. A deletion that reports success without
# deleting is the worst of the failure modes available here, so this is
# done in Python against the parsed response, and verified afterwards.
say "emptying s3://${OCI_BUCKET}"
# Through the api container's boto3, not the AWS CLI, for two reasons
# this bucket taught us the hard way:
#
#   * `aws s3api list-object-versions` is broken on this host — it exits
#     0 and prints "badly formed help string" instead of JSON, while
#     `aws s3 ls` works. A delete loop reading that gets nothing and
#     concludes there is nothing to delete.
#   * the first version asked for --query '{Objects: [].{...}}', which
#     projects [] over the RESPONSE OBJECT rather than a list, and so
#     matched nothing either.
#
# Both failed by finding no work and reporting success, over 204 live
# objects. boto3 raises instead, and the check at the end means this can
# only say the bucket is empty when it is.
#
# NOTE: needs s3:ListBucketVersions on the purge user. Without it this
# falls back to deleting current objects only, which hides them but
# leaves the prior versions and the storage they use.
${COMPOSE} exec -T api python <<'PY' || fail "could not empty the bucket"
from app.config import settings
from app.storage import admin_client

bucket = settings.oci_bucket
removed = 0

try:
    while True:
        page = admin_client.list_object_versions(Bucket=bucket, MaxKeys=500)
        # Delete markers too: a marker is itself a version, and the key
        # does not go away until it does.
        doomed = [
            {"Key": v["Key"], "VersionId": v["VersionId"]}
            for key in ("Versions", "DeleteMarkers")
            for v in page.get(key, [])
        ]
        if not doomed:
            break
        admin_client.delete_objects(
            Bucket=bucket, Delete={"Objects": doomed, "Quiet": True}
        )
        removed += len(doomed)
        print(f"  removed {removed} versions so far")

    left = admin_client.list_object_versions(Bucket=bucket, MaxKeys=1)
    if left.get("Versions") or left.get("DeleteMarkers"):
        raise SystemExit("bucket still has objects after the delete loop")
    print(f"  bucket empty - {removed} versions removed")

except admin_client.exceptions.ClientError as exc:
    if "ListBucketVersions" not in str(exc):
        raise
    print("  no s3:ListBucketVersions on the purge user - current objects only")
    while True:
        page = admin_client.list_objects_v2(Bucket=bucket, MaxKeys=500)
        keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if not keys:
            break
        admin_client.delete_objects(
            Bucket=bucket, Delete={"Objects": keys, "Quiet": True}
        )
        removed += len(keys)
        print(f"  removed {removed} objects so far")
    print(f"  {removed} objects removed; PRIOR VERSIONS REMAIN.")
    print("  Add s3:ListBucketVersions to lilkis-purge to clear them.")
PY

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
# -e passes the three LILKIS_BOOTSTRAP_* variables through if they are
# set, so an unattended run works; no -T, so without them it still
# prompts on the terminal. Adding -T forces the unattended path and takes
# the interactive one away, which is how a handover password ended up
# being set from inside a script.
${COMPOSE} exec     -e LILKIS_BOOTSTRAP_NAME -e LILKIS_BOOTSTRAP_EMAIL -e LILKIS_BOOTSTRAP_PASSWORD     api python -m app.bootstrap

echo
say "done - clean room, one owner, nothing else"
echo
echo "  Sign in once yourself to confirm it works, then hand over."
echo "  Do not run this again after the client has added anything."
