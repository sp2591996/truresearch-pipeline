"""
08_backfill_price_history.py
-------------------------------------------------------------------
Phase B, Step 6: one-time backfill of 10 years of daily price history
for every equity stock, PLUS the Nifty 100 benchmark index -- both
needed to build a real TrueScore training dataset (the model needs to
compute "did this stock beat the market" over rolling 3-month windows
going back years).

10 years (not 5) deliberately matches the original model's own choice
-- it's the minimum runway that safely covers the COVID crash quarter
(Jan-Mar 2020) with 3-4 years of lead-in beforehand, rather than
starting the model's usable history right at the edge of the crash.

Run 07_add_index_asset_type.sql in Supabase FIRST -- this script
inserts the benchmark index as an asset, which needs that column
constraint updated first.

Safe to run more than once (upserts everywhere).

Run with:
    python 08_backfill_price_history.py
-------------------------------------------------------------------
"""
import time

from db_client import get_client
from market_data_provider import get_price_history

BENCHMARK_YF_SYMBOL = "^CNX100"  # Nifty 100 -- same benchmark the original model used


def ensure_benchmark_asset(supabase) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", "NIFTY100")
        .eq("asset_type", "index")
        .execute()
    )
    if existing.data:
        return existing.data[0]["asset_id"]
    res = supabase.table("assets").insert({
        "ticker": "NIFTY100",
        "name": "Nifty 100 Index",
        "asset_type": "index",
        "yfinance_symbol": BENCHMARK_YF_SYMBOL,
        "is_active": True,
    }).execute()
    return res.data[0]["asset_id"]


def backfill_one_asset(supabase, asset_id: int, yf_symbol: str, ticker: str) -> int:
    hist = get_price_history(yf_symbol, period="10y", interval="1d")
    if hist.empty:
        return 0

    rows = []
    for idx, row in hist.iterrows():
        rows.append({
            "asset_id": asset_id,
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]) if row["Open"] == row["Open"] else None,  # NaN check
            "high": float(row["High"]) if row["High"] == row["High"] else None,
            "low": float(row["Low"]) if row["Low"] == row["Low"] else None,
            "close": float(row["Close"]) if row["Close"] == row["Close"] else None,
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
        })

    # Upload in chunks so a single request never gets too large.
    CHUNK = 500
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        supabase.table("prices_daily").upsert(chunk, on_conflict="asset_id,date").execute()
    return len(rows)


def main():
    supabase = get_client()

    print("Ensuring Nifty 100 benchmark index exists as an asset...")
    benchmark_asset_id = ensure_benchmark_asset(supabase)
    print(f"Backfilling benchmark index history ({BENCHMARK_YF_SYMBOL})...")
    n = backfill_one_asset(supabase, benchmark_asset_id, BENCHMARK_YF_SYMBOL, "NIFTY100")
    print(f"  -> {n} days of benchmark history loaded.\n")

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Backfilling 10-year price history for {len(assets)} stocks. This will take a while...")

    ok_count = 0
    failed = []
    for i, a in enumerate(assets, 1):
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            failed.append(ticker)
            continue
        try:
            n = backfill_one_asset(supabase, a["asset_id"], yf_symbol, ticker)
            if n > 0:
                ok_count += 1
            else:
                failed.append(ticker)
        except Exception as e:
            print(f"  ! {ticker}: {e}")
            failed.append(ticker)

        if i % 10 == 0:
            print(f"  [{i}/{len(assets)}] done...")
        time.sleep(0.3)

    print(f"\nDone. {ok_count}/{len(assets)} stocks backfilled.")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
