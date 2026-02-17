-- PostgreSQL initialization script.
-- Creates extensions needed by the application.
-- Run once on first database creation.

CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- fast text search / LIKE queries
CREATE EXTENSION IF NOT EXISTS "btree_gin";       -- GIN indexes for multi-column queries
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- query performance monitoring

-- Timezone: ensure server uses UTC
SET timezone = 'UTC';
