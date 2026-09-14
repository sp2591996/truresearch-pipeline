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
  2. Fetches the current market snapshot and upserts a new
     `ratios_snapshot` row dated today, for every stock -- not just
     ones with a research deck.
  3. On any failure for a stock, that stock's existing data is left
     completely untouched (never wiped to null) -- same principle as
     your old script -- and it's recorded in this run's failed list.

Session 12 round 7 fix (diagnostic script 28 found this): this script
originally only ever wrote pe_ratio, pb_ratio, market_cap, and the
52-week high/low into `ratios_snapshot` -- ev_ebitda, price_to_sales,
roce, debt_equity, and margin were columns that existed in the
database and were displayed on the frontend, but were NEVER actually
populated by any script. 0% of all 500 stocks had a value in any of
them. Fixed here:
  - ev_ebitda, price_to_sales, debt_equity, margin: yfinance's `.info`
    already has these (enterpriseToEbitda, priceToSalesTrailing12Months,
    debtToEquity, profitMargins) -- they just weren't being read.
  - debt_equity specifically: yfinance reports this as a PERCENTAGE
    (e.g. 41.5 meaning a 0.415 ratio), but the frontend shows
    ratios_snapshot.debt_equity as a raw, un-multiplied ratio -- so
    it's divided by 100 here to match what's actually displayed.
  - roce: yfinance has no ROCE field at all. Computed here as
    EBIT / (Total Debt + Stockholders Equity) from the same annual
    financial statements already being fetched for `fundamentals` in
    step 1 -- Capital Employed approximated as Total Debt +
    Stockholders Equity since Current Liabilities isn't a field this
    project stores. A standard simplification when only debt+equity
    figures are on hand, not the textbook-precise version -- documented
    here rather than silently treated as exact.

Phase 1 (US expansion) fix: now that the `assets` table can hold
non-India stocks too (see 66_add_market_column.sql), this script
only ever touches India's stocks (`.eq("market", "india")`). The new
US stocks get their own separate backfill/refresh scripts, run on
their own schedule, once the US ML model work is far enough along.

Session 33 (Stage 2 fast-follow): with the India universe now at
2,568 stocks (up from ~500), added optional --batch-index=N
--batch-count=M args so GitHub Actions can split this into several
parallel jobs, each handling roughly 1/M of the stocks (same idea as
05_daily_price_refresh.py) -- see
.github/workflows/weekly-fundamentals.yml, which now runs 3 batches
in parallel via a matrix strategy. Manual/local runs are unaffected
-- omit both args (or leave batch-count at 1) to process every
stock, exactly as before.

Run manually:
    python 06_weekly_fundamentals_refresh.py
    python 06_weekly_fundamentals_refresh.py --batch-index=0 --batch-count=3   (process only batch 1 of 3)
-------------------------------------------------------------------
"""
import sys
import time
from datetime import date

import pandas as pd

from db_client import get_client
from market_data_provider import get_financial_statements, get_fundamentals
from ingestion_log import start_run, finish_run


def _get_arg(name: str, default: str) -> str:
    prefix = f"--{name}="
    for arg in sys.argv:
        if arg.startswith(prefix):
            return arg[len(prefix):]
    return default

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
    latest_roce = None
    for date_str in sorted(merged.keys()):
        r = merged[date_str]
        cleaned = {key: _clean(r.get(key)) for key in ALL_ROWS}
        if all(v is None for v in cleaned.values()):
            continue  # not a real fiscal year -- some tickers return an empty placeholder column
        net_income, equity = cleaned.get("Net Income"), cleaned.get("Stockholders Equity")
        roe = (net_income / equity) if (net_income is not None and equity not in (None, 0)) else None

        # ROCE = EBIT / Capital Employed. Capital Employed approximated
        # as Total Debt + Stockholders Equity (see file header note) --
        # only computed, not written to `fundamentals` (that table has
        # no roce column); the most recent fiscal year's value is
        # returned below so main() can pass it into ratios_snapshot.
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

    # yfinance reports debtToEquity as a PERCENTAGE (e.g. 41.5 meaning a
    # 0.415 ratio) -- the frontend shows ratios_snapshot.debt_equity as
    # a raw, un-multiplied ratio, so this divides by 100 to match what's
    # actually displayed elsewhere on the site.
    debt_equity_pct = info.get("debtToEquity")
    debt_equity = (debt_equity_pct / 100) if debt_equity_pct is not None else None

    snap = {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "market_cap": info.get("marketCap"),
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        # Previously never populated at all (Session 12 round 7 fix --
        # see file header). yfinance already exposes the first three;
        # roce is computed in refresh_one_stock_fundamentals above and
        # passed in here since yfinance has no field for it.
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "margin": info.get("profitMargins"),
        "debt_equity": debt_equity,
        "roce": roce,
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

    # Supabase/PostgREST silently caps any .select() at 1000 rows unless
    # you page through it with .range() -- the same gotcha this project
    # already hit and fixed elsewhere (Gold chart, sector assignment,
    # price-history backfill). With 2,000+ India equities now, a single
    # un-paginated query here would only ever refresh the first 1,000.
    assets = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, yfinance_symbol")
            .eq("asset_type", "equity")
            .eq("is_active", True)
            .eq("market", "india")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    batch_index = int(_get_arg("batch-index", "0"))
    batch_count = int(_get_arg("batch-count", "1"))
    if batch_count > 1:
        total = len(assets)
        chunk_size = -(-total // batch_count)  # ceil division, so every batch is used
        start = batch_index * chunk_size
        end = start + chunk_size
        assets = assets[start:end]
        print(f"Batch {batch_index + 1}/{batch_count}: refreshing fundamentals + ratios for {len(assets)} of {total} equities...")
    else:
        print(f"Refreshing fundamentals + ratios for {len(assets)} equities. This is the slow job -- it'll take a while.")

    today = date.today().isoformat()
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

        if i % 5 == 0:
            print(f"  [{i}/{len(assets)}] processed... (ok so far: {ok_count}, failed so far: {len(failed_symbols)})")
        time.sleep(0.3)  # be polite to Yahoo Finance, same pacing as the old script

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(assets)} ok. Failed: {failed_symbols if failed_symbols else 'none'}")


if __name__ == "__main__":
    main()
