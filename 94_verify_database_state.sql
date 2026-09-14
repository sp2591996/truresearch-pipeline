-- 94_verify_database_state.sql
-------------------------------------------------------------------
-- Read-only sanity check after the prices_daily trim (91-93) and
-- the Stage 2 NSE universe expansion. Changes nothing. Run each
-- block separately in Supabase's SQL Editor and check the results
-- against the "expected" notes below.

-- CHECK 1: overall database size, and confirm prices_daily actually
-- shrank (expected: total well under 500 MB now; prices_daily down
-- from 640 MB to roughly 380-420 MB).
select relname as table_name, pg_size_pretty(pg_total_relation_size(relid)) as size
from pg_catalog.pg_statio_user_tables
order by pg_total_relation_size(relid) desc
limit 15;

-- CHECK 2: price history date range left in prices_daily (expected:
-- earliest date should now be about 5 years ago, not 10).
select min(date) as earliest_date, max(date) as latest_date, count(*) as total_rows
from prices_daily;

-- CHECK 3: how many active India equities exist, and how many still
-- have ANY price history at all after the trim (expected: both
-- numbers equal to 2568 -- the trim only removed OLD rows per
-- stock, it should never have removed every row for any stock).
select
  (select count(*) from assets where asset_type = 'equity' and market = 'india' and is_active = true) as total_india_equities,
  (select count(distinct pd.asset_id) from prices_daily pd join assets a on a.asset_id = pd.asset_id where a.market = 'india') as india_equities_with_price_data;

-- CHECK 4: sector coverage (expected: 2565 with a real/Unclassified
-- sector, only DHATRE/JAYKAY-RE1/TCC's 3 stay NULL -- wait, those 3
-- ARE in Unclassified per 89_, so this should actually be 0 NULL).
select count(*) as stocks_with_no_sector_at_all
from assets
where asset_type = 'equity' and market = 'india' and is_active = true and sector_id is null;

-- CHECK 5: today's TrueScore coverage (expected: 2568, from the
-- last successful run of 14_score_current_stocks.py).
select count(*) as stocks_scored_today
from scores
where run_date = current_date;
-------------------------------------------------------------------
