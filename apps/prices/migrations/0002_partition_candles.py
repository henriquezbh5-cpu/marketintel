"""Convert fact_price_candle from a regular table to RANGE-partitioned by ts.

Approach: idempotent rename + recreate. If we ever ship to a populated DB,
we'd add a data-migration step (`INSERT INTO new SELECT * FROM old`); for
fresh installs the table is empty so we simply replace it.

After this migration, partitions for the current month + next 3 months are
created. The Celery `ensure_future_partitions` task takes over from there.
"""
from datetime import date, timedelta

from django.db import migrations


def _month_floor(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    return _month_floor(d + timedelta(days=32))


def convert_to_partitioned(apps, schema_editor):
    today = date.today()
    sql_lines = [
        # Drop the regular table (fresh install assumption — see docstring).
        "DROP TABLE IF EXISTS fact_price_candle CASCADE;",

        # Recreate as partitioned parent. The PK must include the partition key.
        """
        CREATE TABLE fact_price_candle (
            id           BIGSERIAL,
            instrument_id BIGINT NOT NULL REFERENCES instruments_instrument(id),
            source_id    BIGINT NOT NULL REFERENCES instruments_source(id),
            resolution   VARCHAR(8) NOT NULL,
            ts           TIMESTAMPTZ NOT NULL,
            open         NUMERIC(24, 12) NOT NULL,
            high         NUMERIC(24, 12) NOT NULL,
            low          NUMERIC(24, 12) NOT NULL,
            close        NUMERIC(24, 12) NOT NULL,
            volume       NUMERIC(32, 12) NOT NULL DEFAULT 0,
            ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            run_id       VARCHAR(64) NOT NULL DEFAULT '',
            PRIMARY KEY (instrument_id, source_id, resolution, ts)
        ) PARTITION BY RANGE (ts);
        """,

        # BRIN on ts — cheap for append-only time-series.
        """
        CREATE INDEX IF NOT EXISTS ix_fact_price_candle_ts_brin
            ON fact_price_candle USING brin (ts) WITH (pages_per_range = 16);
        """,

        # Composite for last-N-by-symbol.
        """
        CREATE INDEX IF NOT EXISTS ix_price_inst_ts_desc
            ON fact_price_candle (instrument_id, ts DESC);
        """,

        # Resolution + ts for resolution-scoped scans.
        """
        CREATE INDEX IF NOT EXISTS ix_price_resolution_ts
            ON fact_price_candle (resolution, ts);
        """,
    ]

    # Pre-create partitions for the current month and next 3 months.
    cursor_month = _month_floor(today)
    for _ in range(4):
        start = cursor_month
        end = _add_month(start)
        partition_name = f"fact_price_candle_{start:%Y_%m}"
        sql_lines.append(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF fact_price_candle
                FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');
            """
        )
        cursor_month = end

    with schema_editor.connection.cursor() as cursor:
        for sql in sql_lines:
            cursor.execute(sql)


def revert_partitioning(apps, schema_editor):
    """Best-effort revert. Only safe on empty / staging DBs."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS fact_price_candle CASCADE;")
        cursor.execute(
            """
            CREATE TABLE fact_price_candle (
                id           BIGSERIAL PRIMARY KEY,
                instrument_id BIGINT NOT NULL,
                source_id    BIGINT NOT NULL,
                resolution   VARCHAR(8) NOT NULL,
                ts           TIMESTAMPTZ NOT NULL,
                open         NUMERIC(24, 12) NOT NULL,
                high         NUMERIC(24, 12) NOT NULL,
                low          NUMERIC(24, 12) NOT NULL,
                close        NUMERIC(24, 12) NOT NULL,
                volume       NUMERIC(32, 12) NOT NULL DEFAULT 0,
                ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                run_id       VARCHAR(64) NOT NULL DEFAULT ''
            );
            """
        )


class Migration(migrations.Migration):
    dependencies = [("prices", "0001_initial")]

    operations = [
        migrations.RunPython(convert_to_partitioned, revert_partitioning),
    ]
