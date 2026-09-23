-- 129_create_watchlist_table.sql
-------------------------------------------------------------------
-- P6 rebuild (Ideation/P6/PRD - TrueResearch Build.pdf): the Watchlist
-- feature the PRD references in several places (homepage Section 1's
-- bookmark-icon shortcut, homepage Section 5 Part 2 "Your Watchlist",
-- the My Portfolio nav super menu's "My Watchlist" item, and the
-- standalone My Watchlist page) didn't exist anywhere on the site
-- before this migration -- the stock page's "Watchlist" button always
-- just linked to /login and did nothing else. This adds the one table
-- needed to make it real.
--
-- Same private-per-user RLS pattern as 107_add_virtual_portfolio_tables.sql
-- (virtual_wallets etc.) -- a user's watchlist is theirs alone, not
-- public like most other tables in this project.
--
-- Run this in Supabase's SQL Editor (left sidebar -> SQL Editor -> New
-- query -> paste this whole file -> Run). Safe to re-run.
-------------------------------------------------------------------

create table if not exists public.watchlist_items (
  id bigint generated always as identity primary key
);

alter table public.watchlist_items
  add column if not exists user_id uuid not null references auth.users(id) on delete cascade,
  add column if not exists asset_id integer not null references public.assets(asset_id) on delete cascade,
  add column if not exists created_at timestamptz not null default now();

alter table public.watchlist_items drop constraint if exists watchlist_items_user_asset_unique;
alter table public.watchlist_items add constraint watchlist_items_user_asset_unique unique (user_id, asset_id);

comment on table public.watchlist_items is
  'One row per (user, asset) a visitor has starred to their watchlist. No units/cost basis -- unlike virtual_holdings, this is a plain follow-list, not a simulated position.';

alter table public.watchlist_items enable row level security;

drop policy if exists "Users manage their own watchlist" on public.watchlist_items;
create policy "Users manage their own watchlist" on public.watchlist_items
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

grant select, insert, update, delete on public.watchlist_items to authenticated;

-- Lets Postgres pick a fast index-only plan for "how many/which people have X on their watchlist" reads, and for a single user's own list.
create index if not exists watchlist_items_asset_id_idx on public.watchlist_items (asset_id);
create index if not exists watchlist_items_user_id_idx on public.watchlist_items (user_id);
