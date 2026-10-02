"""
157_assign_sector_industry_for_new_stocks.py
-------------------------------------------------------------------
Replaces the old two-step process (87_assign_sectors_from_yfinance.py
+ 151_assign_industries_india.py) for any NEW stock that enters the
universe (sector_id IS NULL) -- e.g. after 104_weekly_universe_sync_india.py
adds a stock newly promoted into the Nifty 500.

Run this AFTER 104/the weekly universe sync, whenever new stocks with
sector_id IS NULL show up. Per stock:

  1. Pulls Yahoo Finance's raw sector + industry (get_fundamentals()).
  2. Checks `sector_industry_ticker_overrides` for this exact ticker.
  3. Else checks `sector_industry_aliases` for this (raw_sector,
     raw_industry) combo.
  4. If EITHER matches -> assigns the corrected sector_id/industry_id
     and sets sector_source='manual' (a known-good rule was applied,
     so it's safe to lock -- never touched by this script again).
  5. If NEITHER matches -> does NOT guess. Leaves sector_id/industry_id
     NULL, inserts a row into `sector_industry_review_queue` with the
     raw Yahoo tags + a suggestion (the raw tags themselves, as a
     starting point), and moves on. This is what shows up as "Needs
     Review" on the Admin page for Avdhoot to resolve once -- resolving
     it there should insert a matching row into
     sector_industry_ticker_overrides so this exact stock is never
     re-flagged.

Never touches a stock that already has sector_source='manual' --
existing, reviewed assignments are never overwritten by this script.

Run manually:
    python 157_assign_sector_industry_for_new_stocks.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_fundamentals

MARKET = "india"


def get_or_create_sector(supabase, cache, name):
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    existing = supabase.table("sectors").select("sector_id").eq("name", name).execute().data
    sid = existing[0]["sector_id"] if existing else supabase.table("sectors").insert({"name": name}).execute().data[0]["sector_id"]
    cache[key] = sid
    return sid


def get_or_create_industry(supabase, cache, name, sector_id, is_diversified=False):
    key = (name.strip().lower(), sector_id)
    if key in cache:
        return cache[key]
    res = supabase.table("industries").upsert(
        {"name": name, "sector_id": sector_id, "market": MARKET, "is_diversified": is_diversified},
        on_conflict="name,sector_id,market",
    ).execute()
    iid = res.data[0]["industry_id"]
    cache[key] = iid
    return iid


def main():
    supabase = get_client()
    sector_cache, industry_cache = {}, {}

    ticker_overrides = {
        r["ticker"]: (r["corrected_sector_name"], r["corrected_industry_name"], r["is_diversified"])
        for r in supabase.table("sector_industry_ticker_overrides").select("*").eq("market", MARKET).execute().data
    }
    aliases = {
        (r["raw_sector"], r["raw_industry"]): (r["corrected_sector_name"], r["corrected_industry_name"], r["is_diversified"])
        for r in supabase.table("sector_industry_aliases").select("*").eq("market", MARKET).execute().data
    }
    print(f"Loaded {len(ticker_overrides)} ticker overrides, {len(aliases)} alias rules.")

    assets = []
    offset, page_size = 0, 1000
    while True:
        resp = (
            supabase.table("assets").select("asset_id, ticker, name, yfinance_symbol")
            .eq("asset_type", "equity").eq("market", MARKET).eq("is_active", True)
            .is_("sector_id", "null").range(offset, offset + page_size - 1).execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    print(f"{len(assets)} new stocks need classifying.\n")
    if not assets:
        print("Nothing to do.")
        return

    resolved, flagged = 0, 0
    for i, a in enumerate(assets, 1):
        ticker, yf_symbol = a["ticker"], a.get("yfinance_symbol")
        info = get_fundamentals(yf_symbol) if yf_symbol else None
        raw_sector = (info or {}).get("sector")
        raw_industry = (info or {}).get("industry")

        target = ticker_overrides.get(ticker) or (aliases.get((raw_sector, raw_industry)) if raw_sector and raw_industry else None)

        if target:
            corr_sector, corr_industry, is_div = target
            sector_id = get_or_create_sector(supabase, sector_cache, corr_sector)
            industry_id = get_or_create_industry(supabase, industry_cache, corr_industry, sector_id, is_div)
            supabase.table("assets").update({
                "sector_id": sector_id, "industry_id": industry_id, "sector_source": "manual",
            }).eq("asset_id", a["asset_id"]).execute()
            print(f"  [{i}/{len(assets)}] {ticker}: -> {corr_sector} / {corr_industry} (auto-resolved via known rule)")
            resolved += 1
        else:
            supabase.table("sector_industry_review_queue").insert({
                "asset_id": a["asset_id"], "ticker": ticker, "company_name": a.get("name"),
                "market": MARKET, "raw_sector": raw_sector, "raw_industry": raw_industry,
                "suggested_sector_name": raw_sector, "suggested_industry_name": raw_industry,
                "status": "pending",
            }).execute()
            print(f"  [{i}/{len(assets)}] {ticker}: no matching rule (raw: {raw_sector} / {raw_industry}) -- FLAGGED for Admin review")
            flagged += 1

    print(f"\nDone. {resolved} auto-resolved via known rules, {flagged} flagged for Admin review.")
    if flagged:
        print("Check the Admin page's 'Sector/Industry Needs Review' section to resolve the flagged stocks.")


if __name__ == "__main__":
    main()
