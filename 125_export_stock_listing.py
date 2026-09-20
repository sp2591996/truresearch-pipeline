"""
125_export_stock_listing.py
-------------------------------------------------------------------
Avdhoot's request (updated spec): an Excel file with these columns --
    1) Company name
    2) Company Code (e.g. DLF for DLF Builders)
    3) Basic Information
    4) Business Overview
    5) Market Position
    6) Leadership and Governance
    7) Strategic Highlights
    8) Operational Strengths
    9) Culture and Reputation
    10) Sector
Columns 1, 2, and 10 (Company name, Company Code, Sector) are filled
in automatically by this script, straight from the database. Columns
3-9 are left blank on purpose -- this data doesn't live in Supabase
today, so there's nothing for the script to fill them with. The idea
is you hand this file to ChatGPT (or fill it in yourself) to populate
those blank columns, then bring it back to upload.

What this does, in plain terms:
  1. Connects to the same Supabase database every other script here
     uses (via db_client.py -- no new setup needed, it reads the same
     .env file already sitting in this folder).
  2. Pulls every stock (asset_type = "equity") from the `assets`
     table, for BOTH India and USA, along with its sector name.
  3. Writes it to an Excel file with exactly the 10 columns above,
     in that order, with 1/2/10 filled in and 3-9 left blank.

How to run this (from your own computer, not from Claude):
  1. Open a terminal (Command Prompt / PowerShell / Git Bash) and go
     to your TrueResearch Code folder:
         cd "C:\\Users\\Komal\\Desktop\\Stock App 2.0\\TrueResearch Code"
  2. This script needs one extra package (openpyxl) to write Excel
     files -- if you haven't installed it before, run this once:
         pip install openpyxl
     (If it says "already satisfied", that's fine -- carry on to
     step 3.)
  3. Run:
         python 125_export_stock_listing.py
  4. It will create a file called "stock_listing_export.xlsx" in that
     same folder. Open it in Excel to check it looks right, then hand
     it to ChatGPT to fill in the remaining columns.

This script only READS from the database -- it never changes or
deletes anything, so it's completely safe to run any time.
-------------------------------------------------------------------
"""
import sys

import pandas as pd

from db_client import get_client

OUTPUT_FILE = "stock_listing_export.xlsx"

# The 10 columns Avdhoot asked for, in the exact order requested.
# Only "Company name", "Company Code", and "Sector" get filled in by
# this script -- the rest are intentionally left blank for ChatGPT
# (or manual entry) to populate later, since none of that data lives
# in Supabase.
COLUMN_ORDER = [
    "Company name",
    "Company Code",
    "Basic Information",
    "Business Overview",
    "Market Position",
    "Leadership and Governance",
    "Strategic Highlights",
    "Operational Strengths",
    "Culture and Reputation",
    "Sector",
]

# Columns pulled straight from the `assets` table + the sector name
# joined in from `sectors`. If any of these don't exist in your
# database yet, Supabase will just return them as empty -- the
# script won't crash, it'll just leave that column blank for every row.
ASSET_COLUMNS = "asset_id, ticker, name, market, sector_id, is_active, sectors(name)"


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
            .eq("is_active", True)
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

    print("Fetching every active stock (India + USA)...")
    rows = fetch_all_equities(supabase)
    if not rows:
        print("No stocks found -- nothing to export. Check your database connection.")
        sys.exit(1)

    df = pd.DataFrame(
        [
            {
                "Company name": r.get("name"),
                "Company Code": r.get("ticker"),
                "Basic Information": "",
                "Business Overview": "",
                "Market Position": "",
                "Leadership and Governance": "",
                "Strategic Highlights": "",
                "Operational Strengths": "",
                "Culture and Reputation": "",
                "Sector": (r.get("sectors") or {}).get("name") if r.get("sectors") else None,
                # Kept only to split into per-market tabs below, dropped
                # before the final write since it wasn't in the 10
                # requested columns.
                "_market": (r.get("market") or "").upper(),
            }
            for r in rows
        ]
    )

    india_count = (df["_market"] == "INDIA").sum()
    usa_count = (df["_market"] == "USA").sum()
    print(f"Found {len(df)} stocks total -- {india_count} India, {usa_count} USA.")

    df_india = df[df["_market"] == "INDIA"][COLUMN_ORDER]
    df_usa = df[df["_market"] == "USA"][COLUMN_ORDER]
    df_all = df[COLUMN_ORDER]

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df_all.to_excel(writer, index=False, sheet_name="All Stocks")
        # Also split into two tabs, since you'll likely want to hand
        # ChatGPT one market at a time rather than one giant mixed list.
        df_india.to_excel(writer, index=False, sheet_name="India")
        df_usa.to_excel(writer, index=False, sheet_name="USA")

    print(f"Done. Saved to {OUTPUT_FILE} (in this same folder), with 3 tabs: All Stocks, India, USA.")


if __name__ == "__main__":
    main()
