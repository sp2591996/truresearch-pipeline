-- 61_add_market_mood_table.sql
-------------------------------------------------------------------
-- Market Mood / Sentiment Index (PRD.md A6). One row per calendar
-- day, holding the "marketmood_v1" formula's three real sub-scores
-- plus the blended overall number and a short auto-written
-- commentary line -- same rigor as TrueScore's own versioned,
-- documented approach (see PROJECT_STATE.md Session 30 and
-- TrueScore_Validation_Report.md for the pattern this follows).
--
-- formula_version is part of the primary key (same trick scores.py
-- uses for truescore_v2) so a future v2 formula can be backtested
-- side-by-side with v1's history still intact, rather than
-- overwriting it.
--
-- Same two-layer public-read fix every frontend-facing table needs
-- (see 23_add_public_read_policies.sql / 43_add_research_reports_table.sql):
-- RLS policy + anon GRANT SELECT. Writes only ever come from the
-- Python pipeline (62_calculate_market_mood.py), which uses the
-- SECRET key (bypasses RLS) -- this migration only ever grants read
-- access, same as every other table's public policy.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

create table if not exists public.market_mood (
  run_date date not null,
  formula_version text not null default 'marketmood_v1',
  breadth_score numeric,      -- 0-100: % of Nifty 500 stocks up today
  momentum_score numeric,     -- 0-100: % of Nifty 500 stocks above their own 50-day average
  volatility_score numeric,   -- 0-100: calmer-than-usual (high) vs choppier-than-usual (low)
  overall_score numeric,      -- 0-100: simple average of the three above (v1 -- equal weight)
  advancers integer,          -- how many stocks were up today (goes into breadth_score)
  decliners integer,          -- how many stocks were down today
  universe_count integer,     -- how many stocks had usable data this run (denominator for the two %s above)
  commentary text,            -- short auto-written sentence built from the numbers, e.g. "Markets broadly positive today -- breadth strong, momentum steady."
  created_at timestamptz not null default now(),
  primary key (run_date, formula_version)
);

comment on table public.market_mood is
  'Daily Market Mood gauge (PRD.md A6) -- one row per day per formula_version. v1 = simple average of breadth/momentum/volatility sub-scores, all built entirely from prices_daily (one consistent data source, so the exact same formula can be run live today or backtested against any past date -- no external sentiment data, no fabricated inputs).';
comment on column public.market_mood.breadth_score is
  '(advancers / universe_count) * 100, from each stock''s two most recent prices_daily closes on/before run_date.';
comment on column public.market_mood.momentum_score is
  '% of universe_count trading above their own trailing 50-day simple moving average of daily close, from prices_daily.';
comment on column public.market_mood.volatility_score is
  'Inverted percentile of today''s market-wide average 20-day realized volatility against its own trailing 1-year distribution -- calmer than usual scores higher, choppier than usual scores lower.';

alter table public.market_mood enable row level security;

drop policy if exists "Public read access" on public.market_mood;
create policy "Public read access" on public.market_mood for select using (true);
grant select on public.market_mood to anon, authenticated;
