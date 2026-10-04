-- 164_create_bank_quarterly_pnl.sql
-- -------------------------------------------------------------------
-- CORRECTED 2026-10-05: first run of this file failed with
--   ERROR: 23514: check constraint "ingestion_runs_run_type_check"
--   of relation "ingestion_runs" is violated by some row
-- Diagnostic query confirmed one existing run_type value in the table
-- wasn't on this file's allow-list: 'virtual_portfolio_snapshot' (the
-- My Portfolio snapshot job, added back in 109_snapshot_virtual_portfolios.py
-- / 108_add_virtual_portfolio_snapshot_run_type.sql -- just never carried
-- forward into this file's own copy of the allow-list). Added below.
-- This is a same-file correction (the original attempt never
-- succeeded), not a new numbered file -- see Updated Project
-- Tracker.md Section 11 for the naming rule this follows.
-- -------------------------------------------------------------------
-- New table for the "Financial Statements" Deepdive tab (Avdhoot's
-- ask: quarterly + annual P&L/Balance Sheet/Cash Flow for the 38 bank
-- stocks). After checking what's realistically available (see
-- PROJECT_STATE.md for the full story), this table holds QUARTERLY
-- P&L summary figures from NSE's own official corporate-filings feed
-- (the same source already used for shareholding_pattern/ipos --
-- 100% legal, no scraping). It does NOT attempt a full line-by-line
-- Balance Sheet or Cash Flow at quarterly granularity -- no free,
-- legal, reliable source for that exists for Indian stocks. The
-- Balance Sheet / Cash Flow views in the new tab instead reuse the
-- existing `fundamentals` table (annual only, already populated).
--
-- Source: nse.results_comparison(symbol) -- the "resCmpData" list,
-- typically the last 5 quarters. Amounts arrive in Rupees Lakhs from
-- NSE; this script converts to Crores (divide by 100) to match the
-- units already used everywhere else on the site.
--
-- HOW TO RUN THIS:
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
--   6. If a "Potential issue detected" popup appears about Row Level
--      Security, click "Run and enable RLS" -- this file already sets
--      up the correct public-read-only policy itself, matching every
--      other data table on the site, so that popup's warning is
--      already handled below.
-- -------------------------------------------------------------------

create table if not exists bank_quarterly_pnl (
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

comment on table bank_quarterly_pnl is
  'Quarterly P&L summary (Total Income, Net Profit, EPS) for bank stocks, from NSE official results_comparison feed. Last ~5 quarters per stock -- NSE does not expose older quarterly history via this endpoint.';

-- Same public-read-only pattern as every other data table in this
-- project (e.g. stock_deepdive, sector_overviews): anyone can READ
-- this table (it's what powers the site's public stock pages), but
-- only the backend script -- using the service key, which bypasses
-- RLS entirely -- can write to it. No anon/authenticated insert,
-- update or delete policy is created on purpose.
alter table bank_quarterly_pnl enable row level security;
drop policy if exists "Bank quarterly P&L is public to read" on bank_quarterly_pnl;
create policy "Bank quarterly P&L is public to read" on bank_quarterly_pnl
  for select using (true);

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
    'virtual_portfolio_snapshot'
  ));
