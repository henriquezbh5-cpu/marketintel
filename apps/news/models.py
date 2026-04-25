"""News articles and sentiment, normalised across sources."""
from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.core.models import TimestampedModel
from apps.instruments.models import Instrument, Source


class Sentiment(models.TextChoices):
    POSITIVE = "positive", "Positive"
    NEUTRAL = "neutral", "Neutral"
    NEGATIVE = "negative", "Negative"


class NewsArticle(TimestampedModel):
    """One article from one source. Idempotent on (source, external_id)."""

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="articles")
    external_id = models.CharField(max_length=128)
    title = models.TextField()
    url = models.URLField(max_length=1024)
    summary = models.TextField(blank=True)
    published_at = models.DateTimeField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    instruments = models.ManyToManyField(
        Instrument, related_name="news", blank=True,
        help_text="Instruments mentioned/tagged. Filled by the tagging task.",
    )
    sentiment = models.CharField(
        max_length=16, choices=Sentiment.choices, default=Sentiment.NEUTRAL,
    )
    sentiment_score = models.FloatField(null=True, blank=True, help_text="-1..1")
    metadata = models.JSONField(default=dict, blank=True)
    search = SearchVectorField(null=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="uniq_news_source_extid",
            ),
        ]
        indexes = [
            models.Index(fields=["-published_at"], name="ix_news_published_desc"),
            models.Index(fields=["sentiment", "-published_at"], name="ix_news_sent_pub"),
            GinIndex(fields=["search"], name="ix_news_search_gin"),
        ]
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title[:80]
