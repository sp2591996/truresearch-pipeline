"""
60_add_natural_gas_asset.py
-------------------------------------------------------------------
PRD.md Section L5 -- Commodities, under Other Assets. Avdhoot: add
Natural Gas next, after WTI/Brent crude oil (58_add_crude_oil_assets.py).
Same reasoning as crude oil: India has no free NSE-listed natural-gas
ETF for retail investors (only MCX futures), so this uses the global
benchmark everyone quotes natural gas against instead -- Henry Hub
(the US benchmark, ticker "NG=F" on yfinance), freely available,
quoted in US Dollars per million British thermal units (MMBtu) --
again deliberately NOT converted to Rupees, for the same reason
crude oil wasn't: there's no honest "natural gas in Rupees" price
this could correspond to.

Natural gas is particularly relevant to India as a major LNG
(liquefied natural gas) importer -- global gas prices feed directly
into India's import costs and domestic gas-linked pricing.

Reuses the exact `assets` / `prices_daily` / `live_prices` shape
every other Other Assets script uses, and slots into the SAME
asset_type='commodity' bucket crude oil already uses -- no new
migration needed (57_add_commodity_asset_type.sql already added
'commodity' as an allowed asset_type), and 59_refresh_crude_oil.py's
scheduled refresh already loops over every asset_type='commodity'
row, so it picks this up automatically once this script has run --
no separate refresh script or GitHub Action needed for Natural Gas.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 60_add_natural_gas_asset.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

TICKER = "NATGAS"
NAME = "Natural Gas (Henry Hub)"
YF_SYMBOL = "NG=F"


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
    print(f"\n{NAME} ({TICKER}, {YF_SYMBOL})")
    asset_id = ensure_commodity_asset(supabase, TICKER, NAME, YF_SYMBOL)
    print(f"  asset_id={asset_id}")

    n = backfill_history(supabase, asset_id, YF_SYMBOL)
    print(f"  backfilled {n} days of history")

    ok = refresh_live(supabase, asset_id, YF_SYMBOL)
    print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. Other Assets -> Commodities can now show Natural Gas too. "
          "59_refresh_crude_oil.py's scheduled job already covers this asset "
          "(it loops over every asset_type='commodity' row) -- no new workflow needed.")


if __name__ == "__main__":
    main()
