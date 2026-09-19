-- 113_check_volatility_stuck_cause.sql
-------------------------------------------------------------------
-- Diagnostic only (no schema/data changes). Follow-up to
-- 112_check_v4_volatility_stuck.sql, which found that 1,983 of 2,214
-- stocks (89%) got a "stuck at 50" (neutral/missing) Volatility Score
-- in truescore_v4.
--
-- This checks WHY: for the "stuck" stocks vs. the "not stuck" ones,
-- how many days of price data they actually have in the last 60
-- calendar days. If "stuck" stocks have far fewer recent price rows
-- (e.g. well under 30), it means they simply don't trade often enough
-- for a 30-trading-day volatility number to be computable -- a real
-- data limitation, not a bug. If both groups look similar, it points
-- to an actual bug in the calculation that needs fixing.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run) and share the 2 rows
-- it returns (group_name + avg_recent_trading_days for each).
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
),
stuck_counts as (
  select p.asset_id, count(*) as recent_count
  from prices_daily p
  join stuck s on s.asset_id = p.asset_id
  where p.date >= current_date - interval '60 days'
  group by p.asset_id
),
not_stuck_counts as (
  select p.asset_id, count(*) as recent_count
  from prices_daily p
  join not_stuck s on s.asset_id = p.asset_id
  where p.date >= current_date - interval '60 days'
  group by p.asset_id
)
select 'stuck_at_50' as group_name,
       count(*) as stock_count,
       round(avg(recent_count), 1) as avg_recent_trading_days,
       min(recent_count) as min_recent_trading_days,
       max(recent_count) as max_recent_trading_days
from stuck_counts
union all
select 'not_stuck' as group_name,
       count(*) as stock_count,
       round(avg(recent_count), 1) as avg_recent_trading_days,
       min(recent_count) as min_recent_trading_days,
       max(recent_count) as max_recent_trading_days
from not_stuck_counts;
