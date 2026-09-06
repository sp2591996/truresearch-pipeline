"""
18_export_current_tickers.py
-------------------------------------------------------------------
One-off helper for Phase C, Step 2 (scaling to Nifty 500). Not part
of the regular automated pipeline -- just exports your current list
of equity tickers to a CSV file, so this can be compared against the
full Nifty 500 constituent list to find which ~300 stocks are still
missing.

Writes: current_tickers_export.csv (in this same folder)

Run manually:
    python 18_export_current_tickers.py
-------------------------------------------------------------------
"""
import csv

from db_client import get_client


def main():
    supabase = get_client()
    res = (
        supabase.table("assets")
        .select("ticker, name, sector_id, yfinance_symbol, is_active, sectors(name)")
        .eq("asset_type", "equity")
        .execute()
    )
    rows = res.data
    print(f"Found {len(rows)} equity assets in the database.")

    with open("current_tickers_export.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "name", "sector_id", "sector_name", "yfinance_symbol", "is_active"])
        for r in rows:
            sector_name = (r.get("sectors") or {}).get("name") if r.get("sectors") else None
            writer.writerow([r["ticker"], r["name"], r["sector_id"], sector_name, r["yfinance_symbol"], r["is_active"]])

    print("Wrote current_tickers_export.csv in this folder.")


if __name__ == "__main__":
    main()
