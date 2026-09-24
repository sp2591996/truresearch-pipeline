-- 143_check_stock_deepdive_policies.sql
-- Split out from 141, same reason as 142.
select policyname, cmd, roles, qual
from pg_policies
where tablename = 'stock_deepdive';
