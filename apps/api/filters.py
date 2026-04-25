from __future__ import annotations

import django_filters as filters

from apps.instruments.models import Instrument
from apps.news.models import NewsArticle
from apps.prices.models import PriceCandle


class InstrumentFilter(filters.FilterSet):
    symbol = filters.CharFilter(field_name="symbol", lookup_expr="iexact")
    asset_class = filters.CharFilter()
    source = filters.CharFilter(field_name="source__code")
    current_only = filters.BooleanFilter(field_name="is_current")

    class Meta:
        model = Instrument
        fields = ("symbol", "asset_class", "source", "current_only")


class PriceCandleFilter(filters.FilterSet):
    symbol = filters.CharFilter(field_name="instrument__symbol", lookup_expr="iexact")
    instrument = filters.NumberFilter(field_name="instrument_id")
    resolution = filters.CharFilter()
    source = filters.CharFilter(field_name="source__code")
    ts_from = filters.IsoDateTimeFilter(field_name="ts", lookup_expr="gte")
    ts_to = filters.IsoDateTimeFilter(field_name="ts", lookup_expr="lt")

    class Meta:
        model = PriceCandle
        fields = ("symbol", "instrument", "resolution", "source", "ts_from", "ts_to")


class NewsFilter(filters.FilterSet):
    symbol = filters.CharFilter(field_name="instruments__symbol", lookup_expr="iexact")
    sentiment = filters.CharFilter()
    source = filters.CharFilter(field_name="source__code")
    published_from = filters.IsoDateTimeFilter(field_name="published_at", lookup_expr="gte")
    published_to = filters.IsoDateTimeFilter(field_name="published_at", lookup_expr="lt")
    q = filters.CharFilter(method="search_text")

    class Meta:
        model = NewsArticle
        fields = ("symbol", "sentiment", "source", "published_from", "published_to", "q")

    def search_text(self, queryset, _name, value):
        from django.contrib.postgres.search import SearchQuery
        return queryset.filter(search=SearchQuery(value))
