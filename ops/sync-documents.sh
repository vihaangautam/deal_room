#!/usr/bin/env bash
#
# Copy every document to a second bucket, weekly.
#
#   /opt/lilkis/ops/sync-documents.sh
#
# The documents already have versioning and a no-delete policy on the
# primary bucket. Both of those protect against things going wrong
# *inside* the bucket. Neither protects against the bucket, the account,
# or the person holding the root credentials being the problem.
#
# So: a second copy, and the useful version of that is a copy somewhere
# the primary account's credentials cannot reach. A second bucket in the
# same AWS account is better than nothing and worse than it sounds.
# BACKUP_SYNC_ENDPOINT points this at another provider — Cloudflare R2 is
# the obvious one here since the tunnel already means a Cloudflare
# account, its free tier is 10 GB with no egress charges, and it speaks
# the same S3 API.
#
# Sync, never mirror. Nothing here deletes from the destination: if a
# document disappears from the primary for any reason at all, including
# a reason nobody meant, the copy is still there. The destination grows
# slowly and that is the entire point of it.

set -euo pipefail

LILKIS_DIR="${LILKIS_DIR:-/opt/lilkis}"
fail() { echo "DOCUMENT SYNC FAILED: $*" >&2; exit 1; }
say()  { echo "[$(date -u +%H:%M:%SZ)] $*"; }

[ -f "${LILKIS_DIR}/.env" ] || fail "no ${LILKIS_DIR}/.env"
set -a; . "${LILKIS_DIR}/.env"; set +a

: "${OCI_BUCKET:?missing in .env}"
: "${DOCS_MIRROR_BUCKET:?set DOCS_MIRROR_BUCKET in .env}"
: "${DOCS_MIRROR_ACCESS_KEY_ID:?set DOCS_MIRROR_ACCESS_KEY_ID in .env}"
: "${DOCS_MIRROR_SECRET_ACCESS_KEY:?set DOCS_MIRROR_SECRET_ACCESS_KEY in .env}"

command -v aws >/dev/null || fail "aws CLI missing. Run: sudo apt install -y awscli"

STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT

# Read side: the app's key. It can read everything and delete nothing,
# which is exactly the authority a backup reader should have.
say "listing the primary bucket"
AWS_ACCESS_KEY_ID="${OCI_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${OCI_SECRET_ACCESS_KEY}" \
AWS_DEFAULT_REGION="${AWS_REGION:-ap-south-1}" \
    aws s3 sync "s3://${OCI_BUCKET}/" "${STAGE}/" --only-show-errors \
    || fail "could not read the primary bucket"

COUNT=$(find "${STAGE}" -type f | wc -l)
say "${COUNT} objects staged"

# Write side: the mirror's own credentials and endpoint. A different
# provider means a different --endpoint-url; same-account S3 leaves it
# unset.
say "pushing to the mirror"
MIRROR_ARGS=(--only-show-errors)
[ -n "${DOCS_MIRROR_ENDPOINT:-}" ] && MIRROR_ARGS+=(--endpoint-url "${DOCS_MIRROR_ENDPOINT}")

AWS_ACCESS_KEY_ID="${DOCS_MIRROR_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${DOCS_MIRROR_SECRET_ACCESS_KEY}" \
AWS_DEFAULT_REGION="${DOCS_MIRROR_REGION:-auto}" \
    aws s3 sync "${STAGE}/" "s3://${DOCS_MIRROR_BUCKET}/" "${MIRROR_ARGS[@]}" \
    || fail "could not write to the mirror"

say "OK - ${COUNT} objects, mirror at ${DOCS_MIRROR_BUCKET}"
