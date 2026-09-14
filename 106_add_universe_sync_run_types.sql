-- 106_add_universe_sync_run_types.sql
-- -------------------------------------------------------------------
-- Adds the two new run_type values the weekly universe-sync scripts
-- need (104_weekly_universe_sync_india.py / 105_weekly_universe_sync_usa.py)
-- -- same pattern as every earlier run_type addition in this project
-- (16_/26_/33_/84_).
--
-- HOW TO RUN THIS:
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
-- -------------------------------------------------------------------

alter table ingestion_runs
  drop constraint ingestion_runs_run_type_check;

alter table ingestion_runs
  add constraint ingestion_runs_run_type_check
  check (run_type in (
    'daily_prices', 'weekly_fundamentals', 'scoring', 'performance_tracking',
    'shareholding_refresh', 'ipo_refresh',
    'us_daily_prices', 'us_weekly_fundamentals', 'us_scoring',
    'gold_refresh', 'silver_refresh', 'fx_refresh', 'crude_refresh', 'benchmark_indices',
    'market_mood', 'us_market_mood',
    'model_retrain', 'us_model_retrain',
    'universe_sync_india', 'universe_sync_usa'
  ));
