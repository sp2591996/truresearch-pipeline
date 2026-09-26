-- Diagnostic: sector_id 8 exists (confirmed by 145), yet /sectors/8
-- 404s on the live site -- the site's notFound() only fires when the
-- anon-key query for that row comes back empty, which is exactly what
-- happened with stock_deepdive before migration 144 (RLS policy
-- existed but the base-table GRANT SELECT to anon was missing). Check
-- the same two things for `sectors`.

-- 1. Is RLS even on for this table?
select relrowsecurity, relforcerowsecurity
from pg_class
where oid = 'public.sectors'::regclass;

-- 2. What policies exist, and do they cover anon reads?
select policyname, cmd, roles, qual
from pg_policies
where schemaname = 'public' and tablename = 'sectors';

-- 3. Does anon actually have GRANT SELECT on the base table?
select grantee, privilege_type
from information_schema.role_table_grants
where table_schema = 'public' and table_name = 'sectors';
