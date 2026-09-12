"""
58_add_crude_oil_assets.py
-------------------------------------------------------------------
PRD.md Section L5 -- Commodities, under Other Assets. Session 28's
investigation of Copper found no free NSE-listed ETF exists for any
metal beyond Gold/Silver, and no free NSE-listed instrument exists
for crude oil either -- India has no retail crude-oil ETF; the only
domestic route is MCX futures, which (like Copper) need a different,
harder data source than this project's free yfinance/ETF pipeline.

Rather than leave Crude Oil as an indefinite placeholder the way
Copper is, this uses the two prices the entire world actually quotes
crude oil against -- WTI (US benchmark) and Brent (international
benchmark) -- both freely available on yfinance as continuous futures
contracts, quoted in US Dollars per barrel (NOT Indian Rupees --
there is no honest INR conversion for a global commodity benchmark,
so unlike the FX pairs this is deliberately left in USD and labelled
as such throughout the frontend, rather than fabricating a rupee
price for an instrument nobody in India actually trades directly).

Reuses the exact "assets / prices_daily / live_prices" shape every
other Other Assets script (Gold, Silver, FX) already uses.

IMPORTANT -- run 57_add_commodity_asset_type.sql in Supabase's SQL
Editor FIRST. `assets.asset_type` doesn't allow 'commodity' yet;
this script's insert will fail until that migration runs.

What this does, safe to run more than once (upserts everywhere):
  1. Ensures each crude benchmark exists as an `assets` row
     (asset_type='commodity').
  2. Backfills 10 years of daily price history into `prices_daily`.
  3. Fetches today's live price + day change into `live_prices`.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 58_add_crude_oil_assets.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

# (ticker shown on the site, display name, yfinance symbol)
CRUDE_BENCHMARKS = [
    ("WTICRUDE", "WTI Crude Oil", "CL=F"),
    ("BRENTCRUDE", "Brent Crude Oil", "BZ=F"),
]


def ensure_commodity_asset(supabase, ticker: str, name: str, yf_symbol: str) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", ticker)
        .eq("asset_type", "commodity")
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": ticker,
        "name": name,
        "asset_type": "commodity",
        "yfinance_symbol": yf_symbol,
        "is_active": True,
    }).execute()
    return res.data[0]["asset_id"]


def backfill_history(supabase, asset_id: int, yf_symbol: str) -> int:
    hist = get_price_history(yf_symbol, period="10y", interval="1d")
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


def refresh_live(supabase, asset_id: int, yf_symbol: str) -> bool:
    live = get_live_price(yf_symbol)
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
    for ticker, name, yf_symbol in CRUDE_BENCHMARKS:
        print(f"\n{name} ({ticker}, {yf_symbol})")
        asset_id = ensure_commodity_asset(supabase, ticker, name, yf_symbol)
        print(f"  asset_id={asset_id}")

        n = backfill_history(supabase, asset_id, yf_symbol)
        print(f"  backfilled {n} days of history")

        ok = refresh_live(supabase, asset_id, yf_symbol)
        print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. Other Assets -> Commodities can now read real data from `assets`/`prices_daily`/`live_prices`.")


if __name__ == "__main__":
    main()
