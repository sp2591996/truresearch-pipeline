-- 120_add_v5_score_columns.sql
-------------------------------------------------------------------
-- Adds one more column for TrueScore v3 (formula_version
-- truescore_v5): a Market Cap Score component, added on top of the
-- 5 components already in truescore_v4 (ML Rank, Growth, Relative
-- Valuation, Volatility, Legacy), directly to address a finding from
-- reviewing truescore_v4: its "Top rated" list still leaned toward
-- small, obscure micro-cap stocks. Market Cap Score ranks each stock
-- against the WHOLE market (not sector-relative, same approach as
-- Legacy Score) -- bigger, more established companies score higher.
--
-- New weights (Avdhoot's spec): ML Rank 25% / Growth 20% / Relative
-- Valuation 20% / Volatility 10% / Legacy 15% / Market Cap 10%.
--
-- truescore_v3 (live) and truescore_v4 (previous review candidate)
-- are both left completely untouched -- this column is only
-- populated for truescore_v5 rows, kept alongside them for
-- comparison.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

alter table public.scores
  add column if not exists market_cap_score numeric;

comment on column public.scores.market_cap_score is
  'Market Cap Score (formula_version truescore_v5+): the stock''s market capitalization ranked against EVERY OTHER stock in the whole market (not sector-relative, same approach as legacy_score) on a 0-100 percentile scale -- bigger/more established companies score higher. Added specifically to reduce how often small, obscure micro-cap stocks appear in the "Strong" rated list. See 14_score_current_stocks.py.';
