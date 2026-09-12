-- 44_fix_research_reports_pk.sql
-------------------------------------------------------------------
-- Fixes "there is no unique or exclusion constraint matching the ON
-- CONFLICT specification" when publishing a research report.
--
-- Root cause: 43_add_research_reports_table.sql's `create table if
-- not exists` step silently did nothing (the table already existed
-- from an earlier partial run), so it never actually got its
-- `asset_id` PRIMARY KEY -- only the later `add column if not
-- exists` calls ran, adding the columns but not the key. Without a
-- primary key (or other unique constraint) on asset_id, Postgres has
-- nothing for the app's `upsert(..., { onConflict: "asset_id" })`
-- call to match against, so every publish fails.
--
-- This adds the missing primary key only if it's not already there,
-- so it's safe to run even if a future attempt already has it.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run).
-------------------------------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'research_reports'
      AND constraint_type = 'PRIMARY KEY'
  ) THEN
    ALTER TABLE public.research_reports ADD PRIMARY KEY (asset_id);
    RAISE NOTICE 'Added missing primary key on research_reports.asset_id';
  ELSE
    RAISE NOTICE 'research_reports already has a primary key -- nothing to do';
  END IF;
END $$;
