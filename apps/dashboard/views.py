"""Dashboard views.

Server-side rendered pages backed by direct ORM queries (no internal HTTP
roundtrip to the API). Read-only — the dashboard does not mutate state.
JSON endpoints are provided for client-side polling so panels refresh
without full page reloads.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.db import connection
from django.db.models import Count, Max
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.core.models import DeadLetterTask
from apps.instruments.models import Instrument, Source
from apps.news.models import NewsArticle
from apps.prices.models import PriceCandle, PriceSpot, Resolution


# ────────────────────────────────────────────────────────────────────
# Pages
# ────────────────────────────────────────────────────────────────────

def home(request: HttpRequest):
    """Single-page overview with KPI cards, top movers, sparklines, news."""
    return render(request, "dashboard/home.html", {
        "page": "home",
        "kpis": _kpis(),
    })


def markets(request: HttpRequest):
    """Live instruments table."""
    return render(request, "dashboard/markets.html", {"page": "markets"})


def symbol_detail(request: HttpRequest, symbol: str):
    inst = (
        Instrument.objects
        .select_related("source")
        .filter(symbol__iexact=symbol, is_current=True)
        .first()
    )
    return render(request, "dashboard/symbol.html", {
        "page": "markets",
        "symbol": symbol.upper(),
        "instrument": inst,
    })


def news(request: HttpRequest):
    return render(request, "dashboard/news.html", {"page": "news"})


def system(request: HttpRequest):
    return render(request, "dashboard/system.html", {"page": "system"})


def coverage(request: HttpRequest):
    return render(request, "dashboard/coverage.html", {"page": "coverage"})


# ────────────────────────────────────────────────────────────────────
# JSON endpoints for client-side polling
# ────────────────────────────────────────────────────────────────────

@require_GET
def api_kpis(_request):
    return JsonResponse(_kpis())


@require_GET
def api_top_movers(_request):
    qs = (
        PriceSpot.objects
        .select_related("instrument", "source")
        .filter(change_24h_pct__isnull=False)
    )
    rows = [
        {
            "symbol": s.instrument.symbol,
            "name": s.instrument.name,
            "price": _dec(s.price),
            "change_24h_pct": _dec(s.change_24h_pct),
            "volume_24h": _dec(s.volume_24h),
            "ts": s.ts.isoformat(),
        }
        for s in qs
    ]
    rows.sort(key=lambda r: r["change_24h_pct"], reverse=True)
    gainers = rows[:10]
    losers = sorted(rows, key=lambda r: r["change_24h_pct"])[:10]
    return JsonResponse({"gainers": gainers, "losers": losers})


@require_GET
def api_spots(_request):
    qs = (
        PriceSpot.objects
        .select_related("instrument", "source")
        .order_by("instrument__symbol")
    )
    return JsonResponse({
        "results": [
            {
                "symbol": s.instrument.symbol,
                "name": s.instrument.name,
                "asset_class": s.instrument.asset_class,
                "price": _dec(s.price),
                "change_24h_pct": _dec(s.change_24h_pct),
                "volume_24h": _dec(s.volume_24h),
                "ts": s.ts.isoformat(),
                "source": s.source.code,
            }
            for s in qs
        ]
    })


@require_GET
def api_candles(request, symbol: str):
    """OHLCV candles for charting. ?resolution=1m&hours=24"""
    resolution = request.GET.get("resolution", "1m")
    if resolution not in dict(Resolution.choices):
        resolution = "1m"
    try:
        hours = max(1, min(int(request.GET.get("hours", "24")), 24 * 30))
    except ValueError:
        hours = 24

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    qs = (
        PriceCandle.objects
        .filter(
            instrument__symbol__iexact=symbol,
            resolution=resolution,
            ts__gte=cutoff,
        )
        .order_by("ts")
        .values("ts", "open", "high", "low", "close", "volume")
    )
    return JsonResponse({
        "symbol": symbol.upper(),
        "resolution": resolution,
        "candles": [
            {
                "ts": c["ts"].isoformat(),
                "o": _dec(c["open"]),
                "h": _dec(c["high"]),
                "l": _dec(c["low"]),
                "c": _dec(c["close"]),
                "v": _dec(c["volume"]),
            }
            for c in qs
        ],
    })


@require_GET
def api_sparkline(request, symbol: str):
    """Compact closes for tiny inline charts."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    closes = list(
        PriceCandle.objects
        .filter(
            instrument__symbol__iexact=symbol,
            resolution="5m",
            ts__gte=cutoff,
        )
        .order_by("ts")
        .values_list("close", flat=True)
    )
    return JsonResponse({
        "symbol": symbol.upper(),
        "values": [_dec(c) for c in closes],
    })


@require_GET
def api_news(request):
    """Recent news with optional filters."""
    qs = (
        NewsArticle.objects
        .select_related("source")
        .prefetch_related("instruments")
        .order_by("-published_at")
    )
    sentiment = request.GET.get("sentiment")
    if sentiment:
        qs = qs.filter(sentiment=sentiment)
    symbol = request.GET.get("symbol")
    if symbol:
        qs = qs.filter(instruments__symbol__iexact=symbol).distinct()

    qs = qs[:50]
    return JsonResponse({
        "results": [
            {
                "id": a.id,
                "title": a.title,
                "url": a.url,
                "summary": a.summary[:300],
                "source": a.source.code,
                "published_at": a.published_at.isoformat(),
                "sentiment": a.sentiment,
                "sentiment_score": a.sentiment_score,
                "symbols": [i.symbol for i in a.instruments.all()],
            }
            for a in qs
        ]
    })


@require_GET
def api_system(_request):
    """Pipeline health snapshot."""
    last_spot = PriceSpot.objects.aggregate(latest=Max("ts"))["latest"]
    last_candle = PriceCandle.objects.aggregate(latest=Max("ts"))["latest"]
    last_news = NewsArticle.objects.aggregate(latest=Max("published_at"))["latest"]
    dlq_open = DeadLetterTask.objects.filter(resolved_at__isnull=True).count()
    dlq_total = DeadLetterTask.objects.count()

    partitions = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.relname,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
                   (SELECT count(*) FROM fact_price_candle WHERE tableoid = c.oid) AS rows
            FROM pg_class c
            JOIN pg_inherits i ON i.inhrelid = c.oid
            JOIN pg_class p   ON p.oid     = i.inhparent
            WHERE p.relname = 'fact_price_candle'
            ORDER BY c.relname;
        """)
        partitions = [
            {"name": r[0], "size": r[1], "rows": r[2]}
            for r in cursor.fetchall()
        ]

    sources_status = []
    for s in Source.objects.filter(is_active=True).order_by("code"):
        last_seen = (
            PriceSpot.objects.filter(source=s).aggregate(t=Max("ts"))["t"]
            or PriceCandle.objects.filter(source=s).aggregate(t=Max("ts"))["t"]
            or NewsArticle.objects.filter(source=s).aggregate(t=Max("published_at"))["t"]
        )
        sources_status.append({
            "code": s.code,
            "name": s.name,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "stale": _is_stale(last_seen),
        })

    counts_by_resolution = (
        PriceCandle.objects
        .values("resolution")
        .annotate(n=Count("id"))
        .order_by("resolution")
    )

    return JsonResponse({
        "now": datetime.now(tz=timezone.utc).isoformat(),
        "freshness": {
            "spot": last_spot.isoformat() if last_spot else None,
            "candle": last_candle.isoformat() if last_candle else None,
            "news": last_news.isoformat() if last_news else None,
        },
        "dlq": {"open": dlq_open, "total": dlq_total},
        "partitions": partitions,
        "sources": sources_status,
        "candle_counts": list(counts_by_resolution),
    })


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _kpis() -> dict:
    return {
        "instruments": Instrument.objects.filter(is_current=True).count(),
        "spots": PriceSpot.objects.count(),
        "candles": PriceCandle.objects.count(),
        "news": NewsArticle.objects.count(),
        "sources": Source.objects.filter(is_active=True).count(),
        "dlq_open": DeadLetterTask.objects.filter(resolved_at__isnull=True).count(),
    }


def _dec(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_stale(ts) -> bool:
    if ts is None:
        return True
    return (datetime.now(tz=timezone.utc) - ts) > timedelta(minutes=10)
