-- 98_check_us_stocks_health.sql
-------------------------------------------------------------------
-- Read-only health check for the USA stock universe (S&P 500, not
-- being expanded further -- Supabase free-tier space is staying
-- reserved for India). Changes nothing. Run each block separately
-- in Supabase's SQL Editor.

-- CHECK 1: how many active USA equities exist, and how many have
-- price history (expected: both numbers should match, or be very
-- close -- USA stocks were never trimmed, so this should be close
-- to 100% coverage).
select
  (select count(*) from assets where asset_type = 'equity' and market = 'usa' and is_active = true) as total_usa_equities,
  (select count(distinct pd.asset_id) from prices_daily pd join assets a on a.asset_id = pd.asset_id where a.market = 'usa') as usa_equities_with_price_data;

-- CHECK 2: USA price history date range and row count.
select min(pd.date) as earliest_date, max(pd.date) as latest_date, count(*) as total_rows
from prices_daily pd
join assets a on a.asset_id = pd.asset_id
where a.market = 'usa';

-- CHECK 3: how many active USA equities have fundamentals data at
-- all (expected: close to total_usa_equities -- a few gaps are
-- normal, e.g. very recently listed companies).
select
  (select count(*) from assets where asset_type = 'equity' and market = 'usa' and is_active = true) as total_usa_equities,
  (select count(distinct f.asset_id) from fundamentals f join assets a on a.asset_id = f.asset_id where a.market = 'usa') as usa_equities_with_fundamentals;

-- CHECK 4: sector coverage for USA (expected: 0, or a small number
-- -- USA stocks were sourced from the S&P 500 list itself, which
-- already came with sectors, so this was never expected to need
-- the same Yahoo Finance backfill India did).
select count(*) as usa_stocks_with_no_sector
from assets
where asset_type = 'equity' and market = 'usa' and is_active = true and sector_id is null;

-- CHECK 5: today's USA TrueScore coverage (compare to
-- total_usa_equities from Check 1/3 -- this uses whatever the most
-- recent run_date in the scores table is for USA stocks, not
-- necessarily today, since 73_score_us_stocks.py runs on its own
-- schedule).
select run_date, count(*) as usa_stocks_scored
from scores s
join assets a on a.asset_id = s.asset_id
where a.market = 'usa'
group by run_date
order by run_date desc
limit 5;
-------------------------------------------------------------------
