-- 99_check_us_price_coverage.sql
-------------------------------------------------------------------
-- Read-only check: how many active USA equities exist, and how
-- many actually have price history saved. Changes nothing.
--
-- Expected: both numbers should match or be very close.
-------------------------------------------------------------------

select
  (select count(*) from assets where asset_type = 'equity' and market = 'usa' and is_active = true) as total_usa_equities,
  (select count(distinct pd.asset_id) from prices_daily pd join assets a on a.asset_id = pd.asset_id where a.market = 'usa') as usa_equities_with_price_data;
