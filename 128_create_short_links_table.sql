-- 128_create_short_links_table.sql
-- -------------------------------------------------------------------
-- Powers the shareable short-link feature: sharing a stock, sector,
-- screener view, portfolio, or the whole site produces a short link
-- like trueresearch.app/s/aB3xQ9 that redirects to the real page.
--
-- Deliberately simple: no login required to create one (so sharing
-- works for logged-out visitors too), no way to read anyone else's
-- links back out, and codes are random/unguessable rather than
-- sequential.
--
-- HOW TO RUN THIS (same as before):
--   1. supabase.com/dashboard -> your project -> "SQL Editor" -> "New query"
--   2. Paste this whole file, click "Run"
--   3. If the "Potential issue detected" popup shows up, click "Run query"
--      -- same as every time before, nothing existing is being deleted.
-- -------------------------------------------------------------------

create table if not exists short_links (
  code text primary key,
  target_path text not null,       -- e.g. "/stocks/RELIANCE" -- relative, never a full URL, so it always points at whichever domain serves it
  kind text,                        -- 'stock' | 'sector' | 'screener' | 'portfolio' | 'site' -- for our own analytics later, not required for the redirect to work
  created_by uuid references auth.users(id) on delete set null,  -- null for a logged-out visitor's share
  click_count int not null default 0,
  created_at timestamptz not null default now()
);

alter table short_links enable row level security;

-- Anyone (including logged-out visitors) can create a short link --
-- sharing shouldn't require an account.
drop policy if exists "Anyone can create a short link" on short_links;
create policy "Anyone can create a short link" on short_links
  for insert with check (true);

-- Anyone can look a code up (that's the whole point -- the /s/[code]
-- redirect page needs to read it), but this table has nothing private
-- in it, so a public read is fine.
drop policy if exists "Anyone can look up a short link" on short_links;
create policy "Anyone can look up a short link" on short_links
  for select using (true);

-- Only used to bump click_count when a link is followed.
drop policy if exists "Anyone can update click count" on short_links;
create policy "Anyone can update click count" on short_links
  for update using (true) with check (true);

grant select, insert, update on table public.short_links to authenticated, anon;
