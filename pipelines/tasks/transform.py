"""Transformation tasks. Refresh gold-layer materialized views."""
from __future__ import annotations

from django.db import connection

from .common import pipeline_task

# Gold marts that we keep refreshed. Refresh order matters when one matview
# selects from another — declare them topologically.
GOLD_MARTS = (
    "gold.mv_top_movers_24h",
    "gold.mv_volume_leaders_24h",
    "gold.mv_news_sentiment_daily",
)


@pipeline_task(queue="transform")
def refresh_gold_marts(self, marts: tuple[str, ...] = GOLD_MARTS, *, _run_id: str = "") -> int:
    """Refresh marts CONCURRENTLY (no read blocking). Postgres requires a
    UNIQUE index on each materialized view for CONCURRENTLY to work.
    """
    refreshed = 0
    with connection.cursor() as cursor:
        for mart in marts:
            cursor.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mart}")
            refreshed += 1
    return refreshed
