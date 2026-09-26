-- 148: let the Sector page read sector_overviews (admin-uploaded overview,
-- strengths, weaknesses, etc.). Writes stay server-side via the service key.
alter table sector_overviews enable row level security;
drop policy if exists "Sector overviews are public to read" on sector_overviews;
create policy "Sector overviews are public to read" on sector_overviews
  for select using (true);
grant select on sector_overviews to anon, authenticated;
