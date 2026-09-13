-- 65_redefine_sector_score_components.sql
-------------------------------------------------------------------
-- Redefines the Sector Rank Score (added in 64_...sql) to be built
-- from its OWN 3 sector-level components, mirroring exactly how
-- stock-level TrueScore is 3 components -- not just an aggregate of
-- stocks' already-combined overall_score, per Avdhoot's correction:
--
--   1. sector_ml_score       -- market-cap-weighted average of the
--                                sector's stocks' ml_rank_score.
--   2. sector_growth_score   -- sector-level growth rate (computed
--                                from SUMMED Revenue/EBIT/EBITDA/PAT
--                                across the sector's stocks, same
--                                2-year YoY method as stock Growth
--                                Score), ranked 10-100 against every
--                                OTHER sector.
--   3. sector_valuation_score -- sector-level P/E = sum(market caps)
--                                / sum(net income) across the sector's
--                                stocks (an aggregate P/E, same way
--                                real index P/E ratios are built),
--                                ranked 10-100 against every OTHER
--                                sector -- cheaper (lower P/E) = higher
--                                score.
--
-- sector_rank_score (already existing) becomes the average of these
-- three -- same equal-weight design as stock-level overall_score.
-- avg_truescore is UNCHANGED and kept as-is (still a market-cap-
-- weighted average of stocks' overall_score -- a separate, purely
-- informational figure, not part of this new calculation).
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

alter table public.sector_scores
  add column if not exists sector_ml_score numeric,
  add column if not exists sector_growth_score numeric,
  add column if not exists sector_valuation_score numeric;

comment on column public.sector_scores.sector_ml_score is
  'Market-cap-weighted average of the sector''s stocks'' ml_rank_score (0-100). NOT ranked against other sectors -- a plain weighted average, per Avdhoot''s spec.';
comment on column public.sector_scores.sector_growth_score is
  'This sector''s growth rate (avg YoY growth of SUMMED Revenue/EBIT/EBITDA/PAT across its stocks, last 2 fiscal years) ranked 10-100 against every OTHER sector''s growth rate.';
comment on column public.sector_scores.sector_valuation_score is
  'This sector''s aggregate P/E (sum of member market caps / sum of member net income) ranked 10-100 against every OTHER sector''s aggregate P/E -- cheaper (lower P/E) scores higher.';
comment on column public.sector_scores.sector_rank_score is
  'Sectoral Score: equal-weighted average of sector_ml_score, sector_growth_score and sector_valuation_score (see this migration''s header comment). Previously (before this migration) this was ranked directly off avg_truescore instead -- superseded.';
