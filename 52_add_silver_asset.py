"""
52_add_silver_asset.py
-------------------------------------------------------------------
PRD.md Section L5 -- Silver, under Other Assets -> Metals, mirroring
Gold's own pipeline (47_add_gold_asset.py) exactly.

Data source decision (documented here, same discipline as every other
J/L-section data-source call): SILVERBEES -- the Nippon India Silver
ETF, NSE-listed, trading in INR, closely tracking domestic silver.
Free via yfinance (yfinance_symbol="SILVERBEES.NS"), same provider
every other asset here already goes through -- no new dependency.

IMPORTANT -- run 51_add_silver_asset_type.sql in Supabase's SQL Editor
FIRST. `assets.asset_type` has a check constraint that doesn't allow
'silver' yet; this script's insert will fail until that migration runs.

What this does, safe to run more than once (upserts everywhere):
  1. Ensures the Silver asset row exists in `assets` (asset_type='silver').
  2. Backfills 10 years of daily OHLC history into `prices_daily`.
  3. Fetches today's live price + day change into `live_prices`.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 52_add_silver_asset.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

TICKER = "SILVER"
NAME = "Silver (via Nippon India Silver ETF)"
YF_SYMBOL = "SILVERBEES.NS"


def ensure_silver_asset(supabase) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", TICKER)
        .eq("asset_type", "silver")
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": TICKER,
        "name": NAME,
        "asset_type": "silver",
        "yfinance_symbol": YF_SYMBOL,
        "is_active": True,
    }).execute()
    return res.data[0]["asset_id"]


def backfill_history(supabase, asset_id: int) -> int:
    hist = get_price_history(YF_SYMBOL, period="10y", interval="1d")
    if hist.empty:
        return 0
    rows = []
    for idx, row in hist.iterrows():
        rows.append({
            "asset_id": asset_id,
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]) if row["Open"] == row["Open"] else None,
            "high": float(row["High"]) if row["High"] == row["High"] else None,
            "low": float(row["Low"]) if row["Low"] == row["Low"] else None,
            "close": float(row["Close"]) if row["Close"] == row["Close"] else None,
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
        })
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        supabase.table("prices_daily").upsert(rows[i:i + CHUNK], on_conflict="asset_id,date").execute()
    return len(rows)


def refresh_live(supabase, asset_id: int) -> bool:
    live = get_live_price(YF_SYMBOL)
    if live is None:
        return False
    supabase.table("live_prices").upsert({
        "asset_id": asset_id,
        "price": live["price"],
        "prev_close": live["prev_close"],
        "day_change_pct": live["day_change_pct"],
    }, on_conflict="asset_id").execute()
    return True


def main():
    supabase = get_client()
    print(f"Silver ({TICKER}, {YF_SYMBOL})")
    asset_id = ensure_silver_asset(supabase)
    print(f"  asset_id={asset_id}")

    n = backfill_history(supabase, asset_id)
    print(f"  backfilled {n} days of history")

    ok = refresh_live(supabase, asset_id)
    print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. The Other Assets -> Metals -> Silver page can now read real data from `assets`/`prices_daily`/`live_prices`.")


if __name__ == "__main__":
    main()
