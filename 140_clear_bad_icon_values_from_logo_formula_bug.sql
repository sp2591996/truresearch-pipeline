-- 140_clear_bad_icon_values_from_logo_formula_bug.sql
-------------------------------------------------------------------
-- Cleanup for a real bug: the Stock Detail Upload route's Excel cell
-- reader didn't know how to handle a FORMULA cell (e.g. a
-- "=IFERROR(IMAGE(...),"")" logo-fetch formula in the Company Logo
-- column) -- it stringified the cell's JS object instead, which
-- produced the literal text "[object Object]" and saved that into
-- assets.icon for every row that had a formula there. The upload
-- code is now fixed (see app/api/admin/stock-deepdive-upload/
-- route.ts's cellText()) to skip formula cells instead of mis-
-- reading them. This migration only cleans up the bad values that
-- already got saved before that fix -- run it once, it's safe to
-- run again (no-op the second time).
-------------------------------------------------------------------

update assets
set icon = null
where icon = '[object Object]';
