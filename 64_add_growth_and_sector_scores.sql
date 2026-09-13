-- 64_add_growth_and_sector_scores.sql
-------------------------------------------------------------------
-- Adds TrueResearch's 3rd scoring component: Growth Score.
--
-- WHAT THIS CHANGES (plain English):
--   1. `scores` gets one new column, `growth_score` (0-100, same
--      scale family as the two existing components).
--   2. TrueScore's `overall_score` becomes the average of THREE
--      components instead of two: relative_valuation_score,
--      ml_rank_score, growth_score (previously 50/50 valuation+ML).
--      This is computed in 14_score_current_stocks.py, not here --
--      this migration only makes room for the new number.
--   3. A brand-new table, `sector_scores`, is added: one row per
--      sector per run_date, holding that sector's average TrueScore
--      AND a "sector rank score" -- sectors ranked 10-100 against
--      EACH OTHER, the same way stocks are ranked 10-100 within
--      their own sector for Growth Score. This is a new, separate
--      concept from the existing "Sector Score" already shown on
--      sector pages (which is a market-cap-weighted average, not a
--      cross-sector ranking) -- both are kept, side by side.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

-- 1. New column on the existing `scores` table.
alter table public.scores
  add column if not exists growth_score numeric;

comment on column public.scores.growth_score is
  'Growth Score (formula_version truescore_v3+): average YoY growth of Revenue, EBIT, EBITDA and PAT over the last 2 fiscal years, then ranked against other stocks in the SAME sector on a 10-100 scale (highest grower in the sector = 100, lowest = 10, evenly spaced in between -- not a percentile). See 14_score_current_stocks.py for the exact calculation.';

-- 2. New table: sector-vs-sector ranking.
create table if not exists public.sector_scores (
  sector_id bigint not null references public.sectors(sector_id),
  run_date date not null,
  formula_version text not null default 'truescore_v3',
  avg_truescore numeric,       -- plain (unweighted) average of the sector's stocks' overall_score
  sector_rank_score numeric,   -- 10-100: this sector's avg_truescore ranked against every OTHER sector's avg_truescore
  stock_count integer,         -- how many scored stocks went into avg_truescore (sanity/display use)
  created_at timestamptz not null default now(),
  primary key (sector_id, run_date, formula_version)
);

comment on table public.sector_scores is
  'One row per sector per run_date: the sector''s own average TrueScore, plus that average ranked 10-100 against every other sector (sectors "fighting" each other the same way stocks fight within a sector for Growth Score). Written by 14_score_current_stocks.py, same run as the stock-level scores.';

-- Same two-layer public-read fix every frontend-facing table needs
-- (see 23_add_public_read_policies.sql / 61_add_market_mood_table.sql):
-- RLS policy + anon GRANT SELECT. Writes only ever come from the
-- Python pipeline (14_score_current_stocks.py), which uses the
-- SECRET key (bypasses RLS) -- this migration only ever grants read.
alter table public.sector_scores enable row level security;

drop policy if exists "Public read access" on public.sector_scores;
create policy "Public read access" on public.sector_scores for select using (true);
grant select on public.sector_scores to anon, authenticated;
