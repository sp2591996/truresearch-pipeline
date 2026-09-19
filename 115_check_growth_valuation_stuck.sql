-- 115_check_growth_valuation_stuck.sql
-------------------------------------------------------------------
-- Diagnostic only (no schema/data changes). Split out from
-- 114_check_sector_relative_defaults.sql's first query (Supabase's
-- SQL Editor only showed the second one). Missing sector_id has now
-- been ruled out (114 showed 0 stocks missing a sector).
--
-- This checks whether the EXISTING, LIVE components (Growth Score,
-- Relative Valuation Score) are ALSO stuck at their neutral default
-- for a large share of stocks, the same way the NEW Volatility Score
-- is -- which would point to a shared root cause -- or whether it's
-- isolated to Volatility Score alone, which would point to a bug
-- specific to that one new calculation.
--
-- Run this in Supabase's SQL Editor and share the table it returns
-- (up to 6 rows: 3 components x 2 formula versions).
-------------------------------------------------------------------

select
  formula_version,
  component_name,
  count(*) as total_rows,
  count(*) filter (
    where (component_name = 'growth' and component_value = 55)
       or (component_name in ('relative_valuation', 'volatility') and component_value = 50)
  ) as stuck_at_neutral,
  round(100.0 * count(*) filter (
    where (component_name = 'growth' and component_value = 55)
       or (component_name in ('relative_valuation', 'volatility') and component_value = 50)
  ) / count(*), 1) as pct_stuck
from score_components
where formula_version in ('truescore_v3', 'truescore_v4')
  and component_name in ('growth', 'relative_valuation', 'volatility')
group by formula_version, component_name
order by formula_version, component_name;
