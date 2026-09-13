"""
74_us_daily_price_refresh.py
-------------------------------------------------------------------
The US equivalent of 05_daily_price_refresh.py -- the fast, frequent
price job that keeps `live_prices` and `prices_daily` current for
US (market='usa') stocks. Meant to run every 10-15 minutes during
US market hours, the same way 05_daily_price_refresh.py runs during
NSE hours for India.

Why a separate script instead of just removing 05's market filter:
05_daily_price_refresh.py deliberately only runs during NSE hours
(9:15am-3:30pm IST) and only touches India stocks -- see that
file's own header for why. US markets are open at a completely
different time of day (9:30am-4:00pm US/Eastern), so a single
combined script would either run US refreshes at the wrong time or
skip India refreshes to accommodate US hours. Two small scripts,
each gated to its own market's hours, is simpler and safer than one
script juggling two schedules.

What it does, for every active US equity asset in the database
(mirrors 05_daily_price_refresh.py's own two steps exactly):
  1. Fetches the current price + day change and upserts it into
     `live_prices`.
  2. Fetches the latest daily OHLCV bar and upserts it into
     `prices_daily`.

Run type: reuses the already-allowed "daily_prices" run_type label
(same reasoning as 69_backfill_us_fundamentals.py reusing
"weekly_fundamentals" -- `ingestion_runs.run_type` only accepts a
fixed, pre-approved list of values via a DB check constraint, and
"daily_prices" already describes exactly this kind of job whichever
market it's for).

Rate-limiting note (added after the first real run): fetching 500+
symbols back-to-back with no pause between calls tripped Yahoo
Finance's own rate limiting partway through the run -- it started
returning fake "possibly delisted" errors for perfectly real, huge
companies (Walmart, Disney, Tesla, Visa, etc.) once we'd made too
many requests too quickly. Two things fix this: a small pause after
every symbol, and a retry (after a longer pause) for any symbol that
fails the first time -- since these failures are Yahoo temporarily
saying "slow down," not real bad data, one retry a bit later
succeeds almost every time.

Run manually:
    python 74_us_daily_price_refresh.py
    python 74_us_daily_price_refresh.py --force   (ignore market hours)
-------------------------------------------------------------------
"""
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from db_client import get_client
from market_data_provider import get_live_price, get_price_history
from ingestion_log import start_run, finish_run

US_EASTERN = ZoneInfo("America/New_York")

# Pause between every symbol's requests, and a longer pause before
# retrying a symbol that failed -- see the rate-limiting note above.
REQUEST_DELAY_SECONDS = 0.6
RETRY_DELAY_SECONDS = 5.0


def _within_us_market_hours(now_et: datetime) -> bool:
    """Mon-Fri, 9:30am-4:00pm US/Eastern. Doesn't know about US market
    holidays (Thanksgiving, July 4th, etc.) -- on a holiday this just
    fetches unchanged prices, harmless, just a wasted run. Using
    America/New_York (not a fixed UTC offset) means this automatically
    stays correct across US daylight saving time changes, unlike a
    hardcoded "-4" or "-5" would."""
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return (9 * 60 + 30) <= minutes <= (16 * 60)


def main():
    now_et = datetime.now(US_EASTERN)
    if "--force" not in sys.argv and not _within_us_market_hours(now_et):
        print(f"Outside US market hours ({now_et.strftime('%Y-%m-%d %H:%M %Z')}, "
              f"{now_et.strftime('%A')}) - skipping. Pass --force to run anyway.")
        return

    supabase = get_client()
    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        # asset_type in ("equity", "index") -- widened from equity-only
        # so this same run also keeps the 4 US benchmark indices
        # (SPX500 + the 3 added by 77_add_us_indices.py) current,
        # rather than leaving them to whatever refreshes during India
        # hours (see 46_refresh_benchmark_indices.py's own market
        # filter fix, added at the same time as this change).
        .in_("asset_type", ["equity", "index"])
        .eq("is_active", True)
        .eq("market", "usa")
        .execute()
    )
    assets = assets_res.data
    print(f"Refreshing prices for {len(assets)} US equities/indices...")

    run_id = start_run("us_daily_prices")
    ok_count = 0
    failed_symbols = []

    for i, a in enumerate(assets, 1):
        yf_symbol = a.get("yfinance_symbol")
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        if not yf_symbol:
            failed_symbols.append(ticker)
            continue

        # Try once, and if Yahoo Finance failed us (rate limiting shows
        # up as a failed fetch, not a distinct error type we can check
        # for directly), wait longer and try this one symbol again
        # before giving up on it.
        live = get_live_price(yf_symbol)
        if live is None:
            time.sleep(RETRY_DELAY_SECONDS)
            live = get_live_price(yf_symbol)
        if live is None:
            failed_symbols.append(ticker)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        try:
            supabase.table("live_prices").upsert({
                "asset_id": asset_id,
                "price": live["price"],
                "prev_close": live["prev_close"],
                "day_change_pct": live["day_change_pct"],
            }, on_conflict="asset_id").execute()

            hist = get_price_history(yf_symbol, period="5d", interval="1d")
            if hist.empty:
                time.sleep(RETRY_DELAY_SECONDS)
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
        except Exception as e:
            # Same "one bad save shouldn't kill the whole run" protection
            # 05_daily_price_refresh.py's Session 30 fix added.
            failed_symbols.append(f"{ticker} (save failed: {e})")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        ok_count += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(assets)}] done...")
        time.sleep(REQUEST_DELAY_SECONDS)

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
