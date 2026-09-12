"""
59_refresh_crude_oil.py
-------------------------------------------------------------------
The frequent, lightweight refresh job for EVERY commodity benchmark
(any `assets` row with asset_type='commodity') -- originally written
for WTI/Brent crude oil (58_add_crude_oil_assets.py), but it loops
over all active commodity rows generically, so it automatically also
covers Natural Gas (60_add_natural_gas_asset.py) and any future
commodity added the same way, with no changes needed here. Mirrors
48_refresh_gold.py / 56_refresh_fx.py -- with one deliberate
difference:

Gold/Silver/FX all gate on NSE market hours (9:15am-3:30pm IST,
Mon-Fri) because GOLDBEES/SILVERBEES/most FX pairs only move
meaningfully while NSE is open. Global commodity benchmarks are
different -- WTI, Brent, and Henry Hub natural gas all trade on
global exchanges (NYMEX/ICE) nearly around the clock on weekdays,
including hours when NSE is shut (evening/night IST). So this script
instead gates only on "is it a weekday" and skips the NSE-specific
time window, so scheduled runs actually catch price moves that
happen outside Indian market hours.

Run manually:
    python 59_refresh_crude_oil.py
    python 59_refresh_crude_oil.py --force
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone

from db_client import get_client
from market_data_provider import get_live_price, get_price_history


def _is_weekday(now_utc: datetime) -> bool:
    # Global commodity markets are shut all weekend; the exact daily
    # window varies by exchange/session, so (unlike the NSE-gated
    # scripts) this just checks the day, not a narrow time band.
    return now_utc.weekday() < 5


def main():
    now_utc = datetime.now(timezone.utc)
    if "--force" not in sys.argv and not _is_weekday(now_utc):
        print(f"Weekend ({now_utc.strftime('%Y-%m-%d %H:%M UTC')}) - global commodity markets closed, skipping. Pass --force to run anyway.")
        return

    supabase = get_client()
    commodity_assets = (
        supabase.table("assets")
        .select("asset_id, ticker, yfinance_symbol")
        .eq("asset_type", "commodity")
        .eq("is_active", True)
        .execute()
    ).data

    if not commodity_assets:
        print("No commodity assets found -- run 58_add_crude_oil_assets.py first.")
        return

    ok_count = 0
    failed = []
    for a in commodity_assets:
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            failed.append(ticker)
            continue

        live = get_live_price(yf_symbol)
        if live is None:
            failed.append(ticker)
            continue

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

        ok_count += 1

    print(f"Done. {ok_count}/{len(commodity_assets)} commodity benchmarks refreshed. Failed: {failed if failed else 'none'}")


if __name__ == "__main__":
    main()
