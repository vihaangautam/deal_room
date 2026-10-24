"""Prove the storage layer works against the real bucket, before anything
is deployed on top of it.

    python -m app.checks.storage_check

Every byte this app has ever stored went into S3Mock, a local fake that
is forgiving in ways a real provider is not. storage.py already carries
one workaround for S3Mock's behaviour (it strips the Expect header that
botocore adds to every PUT). Whether real object storage agrees about
signing, about multipart, and about what the application's key is allowed
to do, is unknown until something asks it.

This asks it. Run it against the real endpoint with the real keys and
read the last line.

It writes only to keys under a `__storage_check__/` prefix and removes
them with the admin key at the end, so running it against a bucket that
already holds documents is safe.
"""

import asyncio
import io
import os
import sys
import uuid

from botocore.exceptions import ClientError

from app.config import settings

# The very clients the application and the purge job use, so this tests
# the real configuration — path-style addressing, the Expect-header
# workaround and all — rather than a lookalike built here.
from app.storage import admin_client, app_client

PREFIX = "__storage_check__"
# Big enough to leave the trivial-body path without making this slow.
SAMPLE = 8 * 1024 * 1024


class Result:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def ok(self, what: str) -> None:
        print(f"  PASS  {what}")
        self.passed.append(what)

    def bad(self, what: str, why: str) -> None:
        print(f"  FAIL  {what}\n          {why}")
        self.failed.append((what, why))


def check_round_trip(app, bucket: str, key: str, r: Result) -> None:
    body = b"lilkis storage check " + uuid.uuid4().bytes
    try:
        app.put_object(Bucket=bucket, Key=key, Body=body)
        got = app.get_object(Bucket=bucket, Key=key)["Body"].read()
        if got == body:
            r.ok("upload and download, byte for byte")
        else:
            r.bad("upload and download", f"{len(body)} bytes in, {len(got)} out")
    except Exception as e:
        r.bad("upload and download", str(e))


def check_large_streamed_put(app, bucket: str, key: str, r: Result) -> None:
    """The shape a real document takes.

    The app does NOT use S3 multipart: upload.py chunks over HTTP from
    the browser, stages the chunks on disk, then hands storage.put_object
    one file handle for a single PUT (storage.py, CLAUDE.md §5.6). So the
    thing worth proving against the real endpoint is a streamed body of
    some size, not a multipart assembly nothing calls.

    A 2 GB file is the documented ceiling (PRD F5) and is not worth
    pushing over a home connection here — Phase 8 of GUIDE.md has you do
    one large upload over the tunnel once. This is big enough to leave
    the single-request-body path and catch an Expect-header or chunked
    -encoding problem.
    """
    body = io.BytesIO(b"x" * SAMPLE)
    try:
        app.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/pdf")
        size = app.head_object(Bucket=bucket, Key=key)["ContentLength"]
        if size == SAMPLE:
            r.ok(f"streamed PUT of {SAMPLE // (1024 * 1024)} MB, as a document arrives")
        else:
            r.bad("streamed PUT", f"expected {SAMPLE} bytes, got {size}")
    except Exception as e:
        r.bad("streamed PUT", f"{e}")


def check_presigned(app, bucket: str, key: str, r: Result) -> None:
    """PRD F5: downloads are a 10-minute presigned URL, not a proxy
    through the API. If this does not work, no document can be opened."""
    import urllib.request

    try:
        url = app.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=600
        )
    except Exception as e:
        r.bad("presigned URL generated", str(e))
        return
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            if resp.status == 200 and resp.read():
                r.ok("presigned URL fetched over plain HTTPS")
            else:
                r.bad("presigned URL fetched", f"HTTP {resp.status}")
    except Exception as e:  # urllib raises HTTPError for 4xx
        r.bad(
            "presigned URL fetched",
            f"{e} — a 403 here usually means the signature or the clock is off",
        )


def check_app_key_cannot_delete(app, bucket: str, key: str, r: Result) -> None:
    """The control, not a nicety.

    The application holds a key with no delete permission, so a bug or a
    compromised container cannot destroy a document — only the purge job
    can, with a different key. That is a claim about the bucket policy,
    and this is the only thing that tests it. If it fails, documents are
    one bug away from being gone.
    """
    try:
        app.delete_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("AccessDenied", "Forbidden", "NotAuthorized", "403"):
            r.ok("the app's key is REFUSED delete — the policy holds")
        else:
            r.bad("delete refused for the app key", f"refused, but with {code}: {e}")
        return

    # No exception means the delete went through.
    if "localhost" in (settings.oci_endpoint_url or "") or "127.0.0.1" in (
        settings.oci_endpoint_url or ""
    ):
        # Expected, and worth saying out loud rather than reading as a
        # bug: S3Mock has no permissions model, so both keys are the same
        # unrestricted access. Which means this control has never been
        # true in development — it only becomes true against real OCI
        # with the policy from GUIDE.md Phase 2.5. That is exactly why
        # this check exists.
        r.bad(
            "the app's key is REFUSED delete",
            "Delete succeeded — EXPECTED against S3Mock, which has no permissions "
            "at all. This check only means something against real OCI. Re-run it "
            "with the real endpoint before you trust the no-delete control.",
        )
        return

    r.bad(
        "the app's key is REFUSED delete",
        "DELETE SUCCEEDED against the real bucket. The policy is wrong — see "
        "GUIDE.md Phase 2.5. Until it is fixed, any bug in the app can destroy "
        "a document.",
    )


async def main() -> int:
    missing = [
        name
        for name in ("oci_endpoint_url", "oci_bucket", "oci_access_key_id", "oci_secret_access_key")
        if not getattr(settings, name, None)
    ]
    if missing:
        print("Not configured. Missing: " + ", ".join(m.upper() for m in missing))
        return 2

    bucket = settings.oci_bucket
    print(f"Endpoint : {settings.oci_endpoint_url}")
    print(f"Bucket   : {bucket}\n")

    app, admin = app_client, admin_client
    run = uuid.uuid4().hex[:8]
    simple, multi = f"{PREFIX}/{run}-simple", f"{PREFIX}/{run}-multi"
    r = Result()

    check_round_trip(app, bucket, simple, r)
    check_large_streamed_put(app, bucket, multi, r)
    check_presigned(app, bucket, simple, r)
    check_app_key_cannot_delete(app, bucket, simple, r)

    # Clean up with the key that is allowed to, which also proves the
    # purge job's key works — without that, nothing can ever be purged.
    try:
        for key in (simple, multi):
            admin.delete_object(Bucket=bucket, Key=key)
        r.ok("the purge key CAN delete — cleanup done")
    except Exception as e:
        r.bad(
            "the purge key can delete",
            f"{e} — test objects left under {PREFIX}/, remove them by hand",
        )

    print(f"\n{len(r.passed)} passed, {len(r.failed)} failed")
    if r.failed:
        print("\nNOT READY. Fix the above before deploying:")
        for what, _ in r.failed:
            print(f"  - {what}")
        return 1
    print("\nReady. Real object storage behaves the way the app expects.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
