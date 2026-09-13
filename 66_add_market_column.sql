-- 66_add_market_column.sql
-- -------------------------------------------------------------------
-- Phase 1 (US market expansion), Step 1: teach the database the
-- difference between an Indian stock/sector and a US stock/sector.
--
-- What this does:
--   1. Adds a `market` column to `assets` (default 'india') and to
--      `sectors` (default 'india'). Every row that already exists
--      gets 'india' automatically -- nothing about the current India
--      data changes or breaks.
--   2. Fixes the "uniqueness" rules (the database's own duplicate-
--      prevention checks) on both tables so they are now unique per
--      MARKET too, not just per name/ticker. Why this matters: the
--      US sector list (GICS sectors, e.g. "Information Technology",
--      "Real Estate", "Materials") can easily reuse a name that
--      already exists in India's own sector list. Without this fix,
--      trying to add a US "Information Technology" sector could
--      either fail outright or silently get merged into India's
--      existing "Information Technology" sector -- which would
--      completely break sector-relative scoring (US and Indian IT
--      stocks would get ranked against each other as if they were
--      one sector).
--
-- HOW TO RUN THIS (step by step):
--   1. Open your Supabase project in the browser.
--   2. Click "SQL Editor" in the left sidebar.
--   3. Click "New query".
--   4. Paste this entire file's contents into the editor.
--   5. Click "Run" (or press Ctrl+Enter).
--   6. You should see "Success. No rows returned." -- that's it,
--      nothing else to do here.
--
-- Safe to run more than once (every statement below checks first
-- before making a change, so re-running it does nothing the second
-- time).
-- -------------------------------------------------------------------

-- Step 1: add the `market` column to both tables, defaulting every
-- existing row (all of them India, today) to 'india'.
alter table assets  add column if not exists market text not null default 'india';
alter table sectors add column if not exists market text not null default 'india';

-- Step 2: replace the old "name must be unique" rule on `sectors`
-- with "name must be unique WITHIN a market". This is what lets a US
-- "Information Technology" sector coexist with an India one.
do $$
declare
    constraint_name text;
begin
    select con.conname into constraint_name
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    where rel.relname = 'sectors'
      and con.contype = 'u'
      and array_length(con.conkey, 1) = 1
      and con.conkey = (
          select array_agg(attnum) from pg_attribute
          where attrelid = rel.oid and attname = 'name'
      );

    if constraint_name is not null then
        execute format('alter table sectors drop constraint %I', constraint_name);
    end if;
end $$;

alter table sectors
    drop constraint if exists sectors_name_market_key;
alter table sectors
    add constraint sectors_name_market_key unique (name, market);

-- Step 3: same idea for `assets` -- "ticker + asset_type must be
-- unique" becomes "ticker + asset_type + market must be unique".
do $$
declare
    constraint_name text;
begin
    select con.conname into constraint_name
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    where rel.relname = 'assets'
      and con.contype = 'u'
      and array_length(con.conkey, 1) = 2
      and con.conkey = (
          select array_agg(attnum order by attnum) from pg_attribute
          where attrelid = rel.oid and attname in ('ticker', 'asset_type')
      );

    if constraint_name is not null then
        execute format('alter table assets drop constraint %I', constraint_name);
    end if;
end $$;

alter table assets
    drop constraint if exists assets_ticker_asset_type_market_key;
alter table assets
    add constraint assets_ticker_asset_type_market_key unique (ticker, asset_type, market);
