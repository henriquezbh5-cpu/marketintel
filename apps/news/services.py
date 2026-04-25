"""News upsert + tagging."""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from django.contrib.postgres.search import SearchVector
from django.db import transaction

from apps.instruments.models import Instrument

from .models import NewsArticle, Sentiment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArticleRecord:
    source_code: str
    external_id: str
    title: str
    url: str
    summary: str
    published_at: datetime
    sentiment: str
    sentiment_score: float | None
    metadata: dict
    mentioned_symbols: tuple[str, ...]


_SYMBOL_TOKEN = re.compile(r"\b([A-Z]{2,10})\b")


def extract_symbols(text: str) -> set[str]:
    """Lightweight ticker extractor. Production would use a learned NER model."""
    return set(_SYMBOL_TOKEN.findall(text or ""))


def upsert_articles(records: Iterable[ArticleRecord]) -> int:
    """Upsert articles + link to instruments. Idempotent on (source, external_id)."""
    from apps.instruments.models import Source

    count = 0
    sources_by_code: dict[str, Source] = {}

    for r in records:
        if r.source_code not in sources_by_code:
            sources_by_code[r.source_code] = Source.objects.get(code=r.source_code)
        source = sources_by_code[r.source_code]

        with transaction.atomic():
            article, _created = NewsArticle.objects.update_or_create(
                source=source,
                external_id=r.external_id,
                defaults=dict(
                    title=r.title,
                    url=r.url,
                    summary=r.summary,
                    published_at=r.published_at,
                    sentiment=r.sentiment if r.sentiment in Sentiment.values else Sentiment.NEUTRAL,
                    sentiment_score=r.sentiment_score,
                    metadata=r.metadata,
                ),
            )

            symbols = set(r.mentioned_symbols) | extract_symbols(f"{r.title} {r.summary}")
            if symbols:
                instruments = list(
                    Instrument.objects.filter(symbol__in=symbols, is_current=True),
                )
                article.instruments.set(instruments)

            # Refresh full-text index column
            NewsArticle.objects.filter(pk=article.pk).update(
                search=SearchVector("title", weight="A") + SearchVector("summary", weight="B"),
            )
            count += 1

    logger.info("articles_upserted", extra={"count": count})
    return count
