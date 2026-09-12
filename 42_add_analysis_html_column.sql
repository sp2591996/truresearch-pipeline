-- 42_add_analysis_html_column.sql
-- -------------------------------------------------------------------
-- New HTML-based IPO Analyser pipeline (replaces the paste-JSON flow
-- as the primary path going forward, per Avdhoot's direct request:
-- "give you an html file as an input for each of the IPO analysis").
--
-- Claude now authors a complete, styled HTML snippet per IPO (the
-- 11-part IPO Analyser content from PRD.md H1, written as real HTML
-- instead of a JSON block Claude previously had to structure by hand
-- into fixed sections). Avdhoot uploads that HTML file at
-- /admin/ipo-upload; the server sanitizes it (strips scripts, event
-- handlers, iframes, forms -- see app/api/ipo-analysis-html/route.ts)
-- and stores the safe result here.
--
-- The older `ai_analysis` (jsonb, 7-section schema) column and its
-- upload path are left untouched -- the 5 already-uploaded IPO
-- analyses keep rendering exactly as before. The IPO detail page
-- prefers `analysis_html` when present, and only falls back to
-- `ai_analysis` for IPOs that haven't been re-uploaded yet.
--
-- Run this once in the Supabase SQL editor, same as every other
-- numbered migration in this folder.
-- -------------------------------------------------------------------

alter table public.ipo_assessments
  add column if not exists analysis_html text,
  add column if not exists analysis_html_updated_at timestamptz,
  add column if not exists analysis_html_source_filename text;

comment on column public.ipo_assessments.analysis_html is
  'Sanitized HTML snippet (server-side sanitized on upload) authored by Claude and uploaded via /admin/ipo-upload. Rendered as the primary "IPO Analysis" section on /ipos/[ipoId] when present; takes priority over the older ai_analysis jsonb column.';
comment on column public.ipo_assessments.analysis_html_updated_at is
  'When analysis_html was last saved/overwritten.';
comment on column public.ipo_assessments.analysis_html_source_filename is
  'Original filename of the uploaded .html file, shown on the IPO page as a small provenance note (e.g. "reliance_analysis.html").';
