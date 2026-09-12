"""
49_diagnose_gold_dip.py
-------------------------------------------------------------------
Avdhoot's Gold page chart shows one single-day vertical plunge to
near-zero around Feb 2020, then a normal recovery. Almost certainly a
GOLDBEES unit-split artifact in yfinance's raw history (a split divides
each unit into many smaller ones, dropping the per-unit price sharply
for one bad day of raw data) rather than a real price move -- this
script just finds and prints the exact bad day(s) so we can confirm
before touching any data (same "diagnose before fixing" discipline as
10_diagnose_fundamentals.py / 28_diagnose_missing_ratios.py).

Flags any day where the price moves more than 50% from the previous
day AND recovers within the next few days -- a real crash doesn't
"come back" the very next week; a split artifact does.

Run:
    venv\\Scripts\\python.exe 49_diagnose_gold_dip.py
-------------------------------------------------------------------
"""
from db_client import get_client

# Session 28 (Avdhoot: "your data is only till 2020"): Supabase/
# PostgREST caps any single request at 1000 rows -- silently, with no
# error -- unless the caller explicitly pages through with .range().
# 10 years of daily gold prices is ~2,474 rows, so a plain .select()
# with no range only ever returned the OLDEST 1000 of them (ordered
# ascending), which happens to land right around 2020. This is the
# same root cause behind that missing recent history AND why this
# diagnostic script itself only ever checked 1000 days. Fixed with a
# proper page-until-done loop.
PAGE_SIZE = 1000


def fetch_all_prices(supabase, asset_id: int) -> list[dict]:
    rows: list[dict] = []
    page = 0
    while True:
        chunk = (
            supabase.table("prices_daily")
            .select("date, close")
            .eq("asset_id", asset_id)
            .order("date", desc=False)
            .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1)
            .execute()
        ).data
        rows.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
        page += 1
    return rows


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

    rows = fetch_all_prices(supabase, asset_id)

    print(f"Checking {len(rows)} days of Gold price history for split-artifact dips...\n")

    suspects = []
    for i in range(1, len(rows) - 3):
        prev_close = rows[i - 1]["close"]
        this_close = rows[i]["close"]
        if not prev_close or not this_close:
            continue
        drop_pct = (prev_close - this_close) / prev_close * 100
        if drop_pct > 50:
            # Does it recover within the next 3 days back to roughly prev_close's range?
            later_closes = [r["close"] for r in rows[i + 1:i + 4] if r["close"]]
            recovered = any(c > prev_close * 0.5 for c in later_closes)
            suspects.append((rows[i]["date"], prev_close, this_close, drop_pct, recovered))

    if not suspects:
        print("No single-day drops over 50% found. The dip may be something else -- send a screenshot with the exact date range selected.")
        return

    for date, prev_close, this_close, drop_pct, recovered in suspects:
        tag = "LIKELY SPLIT ARTIFACT (recovered soon after)" if recovered else "genuine large move? (did not recover)"
        print(f"  {date}: {prev_close:.2f} -> {this_close:.2f}  ({drop_pct:.0f}% drop)  -- {tag}")


if __name__ == "__main__":
    main()
