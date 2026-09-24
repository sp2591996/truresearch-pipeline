-- 138_add_icon_column_to_assets.sql
-------------------------------------------------------------------
-- Fixes a gap from migration 137: the Stock Detail Upload Excel
-- template has a "Company Logo" column (Col R), but 137 left it
-- unwired -- it was treated as a future file-upload feature and
-- silently skipped, while the equivalent Sector Upload column
-- ("Sector Logo (icon)") WAS wired, as a simple icon name/key on
-- sector_overviews.icon. That inconsistency is the bug this fixes.
--
-- Goes on `assets`, not `stock_deepdive`: the logo is needed on
-- Stock Page Section 1 (shown immediately, above the fold, on every
-- visit), not gated behind the "subscribe to see more" Section 9
-- Deepdive tab that stock_deepdive backs. Same idea as
-- sector_overviews.icon, just placed on the per-asset row instead of
-- the per-sector row.
-------------------------------------------------------------------

alter table assets
  add column if not exists icon text;

comment on column assets.icon is
  'Stock Page Section 1 logo -- an icon name/key the frontend maps to an image/SVG, not an uploaded image file. Admin Page Section 2 (Stock Detail Upload), Col R "Company Logo".';
