"""
run_value_chain_seed.py
-------------------------------------------------------------------
The ONE reusable script for seeding/updating Value Chain industries
and companies from the data files in value_chain_data/. Replaces the
old pattern of writing a brand-new numbered script per company
(162-169) -- that was filling up the folder and making real one-off
migration scripts hard to find. Going forward:
  - Claude edits/extends a file in value_chain_data/ (e.g. adds a new
    industry, or new companies to an existing one)
  - Avdhoot just re-runs THIS SAME script -- safe to run repeatedly,
    always upserts (updates if a node/slug already exists, inserts if
    not), never duplicates.

Currently wired up: value_chain_data/consumer_services.py (Consumer
Services sector, India) -- which now ALSO covers Food Delivery &
Quick Commerce (folded in here round 5, replacing the old standalone
159_seed_value_chain_pilot_food_delivery.py script -- see
consumer_services.py's header). More sector data files can be added
to the SECTOR_DATA_MODULES list below as other sectors get built out.

Run manually any time the data files change:
    python run_value_chain_seed.py
-------------------------------------------------------------------
"""
from collections import defaultdict

from db_client import get_client
from value_chain_data import consumer_services

MARKET = "india"

# Add future sector data modules here as they're built (e.g. financial_services, etc.)
SECTOR_DATA_MODULES = [
    ("consumer-services", consumer_services),
]


def upsert_node(supabase, cache, *, parent_id, root_sector_id, node_type, name, slug, asset_id=None, market_size_is_manual=False, display_order=0):
    if slug in cache:
        return cache[slug]
    payload = {
        "parent_node_id": parent_id, "root_sector_id": root_sector_id, "market": MARKET,
        "node_type": node_type, "name": name, "slug": slug, "asset_id": asset_id,
        "market_size_is_manual": market_size_is_manual, "display_order": display_order,
    }
    existing = supabase.table("value_chain_nodes").select("node_id").eq("slug", slug).eq("market", MARKET).execute().data
    if existing:
        node_id = existing[0]["node_id"]
        supabase.table("value_chain_nodes").update(payload).eq("node_id", node_id).execute()
    else:
        node_id = supabase.table("value_chain_nodes").insert(payload).execute().data[0]["node_id"]
    cache[slug] = node_id
    return node_id


def set_financials(supabase, node_id, *, period, as_of, revenue, pct, past_cagr, next_growth, source, notes,
                    market_size_min=None, market_size_max=None):
    supabase.table("value_chain_node_financials").upsert(
        {
            "node_id": node_id, "period_label": period, "as_of_date": as_of,
            "revenue": revenue, "revenue_pct_of_company_total": pct,
            "past_3yr_cagr": past_cagr, "next_3yr_projected_growth": next_growth,
            "data_source": source, "notes": notes,
            "market_size_min": market_size_min, "market_size_max": market_size_max,
        },
        on_conflict="node_id,period_label",
    ).execute()


def main():
    supabase = get_client()
    cache = {}

    for sector_slug, module in SECTOR_DATA_MODULES:
        sector = supabase.table("value_chain_nodes").select("node_id, root_sector_id").eq("slug", sector_slug).eq("market", MARKET).execute().data
        if not sector:
            print(f"! Sector node '{sector_slug}' not found -- skipping {module.__name__}.")
            continue
        sector_id, root_sector_id = sector[0]["node_id"], sector[0]["root_sector_id"]
        cache[sector_slug] = sector_id

        # Resolve every ticker used in this module in one query. Companies
        # now sit under a "stages" layer (value_chain_stage nodes) inside
        # each industry, not directly under the industry -- see
        # value_chain_data/consumer_services.py's header for why.
        # Some company entries are unlisted (ticker=None, e.g. Rapido,
        # Zepto, the "Others/Unorganized" bucket) -- filter those out of
        # the ticker lookup rather than querying assets for "None".
        tickers = sorted({c["ticker"] for ind in module.INDUSTRIES for stage in ind["stages"] for c in stage["companies"] if c.get("ticker")})
        assets = supabase.table("assets").select("asset_id, ticker").in_("ticker", tickers).eq("market", MARKET).execute().data
        asset_by_ticker = {a["ticker"]: a["asset_id"] for a in assets}
        missing = [t for t in tickers if t not in asset_by_ticker]
        if missing:
            print(f"! Tickers not found in assets (check spelling): {missing}")

        print(f"\n=== {module.__name__} ===")
        for industry in module.INDUSTRIES:
            industry_id = upsert_node(
                supabase, cache, parent_id=sector_id, root_sector_id=root_sector_id,
                node_type="industry", name=industry["name"], slug=industry["slug"],
                display_order=industry.get("display_order", 0),
            )
            print(f"{industry['name']} (node_id={industry_id})")

            # Auto-compute revenue_pct_of_company_total per ticker (sum of
            # every entry sharing that ticker ACROSS THE WHOLE INDUSTRY, not
            # just within one stage -- a company's offerings can span more
            # than one stage), unless a company entry gives an explicit
            # "pct" override.
            company_totals = defaultdict(float)
            for stage in industry["stages"]:
                for c in stage["companies"]:
                    if c.get("ticker") and c.get("revenue") is not None:
                        company_totals[c["ticker"]] += c["revenue"]

            for s_i, stage in enumerate(industry["stages"], 1):
                # A stage can optionally give a manual total-market-size range
                # (market_size_min/max) -- meant to cover the WHOLE market,
                # including unlisted/unorganized players the "companies" list
                # below doesn't individually model. When present, the stage
                # node is marked market_size_is_manual=True so 160_calculate_
                # value_chain_index.py's rollup never overwrites it with a
                # sum-of-children figure; `revenue` on its financials row is
                # set to the range's midpoint (what rollups to the Industry
                # above use), with the full range in market_size_min/max for
                # the frontend to display as "Rs a - b Cr".
                has_market_size = stage.get("market_size_min") is not None and stage.get("market_size_max") is not None
                stage_id = upsert_node(
                    supabase, cache, parent_id=industry_id, root_sector_id=root_sector_id,
                    node_type="value_chain_stage", name=stage["name"], slug=stage["slug"],
                    display_order=stage.get("display_order", s_i),
                    market_size_is_manual=has_market_size,
                )
                print(f"  [{stage['name']}] (node_id={stage_id})")

                if has_market_size:
                    lo, hi = stage["market_size_min"], stage["market_size_max"]
                    set_financials(
                        supabase, stage_id,
                        period=module.PERIOD, as_of=module.AS_OF,
                        revenue=round((lo + hi) / 2, 2), pct=None,
                        past_cagr=stage.get("market_size_past_cagr"), next_growth=stage.get("market_size_next_growth"),
                        source=stage.get("market_size_source", "claude_estimate"), notes=stage.get("market_size_notes", ""),
                        market_size_min=lo, market_size_max=hi,
                    )
                    print(f"    [market size] Rs {lo:,} - {hi:,} Cr (midpoint {round((lo + hi) / 2, 2):,})")

                for i, c in enumerate(stage["companies"], 1):
                    asset_id = asset_by_ticker.get(c["ticker"]) if c.get("ticker") else None
                    node_id = upsert_node(
                        supabase, cache, parent_id=stage_id, root_sector_id=root_sector_id,
                        node_type=c.get("node_type", "company"), name=c["name"], slug=c["slug"], asset_id=asset_id,
                        display_order=i,
                    )
                    pct = c.get("pct")
                    if pct is None and c.get("ticker") and c.get("revenue") is not None:
                        total = company_totals[c["ticker"]]
                        pct = round(c["revenue"] / total, 4) if total else None
                    set_financials(
                        supabase, node_id,
                        period=module.PERIOD, as_of=module.AS_OF,
                        revenue=c.get("revenue"), pct=pct,
                        past_cagr=c.get("past_cagr"), next_growth=c.get("next_growth"),
                        source=c.get("source", "claude_estimate"), notes=c.get("notes", ""),
                    )
                    print(f"    {c['name']} (node_id={node_id}, revenue={c.get('revenue')}, pct={pct})")

    print("\nDone. Run 160_calculate_value_chain_index.py next to roll these up and recompute the Index.")


if __name__ == "__main__":
    main()
