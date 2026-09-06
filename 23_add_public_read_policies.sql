-- 23_add_public_read_policies.sql
-------------------------------------------------------------------
-- Phase C: allow the new frontend (using the anon/publishable key) to
-- READ from the tables it needs. Row Level Security was enabled on
-- every table back in Session 4 (deliberately, so nothing was public
-- by accident) but no read policies were ever added -- meaning even
-- with correct API keys, every query from the frontend returns ZERO
-- ROWS (not an error) until policies like these exist.
--
-- This script ONLY adds SELECT (read) policies -- it does NOT allow
-- INSERT/UPDATE/DELETE from the frontend's anon key. Writes still only
-- happen from the Python pipeline, which uses the separate, more
-- powerful secret/service_role key that never reaches the browser.
--
-- Safe to re-run (DROP POLICY IF EXISTS before each CREATE).
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run), same place 01_create_tables.sql
-- was originally run.
--
-- Add more tables to this list as the frontend build reaches pages that
-- need them (e.g. peers, research_reports, ipos, learn_content, articles,
-- mutual_fund_nav_history, etc.) -- this file is meant to be extended,
-- not a one-time complete list.
-------------------------------------------------------------------

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
        'peers'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Public read access" ON %I;', tbl);
        EXECUTE format('CREATE POLICY "Public read access" ON %I FOR SELECT USING (true);', tbl);
        RAISE NOTICE 'Public read policy added for table: %', tbl;
    END LOOP;
END $$;
