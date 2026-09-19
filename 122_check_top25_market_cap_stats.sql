-- 122_check_top25_market_cap_stats.sql
-------------------------------------------------------------------
-- Summary stats (not just eyeballing individual names): average and
-- median market cap of the Top 25 stocks under each formula version,
-- so we can see numerically whether truescore_v5 (with Market Cap
-- Score added) skews toward bigger, more established companies than
-- truescore_v3 (live) and truescore_v4 (previous review candidate).
--
-- (Fixed from the first version: Postgres's round() needs a `numeric`
-- type, not `double precision`, which avg()/percentile_cont() return
-- -- added explicit ::numeric casts.)
--
-- Run this in Supabase's SQL Editor and share the table it returns.
-------------------------------------------------------------------

with ranked as (
  select
    s.formula_version,
    r.market_cap,
    row_number() over (partition by s.formula_version order by s.overall_score desc) as rnk
  from scores s
  join lateral (
    select market_cap from ratios_snapshot rs
    where rs.asset_id = s.asset_id
    order by rs.as_of_date desc limit 1
  ) r on true
  where s.formula_version in ('truescore_v3', 'truescore_v4', 'truescore_v5')
)
select
  formula_version,
  count(*) as stocks_in_top25,
  round((avg(market_cap) / 10000000.0)::numeric, 1) as avg_market_cap_crores,
  round((percentile_cont(0.5) within group (order by market_cap) / 10000000.0)::numeric, 1) as median_market_cap_crores,
  round((min(market_cap) / 10000000.0)::numeric, 1) as min_market_cap_crores
from ranked
where rnk <= 25
group by formula_version
order by formula_version;
