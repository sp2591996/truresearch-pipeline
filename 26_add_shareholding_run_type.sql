-- 26_add_shareholding_run_type.sql
-- -------------------------------------------------------------------
-- Session 11, part 3: lets 25_shareholding_refresh.py log itself into
-- `ingestion_runs`, same as daily prices / weekly fundamentals /
-- scoring / performance tracking already do.
--
-- `ingestion_runs.run_type` has a check constraint allowing only:
-- daily_prices, weekly_fundamentals, scoring, performance_tracking.
-- This adds a 5th allowed value: shareholding_refresh.
--
-- Safe to run once. Running it a second time will error with
-- "constraint already exists" -- that's harmless, it just means it
-- already did its job.
-- -------------------------------------------------------------------

alter table ingestion_runs
  drop constraint ingestion_runs_run_type_check;

alter table ingestion_runs
  add constraint ingestion_runs_run_type_check
  check (run_type in ('daily_prices', 'weekly_fundamentals', 'scoring', 'performance_tracking', 'shareholding_refresh'));
