-- 114_check_sector_relative_defaults.sql
-------------------------------------------------------------------
-- Diagnostic only (no schema/data changes). Follow-up to
-- 112/113: checks whether the NEW Volatility Score bug (89% of
-- stocks stuck at neutral 50) is isolated to that one new component,
-- or whether the EXISTING, LIVE components (Growth Score, Relative
-- Valuation Score) -- which use the exact same "rank against other
-- stocks in the same sector" logic -- are ALSO defaulting to neutral
-- for most stocks. If they are too, the real root cause is likely
-- that most stocks are missing a sector assignment, which would be
-- a bigger, pre-existing issue affecting what's already live today
-- (truescore_v3), not something new in truescore_v4.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run) and share the table it
-- returns (6 rows: 3 components x 2 formula versions).
-------------------------------------------------------------------

select
  formula_version,
  component_name,
  count(*) as total_rows,
  count(*) filter (where component_name = 'growth' and component_value = 55) as stuck_growth_55,
  count(*) filter (where component_name in ('relative_valuation', 'volatility') and component_value = 50) as stuck_at_50,
  round(100.0 * count(*) filter (
    where (component_name = 'growth' and component_value = 55)
       or (component_name in ('relative_valuation', 'volatility') and component_value = 50)
  ) / count(*), 1) as pct_stuck
from score_components
where formula_version in ('truescore_v3', 'truescore_v4')
  and component_name in ('growth', 'relative_valuation', 'volatility')
group by formula_version, component_name
order by formula_version, component_name;

-- Separately: how many scored stocks (this run) have NO sector_id at
-- all -- the most direct possible explanation.
select
  count(*) as total_assets_with_a_score,
  count(*) filter (where a.sector_id is null) as missing_sector_id
from scores s
join assets a on a.asset_id = s.asset_id
where s.formula_version = 'truescore_v4';
