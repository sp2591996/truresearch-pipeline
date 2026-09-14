"""
88_list_unclassified.py
-------------------------------------------------------------------
Read-only helper: prints every India equity currently sitting in the
"Unclassified" sector (the ~21 stocks Yahoo Finance had no sector data
for, even after a retry), so they can be reviewed and assigned a
sector by hand.

Does NOT change anything in the database.

Run manually:
    python 88_list_unclassified.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"
UNCLASSIFIED_SECTOR_NAME = "Unclassified"


def main():
    supabase = get_client()
    sector_res = (
        supabase.table("sectors")
        .select("sector_id")
        .eq("market", MARKET)
        .eq("name", UNCLASSIFIED_SECTOR_NAME)
        .maybe_single()
        .execute()
    )
    if not sector_res.data:
        print("No Unclassified sector exists -- nothing to list.")
        return
    unclassified_id = sector_res.data["sector_id"]

    rows = (
        supabase.table("assets")
        .select("ticker, name, yfinance_symbol")
        .eq("asset_type", "equity")
        .eq("market", MARKET)
        .eq("sector_id", unclassified_id)
        .order("ticker")
        .execute()
    ).data

    print(f"{len(rows)} stocks currently in Unclassified:\n")
    for r in rows:
        print(f"{r['ticker']:<15} {r['name']}")


if __name__ == "__main__":
    main()
