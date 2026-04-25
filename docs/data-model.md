# Data Model

> Canonical reference for tables, keys and indexes. Migrations are the source
> of truth; this document explains *why*.

---

## Schemas

| Schema | Purpose |
|---|---|
| `public` | Django default — silver layer (instruments, prices, news) |
| `gold` | Materialised marts for hot dashboards |
| `auth` | Django auth + API keys |

## Dimensions

### `instruments_source`
Catalogue of upstream data providers.

| Column | Type | Notes |
|---|---|---|
| `id` | bigint PK | |
| `code` | slug, unique | Stable identifier used in pipelines |
| `name` | varchar | |
| `base_url` | URL | |
| `is_active` | bool | Toggle without deleting |

### `instruments_instrument` (SCD Type 2)
One row per (source, external_id, version). The active version has
`is_current = TRUE`. When a tracked attribute changes upstream, the current
row is closed (`valid_to` set, `is_current=FALSE`) and a new row is inserted.

| Column | Type | Notes |
|---|---|---|
| `id` | bigint PK | |
| `source_id` | FK → source | |
| `external_id` | varchar(128) | Upstream id |
| `symbol` | varchar(32) | Indexed |
| `name` | varchar(256) | |
| `asset_class` | enum | crypto/equity/fx/commodity |
| `quote_currency` | varchar(16) | |
| `metadata` | jsonb | Non-tracked attributes |
| `valid_from` | timestamptz | |
| `valid_to` | timestamptz nullable | |
| `is_current` | bool | |

**Constraints**:
- Partial UNIQUE `(source_id, external_id) WHERE is_current = TRUE`. Partial
  indexes are a Postgres feature; Django supports them via
  `UniqueConstraint(condition=Q(...))`.

**Indexes**:
- `(symbol, asset_class)` — discovery queries
- `(source_id, external_id, valid_from)` — historical replay

## Facts

### `fact_price_candle` (partitioned)
OHLCV bars. Partitioned by RANGE on `ts`, monthly. See ADR 0005.

| Column | Type | Notes |
|---|---|---|
| `id` | bigint | NOT a PK (the partition key must be in the PK) |
| `instrument_id` | FK | |
| `source_id` | FK | |
| `resolution` | varchar(8) | 1m/5m/15m/1h/4h/1d |
| `ts` | timestamptz | Partition key |
| `open/high/low/close` | decimal(24,12) | Wide enough for sat-precision |
| `volume` | decimal(32,12) | |
| `ingested_at` | timestamptz | |
| `run_id` | varchar(64) | Lineage to Dagster run |

**Primary key**: `(instrument_id, source_id, resolution, ts)` — required to
include the partition key (`ts`).

**Indexes** (per partition):
- BRIN on `ts` — append-only friendly
- B-tree on `(instrument_id, ts DESC)` — last-N queries

### `fact_price_spot`
Tiny denormalised table — one row per current instrument with latest spot.
Refreshed by the spot ingestion task.

| Column | Type | Notes |
|---|---|---|
| `instrument_id` | PK FK | |
| `price` | decimal(24,12) | |
| `change_24h_pct` | decimal(10,4) nullable | |
| `volume_24h` | decimal(32,12) | |
| `ts` | timestamptz | |
| `source_id` | FK | |

### `news_newsarticle`
Idempotent on (source_id, external_id).

| Column | Type | Notes |
|---|---|---|
| `id` | bigint PK | |
| `source_id` | FK | |
| `external_id` | varchar(128) | |
| `title` | text | |
| `url` | varchar(1024) | |
| `summary` | text | |
| `published_at` | timestamptz | Indexed DESC |
| `sentiment` | enum | positive/neutral/negative |
| `sentiment_score` | float | -1..1 |
| `metadata` | jsonb | |
| `search` | tsvector | Full-text index column, GIN |

M2M `news_newsarticle_instruments` for tagged symbols.

## Gold marts (matviews)

| Matview | Refresh cadence | Purpose |
|---|---|---|
| `gold.mv_top_movers_24h` | 5 min | Sorted by `change_24h_pct` |
| `gold.mv_volume_leaders_24h` | 5 min | Sorted by `volume_24h` |
| `gold.mv_news_sentiment_daily` | 1 hour | Daily sentiment per symbol |

All matviews have UNIQUE indexes for `REFRESH ... CONCURRENTLY`.

## Auth

| Table | Purpose |
|---|---|
| `auth_user` | Django users — service accounts, dev users |
| `api_apikey` | One row per issued key. `key_hash` is sha256 of the raw key. |

---

## Conventions

- All timestamps are UTC, stored as `timestamptz`.
- Decimals favour precision (≤ 24 digits). We don't use floats for money/price.
- IDs are `bigint`, not UUID — partitioned facts benefit from monotonic ids
  (better BRIN behaviour).
- JSONB for non-tracked metadata. Promote to columns when a field becomes hot.
