-- 96_check_price_coverage.sql
-------------------------------------------------------------------
-- Read-only check: confirms the trim only removed OLD rows per
-- stock, and never accidentally removed ALL of any stock's price
-- history. Changes nothing.
--
-- Expected: both numbers equal to 2568.
-------------------------------------------------------------------

select
  (select count(*) from assets where asset_type = 'equity' and market = 'india' and is_active = true) as total_india_equities,
  (select count(distinct pd.asset_id) from prices_daily pd join assets a on a.asset_id = pd.asset_id where a.market = 'india') as india_equities_with_price_data;
