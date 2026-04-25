-- Gold marts. Materialised views refreshed by Celery `refresh_gold_marts`.
-- Each requires a UNIQUE index for `REFRESH MATERIALIZED VIEW CONCURRENTLY`.

-- ─── Top movers in the last 24h ──────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mv_top_movers_24h AS
SELECT
    s.instrument_id,
    i.symbol,
    s.price,
    s.change_24h_pct,
    s.volume_24h,
    s.ts
FROM fact_price_spot s
JOIN instruments_instrument i ON i.id = s.instrument_id
WHERE i.is_current = TRUE
  AND s.change_24h_pct IS NOT NULL
ORDER BY s.change_24h_pct DESC NULLS LAST;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_top_movers_24h
    ON gold.mv_top_movers_24h (instrument_id);

-- ─── Volume leaders ──────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mv_volume_leaders_24h AS
SELECT
    s.instrument_id,
    i.symbol,
    s.volume_24h,
    s.price,
    s.ts
FROM fact_price_spot s
JOIN instruments_instrument i ON i.id = s.instrument_id
WHERE i.is_current = TRUE
ORDER BY s.volume_24h DESC;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_volume_leaders_24h
    ON gold.mv_volume_leaders_24h (instrument_id);

-- ─── Daily news sentiment per symbol ─────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mv_news_sentiment_daily AS
SELECT
    i.symbol,
    date_trunc('day', n.published_at)::date AS day,
    count(*)                                AS article_count,
    avg(n.sentiment_score)                  AS avg_score,
    sum(CASE WHEN n.sentiment = 'positive' THEN 1 ELSE 0 END) AS pos_count,
    sum(CASE WHEN n.sentiment = 'negative' THEN 1 ELSE 0 END) AS neg_count
FROM news_newsarticle n
JOIN news_newsarticle_instruments ni ON ni.newsarticle_id = n.id
JOIN instruments_instrument i ON i.id = ni.instrument_id AND i.is_current = TRUE
WHERE n.published_at >= now() - INTERVAL '90 days'
GROUP BY i.symbol, date_trunc('day', n.published_at);

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_news_sentiment_daily
    ON gold.mv_news_sentiment_daily (symbol, day);
