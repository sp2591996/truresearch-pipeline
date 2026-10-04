-- 166_create_quarterly_pnl_table.sql
-- -------------------------------------------------------------------
-- Generalizes 164_create_bank_quarterly_pnl.sql's idea to ALL Nifty
-- 500 stocks, not just the 26 bank stocks. Avdhoot's ask (2026-10-05):
-- "Lets extract for all the 500 stocks this, not just 26 banks."
--
-- This is a NEW table (`quarterly_pnl`), not a rename/edit of the
-- existing `bank_quarterly_pnl` table -- that table already has real,
-- working data for the 26 banks (fetched successfully via
-- 165_fetch_bank_quarterly_pnl.py) and is left untouched. Going
-- forward, this new, asset-agnostic table is the one that should be
-- used for any stock (banks included -- it's fine if a bank's data
-- exists in both tables).
--
-- Same data source and same honest limits as 164/165: NSE's own
-- official `results_comparison` feed (free, legal, no scraping) --
-- last ~5 quarters of summary P&L (Total Income, Net Profit, EPS)
-- only. Not a full line-item statement, not 10 years of quarterly
-- history -- no free/legal source for that exists for Indian stocks
-- (see PROJECT_STATE.md Session 41 for the full investigation).
--
-- HOW TO RUN THIS:
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
--   6. If a "Potential issue detected" popup appears about Row Level
--      Security, click "Run and enable RLS" -- this file already sets
--      up the correct public-read-only policy itself.
-- -------------------------------------------------------------------

create table if not exists quarterly_pnl (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  period_end_date date not null,
  relating_to text,              -- e.g. "Third Quarter", as NSE labels it
  total_income_cr numeric,       -- Rupees Crores
  net_profit_cr numeric,         -- Rupees Crores
  eps numeric,
  is_audited boolean,
  is_consolidated boolean,
  source text not null default 'nse',
  fetched_at timestamptz not null default now(),
  unique (asset_id, period_end_date, is_consolidated)
);

comment on table quarterly_pnl is
  'Quarterly P&L summary (Total Income, Net Profit, EPS) for all Nifty 500 stocks, from NSE official results_comparison feed. Last ~5 quarters per stock -- NSE does not expose older quarterly history via this endpoint. Generalizes bank_quarterly_pnl (164/165) to every stock, not just banks.';

-- Same public-read-only pattern as every other data table in this
-- project: anyone can READ (powers the public stock pages), only the
-- backend script (service key, bypasses RLS) can write.
alter table quarterly_pnl enable row level security;
drop policy if exists "Quarterly P&L is public to read" on quarterly_pnl;
create policy "Quarterly P&L is public to read" on quarterly_pnl
  for select using (true);

-- Index for the frontend's per-stock lookup pattern (fetch all
-- quarters for one asset_id, newest first).
create index if not exists idx_quarterly_pnl_asset_period
  on quarterly_pnl (asset_id, period_end_date desc);

-- Re-expand the ingestion_runs allow-list to include this new job
-- type. Carries forward every value already confirmed live on
-- Avdhoot's real database (including 'virtual_portfolio_snapshot',
-- found via the 2026-10-05 diagnostic query that unblocked file 164).
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
    'universe_sync_india', 'universe_sync_usa',
    'bank_quarterly_pnl',
    'virtual_portfolio_snapshot',
    'quarterly_pnl'
  ));
