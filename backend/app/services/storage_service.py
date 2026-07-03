"""S3 / MinIO storage. Media bytes go browser<->S3 directly via presigned URLs;
the API never proxies file content."""
from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_PRESIGN_EXPIRY = 3600  # 1 hour


def _client(endpoint_url: str | None = None):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _public_client():
    """Client whose endpoint is baked into presigned URLs the BROWSER uses."""
    return _client(endpoint_url=settings.s3_public_endpoint_url)


def ensure_bucket() -> None:
    s3 = _client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        s3.create_bucket(Bucket=settings.s3_bucket)
        log.info("created bucket", bucket=settings.s3_bucket)


def presign_put(s3_key: str, content_type: str, expires: int = _PRESIGN_EXPIRY) -> str:
    return _public_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presign_get(s3_key: str, expires: int = _PRESIGN_EXPIRY) -> str:
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": s3_key},
        ExpiresIn=expires,
    )


def head_object(s3_key: str) -> dict | None:
    """Return object metadata if it exists, else None."""
    try:
        resp = _client().head_object(Bucket=settings.s3_bucket, Key=s3_key)
        return {
            "size_bytes": resp.get("ContentLength"),
            "content_type": resp.get("ContentType"),
            "etag": resp.get("ETag", "").strip('"'),
        }
    except ClientError:
        return None


def download_to(s3_key: str, dest_path: str) -> None:
    _client().download_file(settings.s3_bucket, s3_key, dest_path)


def upload_file(local_path: str, s3_key: str, content_type: str = "image/jpeg") -> None:
    _client().upload_file(
        local_path,
        settings.s3_bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )
