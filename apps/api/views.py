"""DRF viewsets exposing the data platform."""
from __future__ import annotations

from rest_framework import mixins, viewsets

from apps.instruments.models import Instrument, Source
from apps.news.models import NewsArticle
from apps.prices.models import PriceCandle, PriceSpot

from .filters import InstrumentFilter, NewsFilter, PriceCandleFilter
from .pagination import NewsCursorPagination, TimeseriesCursorPagination
from .serializers import (
    InstrumentSerializer,
    NewsArticleSerializer,
    PriceCandleSerializer,
    PriceSpotSerializer,
    SourceSerializer,
)


class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Source.objects.filter(is_active=True)
    serializer_class = SourceSerializer
    throttle_scope = "catalog"
    pagination_class = None  # Small enumerable list


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Instrument.objects.select_related("source").filter(is_current=True)
    serializer_class = InstrumentSerializer
    filterset_class = InstrumentFilter
    throttle_scope = "catalog"
    lookup_field = "symbol"
    lookup_value_regex = r"[A-Za-z0-9_-]+"


class PriceCandleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List candles. Always require a symbol or instrument id + a time range.

    Without those filters the endpoint refuses — protects against accidental
    full-table scans across partitions.
    """

    queryset = PriceCandle.objects.select_related("instrument", "source")
    serializer_class = PriceCandleSerializer
    filterset_class = PriceCandleFilter
    pagination_class = TimeseriesCursorPagination
    throttle_scope = "prices"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if not (params.get("symbol") or params.get("instrument")):
            return qs.none()
        return qs


class PriceSpotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PriceSpot.objects.select_related("instrument", "source")
    serializer_class = PriceSpotSerializer
    throttle_scope = "prices"
    lookup_field = "instrument__symbol"
    lookup_url_kwarg = "symbol"


class NewsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = NewsArticle.objects.select_related("source").prefetch_related("instruments")
    serializer_class = NewsArticleSerializer
    filterset_class = NewsFilter
    pagination_class = NewsCursorPagination
    throttle_scope = "news"
