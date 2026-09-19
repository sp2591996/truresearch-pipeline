-- 112_check_v4_volatility_stuck.sql
-------------------------------------------------------------------
-- Diagnostic only (no schema/data changes). Checks whether the new
-- Volatility Score component of truescore_v4 is stuck at the neutral
-- default (50) for most/all stocks, which would indicate a bug in
-- 14_score_current_stocks.py's volatility calculation rather than
-- genuinely-missing data for a few thin-trading stocks.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run) and share the two
-- numbers it returns.
-------------------------------------------------------------------

select
  count(*) as total_volatility_rows,
  count(*) filter (where component_value = 50) as stuck_at_fifty
from score_components
where formula_version = 'truescore_v4' and component_name = 'volatility';
