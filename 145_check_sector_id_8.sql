-- Diagnostic: is sector_id 8 actually in the `sectors` table, and what
-- ids/markets do exist? Run this to see why /sectors/8 shows a 404.
select sector_id, name, market
from public.sectors
order by sector_id;
