"""
89_manual_sector_overrides.py
-------------------------------------------------------------------
Manual sector assignment for the small number of stocks Yahoo Finance
genuinely has no sector data for, even after 87's retry pass. Reviewed
by hand (company name/business looked up individually), NOT another
automated guess -- Avdhoot explicitly asked for this after seeing the
final Unclassified list.

Uses the exact same sector NAME strings Yahoo Finance's own taxonomy
uses elsewhere in this project (Industrials, Real Estate, Consumer
Cyclical, Financial Services, Basic Materials, Consumer Defensive) so
these stocks land in the SAME sector rows the automated script already
created -- not new one-off sector names.

3 stocks are deliberately NOT included here and will stay Unclassified:
DHATRE (Dhatre Udyog Limited), JAYKAY-RE1 (Jaykay Enterprises
Limited-RE), and TCC (TCC Concept Limited) -- their names are too
generic to confidently identify their actual business from public
knowledge alone. Leaving 3 stocks out of 2,068 honestly Unclassified
is a fine outcome; guessing wrong and quietly asserting it as fact
would not be.

Run manually:
    python 89_manual_sector_overrides.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"

# ticker -> Yahoo-Finance-style sector name
MANUAL_SECTORS = {
    "3PLAND": "Real Estate",
    "AARNAV": "Consumer Cyclical",       # Aarnav Fashions -- apparel
    "ARTEMISMED": "Healthcare",           # Artemis Hospitals, Gurgaon
    "AUSTENG": "Industrials",             # Austin Engineering
    "DISAQ": "Industrials",               # Disa India -- foundry/moulding machinery
    "ELCIDIN": "Financial Services",      # EL CID Investments
    "ELPROINTL": "Industrials",           # Elpro International -- electrical/industrial products
    "GUJRAFFIA": "Basic Materials",       # Gujarat Raffia -- polypropylene woven sacks/packaging
    "HBESD": "Real Estate",               # HB Estate Developers
    "KAMANWALA": "Real Estate",           # Kamanwala Housing Construction
    "MAFATIND": "Consumer Cyclical",      # Mafatlal Industries -- textiles
    "NIMBSPROJ": "Real Estate",           # Nimbus Projects
    "RAJPALAYAM": "Consumer Cyclical",    # Rajapalayam Mills -- cotton textiles
    "SHRIKRISH": "Real Estate",           # Shri Krishna Devcon
    "SINGERIND": "Consumer Cyclical",     # Singer India -- consumer durables/sewing machines
    "TANAA": "Industrials",               # Taneja Aerospace & Aviation
    "VIJSOLX": "Consumer Defensive",      # Vijay Solvex -- edible oil/solvent extraction
    "ZODIAC": "Industrials",              # Zodiac Energy -- solar EPC contractor, not a utility
}

# Deliberately left Unclassified -- too generic to identify confidently:
#   DHATRE (Dhatre Udyog Limited)
#   JAYKAY-RE1 (Jaykay Enterprises Limited-RE)
#   TCC (TCC Concept Limited)


def get_or_create_sector(supabase, sector_cache: dict, name: str) -> int:
    key = name.strip().lower()
    if key in sector_cache:
        return sector_cache[key]
    res = supabase.table("sectors").upsert(
        {"name": name, "market": MARKET}, on_conflict="name,market"
    ).execute()
    sector_id = res.data[0]["sector_id"]
    sector_cache[key] = sector_id
    return sector_id


def main():
    supabase = get_client()
    existing_sectors = (
        supabase.table("sectors").select("sector_id, name").eq("market", MARKET).execute()
    ).data
    sector_cache = {s["name"].strip().lower(): s["sector_id"] for s in existing_sectors}

    ok_count = 0
    failed = []
    for ticker, sector_name in MANUAL_SECTORS.items():
        try:
            sector_id = get_or_create_sector(supabase, sector_cache, sector_name)
            res = (
                supabase.table("assets")
                .update({"sector_id": sector_id})
                .eq("ticker", ticker)
                .eq("asset_type", "equity")
                .eq("market", MARKET)
                .execute()
            )
            if res.data:
                ok_count += 1
                print(f"  {ticker}: -> {sector_name}")
            else:
                print(f"  ! {ticker}: not found in assets -- skipped")
                failed.append(ticker)
        except Exception as e:
            print(f"  ! {ticker}: FAILED -- {e}")
            failed.append(ticker)

    print(f"\nDone. {ok_count}/{len(MANUAL_SECTORS)} stocks manually assigned a sector.")
    print(f"Failed: {failed if failed else 'none'}")
    print("\nStill Unclassified (deliberately, per this script's own notes): DHATRE, JAYKAY-RE1, TCC")


if __name__ == "__main__":
    main()
