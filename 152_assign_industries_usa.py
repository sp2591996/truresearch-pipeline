"""
152_assign_industries_usa.py
-------------------------------------------------------------------
Phase 2 (Session 39), USA side: fills in `industry_id` for every S&P
500 stock -- the finer-grained twin of 67_add_sp500_stocks.py.

Unlike India (which needs a live Yahoo Finance call per stock, see
151_assign_industries_india.py), the USA side already has the answer
sitting in `sp500_master.csv` -- it carries the OFFICIAL GICS
sub-industry per company (e.g. "Household Products", "Packaged
Foods", "Industrial Conglomerates") in its `gics_sub_industry`
column, the same file 67_add_sp500_stocks.py already used for the
broader `gics_sector` column. No new data source needed -- just
reading a column of the same file that was previously ignored.

What it does, per row in the CSV:
  1. Looks up this ticker's EXISTING sector_id (already assigned by
     67_add_sp500_stocks.py from the CSV's gics_sector column).
  2. Creates/matches an `industries` row for (gics_sub_industry, that
     sector_id, market='usa').
  3. Updates that stock's `industry_id`.

Safe to re-run (upserts everywhere). Does not touch sector_id.

Run manually:
    python 152_assign_industries_usa.py
-------------------------------------------------------------------
"""
import csv

from db_client import get_client

CSV_FILE = "sp500_master.csv"
MARKET = "usa"


def get_or_create_industry(supabase, industry_cache: dict, name: str, sector_id: int) -> int:
    key = (name.strip().lower(), sector_id)
    if key in industry_cache:
        return industry_cache[key]
    res = supabase.table("industries").upsert(
        {"name": name, "sector_id": sector_id, "market": MARKET},
        on_conflict="name,sector_id,market",
    ).execute()
    industry_id = res.data[0]["industry_id"]
    industry_cache[key] = industry_id
    return industry_id


def main():
    supabase = get_client()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} US stocks from {CSV_FILE}.")

    sectors_res = (
        supabase.table("sectors").select("sector_id, name").eq("market", MARKET).execute()
    )
    sector_id_by_name = {r["name"]: r["sector_id"] for r in sectors_res.data}
    print(f"Found {len(sector_id_by_name)} existing '{MARKET}' sectors in the database.")

    existing_industries = (
        supabase.table("industries").select("industry_id, name, sector_id").eq("market", MARKET).execute()
    ).data
    industry_cache = {(r["name"].strip().lower(), r["sector_id"]): r["industry_id"] for r in existing_industries}
    print(f"Found {len(industry_cache)} existing '{MARKET}' industries in the database.")

    ok_count = 0
    failed = []
    for r in rows:
        ticker = r["ticker"]
        sector_id = sector_id_by_name.get(r["gics_sector"])
        sub_industry = r.get("gics_sub_industry")

        if sector_id is None:
            print(f"  ! {ticker}: could not resolve sector '{r['gics_sector']}' -- skipped")
            failed.append(ticker)
            continue
        if not sub_industry:
            print(f"  ! {ticker}: no gics_sub_industry in CSV -- skipped")
            failed.append(ticker)
            continue

        try:
            industry_id = get_or_create_industry(supabase, industry_cache, sub_industry, sector_id)
            res = (
                supabase.table("assets")
                .update({"industry_id": industry_id})
                .eq("ticker", ticker)
                .eq("asset_type", "equity")
                .eq("market", MARKET)
                .execute()
            )
            if res.data:
                ok_count += 1
            else:
                print(f"  ! {ticker}: not found in assets -- skipped (run 67_add_sp500_stocks.py first?)")
                failed.append(ticker)
        except Exception as e:
            print(f"  ! {ticker}: failed -- {e}")
            failed.append(ticker)

    print(f"\nDone. Assigned an industry to {ok_count} of {len(rows)} US stocks.")
    print(f"Failed: {failed if failed else 'none'}")
    print(
        "\nNext step (not done by this script): run "
        "153_manual_conglomerate_overrides.py to tag known multi-business "
        "conglomerates (Berkshire Hathaway etc.) as 'Diversified' if GICS "
        "itself doesn't already capture that (some genuinely do, e.g. "
        "'Industrial Conglomerates' / 'Multi-Sector Holdings' are real "
        "GICS sub-industries)."
    )


if __name__ == "__main__":
    main()
