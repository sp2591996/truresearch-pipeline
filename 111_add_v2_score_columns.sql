-- 111_add_v2_score_columns.sql
-------------------------------------------------------------------
-- Adds TrueResearch's TrueScore v2 redesign (formula_version
-- truescore_v4): two new components, Volatility Score and Legacy
-- Score, computed alongside the existing 3 (Relative Valuation, ML
-- Rank, Growth) inside 14_score_current_stocks.py.
--
-- WHAT THIS CHANGES (plain English):
--   `scores` gets two new columns, `volatility_score` and
--   `legacy_score` (0-100, same scale family as the existing
--   components). These are only populated for formula_version
--   truescore_v4 rows -- truescore_v3 rows keep these columns NULL.
--   truescore_v3 stays completely unchanged and keeps being written
--   every run, side by side with the new truescore_v4 rows, until
--   Avdhoot reviews and approves promoting v4 to live.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

alter table public.scores
  add column if not exists volatility_score numeric;

alter table public.scores
  add column if not exists legacy_score numeric;

comment on column public.scores.volatility_score is
  'Volatility Score (formula_version truescore_v4+): 30-day annualized price volatility, inverted (lower volatility = higher score) and ranked against other stocks in the SAME sector on a 0-100 percentile scale. See 14_score_current_stocks.py.';

comment on column public.scores.legacy_score is
  'Legacy Score (formula_version truescore_v4+): how long the stock has been listed (tenure in days since assets.listed_date), ranked against every OTHER stock in the market (not sector-relative) on a 0-100 percentile scale -- older/longer-listed = higher score. See 14_score_current_stocks.py.';
