"""S3-compatible object storage helper.

Wraps boto3 with sane defaults for MinIO-in-dev / S3-in-prod. Used by ingestion
tasks to dump raw JSONL to the bronze bucket. Keeps a single client per process.
"""
from __future__ import annotations

import functools
import gzip
import io
import json
import logging
from collections.abc import Iterable
from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from django.conf import settings

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_s3_client():
    """One client per process — boto3 clients are thread-safe."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 5}),
    )


def put_jsonl_gz(bucket: str, key: str, records: Iterable[dict[str, Any]]) -> int:
    """Write an iterable of dicts to `s3://{bucket}/{key}` as gzip-compressed JSONL.

    Returns the number of records written. The function buffers in memory; for
    large dumps callers should chunk to keep peak memory bounded.
    """
    buffer = io.BytesIO()
    count = 0
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        for record in records:
            gz.write((json.dumps(record, default=str) + "\n").encode("utf-8"))
            count += 1

    buffer.seek(0)
    get_s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer,
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
    )
    logger.info(
        "bronze_write",
        extra={"bucket": bucket, "key": key, "record_count": count},
    )
    return count
