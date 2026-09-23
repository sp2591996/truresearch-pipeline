-- 133_check_sector_breakdown_post_nifty500.sql
-------------------------------------------------------------------
-- Read-only check (Avdhoot, P6, 2026-09-24). Split out from
-- 132_check_sector_counts_post_nifty500.sql because Supabase's SQL
-- Editor only shows the LAST statement's result when multiple are
-- run together -- 132's second query (stocks_with_no_sector = 0)
-- was shown, but this first one (the actual sector breakdown) never
-- displayed. This is that same first query, on its own, so it
-- actually shows. Changes nothing.
-------------------------------------------------------------------

select s.name as sector, count(*) as num_stocks
from assets a
join sectors s on s.sector_id = a.sector_id
where a.market = 'india' and a.asset_type = 'equity'
group by s.name
order by num_stocks desc;
