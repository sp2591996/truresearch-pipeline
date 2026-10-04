-- 164_create_bank_quarterly_pnl.sql
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
-- Source: nse.results_comparison(symbol) -- "resCmpData" list,
-- typically the last ~5 quarters. Amounts arrive in Rupees Lakhs from
-- NSE; this script converts to Crores (divide by 100) to match the
-- units already used everywhere else on the site.
--
-- HOW TO RUN THIS:
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
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
  'Quarterly P&L summary (Total Income, Net Profit, EPS) for bank stocks, from NSE's official results_comparison feed. Last ~5 quarters per stock -- NSE does not expose older quarterly history via this endpoint.';

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
    'bank_quarterly_pnl'
  ));
