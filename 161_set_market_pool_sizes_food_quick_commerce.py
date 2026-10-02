"""
161_set_market_pool_sizes_food_quick_commerce.py
-------------------------------------------------------------------
Fills in the "market pool" total size for the two pilot Value Chain
category nodes seeded in 159_seed_value_chain_pilot_food_delivery.py
(Food Delivery, Quick Commerce). These are market_size_is_manual=True
nodes -- their market size is meant to cover the WHOLE market
(including unlisted/unorganized players), not just the sum of the
listed-company nodes beneath them, so it has to be entered by hand
rather than rolled up automatically.

IMPORTANT -- these are Claude's own estimates, not sourced numbers:
web research for "India food delivery / quick commerce market size"
turned up only paid market-research-firm press releases that disagree
with each other by 2-5x and don't show their methodology, so nothing
reliable enough to cite was found. Instead, each number below is a
blended bottom-up (known company revenues + estimate for the rest)
and top-down (implied from GOV/take-rate) estimate, landing on the
MIDPOINT of the range Avdhoot approved. The full range and "estimated,
not sourced" flag are written into the `notes` column so this is never
mistaken for a verified figure later -- replace these with real
numbers the moment a trustworthy source (or Avdhoot's own call) is
available.

Food Delivery, FY2025:
  - Range: Rs 16,000 - 17,500 Cr -> midpoint Rs 16,750 Cr
  - Past 3yr growth range: 18-20% -> midpoint 19%
  - Next 3yr projected range: 14-17% -> midpoint 15.5%
  - Sanity check: sum of current listed children (Eternal 9,418 +
    Swiggy 6,362 = 15,780 Cr) is comfortably below this, as required.

Quick Commerce, FY2025:
  - Range: Rs 19,500 - 21,500 Cr -> midpoint Rs 20,500 Cr
  - Past 3yr growth range: 80-90% -> midpoint 85%
  - Next 3yr projected range: 40-50% -> midpoint 45%
  - Sanity check: sum of current listed children (Blinkit 5,206 +
    Instamart 2,129.58 + Zepto 11,110 = 18,445.58 Cr) is below this,
    as required -- though see the flag below.

KNOWN DATA-QUALITY FLAG (not fixed by this script): Zepto's 11,110 Cr
figure looks like it may be GMV, not net revenue, given its size
relative to Blinkit at a similar operating scale. Worth revisiting
separately before trusting Quick Commerce's children sum too closely.

Run manually:
    python 161_set_market_pool_sizes_food_quick_commerce.py
-------------------------------------------------------------------
"""
from db_client import get_client

PERIOD = "FY2025"
AS_OF = "2025-03-31"

MARKET_POOLS = [
    {
        "slug": "food-delivery",
        "revenue": 16750,
        "past_3yr_cagr": 19.0,
        "next_3yr_projected_growth": 15.5,
        "notes": (
            "Claude estimate (bottom-up + top-down blend), not a sourced "
            "figure -- approved range Rs 16,000-17,500 Cr, midpoint used. "
            "No reliable third-party market-size source found; replace "
            "when a trustworthy number is available."
        ),
    },
    {
        "slug": "quick-commerce",
        "revenue": 20500,
        "past_3yr_cagr": 85.0,
        "next_3yr_projected_growth": 45.0,
        "notes": (
            "Claude estimate (bottom-up + top-down blend), not a sourced "
            "figure -- approved range Rs 19,500-21,500 Cr, midpoint used. "
            "No reliable third-party market-size source found; replace "
            "when a trustworthy number is available. NOTE: Zepto's "
            "revenue figure on this tree may actually be GMV, not net "
            "revenue -- worth a separate review."
        ),
    },
]


def main():
    supabase = get_client()

    for pool in MARKET_POOLS:
        node_res = (
            supabase.table("value_chain_nodes")
            .select("node_id, name, market_size_is_manual")
            .eq("slug", pool["slug"])
            .eq("market", "india")
            .execute()
        )
        if not node_res.data:
            print(f"  ! {pool['slug']}: node not found -- skipped")
            continue
        node = node_res.data[0]
        node_id = node["node_id"]

        if not node.get("market_size_is_manual"):
            print(f"  ! {pool['slug']}: market_size_is_manual is False on this node -- expected True, skipping to avoid overwriting an auto-rollup node by mistake")
            continue

        supabase.table("value_chain_node_financials").upsert(
            {
                "node_id": node_id,
                "period_label": PERIOD,
                "as_of_date": AS_OF,
                "revenue": pool["revenue"],
                "revenue_pct_of_company_total": None,
                "past_3yr_cagr": pool["past_3yr_cagr"],
                "next_3yr_projected_growth": pool["next_3yr_projected_growth"],
                "data_source": "claude_estimate",
                "notes": pool["notes"],
            },
            on_conflict="node_id,period_label",
        ).execute()
        print(f"  {node['name']}: market size set to Rs {pool['revenue']:,} Cr (past 3yr {pool['past_3yr_cagr']}%, next 3yr {pool['next_3yr_projected_growth']}%)")

    print("\nDone. Re-run 160_calculate_value_chain_index.py if you want the index job to pick up the refreshed rollups.")


if __name__ == "__main__":
    main()
