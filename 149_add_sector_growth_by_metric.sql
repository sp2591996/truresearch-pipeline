-- 149_add_sector_growth_by_metric.sql
-- Session 38: adds 4 new columns to sector_scores so the sector-level
-- Revenue/EBITDA/EBIT/PAT growth % (each computed the same
-- aggregate-sums-first way as the existing sector_pe / sector_growth_raw
-- columns) can be stored and read consistently everywhere, instead of
-- each frontend page averaging each stock's own growth % live.
--
-- Run this once in the Supabase SQL Editor, then re-run
-- 14_score_current_stocks.py (India) and 73_score_us_stocks.py (USA)
-- to populate the new columns.

alter table sector_scores
  add column if not exists sector_revenue_growth double precision,
  add column if not exists sector_ebitda_growth double precision,
  add column if not exists sector_ebit_growth double precision,
  add column if not exists sector_pat_growth double precision;
