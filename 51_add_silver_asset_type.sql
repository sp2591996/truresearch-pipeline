-- ============================================================================
-- TrueResearch V2 — Session 28: allow "silver" as an asset type
-- ============================================================================
-- Same pattern as 07_add_index_asset_type.sql -- Silver (PRD.md L5) is just
-- another row in `assets`, reusing all existing price-history machinery
-- (prices_daily, live_prices, market_data_provider.py) rather than a new
-- table. This adds "silver" as an allowed asset_type. Safe to run more than
-- once. Run this in Supabase's SQL Editor before running 52_add_silver_
-- asset.py (that script's insert will fail with a constraint violation
-- until this has been run).
-- ============================================================================

alter table assets drop constraint if exists assets_asset_type_check;
alter table assets add constraint assets_asset_type_check
  check (asset_type in ('equity','gold','silver','mutual_fund','debt','reit','intl_equity','index'));
