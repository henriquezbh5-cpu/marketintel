"""DuckDB analytical layer.

We don't push every analytical query to Postgres — partitioned scans of months
of candles to compute correlations, factor exposures or backtests will starve
the OLTP path. DuckDB embedded in a worker is faster, isolates analytical load,
and reads Postgres + Parquet via foreign-data extensions.

Usage pattern:
    with analytical_db() as conn:
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        conn.execute(f"CALL postgres_attach('{DSN}')")
        df = conn.execute("SELECT ... FROM postgres_db.public.fact_price_candle").fetchdf()
"""
from .db import analytical_db, register_views

__all__ = ("analytical_db", "register_views")
