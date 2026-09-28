-- 150_add_industries.sql
-- -------------------------------------------------------------------
-- Phase 1 of the sector/industry rework (Avdhoot's request, Session
-- 38-39: Gillette/HUL/Nestle shouldn't be treated as peers just
-- because they're all "Consumer Defensive"; Reliance shouldn't be
-- compared 1:1 against pure oil & gas refiners either).
--
-- WHAT THIS ADDS (plain English):
--   1. A new `industries` table -- a finer-grained grouping than
--      `sectors`, and each industry belongs to exactly one sector
--      (e.g. "Household & Personal Products" industry sits under the
--      "Consumer Defensive" sector). A genuine conglomerate (Reliance,
--      Adani Enterprises, ITC...) gets its own "Diversified - <Sector
--      Name>" industry row instead of being forced into a real
--      industry it doesn't actually belong in -- per Avdhoot's
--      decision, scoped PER SECTOR (so a diversified energy
--      conglomerate and a diversified industrials conglomerate don't
--      end up lumped together either).
--   2. `assets` gets a new `industry_id` column (nullable for now --
--      Phase 2's assignment script fills it in for every stock; until
--      then the site keeps working exactly as it does today, since
--      nothing reads this column yet).
--   3. A new `industry_scores` table -- identical shape to the
--      existing `sector_scores` table, just keyed by industry_id
--      instead of sector_id. Populated by Phase 3 (the scoring
--      scripts), empty until then.
--
-- Nothing in this migration changes any EXISTING table's behavior or
-- any number currently shown on the site -- it only adds new, unused-
-- until-later structure. Safe to run now, well before Phases 2-5 are
-- built.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-- -------------------------------------------------------------------

-- 1. industries table.
create table if not exists public.industries (
  industry_id bigint generated always as identity primary key,
  sector_id bigint not null references public.sectors(sector_id),
  name text not null,
  market text not null,
  is_diversified boolean not null default false,  -- true for "Diversified - <Sector>" rows (conglomerates)
  created_at timestamptz not null default now(),
  -- Same industry name can exist under different sectors in theory
  -- (rare), and "Diversified" is deliberately per-sector -- so
  -- uniqueness is scoped to (name, sector_id, market), not name alone.
  constraint industries_name_sector_market_key unique (name, sector_id, market)
);

comment on table public.industries is
  'Finer-grained grouping than sectors, one level down (each industry belongs to exactly one sector). Added Session 38-39 to fix over-broad sector peer comparisons (e.g. Gillette vs HUL vs Nestle all landing in "Consumer Defensive"). is_diversified=true marks the per-sector "Diversified" bucket used for genuine conglomerates (Reliance, Adani Enterprises, etc.) that do not belong in any single real industry.';

alter table public.industries enable row level security;
drop policy if exists "Public read access" on public.industries;
create policy "Public read access" on public.industries for select using (true);
grant select on public.industries to anon, authenticated;

-- 2. assets.industry_id (nullable -- Phase 2 fills this in).
alter table public.assets
  add column if not exists industry_id bigint references public.industries(industry_id);

comment on column public.assets.industry_id is
  'Finer-grained grouping than sector_id -- see industries table. NULL until Phase 2''s assignment script runs; existing sector_id-based logic is unaffected until frontend code is updated in Phase 5 to read this instead.';

-- 3. industry_scores table -- same shape as sector_scores.
create table if not exists public.industry_scores (
  industry_id bigint not null references public.industries(industry_id),
  run_date date not null,
  formula_version text not null,
  avg_truescore numeric,
  stock_count integer,
  industry_ml_score numeric,
  industry_growth_score numeric,
  industry_valuation_score numeric,
  industry_rank_score numeric,        -- ranked against other industries in the SAME sector (not market-wide -- comparing "Software" to "Household Products" cross-sector isn't meaningful the way comparing two sectors is)
  industry_growth_raw numeric,
  industry_pe numeric,
  industry_revenue_growth numeric,
  industry_ebitda_growth numeric,
  industry_ebit_growth numeric,
  industry_pat_growth numeric,
  created_at timestamptz not null default now(),
  primary key (industry_id, run_date, formula_version)
);

comment on table public.industry_scores is
  'One row per industry per run_date/formula_version -- the industry-level twin of sector_scores. Populated by Phase 3 (14_score_current_stocks.py / 73_score_us_stocks.py), empty until then. industry_rank_score ranks an industry against other industries WITHIN THE SAME SECTOR, unlike sector_rank_score which ranks sectors market-wide.';

alter table public.industry_scores enable row level security;
drop policy if exists "Public read access" on public.industry_scores;
create policy "Public read access" on public.industry_scores for select using (true);
grant select on public.industry_scores to anon, authenticated;
