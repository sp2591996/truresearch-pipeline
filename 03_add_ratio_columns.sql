-- ============================================================================
-- TrueResearch V2 — Phase B, Script 3: small schema addition
-- ============================================================================
-- Your old data has market cap and 52-week high/low, which weren't in the
-- original ratios_snapshot table. Adding them now -- this is a pure
-- addition, doesn't touch or risk any existing data. Safe to run more than
-- once.
-- ============================================================================

alter table ratios_snapshot add column if not exists market_cap numeric;
alter table ratios_snapshot add column if not exists week52_high numeric;
alter table ratios_snapshot add column if not exists week52_low numeric;
