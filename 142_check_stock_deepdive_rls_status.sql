-- 142_check_stock_deepdive_rls_status.sql
-- Split out from 141 (Supabase's SQL Editor only shows the last
-- statement's result when several run together) -- this is just the
-- RLS/policy half of that check.
select relrowsecurity as rls_enabled, relforcerowsecurity as rls_forced
from pg_class where relname = 'stock_deepdive';
