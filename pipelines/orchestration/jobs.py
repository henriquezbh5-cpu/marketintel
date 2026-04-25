"""Dagster jobs — selectable subsets of the asset graph."""
from __future__ import annotations

from dagster import AssetSelection, define_asset_job

ingest_prices_job = define_asset_job(
    name="ingest_prices_job",
    selection=AssetSelection.assets("bronze_coingecko_spot", "silver_price_spot"),
    description="Pull and normalise spot prices end-to-end.",
)

full_refresh_job = define_asset_job(
    name="full_refresh_job",
    selection=AssetSelection.all(),
    description="Refresh every asset. Use sparingly — backfills only.",
)
