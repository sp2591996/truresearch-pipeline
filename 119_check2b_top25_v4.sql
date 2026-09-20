-- 119_check2b_top25_v4.sql
-------------------------------------------------------------------
-- Validation Check #2b: Top 25 stocks by truescore_v4 (the new,
-- in-review formula), with market cap, for the same comparison as
-- 118a (truescore_v3's Top 25).
--
-- Run this in Supabase's SQL Editor and share the table it returns.
-------------------------------------------------------------------

select
  a.ticker,
  a.name,
  r.market_cap,
  s.overall_score,
  s.truescore_rating
from scores s
join assets a on a.asset_id = s.asset_id
left join lateral (
  select market_cap from ratios_snapshot rs
  where rs.asset_id = s.asset_id
  order by rs.as_of_date desc limit 1
) r on true
where s.formula_version = 'truescore_v4'
order by s.overall_score desc
limit 25;
