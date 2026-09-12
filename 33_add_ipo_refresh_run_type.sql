-- 33_add_ipo_refresh_run_type.sql
-- -------------------------------------------------------------------
-- Lets 33_refresh_ipos.py log itself into `ingestion_runs`, same as
-- every other pipeline script (26_add_shareholding_run_type.sql did
-- the same thing for shareholding_refresh).
--
-- `ingestion_runs.run_type` currently allows: daily_prices,
-- weekly_fundamentals, scoring, performance_tracking,
-- shareholding_refresh. This adds a 6th allowed value: ipo_refresh.
--
-- Safe to run once. Running it a second time will error with
-- "constraint already exists" -- that's harmless, it just means it
-- already did its job.
-- -------------------------------------------------------------------

alter table ingestion_runs
  drop constraint ingestion_runs_run_type_check;

alter table ingestion_runs
  add constraint ingestion_runs_run_type_check
  check (run_type in ('daily_prices', 'weekly_fundamentals', 'scoring', 'performance_tracking', 'shareholding_refresh', 'ipo_refresh'));
