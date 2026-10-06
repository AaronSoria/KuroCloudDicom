"""Internal S3 helpers used by the volume computations. Not part of the public API."""
from __future__ import annotations

from typing import Any


def SplitS3Path(s3_path: str) -> tuple[str, str]:
    """Split an ``s3://bucket/prefix/`` path into ``(bucket, prefix)``.

    Also accepts the ``s3:///bucket/prefix/`` form returned by ``S3Path()``.
    A value without the ``s3://`` scheme is treated as a bare key prefix.
    """
    if not s3_path.startswith("s3://"):
        return "", s3_path
    bucket, _, prefix = s3_path[len("s3://"):].lstrip("/").partition("/")
    return bucket, prefix


def ListKeys(client: Any, bucket: str, prefix: str) -> list[str]:
    """Return every object key in ``bucket`` that starts with ``prefix``, following pagination."""
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []))
    return keys
