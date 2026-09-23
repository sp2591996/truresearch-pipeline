"""
104_weekly_universe_sync_india.py
-------------------------------------------------------------------
Weekly job (Avdhoot: "automate inclusion / exclusion of any indian /
US stock in the current set"): keeps your India stock universe
current, automatically, every week -- so a newly listed company shows
up on the site without anyone having to remember to add it, and a
delisted/removed one stops showing up too.

CHANGED (Avdhoot, P6, 2026-09-24: "Decrease the scope of Indian Stocks
to only NIFTY 500 ... This will free up supabase space, focus more on
core stocks, and also help us build this MVP very well"): this used to
source from NSE's FULL mainboard equity list (~2500 stocks). Since a
one-time cleanup (131_narrow_india_universe_to_nifty500.sql) removes
everything outside the Nifty 500, this script now sources from the
Nifty 500's own official constituent list instead -- otherwise the
very next weekly run would just re-add every stock that migration
removed. The mainboard-vs-Nifty500 mechanics below are otherwise
unchanged: same "fetch the live list, diff against the database, add
what's new, deactivate what dropped off" shape.

What it does, each run:
  1. Fetches NSE's official, current Nifty 500 constituent list (same
     warmed-up-session approach 85_fetch_nse_equity_list.py used for
     the old full mainboard list).
  2. Compares it against every India equity currently in `assets`:
       - On the Nifty 500 list but NOT in the database  -> added
         (is_active=True, sector_id left NULL on purpose -- the very
         next scheduled job, Weekly Universe Sync's sibling step
         87_assign_sectors_from_yfinance.py, fills that in for exactly
         these new rows).
       - In the database as active but NOT on the current Nifty 500
         list anymore -> marked is_active=False. This now covers BOTH
         a genuine delisting AND an index reconstitution drop (a stock
         that's still trading on NSE but fell out of the Nifty 500) --
         both cases mean "no longer in scope for this MVP", which is
         exactly what this change was for.
       - On both -> left alone entirely (existing scored stocks are
         never touched by this script).
  3. Logs itself to `ingestion_runs` (run_type='universe_sync_india')
     so it shows up on the admin Pipeline Runs page like every other
     job. Reusing that table's existing shape: `ok_count` = stocks
     newly added this run, `failed_symbols`/`failed_count` = stocks
     newly deactivated this run (not literal failures -- see this
     job's "note" in lib/pipelineJobs.ts on the frontend, which
     explains this reuse so it doesn't read as an error).

Meant to run WEEKLY, the day before your existing weekly fundamentals/
TrueScore/shareholding jobs (see PROJECT_STATE.md / cron-job.org setup
notes) -- so any stock added this run has a full week's head start to
get its sector + price history + fundamentals + score filled in by the
scripts that already run after it:
    104 (this script) -> 87_assign_sectors_from_yfinance.py
                       -> 20_backfill_new_stocks_price_history.py
                       -> (existing weekly fundamentals/TrueScore/shareholding jobs)

Run manually:
    venv\\Scripts\\python.exe 104_weekly_universe_sync_india.py
-------------------------------------------------------------------
"""
import requests

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "india"
NSE_HOME = "https://www.nseindia.com"
NIFTY500_CSV_CANDIDATES = [
    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://www1.nseindia.com/content/indices/ind_nifty500list.csv",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/vnd.ms-excel,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/securities-available-for-trading",
}


def fetch_nifty500_list() -> list:
    """Returns [{'ticker':.., 'name':.., 'isin':.., 'yfinance_symbol':..}, ...]
    for every current Nifty 500 constituent. Raises on failure --
    deliberately does NOT fall back to "assume nothing changed", since
    a bad fetch could otherwise deactivate your entire universe.

    NSE's own ind_nifty500list.csv column names have varied over time
    (e.g. "Symbol" vs "SYMBOL", "Company Name" vs "NAME OF COMPANY"),
    unlike the old full-mainboard EQUITY_L.csv this replaced -- so
    column lookups here are case/spacing-insensitive instead of exact,
    matched against the *_KEYS lists below."""
    import csv
    import io
    import re

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    SYMBOL_KEYS = {"symbol"}
    NAME_KEYS = {"companyname", "nameofcompany"}
    ISIN_KEYS = {"isincode", "isinnumber", "isin"}

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(NSE_HOME, timeout=15)  # warm up cookies, same as 85_

    last_error = None
    raw_csv = None
    for url in NIFTY500_CSV_CANDIDATES:
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            raw_csv = resp.text
            break
        except Exception as e:
            last_error = e
    if raw_csv is None:
        raise RuntimeError(f"Could not fetch NSE's Nifty 500 list from any known URL: {last_error}")

    reader = csv.DictReader(io.StringIO(raw_csv))
    all_rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    if not all_rows:
        raise RuntimeError("NSE returned an empty Nifty 500 file -- refusing to treat that as 'every stock delisted'.")

    # Map each row's actual column names to our normalized keys once,
    # using the first row's headers.
    header_map = {norm(k): k for k in all_rows[0].keys()}
    symbol_col = next((header_map[k] for k in SYMBOL_KEYS if k in header_map), None)
    name_col = next((header_map[k] for k in NAME_KEYS if k in header_map), None)
    isin_col = next((header_map[k] for k in ISIN_KEYS if k in header_map), None)
    if symbol_col is None:
        raise RuntimeError(f"Could not find a Symbol column in NSE's Nifty 500 file -- got columns: {list(all_rows[0].keys())}")

    out = []
    for r in all_rows:
        ticker = r.get(symbol_col, "").strip()
        if not ticker:
            continue
        out.append({
            "ticker": ticker,
            "name": r.get(name_col, "").strip() if name_col else "",
            "isin": (r.get(isin_col, "").strip() or None) if isin_col else None,
            "yfinance_symbol": f"{ticker}.NS",
        })
    if len(out) < 400:
        # A truncated/garbled fetch could otherwise look like "most of
        # the Nifty 500 just got delisted" and wipe out the universe --
        # refuse instead of trusting a suspiciously small list.
        raise RuntimeError(f"Nifty 500 fetch returned only {len(out)} rows (expected ~500) -- refusing to treat this as real, looks like a bad/partial fetch.")
    return out


def fetch_all_db_india_equities(supabase) -> list:
    """Every India equity currently in `assets` (active or not),
    paginated -- see the many other scripts in this project with the
    same .range() comment for why pagination is required."""
    rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, is_active")
            .eq("asset_type", "equity")
            .eq("market", MARKET)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def main():
    supabase = get_client()

    print("Fetching NSE's current official Nifty 500 constituent list...")
    try:
        nse_rows = fetch_nifty500_list()
    except Exception as e:
        print(f"FAILED to fetch NSE's Nifty 500 list: {e}")
        print("Not touching the database -- a bad fetch should never look like a mass delisting.")
        return
    nse_by_ticker = {r["ticker"]: r for r in nse_rows}
    print(f"NSE's Nifty 500 currently lists {len(nse_rows)} constituents.\n")

    db_rows = fetch_all_db_india_equities(supabase)
    db_by_ticker = {r["ticker"]: r for r in db_rows}
    print(f"Your database currently has {len(db_rows)} India equity rows.\n")

    run_id = start_run("universe_sync_india")

    # -- New stocks: on NSE's list, not yet in the database. --
    new_tickers = [t for t in nse_by_ticker if t not in db_by_ticker]
    added_ok = []
    added_failed = []
    for ticker in new_tickers:
        r = nse_by_ticker[ticker]
        try:
            supabase.table("assets").upsert({
                "ticker": r["ticker"],
                "name": r["name"],
                "asset_type": "equity",
                "sector_id": None,
                "isin": r["isin"],
                "yfinance_symbol": r["yfinance_symbol"],
                "market": MARKET,
                "is_active": True,
            }, on_conflict="ticker,asset_type,market").execute()
            added_ok.append(ticker)
        except Exception as e:
            print(f"  ! could not add {ticker}: {e}")
            added_failed.append(ticker)
    print(f"Added {len(added_ok)} new stock(s): {added_ok if added_ok else 'none'}")
    if added_failed:
        print(f"Failed to add {len(added_failed)}: {added_failed}")

    # -- Removed stocks: currently active in the database, no longer
    # on NSE's list. Deactivate, never delete -- their history stays. --
    to_deactivate = [
        r["ticker"] for r in db_rows
        if r["is_active"] and r["ticker"] not in nse_by_ticker
    ]
    deactivated_ok = []
    for ticker in to_deactivate:
        asset_id = db_by_ticker[ticker]["asset_id"]
        try:
            supabase.table("assets").update({"is_active": False}).eq("asset_id", asset_id).execute()
            deactivated_ok.append(ticker)
        except Exception as e:
            print(f"  ! could not deactivate {ticker}: {e}")
    print(f"Deactivated {len(deactivated_ok)} stock(s) no longer in the Nifty 500: "
          f"{deactivated_ok if deactivated_ok else 'none'}")

    finish_run(run_id, ok_count=len(added_ok), failed_symbols=deactivated_ok)

    print(f"\nDone. {len(added_ok)} added, {len(deactivated_ok)} deactivated.")
    if added_ok:
        print(
            "\nNext steps for the newly added stocks (run automatically by the "
            "rest of this week's pipeline, or run manually right now if you don't "
            "want to wait): "
            "87_assign_sectors_from_yfinance.py, then "
            "20_backfill_new_stocks_price_history.py."
        )


if __name__ == "__main__":
    main()
