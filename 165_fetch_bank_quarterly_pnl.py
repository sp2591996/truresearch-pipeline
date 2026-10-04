"""
165_fetch_bank_quarterly_pnl.py
-------------------------------------------------------------------
Fills the new `bank_quarterly_pnl` table (164_create_bank_quarterly_pnl.sql
-- run that SQL file in Supabase first) for the 38 bank stocks that
have a Deepdive page (same ticker list as 163_reclassify_bank_industries.py).

Data source: NSE's own official `results_comparison` endpoint (the
`nse` PyPI package, already used elsewhere in this project for
shareholding_pattern/ipos -- legal, no scraping). This gives the last
~5 quarters of summary P&L figures (Total Income, Net Profit, EPS) --
NOT a full line-by-line statement, and NOT 10 years of history. See
PROJECT_STATE.md for why a fuller version isn't realistically
available for free.

Amounts arrive from NSE in Rupees LAKHS -- this script converts to
CRORES (divide by 100) to match every other number already on the
site.

Run manually (safe to re-run any time -- it just overwrites each
quarter's row with the latest figures NSE has):
    python 165_fetch_bank_quarterly_pnl.py
-------------------------------------------------------------------
"""
import tempfile
import time
from datetime import datetime

from nse import NSE

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "india"
REQUEST_DELAY_SECONDS = 0.5
RETRY_DELAY_SECONDS = 5

# Same 38 tickers as 163_reclassify_bank_industries.py.
BANK_TICKERS = [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
    "FEDERALBNK", "IDFCFIRSTB", "BANDHANBNK", "YESBANK", "RBLBANK",
    "IDBI", "CSBBANK", "DCBBANK", "SOUTHBANK", "KTKBANK", "TMB",
    "J&KBANK", "DHANBANK", "KARURVYSYA", "CUB",
    "SBIN", "PNB", "BANKBARODA", "CANBK", "UNIONBANK", "INDIANB",
    "BANKINDIA", "CENTRALBK", "IOB", "UCOBANK", "MAHABANK", "PSB",
    "AUBANK", "EQUITASBNK", "UJJIVANSFB", "JSFB", "UTKARSHBNK", "ESAFSFB",
]


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

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker")
        .eq("market", MARKET)
        .eq("asset_type", "equity")
        .in_("ticker", BANK_TICKERS)
        .execute()
    )
    asset_by_ticker = {a["ticker"]: a["asset_id"] for a in assets_res.data}
    missing = [t for t in BANK_TICKERS if t not in asset_by_ticker]
    if missing:
        print(f"WARNING: {len(missing)} ticker(s) not found in assets table, skipping: {', '.join(missing)}")

    # Quick coverage check on the EXISTING annual fundamentals table too --
    # this feeds the Balance Sheet / Cash Flow views in the new tab, and
    # we've never explicitly confirmed it covers all 38 bank stocks.
    fund_res = (
        supabase.table("fundamentals")
        .select("asset_id, fiscal_year_end_date")
        .in_("asset_id", list(asset_by_ticker.values()))
        .execute()
    )
    years_by_asset = {}
    for row in fund_res.data:
        years_by_asset.setdefault(row["asset_id"], set()).add(row["fiscal_year_end_date"][:4])
    no_annual_data = [t for t, aid in asset_by_ticker.items() if aid not in years_by_asset]
    thin_annual_data = [
        (t, len(years_by_asset[aid])) for t, aid in asset_by_ticker.items()
        if aid in years_by_asset and len(years_by_asset[aid]) < 3
    ]
    print("Annual fundamentals (Balance Sheet / Cash Flow source) coverage check:")
    print(f"  {len(asset_by_ticker) - len(no_annual_data)}/{len(asset_by_ticker)} bank stocks have at least 1 year of annual data")
    if no_annual_data:
        print(f"  NO annual data at all: {', '.join(no_annual_data)}")
    if thin_annual_data:
        print(f"  Fewer than 3 years of annual data: {', '.join(f'{t} ({n}yr)' for t, n in thin_annual_data)}")
    print()

    print(f"Fetching quarterly P&L for {len(asset_by_ticker)} bank stocks from NSE...\n")

    run_id = start_run("bank_quarterly_pnl")
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
                supabase.table("bank_quarterly_pnl").upsert(
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
