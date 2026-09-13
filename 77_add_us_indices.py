"""
77_add_us_indices.py
-------------------------------------------------------------------
Adds 3 more US benchmark indices to the Markets tab (Avdhoot's
request, chat: "have other indexes integrated on the market page for
usa - beyond s&p 500"). Same exact pattern 45_add_benchmark_indices.py
used for India's NIFTY50/SENSEX/NIFTYBANK, and the same one
68_backfill_us_price_history.py already used to add SPX500 itself --
an index is just another `assets` row with asset_type='index', so all
the existing price-history machinery (prices_daily, live_prices,
market_data_provider.py) works completely unchanged.

The 3 added here are the other widely-tracked US benchmarks, the same
"big 4" any US markets page would be expected to show alongside the
S&P 500:
  - Dow Jones Industrial Average (^DJI)
  - Nasdaq Composite (^IXIC)
  - Russell 2000 (^RUT) -- small-cap benchmark, a useful contrast to
    the other 3 which all skew large-cap

Every asset created here gets market="usa" explicitly (unlike India's
45_add_benchmark_indices.py, which didn't need to -- it ran before the
`market` column existed and relied on the column's 'india' default).

Safe to run more than once (upserts everywhere).

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 77_add_us_indices.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

MARKET = "usa"

# (ticker shown on the site, display name, yfinance symbol)
US_INDICES = [
    ("DOWJONES", "Dow Jones Industrial Average", "^DJI"),
    ("NASDAQCOMP", "Nasdaq Composite", "^IXIC"),
    ("RUSSELL2000", "Russell 2000", "^RUT"),
]


def ensure_index_asset(supabase, ticker: str, name: str, yf_symbol: str) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", ticker)
        .eq("asset_type", "index")
        .eq("market", MARKET)
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": ticker,
        "name": name,
        "asset_type": "index",
        "yfinance_symbol": yf_symbol,
        "market": MARKET,
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
    for ticker, name, yf_symbol in US_INDICES:
        print(f"\n{name} ({ticker}, {yf_symbol})")
        asset_id = ensure_index_asset(supabase, ticker, name, yf_symbol)
        print(f"  asset_id={asset_id}")

        n = backfill_history(supabase, asset_id, yf_symbol)
        print(f"  backfilled {n} days of history")

        ok = refresh_live(supabase, asset_id, yf_symbol)
        print(f"  live price refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. The Markets tab can now read all 4 US indices (SPX500 + these 3) from `assets`/`prices_daily`/`live_prices`.")
    print("Remember to also update app/markets/page.tsx's USA_INDEX_TICKERS list on the frontend -- that's a separate, already-done step.")


if __name__ == "__main__":
    main()
