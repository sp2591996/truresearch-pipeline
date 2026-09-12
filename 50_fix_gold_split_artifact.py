"""
50_fix_gold_split_artifact.py
-------------------------------------------------------------------
49_diagnose_gold_dip.py confirmed exactly one bad day in the Gold
price history: 2019-12-19, where the recorded close (0.34) is a ~99%
one-day plunge from the day before (33.60) that fully recovers within
days -- the signature of a GOLDBEES unit-split day yfinance's raw
history didn't adjust correctly, not a real price move. No other day
in the full history shows this pattern.

This does not invent a replacement number (never fake data, same rule
every other script in this project follows) -- it simply DELETES that
one bad row. `prices_daily` has no "must have a row for every date"
requirement (plenty of legitimate gaps already exist for market
holidays), so the chart will just draw straight through the missing
day using its real neighbors on either side, instead of spiking to
near-zero.

Safe to run more than once -- deleting an already-deleted row is a
no-op.

Run:
    venv\\Scripts\\python.exe 50_fix_gold_split_artifact.py
-------------------------------------------------------------------
"""
from db_client import get_client

BAD_DATE = "2019-12-19"


def main():
    supabase = get_client()
    asset = (
        supabase.table("assets")
        .select("asset_id")
        .eq("asset_type", "gold")
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not asset.data:
        print("No gold asset found -- run 47_add_gold_asset.py first.")
        return
    asset_id = asset.data["asset_id"]

    existing = (
        supabase.table("prices_daily")
        .select("date, close")
        .eq("asset_id", asset_id)
        .eq("date", BAD_DATE)
        .execute()
    ).data

    if not existing:
        print(f"No row found for {BAD_DATE} -- already cleaned up, nothing to do.")
        return

    print(f"Found {BAD_DATE}: close={existing[0]['close']} -- deleting this one bad row.")
    supabase.table("prices_daily").delete().eq("asset_id", asset_id).eq("date", BAD_DATE).execute()
    print("Done. The Gold chart will no longer show the false dip.")


if __name__ == "__main__":
    main()
