"""
20_backfill_new_stocks_price_history.py
-------------------------------------------------------------------
Phase C, Step 3: one-time 10-year price history backfill for the 300
Nifty 500 stocks added by 19_add_nifty500_expansion.py. Your original
200 already have this (done back in Phase B via
08_backfill_price_history.py) -- this script does the exact same
thing, with the exact same settings (10 years, matching the original
model's own choice of runway before the COVID crash quarter), but
skips any stock that already has price history, so it only does real
work for the new 300 and is always safe to re-run later too (for
example, if you add more stocks again in the future).

How it decides what to skip: for every active equity, it checks
whether `prices_daily` already has at least one row for that stock.
If yes, it's already backfilled -- skipped. If no, it fetches 10
years of daily prices from Yahoo Finance and saves them.

This is the slow step -- 300 stocks, roughly half a second to a
couple of seconds each depending on Yahoo Finance's response time, so
expect this to take somewhere from 15 minutes to a bit over an hour.
It's fine to let it run in the background; if it gets interrupted
partway through, just run it again -- it picks up exactly where it
left off, since already-backfilled stocks are skipped.

Run manually:
    python 20_backfill_new_stocks_price_history.py
-------------------------------------------------------------------
"""
import time

from db_client import get_client
from market_data_provider import get_price_history

PERIOD = "10y"


def already_has_history(supabase, asset_id: int) -> bool:
    res = (
        supabase.table("prices_daily")
        .select("asset_id")
        .eq("asset_id", asset_id)
        .limit(1)
        .execute()
    )
    return len(res.data) > 0


def backfill_one_asset(supabase, asset_id: int, yf_symbol: str) -> int:
    hist = get_price_history(yf_symbol, period=PERIOD, interval="1d")
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
        chunk = rows[i:i + CHUNK]
        supabase.table("prices_daily").upsert(chunk, on_conflict="asset_id,date").execute()
    return len(rows)


def main():
    supabase = get_client()

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Checking {len(assets)} active equities for existing price history...")

    to_backfill = []
    for a in assets:
        if not already_has_history(supabase, a["asset_id"]):
            to_backfill.append(a)
    print(f"{len(assets) - len(to_backfill)} already have history (skipping). "
          f"{len(to_backfill)} need a fresh backfill.\n")

    if not to_backfill:
        print("Nothing to do -- every active equity already has price history.")
        return

    ok_count = 0
    failed = []
    for i, a in enumerate(to_backfill, 1):
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            print(f"  ! {ticker}: no yfinance_symbol on file -- skipped")
            failed.append(ticker)
            continue
        try:
            n = backfill_one_asset(supabase, a["asset_id"], yf_symbol)
            if n > 0:
                ok_count += 1
                print(f"  [{i}/{len(to_backfill)}] {ticker}: {n} days loaded")
            else:
                print(f"  [{i}/{len(to_backfill)}] {ticker}: no data returned -- skipped")
                failed.append(ticker)
        except Exception as e:
            print(f"  [{i}/{len(to_backfill)}] {ticker}: FAILED -- {e}")
            failed.append(ticker)
        time.sleep(0.3)

    print(f"\nDone. {ok_count}/{len(to_backfill)} new stocks backfilled.")
    print(f"Failed: {failed if failed else 'none'}")


if __name__ == "__main__":
    main()
