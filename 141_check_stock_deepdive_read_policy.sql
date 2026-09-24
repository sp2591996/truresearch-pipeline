-- 141_check_stock_deepdive_read_policy.sql
-------------------------------------------------------------------
-- Diagnostic for "RELIANCE has content in stock_deepdive (confirmed
-- via the admin download) but the Stock Page still shows 'not filled
-- in yet'". The Stock Page reads with the anon/public key, subject
-- to RLS -- every other admin-uploaded table this page reads was
-- already being read this way, but stock_deepdive is brand new, so
-- this checks whether its "public can read" policy actually exists
-- and is enabled, and separately proves the row is really there.
-------------------------------------------------------------------

-- 1. Is RLS on, and does the public-read policy exist?
select relrowsecurity as rls_enabled, relforcerowsecurity as rls_forced
from pg_class where relname = 'stock_deepdive';

select policyname, cmd, roles, qual
from pg_policies
where tablename = 'stock_deepdive';

-- 2. Does RELIANCE's row actually exist, and is what_does_company_do filled?
select sd.asset_id, a.ticker, left(sd.what_does_company_do, 60) as preview
from stock_deepdive sd
join assets a on a.asset_id = sd.asset_id
where a.ticker = 'RELIANCE' and a.market = 'india';
