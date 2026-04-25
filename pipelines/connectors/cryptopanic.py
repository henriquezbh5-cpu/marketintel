"""CryptoPanic news adapter.

Docs: https://cryptopanic.com/developers/api/
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings

from .base import BaseConnector


@dataclass(frozen=True)
class CPArticle:
    external_id: str
    title: str
    url: str
    published_at: datetime
    source_name: str
    sentiment: str
    currencies: tuple[str, ...]
    raw: dict


_VOTE_TO_SENTIMENT = {
    "positive": "positive",
    "important": "neutral",
    "negative": "negative",
    "toxic": "negative",
    "saved": "neutral",
    "lol": "neutral",
}


class CryptoPanicConnector(BaseConnector):
    source_code = "cryptopanic"

    @classmethod
    def from_settings(cls) -> "CryptoPanicConnector":
        return cls(
            base_url=settings.CRYPTOPANIC_BASE_URL,
            rate_limit_per_min=60,
            api_key=settings.CRYPTOPANIC_API_KEY or None,
        )

    def auth_headers(self) -> Mapping[str, str]:
        # API key is sent as a query param, not header
        return {}

    def fetch_recent(self, currencies: tuple[str, ...] = (), public: bool = True) -> list[CPArticle]:
        params: dict = {"public": "true" if public else "false"}
        if self.api_key:
            params["auth_token"] = self.api_key
        if currencies:
            params["currencies"] = ",".join(currencies)

        data = self._get("/posts/", params=params)
        results = data.get("results", [])

        articles: list[CPArticle] = []
        for item in results:
            vote = _dominant_vote(item.get("votes", {}))
            articles.append(
                CPArticle(
                    external_id=str(item["id"]),
                    title=item.get("title", ""),
                    url=item.get("url") or item.get("source", {}).get("domain", ""),
                    published_at=datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")),
                    source_name=item.get("source", {}).get("title", ""),
                    sentiment=_VOTE_TO_SENTIMENT.get(vote, "neutral"),
                    currencies=tuple(c["code"] for c in item.get("currencies") or []),
                    raw=item,
                )
            )
        return articles


def _dominant_vote(votes: dict) -> str:
    if not votes:
        return "neutral"
    return max(votes.items(), key=lambda kv: kv[1])[0]
