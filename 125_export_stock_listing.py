"""
125_export_stock_listing.py
-------------------------------------------------------------------
Avdhoot's request: "give me all the stock names, and their acronyms
and other details in excel... I will then give this excel to chatgpt
to populate the details to upload."

What this does, in plain terms:
  1. Connects to the same Supabase database every other script here
     uses (via db_client.py -- no new setup needed, it reads the same
     .env file already sitting in this folder).
  2. Pulls every stock (asset_type = "equity") from the `assets`
     table, for BOTH India and USA, along with its sector name.
  3. Writes it all to one Excel file, with a clean set of columns:
     Ticker, Name, Market, Sector, ISIN, Yahoo Finance Symbol, Listed
     Date, Active.
  4. Also adds a few empty columns at the end (Company Brief,
     Business Description, Key Products) -- so when you hand this
     file to ChatGPT, there's an obvious place for it to fill in the
     extra details you want, without you having to add columns
     yourself first. Feel free to rename/add more empty columns
     before you send it over -- this is just a sensible starting set.

How to run this (from your own computer, not from Claude):
  1. Open a terminal (Command Prompt / PowerShell / Git Bash) and go
     to your TrueResearch Code folder:
         cd "C:\\Users\\Komal\\Desktop\\Stock App 2.0\\TrueResearch Code"
  2. This script needs one extra package (openpyxl) to write Excel
     files -- if you haven't installed it before, run this once:
         pip install openpyxl
     (If it says "already satisfied", that's fine, it just means you
     already have it -- carry on to step 3.)
  3. Run:
         python 125_export_stock_listing.py
  4. It will create a file called "stock_listing_export.xlsx" in that
     same folder. Open it in Excel to check it looks right, then hand
     it to ChatGPT.

This script only READS from the database -- it never changes or
deletes anything, so it's completely safe to run any time.
-------------------------------------------------------------------
"""
import sys

import pandas as pd

from db_client import get_client

OUTPUT_FILE = "stock_listing_export.xlsx"

# Columns pulled straight from the `assets` table + the sector name
# joined in from `sectors`. If any of these don't exist in your
# database yet, Supabase will just return them as empty -- the
# script won't crash, it'll just leave that column blank for every row.
ASSET_COLUMNS = "asset_id, ticker, name, market, sector_id, isin, yfinance_symbol, listed_date, is_active, sectors(name)"


def fetch_all_equities(supabase):
    """Pulls every equity row, page by page (Supabase caps each request
    at 1000 rows, and we have 500-1000+ stocks across both markets)."""
    all_rows = []
    page_size = 1000
    start = 0
    while True:
        res = (
            supabase.table("assets")
            .select(ASSET_COLUMNS)
            .eq("asset_type", "equity")
            .order("market")
            .order("ticker")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return all_rows


def main():
    print("Connecting to the database...")
    try:
        supabase = get_client()
    except RuntimeError as e:
        print(f"Could not connect: {e}")
        sys.exit(1)

    print("Fetching every stock (India + USA)...")
    rows = fetch_all_equities(supabase)
    if not rows:
        print("No stocks found -- nothing to export. Check your database connection.")
        sys.exit(1)

    df = pd.DataFrame(
        [
            {
                "Ticker": r.get("ticker"),
                "Name": r.get("name"),
                "Market": (r.get("market") or "").upper(),
                "Sector": (r.get("sectors") or {}).get("name") if r.get("sectors") else None,
                "ISIN": r.get("isin"),
                "Yahoo Finance Symbol": r.get("yfinance_symbol"),
                "Listed Date": r.get("listed_date"),
                "Active": "Yes" if r.get("is_active") else "No",
                # Empty on purpose -- fill these in yourself, or hand
                # the file to ChatGPT to populate them for you.
                "Company Brief": "",
                "Business Description": "",
                "Key Products": "",
            }
            for r in rows
        ]
    )

    india_count = (df["Market"] == "INDIA").sum()
    usa_count = (df["Market"] == "USA").sum()
    print(f"Found {len(df)} stocks total -- {india_count} India, {usa_count} USA.")

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="All Stocks")
        # Also split into two tabs, since you'll likely want to hand
        # ChatGPT one market at a time rather than one giant mixed list.
        df[df["Market"] == "INDIA"].to_excel(writer, index=False, sheet_name="India")
        df[df["Market"] == "USA"].to_excel(writer, index=False, sheet_name="USA")

    print(f"Done. Saved to {OUTPUT_FILE} (in this same folder), with 3 tabs: All Stocks, India, USA.")


if __name__ == "__main__":
    main()
