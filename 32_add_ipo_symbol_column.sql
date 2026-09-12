-- 32_add_ipo_symbol_column.sql
-------------------------------------------------------------------
-- IPO Tracker ingestion (33_refresh_ipos.py) needs a stable way to
-- tell "this is the same IPO I saw last run" so re-running the script
-- updates existing rows instead of creating duplicates every time --
-- `ipos` only had ipo_id (auto-generated, useless for this) and
-- company_name (can have small formatting differences run to run).
-- NSE's own IPO listings always carry a `symbol` (e.g. "PRANAV"),
-- which is stable across runs -- this adds it as a real column with a
-- uniqueness constraint so 33_refresh_ipos.py can upsert on it
-- (same on_conflict=... pattern every other ingestion script here uses).
--
-- Written to be safe to re-run: skips adding the constraint if it
-- already exists, instead of erroring.
--
-- Run this in Supabase's SQL Editor, same place as every other
-- numbered .sql file in this project.
-------------------------------------------------------------------

ALTER TABLE ipos ADD COLUMN IF NOT EXISTS symbol text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ipos_symbol_unique'
    ) THEN
        ALTER TABLE ipos ADD CONSTRAINT ipos_symbol_unique UNIQUE (symbol);
    END IF;
END $$;
