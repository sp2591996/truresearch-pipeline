"""
69_backfill_us_fundamentals.py
-------------------------------------------------------------------
Phase 1 (US expansion), Step 4: one-time fundamentals + ratios load
for every S&P 500 stock added by 67_add_sp500_stocks.py.

This is the direct US equivalent of 06_weekly_fundamentals_refresh.py
-- exact same logic (annual financial statements into `fundamentals`,
current market snapshot into `ratios_snapshot`), just scoped to
`market = "usa"`. yfinance's annual statements already return several
years of history in a single call, so running this once gives enough
historical fundamentals data for the growth score and for building a
US training dataset later -- this script also doubles as the ongoing
weekly refresh job for US stocks once the US market goes live (just
keep re-running it on a schedule, same as 06 does for India).

Same field-cleaning rules as 06: yfinance returns real NaN floats
(not None) for missing line items, and a fiscal year where EVERY
field is missing isn't a real year -- both are skipped rather than
written as fake zeros.

BEFORE YOU RUN THIS: run 67_add_sp500_stocks.py first (adds the
stocks this script fetches fundamentals for). This is the SLOW job
-- one call per stock for financial statements, another for the
current snapshot, with a polite pause between stocks -- expect it to
take a while for 503 stocks.

Run manually:
    python 69_backfill_us_fundamentals.py
-------------------------------------------------------------------
"""
import time
from datetime import date

import pandas as pd

from db_client import get_client
from market_data_provider import get_financial_statements, get_fundamentals
from ingestion_log import start_run, finish_run

MARKET = "usa"

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
    """None AND pandas/NumPy NaN both mean "missing" -- same fix 06 needed."""
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
    latest_roce = None
    for date_str in sorted(merged.keys()):
        r = merged[date_str]
        cleaned = {key: _clean(r.get(key)) for key in ALL_ROWS}
        if all(v is None for v in cleaned.values()):
            continue  # not a real fiscal year -- some tickers return an empty placeholder column
        net_income, equity = cleaned.get("Net Income"), cleaned.get("Stockholders Equity")
        roe = (net_income / equity) if (net_income is not None and equity not in (None, 0)) else None

        ebit, total_debt = cleaned.get("EBIT"), cleaned.get("Total Debt")
        capital_employed = (total_debt or 0) + (equity or 0)
        roce = (ebit / capital_employed) if (ebit is not None and capital_employed) else None

        payload = {"asset_id": asset_id, "fiscal_year_end_date": date_str, "roe": roe}
        for yf_name, col_name in COLUMN_MAP.items():
            payload[col_name] = cleaned[yf_name]
        supabase.table("fundamentals").upsert(
            payload, on_conflict="asset_id,fiscal_year_end_date"
        ).execute()
        wrote_any = True
        latest_roce = roce  # keys iterated oldest -> newest, so the last one is the latest fiscal year
    return wrote_any, latest_roce


def refresh_one_stock_ratios(supabase, asset_id, yf_symbol, today, roce=None):
    info = get_fundamentals(yf_symbol)

    debt_equity_pct = info.get("debtToEquity")
    debt_equity = (debt_equity_pct / 100) if debt_equity_pct is not None else None

    # USA "who owns this stock" stat card (76_add_ownership_columns.sql):
    # yfinance reports these as 0-1 fractions (e.g. 0.663 = 66.3%),
    # matching the *100 convention every other percentage column on this
    # page already uses (see roe/roce/margin math elsewhere in this
    # file) -- multiplied here so the frontend can display them
    # directly without its own conversion.
    insider_pct = info.get("heldPercentInsiders")
    institutional_pct = info.get("heldPercentInstitutions")

    snap = {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "market_cap": info.get("marketCap"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "margin": info.get("profitMargins"),
        "debt_equity": debt_equity,
        "roce": roce,
        "insider_ownership_pct": (insider_pct * 100) if insider_pct is not None else None,
        "institutional_ownership_pct": (institutional_pct * 100) if institutional_pct is not None else None,
    }
    if all(v is None for v in snap.values()):
        return False
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
        .eq("market", MARKET)
        .execute()
    )
    assets = assets_res.data
    today = date.today().isoformat()
    print(f"Refreshing fundamentals + ratios for {len(assets)} US equities. This is the slow job -- it'll take a while.")

    # Note: "weekly_fundamentals" is reused here (rather than a new
    # "us_fundamentals_backfill" label) because the `ingestion_runs`
    # table only accepts a fixed, pre-approved list of run_type values
    # (a database check constraint) -- reusing this existing, already-
    # allowed value avoids needing a schema change just for a log label.
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
        latest_roce = None
        try:
            fund_ok, latest_roce = refresh_one_stock_fundamentals(supabase, asset_id, yf_symbol)
        except Exception as e:
            print(f"  ! {ticker} fundamentals: {e}")
        try:
            ratios_ok = refresh_one_stock_ratios(supabase, asset_id, yf_symbol, today, roce=latest_roce)
        except Exception as e:
            print(f"  ! {ticker} ratios: {e}")

        if fund_ok or ratios_ok:
            ok_count += 1
        else:
            failed_symbols.append(ticker)

        if i % 20 == 0:
            print(f"  [{i}/{len(assets)}] processed...")
        time.sleep(0.3)

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(assets)} ok. Failed: {failed_symbols if failed_symbols else 'none'}")


if __name__ == "__main__":
    main()
