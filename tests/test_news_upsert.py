from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apps.news.models import NewsArticle
from apps.news.services import ArticleRecord, extract_symbols, upsert_articles


@pytest.mark.unit
def test_extract_symbols_finds_uppercase_tokens():
    text = "BTC and ETH rallied while xrp lagged. SOL/USDT is hot."
    found = extract_symbols(text)
    assert {"BTC", "ETH", "SOL", "USDT"} <= found
    assert "xrp" not in found


@pytest.mark.integration
def test_upsert_is_idempotent_on_natural_key(coingecko_source):
    record = ArticleRecord(
        source_code="coingecko",
        external_id="abc123",
        title="BTC hits ATH",
        url="https://example.com/x",
        summary="BTC pumps",
        published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        sentiment="positive",
        sentiment_score=0.9,
        metadata={},
        mentioned_symbols=("BTC",),
    )
    upsert_articles([record])
    upsert_articles([record])
    assert NewsArticle.objects.count() == 1
