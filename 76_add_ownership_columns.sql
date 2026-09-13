-- 76_add_ownership_columns.sql
-- -------------------------------------------------------------------
-- Adds two columns to `ratios_snapshot` for the USA "who owns this
-- stock" stat card (insider % + institutional %) -- the closest real
-- equivalent to India's Promoter/FII/DII/Public shareholding chart,
-- given Yahoo Finance only exposes a current snapshot, not India's
-- quarterly filing history (see chat discussion, Session after the
-- US daily price refresh work).
--
-- Nullable, and simply left NULL for every existing India row --
-- India keeps using its own `shareholding_pattern` table/chart
-- unchanged; these two new columns are USA-only in practice, just
-- stored on the same per-stock snapshot table that already gets
-- refreshed weekly (06_weekly_fundamentals_refresh.py for India,
-- 69_backfill_us_fundamentals.py for USA) rather than a brand new
-- table for two numbers.
--
-- Run manually (once) in the Supabase SQL editor.
-- -------------------------------------------------------------------

alter table ratios_snapshot
  add column if not exists insider_ownership_pct numeric,
  add column if not exists institutional_ownership_pct numeric;

comment on column ratios_snapshot.insider_ownership_pct is
  'USA only (for now): % of shares held by company insiders, from yfinance heldPercentInsiders. Null for India rows -- India uses the shareholding_pattern table/chart instead.';
comment on column ratios_snapshot.institutional_ownership_pct is
  'USA only (for now): % of shares held by institutions, from yfinance heldPercentInstitutions. Null for India rows -- India uses the shareholding_pattern table/chart instead.';
