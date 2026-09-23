-- 130_add_wallet_created_at.sql
-------------------------------------------------------------------
-- P6 rebuild (Ideation/P6/PRD - TrueResearch Build.pdf, Homepage
-- Section 5 Part 1: "Your Investments" summary should show "lifetime
-- CAGR"): there was no timestamp anywhere recording when a
-- virtual_wallets row (a visitor's virtual portfolio) was first
-- created, so there was no honest way to annualize a return into a
-- CAGR figure -- the app would have had to guess an elapsed time,
-- producing a fabricated-looking number. This adds that one column.
--
-- Important limitation, flagged upfront (Avdhoot was told this before
-- asking for the build): this only gives a TRUE start date for
-- wallets created AFTER this migration runs. Every wallet that
-- already exists today has no recorded creation date, so this
-- backfills `created_at` to each existing wallet's EARLIEST portfolio
-- snapshot date (virtual_portfolio_snapshots) as the closest honest
-- proxy available -- if a wallet has no snapshots yet either, it
-- backfills to now() (today), which means CAGR for that wallet will
-- read as "since today" until it has real history. The app is
-- expected to label the figure accordingly (e.g. "CAGR since <date>"
-- rather than an unqualified "Lifetime CAGR") so this approximation
-- is never presented as more precise than it is.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

alter table public.virtual_wallets
  add column if not exists created_at timestamptz;

-- Backfill: earliest snapshot date per wallet, if one exists.
update public.virtual_wallets w
set created_at = earliest.first_snapshot
from (
  select user_id, min(snapshot_date)::timestamptz as first_snapshot
  from public.virtual_portfolio_snapshots
  group by user_id
) earliest
where earliest.user_id = w.user_id
  and w.created_at is null;

-- Any wallet still without a created_at (no snapshots yet) falls back to now().
update public.virtual_wallets
set created_at = now()
where created_at is null;

alter table public.virtual_wallets
  alter column created_at set default now(),
  alter column created_at set not null;

comment on column public.virtual_wallets.created_at is
  'When this virtual portfolio was first set up. For wallets that existed before this column was added, this is a BACKFILLED approximation (earliest snapshot date, or now() if no snapshots existed yet) -- not a guaranteed-exact creation time. New wallets get a real, exact timestamp going forward.';
