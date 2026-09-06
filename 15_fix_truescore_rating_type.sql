-- ============================================================================
-- TrueResearch V2 — Phase B, Step 6, Script: fix truescore_rating column type
-- ============================================================================
-- The `scores` table's `truescore_rating` column was accidentally created as
-- `numeric` back when the schema was first built. TrueScore Rating is meant
-- to be a plain-English label (e.g. "Strong", "Above Average", "Average",
-- "Below Average", "Weak") -- a readable rating, not a raw number. This
-- changes the column to text so 14_score_current_stocks.py can save it.
-- Safe to run more than once. The `scores` table is currently empty of real
-- (non-legacy) rows, so no data is lost by this change.
-- ============================================================================

alter table scores alter column truescore_rating type text;
