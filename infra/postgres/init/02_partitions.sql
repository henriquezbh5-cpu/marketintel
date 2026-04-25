-- Convert the candle fact to a declarative-partitioned parent.
--
-- Django creates the table; this script (run AFTER `manage.py migrate`) detaches
-- it and re-creates as partitioned. The migration `prices/0002_partition_candles.py`
-- handles the conversion idempotently in production.
--
-- For dev / first-run we create the partitioned parent + initial monthly children.
-- Add this snippet to the migration too — kept here as the canonical reference.

-- ─── If table already exists (Django created), rename and copy out ───
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'fact_price_candle'
          AND relkind = 'r'  -- ordinary, not partitioned
    ) THEN
        -- Defer to migration 0002. This script no-ops in that case.
        RAISE NOTICE 'fact_price_candle already exists as ordinary table; skipping partition conversion. Run migration 0002.';
    END IF;
END
$$;

-- ─── BRIN index on the parent (cheap for time-series append) ───
-- Created after the migration converts to partitioned.
-- CREATE INDEX IF NOT EXISTS ix_fact_price_candle_ts_brin
--     ON fact_price_candle USING brin (ts) WITH (pages_per_range = 16);

-- ─── Initial monthly partitions (current + next 3 months) ───
-- The `ensure_future_partitions` Celery task takes over after first creation.
-- Below is what the task generates; kept readable as documentation.
--
-- CREATE TABLE IF NOT EXISTS fact_price_candle_2026_04
--     PARTITION OF fact_price_candle
--     FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
