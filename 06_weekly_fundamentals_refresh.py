"""
06_weekly_fundamentals_refresh.py
-------------------------------------------------------------------
Phase B, Step 5b: the slower, weekly-cadence job -- replaces
refresh_weekly_data.py. Meant to run once a week (GitHub Actions,
same idea as your old .github/workflows/refresh-weekly.yml).

What it does, for every active equity asset in the database:
  1. Fetches each company's own annual financial statements (income
     statement, balance sheet, cash flow) and upserts any NEW fiscal
     year rows into `fundamentals`. Exact same field-cleaning logic as
     your old script: yfinance returns real NaN floats (not None) for
     missing line items, and a period where EVERY field is missing
     isn't a real fiscal year -- both are skipped, never written as
     fake zeros or the literal text "nan".
  2. Fetches the current market snapshot (P/E, P/B, market cap,
     52-week high/low) and upserts a new `ratios_snapshot` row dated
     today, for every stock -- not just ones with a research deck.
  3. On any failure for a stock, that stock's existing data is left
     completely untouched (never wiped to null) -- same principle as
     your old script -- and it's recorded in this run's failed list.

Run manually:
    python 06_weekly_fundamentals_refresh.py
-------------------------------------------------------------------
"""
import time
from datetime import date

import pandas as pd

from db_client import get_client
from market_data_provider import get_financial_statements, get_fundamentals
from ingestion_log import start_run, finish_run

INCOME_ROWS = ["Total Revenue", "Net Income", "EBIT", "EBITDA"]
BALANCE_ROWS = ["Total Debt", "Stockholders Equity", "Cash And Cash Equivalents", "Total Assets"]
CASHFLOW_ROWS = ["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"]
ALL_ROWS = INCOME_ROWS + BALANCE_ROWS + CASHFLOW_ROWS

# Maps yfinance's statement row names -> our fundamentals table's column names.
COLUMN_MAP = {
    "Total Revenue": "total_revenue",
    "Net Income": "net_income",
    "EBIT": "ebit",
    "EBITDA": "ebitda",
    "Total Debt": "total_debt",
    "Stockholders Equity": "stockholders_equity",
    "Cash And Cash Equivalents": "cash",
    "Total Assets": "total_assets",
    "Free Cash Flow": "free_cash_flow",
    "Operating Cash Flow": "operating_cash_flow",
    "Capital Expenditure": "capex",
}


def _clean(v):
    """None AND pandas/NumPy NaN both mean "missing" -- yfinance returns
    real NaN floats (not None) for a line item a company didn't report
    that period. Same fix your old script needed after a real PR review
    caught literal "nan" text in a CSV."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _fetch_statement_rows(statement, rows):
    out = {}
    if statement is None or statement.empty:
        return out
    for row_name in rows:
        if row_name not in statement.index:
            continue
        series = statement.loc[row_name]
        for period, value in series.items():
            date_str = period.strftime("%Y-%m-%d") if hasattr(period, "strftime") else str(period)
            out.setdefault(date_str, {})[row_name] = value
    return out


def refresh_one_stock_fundamentals(supabase, asset_id, yf_symbol):
    statements = get_financial_statements(yf_symbol)
    merged = {}
    for statement, rows in (
        (statements["income_stmt"], INCOME_ROWS),
        (statements["balance_sheet"], BALANCE_ROWS),
        (statements["cashflow"], CASHFLOW_ROWS),
    ):
        for date_str, values in _fetch_statement_rows(statement, rows).items():
            merged.setdefault(date_str, {}).update(values)

    wrote_any = False
    for date_str in sorted(merged.keys()):
        r = merged[date_str]
        cleaned = {key: _clean(r.get(key)) for key in ALL_ROWS}
        if all(v is None for v in cleaned.values()):
            continue  # not a real fiscal year -- some tickers return an empty placeholder column
        net_income, equity = cleaned.get("Net Income"), cleaned.get("Stockholders Equity")
        roe = (net_income / equity) if (net_income is not None and equity not in (None, 0)) else None

        payload = {"asset_id": asset_id, "fiscal_year_end_date": date_str, "roe": roe}
        for yf_name, col_name in COLUMN_MAP.items():
            payload[col_name] = cleaned[yf_name]
        supabase.table("fundamentals").upsert(
            payload, on_conflict="asset_id,fiscal_year_end_date"
        ).execute()
        wrote_any = True
    return wrote_any


def refresh_one_stock_ratios(supabase, asset_id, yf_symbol, today):
    info = get_fundamentals(yf_symbol)
    snap = {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "market_cap": info.get("marketCap"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
    }
    if all(v is None for v in snap.values()):
        return False  # yfinance didn't error, but gave us nothing usable -- treat as a failure, same as old script
    supabase.table("ratios_snapshot").upsert({
        "asset_id": asset_id,
        "as_of_date": today,
        **snap,
    }, on_conflict="asset_id,as_of_date").execute()
    return True


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
    today = date.today().isoformat()
    print(f"Refreshing fundamentals + ratios for {len(assets)} equities. This is the slow job -- it'll take a while.")

    run_id = start_run("weekly_fundamentals")
    ok_count = 0
    failed_symbols = []

    for i, a in enumerate(assets, 1):
        yf_symbol = a.get("yfinance_symbol")
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        if not yf_symbol:
            failed_symbols.append(ticker)
            continue

        fund_ok = False
        ratios_ok = False
        try:
            fund_ok = refresh_one_stock_fundamentals(supabase, asset_id, yf_symbol)
        except Exception as e:
            print(f"  ! {ticker} fundamentals: {e}")
        try:
            ratios_ok = refresh_one_stock_ratios(supabase, asset_id, yf_symbol, today)
        except Exception as e:
            print(f"  ! {ticker} ratios: {e}")

        if fund_ok or ratios_ok:
            ok_count += 1
        else:
            failed_symbols.append(ticker)

        if i % 20 == 0:
            print(f"  [{i}/{len(assets)}] processed...")
        time.sleep(0.3)  # be polite to Yahoo Finance, same pacing as the old script

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(assets)} ok. Failed: {failed_symbols if failed_symbols else 'none'}")


if __name__ == "__main__":
    main()
