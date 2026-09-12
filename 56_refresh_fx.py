"""
56_refresh_fx.py
-------------------------------------------------------------------
The frequent, lightweight refresh job for FX pairs (asset_type='fx'),
mirroring 46_refresh_benchmark_indices.py / 48_refresh_gold.py /
53_refresh_silver.py exactly.

Run manually:
    python 56_refresh_fx.py
    python 56_refresh_fx.py --force
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone, timedelta

from db_client import get_client
from market_data_provider import get_live_price, get_price_history

IST = timezone(timedelta(hours=5, minutes=30))


def _within_nse_hours(now_ist: datetime) -> bool:
    if now_ist.weekday() >= 5:
        return False
    minutes = now_ist.hour * 60 + now_ist.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


def main():
    now_ist = datetime.now(IST)
    if "--force" not in sys.argv and not _within_nse_hours(now_ist):
        print(f"Outside NSE market hours ({now_ist.strftime('%Y-%m-%d %H:%M IST')}) - skipping. Pass --force to run anyway.")
        return

    supabase = get_client()
    fx_assets = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        .eq("asset_type", "fx")
        .eq("is_active", True)
        .execute()
    ).data

    if not fx_assets:
        print("No FX assets found -- run 55_add_fx_assets.py first.")
        return

    ok_count = 0
    failed = []
    for a in fx_assets:
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            failed.append(ticker)
            continue

        live = get_live_price(yf_symbol)
        if live is None:
            failed.append(ticker)
            continue

        # Session 30 fix: a database-side hiccup (e.g. a transient 504
        # Gateway Timeout from Supabase) on saving used to crash the
        # whole run -- now skipped and recorded, same as a yfinance-side
        # failure above.
        try:
            supabase.table("live_prices").upsert({
                "asset_id": a["asset_id"],
                "price": live["price"],
                "prev_close": live["prev_close"],
                "day_change_pct": live["day_change_pct"],
            }, on_conflict="asset_id").execute()

            hist = get_price_history(yf_symbol, period="5d", interval="1d")
            if not hist.empty:
                last_row = hist.iloc[-1]
                bar_date = hist.index[-1].strftime("%Y-%m-%d")
                supabase.table("prices_daily").upsert({
                    "asset_id": a["asset_id"],
                    "date": bar_date,
                    "open": float(last_row["Open"]) if last_row["Open"] == last_row["Open"] else None,
                    "high": float(last_row["High"]) if last_row["High"] == last_row["High"] else None,
                    "low": float(last_row["Low"]) if last_row["Low"] == last_row["Low"] else None,
                    "close": float(last_row["Close"]) if last_row["Close"] == last_row["Close"] else None,
                    "volume": int(last_row["Volume"]) if last_row["Volume"] == last_row["Volume"] else None,
                }, on_conflict="asset_id,date").execute()
        except Exception as e:
            failed.append(f"{ticker} (save failed: {e})")
            continue

        ok_count += 1

    print(f"Done. {ok_count}/{len(fx_assets)} FX pairs refreshed. Failed: {failed if failed else 'none'}")


if __name__ == "__main__":
    main()
