-- 116_check_null_close_prices.sql
-------------------------------------------------------------------
-- Diagnostic only (no schema/data changes). Growth Score and
-- Relative Valuation Score are fine (~1-15% neutral, normal/expected
-- for a stock or two missing data). Only Volatility Score is broken
-- (89.6% stuck). Missing sector_id was ruled out (115: 0 missing).
-- Row COUNT in the last 60 days looked normal for both groups (113),
-- but that only checked that a row EXISTS for each date -- not
-- whether its `close` price is actually filled in. This checks that:
-- how many of the last 60 days' price rows have a NULL close price,
-- for "stuck" (broken volatility) stocks vs. "not stuck" ones. If
-- "stuck" stocks have far more NULL closes, that's the real cause --
-- a rolling 30-day volatility calculation can't produce a number if
-- any of those 30 days has a missing close price.
--
-- Run this in Supabase's SQL Editor and share the table it returns.
-------------------------------------------------------------------

with stuck as (
  select sc.asset_id
  from score_components sc
  where sc.formula_version = 'truescore_v4'
    and sc.component_name = 'volatility'
    and sc.component_value = 50
),
not_stuck as (
  select sc.asset_id
  from score_components sc
  where sc.formula_version = 'truescore_v4'
    and sc.component_name = 'volatility'
    and sc.component_value <> 50
)
select 'stuck_at_50' as group_name,
       count(*) as recent_price_rows,
       count(*) filter (where p.close is null) as null_close_rows,
       round(100.0 * count(*) filter (where p.close is null) / count(*), 1) as pct_null_close
from prices_daily p
join stuck s on s.asset_id = p.asset_id
where p.date >= current_date - interval '60 days'
union all
select 'not_stuck' as group_name,
       count(*) as recent_price_rows,
       count(*) filter (where p.close is null) as null_close_rows,
       round(100.0 * count(*) filter (where p.close is null) / count(*), 1) as pct_null_close
from prices_daily p
join not_stuck s on s.asset_id = p.asset_id
where p.date >= current_date - interval '60 days';
