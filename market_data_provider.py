"""
market_data_provider.py
-------------------------------------------------------------------
THE DATA PROVIDER ABSTRACTION LAYER.

This is the ONLY file in the whole project allowed to import/call
`yfinance` directly. Every other script (ingestion pipelines, scoring
scripts, backfills) asks THIS file for market data instead of talking
to Yahoo Finance itself.

Why this matters (per PROJECT_STATE.md's locked tech-stack rule --
"never call yfinance directly from business logic"): if Yahoo Finance
ever changes its API, gets rate-limited, or we ever want to switch to
a paid/more reliable data source, we only have to change the *inside*
of the functions below. Every script that already calls
get_live_price(), get_price_history(), etc. keeps working exactly as
before, completely unaware anything changed underneath.

Functions provided:
    get_live_price(yf_symbol)          -> dict: current price + day change
    get_price_history(yf_symbol, period, interval) -> pandas DataFrame
    get_fundamentals(yf_symbol)        -> dict: latest company financials
    get_financial_statements(yf_symbol) -> dict: raw annual income/balance/cashflow statements
-------------------------------------------------------------------
"""
import yfinance as yf
import pandas as pd


def get_live_price(yf_symbol: str) -> dict:
    """Current price + previous close + day change %, for one stock.
    Example: get_live_price("RELIANCE.NS")
    Returns: {"price": 2851.10, "prev_close": 2828.20, "day_change_pct": 0.81}
    or None if the data isn't available (e.g. bad symbol, market data lag).
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        fi = ticker.fast_info
        last_price = getattr(fi, "last_price", None)
        prev_close = getattr(fi, "previous_close", None)
        if last_price is None or prev_close is None:
            return None
        day_change_pct = round((last_price - prev_close) / prev_close * 100, 2) if prev_close else None
        return {
            "price": round(float(last_price), 2),
            "prev_close": round(float(prev_close), 2),
            "day_change_pct": day_change_pct,
        }
    except Exception as e:
        print(f"  ! get_live_price failed for {yf_symbol}: {e}")
        return None


def get_price_history(yf_symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """Historical daily prices for one stock, going back `period`
    (default 5 years -- matches our agreed one-time backfill plan).
    Returns a pandas DataFrame with columns: Open, High, Low, Close, Volume
    (indexed by date), or an empty DataFrame if nothing was found.
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=period, interval=interval)
        return hist
    except Exception as e:
        print(f"  ! get_price_history failed for {yf_symbol}: {e}")
        return pd.DataFrame()


def get_fundamentals(yf_symbol: str) -> dict:
    """Latest available fundamentals snapshot for one stock (P/E, P/B,
    market cap, sector, etc. -- whatever Yahoo Finance's `.info` call
    currently exposes). This is the heavier, slower call -- use sparingly
    (weekly refresh), not on every page load.
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        return ticker.info or {}
    except Exception as e:
        print(f"  ! get_fundamentals failed for {yf_symbol}: {e}")
        return {}


def get_financial_statements(yf_symbol: str) -> dict:
    """Raw annual financial statements (income statement, balance sheet,
    cash flow) for one stock, as pandas DataFrames -- rows are line items
    (e.g. "Total Revenue"), columns are fiscal year-end dates. This is the
    heaviest call yfinance offers -- used only in the weekly fundamentals
    refresh, never the daily price job. Combining/interpreting these rows
    is the caller's job; this function's only job is being the one place
    that calls yfinance for this data.
    Returns {"income_stmt": DataFrame, "balance_sheet": DataFrame, "cashflow": DataFrame},
    with empty DataFrames for anything that fails.
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        return {
            "income_stmt": ticker.income_stmt,
            "balance_sheet": ticker.balance_sheet,
            "cashflow": ticker.cashflow,
        }
    except Exception as e:
        print(f"  ! get_financial_statements failed for {yf_symbol}: {e}")
        return {"income_stmt": pd.DataFrame(), "balance_sheet": pd.DataFrame(), "cashflow": pd.DataFrame()}


def get_listing_date(yf_symbol: str):
    """The date a stock first started trading, per Yahoo Finance's own
    record (`firstTradeDateEpochUtc`, inside the same `.info` call
    get_fundamentals() already uses). Added for TrueScore v2 (PRD.md M3)
    -- Legacy Score's interim definition is listing tenure, and this is
    the one place that's allowed to know HOW that date gets sourced.
    Returns a `datetime.date`, or None if Yahoo doesn't have it for this
    symbol (a handful of thinly-covered small-caps won't).
    """
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}
        epoch = info.get("firstTradeDateEpochUtc") or info.get("firstTradeDateMilliseconds")
        if epoch is None:
            return None
        # Yahoo has returned this in seconds in some SDK versions and
        # milliseconds in others -- a value bigger than ~year-3000-in-
        # seconds is almost certainly milliseconds, so this covers both
        # without needing to know which one this yfinance version gives.
        # BUG FIX: the ms-vs-seconds check below used to only look at
        # epoch > 10_000_000_000, which only ever catches LARGE POSITIVE
        # numbers. A stock listed well before 1970 (Coca-Cola, Chevron,
        # every other long-established US blue chip Yahoo flagged with
        # "date value out of range") comes back as a large NEGATIVE
        # milliseconds value instead -- abs() catches both directions.
        if abs(epoch) > 10_000_000_000:
            epoch = epoch / 1000
        # Windows-safe conversion: datetime.fromtimestamp() calls into the
        # OS's own C library on the backend, and Windows' version can't
        # handle dates before 1970 (or, on some builds, before 1980) --
        # exactly what a long-established company like Coca-Cola or
        # Chevron has (they started trading decades before that). Doing
        # the arithmetic in pure Python instead of asking the OS to do it
        # sidesteps that platform limit entirely, for any date, on any OS.
        from datetime import datetime, timedelta, timezone
        result = (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=epoch)).date()
        # Sanity clamp: no real stock exchange listing predates 1790 (the
        # NYSE's own founding) or lies in the future -- if either of
        # those happens, the source data itself is bad/garbled rather
        # than this conversion being wrong, so treat it as "unknown"
        # instead of writing a nonsense date into the database.
        if result.year < 1790 or result.year > datetime.now(timezone.utc).year:
            print(f"  ! get_listing_date got an implausible date ({result}) for {yf_symbol}, treating as unknown")
            return None
        return result
    except Exception as e:
        print(f"  ! get_listing_date failed for {yf_symbol}: {e}")
        return None
