"""
56_refresh_fx.py
-------------------------------------------------------------------
The frequent, lightweight refresh job for FX pairs (asset_type='fx'),
mirroring 46_refresh_benchmark_indices.py / 48_refresh_gold.py /
53_refresh_silver.py exactly.

SAR/INR, KWD/INR, and OMR/INR have no usable direct Yahoo ticker, so
55_add_fx_assets.py stores "SAR=X" etc. as their yfinance_symbol --
that's USD/<currency>, NOT <currency>/INR. They have to be computed as
(USD/INR) / (USD/<currency>) here too; saving the raw quote would show
1 USD = 3.75 SAR as "1 SAR = Rs 3.75". To repair rows a run without this
step already wrote: run 55_add_fx_assets.py, then this script.

Run manually:
    python 56_refresh_fx.py
    python 56_refresh_fx.py --force
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd

from db_client import get_client
from market_data_provider import get_live_price, get_price_history
from ingestion_log import start_run, finish_run

IST = timezone(timedelta(hours=5, minutes=30))

# Pairs priced as a cross rate through USD (see file header).
CROSS_RATE_TICKERS = {"SARINR", "KWDINR", "OMRINR"}

# Yahoo's SAR=X is unreliable: 116 of 259 daily closes over the past year
# were more than 1% off the 3.75 peg, which made a pegged currency show
# -3% days (OMR=X has occasional bad bars too). Both are fixed to the US
# Dollar by law, so the official peg is used in place of the Yahoo quote.
# KWD isn't here: it's pegged to a basket, so it stays on Yahoo's KWD=X.
PEGGED_TO_USD = {"SAR=X": 3.75, "OMR=X": 0.3845}


def _within_nse_hours(now_ist: datetime) -> bool:
    if now_ist.weekday() >= 5:
        return False
    minutes = now_ist.hour * 60 + now_ist.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


def _direct_quote(yf_symbol: str):
    """Today's live quote + latest daily bar for a pair Yahoo quotes
    directly against INR. Returns (live, bar), either may be None."""
    live = get_live_price(yf_symbol)
    if live is None:
        return None, None
    hist = get_price_history(yf_symbol, period="5d", interval="1d")
    if hist.empty:
        return live, None
    last_row = hist.iloc[-1]
    return live, {
        "date": hist.index[-1].strftime("%Y-%m-%d"),
        "open": float(last_row["Open"]) if last_row["Open"] == last_row["Open"] else None,
        "high": float(last_row["High"]) if last_row["High"] == last_row["High"] else None,
        "low": float(last_row["Low"]) if last_row["Low"] == last_row["Low"] else None,
        "close": float(last_row["Close"]) if last_row["Close"] == last_row["Close"] else None,
        "volume": int(last_row["Volume"]) if last_row["Volume"] == last_row["Volume"] else None,
    }


def _cross_quote(cross_symbol: str):
    """Same as _direct_quote, for <currency>/INR = (USD/INR) / (USD/<currency>).
    Built from daily bars, not get_live_price: that rounds to 2 decimals,
    which turns USD/KWD 0.3066 into 0.31 -- about 1% off once divided."""
    usdinr = get_price_history("INR=X", period="5d", interval="1d")
    if usdinr.empty:
        return None, None
    peg = PEGGED_TO_USD.get(cross_symbol)
    if peg:
        usdxxx = pd.DataFrame(peg, index=usdinr.index, columns=["Open", "High", "Low", "Close"])
    else:
        usdxxx = get_price_history(cross_symbol, period="5d", interval="1d")
    if usdxxx.empty:
        return None, None
    common_dates = usdinr.index.intersection(usdxxx.index)

    def cross(idx, field):
        av, bv = usdinr.loc[idx][field], usdxxx.loc[idx][field]
        if av != av or bv != bv or bv == 0:
            return None
        return float(av) / float(bv)

    closes = [(idx, cross(idx, "Close")) for idx in common_dates]
    closes = [(idx, c) for idx, c in closes if c is not None]
    if not closes:
        return None, None
    idx, price = closes[-1]
    prev_close = closes[-2][1] if len(closes) > 1 else None
    live = {
        "price": price,
        "prev_close": prev_close,
        "day_change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close else None,
    }
    return live, {
        "date": idx.strftime("%Y-%m-%d"),
        "open": cross(idx, "Open"),
        "high": cross(idx, "High"),
        "low": cross(idx, "Low"),
        "close": price,
        "volume": None,
    }


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

    run_id = start_run("fx_refresh")
    ok_count = 0
    failed = []
    for a in fx_assets:
        yf_symbol = a.get("yfinance_symbol")
        ticker = a["ticker"]
        if not yf_symbol:
            failed.append(ticker)
            continue

        if ticker in CROSS_RATE_TICKERS:
            live, bar = _cross_quote(yf_symbol)
        else:
            live, bar = _direct_quote(yf_symbol)
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

            if bar is not None:
                supabase.table("prices_daily").upsert({
                    "asset_id": a["asset_id"],
                    **bar,
                }, on_conflict="asset_id,date").execute()
        except Exception as e:
            failed.append(f"{ticker} (save failed: {e})")
            continue

        ok_count += 1

    finish_run(run_id, ok_count, failed)
    print(f"Done. {ok_count}/{len(fx_assets)} FX pairs refreshed. Failed: {failed if failed else 'none'}")


if __name__ == "__main__":
    main()
