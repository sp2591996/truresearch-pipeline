"""
check_automotive_classification.py
-------------------------------------------------------------------
READ-ONLY check script, not numbered into the migrations sequence.
Run this first, before 173_reclassify_ashokley_to_automotive.py, to
confirm the exact sector/industry names and IDs that TATAMOTORS,
M&M, MARUTI, EICHERMOT, BAJAJ-AUTO currently sit under -- so the
reclassification script moves ASHOKLEY to the real, already-existing
Automotive industry rather than a guessed name.

Run manually from the TrueResearch Code folder (same venv you've
used for other scripts in this project):
    python check_automotive_classification.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"
TICKERS_TO_CHECK = ["TATAMOTORS", "M&M", "MARUTI", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO", "ASHOKLEY"]


def main():
    supabase = get_client()

    # Pull each ticker's asset row (sector_id, industry_id, sector_source)
    rows = []
    for ticker in TICKERS_TO_CHECK:
        asset = (
            supabase.table("assets")
            .select("asset_id, ticker, sector_id, industry_id, sector_source")
            .eq("ticker", ticker).eq("market", MARKET).eq("asset_type", "equity")
            .limit(1).execute().data
        )
        if not asset:
            print(f"{ticker}: NOT FOUND in assets table")
            continue
        rows.append((ticker, asset[0]))

    # Resolve sector_id/industry_id to their actual names
    sector_cache, industry_cache = {}, {}
    print(f"{'Ticker':<12} {'Sector':<28} {'Industry':<35} {'sector_source'}")
    print("-" * 100)
    for ticker, a in rows:
        sid, iid = a.get("sector_id"), a.get("industry_id")
        if sid not in sector_cache:
            s = supabase.table("sectors").select("name").eq("sector_id", sid).execute().data
            sector_cache[sid] = s[0]["name"] if s else f"(unknown sector_id={sid})"
        if iid not in industry_cache:
            i = supabase.table("industries").select("name").eq("industry_id", iid).execute().data
            industry_cache[iid] = i[0]["name"] if i else f"(unknown industry_id={iid})"
        print(f"{ticker:<12} {sector_cache[sid]:<28} {industry_cache[iid]:<35} {a.get('sector_source')}")


if __name__ == "__main__":
    main()
