-- 134_check_table_sizes.sql
-------------------------------------------------------------------
-- Read-only check (Avdhoot, P6, 2026-09-24): "my supabase size is
-- still 431 out of 500 mb, given I have deleted all the remaining
-- stocks shouldnt it come down". Postgres doesn't shrink a table's
-- file on disk just because rows were deleted -- DELETE only marks
-- that space as reusable for future inserts (MVCC), it doesn't return
-- it to the OS. VACUUM FULL is what actually rewrites a table into a
-- smaller file and gives the space back.
--
-- This just lists every table by its ACTUAL on-disk size right now,
-- biggest first, so we VACUUM FULL only the ones actually worth it
-- instead of blindly running it on everything (VACUUM FULL briefly
-- locks whichever table it's running on, so no reason to lock ones
-- that are already tiny). Changes nothing.
-------------------------------------------------------------------

select
  relname as table_name,
  pg_size_pretty(pg_total_relation_size(relid)) as total_size,
  pg_size_pretty(pg_relation_size(relid)) as table_size,
  pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) as indexes_and_toast_size,
  n_live_tup as approx_live_rows,
  n_dead_tup as approx_dead_rows
from pg_catalog.pg_statio_user_tables
join pg_stat_user_tables using (relid)
order by pg_total_relation_size(relid) desc
limit 20;
