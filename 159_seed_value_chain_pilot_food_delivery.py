"""
159_seed_value_chain_pilot_food_delivery.py
-------------------------------------------------------------------
Pilot Value Chain tree for Food Delivery & Quick Commerce, built from
real FY2025 public filings (sources noted inline) -- for Avdhoot to
review/correct before this pattern is repeated across other sectors.

Tree:
  Consumer Services (Sector, existing)
   -> Food & Quick Commerce (Industry, new value-chain-specific grouping)
       -> Food Delivery (market_pool)
           -> Eternal (Zomato) -- Food Delivery   [company]
           -> Swiggy -- Food Delivery             [company]
           -> Rapido -- Food Delivery             [company, unlisted]
           -> Others / Unorganized                [unlisted_other]
       -> Quick Commerce (market_pool)
           -> Eternal (Blinkit)                   [company]
           -> Swiggy -- Instamart                 [company]
           -> Zepto                               [company, unlisted]

Revenue figures (FY2025, i.e. year ended March 2025), all INR crore:
  Eternal (Zomato) -- "Adjusted Revenue" by segment, from FY25 Annual
    Report (via medianama.com summary): Food Delivery 9,418;
    Blinkit (Quick Commerce) 5,206; Total company revenue 20,243.
    NOTE: "Adjusted Revenue" is Eternal's own segment metric and may
    not tie exactly to statutory consolidated revenue -- flagged as
    an honest limitation, not hidden.
  Swiggy -- actual segment REVENUE (not GOV) from the Q4 FY25
    Shareholder Letter: Food Delivery 6,361.72; Quick Commerce
    (Instamart) 2,129.58; Total company revenue 15,226.76.
  Rapido -- unlisted. FY25 total income crossed ~1,000 crore (mixed
    ride-hailing + delivery, exact delivery-only split not publicly
    broken out as of this writing) -- entered as a rough placeholder,
    clearly marked estimated, not precise.
  Zepto -- unlisted, pure quick commerce. FY25 revenue ~11,110 crore.

This script is safe to re-run (upserts).

Run manually:
    python 159_seed_value_chain_pilot_food_delivery.py
-------------------------------------------------------------------
"""
from db_client import get_client

MARKET = "india"
PERIOD = "FY2025"
AS_OF = "2025-03-31"


def get_sector_id(supabase, name):
    r = supabase.table("sectors").select("sector_id").eq("name", name).execute().data
    if not r:
        raise SystemExit(f"Sector '{name}' not found -- run the sector/industry cleanup first.")
    return r[0]["sector_id"]


def get_asset_id(supabase, ticker):
    r = supabase.table("assets").select("asset_id").eq("ticker", ticker).eq("market", MARKET).eq("asset_type", "equity").execute().data
    return r[0]["asset_id"] if r else None


def upsert_node(supabase, parent_id, root_sector_id, node_type, name, slug, asset_id=None, market_size_is_manual=False, display_order=0):
    existing = (
        supabase.table("value_chain_nodes").select("node_id")
        .eq("slug", slug).eq("market", MARKET)
        .execute().data
    )
    payload = {
        "parent_node_id": parent_id, "root_sector_id": root_sector_id, "market": MARKET,
        "node_type": node_type, "name": name, "slug": slug, "asset_id": asset_id,
        "market_size_is_manual": market_size_is_manual, "display_order": display_order,
    }
    if existing:
        node_id = existing[0]["node_id"]
        supabase.table("value_chain_nodes").update(payload).eq("node_id", node_id).execute()
    else:
        node_id = supabase.table("value_chain_nodes").insert(payload).execute().data[0]["node_id"]
    return node_id


def set_financials(supabase, node_id, revenue, pct_of_company_total=None, source="reported", notes=None):
    supabase.table("value_chain_node_financials").upsert({
        "node_id": node_id, "period_label": PERIOD, "as_of_date": AS_OF,
        "revenue": revenue, "revenue_pct_of_company_total": pct_of_company_total,
        "data_source": source, "notes": notes,
    }, on_conflict="node_id,period_label").execute()


def main():
    supabase = get_client()
    sector_id = get_sector_id(supabase, "Consumer Services")

    sector_node = upsert_node(supabase, None, sector_id, "sector", "Consumer Services", "consumer-services")
    industry_node = upsert_node(supabase, sector_node, sector_id, "industry", "Food & Quick Commerce", "food-quick-commerce")

    food_delivery = upsert_node(supabase, industry_node, sector_id, "market_pool", "Food Delivery", "food-delivery", market_size_is_manual=True, display_order=1)
    quick_commerce = upsert_node(supabase, industry_node, sector_id, "market_pool", "Quick Commerce", "quick-commerce", market_size_is_manual=True, display_order=2)

    # -- Food Delivery companies --
    eternal_id = get_asset_id(supabase, "ETERNAL")
    swiggy_id = get_asset_id(supabase, "SWIGGY")

    n = upsert_node(supabase, food_delivery, sector_id, "company", "Eternal (Zomato) — Food Delivery", "eternal-food-delivery", asset_id=eternal_id, display_order=1)
    set_financials(supabase, n, revenue=9418, pct_of_company_total=round(9418 / 20243, 4), source="reported",
                    notes="FY25 'Adjusted Revenue' per Eternal's annual report segment disclosure (may not tie exactly to statutory consolidated revenue).")

    n = upsert_node(supabase, food_delivery, sector_id, "company", "Swiggy — Food Delivery", "swiggy-food-delivery", asset_id=swiggy_id, display_order=2)
    set_financials(supabase, n, revenue=6361.72, pct_of_company_total=round(6361.72 / 15226.76, 4), source="reported",
                    notes="FY25 segment revenue (not GOV) per Swiggy's Q4 FY25 Shareholder Letter.")

    n = upsert_node(supabase, food_delivery, sector_id, "company", "Rapido — Food Delivery", "rapido-food-delivery", asset_id=None, display_order=3)
    set_financials(supabase, n, revenue=None, pct_of_company_total=None, source="estimated",
                    notes="Unlisted. FY25 total income crossed ~INR 1,000 Cr (ride-hailing + delivery combined) per press reports; delivery-only revenue not separately disclosed as of this writing -- left blank rather than guessed.")

    n = upsert_node(supabase, food_delivery, sector_id, "unlisted_other", "Others / Unorganized", "food-delivery-others", display_order=4)
    set_financials(supabase, n, revenue=None, source="estimated", notes="Placeholder for smaller/local food delivery players not individually tracked -- needs a market-size estimate from Avdhoot or a research pass.")

    # -- Quick Commerce companies --
    n = upsert_node(supabase, quick_commerce, sector_id, "company", "Eternal (Blinkit)", "eternal-blinkit", asset_id=eternal_id, display_order=1)
    set_financials(supabase, n, revenue=5206, pct_of_company_total=round(5206 / 20243, 4), source="reported",
                    notes="FY25 'Adjusted Revenue' per Eternal's annual report segment disclosure.")

    n = upsert_node(supabase, quick_commerce, sector_id, "company", "Swiggy — Instamart", "swiggy-instamart", asset_id=swiggy_id, display_order=2)
    set_financials(supabase, n, revenue=2129.58, pct_of_company_total=round(2129.58 / 15226.76, 4), source="reported",
                    notes="FY25 segment revenue (not GOV) per Swiggy's Q4 FY25 Shareholder Letter.")

    n = upsert_node(supabase, quick_commerce, sector_id, "company", "Zepto", "zepto-quick-commerce", asset_id=None, display_order=3)
    set_financials(supabase, n, revenue=11110, pct_of_company_total=1.0, source="estimated",
                    notes="Unlisted, pure-play quick commerce -- FY25 revenue ~INR 11,110 Cr per press reports (Entrackr/Business Standard), not an audited figure TrueResearch has independently verified.")

    print("Pilot Food Delivery / Quick Commerce tree seeded.")
    print(f"Sector node: {sector_node}, Industry node: {industry_node}")
    print(f"Food Delivery node: {food_delivery}, Quick Commerce node: {quick_commerce}")
    print("\nNOTE: Food Delivery / Quick Commerce 'market pool' total size still needs Avdhoot's "
          "input (or a further research pass) to account for the unlisted/unorganized portion -- "
          "left blank, not guessed.")


if __name__ == "__main__":
    main()
