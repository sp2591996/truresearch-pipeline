# Session Log — Phase C: Frontend Permissions & Live Price Gap

**Date:** 2026-09-06
**Project:** TrueResearch (Stock App 2.0) — Next.js frontend + Supabase (Postgres) backend + Python data pipeline
**For:** Avdhoot — paste this into a new chat so Claude has full context if the conversation resets.

---

## 1. Problem we started with

The frontend (`trueresearch-frontend`, running locally at `http://localhost:3000`) was showing **no data at all** — pages like `/screener` appeared blank. This is a classic Postgres/Supabase issue: Row Level Security (RLS) was turned on for every table back in Session 4, but no read rules had ever been added for the `anon` role (the identity the frontend's public API key connects as). Even with the correct API keys, every query was silently returning **zero rows** (not an error).

## 2. Root cause — two separate permission gates

Postgres/Supabase has **two independent gates** a query must pass, and both were missing for `anon`:

1. **Row Level Security (RLS) policies** — "which rows is this role allowed to see"
2. **Table-level GRANTs** — "can this role touch this table at all" (a completely separate layer from RLS)

Only `service_role` (used by the Python pipeline) had ever been granted access — because when Session 4 set this up, the frontend didn't exist yet.

## 3. Fix applied

Two SQL scripts (already written, in `TrueResearch Code/`) were run in the Supabase SQL Editor:

- **`23_add_public_read_policies.sql`** — adds `CREATE POLICY "Public read access" ... FOR SELECT USING (true)` for the `anon` and `authenticated` roles, on: `assets, sectors, scores, score_components, score_backtest_results, score_performance_tracking, ratios_snapshot, fundamentals, prices_daily, live_prices, peers, shareholding_pattern`.
- **`24_grant_anon_select.sql`** — adds the matching `GRANT SELECT ... TO anon, authenticated` on the same table list, plus `GRANT USAGE ON SCHEMA public`.

Both ran successfully ("Success. No rows returned" is expected for these — they're `DO $$ ... $$` blocks, not `SELECT`s, so no result table is expected).

**Result confirmed working:** verified directly by opening the frontend — the Screener page now loads and shows all 500 Nifty 500 stocks with tickers, sectors, scores, P/E, and market cap.

**Note:** `ingestion_runs` was never included in either script's table list — that's intentional, it's an internal pipeline log table not meant to be frontend-readable, not an oversight.

## 4. Second issue found — live prices missing for most stocks

After the permissions fix, most rows on the Screener showed **`—` for price** and a **"Markets closed"** pill instead of a real day-change percentage (291 of 500 stocks affected). Only stocks that already had a row in the `live_prices` table showed real numbers.

### Root cause
When `19_add_nifty500_expansion.py` added 300 new stocks (expanding from the original ~200 to the full Nifty 500), it **deliberately did not fetch any price data** for them — that was explicitly left as a separate, later step ("Step 3 onward") to be run manually. That step was never run.

There are two separate price-related scripts:
- **`20_backfill_new_stocks_price_history.py`** — one-time 10-year historical backfill (for chart data in `prices_daily`), skips any stock that already has history.
- **`05_daily_price_refresh.py`** — the fast/frequent job that fetches **today's live price** into `live_prices` (and the latest daily bar into `prices_daily`). This script **skips itself entirely outside NSE market hours** (Mon–Fri, 9:15am–3:30pm IST) unless you pass `--force`. Since today is Sunday, it would normally do nothing.

### What we ran / found
- Ran `20_backfill_new_stocks_price_history.py` first → **result: all 500 stocks already had historical price data.** Nothing needed there — that part was already done in an earlier session.
- This means the *only* gap is `live_prices` (today's snapshot), not the historical chart data.

### Command in progress (last step)
```
venv\Scripts\python.exe 05_daily_price_refresh.py --force
```
Run from a terminal opened inside `TrueResearch Code` (via VS Code's integrated PowerShell terminal). This fetches the current price for every one of the 500 active equities and upserts into `live_prices` + `prices_daily`, ignoring the market-hours check because of `--force`.

**Status when this log was written: this command had just been kicked off — waiting on its output/completion.**

## 5. Useful environment notes for next time

- Project folder (on Avdhoot's Windows laptop): `C:\Users\Komal\Desktop\Stock App 2.0\`
  - `TrueResearch Code\` — Python data pipeline + SQL scripts (numbered `01_...` through `24_...`)
  - `trueresearch-frontend\` — Next.js app (runs via `npm run dev` on `localhost:3000`)
- The project has a Python virtual environment at `TrueResearch Code\venv\`. **PowerShell blocks `.ps1` activation scripts by default** (`running scripts is disabled on this system`) — don't fight this; skip activation and just call the interpreter directly:
  ```
  venv\Scripts\python.exe <script_name>.py
  ```
- Frontend Supabase client only ever uses the **publishable/anon key** (safe for browsers), stored in `trueresearch-frontend\.env.local`. The pipeline scripts use the more powerful **service_role key** (`.env` in `TrueResearch Code\`), which never reaches the browser.
- Data-fetching for pages like `/screener` happens **server-side** (Next.js Server Component, no `"use client"`), so Supabase calls never show up in the browser's Network tab — that's expected, not a bug.

## 6. Next steps once `--force` finishes

1. Confirm the script's final summary line (e.g. `Done. 500/500 ok.`), and note any `Failed:` tickers.
2. Refresh the Screener page — prices/1-day-change should now show for all (or nearly all) 500 stocks instead of "Markets closed".
3. Longer-term: this `--force` fix is a one-time manual catch-up. The recurring job (`.github/workflows/daily-prices.yml`, if that's how it's scheduled) should keep `live_prices` fresh going forward automatically during market hours — worth double-checking that workflow is actually enabled/running on a schedule so this gap doesn't recur for future newly-added stocks.
