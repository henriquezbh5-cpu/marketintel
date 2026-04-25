"""CoinGecko adapter — public free tier.

Docs: https://www.coingecko.com/api/documentation
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.conf import settings

from .base import BaseConnector


@dataclass(frozen=True)
class CGCoin:
    coin_id: str           # CoinGecko id, e.g. "bitcoin"
    symbol: str            # ticker, e.g. "btc"
    name: str
    market_cap_rank: int | None
    raw: dict


@dataclass(frozen=True)
class CGSpotPrice:
    coin_id: str
    symbol: str
    price_usd: Decimal
    change_24h_pct: Decimal | None
    volume_24h: Decimal
    ts: datetime
    raw: dict


class CoinGeckoConnector(BaseConnector):
    source_code = "coingecko"

    @classmethod
    def from_settings(cls) -> "CoinGeckoConnector":
        return cls(
            base_url=settings.COINGECKO_BASE_URL,
            rate_limit_per_min=settings.COINGECKO_RATE_LIMIT_PER_MIN,
            api_key=settings.COINGECKO_API_KEY or None,
        )

    def auth_headers(self) -> Mapping[str, str]:
        if self.api_key:
            return {"x-cg-pro-api-key": self.api_key}
        return {}

    # ── Endpoints ──────────────────────────────────────────────
    def list_coins(self) -> list[CGCoin]:
        data = self._get("/coins/list", params={"include_platform": "false"})
        return [
            CGCoin(
                coin_id=item["id"],
                symbol=item["symbol"].upper(),
                name=item["name"],
                market_cap_rank=None,
                raw=item,
            )
            for item in data
        ]

    def fetch_spot(self, coin_ids: Iterable[str]) -> list[CGSpotPrice]:
        ids = ",".join(coin_ids)
        if not ids:
            return []
        data = self._get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ids,
                "order": "market_cap_desc",
                "per_page": 250,
                "page": 1,
                "price_change_percentage": "24h",
            },
        )
        ts = datetime.now(tz=timezone.utc)
        return [
            CGSpotPrice(
                coin_id=item["id"],
                symbol=item["symbol"].upper(),
                price_usd=_decimal(item.get("current_price")),
                change_24h_pct=_decimal_optional(item.get("price_change_percentage_24h")),
                volume_24h=_decimal(item.get("total_volume", 0)),
                ts=ts,
                raw=item,
            )
            for item in data
        ]


def _decimal(value) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


def _decimal_optional(value):
    return Decimal(str(value)) if value is not None else None
