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
