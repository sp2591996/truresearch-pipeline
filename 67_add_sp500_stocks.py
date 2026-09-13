"""
67_add_sp500_stocks.py
-------------------------------------------------------------------
Phase 1 (US market expansion), Step 2: adds the S&P 500 -- all ~503
US stocks -- into the database as a brand new market, separate from
the existing ~500 Indian stocks.

Reads from `sp500_master.csv` (in this same folder) -- sourced from
Wikipedia's "List of S&P 500 companies" page, one row per company,
with columns: ticker, yfinance_symbol, name, gics_sector,
gics_sub_industry.

What it does:
  1. Adds one `sectors` row per unique GICS sector used in the CSV
     (11 sectors: Information Technology, Health Care, Financials,
     Consumer Discretionary, Communication Services, Industrials,
     Consumer Staples, Energy, Utilities, Real Estate, Materials),
     each tagged market='usa'. These are completely separate rows
     from India's existing sectors, even if a name happens to match
     (e.g. India also has an "Energy" sector) -- the new `market`
     column (added by 66_add_market_column.sql, which MUST be run
     first) keeps them from ever being confused with each other.
  2. Adds all ~503 stocks to `assets` (asset_type='equity',
     is_active=True, market='usa'), with the correct sector_id looked
     up by (sector name, market='usa').

Important -- what this does NOT do: no price history, no
fundamentals, and no scoring for these stocks yet. Those are later,
separate steps (on purpose, so each one can be checked before moving
to the next):
  - a one-time 10-year price + fundamentals backfill for these ~503
    new stocks
  - building and validating a US-specific ML model
  - only then, running the scoring script for the US market

Safe to re-run (upserts everywhere, so running this twice never
creates duplicates).

BEFORE YOU RUN THIS:
  You must first run 66_add_market_column.sql in Supabase's SQL
  Editor (see that file's own instructions). If you skip that step,
  this script will fail with an error mentioning a missing "market"
  column.

Run manually:
    python 67_add_sp500_stocks.py
-------------------------------------------------------------------
"""
import csv

from db_client import get_client

CSV_FILE = "sp500_master.csv"
MARKET = "usa"


def main():
    supabase = get_client()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} US stocks from {CSV_FILE}.")

    # Step 1: existing sectors for this market.
    sectors_res = (
        supabase.table("sectors")
        .select("sector_id, name")
        .eq("market", MARKET)
        .execute()
    )
    sector_id_by_name = {r["name"]: r["sector_id"] for r in sectors_res.data}
    print(f"Found {len(sector_id_by_name)} existing '{MARKET}' sectors in the database.")

    needed_sector_names = {r["gics_sector"] for r in rows}
    new_sector_names = needed_sector_names - set(sector_id_by_name.keys())
    if new_sector_names:
        print(f"Adding {len(new_sector_names)} new sector(s): {sorted(new_sector_names)}")
        for name in sorted(new_sector_names):
            res = supabase.table("sectors").upsert(
                {"name": name, "market": MARKET}, on_conflict="name,market"
            ).execute()
            sector_id_by_name[name] = res.data[0]["sector_id"]
    else:
        print("No new sectors needed -- every GICS sector in the CSV already exists.")

    # Step 2: add the ~503 stocks.
    ok_count = 0
    failed = []
    for r in rows:
        sector_id = sector_id_by_name.get(r["gics_sector"])
        if sector_id is None:
            print(f"  ! {r['ticker']}: could not resolve sector '{r['gics_sector']}' -- skipped")
            failed.append(r["ticker"])
            continue
        try:
            supabase.table("assets").upsert({
                "ticker": r["ticker"],
                "name": r["name"],
                "asset_type": "equity",
                "sector_id": sector_id,
                "yfinance_symbol": r["yfinance_symbol"],
                "market": MARKET,
                "is_active": True,
            }, on_conflict="ticker,asset_type,market").execute()
            ok_count += 1
        except Exception as e:
            print(f"  ! {r['ticker']}: failed -- {e}")
            failed.append(r["ticker"])

    print(f"\nDone. Added/updated {ok_count} of {len(rows)} US stocks in `assets`.")
    print(f"Failed: {failed if failed else 'none'}")
    print(
        "\nNext steps (not done by this script): "
        "run a one-time 10-year price + fundamentals backfill for these new stocks, "
        "build and validate a US ML model, "
        "then run the scoring script for the US market."
    )


if __name__ == "__main__":
    main()
