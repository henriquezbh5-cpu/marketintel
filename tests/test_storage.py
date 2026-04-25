from __future__ import annotations

import gzip
import io
import json

import boto3
import pytest

try:
    from moto import mock_aws  # moto >= 5
except ImportError:  # pragma: no cover
    mock_aws = None


@pytest.mark.unit
@pytest.mark.skipif(mock_aws is None, reason="moto not installed")
def test_put_jsonl_gz_writes_each_record(monkeypatch):
    from apps.core import storage

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="bronze")

        # Make storage.get_s3_client() use moto's client.
        storage.get_s3_client.cache_clear()
        monkeypatch.setattr(storage, "get_s3_client", lambda: s3)

        count = storage.put_jsonl_gz(
            "bronze",
            "test/key.jsonl.gz",
            ({"i": i} for i in range(3)),
        )
        assert count == 3

        body = s3.get_object(Bucket="bronze", Key="test/key.jsonl.gz")["Body"].read()
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
            lines = gz.read().decode("utf-8").strip().splitlines()
        assert [json.loads(line) for line in lines] == [{"i": 0}, {"i": 1}, {"i": 2}]
