-- 121_check_top25_v5.sql
-------------------------------------------------------------------
-- Same format as 118/119 (Top 25 by overall_score, with market cap),
-- but for truescore_v5 -- the new formula with Market Cap Score
-- added. Compare this against 118 (v3) and 119 (v4) to see whether
-- adding Market Cap Score actually reduced how often tiny, obscure
-- stocks appear in the "Strong" rated list.
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
where s.formula_version = 'truescore_v5'
order by s.overall_score desc
limit 25;
