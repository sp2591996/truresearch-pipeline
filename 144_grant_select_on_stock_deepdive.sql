-- 144_grant_select_on_stock_deepdive.sql
-------------------------------------------------------------------
-- Real bug found via the debug endpoint's exact error: "permission
-- denied for table stock_deepdive (Grant the required privileges to
-- the current role with: GRANT SELECT ON public.stock_deepdive TO
-- anon;)". Migration 137 created stock_deepdive's RLS "public can
-- read" policy, but an RLS policy only takes effect once the role
-- already has base table-level privilege -- Postgres checks both,
-- and this table never got the plain GRANT (every other table this
-- app reads already had it from much earlier setup; stock_deepdive
-- is the first brand-new table added since then). This is what was
-- causing "content confirmed in the database, but the Stock Page
-- still shows 'not filled in yet'" for every stock.
-------------------------------------------------------------------

grant select on public.stock_deepdive to anon, authenticated;
