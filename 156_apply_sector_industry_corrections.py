"""
156_apply_sector_industry_corrections.py
-------------------------------------------------------------------
One-time cleanup pass (Avdhoot's review, 2026-10-01) fixing the
Sector<>Industry mapping mess found across all 502 India stocks:
industries scattered across unrelated sectors (Steel under both
Capital Goods AND Metals & Mining, etc.), a junk-drawer "Services"
sector, single-stock "Diversified"/"Industrials" sectors, and a few
company-specific mistags (Lenskart tagged as medical devices, paint
makers tagged generic "Specialty Chemicals", etc.)

What this script does, in order:
  1. Creates/updates rows in `sector_industry_aliases` (general
     raw-tag -> corrected-tag rules) and `sector_industry_ticker_overrides`
     (company-specific corrections) -- see 155_....sql, run that FIRST.
  2. Re-reads every active India equity's CURRENT sector/industry.
  3. For each stock: checks ticker override first, then the general
     alias table, applies whichever matches to `sector_id`/`industry_id`
     (creating the sector/industry row if it doesn't exist yet), and
     sets `sector_source = 'manual'` -- this is what protects it from
     ever being silently overwritten by a future Yahoo-based sync.
  4. Any stock that matches NEITHER (i.e. was already fine as-is) still
     gets `sector_source = 'manual'` set, since this whole batch was
     reviewed by Avdhoot -- not just the 45 that changed.
  5. DUMMYHEG is deliberately skipped -- flagged separately as a likely
     delisted/dummy row that should probably be deleted, not reclassified.

Safe to re-run (idempotent -- upserts, not inserts).

Run manually:
    python 156_apply_sector_industry_corrections.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"
SKIP_TICKERS = {"DUMMYHEG"}  # flagged for deletion decision, not reclassification

# ---------------------------------------------------------------
# General rules: (raw_sector, raw_industry) -> corrected (sector, industry)
# Applied to ANY stock (existing or future) whose Yahoo Finance tags
# match -- these are patterns, not one-off company facts.
# ---------------------------------------------------------------
GENERAL_ALIASES = [
    # (raw_sector, raw_industry, corrected_sector, corrected_industry, is_diversified, note)
    ("Capital Goods", "Steel", "Metals & Mining", "Steel", False,
     "Steel producers belong with other steelmakers, not Capital Goods"),
    ("Services", "Information Technology Services", "Information Technology", "Information Technology Services", False,
     "IT/BPO services companies belong in Information Technology, not the junk-drawer Services sector"),
    ("Services", "Airlines", "Transportation & Logistics", "Airlines", False,
     "New Transportation & Logistics sector replaces junk-drawer Services"),
    ("Services", "Airports & Air Services", "Transportation & Logistics", "Airports & Air Services", False,
     "New Transportation & Logistics sector replaces junk-drawer Services"),
    ("Services", "Integrated Freight & Logistics", "Transportation & Logistics", "Integrated Freight & Logistics", False,
     "New Transportation & Logistics sector replaces junk-drawer Services"),
    ("Services", "Marine Shipping", "Transportation & Logistics", "Marine Shipping", False,
     "New Transportation & Logistics sector replaces junk-drawer Services"),
    ("Services", "Railroads", "Transportation & Logistics", "Railroads", False,
     "New Transportation & Logistics sector replaces junk-drawer Services"),
    ("Oil Gas & Consumable Fuels", "Thermal Coal", "Metals & Mining", "Thermal Coal", False,
     "Coal mining grouped with Metals & Mining, not Oil & Gas"),
]

# ---------------------------------------------------------------
# Company-specific overrides: ticker -> corrected (sector, industry)
# These do NOT generalize (e.g. not every "Medical Instruments &
# Supplies" stock is mistagged -- just Lenskart specifically).
# ---------------------------------------------------------------
TICKER_OVERRIDES = [
    # (ticker, corrected_sector, corrected_industry, is_diversified, note)
    ("HEGAM", "Capital Goods", "Electrical Equipment & Parts", False,
     "Single-stock 'Industrials' sector folded into Capital Goods"),
    ("3MINDIA", "Capital Goods", "Diversified", True,
     "Diversified industrial/consumer/healthcare conglomerate"),
    ("DCMSHRIRAM", "Chemicals", "Diversified", True,
     "Chemicals + sugar + fertilizer + plastics conglomerate; core business is chemicals"),
    ("GODREJIND", "Chemicals", "Diversified", True,
     "Core business is chemicals (+ real estate/FMCG stakes); 'Diversified' sector removed entirely"),
    ("HEG", "Capital Goods", "Metal Fabrication", False,
     "Graphite electrode maker (industrial input for steelmaking) -- was missing an industry entirely"),
    ("APLAPOLLO", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("GALLANTT", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("GPIL", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("JINDALSAW", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("SHYAMMETL", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("USHAMART", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("WELCORP", "Metals & Mining", "Steel", False, "Steel producer, moved out of Capital Goods"),
    ("LENSKART", "Consumer Services", "Specialty Retail", False,
     "Eyewear retailer -- Yahoo mistagged as 'Medical Instruments & Supplies'"),
    ("ASIANPAINT", "Consumer Durables", "Paints", False, "Paint makers grouped under a dedicated Paints industry"),
    ("BERGEPAINT", "Consumer Durables", "Paints", False, "Paint makers grouped under a dedicated Paints industry"),
    ("JSWDULUX", "Consumer Durables", "Paints", False, "Paint makers grouped under a dedicated Paints industry"),
    ("ACUTAAS", "Chemicals", "Specialty Chemicals", False,
     "Pharma intermediates/specialty chemicals maker -- grouped with Chemicals, not Healthcare"),
    ("TMCV", "Automobile and Auto Components", "Auto Manufacturers", False,
     "Commercial vehicle manufacturer -- moved to sit with other auto OEMs"),
    ("EIDPARRY", "Fast Moving Consumer Goods", "Packaged Foods", False,
     "Core business is sugar production, not agricultural inputs"),
    ("UBL", "Fast Moving Consumer Goods", "Beverages - Alcoholic", False, "Consolidated beverage sub-categories"),
    ("ABDL", "Fast Moving Consumer Goods", "Beverages - Alcoholic", False, "Consolidated beverage sub-categories"),
    ("RADICO", "Fast Moving Consumer Goods", "Beverages - Alcoholic", False, "Consolidated beverage sub-categories"),
    ("UNITDSPR", "Fast Moving Consumer Goods", "Beverages - Alcoholic", False, "Consolidated beverage sub-categories"),
    ("VBL", "Fast Moving Consumer Goods", "Beverages - Non-Alcoholic", False, "Consolidated beverage sub-categories"),
    ("IKS", "Healthcare", "Health Information Services", False,
     "Healthcare-focused ITeS -- made consistent with Indegene (same business model)"),
    ("SAGILITY", "Healthcare", "Health Information Services", False,
     "Healthcare-focused ITeS -- made consistent with Indegene (same business model)"),
    ("CAMS", "Financial Services", "Financial Data & Stock Exchanges", False,
     "Registrar & Transfer Agent -- generic 'IT Services' label was too vague"),
    ("KFINTECH", "Financial Services", "Financial Data & Stock Exchanges", False,
     "Registrar & Transfer Agent, same business model as CAMS"),
    ("URBANCO", "Consumer Services", "Internet Retail", False,
     "Home-services marketplace, not generic 'Software - Application'"),
    ("ECLERX", "Information Technology", "Information Technology Services", False, "Moved out of junk-drawer Services"),
    ("FSL", "Information Technology", "Information Technology Services", False, "Moved out of junk-drawer Services"),
    ("REDINGTON", "Information Technology", "Information Technology Services", False, "Moved out of junk-drawer Services"),
    ("MMTC", "Metals & Mining", "Diversified", True, "State trading corp dealing mainly in metals/minerals"),
    ("IGIL", "Consumer Services", "Specialty Business Services", False,
     "Gem/jewelry certification & grading services, not a mining company"),
]


def get_or_create_sector(supabase, cache: dict, name: str) -> int:
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    existing = supabase.table("sectors").select("sector_id").eq("name", name).execute().data
    if existing:
        sid = existing[0]["sector_id"]
    else:
        res = supabase.table("sectors").insert({"name": name}).execute()
        sid = res.data[0]["sector_id"]
        print(f"  + created new sector: {name}")
    cache[key] = sid
    return sid


def get_or_create_industry(supabase, cache: dict, name: str, sector_id: int, market: str, is_diversified: bool) -> int:
    key = (name.strip().lower(), sector_id)
    if key in cache:
        return cache[key]
    res = supabase.table("industries").upsert(
        {"name": name, "sector_id": sector_id, "market": market, "is_diversified": is_diversified},
        on_conflict="name,sector_id,market",
    ).execute()
    iid = res.data[0]["industry_id"]
    cache[key] = iid
    return iid


def main():
    supabase = get_client()
    sector_cache, industry_cache = {}, {}

    # Step 1: populate the alias + override rule tables (so future
    # syncs can reuse them).
    print("Populating sector_industry_aliases...")
    for raw_sector, raw_industry, corr_sector, corr_industry, is_div, note in GENERAL_ALIASES:
        supabase.table("sector_industry_aliases").upsert({
            "market": MARKET, "raw_sector": raw_sector, "raw_industry": raw_industry,
            "corrected_sector_name": corr_sector, "corrected_industry_name": corr_industry,
            "is_diversified": is_div, "note": note,
        }, on_conflict="market,raw_sector,raw_industry").execute()
    print(f"  {len(GENERAL_ALIASES)} alias rules upserted.")

    print("Populating sector_industry_ticker_overrides...")
    for ticker, corr_sector, corr_industry, is_div, note in TICKER_OVERRIDES:
        supabase.table("sector_industry_ticker_overrides").upsert({
            "ticker": ticker, "market": MARKET,
            "corrected_sector_name": corr_sector, "corrected_industry_name": corr_industry,
            "is_diversified": is_div, "note": note,
        }, on_conflict="ticker,market").execute()
    print(f"  {len(TICKER_OVERRIDES)} ticker overrides upserted.")

    # Step 2: apply to every active India equity.
    print("\nFetching current India equities...")
    assets = []
    offset, page_size = 0, 1000
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, sector_id, industry_id")
            .eq("asset_type", "equity").eq("market", MARKET).eq("is_active", True)
            .range(offset, offset + page_size - 1).execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    print(f"  {len(assets)} stocks found.")

    # Need raw sector/industry NAMES (not just ids) to match against aliases.
    sectors_by_id = {r["sector_id"]: r["name"] for r in supabase.table("sectors").select("sector_id, name").execute().data}
    industries_by_id = {r["industry_id"]: r["name"] for r in supabase.table("industries").select("industry_id, name").execute().data}

    ticker_override_map = {t: (s, i, d) for t, s, i, d, _ in TICKER_OVERRIDES}
    alias_map = {(rs, ri): (cs, ci, d) for rs, ri, cs, ci, d, _ in GENERAL_ALIASES}

    manual_count, skipped_count, unchanged_count = 0, 0, 0
    for a in assets:
        ticker = a["ticker"]
        if ticker in SKIP_TICKERS:
            print(f"  {ticker}: SKIPPED (flagged for deletion decision, not reclassified)")
            skipped_count += 1
            continue

        raw_sector_name = sectors_by_id.get(a.get("sector_id"))
        raw_industry_name = industries_by_id.get(a.get("industry_id"))

        target = None
        if ticker in ticker_override_map:
            target = ticker_override_map[ticker]
        elif (raw_sector_name, raw_industry_name) in alias_map:
            target = alias_map[(raw_sector_name, raw_industry_name)]

        if target:
            corr_sector, corr_industry, is_div = target
            sector_id = get_or_create_sector(supabase, sector_cache, corr_sector)
            industry_id = get_or_create_industry(supabase, industry_cache, corr_industry, sector_id, MARKET, is_div)
            supabase.table("assets").update({
                "sector_id": sector_id, "industry_id": industry_id, "sector_source": "manual",
            }).eq("asset_id", a["asset_id"]).execute()
            manual_count += 1
        else:
            # Already correct as reviewed -- still lock it as manual so
            # a future Yahoo-based sync can never silently change it.
            supabase.table("assets").update({"sector_source": "manual"}).eq("asset_id", a["asset_id"]).execute()
            unchanged_count += 1

    print(f"\nDone. {manual_count} stocks corrected, {unchanged_count} confirmed-as-is, "
          f"{skipped_count} skipped (flagged). All {manual_count + unchanged_count} now "
          f"marked sector_source='manual' -- protected from future auto-sync overwrites.")
    print("\nNext: run 155_....sql in Supabase FIRST if you haven't already, then this script.")
    print("After this, update the weekly universe-sync scripts to check these override/alias "
          "tables for NEW stocks, and only flag genuinely unmatched ones into "
          "sector_industry_review_queue for the Admin page.")


if __name__ == "__main__":
    main()
