-- 92_trim_price_history_delete.sql
-------------------------------------------------------------------
-- STEP 2 of the prices_daily trim (see 91_trim_price_history.sql
-- for the full context/explanation and Step 1's preview query).
--
-- This is the actual delete, ready to run as-is -- no lines need
-- uncommenting. Confirmed safe via Step 1's preview: 2,466,888 rows
-- will be deleted (rows older than 5 years), bringing prices_daily
-- down from 640 MB to a healthier size, safely under the 500 MB
-- free-tier limit once combined with 93 (VACUUM FULL) afterward.
--
-- This cannot be undone -- if older history is ever needed again,
-- it would have to be re-fetched from Yahoo Finance from scratch.
--
-- Run in Supabase's SQL Editor (Dashboard -> SQL Editor -> New
-- query -> paste this -> Run). May take a little while for ~2.4
-- million rows -- that's normal.
-------------------------------------------------------------------

delete from prices_daily
where date < (current_date - interval '5 years');
