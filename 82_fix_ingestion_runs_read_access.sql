-- 82_fix_ingestion_runs_read_access.sql
-------------------------------------------------------------------
-- Fixes "permission denied for table ingestion_runs" on the new
-- Pipeline Runs admin page. `ingestion_runs` was supposed to already
-- be covered by 23_add_public_read_policies.sql / 24_grant_anon_select.sql,
-- but the website is still being refused, so this re-applies both
-- fixes for just this one table. Safe to re-run any number of times.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run).
-------------------------------------------------------------------

-- 1. Table-level grant: lets the website's "anon" connection touch
--    this table at all.
GRANT SELECT ON ingestion_runs TO anon, authenticated;

-- 2. Row Level Security policy: lets it see the actual rows (a grant
--    alone isn't enough once RLS is turned on for a table).
DROP POLICY IF EXISTS "Public read access" ON ingestion_runs;
CREATE POLICY "Public read access" ON ingestion_runs FOR SELECT USING (true);
