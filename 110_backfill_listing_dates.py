"""
110_backfill_listing_dates.py
-------------------------------------------------------------------
One-time backfill of `assets.listed_date` for every active equity
(India + USA), needed for TrueScore Formula v2 (PRD.md M3) -- Legacy
Score's interim definition is how long a company has been listed,
percentile-ranked within its own market. That needs a real
`listed_date` on every stock first; the column has existed in the
schema since the start (Database_Schema.md), but nothing has ever
actually written to it until now.

Source: Yahoo Finance's own `firstTradeDateEpochUtc` field, via the
new get_listing_date() in market_data_provider.py (the only file
allowed to call yfinance directly -- see that file's own header for
why). Not every ticker has this field populated on Yahoo's side
(mostly obscure/thinly-covered small-caps) -- those are reported as
failures at the end rather than silently left blank, so it's a known,
visible gap rather than a mystery later.

Safe to re-run (upserts the same way every other backfill in this
project does -- an update on `asset_id`, not an insert, so running
this twice just re-checks/re-fills, never duplicates).

Run with:
    python 110_backfill_listing_dates.py
-------------------------------------------------------------------
"""
import time

from db_client import get_client
from market_data_provider import get_listing_date


# BUG FIX (Avdhoot: "why only 1000 taken" -- the first run stopped at
# 1000 stocks): the exact same Supabase/PostgREST 1000-row-per-request
# cap documented all over PROJECT_STATE.md and already fixed in every
# other affected script (05/06/08/etc. on the pipeline side, the
# Screener on the website side) -- a plain .select()...execute() with
# no .range() silently truncates at 1000 rows no matter how many
# actually match. This project has ~3,000 active equities combined
# (India + USA), so the old version of this script could only ever see
# the first 1,000. Paginating with .range() in 1000-row pages, same
# fetch_all_rows() pattern used everywhere else, fixes it.
def fetch_all_rows(build):
    PAGE = 1000
    all_rows = []
    start = 0
    while True:
        res = build(start, start + PAGE - 1)
        page = res.data or []
        all_rows.extend(page)
        if len(page) < PAGE:
            break
        start += PAGE
    return all_rows


def main():
    supabase = get_client()

    assets = fetch_all_rows(
        lambda start, end: supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol, market, listed_date")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .range(start, end)
        .execute()
    )
    # Skip anything that already has a listed_date -- makes a re-run
    # after a partial/interrupted first pass fast (only chases what's
    # still missing) instead of re-fetching all ~3,000 stocks again.
    todo = [a for a in assets if not a.get("listed_date")]
    print(f"{len(assets)} active equities total, {len(todo)} still missing listed_date. Fetching...")

    ok_count = 0
    failed = []
    for i, a in enumerate(todo, 1):
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            failed.append(ticker)
            continue
        try:
            listed_date = get_listing_date(yf_symbol)
            if listed_date is not None:
                supabase.table("assets").update({"listed_date": listed_date.isoformat()}).eq("asset_id", a["asset_id"]).execute()
                ok_count += 1
            else:
                failed.append(ticker)
        except Exception as e:
            # BUG FIX: a single bad response (a dropped connection, a rate
            # limit, one weird stock) used to take down the ENTIRE run --
            # after processing hundreds of stocks, one failure meant
            # starting over. Every other bulk script in this project
            # already isolates per-stock failures the same way (see
            # 08_backfill_price_history.py); this one now does too.
            print(f"  ! {ticker}: {e}")
            failed.append(ticker)

        if i % 25 == 0:
            print(f"  [{i}/{len(todo)}] done...")
        time.sleep(0.3)  # same gentle pacing as 08_backfill_price_history.py

    print(f"\nDone. {ok_count}/{len(todo)} stocks backfilled this run.")
    if failed:
        print(f"Yahoo Finance had no listing date for {len(failed)} tickers: {failed}")
        print("These will need a manual/alternate source later, or Legacy Score will")
        print("treat them as 'not enough data yet' rather than guessing (same graceful-")
        print("degradation rule as every other TrueScore component, per PRD.md M6b).")


if __name__ == "__main__":
    main()
