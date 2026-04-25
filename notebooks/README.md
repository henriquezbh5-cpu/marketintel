# Notebooks

Analytical notebooks. Run inside the dev container so they pick up the same
environment variables and packages as the rest of the platform.

```bash
docker compose exec web python -m ipykernel install --user --name marketintel
docker compose exec -w /app web jupyter lab --ip 0.0.0.0 --port 8888 --no-browser
```

## Suggested structure

| Notebook | Goal |
|---|---|
| `01_correlation_analysis.ipynb` | Pairwise return correlation across top-N symbols. Uses DuckDB + the `correlation_matrix.sql` query. |
| `02_volume_by_session.ipynb` | Liquidity heatmap by Asia / Europe / US session. |
| `03_news_sentiment_alpha.ipynb` | Does aggregate news sentiment lead BTC price changes? |
| `04_anomaly_detection.ipynb` | Flag candles >5σ vs rolling distribution. |

Each notebook should:
1. Import `warehouse.analytical_db` + `register_views` to attach Postgres.
2. Read SQL from `warehouse/queries/` (don't inline SQL in the notebook —
   queries live in version control as files).
3. Save plots to `notebooks/output/` if they're meant to be shared.

Notebooks themselves are not committed beyond this README and a couple of
canonical examples — the queries are the durable artefact.
