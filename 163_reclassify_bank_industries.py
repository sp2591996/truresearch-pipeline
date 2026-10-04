"""
163_reclassify_bank_industries.py
-------------------------------------------------------------------
Fixes an external site-audit finding: every Indian bank stock (38 of
them, after the Banking Sector Deep Dive work) was lumped into one
industry, "Banks - Regional", regardless of actual type -- so HDFC
Bank, SBI, and a genuinely small regional bank all showed up under
the same label, and the industry page's own "largest names by market
cap" (HDFC/ICICI/SBI) made that mislabeling obvious.

This splits them into the three categories most financial sites
(Screener, Trendlyne) use for Indian banks:
  - Private Sector Banks
  - Public Sector Banks
  - Small Finance Banks

Same mechanism as 156_apply_sector_industry_corrections.py (per-ticker
overrides in `sector_industry_ticker_overrides`, applied via
sector_source='manual' so no future automated sync silently reverts
this). Run 155_....sql FIRST if that hasn't already been run on this
database (it's idempotent, and was already applied for the original
156 cleanup pass, so this is likely a no-op check).

This script only touches the 38 bank tickers below -- it does NOT
re-walk every asset in the database the way 156 does, since nothing
else needs reclassifying here.

Run manually:
    python 163_reclassify_bank_industries.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"
SECTOR_NAME = "Financial Services"

# (ticker, corrected_industry, note)
BANK_TICKER_OVERRIDES = [
    # --- Private Sector Banks (20) ---
    ("HDFCBANK", "Private Sector Banks", "Large private bank"),
    ("ICICIBANK", "Private Sector Banks", "Large private bank"),
    ("KOTAKBANK", "Private Sector Banks", "Large private bank"),
    ("AXISBANK", "Private Sector Banks", "Large private bank"),
    ("INDUSINDBK", "Private Sector Banks", "Large private bank"),
    ("FEDERALBNK", "Private Sector Banks", "Mid-size private bank"),
    ("IDFCFIRSTB", "Private Sector Banks", "Mid-size private bank"),
    ("BANDHANBNK", "Private Sector Banks", "Mid-size private bank"),
    ("YESBANK", "Private Sector Banks", "Mid-size private bank"),
    ("RBLBANK", "Private Sector Banks", "Mid-size private bank"),
    ("IDBI", "Private Sector Banks", "RBI reclassified IDBI Bank as a private-sector bank in 2019 after LIC became majority owner"),
    ("CSBBANK", "Private Sector Banks", "Older/smaller private bank"),
    ("DCBBANK", "Private Sector Banks", "Older/smaller private bank"),
    ("SOUTHBANK", "Private Sector Banks", "Older/smaller private bank"),
    ("KTKBANK", "Private Sector Banks", "Older/smaller private bank"),
    ("TMB", "Private Sector Banks", "Older/smaller private bank (Tamilnad Mercantile Bank)"),
    ("J&KBANK", "Private Sector Banks", "Older/smaller private bank (Jammu & Kashmir Bank)"),
    ("DHANBANK", "Private Sector Banks", "Older/smaller private bank (Dhanlaxmi Bank)"),
    ("KARURVYSYA", "Private Sector Banks", "Older/smaller private bank (Karur Vysya Bank)"),
    ("CUB", "Private Sector Banks", "Older/smaller private bank (City Union Bank)"),

    # --- Public Sector Banks (12) ---
    ("SBIN", "Public Sector Banks", "PSU bank (State Bank of India)"),
    ("PNB", "Public Sector Banks", "PSU bank (Punjab National Bank)"),
    ("BANKBARODA", "Public Sector Banks", "PSU bank (Bank of Baroda)"),
    ("CANBK", "Public Sector Banks", "PSU bank (Canara Bank)"),
    ("UNIONBANK", "Public Sector Banks", "PSU bank (Union Bank of India)"),
    ("INDIANB", "Public Sector Banks", "PSU bank (Indian Bank)"),
    ("BANKINDIA", "Public Sector Banks", "PSU bank (Bank of India)"),
    ("CENTRALBK", "Public Sector Banks", "PSU bank (Central Bank of India)"),
    ("IOB", "Public Sector Banks", "PSU bank (Indian Overseas Bank)"),
    ("UCOBANK", "Public Sector Banks", "PSU bank (UCO Bank)"),
    ("MAHABANK", "Public Sector Banks", "PSU bank (Bank of Maharashtra)"),
    ("PSB", "Public Sector Banks", "PSU bank (Punjab & Sind Bank)"),

    # --- Small Finance Banks (6) ---
    ("AUBANK", "Small Finance Banks", "Small finance bank (AU)"),
    ("EQUITASBNK", "Small Finance Banks", "Small finance bank (Equitas)"),
    ("UJJIVANSFB", "Small Finance Banks", "Small finance bank (Ujjivan)"),
    ("JSFB", "Small Finance Banks", "Small finance bank (Jana)"),
    ("UTKARSHBNK", "Small Finance Banks", "Small finance bank (Utkarsh)"),
    ("ESAFSFB", "Small Finance Banks", "Small finance bank (ESAF)"),
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


def get_or_create_industry(supabase, cache: dict, name: str, sector_id: int, market: str) -> int:
    key = (name.strip().lower(), sector_id)
    if key in cache:
        return cache[key]
    res = supabase.table("industries").upsert(
        {"name": name, "sector_id": sector_id, "market": market, "is_diversified": False},
        on_conflict="name,sector_id,market",
    ).execute()
    iid = res.data[0]["industry_id"]
    cache[key] = iid
    print(f"  + industry ready: {name} (id {iid})")
    return iid


def main():
    supabase = get_client()
    sector_cache, industry_cache = {}, {}

    print("Populating sector_industry_ticker_overrides for 38 bank tickers...")
    for ticker, corr_industry, note in BANK_TICKER_OVERRIDES:
        supabase.table("sector_industry_ticker_overrides").upsert({
            "ticker": ticker, "market": MARKET,
            "corrected_sector_name": SECTOR_NAME, "corrected_industry_name": corr_industry,
            "is_diversified": False, "note": note,
        }, on_conflict="ticker,market").execute()
    print(f"  {len(BANK_TICKER_OVERRIDES)} ticker overrides upserted.")

    print("\nApplying to each bank's asset row...")
    financial_services_sector_id = get_or_create_sector(supabase, sector_cache, SECTOR_NAME)

    updated, missing = 0, []
    for ticker, corr_industry, _note in BANK_TICKER_OVERRIDES:
        asset = (
            supabase.table("assets")
            .select("asset_id, ticker")
            .eq("ticker", ticker).eq("market", MARKET).eq("asset_type", "equity")
            .limit(1).execute().data
        )
        if not asset:
            missing.append(ticker)
            print(f"  {ticker}: NOT FOUND in assets table -- skipped")
            continue
        industry_id = get_or_create_industry(supabase, industry_cache, corr_industry, financial_services_sector_id, MARKET)
        supabase.table("assets").update({
            "sector_id": financial_services_sector_id,
            "industry_id": industry_id,
            "sector_source": "manual",
        }).eq("asset_id", asset[0]["asset_id"]).execute()
        updated += 1
        print(f"  {ticker}: -> {corr_industry}")

    print(f"\nDone. {updated} bank stocks reclassified into Private Sector Banks / "
          f"Public Sector Banks / Small Finance Banks, all marked sector_source='manual' "
          f"so they are protected from being silently re-merged by a future sync.")
    if missing:
        print(f"\n{len(missing)} ticker(s) not found in assets table (check spelling/listing "
              f"status): {', '.join(missing)}")


if __name__ == "__main__":
    main()
