"""
167_fetch_quarterly_pnl_all_stocks.py
-------------------------------------------------------------------
Fills the new `quarterly_pnl` table (166_create_quarterly_pnl_table.sql
-- run that SQL file in Supabase first) for ALL Nifty 500 stocks, not
just the 26 banks that 165_fetch_bank_quarterly_pnl.py covers.
Avdhoot's ask (2026-10-05): "Lets extract for all the 500 stocks this,
not just 26 banks."

Ticker list source: nifty500_master_tickers.txt (one ticker per line,
500 total) -- the same authoritative Nifty 500 list already used
elsewhere in this project (e.g. 163_reclassify_bank_industries.py).
Using this file, not just "every India equity in the assets table",
because the Nifty-500-narrowing migration (131_...) may not have been
run yet -- this keeps the fetch scoped correctly either way.

Data source: NSE's own official `results_comparison` endpoint (the
`nse` PyPI package -- same as 165, legal, no scraping). Gives the
last ~5 quarters of summary P&L (Total Income, Net Profit, EPS) --
NOT a full line-by-line statement, NOT 10 years of history.

Amounts arrive from NSE in Rupees LAKHS -- converted to CRORES
(divide by 100) to match every other number already on the site.

This is a bigger run than 165 (500 stocks vs 26) -- expect it to take
roughly 10-20 minutes, since each stock is fetched one at a time with
a small delay to stay polite to NSE's servers (same rate-limit
approach already used throughout this project, e.g. 05/74_daily_price_refresh.py).
Safe to re-run any time -- it just overwrites each quarter's row with
NSE's latest figures.

Run manually:
    python 167_fetch_quarterly_pnl_all_stocks.py
-------------------------------------------------------------------
"""
import os
import tempfile
import time
from datetime import datetime

from nse import NSE

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "india"
REQUEST_DELAY_SECONDS = 0.5
RETRY_DELAY_SECONDS = 5
TICKER_FILE = os.path.join(os.path.dirname(__file__), "nifty500_master_tickers.txt")


def load_ticker_list():
    with open(TICKER_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_date(value):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def to_crores(lakhs_value):
    if lakhs_value is None or lakhs_value == "":
        return None
    try:
        return float(lakhs_value) / 100
    except (TypeError, ValueError):
        return None


def fetch_with_retry(nse, symbol):
    try:
        return nse.results_comparison(symbol)
    except Exception:
        time.sleep(RETRY_DELAY_SECONDS)
        return nse.results_comparison(symbol)  # let a second failure raise normally


def main():
    supabase = get_client()
    nifty500_tickers = load_ticker_list()
    print(f"Loaded {len(nifty500_tickers)} tickers from {os.path.basename(TICKER_FILE)}")

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker")
        .eq("market", MARKET)
        .eq("asset_type", "equity")
        .in_("ticker", nifty500_tickers)
        .execute()
    )
    asset_by_ticker = {a["ticker"]: a["asset_id"] for a in assets_res.data}
    missing = [t for t in nifty500_tickers if t not in asset_by_ticker]
    if missing:
        print(f"WARNING: {len(missing)} ticker(s) not found in assets table, skipping: {', '.join(missing)}")

    print(f"\nFetching quarterly P&L for {len(asset_by_ticker)} stocks from NSE...")
    print("(This covers all Nifty 500 stocks, not just banks -- expect ~10-20 minutes.)\n")

    run_id = start_run("quarterly_pnl")
    ok_count = 0
    quarters_saved = 0
    failed_symbols = []

    with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
        for i, (ticker, asset_id) in enumerate(asset_by_ticker.items(), 1):
            print(f"[{i}/{len(asset_by_ticker)}] {ticker} ...", end=" ")
            try:
                data = fetch_with_retry(nse, ticker)
            except Exception as e:
                print(f"skipped (couldn't fetch: {e})")
                failed_symbols.append(ticker)
                time.sleep(REQUEST_DELAY_SECONDS)
                continue
            time.sleep(REQUEST_DELAY_SECONDS)

            rows = (data or {}).get("resCmpData") or []
            if not rows:
                print("skipped (no quarterly data returned)")
                failed_symbols.append(ticker)
                continue

            saved_this_stock = 0
            for r in rows:
                period_end = parse_date(r.get("re_to_dt"))
                if not period_end:
                    continue
                is_consolidated = "consolidated" in (r.get("re_cons") or "").lower()
                record = {
                    "asset_id": asset_id,
                    "period_end_date": period_end,
                    "relating_to": r.get("re_relate_to"),
                    "total_income_cr": to_crores(r.get("re_total_inc")),
                    "net_profit_cr": to_crores(r.get("re_net_profit")),
                    "eps": r.get("re_basic_eps"),
                    "is_audited": (r.get("re_audited") or "").upper().startswith("A") or None,
                    "is_consolidated": is_consolidated,
                    "source": "nse",
                }
                supabase.table("quarterly_pnl").upsert(
                    record, on_conflict="asset_id,period_end_date,is_consolidated"
                ).execute()
                saved_this_stock += 1

            quarters_saved += saved_this_stock
            ok_count += 1
            print(f"{saved_this_stock} quarters saved")

    finish_run(run_id, ok_count=ok_count, failed_symbols=failed_symbols)

    print(f"\nDone. {ok_count}/{len(asset_by_ticker)} stocks updated, {quarters_saved} quarter-rows saved.")
    if failed_symbols:
        print(f"{len(failed_symbols)} stock(s) had no usable data: {', '.join(failed_symbols)}")
        print("(NSE's own feed may simply not have recent filings for these -- not necessarily a bug.)")


if __name__ == "__main__":
    main()
