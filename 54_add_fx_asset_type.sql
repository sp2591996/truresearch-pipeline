-- ============================================================================
-- TrueResearch V2 — Session 28: allow "fx" as an asset type
-- ============================================================================
-- Same pattern as 07_add_index_asset_type.sql / the silver migration --
-- FX pairs (PRD.md L5) are just more rows in `assets`, reusing all existing
-- price-history machinery. Run this in Supabase's SQL Editor before running
-- 55_add_fx_assets.py.
-- ============================================================================

alter table assets drop constraint if exists assets_asset_type_check;
alter table assets add constraint assets_asset_type_check
  check (asset_type in ('equity','gold','silver','fx','mutual_fund','debt','reit','intl_equity','index'));
