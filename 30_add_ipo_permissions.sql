-- 30_add_ipo_permissions.sql
-------------------------------------------------------------------
-- IPO Tracker (PRD.md H1 / Wireframes.md "IPO Tracker"). The `ipos`
-- and `ipo_assessments` tables were created back in 01_create_tables.sql
-- but never got the same public-read treatment every other
-- frontend-facing table needed (23_add_public_read_policies.sql /
-- 24_grant_anon_select.sql) -- without this, the frontend's anon key
-- gets "permission denied" (or silently zero rows) the same way
-- shareholding_pattern did before Session 10 part 11 fixed it there.
--
-- Same two-layer fix as those two scripts, just for these 2 tables:
--   1. Row Level Security read policy (RLS was enabled on every table
--      back in Session 4, so no policy = zero rows even with a
--      correct key).
--   2. Table-level GRANT SELECT to the `anon` role (a separate gate
--      from RLS -- both are required).
-- Read-only: the frontend's anon key still cannot insert/update/
-- delete. Writes only ever come from the Python pipeline's
-- service_role key.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run), same place every other
-- numbered .sql file in this project has been run. Safe to re-run.
-------------------------------------------------------------------

DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ipos', 'ipo_assessments']
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "Public read access" ON %I;', tbl);
        EXECUTE format('CREATE POLICY "Public read access" ON %I FOR SELECT USING (true);', tbl);
        EXECUTE format('GRANT SELECT ON %I TO anon, authenticated;', tbl);
        RAISE NOTICE 'Public read access enabled for table: %', tbl;
    END LOOP;
END $$;
