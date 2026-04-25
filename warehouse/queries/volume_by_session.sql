-- Average traded volume per market session (Asia / Europe / US) for each symbol
-- over the last 30 days. Useful for liquidity-aware execution.

WITH sessions AS (
    SELECT
        i.symbol,
        c.ts,
        c.volume,
        CASE
            WHEN extract(hour FROM c.ts AT TIME ZONE 'UTC') BETWEEN 0 AND 7  THEN 'asia'
            WHEN extract(hour FROM c.ts AT TIME ZONE 'UTC') BETWEEN 8 AND 15 THEN 'europe'
            ELSE 'us'
        END AS session
    FROM mi_fact_price_candle c
    JOIN mi_dim_instrument i ON i.id = c.instrument_id
    WHERE c.resolution = '1h'
      AND c.ts >= now() - INTERVAL '30 days'
)
SELECT
    symbol,
    session,
    avg(volume)         AS avg_volume,
    median(volume)      AS median_volume,
    quantile_cont(volume, 0.95) AS p95_volume
FROM sessions
GROUP BY symbol, session
ORDER BY symbol, session;
