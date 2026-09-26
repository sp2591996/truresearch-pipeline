"""
147_refresh_hourly_prices.py
-------------------------------------------------------------------
Keeps the last 7 days of HOURLY price bars in `prices_hourly` (for the
stock page's 1 Day / 1 Week chart and the sector index's 1 Day / 1 Week
chart). Runs about once an hour during each market's trading hours (see
.github/workflows/hourly-prices.yml).

Each run:
  1. For every active equity of a market that is currently open (or closed
     less than an hour ago, to capture the final bar), fetch the last 2
     days of 1-hour bars from yfinance and upsert them. Upserting means the
     in-progress bar simply keeps updating until it completes.
  2. Calls the database function roll_up_and_purge_prices_hourly()
     (migration 147), which converts any finished day that is still missing
     a daily bar into one in `prices_daily`, then deletes hourly rows older
     than 7 days -- so hourly data never piles up.

Run manually:
    python 147_refresh_hourly_prices.py --force            (ignore market hours, both markets)
    python 147_refresh_hourly_prices.py --market=india --force
    python 147_refresh_hourly_prices.py --force --backfill  (fetch 7 days, use once after setup)
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from db_client import get_client
from market_data_provider import get_price_history

MARKETS = {
    # open, close (local minutes from midnight), timezone
    "india": {"tz": ZoneInfo("Asia/Kolkata"), "open": 9 * 60 + 15, "close": 15 * 60 + 30},
    "usa": {"tz": ZoneInfo("America/New_York"), "open": 9 * 60 + 30, "close": 16 * 60},
}
GRACE_AFTER_CLOSE_MIN = 60


def _arg(name: str, default: str = "") -> str:
    prefix = f"--{name}="
    for a in sys.argv:
        if a.startswith(prefix):
            return a[len(prefix):]
    return default


def _market_active(market: str) -> bool:
    cfg = MARKETS[market]
    now = datetime.now(cfg["tz"])
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return cfg["open"] <= minutes <= cfg["close"] + GRACE_AFTER_CLOSE_MIN


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN -> None


def refresh_market(supabase, market: str, period: str) -> None:
    assets, offset = [], 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, yfinance_symbol")
            .eq("asset_type", "equity").eq("is_active", True).eq("market", market)
            .range(offset, offset + 999).execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    print(f"[{market}] fetching {period} of hourly bars for {len(assets)} stocks...")
    ok, failed = 0, []
    for a in assets:
        sym = a.get("yfinance_symbol")
        if not sym:
            failed.append(a["ticker"])
            continue
        hist = get_price_history(sym, period=period, interval="1h")
        if hist is None or hist.empty:
            failed.append(a["ticker"])
            continue
        rows = []
        for ts, r in hist.iterrows():
            close = _num(r["Close"])
            if close is None or close <= 0:
                continue
            ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
            vol = _num(r["Volume"])
            rows.append({
                "asset_id": a["asset_id"],
                "ts": ts_utc.isoformat(),
                "open": _num(r["Open"]), "high": _num(r["High"]), "low": _num(r["Low"]),
                "close": close,
                "volume": int(vol) if vol is not None else None,
            })
        if not rows:
            failed.append(a["ticker"])
            continue
        try:
            supabase.table("prices_hourly").upsert(rows, on_conflict="asset_id,ts").execute()
            ok += 1
        except Exception as e:
            failed.append(f"{a['ticker']} (save failed: {e})")
    print(f"[{market}] done. {ok}/{len(assets)} ok. Failed: {failed if failed else 'none'}")


def main():
    force = "--force" in sys.argv
    only = _arg("market")
    period = "7d" if "--backfill" in sys.argv else "2d"
    supabase = get_client()
    markets = [only] if only else list(MARKETS)
    ran_any = False
    for m in markets:
        if not force and not _market_active(m):
            print(f"[{m}] outside trading hours - skipping.")
            continue
        refresh_market(supabase, m, period)
        ran_any = True
    if ran_any or force:
        supabase.rpc("roll_up_and_purge_prices_hourly", {}).execute()
        print("Rolled up finished days into prices_daily and purged hourly rows older than 7 days.")


if __name__ == "__main__":
    main()
