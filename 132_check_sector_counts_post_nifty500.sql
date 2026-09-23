-- 132_check_sector_counts_post_nifty500.sql
-------------------------------------------------------------------
-- Read-only check (Avdhoot, P6, 2026-09-24, after 131_narrow_india_
-- universe_to_nifty500.sql brought India down to exactly 500 stocks):
-- "Finetune sectors -- bringing to Nifty 500 itself will bring #
-- of sectors down, then we will see still if the number is very
-- high." This just shows the current sector breakdown so we can
-- decide together whether any further consolidation is needed.
-- Changes nothing.
-------------------------------------------------------------------

select s.name as sector, count(*) as num_stocks
from assets a
join sectors s on s.sector_id = a.sector_id
where a.market = 'india' and a.asset_type = 'equity'
group by s.name
order by num_stocks desc;

-- Also worth a look: any active India stock still missing a sector.
select count(*) as stocks_with_no_sector
from assets
where asset_type = 'equity' and market = 'india' and is_active = true and sector_id is null;
