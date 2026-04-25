from __future__ import annotations

from rest_framework import serializers

from apps.instruments.models import Instrument, Source
from apps.news.models import NewsArticle
from apps.prices.models import PriceCandle, PriceSpot


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ("code", "name", "base_url", "is_active")


class InstrumentSerializer(serializers.ModelSerializer):
    source = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = Instrument
        fields = (
            "id", "source", "external_id", "symbol", "name",
            "asset_class", "quote_currency", "metadata",
            "valid_from", "valid_to", "is_current",
        )


class PriceCandleSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="instrument.symbol", read_only=True)
    source = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = PriceCandle
        fields = (
            "symbol", "source", "resolution", "ts",
            "open", "high", "low", "close", "volume",
        )


class PriceSpotSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="instrument.symbol", read_only=True)
    source = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = PriceSpot
        fields = ("symbol", "price", "change_24h_pct", "volume_24h", "ts", "source")


class NewsArticleSerializer(serializers.ModelSerializer):
    source = serializers.SlugRelatedField(slug_field="code", read_only=True)
    instruments = serializers.SlugRelatedField(
        slug_field="symbol", read_only=True, many=True,
    )

    class Meta:
        model = NewsArticle
        fields = (
            "id", "source", "external_id", "title", "url", "summary",
            "published_at", "sentiment", "sentiment_score", "instruments",
        )
