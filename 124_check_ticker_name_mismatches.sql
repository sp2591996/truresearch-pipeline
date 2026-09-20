-- 124_check_ticker_name_mismatches.sql
-- -------------------------------------------------------------------
-- Diagnostic only (Avdhoot's live report, Session 38): the stock page
-- showed "JAICORPLTD -- Western Digital", i.e. an Indian-looking
-- ticker paired with a US company's name. The frontend code that
-- renders this (TrueScoreDeepdive.tsx) just displays whatever
-- `assets.name` says for that ticker+market -- it doesn't invent or
-- swap names, so this points to a real data problem in the `assets`
-- table itself: a row where the ticker and name don't belong together.
--
-- Run this in Supabase's SQL editor and send Avdhoot (well, send
-- yourself, or paste the results back to Claude) whatever comes back.
-- This can't fix the problem sight-unseen -- it's a first pass to see
-- how big the problem is and find the exact bad row(s).
-- -------------------------------------------------------------------

-- 1. The exact row(s) behind the reported bug -- find every asset
-- whose ticker is "JAICORPLTD" (across both markets, in case there's
-- a duplicate) and see what name/market is actually stored for it.
SELECT asset_id, ticker, name, market, sector_id, asset_type, is_active
FROM assets
WHERE ticker = 'JAICORPLTD';

-- 2. Same check the other way -- find any asset row whose NAME is
-- "Western Digital" and see what ticker(s) are attached to it. If
-- there are two rows here (one correctly "WDC"/usa, one incorrectly
-- "JAICORPLTD"/something), that's the actual duplicate/corruption.
SELECT asset_id, ticker, name, market, sector_id, asset_type, is_active
FROM assets
WHERE name ILIKE '%western digital%';

-- 3. A broader sanity check across the whole `assets` table: find any
-- ticker string that appears MORE THAN ONCE overall (across markets or
-- within the same market) -- a ticker should be unique per market, so
-- any group here with count > 1 within the same market is a genuine
-- duplicate-row problem, not just an India/USA ticker coincidence.
SELECT ticker, market, COUNT(*) AS row_count, array_agg(asset_id) AS asset_ids, array_agg(name) AS names
FROM assets
GROUP BY ticker, market
HAVING COUNT(*) > 1
ORDER BY row_count DESC;

-- 4. A rough pattern check for India-style tickers (ending "LTD",
-- "IND", or all-uppercase with no spaces, common NSE symbol style)
-- that are marked market = 'usa' -- these are the ones most likely to
-- be the same kind of mismatch as the reported bug.
SELECT asset_id, ticker, name, market, sector_id
FROM assets
WHERE market = 'usa'
  AND (ticker LIKE '%LTD' OR ticker LIKE '%IND' OR ticker LIKE '%CORP')
ORDER BY ticker;
