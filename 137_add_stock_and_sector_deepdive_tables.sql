-- 137_add_stock_and_sector_deepdive_tables.sql
-------------------------------------------------------------------
-- P6 PRD (Stock Page Section 9 Deepdive + Admin Page Sections 2 & 3):
-- admin-uploadable qualitative content for the Stock Page's deep-dive
-- tab (revenue model, business quality write-ups, bear/base/bull
-- cases, strengths/weaknesses, risks, management, why invest/not,
-- what to watch) and the Sector Specific Page's equivalent content.
-- Everything here maps 1:1 to the Admin Page's Excel upload columns
-- (see 137_stock_detail_upload_template.xlsx / 137_sector_upload_
-- template.xlsx, generated alongside this migration).
--
-- New table rather than reusing `research_reports` (which is a
-- separate, differently-shaped concept: template-driven, tiered
-- flagship/summary reports) or bolting more columns onto
-- `asset_qualitative` (which is small and already serves its own
-- purpose) -- this keeps the admin-upload content in one place that
-- maps cleanly to the Excel template's columns.
-------------------------------------------------------------------

create table if not exists stock_deepdive (
  asset_id integer primary key references assets(asset_id) on delete cascade,

  -- Stock Page Section 5 -- "What does the company do?" (50-100 words)
  what_does_company_do text,

  -- Stock Page Section 9A -- Revenue Model
  target_customers text,
  target_geographies text,
  product_offerings text,        -- one offering per line
  revenue_streams_share text,    -- one "Label: NN%" per line, e.g. "BFSI: 32%"

  -- Stock Page Section 9F/9G -- Strengths, Weaknesses, Risks (min 3 each, one per line)
  strengths text,
  weaknesses text,
  key_risks text,

  -- Stock Page Section 9H -- Company Management (50-100 words)
  management_text text,

  -- Stock Page Section 9J -- Bear / Base / Bull Case (min 3 points each, one per line)
  bear_case text,
  base_case text,
  bull_case text,

  -- Stock Page Section 9L -- Reasons for Investment (min 3 points each, one per line)
  why_invest text,
  why_not_invest text,

  -- Stock Page Section 9M -- Key Things to Watch (one per line)
  key_things_to_watch text,

  updated_at timestamptz not null default now()
);

comment on table stock_deepdive is
  'Admin-uploaded qualitative content for a stock''s Section 9 Deepdive tab. One row per asset. Populated via the Admin Page''s Stock Detail Upload Excel (Section 2), matching its columns A-Q (Col A ticker is the match key, not stored here; Col R Company Logo is handled as a file, not text).';

alter table stock_deepdive enable row level security;
drop policy if exists "Stock deepdive is public to read" on stock_deepdive;
create policy "Stock deepdive is public to read" on stock_deepdive
  for select using (true);
-- No insert/update/delete policy for anon/authenticated -- writes only
-- happen server-side via the admin upload route, using the service
-- role key (same pattern as every other admin-only write path in this
-- project).

-- Sector Specific Page's equivalent content extends the sector_overviews
-- table that already exists (same shape of idea -- one row per sector,
-- admin-managed) rather than creating a second sector table.
alter table sector_overviews
  add column if not exists strengths text,
  add column if not exists weaknesses text,
  add column if not exists key_risks text,
  add column if not exists why_invest text,
  add column if not exists why_not_invest text,
  add column if not exists key_things_to_watch text,
  add column if not exists icon text;

comment on column sector_overviews.overview_text is
  'Sector Specific Page Section 4 -- "Sector explained in 1 min" (50-100 words). Admin Page Section 3, Col B.';
comment on column sector_overviews.strengths is 'One strength per line. Admin Page Section 3, Col C.';
comment on column sector_overviews.weaknesses is 'One weakness per line. Admin Page Section 3, Col D.';
comment on column sector_overviews.key_risks is 'One risk per line. Admin Page Section 3, Col E.';
comment on column sector_overviews.why_invest is 'One reason per line. Admin Page Section 3, Col F.';
comment on column sector_overviews.why_not_invest is 'One reason per line. Admin Page Section 3, Col G.';
comment on column sector_overviews.key_things_to_watch is 'One item per line. Admin Page Section 3, Col H.';
comment on column sector_overviews.icon is 'Customised sector icon (Admin Page Section 3, Col I) -- an icon name/key the frontend maps to an SVG, not an uploaded image file.';
