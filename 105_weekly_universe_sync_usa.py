"""
105_weekly_universe_sync_usa.py
-------------------------------------------------------------------
The US equivalent of 104_weekly_universe_sync_india.py -- keeps your
US stock universe (currently the S&P 500) current automatically every
week, adding newly-added constituents and marking removed ones
inactive, mirroring how 67_add_sp500_stocks.py originally built this
list by hand from a one-time saved file.

Data source honesty note: unlike India (NSE publishes an official,
free, machine-readable equity list -- see 104_'s own fetch function),
there is no equivalent official free feed for "the current S&P 500
constituent list." The best free, reliable source is Wikipedia's
"List of S&P 500 companies" page, which S&P/media outlets treat as
accurate and which is updated promptly whenever S&P actually changes
the index. This is a WEB PAGE, not an API, so it's inherently a bit
more fragile than NSE's official CSV: if Wikipedia ever changes that
page's table layout, this script will fail loudly (raise an error and
touch nothing) rather than silently misreading it -- see the column-
name check below.

What it does, each run:
  1. Fetches and parses the current constituent table from Wikipedia.
  2. Compares it against every US equity currently in `assets`:
       - In the table but NOT in the database -> added (is_active=True,
         with its GICS sector resolved/created immediately, same as
         67_add_sp500_stocks.py did originally -- no NULL-sector step
         needed here since Wikipedia's table already includes it).
       - In the database as active but NOT in the current table
         anymore -> marked is_active=False (removed from the index).
       - In both -> left alone.
  3. Logs itself to `ingestion_runs` (run_type='universe_sync_usa').
     Same reuse of the table's shape as the India script: ok_count =
     stocks added, failed_symbols/failed_count = stocks deactivated.

Meant to run WEEKLY, the day before your existing weekly US
fundamentals/TrueScore jobs, so a newly added stock has time to get
its price history + fundamentals + score filled in before the site
would otherwise show it as incomplete:
    105 (this script) -> 20_backfill_new_stocks_price_history.py
                          (already generic -- works for any market)
                       -> (existing weekly US fundamentals/TrueScore jobs)

Setup (one-time): this script uses pandas.read_html(), which needs
one extra library not previously required by this project:
    venv\\Scripts\\python.exe -m pip install lxml

Run manually:
    venv\\Scripts\\python.exe 105_weekly_universe_sync_usa.py
-------------------------------------------------------------------
"""
import requests

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "usa"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
# The exact column names this script expects Wikipedia's first table to
# have. If Wikipedia renames/reorders these, pandas.read_html will still
# "succeed" but return something this script would misread -- so this
# is checked explicitly below rather than trusted blindly.
EXPECTED_COLUMNS = {"Symbol", "Security", "GICS Sector"}


def fetch_sp500_table() -> list:
    """Returns [{'ticker':.., 'name':.., 'gics_sector':.., 'yfinance_symbol':..}, ...]
    Raises on any structural surprise -- deliberately refuses to guess."""
    import pandas as pd

    resp = requests.get(WIKI_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    tables = pd.read_html(resp.text)
    if not tables:
        raise RuntimeError("Wikipedia page returned no tables at all -- the page may have changed.")

    table = tables[0]
    if not EXPECTED_COLUMNS.issubset(set(table.columns)):
        raise RuntimeError(
            f"Wikipedia's S&P 500 table no longer has the expected columns "
            f"{sorted(EXPECTED_COLUMNS)} -- found {list(table.columns)} instead. "
            f"The page's layout has likely changed; this script needs a small "
            f"update rather than blindly continuing."
        )

    out = []
    for _, row in table.iterrows():
        ticker = str(row["Symbol"]).strip()
        if not ticker or ticker.lower() == "nan":
            continue
        out.append({
            "ticker": ticker,
            # Yahoo Finance uses a dash where the index table uses a dot
            # (e.g. "BRK.B" on the page -> "BRK-B" for yfinance) -- same
            # convention the original sp500_master.csv already used.
            "yfinance_symbol": ticker.replace(".", "-"),
            "name": str(row["Security"]).strip(),
            "gics_sector": str(row["GICS Sector"]).strip(),
        })
    if len(out) < 400:
        # A real S&P 500 fetch should always be close to 500 rows --
        # anything drastically short means something upstream broke
        # (e.g. only a partial table was parsed), not a real index change.
        raise RuntimeError(
            f"Only parsed {len(out)} rows from Wikipedia's table -- expected ~500. "
            f"Refusing to treat this as a real mass-removal from the S&P 500."
        )
    return out


def fetch_all_db_usa_equities(supabase) -> list:
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


def get_or_create_sector(supabase, sector_cache: dict, name: str) -> int:
    key = name.strip().lower()
    if key in sector_cache:
        return sector_cache[key]
    res = supabase.table("sectors").upsert(
        {"name": name, "market": MARKET}, on_conflict="name,market"
    ).execute()
    sector_id = res.data[0]["sector_id"]
    sector_cache[key] = sector_id
    return sector_id


def main():
    supabase = get_client()

    print("Fetching the current S&P 500 constituent list from Wikipedia...")
    try:
        sp500_rows = fetch_sp500_table()
    except Exception as e:
        print(f"FAILED to fetch/parse the S&P 500 list: {e}")
        print("Not touching the database -- a bad fetch should never look like a mass removal.")
        return
    sp500_by_ticker = {r["ticker"]: r for r in sp500_rows}
    print(f"Wikipedia currently lists {len(sp500_rows)} S&P 500 constituents.\n")

    db_rows = fetch_all_db_usa_equities(supabase)
    db_by_ticker = {r["ticker"]: r for r in db_rows}
    print(f"Your database currently has {len(db_rows)} US equity rows.\n")

    sector_cache = {
        s["name"].strip().lower(): s["sector_id"]
        for s in supabase.table("sectors").select("sector_id, name").eq("market", MARKET).execute().data
    }

    run_id = start_run("universe_sync_usa")

    new_tickers = [t for t in sp500_by_ticker if t not in db_by_ticker]
    added_ok = []
    added_failed = []
    for ticker in new_tickers:
        r = sp500_by_ticker[ticker]
        try:
            sector_id = get_or_create_sector(supabase, sector_cache, r["gics_sector"])
            supabase.table("assets").upsert({
                "ticker": r["ticker"],
                "name": r["name"],
                "asset_type": "equity",
                "sector_id": sector_id,
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

    to_deactivate = [
        r["ticker"] for r in db_rows
        if r["is_active"] and r["ticker"] not in sp500_by_ticker
    ]
    deactivated_ok = []
    for ticker in to_deactivate:
        asset_id = db_by_ticker[ticker]["asset_id"]
        try:
            supabase.table("assets").update({"is_active": False}).eq("asset_id", asset_id).execute()
            deactivated_ok.append(ticker)
        except Exception as e:
            print(f"  ! could not deactivate {ticker}: {e}")
    print(f"Deactivated {len(deactivated_ok)} stock(s) no longer in the S&P 500: "
          f"{deactivated_ok if deactivated_ok else 'none'}")

    finish_run(run_id, ok_count=len(added_ok), failed_symbols=deactivated_ok)

    print(f"\nDone. {len(added_ok)} added, {len(deactivated_ok)} deactivated.")
    if added_ok:
        print(
            "\nNext step for the newly added stocks (run automatically by the "
            "rest of this week's pipeline, or run manually right now if you don't "
            "want to wait): 20_backfill_new_stocks_price_history.py."
        )


if __name__ == "__main__":
    main()
