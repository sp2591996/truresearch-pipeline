-- ============================================================================
-- TrueResearch V2 — Phase B, Step 6, Script 1: allow "index" as an asset type
-- ============================================================================
-- We need to store the Nifty 100 benchmark index's price history somewhere,
-- to measure "did this stock beat the market" for TrueScore training. The
-- cleanest way is to treat the index as just another row in `assets` (reusing
-- all our existing price-history machinery) rather than a special-case table.
-- This adds "index" as an allowed asset_type. Safe to run more than once.
-- ============================================================================

alter table assets drop constraint if exists assets_asset_type_check;
alter table assets add constraint assets_asset_type_check
  check (asset_type in ('equity','gold','mutual_fund','debt','reit','intl_equity','index'));
