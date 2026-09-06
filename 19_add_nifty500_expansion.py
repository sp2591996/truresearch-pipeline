"""
19_add_nifty500_expansion.py
-------------------------------------------------------------------
Phase C, Step 2: adds the ~300 Nifty 500 stocks that are NOT yet in
your database (your original 200 + these 300 = the full Nifty 500).

Reads from `missing_300_nifty500.csv` (in this same folder) -- the
result of comparing NSE's official current Nifty 500 list against
your existing `assets` table (built via 18_export_current_tickers.py).

What it does:
  1. Adds 2 new rows to `sectors` for sector names this file uses
     that don't exist in your `sectors` table yet ("Diversified",
     "Media Entertainment & Publication") -- everything else already
     matches your existing 18 sectors exactly, so no other new
     sectors get created.
  2. Adds all 300 stocks to `assets` (asset_type='equity',
     is_active=True, with ticker/name/isin/yfinance_symbol from the
     CSV and the correct sector_id looked up by sector name).

Important -- what this does NOT do: it does not fetch any price
history or fundamentals for these 300 stocks, and it does not score
them. That's Step 3 onward (price backfill), a manual weekly-job run
(fundamentals), and finally re-running 14_score_current_stocks.py --
separate steps, on purpose, so each can be checked before moving to
the next.

Safe to re-run (upserts everywhere -- on_conflict "ticker,asset_type"
for assets, "name" for sectors -- so running this twice never creates
duplicates).

Run manually:
    python 19_add_nifty500_expansion.py
-------------------------------------------------------------------
"""
import csv

from db_client import get_client

CSV_FILE = "missing_300_nifty500.csv"


def main():
    supabase = get_client()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} stocks from {CSV_FILE}.")

    # Step 1: existing sectors.
    sectors_res = supabase.table("sectors").select("sector_id, name").execute()
    sector_id_by_name = {r["name"]: r["sector_id"] for r in sectors_res.data}
    print(f"Found {len(sector_id_by_name)} existing sectors in the database.")

    # Add any sector names used in the CSV that don't exist yet.
    needed_sector_names = {r["Industry"] for r in rows}
    new_sector_names = needed_sector_names - set(sector_id_by_name.keys())
    if new_sector_names:
        print(f"Adding {len(new_sector_names)} new sector(s): {sorted(new_sector_names)}")
        for name in sorted(new_sector_names):
            res = supabase.table("sectors").upsert(
                {"name": name}, on_conflict="name"
            ).execute()
            sector_id_by_name[name] = res.data[0]["sector_id"]
    else:
        print("No new sectors needed -- every sector in the CSV already exists.")

    # Step 2: add the 300 stocks.
    ok_count = 0
    failed = []
    for r in rows:
        sector_id = sector_id_by_name.get(r["Industry"])
        if sector_id is None:
            print(f"  ! {r['Symbol']}: could not resolve sector '{r['Industry']}' -- skipped")
            failed.append(r["Symbol"])
            continue
        try:
            supabase.table("assets").upsert({
                "ticker": r["Symbol"],
                "name": r["Company Name"],
                "asset_type": "equity",
                "sector_id": sector_id,
                "isin": r["ISIN Code"],
                "yfinance_symbol": r["yfinance_symbol"],
                "is_active": True,
            }, on_conflict="ticker,asset_type").execute()
            ok_count += 1
        except Exception as e:
            print(f"  ! {r['Symbol']}: failed -- {e}")
            failed.append(r["Symbol"])

    print(f"\nDone. Added/updated {ok_count} of {len(rows)} stocks in `assets`.")
    print(f"Failed: {failed if failed else 'none'}")
    print(
        "\nNext steps (not done by this script): "
        "run the 10-year price backfill for these new stocks, "
        "then a weekly fundamentals refresh, "
        "then re-run 14_score_current_stocks.py to score all 500."
    )


if __name__ == "__main__":
    main()
