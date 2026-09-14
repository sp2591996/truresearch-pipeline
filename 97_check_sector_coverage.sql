-- 97_check_sector_coverage.sql
-------------------------------------------------------------------
-- Read-only check: confirms every active India stock has a sector
-- assigned (even if it's the "Unclassified" fallback). Changes
-- nothing.
--
-- Expected: 0.
-------------------------------------------------------------------

select count(*) as stocks_with_no_sector_at_all
from assets
where asset_type = 'equity' and market = 'india' and is_active = true and sector_id is null;
