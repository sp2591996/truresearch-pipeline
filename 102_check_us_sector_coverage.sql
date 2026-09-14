-- 102_check_us_sector_coverage.sql
-------------------------------------------------------------------
-- Read-only check: how many active USA equities have no sector
-- assigned. Changes nothing.
--
-- Expected: 0 (or very close) -- the S&P 500 list USA stocks were
-- sourced from already came with sector data built in.
-------------------------------------------------------------------

select count(*) as usa_stocks_with_no_sector
from assets
where asset_type = 'equity' and market = 'usa' and is_active = true and sector_id is null;
