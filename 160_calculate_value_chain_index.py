"""
160_calculate_value_chain_index.py
-------------------------------------------------------------------
Daily job (same cadence as the main TrueScore pipeline, per Avdhoot's
call) that computes, for every node in the Value Chain tree:
  - revenue rollup (category nodes = sum of children; market_pool
    nodes keep whatever was typed in by hand -- never overwritten here)
  - index_value (rebased to 100 on a node's first run, then compounded
    daily using each contributing LISTED company's own day_change_pct)
  - weighted_truescore (same weighting)

Weighting rule (Avdhoot's formula): for a company node, weight =
(that node's revenue_pct_of_company_total) x (that company's market
cap). This weight is computed ONCE per company-node (it doesn't change
as you walk up the tree) -- a node higher up just averages across every
company-type node in its whole subtree using these same weights.
Unlisted companies and "Others/Unorganized" nodes are shown on the
page but never enter this average (no market cap to weight by).

Safe to re-run for the same day (upserts by (node_id, run_date)).

Run manually (or add to a daily GitHub Actions workflow once Avdhoot
is happy with it -- not wired into a .yml yet, this is the pilot run):
    python 160_calculate_value_chain_index.py
-------------------------------------------------------------------
"""
import datetime

from db_client import get_client

MARKET = "india"


def main():
    supabase = get_client()
    today = datetime.date.today().isoformat()

    nodes = supabase.table("value_chain_nodes").select("*").eq("market", MARKET).execute().data
    by_parent: dict = {}
    by_id = {n["node_id"]: n for n in nodes}
    for n in nodes:
        by_parent.setdefault(n["parent_node_id"], []).append(n)

    # Latest financials per node (most recent period_label by as_of_date).
    fin_rows = supabase.table("value_chain_node_financials").select("*").execute().data
    latest_fin: dict = {}
    for r in fin_rows:
        existing = latest_fin.get(r["node_id"])
        if existing is None or r["as_of_date"] > existing["as_of_date"]:
            latest_fin[r["node_id"]] = r

    # Market cap + day change + TrueScore for every company-node's asset.
    asset_ids = [n["asset_id"] for n in nodes if n["node_type"] == "company" and n.get("asset_id")]
    market_cap_by_asset, day_change_by_asset, truescore_by_asset = {}, {}, {}
    if asset_ids:
        ratios = (
            supabase.table("ratios_snapshot").select("asset_id, market_cap, as_of_date")
            .in_("asset_id", asset_ids).order("as_of_date", desc=True).execute().data
        )
        for r in ratios:
            market_cap_by_asset.setdefault(r["asset_id"], r["market_cap"])

        live = supabase.table("live_prices").select("asset_id, day_change_pct").in_("asset_id", asset_ids).execute().data
        for r in live:
            day_change_by_asset[r["asset_id"]] = r["day_change_pct"]

        scores = (
            supabase.table("scores").select("asset_id, overall_score, run_date")
            .in_("asset_id", asset_ids).order("run_date", desc=True).execute().data
        )
        for r in scores:
            truescore_by_asset.setdefault(r["asset_id"], r["overall_score"])

    # Step 1: compute each company-node's OWN weight (revenue_pct x market_cap).
    # This never changes as we walk up the tree.
    company_weight: dict = {}
    for n in nodes:
        if n["node_type"] != "company" or not n.get("asset_id"):
            continue
        fin = latest_fin.get(n["node_id"])
        pct = fin.get("revenue_pct_of_company_total") if fin else None
        cap = market_cap_by_asset.get(n["asset_id"])
        if pct is not None and cap is not None:
            company_weight[n["node_id"]] = {
                "weight": float(pct) * float(cap),
                "day_change_pct": day_change_by_asset.get(n["asset_id"]),
                "truescore": truescore_by_asset.get(n["asset_id"]),
            }

    # Step 2: for every node, find every company-type node in its subtree.
    def collect_company_descendants(node_id):
        result = []
        for child in by_parent.get(node_id, []):
            if child["node_type"] == "company":
                result.append(child["node_id"])
            result.extend(collect_company_descendants(child["node_id"]))
        return result

    # Step 3: revenue rollup (bottom-up), skipping market_pool nodes (manual).
    def rollup_node(node_id):
        """Returns (revenue, past_3yr_cagr, next_3yr_projected_growth) for a
        node -- revenue is a straight sum of children, growth figures are
        revenue-weighted averages of children's growth (bigger pieces of
        the business move the number more, same idea as the market-cap
        weighting used for the Index itself).

        Manual nodes (market pools, e.g. "Food Delivery") carry their own
        admin-entered revenue/growth -- that IS this node's contribution
        to a parent's rollup; never recompute it from children. BUG FIX
        (Session 40): this used to discard a manual node's value entirely
        when used as an input to its PARENT's rollup, which silently
        dropped Food Delivery / Quick Commerce out of the Industry and
        Sector totals above them (both ended up with no revenue/growth
        row at all).
        """
        node = by_id[node_id]
        if node["market_size_is_manual"]:
            fin = latest_fin.get(node_id)
            if fin and fin.get("revenue") is not None:
                return float(fin["revenue"]), fin.get("past_3yr_cagr"), fin.get("next_3yr_projected_growth")
            return None, None, None

        children = by_parent.get(node_id, [])
        if not children:
            fin = latest_fin.get(node_id)
            if fin and fin.get("revenue") is not None:
                return float(fin["revenue"]), fin.get("past_3yr_cagr"), fin.get("next_3yr_projected_growth")
            return None, None, None

        total_rev = 0.0
        past_weighted, past_weight = 0.0, 0.0
        next_weighted, next_weight = 0.0, 0.0
        any_rev = False
        for c in children:
            rev, past, nxt = rollup_node(c["node_id"])
            if rev is None:
                continue
            total_rev += rev
            any_rev = True
            if past is not None:
                past_weighted += rev * past
                past_weight += rev
            if nxt is not None:
                next_weighted += rev * nxt
                next_weight += rev

        if not any_rev:
            return None, None, None
        past_cagr = (past_weighted / past_weight) if past_weight > 0 else None
        next_growth = (next_weighted / next_weight) if next_weight > 0 else None
        return total_rev, past_cagr, next_growth

    updated = 0
    for n in nodes:
        descendants = collect_company_descendants(n["node_id"]) if n["node_type"] != "company" else [n["node_id"]]
        weighted = [company_weight[d] for d in descendants if d in company_weight]
        total_weight = sum(w["weight"] for w in weighted)

        if total_weight > 0:
            day_change = sum(w["weight"] * (w["day_change_pct"] or 0) for w in weighted) / total_weight
            truescore = sum(w["weight"] * (w["truescore"] or 0) for w in weighted) / total_weight

            prev = (
                supabase.table("value_chain_node_index").select("index_value")
                .eq("node_id", n["node_id"]).order("run_date", desc=True).limit(1).execute().data
            )
            prev_value = float(prev[0]["index_value"]) if prev else 100.0
            index_value = prev_value * (1 + day_change / 100.0)

            supabase.table("value_chain_node_index").upsert({
                "node_id": n["node_id"], "run_date": today,
                "index_value": round(index_value, 4), "day_change_pct": round(day_change, 4),
                "weighted_truescore": round(truescore, 2), "constituent_count": len(weighted),
            }, on_conflict="node_id,run_date").execute()
            updated += 1

        # Revenue + growth rollup for category nodes (not market_pool, not company).
        if n["node_type"] not in ("company", "market_pool") and not n["market_size_is_manual"]:
            rev, past_cagr, next_growth = rollup_node(n["node_id"])
            if rev is not None:
                supabase.table("value_chain_node_financials").upsert({
                    "node_id": n["node_id"], "period_label": "rollup-latest", "as_of_date": today,
                    "revenue": round(rev, 2),
                    "past_3yr_cagr": round(past_cagr, 2) if past_cagr is not None else None,
                    "next_3yr_projected_growth": round(next_growth, 2) if next_growth is not None else None,
                    "data_source": "computed",
                    "notes": "Auto-summed from children by 160_calculate_value_chain_index.py (revenue: sum of children; growth: revenue-weighted average of children's growth)",
                }, on_conflict="node_id,period_label").execute()

    print(f"Done. {updated} nodes had an index computed today ({today}). "
          f"{len(nodes) - updated} nodes had no listed-company descendants with both revenue% and market cap on file yet.")


if __name__ == "__main__":
    main()
