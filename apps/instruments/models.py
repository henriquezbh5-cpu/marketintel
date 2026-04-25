"""Dimensions: data sources and instruments (with SCD2 history)."""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.models import SCD2Model, TimestampedModel


class Source(TimestampedModel):
    """A third-party data provider (CoinGecko, Binance, etc.)."""

    code = models.SlugField(max_length=32, unique=True, help_text="Stable identifier used in pipelines")
    name = models.CharField(max_length=128)
    base_url = models.URLField()
    docs_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class AssetClass(models.TextChoices):
    CRYPTO = "crypto", "Cryptocurrency"
    EQUITY = "equity", "Equity"
    FX = "fx", "Foreign exchange"
    COMMODITY = "commodity", "Commodity"


class Instrument(SCD2Model):
    """Tradable instrument. SCD2 captures rebrand, ticker change, listing/delisting.

    Natural key: (source, external_id). The same logical instrument can be
    represented by multiple `Instrument` rows over time when the upstream
    record changes (e.g. a token rebrand). `is_current=True` flags the active
    version that pipelines should write to.
    """

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="instruments")
    external_id = models.CharField(
        max_length=128,
        help_text="ID in the upstream source. Stable per source; not necessarily globally unique.",
    )
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=256)
    asset_class = models.CharField(max_length=16, choices=AssetClass.choices, default=AssetClass.CRYPTO)
    quote_currency = models.CharField(max_length=16, default="USD")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            # Only one current version per natural key. Partial unique index
            # — supported natively by Postgres.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=Q(is_current=True),
                name="uniq_current_instrument_per_source",
            ),
        ]
        indexes = [
            models.Index(fields=["symbol", "asset_class"]),
            models.Index(fields=["source", "external_id", "valid_from"]),
        ]
        ordering = ["symbol"]

    def __str__(self) -> str:
        return f"{self.symbol} ({self.source.code})"

    def natural_key(self) -> tuple[str, str]:
        return (self.source.code, self.external_id)
