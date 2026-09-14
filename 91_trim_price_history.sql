-- 91_trim_price_history.sql
-------------------------------------------------------------------
-- Trims prices_daily down to the last 5 years of history per stock,
-- to bring the database back under Supabase's 500 MB free-tier
-- limit. prices_daily was found to be 640 MB -- 91% of the entire
-- 705 MB database -- after the 10-year price history backfill for
-- all 2,568 India stocks (20_backfill_new_stocks_price_history.py).
--
-- Why 5 years is safe to cut down to: the frontend's own price
-- charts only ever display 5 years of history (see the comment in
-- 05_daily_price_refresh.py), so nothing the site shows today is
-- affected. The only thing that loses runway is future ML model
-- retraining, which previously had up to 10 years available.
--
-- Run this in THREE steps, in order, in Supabase's SQL Editor
-- (Dashboard -> SQL Editor -> New query):
--
-- STEP 1 -- preview only, changes nothing. Run this first to see
-- how many rows will be deleted:
select count(*) as rows_to_delete
from prices_daily
where date < (current_date - interval '5 years');

-- STEP 2 -- the actual delete. Run this only after checking Step 1's
-- number looks reasonable (roughly half of prices_daily's current
-- row count, since it's a 10-year backfill being cut to 5 years).
-- This cannot be undone -- if you ever want the older history back,
-- it would need to be re-fetched from Yahoo Finance from scratch.
--
-- delete from prices_daily
-- where date < (current_date - interval '5 years');

-- STEP 3 -- reclaims the freed disk space. A DELETE alone does not
-- shrink the table on disk (Postgres keeps the empty space around
-- for reuse) -- Supabase's storage-used figure won't actually drop
-- until this runs. Takes a short exclusive lock on prices_daily
-- (fine to run right after Step 2; the table is only ever written
-- to by the daily/backfill scripts, not read live by users during
-- this).
--
-- vacuum full prices_daily;
-------------------------------------------------------------------
