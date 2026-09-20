-- 118_check2a_top25_v3.sql
-------------------------------------------------------------------
-- Validation Check #2a: Top 25 stocks by truescore_v3 (your current
-- LIVE formula), with market cap, so it's easy to see whether the
-- list is dominated by obscure penny stocks or credible names.
-- Companion to 118b (truescore_v4's Top 25) -- run both and compare.
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
where s.formula_version = 'truescore_v3'
order by s.overall_score desc
limit 25;
