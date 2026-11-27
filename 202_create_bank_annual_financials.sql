-- 202_create_bank_annual_financials.sql
-- -------------------------------------------------------------------
-- New table for the detailed bank financials on the redesigned bank
-- deep dives (stock, industry and sector pages): one row per bank per
-- fiscal year, the bank on its own (standalone), as filed with NSE.
--
-- Why a new table: `fundamentals` holds group (consolidated) figures
-- from Yahoo with only a few lines (revenue, profit, equity, assets),
-- and they don't line up with bank measures such as margin, deposits
-- and bad loans, which banks report standalone. HDFC Bank's equity in
-- `fundamentals` is also 45-58% too high since the merger.
--
-- Filled by 203_refresh_bank_annual_financials.py, which reads each
-- bank's official March-quarter results filing from NSE (the XBRL
-- file every listed bank must file) -- the same `nse` package already
-- used for shareholding, IPOs and quarterly results. Runs weekly via
-- .github/workflows/bank-annual-financials.yml and only downloads
-- filings it hasn't saved yet.
--
-- Amounts are in Rupees Crores, ratios in percent, like the rest of
-- the site.
--
-- HOW TO RUN THIS:
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
--   6. If a "Potential issue detected" popup appears about Row Level
--      Security, click "Run and enable RLS" -- this file sets up the
--      same public-read-only policy as every other data table.
-- -------------------------------------------------------------------

create table if not exists bank_annual_financials (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  fiscal_year_end date not null,          -- e.g. 2026-03-31 for FY26
  basis text not null default 'standalone' check (basis in ('standalone', 'consolidated')),

  -- Income statement, full year, Rupees Crores
  interest_earned_cr numeric,
  interest_expended_cr numeric,
  other_income_cr numeric,
  operating_expenses_cr numeric,          -- staff, branches, technology
  provisions_cr numeric,                  -- set aside for bad loans etc. (excl. tax)
  profit_before_tax_cr numeric,
  net_profit_cr numeric,
  eps numeric,                            -- basic, Rupees per share

  -- Balance sheet at year end, Rupees Crores
  deposits_cr numeric,
  borrowings_cr numeric,
  advances_cr numeric,                    -- loans
  investments_cr numeric,
  net_worth_cr numeric,                   -- share capital + reserves
  total_assets_cr numeric,

  -- Ratios at year end, percent
  gross_npa_pct numeric,
  net_npa_pct numeric,
  return_on_assets_pct numeric,
  cet1_pct numeric,

  source text not null default 'nse',
  source_url text,                        -- the XBRL file it was read from
  filed_at timestamptz,                   -- when the bank filed it with NSE
  fetched_at timestamptz not null default now(),
  unique (asset_id, fiscal_year_end, basis)
);

comment on table bank_annual_financials is
  'Bank annual financials (standalone), read from each bank''s official NSE results filing (XBRL). Filled weekly by 203_refresh_bank_annual_financials.py.';

alter table bank_annual_financials enable row level security;
drop policy if exists "Bank annual financials are public to read" on bank_annual_financials;
create policy "Bank annual financials are public to read" on bank_annual_financials
  for select using (true);
-- The policy alone isn't enough: new tables aren't readable by the website's
-- key until it is granted (the first run hit "permission denied").
grant select on public.bank_annual_financials to anon, authenticated;

-- Allow the new job name in the run log. Same list as
-- 166_create_quarterly_pnl_table.sql plus 'bank_annual_financials'.
-- NOT VALID: Postgres checks only new rows, so an old job name missing
-- from this list can't make the file fail (what happened with 164).
alter table ingestion_runs
  drop constraint if exists ingestion_runs_run_type_check;

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
    'quarterly_pnl',
    'bank_annual_financials'
  )) not valid;
