"""
154_export_stock_industry_sector.py
-------------------------------------------------------------------
Avdhoot's ask: a simple Excel file listing every INDIAN stock, its
industry, and its sector, as currently stored in the database --
useful for spot-checking the sector/industry assignments by eye.

What it does:
  1. Reads every "india" stock from `assets`.
  2. Joins in its sector name (via `sector_id` -> `sectors`).
  3. Joins in its industry name (via `industry_id` -> `industries`),
     plus whether that industry is a "Diversified" conglomerate tag.
  4. Writes it all to one Excel file, sorted by Sector then Industry
     then Ticker, so related stocks sit together and are easy to
     scan through.

Needs the `openpyxl` package (same as pandas needs for .xlsx output).
If it's not installed, run:  pip install openpyxl

Run manually:
    python 154_export_stock_industry_sector.py

Output:
    stock_industry_sector_india.xlsx  (in the same folder you run it from)
-------------------------------------------------------------------
"""
import pandas as pd

from db_client import get_client

MARKET = "india"
OUTPUT_FILE = "stock_industry_sector_india.xlsx"


def main():
    supabase = get_client()

    print(f"Fetching '{MARKET}' stocks from the database...")
    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, name, sector_id, industry_id")
        .eq("asset_type", "equity")
        .eq("market", MARKET)
        .execute()
    )
    assets = assets_res.data
    print(f"  Found {len(assets)} stocks.")

    sectors_res = supabase.table("sectors").select("sector_id, name").eq("market", MARKET).execute()
    sector_name_by_id = {r["sector_id"]: r["name"] for r in sectors_res.data}

    industries_res = (
        supabase.table("industries")
        .select("industry_id, name, is_diversified")
        .eq("market", MARKET)
        .execute()
    )
    industry_by_id = {r["industry_id"]: r for r in industries_res.data}

    rows = []
    for a in assets:
        sector_name = sector_name_by_id.get(a.get("sector_id"), "(no sector assigned)")
        industry_row = industry_by_id.get(a.get("industry_id"))
        industry_name = industry_row["name"] if industry_row else "(no industry assigned)"
        is_diversified = bool(industry_row["is_diversified"]) if industry_row else False

        rows.append({
            "Ticker": a["ticker"],
            "Company Name": a.get("name") or "",
            "Sector": sector_name,
            "Industry": industry_name,
            "Diversified (Conglomerate)?": "Yes" if is_diversified else "",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["Sector", "Industry", "Ticker"]).reset_index(drop=True)

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\nDone. Wrote {len(df)} rows to {OUTPUT_FILE}")

    missing_sector = (df["Sector"] == "(no sector assigned)").sum()
    missing_industry = (df["Industry"] == "(no industry assigned)").sum()
    if missing_sector or missing_industry:
        print(f"Note: {missing_sector} stock(s) have no sector, {missing_industry} stock(s) have no industry.")


if __name__ == "__main__":
    main()
