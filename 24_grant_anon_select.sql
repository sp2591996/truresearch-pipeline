-- 24_grant_anon_select.sql
-------------------------------------------------------------------
-- Phase C: fixes "permission denied for table X" (Postgres error
-- 42501) errors from the frontend, which is a DIFFERENT permission
-- layer from Row Level Security (23_add_public_read_policies.sql).
--
-- Postgres has two separate gates a query must pass:
--   1. Table-level GRANTs -- "can this database role touch this
--      table at all" (this script)
--   2. Row Level Security policies -- "which specific rows can it
--      see" (the previous script, 23_add_public_read_policies.sql)
-- Both were missing for the `anon` role (what the frontend connects
-- as), because Session 4 only ever granted access to `service_role`
-- (what the Python pipeline uses) -- the frontend didn't exist yet,
-- so `anon` access was never set up. This script is the other half
-- of that fix.
--
-- Grants SELECT only (read-only) -- anon still cannot insert, update,
-- or delete anything. Safe to re-run.
--
-- Run this in Supabase's SQL Editor, same place as
-- 23_add_public_read_policies.sql. Run this AFTER that script
-- (order doesn't actually matter, but that's the order they were
-- written).
-------------------------------------------------------------------

GRANT USAGE ON SCHEMA public TO anon, authenticated;

DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'assets',
        'sectors',
        'scores',
        'score_components',
        'score_backtest_results',
        'score_performance_tracking',
        'ratios_snapshot',
        'fundamentals',
        'prices_daily',
        'live_prices',
        'peers',
        'shareholding_pattern',
        'ingestion_runs'
    ]
    LOOP
        EXECUTE format('GRANT SELECT ON %I TO anon, authenticated;', tbl);
        RAISE NOTICE 'SELECT granted to anon + authenticated on table: %', tbl;
    END LOOP;
END $$;
