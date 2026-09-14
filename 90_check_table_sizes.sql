-- 90_check_table_sizes.sql
-------------------------------------------------------------------
-- Read-only diagnostic: lists every table in the database with its
-- total on-disk size (data + indexes), largest first. Used to find
-- out what's actually filling up the 500 MB free-tier limit, before
-- deciding what to trim.
--
-- Changes nothing. Safe to run any time.
--
-- Run manually in Supabase:
--   Dashboard -> SQL Editor -> New query -> paste this -> Run
-------------------------------------------------------------------

select relname as table_name, pg_size_pretty(pg_total_relation_size(relid)) as size
from pg_catalog.pg_statio_user_tables
order by pg_total_relation_size(relid) desc
limit 15;
