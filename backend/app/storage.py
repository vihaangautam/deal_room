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


def put_object(key: str, body: bytes, content_type: str) -> None:
    app_client.put_object(Bucket=settings.oci_bucket, Key=key, Body=body, ContentType=content_type)


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
