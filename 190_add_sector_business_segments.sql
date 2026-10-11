-- 173_add_sector_business_segments.sql
-- -------------------------------------------------------------------
-- Sector Deepdive's "Business" tab (SectorDeepdiveSection.tsx) used
-- to depend entirely on the Value Chain tree (value_chain_nodes),
-- which only exists for one sector (Consumer Services / Food
-- Delivery) -- every other sector, including Capital Goods, showed
-- an empty "Not uploaded yet" Business tab because of this.
--
-- Avdhoot's explicit decision (2026-10-11): scrap the Value Chain
-- dependency for this tab going forward and replace it with a
-- simpler, more quantified structure -- summarised sector segments
-- (effectively each sector's industries), each with a real market-
-- cap-share % and a short, specific description naming real
-- companies and their own % shares, similar in spirit to a stock's
-- own Business tab but summarised at sector level.
--
-- One new jsonb column on the existing sector_overviews table (one
-- row per sector already) holds this as an array of objects:
--   [{ "name": "Specialty Industrial Machinery", "market_cap_share_pct": 35.6,
--      "top_companies": "BHEL (~5.1%), ABB India (~4.9%), ...",
--      "description": "..." }, ...]
--
-- Run this in Supabase's SQL Editor. Safe to re-run.
-- -------------------------------------------------------------------

alter table public.sector_overviews
  add column if not exists business_segments jsonb;

comment on column public.sector_overviews.business_segments is
  'Array of {name, market_cap_share_pct, top_companies, description} -- summarised, quantified sector-segment breakdown shown on the Business tab. Replaces the old Value Chain tree dependency for sectors that never got a value_chain_nodes tree built.';
