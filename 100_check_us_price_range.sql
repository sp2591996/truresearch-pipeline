-- 100_check_us_price_range.sql
-------------------------------------------------------------------
-- Read-only check: earliest/latest dates and row count in USA price
-- history. Changes nothing. Informational only -- USA data was
-- never trimmed, so no strict "expected" value here.
-------------------------------------------------------------------

select min(pd.date) as earliest_date, max(pd.date) as latest_date, count(*) as total_rows
from prices_daily pd
join assets a on a.asset_id = pd.asset_id
where a.market = 'usa';
