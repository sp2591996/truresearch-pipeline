-- 126_create_user_profiles_table.sql
-- -------------------------------------------------------------------
-- Powers M10a (post-login profile completion) and E4 (Risk-Profiling
-- Questionnaire -> Suggested Allocation), per PRD.md's Draft 5
-- decision that M10a reuses E4 rather than a second separate flow.
--
-- HOW TO RUN THIS (one-time, takes 2 minutes):
--   1. Go to https://supabase.com/dashboard and open the TrueResearch project.
--   2. In the left sidebar, click "SQL Editor".
--   3. Click "New query".
--   4. Paste this whole file's contents into the box.
--   5. Click "Run" (bottom right).
--   You should see "Success. No rows returned." -- that means it worked.
-- -------------------------------------------------------------------

create table if not exists user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  phone text,
  risk_answers jsonb,
  risk_score int,
  risk_profile text, -- 'Conservative' | 'Moderate' | 'Aggressive'
  suggested_allocation jsonb, -- e.g. {"equity":60,"debt":30,"gold":10}
  profile_completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table user_profiles enable row level security;

drop policy if exists "Users can view own profile" on user_profiles;
create policy "Users can view own profile" on user_profiles
  for select using (auth.uid() = id);

drop policy if exists "Users can insert own profile" on user_profiles;
create policy "Users can insert own profile" on user_profiles
  for insert with check (auth.uid() = id);

drop policy if exists "Users can update own profile" on user_profiles;
create policy "Users can update own profile" on user_profiles
  for update using (auth.uid() = id);
