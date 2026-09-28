"""
151_assign_industries_india.py
-------------------------------------------------------------------
Phase 2 (Session 39): fills in `industry_id` for every active India
equity that doesn't have one yet -- the finer-grained twin of
87_assign_sectors_from_yfinance.py (Avdhoot's request: Gillette/HUL/
Nestle shouldn't be treated as directly comparable peers just because
they all land in the same broad "Consumer Defensive" sector).

How it works, per stock:
  1. Calls get_fundamentals(yf_symbol) and reads the "industry" field
     Yahoo Finance returns (e.g. "Household & Personal Products",
     "Packaged Foods", "Specialty Retail" -- a much finer breakdown
     than the "sector" field the earlier script used).
  2. Looks up this stock's EXISTING sector_id (already assigned by
     87_assign_sectors_from_yfinance.py) -- every industry belongs to
     exactly one sector, so the industry row is created/matched
     scoped to (industry name, that same sector_id, market).
  3. If Yahoo Finance has no industry for this stock, it's put in a
     per-sector "Unclassified" industry (created once per sector) --
     never silently left NULL, never guessed.

Does NOT touch sector_id -- this only fills the new, additional
industry_id column. Safe to run alongside the existing sector script;
resumable (only processes industry_id IS NULL), safe to re-run.

Run manually:
    python 151_assign_industries_india.py
-------------------------------------------------------------------
"""
import time

from db_client import get_client
from market_data_provider import get_fundamentals

MARKET = "india"
UNCLASSIFIED_INDUSTRY_NAME = "Unclassified"


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

    existing_industries = (
        supabase.table("industries").select("industry_id, name, sector_id").eq("market", MARKET).execute()
    ).data
    industry_cache = {(r["name"].strip().lower(), r["sector_id"]): r["industry_id"] for r in existing_industries}
    print(f"Found {len(industry_cache)} existing India industries.")

    # Same pagination gotcha as 87_assign_sectors_from_yfinance.py --
    # PostgREST caps .select() at 1000 rows without .range() paging.
    assets = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, yfinance_symbol, sector_id")
            .eq("asset_type", "equity")
            .eq("market", MARKET)
            .eq("is_active", True)
            .is_("industry_id", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    print(f"{len(assets)} stocks need an industry assigned.\n")
    if not assets:
        print("Nothing to do -- every active India equity already has an industry.")
        return

    ok_count = 0
    failed = []

    for i, a in enumerate(assets, 1):
        ticker = a["ticker"]
        yf_symbol = a.get("yfinance_symbol")
        sector_id = a.get("sector_id")

        if sector_id is None:
            print(f"  [{i}/{len(assets)}] {ticker}: no sector_id yet (run 87_assign_sectors_from_yfinance.py first) -- skipped")
            failed.append(f"{ticker} (no sector_id)")
            continue

        if not yf_symbol:
            print(f"  [{i}/{len(assets)}] {ticker}: no yfinance_symbol on file -- skipped")
            failed.append(f"{ticker} (no yfinance_symbol)")
            continue

        info = get_fundamentals(yf_symbol)
        yahoo_industry = (info or {}).get("industry")

        try:
            if yahoo_industry:
                industry_id = get_or_create_industry(supabase, industry_cache, yahoo_industry, sector_id)
                supabase.table("assets").update({"industry_id": industry_id}).eq("asset_id", a["asset_id"]).execute()
                ok_count += 1
                print(f"  [{i}/{len(assets)}] {ticker}: {yahoo_industry}")
            else:
                industry_id = get_or_create_industry(supabase, industry_cache, UNCLASSIFIED_INDUSTRY_NAME, sector_id)
                supabase.table("assets").update({"industry_id": industry_id}).eq("asset_id", a["asset_id"]).execute()
                print(f"  [{i}/{len(assets)}] {ticker}: no industry data from Yahoo Finance -- put in this sector's Unclassified")
                failed.append(f"{ticker} (no industry data available)")
        except Exception as e:
            print(f"  [{i}/{len(assets)}] {ticker}: FAILED -- {e}")
            failed.append(f"{ticker} (save failed: {e})")

        time.sleep(0.3)

    print(f"\nDone. {ok_count}/{len(assets)} stocks assigned a real Yahoo Finance industry.")
    print(f"{len(failed)} put in Unclassified or failed -- see list above.")
    print(
        "\nNext step (not done by this script): run "
        "153_manual_conglomerate_overrides.py to tag known multi-business "
        "conglomerates (Reliance etc.) as 'Diversified' instead of whatever "
        "single industry Yahoo happened to assign them."
    )


if __name__ == "__main__":
    main()
