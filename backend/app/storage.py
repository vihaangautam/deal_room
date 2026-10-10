"""boto3 wrapper — S3-compatible only, per CLAUDE.md §2.6 ("Use S3 API
only. Never import OCI SDK."). Points at S3Mock locally; Phase 3 repoints
OCI_ENDPOINT_URL/keys at real OCI Object Storage with no code change here
(ARCHITECTURE.md §17).

Two clients, matching ARCHITECTURE.md §9's access policy: the app key can
read and create objects but not delete; only a separate admin key (used by
the purge background job, not yet built) can delete. Locally both keys are
the same S3Mock placeholder credential, but the code shape is correct for
the real OCI cutover.
"""

from typing import IO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

_client_config = Config(s3={"addressing_style": "path"})


def _strip_expect_header(request, **kwargs) -> None:
    """botocore adds "Expect: 100-continue" to every S3 PUT. S3Mock never
    sends the interim 100-Continue response, so botocore's HTTP client
    waits for one that's never coming and the connection gets dropped —
    plain curl PUTting the same bytes works fine, confirming it's this,
    not the network or the bytes. Real AWS S3 (and real OCI, same API)
    handles this correctly, so this is dev-only — see _make_client."""
    request.headers.pop("Expect", None)


def _make_client(access_key: str, secret_key: str):
    client = boto3.client(
        "s3",
        endpoint_url=settings.oci_endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=_client_config,
    )
    if settings.environment != "production":
        client.meta.events.register("before-send.s3.PutObject", _strip_expect_header)
    return client


app_client = _make_client(settings.oci_access_key_id, settings.oci_secret_access_key)
admin_client = _make_client(settings.oci_admin_access_key_id, settings.oci_admin_secret_access_key)


def ensure_bucket() -> None:
    """Called once at app startup. Idempotent — the correct pattern
    against real OCI too, not just S3Mock's quirky env-var config (see
    docker-compose.yml's comment on why we don't rely on that)."""
    try:
        app_client.head_bucket(Bucket=settings.oci_bucket)
    except ClientError:
        app_client.create_bucket(Bucket=settings.oci_bucket)


def put_object(key: str, body: bytes | IO[bytes], content_type: str) -> None:
    """body may be an open file object — boto3 streams it rather than
    reading it into memory, which is the whole point at PRD F5's 2 GB
    per-file ceiling. Still a single PUT, not multipart (CLAUDE.md §5.6);
    2 GB is within S3's and OCI's 5 GB single-PUT limit."""
    app_client.put_object(Bucket=settings.oci_bucket, Key=key, Body=body, ContentType=content_type)


def object_exists(key: str) -> bool:
    """Used by the demo seed to spot rows whose object has gone. S3Mock
    keeps objects in a container temp dir and loses them on restart, while
    Postgres keeps its rows on a named volume — so a laptop reboot leaves
    every seeded document pointing at nothing."""
    try:
        app_client.head_object(Bucket=settings.oci_bucket, Key=key)
        return True
    except ClientError:
        return False


def delete_object(key: str) -> None:
    """Admin key only — PRD F10 purge. The app key has no delete
    permission against real OCI (ARCHITECTURE.md §9); S3Mock doesn't
    enforce that distinction, but admin_client keeps the code shape
    correct for the cutover."""
    admin_client.delete_object(Bucket=settings.oci_bucket, Key=key)


def presigned_download_url(key: str, filename: str, expires_in: int = 600) -> str:
    """ARCHITECTURE.md §5 / CLAUDE.md §10: never exceed 10 minutes."""
    return app_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.oci_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires_in,
    )
