"""DuckDB connection + view registration."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator

import duckdb
from django.conf import settings


@contextlib.contextmanager
def analytical_db(path: str = ":memory:") -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a DuckDB connection. Default in-memory; pass a path for persistence."""
    conn = duckdb.connect(path)
    try:
        # Defensive defaults
        conn.execute("PRAGMA threads=4")
        yield conn
    finally:
        conn.close()


def register_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Attach Postgres + register our most-used views.

    Calling this lets analytical queries reference `mi.fact_price_candle` etc
    as if they were native DuckDB tables. The Postgres scanner pushes filters
    down so partition pruning still applies.
    """
    db = settings.DATABASES["default"]
    dsn = (
        f"host={db['HOST']} port={db['PORT']} "
        f"dbname={db['NAME']} user={db['USER']} password={db['PASSWORD']}"
    )

    conn.execute("INSTALL postgres_scanner")
    conn.execute("LOAD postgres_scanner")
    conn.execute(f"CALL postgres_attach('{dsn}', source_schema='public', overwrite=true)")
    conn.execute(
        """
        CREATE OR REPLACE VIEW mi_fact_price_candle AS
        SELECT * FROM postgres_db.public.fact_price_candle;
        """
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW mi_dim_instrument AS
        SELECT * FROM postgres_db.public.instruments_instrument
        WHERE is_current = TRUE;
        """
    )
