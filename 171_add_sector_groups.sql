-- =====================================================================
-- 171_add_sector_groups.sql
--
-- Adds a "Sector Group" layer ON TOP OF the existing sectors table,
-- purely for navigation/display (fewer buckets to browse in the
-- Screener filter and the homepage/sector browse page). It does NOT
-- move, merge or delete any existing sector -- every sector keeps its
-- own sector_id, its own index, its own KPIs, its own score history
-- exactly as today. A sector just gets an extra tag saying which
-- group it belongs to.
--
-- Safe, additive, fully reversible (drop the column + table to undo).
-- =====================================================================

-- 1) The groups table itself
create table if not exists sector_groups (
  group_id serial primary key,
  name text not null,
  market text not null,
  display_order int,
  created_at timestamptz default now()
);

comment on table sector_groups is
  'Navigation-only grouping of sectors into broader buckets (e.g. "Industrials, Construction & Realty"). Does not affect how individual sectors are scored or indexed.';

-- 2) Link sectors -> sector_groups
alter table sectors add column if not exists sector_group_id int references sector_groups(group_id);

-- 3) Row-level security + grants, matching the pattern used for every
--    other public-read reference table in this project (see
--    148_sector_overviews_public_read.sql)
alter table sector_groups enable row level security;
drop policy if exists "Sector groups are public to read" on sector_groups;
create policy "Sector groups are public to read" on sector_groups
  for select using (true);
grant select on sector_groups to anon, authenticated;

-- =====================================================================
-- 4) Seed the groups
-- =====================================================================

-- ---- INDIA: 19 sectors -> 7 groups ----
insert into sector_groups (name, market, display_order) values
  ('Financial Services', 'india', 1),
  ('Industrials, Construction & Realty', 'india', 2),
  ('Consumer', 'india', 3),
  ('Automobile & Auto Components', 'india', 4),
  ('Healthcare & Chemicals', 'india', 5),
  ('Energy, Power & Metals', 'india', 6),
  ('Technology, Media & Telecom', 'india', 7);

-- ---- USA: 11 sectors -> 9 groups (only the 3 smallest get merged;
-- the rest are already large, standard GICS sectors on their own) ----
insert into sector_groups (name, market, display_order) values
  ('Energy, Utilities & Materials', 'usa', 1),
  ('Communication Services', 'usa', 2),
  ('Consumer Staples', 'usa', 3),
  ('Real Estate', 'usa', 4),
  ('Health Care', 'usa', 5),
  ('Information Technology', 'usa', 6),
  ('Consumer Discretionary', 'usa', 7),
  ('Financials', 'usa', 8),
  ('Industrials', 'usa', 9);

-- =====================================================================
-- 5) Map every existing sector to its group, by name
-- =====================================================================

-- India
update sectors set sector_group_id = (select group_id from sector_groups where name = 'Financial Services' and market = 'india')
  where name = 'Financial Services' and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Industrials, Construction & Realty' and market = 'india')
  where name in ('Capital Goods', 'Construction', 'Construction Materials', 'Transportation & Logistics', 'Realty') and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Consumer' and market = 'india')
  where name in ('Consumer Services', 'Consumer Durables', 'Fast Moving Consumer Goods', 'Textiles') and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Automobile & Auto Components' and market = 'india')
  where name = 'Automobile and Auto Components' and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Healthcare & Chemicals' and market = 'india')
  where name in ('Healthcare', 'Chemicals') and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Energy, Power & Metals' and market = 'india')
  where name in ('Oil Gas & Consumable Fuels', 'Power', 'Metals & Mining') and market = 'india';

update sectors set sector_group_id = (select group_id from sector_groups where name = 'Technology, Media & Telecom' and market = 'india')
  where name in ('Information Technology', 'Media Entertainment & Publication', 'Telecommunication') and market = 'india';

-- USA
update sectors set sector_group_id = (select group_id from sector_groups where name = 'Energy, Utilities & Materials' and market = 'usa')
  where name in ('Energy', 'Utilities', 'Materials') and market = 'usa';

update sectors set sector_group_id = (select group_id from sector_groups where name = sectors.name and market = 'usa')
  where market = 'usa' and name in ('Communication Services', 'Consumer Staples', 'Real Estate', 'Health Care', 'Information Technology', 'Consumer Discretionary', 'Financials', 'Industrials');

-- =====================================================================
-- 6) VERIFY -- should return ZERO rows (every sector has a group)
-- =====================================================================
select sector_id, name, market from sectors where sector_group_id is null;

-- Sanity check -- group -> sector -> stock-count rollup
select
  g.name as group_name, g.market,
  s.name as sector_name,
  (select count(*) from assets a where a.sector_id = s.sector_id) as stock_count
from sector_groups g
join sectors s on s.sector_group_id = g.group_id
order by g.market, g.display_order, stock_count desc;
