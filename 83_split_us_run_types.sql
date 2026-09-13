-- 83_split_us_run_types.sql
-------------------------------------------------------------------
-- Fixes a real bug found via the new Pipeline Runs admin page: USA's
-- daily-price refresh (74_us_daily_price_refresh.py) and USA's weekly
-- fundamentals refresh (69_backfill_us_fundamentals.py) were both
-- reusing India's own run_type labels ("daily_prices" /
-- "weekly_fundamentals") to log themselves into `ingestion_runs`,
-- instead of getting their own. Harmless to the actual data pipeline
-- (each script only ever touches its own market's stocks either way)
-- but it meant the admin page's "Daily Price Refresh — India" card
-- could show a run that was actually the USA job, and vice versa --
-- exactly what Avdhoot spotted (US tickers like PLTR/PANW/PYPL
-- appearing under the "India" card).
--
-- This adds 'us_daily_prices' and 'us_weekly_fundamentals' as newly
-- allowed run_type values. It does NOT rename or touch any existing
-- rows already saved under 'daily_prices'/'weekly_fundamentals' --
-- old history stays exactly as it is; only runs from now on (after
-- 74_us_daily_price_refresh.py / 69_backfill_us_fundamentals.py are
-- updated too) will log under the new, correctly-separated labels.
--
-- Run this in Supabase's SQL Editor (same place as the last fix).
-------------------------------------------------------------------

alter table ingestion_runs
  drop constraint ingestion_runs_run_type_check;

alter table ingestion_runs
  add constraint ingestion_runs_run_type_check
  check (run_type in (
    'daily_prices', 'weekly_fundamentals', 'scoring', 'performance_tracking',
    'shareholding_refresh', 'ipo_refresh',
    'us_daily_prices', 'us_weekly_fundamentals'
  ));
