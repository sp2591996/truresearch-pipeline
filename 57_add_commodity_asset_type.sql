-- ============================================================================
-- TrueResearch V2 -- Session 29: allow "commodity" as an asset type
-- ============================================================================
-- Same pattern as 54_add_fx_asset_type.sql / 07_add_index_asset_type.sql --
-- Crude oil (PRD.md L5, "Commodities") is just more rows in `assets`,
-- reusing all existing price-history machinery. Run this in Supabase's
-- SQL Editor before running 58_add_crude_oil_assets.py.
-- ============================================================================

alter table assets drop constraint if exists assets_asset_type_check;
alter table assets add constraint assets_asset_type_check
  check (asset_type in ('equity','gold','silver','fx','commodity','mutual_fund','debt','reit','intl_equity','index'));
