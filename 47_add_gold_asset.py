"""
47_add_gold_asset.py
-------------------------------------------------------------------
PRD.md Section J2 / L5 -- Gold, under the Other Assets -> Metals tab.

Fills the real data gap PROJECT_STATE.md flagged: Gold has always had
a schema slot (`assets.asset_type = 'gold'`) but no ingestion script
ever populated it -- so the Other Assets page has only ever been able
to show an honest placeholder, never real data.

Data source decision (documented here, same discipline as every other
J-section data-source call in PRD.md): rather than a brand-new paid
gold-price API, this uses GOLDBEES -- the Nippon India ETF Gold BeES
fund, an NSE-listed security that trades in INR and closely tracks the
domestic gold price. Free via yfinance (yfinance_symbol="GOLDBEES.NS"),
same data provider every other asset in this project already goes
through (market_data_provider.py) -- no new dependency, no new API key.
This is a real, honest choice, not a workaround: the frontend Gold page
labels it clearly as "Gold, via the GOLDBEES ETF" rather than implying
it's an exact bullion/jewellery-shop rate, since an ETF's market price
can drift slightly from the physical spot price (tracking difference).

Reuses the exact pattern 45_add_benchmark_indices.py already proved out
for NIFTY 50/SENSEX/NIFTY BANK -- an asset class is just another row in
`assets`, so all the existing price-history machinery (prices_daily,
live_prices, market_data_provider.py) works completely unchanged.

What this does, safe to run more than once (upserts everywhere):
  1. Ensures the Gold asset row exists in `assets` (asset_type='gold').
  2. Backfills 10 years of daily OHLC history into `prices_daily` (same
     "10 years" reasoning as the benchmark indices -- gives the Gold
     page's chart real history from day one, not just today onward).
  3. Fetches today's live price + day change into `live_prices`.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 47_add_gold_asset.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

TICKER = "GOLD"
NAME = "Gold (via Nippon India ETF Gold BeES)"
YF_SYMBOL = "GOLDBEES.NS"


def ensure_gold_asset(supabase) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", TICKER)
        .eq("asset_type", "gold")
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": TICKER,
        "name": NAME,
        "asset_type": "gold",
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
    print(f"Gold ({TICKER}, {YF_SYMBOL})")
    asset_id = ensure_gold_asset(supabase)
    print(f"  asset_id={asset_id}")

    n = backfill_history(supabase, asset_id)
    print(f"  backfilled {n} days of history")

    ok = refresh_live(supabase, asset_id)
    print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. The Other Assets -> Metals -> Gold page can now read real data from `assets`/`prices_daily`/`live_prices`.")


if __name__ == "__main__":
    main()
