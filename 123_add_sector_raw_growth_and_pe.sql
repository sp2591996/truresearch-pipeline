-- 123_add_sector_raw_growth_and_pe.sql
-- -------------------------------------------------------------------
-- Avdhoot's request (this session): the Sector Page's Growth and
-- Relative Valuation deepdive popups need to show REAL numbers (this
-- sector's actual growth %, this sector's actual P/E, and the same for
-- other sectors / the overall market) -- not just the 10-100 rank score,
-- which is meaningless to compare directly ("what IS a growth score of
-- 62?"). `sector_scores` already has sector_growth_score and
-- sector_valuation_score (the RANK), but 14_score_current_stocks.py was
-- computing the underlying raw numbers (sector_growth_raw, sector_pe)
-- and then throwing them away before saving -- this just adds two
-- columns so the script (already updated to write them) has somewhere
-- to put them.
--
-- Both nullable: a sector can have no meaningful growth rate (not
-- enough fiscal-year history) or no meaningful P/E (net loss overall),
-- same "leave it None rather than fake a number" rule already used
-- everywhere else in this pipeline.
--
-- Run this in the Supabase SQL editor (or via the Supabase CLI) BEFORE
-- re-running 14_score_current_stocks.py, same as every other
-- *_add_*_columns.sql migration in this folder.
-- -------------------------------------------------------------------

alter table sector_scores
  add column if not exists sector_growth_raw double precision,
  add column if not exists sector_pe double precision;

comment on column sector_scores.sector_growth_raw is
  'Real (not ranked) sector-wide growth rate -- summed Revenue/EBIT/EBITDA/PAT across the sector''s stocks, then 3-year CAGR per metric (fallback to YoY-average per metric when 3-yr CAGR is unavailable/an outlier), averaged across the 4 metrics. Same units as a decimal growth rate (0.15 = 15%). NULL if nothing was computable.';

comment on column sector_scores.sector_pe is
  'Real (not ranked) sector-aggregate P/E: sum of member stocks'' market cap / sum of member stocks'' net income (only stocks with positive market cap included; NULL if the sector''s net income sum is not positive, i.e. the sector is loss-making overall).';
