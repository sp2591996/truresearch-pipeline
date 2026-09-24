-- 139_add_acronym_column_to_assets.sql
-------------------------------------------------------------------
-- Fixes the same class of gap as migration 138, found while wiring
-- up the Admin "download current data" feature: the Stock Detail
-- Upload Excel's Column B ("Company Acronym") was being parsed by
-- the upload route but never written anywhere -- same silent-drop
-- bug as Column R (Company Logo) was before 138. Goes on `assets`
-- for the same reason as icon: it's a Section 1 field shown on every
-- Stock Page visit, not deepdive-tab-only content.
-------------------------------------------------------------------

alter table assets
  add column if not exists acronym text;

comment on column assets.acronym is
  'Stock Page Section 1 short name/acronym shown next to the logo. Admin Page Section 2 (Stock Detail Upload), Col B "Company Acronym".';
