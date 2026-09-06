-- ============================================================================
-- TrueResearch V2 — Phase B, Script 2: Grant permissions
-- ============================================================================
-- What this does: our tables were deliberately created "closed" (no API
-- role could touch them yet, per the safe default we chose when the
-- project was created). This script explicitly opens them up to
-- `service_role` only -- the powerful, secret-key-only role our Python
-- pipeline scripts use. It does NOT open anything to `anon` or
-- `authenticated` (the roles a public website visitor's browser would
-- use) -- that stays locked down until we deliberately write access
-- policies later, once real user-facing features need it.
-- Safe to run more than once.
-- ============================================================================

grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

-- Make sure this also applies automatically to any table we add later,
-- so we don't have to remember to re-run this every time.
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
