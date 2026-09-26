-- 127_fix_user_profiles_grants.sql
-- -------------------------------------------------------------------
-- Fixes "permission denied for table user_profiles" (403 in the
-- browser). The row-security POLICIES from 126_create_user_profiles_table.sql
-- were correct, but Supabase also requires a separate, more basic
-- GRANT before logged-in users can touch a new table at all -- that
-- step was missing. This adds it.
--
-- HOW TO RUN THIS (same as last time):
--   1. supabase.com/dashboard -> your project -> "SQL Editor" (left sidebar)
--   2. "New query"
--   3. Paste this whole file's contents
--   4. Click "Run"
--   If you see the same "Potential issue detected" popup as before,
--   click "Run query" -- same reason as before, nothing is being deleted.
-- -------------------------------------------------------------------

grant select, insert, update on table public.user_profiles to authenticated;
