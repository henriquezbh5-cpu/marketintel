-- Postgres extensions used across the platform.
-- Runs once at container init via the postgres image entrypoint.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- trigram search on news titles
CREATE EXTENSION IF NOT EXISTS "btree_gin";     -- composite GIN indexes
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Gold schema for materialised marts. Kept separate so we can grant read-only
-- access to BI tools without exposing OLTP internals.
CREATE SCHEMA IF NOT EXISTS gold;
