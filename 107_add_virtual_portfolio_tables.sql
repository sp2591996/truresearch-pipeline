-- 107_add_virtual_portfolio_tables.sql
-------------------------------------------------------------------
-- Gamified virtual investing (next-phase item 3, Avdhoot's 5-point
-- list). Four new tables, all keyed to a real logged-in user
-- (auth.users, wired up by the Login feature / lib/AuthContext.tsx)
-- instead of being open/public like every other table in this
-- project -- this is the first feature where each visitor's data is
-- genuinely private to them, so RLS here is "only the owning user,
-- full stop" rather than the usual "public read, admin-only write"
-- pattern every other table uses (research_reports, ipo_assessments,
-- etc.).
--
-- Single-currency design (Avdhoot's call): everything is tracked in
-- one INR wallet. Buying a USD-priced US stock converts INR -> USD at
-- that moment's live rate (the `USDINR` row already refreshed every 5
-- minutes by fx-refresh.yml -- see 55_add_fx_assets.py); selling
-- converts back to INR at whatever the rate is AT THE TIME OF SALE,
-- same real currency risk a real India-based investor buying US
-- stocks would have. Gold/silver/crude/FX all buy and sell the exact
-- same way as a stock -- they're already just rows in `assets` with
-- their own `live_prices` row, so no separate mechanism is needed for
-- them at all.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

-- 1. One wallet per user: their chosen starting play-money amount,
-- and their current spendable cash balance. `starting_cash_inr` is
-- kept separately (never changed after creation) purely so a "reset
-- my portfolio" action always knows what amount to reset back to.
create table if not exists public.virtual_wallets (
  user_id uuid primary key references auth.users(id) on delete cascade
);

alter table public.virtual_wallets
  add column if not exists starting_cash_inr numeric not null default 100000,
  add column if not exists cash_balance_inr numeric not null default 100000,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

comment on table public.virtual_wallets is
  'One row per logged-in user playing the virtual investing game. starting_cash_inr is fixed at creation/reset time; cash_balance_inr moves with every buy/sell.';

-- 2. What they currently own. One row per (user, asset) -- buying more
-- of something already held updates units + recomputes avg_cost_inr
-- (weighted average) rather than adding a second row. A row with
-- units = 0 after a full sell is deleted, not kept at zero, so
-- "what do I currently hold" is always just "every row in this table
-- for me".
create table if not exists public.virtual_holdings (
  id bigint generated always as identity primary key
);

alter table public.virtual_holdings
  add column if not exists user_id uuid not null references auth.users(id) on delete cascade,
  add column if not exists asset_id integer not null references public.assets(asset_id) on delete cascade,
  add column if not exists units numeric not null,
  add column if not exists avg_cost_inr numeric not null,
  add column if not exists updated_at timestamptz not null default now();

alter table public.virtual_holdings drop constraint if exists virtual_holdings_user_asset_unique;
alter table public.virtual_holdings add constraint virtual_holdings_user_asset_unique unique (user_id, asset_id);

comment on table public.virtual_holdings is
  'Current virtual positions -- one row per user per asset they hold. avg_cost_inr is the weighted average INR cost per unit, used to show unrealized gain/loss while holding.';

-- 3. The full buy/sell history -- this is the "transaction statement".
-- Never updated or deleted (a sell is its own new row, not an edit to
-- the buy row), so this table alone is a complete, permanent record.
create table if not exists public.virtual_transactions (
  id bigint generated always as identity primary key
);

alter table public.virtual_transactions
  add column if not exists user_id uuid not null references auth.users(id) on delete cascade,
  add column if not exists asset_id integer not null references public.assets(asset_id) on delete cascade,
  add column if not exists txn_type text not null,
  add column if not exists units numeric not null,
  add column if not exists price_per_unit numeric not null,
  add column if not exists price_currency text not null default 'INR',
  add column if not exists fx_rate_used numeric,
  add column if not exists amount_inr numeric not null,
  add column if not exists wallet_balance_after_inr numeric not null,
  add column if not exists executed_at timestamptz not null default now();

alter table public.virtual_transactions drop constraint if exists virtual_transactions_txn_type_check;
alter table public.virtual_transactions add constraint virtual_transactions_txn_type_check check (txn_type in ('buy', 'sell'));
alter table public.virtual_transactions drop constraint if exists virtual_transactions_price_currency_check;
alter table public.virtual_transactions add constraint virtual_transactions_price_currency_check check (price_currency in ('INR', 'USD'));

comment on table public.virtual_transactions is
  'Permanent buy/sell ledger for the virtual investing game -- one row per trade, never edited or deleted. fx_rate_used is null for INR-priced assets, set to the USDINR rate at execution time for USD-priced ones.';

-- 4. One portfolio-value snapshot per user per day, so "how has my
-- portfolio changed today/this week/overall" is a fast lookup instead
-- of recomputing every holding's live value on every page load. A
-- daily job (to be scheduled, same pattern as every other *-refresh.yml
-- job in this project) will populate this going forward.
create table if not exists public.virtual_portfolio_snapshots (
  id bigint generated always as identity primary key
);

alter table public.virtual_portfolio_snapshots
  add column if not exists user_id uuid not null references auth.users(id) on delete cascade,
  add column if not exists snapshot_date date not null,
  add column if not exists cash_balance_inr numeric not null,
  add column if not exists holdings_value_inr numeric not null,
  add column if not exists total_value_inr numeric not null;

alter table public.virtual_portfolio_snapshots drop constraint if exists virtual_portfolio_snapshots_user_date_unique;
alter table public.virtual_portfolio_snapshots add constraint virtual_portfolio_snapshots_user_date_unique unique (user_id, snapshot_date);

comment on table public.virtual_portfolio_snapshots is
  'One row per user per day: their total virtual portfolio value that day. Powers daily/weekly/overall change without live recomputation on every page load.';

-------------------------------------------------------------------
-- Row Level Security -- deliberately different from every other
-- table in this project. Everywhere else, RLS grants PUBLIC read
-- access (anyone can see stock scores, research reports, etc.) and
-- only the secret key can write. Here, a user's virtual-investing
-- data is theirs alone -- nobody else, not even another logged-in
-- user, can read or write it. The frontend's browser client (using
-- the publishable/anon key) can still read/write because these
-- policies check auth.uid() = user_id, and Supabase automatically
-- knows who's logged in from their session -- no extra code needed
-- beyond what lib/AuthContext.tsx already sets up.
-------------------------------------------------------------------

alter table public.virtual_wallets enable row level security;
alter table public.virtual_holdings enable row level security;
alter table public.virtual_transactions enable row level security;
alter table public.virtual_portfolio_snapshots enable row level security;

drop policy if exists "Users manage their own wallet" on public.virtual_wallets;
create policy "Users manage their own wallet" on public.virtual_wallets
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage their own holdings" on public.virtual_holdings;
create policy "Users manage their own holdings" on public.virtual_holdings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage their own transactions" on public.virtual_transactions;
create policy "Users manage their own transactions" on public.virtual_transactions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users manage their own snapshots" on public.virtual_portfolio_snapshots;
create policy "Users manage their own snapshots" on public.virtual_portfolio_snapshots
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

grant select, insert, update, delete on public.virtual_wallets to authenticated;
grant select, insert, update, delete on public.virtual_holdings to authenticated;
grant select, insert, update, delete on public.virtual_transactions to authenticated;
grant select, insert, update, delete on public.virtual_portfolio_snapshots to authenticated;
