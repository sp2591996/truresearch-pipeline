"""
55_add_fx_assets.py
-------------------------------------------------------------------
PRD.md Section L5 -- FX, under Other Assets. "Live rates for major
currency pairs (starting with USD/INR)" -- covers USD/INR, EUR/INR,
GBP/INR, JPY/INR, plus (Session 28, Avdhoot: "add AED to INR, SAR,
KWD, OMR -- wherever Indians mostly stay/invest") the 4 Gulf
currencies of the countries with the largest Indian expatriate
populations and remittance flows: UAE, Saudi Arabia, Kuwait, Oman.

Direct Yahoo Finance tickers exist for USD/INR, EUR/INR, GBP/INR,
JPY/INR, and AED/INR -- those are fetched straight from yfinance,
same as before.

SAR/INR, KWD/INR, and OMR/INR do NOT have usable direct tickers --
confirmed by actually running this script: "SARINR=X" and "KWDINR=X"
returned 404 "Quote not found", and "OMRINR=X" returned only 1 day
of history (effectively no real history). All three of those
currencies are pegged to the US Dollar, so instead this script
computes them as a cross rate through two tickers that DO have full
data: USD/INR ("INR=X") and USD/<currency> ("SAR=X", "KWD=X",
"OMR=X" -- these are the standard, liquid tickers everyone quotes
these currencies against, since they're USD-pegged). The math:
    <currency>/INR  =  (USD/INR)  /  (USD/<currency>)
e.g. 1 USD = 83 INR and 1 USD = 3.75 SAR, so 1 SAR = 83/3.75 INR.

Reuses the exact pattern 45_add_benchmark_indices.py already proved
out for multiple assets in one script.

IMPORTANT -- run 54_add_fx_asset_type.sql in Supabase's SQL Editor
FIRST. `assets.asset_type` doesn't allow 'fx' yet; this script's
insert will fail until that migration runs.

What this does, safe to run more than once (upserts everywhere):
  1. Ensures each FX pair exists as an `assets` row (asset_type='fx').
  2. Backfills 10 years of daily rate history into `prices_daily`
     (direct for USD/EUR/GBP/JPY/AED, computed cross-rate for
     SAR/KWD/OMR).
  3. Fetches today's live rate + day change into `live_prices`.

Run once, from inside TrueResearch Code (same venv as every other
pipeline script):
    venv\\Scripts\\python.exe 55_add_fx_assets.py
-------------------------------------------------------------------
"""
from db_client import get_client
from market_data_provider import get_live_price, get_price_history

# (ticker shown on the site, display name, yfinance symbol, cross-symbol)
# cross-symbol is None for a pair fetched directly from yfinance.
# When set, it means: this pair has no usable direct INR ticker, so
# compute it as (USD/INR) / (USD/<cross-symbol currency>) instead.
FX_PAIRS = [
    ("USDINR", "US Dollar / Indian Rupee", "INR=X", None),
    ("EURINR", "Euro / Indian Rupee", "EURINR=X", None),
    ("GBPINR", "British Pound / Indian Rupee", "GBPINR=X", None),
    ("JPYINR", "Japanese Yen / Indian Rupee", "JPYINR=X", None),
    ("AEDINR", "UAE Dirham / Indian Rupee", "AEDINR=X", None),
    ("SARINR", "Saudi Riyal / Indian Rupee", "SAR=X", "SAR=X"),
    ("KWDINR", "Kuwaiti Dinar / Indian Rupee", "KWD=X", "KWD=X"),
    ("OMRINR", "Omani Rial / Indian Rupee", "OMR=X", "OMR=X"),
]


def ensure_fx_asset(supabase, ticker: str, name: str, yf_symbol: str) -> int:
    existing = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", ticker)
        .eq("asset_type", "fx")
        .execute()
    )
    if existing.data:
        asset_id = existing.data[0]["asset_id"]
        # Keep the stored yfinance_symbol current -- SAR/KWD/OMR were
        # first inserted with a direct "SARINR=X"-style symbol that
        # turned out not to exist; this updates it to the cross-rate
        # symbol on a re-run without needing a fresh row.
        supabase.table("assets").update({"yfinance_symbol": yf_symbol}).eq("asset_id", asset_id).execute()
        return asset_id
    res = supabase.table("assets").insert({
        "ticker": ticker,
        "name": name,
        "asset_type": "fx",
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


def backfill_history_cross(supabase, asset_id: int, cross_symbol: str) -> int:
    """<currency>/INR = (USD/INR) / (USD/<currency>), aligned by date."""
    usdinr = get_price_history("INR=X", period="10y", interval="1d")
    usdxxx = get_price_history(cross_symbol, period="10y", interval="1d")
    if usdinr.empty or usdxxx.empty:
        return 0
    # Keep only dates present in both series.
    common_dates = usdinr.index.intersection(usdxxx.index)
    rows = []
    for idx in common_dates:
        a = usdinr.loc[idx]
        b = usdxxx.loc[idx]

        def cross(field):
            av, bv = a[field], b[field]
            if av != av or bv != bv or bv == 0:
                return None
            return float(av) / float(bv)

        rows.append({
            "asset_id": asset_id,
            "date": idx.strftime("%Y-%m-%d"),
            "open": cross("Open"),
            "high": cross("High"),
            "low": cross("Low"),
            "close": cross("Close"),
            "volume": None,
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


def refresh_live_cross(supabase, asset_id: int, cross_symbol: str) -> bool:
    usdinr = get_live_price("INR=X")
    usdxxx = get_live_price(cross_symbol)
    if usdinr is None or usdxxx is None or not usdxxx.get("price"):
        return False
    price = usdinr["price"] / usdxxx["price"]
    prev_close = None
    day_change_pct = None
    if usdinr.get("prev_close") and usdxxx.get("prev_close"):
        prev_close = usdinr["prev_close"] / usdxxx["prev_close"]
        if prev_close:
            day_change_pct = ((price - prev_close) / prev_close) * 100
    supabase.table("live_prices").upsert({
        "asset_id": asset_id,
        "price": price,
        "prev_close": prev_close,
        "day_change_pct": day_change_pct,
    }, on_conflict="asset_id").execute()
    return True


def main():
    supabase = get_client()
    for ticker, name, yf_symbol, cross_symbol in FX_PAIRS:
        print(f"\n{name} ({ticker}, {yf_symbol})")
        asset_id = ensure_fx_asset(supabase, ticker, name, yf_symbol)
        print(f"  asset_id={asset_id}")

        if cross_symbol:
            n = backfill_history_cross(supabase, asset_id, cross_symbol)
        else:
            n = backfill_history(supabase, asset_id, yf_symbol)
        print(f"  backfilled {n} days of history")

        if cross_symbol:
            ok = refresh_live_cross(supabase, asset_id, cross_symbol)
        else:
            ok = refresh_live(supabase, asset_id, yf_symbol)
        print(f"  live rate refreshed: {'ok' if ok else 'FAILED -- check yfinance symbol'}")

    print("\nDone. Other Assets -> FX can now read real data from `assets`/`prices_daily`/`live_prices`.")


if __name__ == "__main__":
    main()
