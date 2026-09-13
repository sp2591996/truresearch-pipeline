-- 84_add_remaining_run_types.sql
-------------------------------------------------------------------
-- Fast-follow to the admin Pipeline Runs page (Session 32): several
-- jobs never logged themselves into `ingestion_runs` at all (Gold,
-- Silver, FX, Crude Oil, Benchmark Indices refresh; both Market Mood
-- jobs; both Monthly Model Retrain jobs; both weekly TrueScore
-- re-score jobs), so the admin page could only show "no run history
-- yet" for them. Each of those scripts has now been updated to log
-- itself -- this adds the new run_type values they need.
--
-- Run this in Supabase's SQL Editor (same place as the last two
-- fixes).
-------------------------------------------------------------------

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
    'model_retrain', 'us_model_retrain'
  ));
