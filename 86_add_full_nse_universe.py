"""
86_add_full_nse_universe.py
-------------------------------------------------------------------
Stage 2, Step 2: adds the ~2,068 NSE mainboard stocks not yet in your
database (confirmed via 85_fetch_nse_equity_list.py's real run:
2,568 total mainboard stocks - 500 already present = 2,068 new),
reading from nse_full_equity_list.csv (produced by that script).

Same safe pattern as 19_add_nifty500_expansion.py / 67_add_sp500_stocks.py:
  - Adds each stock to `assets` (asset_type='equity', market='india',
    is_active=True, with ticker/name/isin/yfinance_symbol from the CSV).
  - sector_id is left NULL for now -- NSE's own list has no industry
    column (unlike the old Nifty 500 list this project started with).
    87_backfill_full_universe.py (the next script, not this one) will
    fill in each stock's sector from Yahoo Finance's own data, and also
    backfill price history -- deliberately separate steps so each can
    be checked before moving to the next, same discipline every prior
    expansion in this project followed.
  - Safe to re-run (upserts on "ticker,asset_type,market" -- the exact
    constraint 66_add_market_column.sql created -- so running this
    twice never creates duplicates).

This does NOT touch is_active on any EXISTING stock -- only inserts/
updates the new ones from the CSV. Your current 500 scored stocks are
completely unaffected by this script.

Run manually (after 85_fetch_nse_equity_list.py has produced
nse_full_equity_list.csv):
    python 86_add_full_nse_universe.py
-------------------------------------------------------------------
"""
import csv

from db_client import get_client

CSV_FILE = "nse_full_equity_list.csv"
MARKET = "india"


def main():
    supabase = get_client()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} mainboard stocks from {CSV_FILE}.")

    existing = (
        supabase.table("assets")
        .select("ticker")
        .eq("asset_type", "equity")
        .eq("market", MARKET)
        .execute()
    ).data
    existing_tickers = {r["ticker"] for r in existing}
    new_rows = [r for r in rows if r["ticker"] not in existing_tickers]
    print(f"{len(existing_tickers)} already in the database, {len(new_rows)} are new.")

    # Not logged to ingestion_runs -- this is a one-time setup script,
    # same as 19_add_nifty500_expansion.py / 67_add_sp500_stocks.py
    # before it, neither of which logs there either.
    ok_count = 0
    failed = []

    for r in new_rows:
        try:
            supabase.table("assets").upsert({
                "ticker": r["ticker"],
                "name": r["name"],
                "asset_type": "equity",
                "sector_id": None,
                "isin": r["isin"] or None,
                "yfinance_symbol": r["yfinance_symbol"],
                "market": MARKET,
                "is_active": True,
            }, on_conflict="ticker,asset_type,market").execute()
            ok_count += 1
        except Exception as e:
            print(f"  ! {r['ticker']}: failed -- {e}")
            failed.append(r["ticker"])

    print(f"\nDone. Added/updated {ok_count} of {len(new_rows)} new stocks in `assets`.")
    print(f"Failed: {failed if failed else 'none'}")
    print(
        "\nNext step (not done by this script): run 87_backfill_full_universe.py "
        "to fetch each new stock's sector + 5-year price history from Yahoo "
        "Finance. Until that runs, these new stocks exist in the database but "
        "won't show sector grouping, price charts, or a TrueScore yet -- "
        "they won't appear broken on the site, just incomplete."
    )


if __name__ == "__main__":
    main()
