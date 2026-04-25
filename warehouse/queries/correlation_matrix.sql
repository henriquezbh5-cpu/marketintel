-- Pairwise return correlation across the top-N symbols over a window.
-- Run via DuckDB. Postgres-scanned views are pushed-down filtered.
--
-- Parameters (substitute via DuckDB params or string-format in the caller):
--   :resolution    — '1h' / '1d'
--   :since         — TIMESTAMP lower bound (UTC)
--   :symbols       — list of symbols to include
--
-- Output: long-format (symbol_a, symbol_b, corr) — feed into a heatmap.

WITH returns AS (
    SELECT
        i.symbol,
        c.ts,
        ln(c.close::DOUBLE / lag(c.close::DOUBLE) OVER (PARTITION BY i.symbol ORDER BY c.ts)) AS log_ret
    FROM mi_fact_price_candle c
    JOIN mi_dim_instrument i ON i.id = c.instrument_id
    WHERE c.resolution = :resolution
      AND c.ts >= :since
      AND i.symbol IN :symbols
),
clean AS (
    SELECT * FROM returns WHERE log_ret IS NOT NULL
),
pairs AS (
    SELECT
        a.symbol AS symbol_a,
        b.symbol AS symbol_b,
        corr(a.log_ret, b.log_ret) AS corr
    FROM clean a
    JOIN clean b ON a.ts = b.ts AND a.symbol < b.symbol
    GROUP BY 1, 2
)
SELECT * FROM pairs
ORDER BY symbol_a, symbol_b;
