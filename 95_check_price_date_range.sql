-- 95_check_price_date_range.sql
-------------------------------------------------------------------
-- Read-only check: confirms prices_daily now holds roughly 5 years
-- of history (not 10) after the trim. Changes nothing.
--
-- Expected: earliest_date should be about 5 years ago from today.
-------------------------------------------------------------------

select min(date) as earliest_date, max(date) as latest_date, count(*) as total_rows
from prices_daily;
