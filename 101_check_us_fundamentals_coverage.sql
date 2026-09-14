-- 101_check_us_fundamentals_coverage.sql
-------------------------------------------------------------------
-- Read-only check: how many active USA equities have fundamentals
-- (financial statement) data saved. Changes nothing.
--
-- Expected: close to total_usa_equities -- small gaps are normal
-- for very recently listed companies.
-------------------------------------------------------------------

select
  (select count(*) from assets where asset_type = 'equity' and market = 'usa' and is_active = true) as total_usa_equities,
  (select count(distinct f.asset_id) from fundamentals f join assets a on a.asset_id = f.asset_id where a.market = 'usa') as usa_equities_with_fundamentals;
