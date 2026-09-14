"""
85_fetch_nse_equity_list.py
-------------------------------------------------------------------
Stage 2, Step 1: fetches NSE's own official master list of every
mainboard-listed equity (not SME/Emerge) directly from NSE's public
archive CSV endpoint, and saves it locally for review -- this script
does NOT touch the database at all. Nothing gets added to `assets`
until you've checked this output looks right and we build the next
script together.

NSE's site actively blocks plain/non-browser requests (a well-known
quirk -- it's the same reason 31_check_nse_ipo_api.py had to check the
`nse` package actually worked before this project trusted it for the
IPO tracker). This script works around it the standard way: visit
NSE's homepage first with real browser-like headers to pick up the
session cookies NSE requires, then request the CSV using that same
session.

Filters OUT SME-platform stocks (NSE Emerge) -- same rule Avdhoot gave
for the IPO tracker ("make sure you dont include SME IPOs") -- by
keeping only SERIES values that mean mainboard-listed equity (EQ, BE,
BZ) and dropping anything else (SM-prefixed SME series, etc).

Run manually:
    python 85_fetch_nse_equity_list.py

Output:
    nse_full_equity_list.csv -- one row per mainboard stock, columns:
    ticker, name, isin, series, yfinance_symbol
    Also prints: total count, how many are already in your `assets`
    table (India) vs genuinely new, and a handful of sample new rows
    so you can eyeball that it looks sane before we go further.
-------------------------------------------------------------------
"""
import csv
import io

import requests

from db_client import get_client

NSE_HOME = "https://www.nseindia.com"
# NSE has renamed/moved this file before -- try a few known paths in
# order rather than hardcoding one and failing outright if it moves again.
NSE_EQUITY_CSV_CANDIDATES = [
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://nsearchives.nseindia.com/content/equity/EQUITY_L.csv",
    "https://archives.nseindia.com/content/equity/EQUITY_L.csv",
]
MAINBOARD_SERIES = {"EQ", "BE", "BZ"}  # excludes SME (SM-prefixed) series entirely

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/vnd.ms-excel,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/securities-available-for-trading",
}


def fetch_equity_list_csv() -> str:
    session = requests.Session()
    session.headers.update(HEADERS)
    # NSE requires a warmed-up session (cookies from a real page visit)
    # before it will serve this CSV to a script -- a bare request
    # without this step reliably gets refused.
    session.get(NSE_HOME, timeout=15)

    last_error = None
    for url in NSE_EQUITY_CSV_CANDIDATES:
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            print(f"  (fetched from {url})")
            return resp.text
        except Exception as e:
            print(f"  tried {url} -- failed ({e})")
            last_error = e
    raise last_error


def main():
    print("Fetching NSE's official equity list (this may take a few seconds)...")
    try:
        raw_csv = fetch_equity_list_csv()
    except Exception as e:
        print(f"FAILED to fetch NSE's list: {e}")
        print(
            "This usually means NSE changed how it blocks non-browser requests, "
            "or your network/firewall is blocking it. Paste this exact error back "
            "so we can figure out the next step -- do NOT retry blindly."
        )
        return

    reader = csv.DictReader(io.StringIO(raw_csv))
    # NSE's own CSV has a stray leading space in every column name after
    # the first (e.g. " SERIES", " ISIN NUMBER") -- strip both the column
    # names and every value so lookups below actually match.
    all_rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    print(f"NSE returned {len(all_rows)} total rows.")
    if not all_rows:
        print("Got an empty file -- something's wrong, stopping here.")
        return
    print(f"Columns found: {list(all_rows[0].keys())}")

    mainboard_rows = [r for r in all_rows if r.get("SERIES", "").strip() in MAINBOARD_SERIES]
    print(f"{len(mainboard_rows)} of those are mainboard-listed (SERIES in {sorted(MAINBOARD_SERIES)}) -- the rest are SME/other, excluded.")

    supabase = get_client()
    existing = (
        supabase.table("assets")
        .select("ticker")
        .eq("asset_type", "equity")
        .eq("market", "india")
        .execute()
    ).data
    existing_tickers = {r["ticker"] for r in existing}
    print(f"Your database currently has {len(existing_tickers)} India equities.")

    out_rows = []
    new_rows = []
    for r in mainboard_rows:
        ticker = r.get("SYMBOL", "").strip()
        if not ticker:
            continue
        row = {
            "ticker": ticker,
            "name": r.get("NAME OF COMPANY", "").strip(),
            "isin": r.get("ISIN NUMBER", "").strip(),
            "series": r.get("SERIES", "").strip(),
            "yfinance_symbol": f"{ticker}.NS",
        }
        out_rows.append(row)
        if ticker not in existing_tickers:
            new_rows.append(row)

    with open("nse_full_equity_list.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "name", "isin", "series", "yfinance_symbol"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nSaved {len(out_rows)} mainboard stocks to nse_full_equity_list.csv.")
    print(f"Of those, {len(new_rows)} are NOT yet in your database -- these are what Stage 2 would add.")
    print("\nSample of new stocks (first 15):")
    for r in new_rows[:15]:
        print(f"  {r['ticker']:<15} {r['name']}")
    print(
        "\nNothing has been changed in your database. Review "
        "nse_full_equity_list.csv and the counts above, then send them back "
        "so we can build the next step (adding these to `assets` + sector "
        "lookup + price history backfill)."
    )


if __name__ == "__main__":
    main()
