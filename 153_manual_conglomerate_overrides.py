"""
153_manual_conglomerate_overrides.py
-------------------------------------------------------------------
Phase 2 (Session 39), final step: tags genuine multi-business
conglomerates as "Diversified" instead of whatever single (and
misleading) industry the automated scripts assigned them.

Avdhoot's example: Reliance Industries gets classified under "Oil &
Gas Refining & Marketing" (its Yahoo Finance industry), but its real
business is refining + petrochemicals + telecom (Jio) + retail --
comparing it 1:1 against pure refiners overstates/understates its
valuation in a way that isn't fair to either side.

Per Avdhoot's decision: each conglomerate goes into a "Diversified"
industry SCOPED TO ITS OWN SECTOR (not one single global bucket) --
e.g. Reliance -> "Diversified" under the Energy sector, ITC ->
"Diversified" under Consumer Defensive -- so it's still grouped with
other diversified players in roughly the same space, not thrown in
with, say, a diversified industrials company.

This list is a STARTING POINT, not exhaustive -- reviewed by hand,
same spirit as 89_manual_sector_overrides.py. Add more tickers here
as you spot them; this script is safe to re-run any time with an
updated list.

USA: GICS already has real sub-industries for this in many cases
("Industrial Conglomerates", "Multi-Sector Holdings"), so the US list
below is deliberately short -- only for cases GICS doesn't already
capture well.

Run manually:
    python 153_manual_conglomerate_overrides.py
-------------------------------------------------------------------
"""
from db_client import get_client

DIVERSIFIED_NAME = "Diversified"

# ticker -> market. Reviewed by hand: each of these runs multiple,
# genuinely unrelated core businesses (not just diversified within one
# industry, e.g. a bank with several loan products doesn't count).
CONGLOMERATE_TICKERS = {
    # -- India --
    "RELIANCE": "india",   # refining + petrochemicals + telecom (Jio) + retail
    "ADANIENT": "india",   # incubator for airports, green energy, mining, data centers, etc.
    "ITC": "india",        # cigarettes + FMCG/food + hotels + paperboard + agri
    "GRASIM": "india",     # cement (via UltraTech) + chemicals + textiles + financial services (via AB Capital)
    "GODREJIND": "india",  # chemicals + real estate (Godrej Properties) + agri + FMCG stakes
    "BAJAJHLDNG": "india", # pure holding company across auto (Bajaj Auto) + finance (Bajaj Finserv) -- not one operating business at all
    "TATAINVEST": "india", # Tata Group investment/holding company, same reasoning as Bajaj Holdings
    "LT": "india",         # engineering/construction + IT services (LTIMindtree stake) + financial services + defense

    # -- USA (only where GICS itself doesn't already say "conglomerate") --
    # FIX: ticker in `assets`/sp500_master.csv is "BRK.B" (BRK-B is only
    # its yfinance_symbol) -- was skipped on the first run because of this.
    # Also, GICS already tags this "Multi-Sector Holdings", which is
    # basically the same idea as Diversified -- this is a cosmetic
    # consistency fix, not correcting a real mislabeling like Reliance was.
    "BRK.B": "usa",        # Berkshire Hathaway -- insurance + railroads + energy + retail + manufacturing
}


def get_or_create_industry(supabase, industry_cache: dict, name: str, sector_id: int, market: str) -> int:
    key = (name.strip().lower(), sector_id)
    if key in industry_cache:
        return industry_cache[key]
    res = supabase.table("industries").upsert(
        {"name": name, "sector_id": sector_id, "market": market, "is_diversified": True},
        on_conflict="name,sector_id,market",
    ).execute()
    industry_id = res.data[0]["industry_id"]
    industry_cache[key] = industry_id
    return industry_id


def main():
    supabase = get_client()
    industry_cache: dict = {}

    ok_count = 0
    failed = []
    for ticker, market in CONGLOMERATE_TICKERS.items():
        asset_res = (
            supabase.table("assets")
            .select("asset_id, sector_id")
            .eq("ticker", ticker)
            .eq("asset_type", "equity")
            .eq("market", market)
            .execute()
        )
        asset = asset_res.data[0] if asset_res.data else None
        if not asset:
            print(f"  ! {ticker} ({market}): not found in assets -- skipped")
            failed.append(ticker)
            continue
        sector_id = asset.get("sector_id")
        if sector_id is None:
            print(f"  ! {ticker} ({market}): has no sector_id yet -- skipped")
            failed.append(ticker)
            continue

        try:
            industry_id = get_or_create_industry(supabase, industry_cache, DIVERSIFIED_NAME, sector_id, market)
            supabase.table("assets").update({"industry_id": industry_id}).eq("asset_id", asset["asset_id"]).execute()
            ok_count += 1
            print(f"  {ticker} ({market}): -> Diversified (sector_id={sector_id})")
        except Exception as e:
            print(f"  ! {ticker} ({market}): FAILED -- {e}")
            failed.append(ticker)

    print(f"\nDone. {ok_count}/{len(CONGLOMERATE_TICKERS)} conglomerates tagged Diversified.")
    print(f"Failed/skipped: {failed if failed else 'none'}")
    print(
        "\nThis list is a starting point -- if you spot other genuine "
        "conglomerates while browsing the site, add their ticker to "
        "CONGLOMERATE_TICKERS above and re-run this script."
    )


if __name__ == "__main__":
    main()
