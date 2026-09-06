-- 16_add_performance_tracking_run_type.sql
-- -------------------------------------------------------------------
-- Phase C, Step 1: lets the new score-performance-tracking job log
-- itself into `ingestion_runs`, the same way daily prices / weekly
-- fundamentals / scoring already do.
--
-- `ingestion_runs.run_type` has a "check constraint" -- a rule baked
-- into the table that only allows a fixed list of values in that
-- column. Today that list is: daily_prices, weekly_fundamentals,
-- scoring. This script adds a 4th allowed value: performance_tracking.
--
-- Safe to run once. Running it a second time will error with
-- "constraint already exists" -- that's harmless, it just means it
-- already did its job.
-- -------------------------------------------------------------------

alter table ingestion_runs
  drop constraint ingestion_runs_run_type_check;

alter table ingestion_runs
  add constraint ingestion_runs_run_type_check
  check (run_type in ('daily_prices', 'weekly_fundamentals', 'scoring', 'performance_tracking'));
