"""
05_daily_price_refresh.py
-------------------------------------------------------------------
Phase B, Step 5a: the fast, frequent price job -- replaces
fetch_live_prices.py. Meant to run every 10-15 minutes during market
hours (the GitHub Actions schedule will call this, same idea as your
old .github/workflows/refresh-prices.yml).

What it does, for every active equity asset in the database:
  1. Fetches the current price + day change (cheap yfinance call) and
     upserts it into `live_prices` -- overwrites the previous snapshot,
     since only "right now" matters for this table.
  2. Also fetches the latest daily OHLCV bar and upserts it into
     `prices_daily` -- this is NEW versus your old site, which never
     kept price history. This is what slowly builds up the 5-year
     chart data over time, on top of the one-time historical backfill
     (a separate, later script).

Like your old scripts: a failure on one stock never wipes anything --
it's just skipped and recorded in the run's failed_symbols list. This
run also skips itself entirely outside NSE market hours, same
protection as before, unless you pass --force.

Run manually:
    python 05_daily_price_refresh.py
    python 05_daily_price_refresh.py --force   (ignore market hours)
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone, timedelta

from db_client import get_client
from market_data_provider import get_live_price, get_price_history
from ingestion_log import start_run, finish_run

IST = timezone(timedelta(hours=5, minutes=30))


def _within_nse_hours(now_ist: datetime) -> bool:
    """Mon-Fri, 9:15am-3:30pm IST. Doesn't know about NSE holidays --
    on a market holiday this just fetches unchanged prices, harmless,
    just a wasted run. Same logic as the old fetch_live_prices.py."""
    if now_ist.weekday() >= 5:
        return False
    minutes = now_ist.hour * 60 + now_ist.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


def main():
    now_ist = datetime.now(IST)
    if "--force" not in sys.argv and not _within_nse_hours(now_ist):
        print(f"Outside NSE market hours ({now_ist.strftime('%Y-%m-%d %H:%M IST')}, "
              f"{now_ist.strftime('%A')}) - skipping. Pass --force to run anyway.")
        return

    supabase = get_client()
    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Refreshing prices for {len(assets)} equities...")

    run_id = start_run("daily_prices")
    ok_count = 0
    failed_symbols = []

    for i, a in enumerate(assets, 1):
        yf_symbol = a.get("yfinance_symbol")
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        if not yf_symbol:
            failed_symbols.append(ticker)
            continue

        live = get_live_price(yf_symbol)
        if live is None:
            failed_symbols.append(ticker)
            continue

        supabase.table("live_prices").upsert({
            "asset_id": asset_id,
            "price": live["price"],
            "prev_close": live["prev_close"],
            "day_change_pct": live["day_change_pct"],
        }, on_conflict="asset_id").execute()

        hist = get_price_history(yf_symbol, period="5d", interval="1d")
        if not hist.empty:
            last_row = hist.iloc[-1]
            bar_date = hist.index[-1].strftime("%Y-%m-%d")
            supabase.table("prices_daily").upsert({
                "asset_id": asset_id,
                "date": bar_date,
                "open": float(last_row["Open"]) if not pd_isna(last_row["Open"]) else None,
                "high": float(last_row["High"]) if not pd_isna(last_row["High"]) else None,
                "low": float(last_row["Low"]) if not pd_isna(last_row["Low"]) else None,
                "close": float(last_row["Close"]) if not pd_isna(last_row["Close"]) else None,
                "volume": int(last_row["Volume"]) if not pd_isna(last_row["Volume"]) else None,
            }, on_conflict="asset_id,date").execute()

        ok_count += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(assets)}] done...")

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(assets)} ok. Failed: {failed_symbols if failed_symbols else 'none'}")


def pd_isna(v) -> bool:
    try:
        import pandas as pd
        return pd.isna(v)
    except Exception:
        return v is None


if __name__ == "__main__":
    main()
