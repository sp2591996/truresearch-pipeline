-- 155_sector_industry_source_tracking_and_overrides.sql
-- -------------------------------------------------------------------
-- Adds the machinery to (a) protect manually-corrected sector/industry
-- assignments from ever being silently overwritten by a future Yahoo
-- Finance-based sync, and (b) let genuinely new/ambiguous stocks get
-- flagged for Avdhoot to resolve in the Admin page instead of being
-- auto-classified with a possibly-wrong label.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor ->
-- New query -> paste this whole file -> Run). Safe to re-run.
-- -------------------------------------------------------------------

-- 1. Track where a stock's sector/industry assignment came from.
alter table public.assets
  add column if not exists sector_source text not null default 'auto'
  check (sector_source in ('auto', 'manual'));

comment on column public.assets.sector_source is
  '''manual'' = a human (or a reviewed one-time cleanup pass) confirmed this sector_id/industry_id -- any future automated sync (e.g. weekly universe sync) must SKIP this stock entirely, never overwrite it. ''auto'' = still using whatever Yahoo Finance/the automated script last assigned, fair game to be updated automatically.';

-- 2. General reusable rules: "whenever Yahoo Finance returns THIS raw
--    sector+industry combo, always correct it to THIS sector+industry"
--    -- e.g. (Capital Goods, Steel) -> (Metals & Mining, Steel). Applied
--    automatically to any stock (existing or brand new) matching the
--    raw combo, no per-ticker entry needed.
create table if not exists public.sector_industry_aliases (
  alias_id bigint generated always as identity primary key,
  market text not null,
  raw_sector text not null,
  raw_industry text not null,
  corrected_sector_name text not null,
  corrected_industry_name text not null,
  is_diversified boolean not null default false,
  note text,
  created_at timestamptz not null default now(),
  constraint sector_industry_aliases_key unique (market, raw_sector, raw_industry)
);

comment on table public.sector_industry_aliases is
  'General Yahoo-raw-tag -> corrected-tag rules, applied to any stock (existing or new) whose raw sector+industry from Yahoo Finance matches. E.g. every stock Yahoo puts in (Capital Goods, Steel) gets corrected to (Metals & Mining, Steel) automatically.';

alter table public.sector_industry_aliases enable row level security;
drop policy if exists "Public read access" on public.sector_industry_aliases;
create policy "Public read access" on public.sector_industry_aliases for select using (true);
grant select on public.sector_industry_aliases to anon, authenticated;

-- 3. Per-ticker overrides: for company-specific corrections that don't
--    generalize to every stock sharing the same raw Yahoo tag (e.g.
--    Lenskart was mistagged "Medical Instruments & Supplies" but that
--    doesn't mean every "Medical Instruments & Supplies" stock is
--    wrong -- just this one company).
create table if not exists public.sector_industry_ticker_overrides (
  ticker text not null,
  market text not null,
  corrected_sector_name text not null,
  corrected_industry_name text not null,
  is_diversified boolean not null default false,
  note text,
  created_at timestamptz not null default now(),
  primary key (ticker, market)
);

comment on table public.sector_industry_ticker_overrides is
  'Company-specific sector/industry corrections that do not generalize into a sector_industry_aliases rule. Checked BEFORE sector_industry_aliases when classifying a stock.';

alter table public.sector_industry_ticker_overrides enable row level security;
drop policy if exists "Public read access" on public.sector_industry_ticker_overrides;
create policy "Public read access" on public.sector_industry_ticker_overrides for select using (true);
grant select on public.sector_industry_ticker_overrides to anon, authenticated;

-- 4. Review queue: a new stock whose raw Yahoo sector+industry matches
--    NEITHER a ticker override NOR a general alias gets a row here
--    instead of being auto-classified -- shows up on the Admin page
--    for Avdhoot to resolve once.
create table if not exists public.sector_industry_review_queue (
  queue_id bigint generated always as identity primary key,
  asset_id bigint not null references public.assets(asset_id),
  ticker text not null,
  company_name text,
  market text not null,
  raw_sector text,
  raw_industry text,
  suggested_sector_name text,     -- best-guess suggestion shown to Avdhoot, not auto-applied
  suggested_industry_name text,
  status text not null default 'pending' check (status in ('pending', 'resolved')),
  resolved_sector_name text,
  resolved_industry_name text,
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);

comment on table public.sector_industry_review_queue is
  'Stocks whose raw Yahoo Finance sector/industry did not match any known ticker override or alias rule -- flagged here instead of being auto-classified. Shown as a "Needs Review" list on the Admin page; resolving one here should also insert a matching row into sector_industry_ticker_overrides so the same stock is never re-flagged.';

alter table public.sector_industry_review_queue enable row level security;
drop policy if exists "Public read access" on public.sector_industry_review_queue;
create policy "Public read access" on public.sector_industry_review_queue for select using (true);
grant select on public.sector_industry_review_queue to anon, authenticated;
-- NOTE: write access (resolving a queue row) goes through the Admin
-- page's existing server-side admin auth (service-role key), not
-- through anon/authenticated -- no public write policy added here on
-- purpose, same pattern as other admin-only tables.
