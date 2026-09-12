"""
45_add_benchmark_indices.py
-------------------------------------------------------------------
PRD.md Section L2 (Markets tab) -- one-time setup for the 3 India
benchmark indices the Markets tab needs: NIFTY 50, SENSEX, NIFTY BANK.

Reuses the exact same pattern 08_backfill_price_history.py already
proved out for the NIFTY100 benchmark (used internally for TrueScore's
"did this stock beat the market" calc) -- an index is just another row
in `assets` with asset_type='index', so all the existing price-history
machinery (prices_daily, live_prices, market_data_provider.py) works
unchanged. No new tables, no schema change needed (07_add_index_asset_
type.sql already allows asset_type='index').

What this does, safe to run more than once (upserts everywhere):
  1. Ensures NIFTY 50 / SENSEX / NIFTY BANK exist as `assets` rows.
  2. Backfills 10 years of daily OHLC history for each into
     `prices_daily` -- same "10 years, not 5" reasoning as
     08_backfill_price_history.py (covers the COVID crash quarter with
     years of lead-in).
  3. Fetches today's live price + day change into `live_prices`, so
     the Markets tab has something to show immediately after this run.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 45_add_benchmark_indices.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

# (ticker shown on the site, display name, yfinance symbol)
BENCHMARK_INDICES = [
    ("NIFTY50", "Nifty 50", "^NSEI"),
    ("SENSEX", "S&P BSE Sensex", "^BSESN"),
    ("NIFTYBANK", "Nifty Bank", "^NSEBANK"),
]


def ensure_index_asset(supabase, ticker: str, name: str, yf_symbol: str) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", ticker)
        .eq("asset_type", "index")
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": ticker,
        "name": name,
        "asset_type": "index",
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
    for ticker, name, yf_symbol in BENCHMARK_INDICES:
        print(f"\n{name} ({ticker}, {yf_symbol})")
        asset_id = ensure_index_asset(supabase, ticker, name, yf_symbol)
        print(f"  asset_id={asset_id}")

        n = backfill_history(supabase, asset_id, yf_symbol)
        print(f"  backfilled {n} days of history")

        ok = refresh_live(supabase, asset_id, yf_symbol)
        print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. The Markets tab can now read these 3 indices from `assets`/`prices_daily`/`live_prices`.")


if __name__ == "__main__":
    main()
