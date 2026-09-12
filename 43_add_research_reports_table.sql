-- 43_add_research_reports_table.sql
-------------------------------------------------------------------
-- Research Report Page (PRD.md B3 / Wireframes.md "Research Report
-- Page"). One row per stock, holding a sanitized HTML write-up
-- authored by Claude and published through the new
-- /admin/research-upload page -- exactly the same "upload one HTML
-- file per item" pipeline already built for IPOs
-- (42_add_analysis_html_column.sql / app/api/ipo-analysis-html /
-- components/IpoHtmlFrame.tsx), just keyed to a stock (asset_id)
-- instead of an IPO.
--
-- tier matches PRD.md B3's "Flagship depth for top ~50 stocks, faster
-- Auto Research Summary for the rest" -- shown as a badge on the
-- Research page and each report's own header.
--
-- Same two-layer public-read fix every other frontend-facing table
-- needs (see 23_add_public_read_policies.sql / 30_add_ipo_permissions.sql):
-- RLS policy + anon GRANT SELECT. Writes only ever come from the admin
-- upload page's API route, which uses the SECRET key (bypasses RLS),
-- never the anon key -- so this migration only ever grants read access,
-- same as every other table's public policy.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

-- Session 25 fix: an earlier attempt at running this file apparently
-- left a `research_reports` table behind with only some of its
-- columns (Avdhoot hit "column report_html does not exist" when the
-- COMMENT statements below ran against it). `create table if not
-- exists` silently does nothing when the table is already there, even
-- if it's missing columns -- so each column is now added separately
-- with `add column if not exists`, which repairs a partial table the
-- same safe way 42_add_analysis_html_column.sql already does. Safe to
-- re-run any number of times either way.
create table if not exists public.research_reports (
  asset_id integer primary key references public.assets(asset_id) on delete cascade
);

alter table public.research_reports
  add column if not exists tier text not null default 'summary',
  add column if not exists report_html text,
  add column if not exists report_html_updated_at timestamptz,
  add column if not exists report_html_source_filename text;

-- Constraints can't use "if not exists" the same way -- drop-then-add
-- so re-running this file never errors on a duplicate constraint.
alter table public.research_reports drop constraint if exists research_reports_tier_check;
alter table public.research_reports add constraint research_reports_tier_check check (tier in ('flagship', 'summary'));

comment on table public.research_reports is
  'One written research report per stock (PRD.md B3), uploaded as a sanitized HTML file via /admin/research-upload -- same pipeline as ipo_assessments.analysis_html.';
comment on column public.research_reports.tier is
  '''flagship'' (deep, top ~50 stocks) or ''summary'' (faster Auto Research Summary, the rest) -- shown as a badge on /research and the report page itself.';
comment on column public.research_reports.report_html is
  'Sanitized HTML (server-side sanitized on upload, same allow-list as ipo_assessments.analysis_html) rendered full-page via IpoHtmlFrame on /research/[ticker].';

alter table public.research_reports enable row level security;

drop policy if exists "Public read access" on public.research_reports;
create policy "Public read access" on public.research_reports for select using (true);
grant select on public.research_reports to anon, authenticated;
