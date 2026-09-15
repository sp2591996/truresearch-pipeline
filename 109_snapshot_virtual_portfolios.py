"""
109_snapshot_virtual_portfolios.py
-------------------------------------------------------------------
Gamified virtual investing (next-phase item 3) -- Avdhoot asked for
daily/weekly/overall portfolio change. Overall change is a simple
subtraction the frontend can already do live (today's value minus
starting cash), but daily/weekly change needs to know what a
player's portfolio was worth on a PAST date -- nothing on the site
remembers that by itself. This script is what fixes that: once a
day, for every player, it adds up their wallet cash + the live INR
value of everything they hold, and saves one row into
virtual_portfolio_snapshots for today's date. Over time this builds
a daily history the frontend can look back through.

Same currency-conversion rule as the frontend's lib/virtualPortfolio.ts
(deriveTradeMarket): a commodity (WTICRUDE/BRENTCRUDE/NATGAS) is
USD-priced regardless of its `market` column; an equity's `market`
column (india/usa) says which currency it's actually priced in;
everything else (gold/silver/fx) is already INR. Kept in sync with
that file deliberately -- if the rule ever changes there, it must
change here too.

Safe to re-run: upserts on (user_id, snapshot_date), so running this
twice on the same day just overwrites with a fresher number instead
of creating a duplicate row.

Run manually:
    python 109_snapshot_virtual_portfolios.py
-------------------------------------------------------------------
"""
from datetime import datetime, timezone

from db_client import get_client
from ingestion_log import start_run, finish_run


def get_usd_inr_rate(supabase) -> float | None:
    fx_asset = (
        supabase.table("assets").select("asset_id").eq("ticker", "USDINR").maybe_single().execute()
    ).data
    if not fx_asset:
        return None
    price_row = (
        supabase.table("live_prices").select("price").eq("asset_id", fx_asset["asset_id"]).maybe_single().execute()
    ).data
    return price_row["price"] if price_row and price_row.get("price") else None


def derive_trade_market(asset_type: str | None, assets_market_column: str | None) -> str:
    """Mirrors deriveTradeMarket() in trueresearch-frontend/lib/virtualPortfolio.ts -- keep both in sync."""
    if asset_type == "commodity":
        return "usa"
    if asset_type == "equity":
        return "usa" if assets_market_column == "usa" else "india"
    return "india"


def main():
    supabase = get_client()
    run_id = start_run("virtual_portfolio_snapshot")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    wallets = supabase.table("virtual_wallets").select("user_id, cash_balance_inr").execute().data or []
    if not wallets:
        finish_run(run_id, 0, [])
        print("No virtual wallets yet -- nothing to snapshot.")
        return

    # Fetched once, reused for every player -- not per-user, since
    # asset prices and the FX rate don't change per player.
    usd_inr_rate = get_usd_inr_rate(supabase)

    ok_count = 0
    failed: list[str] = []

    for wallet in wallets:
        user_id = wallet["user_id"]
        try:
            holdings = (
                supabase.table("virtual_holdings").select("asset_id, units").eq("user_id", user_id).execute()
            ).data or []

            holdings_value_inr = 0.0
            if holdings:
                asset_ids = [h["asset_id"] for h in holdings]
                assets = (
                    supabase.table("assets").select("asset_id, asset_type, market").in_("asset_id", asset_ids).execute()
                ).data or []
                assets_by_id = {a["asset_id"]: a for a in assets}
                prices = (
                    supabase.table("live_prices").select("asset_id, price").in_("asset_id", asset_ids).execute()
                ).data or []
                price_by_id = {p["asset_id"]: p["price"] for p in prices}

                for h in holdings:
                    asset = assets_by_id.get(h["asset_id"])
                    price_native = price_by_id.get(h["asset_id"])
                    if not asset or price_native is None:
                        continue
                    market = derive_trade_market(asset.get("asset_type"), asset.get("market"))
                    if market == "usa":
                        if not usd_inr_rate:
                            continue  # can't value this holding today without a rate -- skip rather than guess
                        holdings_value_inr += h["units"] * price_native * usd_inr_rate
                    else:
                        holdings_value_inr += h["units"] * price_native

            cash_balance_inr = wallet["cash_balance_inr"]
            total_value_inr = cash_balance_inr + holdings_value_inr

            supabase.table("virtual_portfolio_snapshots").upsert({
                "user_id": user_id,
                "snapshot_date": today,
                "cash_balance_inr": cash_balance_inr,
                "holdings_value_inr": holdings_value_inr,
                "total_value_inr": total_value_inr,
            }, on_conflict="user_id,snapshot_date").execute()
            ok_count += 1
        except Exception as e:
            failed.append(f"{user_id} (snapshot failed: {e})")
            continue

    finish_run(run_id, ok_count, failed)
    print(f"Done. {ok_count}/{len(wallets)} players snapshotted for {today}. Failed: {failed if failed else 'none'}")


if __name__ == "__main__":
    main()
