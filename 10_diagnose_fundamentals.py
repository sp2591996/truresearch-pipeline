"""
10_diagnose_fundamentals.py
-------------------------------------------------------------------
One-time diagnostic: 09_build_training_data.py built rows for almost
only recently-listed companies and ZERO rows for old, established ones
like RELIANCE and TCS -- the opposite of what we'd expect. This script
prints exactly what data we have for a couple of sample stocks so we
can see the real cause instead of guessing.

Run with:
    python 10_diagnose_fundamentals.py
-------------------------------------------------------------------
"""
from db_client import get_client

SAMPLE_TICKERS = ["RELIANCE", "TCS", "NYKAA", "SWIGGY"]


def main():
    supabase = get_client()

    for ticker in SAMPLE_TICKERS:
        print(f"\n===== {ticker} =====")
        asset_res = (
            supabase.table("assets")
            .select("asset_id, ticker, asset_type, is_active")
            .eq("ticker", ticker)
            .execute()
        )
        if not asset_res.data:
            print("  No asset row found at all!")
            continue
        asset = asset_res.data[0]
        asset_id = asset["asset_id"]
        print(f"  asset_id={asset_id}  asset_type={asset['asset_type']}  is_active={asset['is_active']}")

        prices_res = (
            supabase.table("prices_daily")
            .select("date")
            .eq("asset_id", asset_id)
            .order("date")
            .limit(5000)
            .execute()
        )
        prices = prices_res.data
        if prices:
            print(f"  prices_daily: {len(prices)} rows, from {prices[0]['date']} to {prices[-1]['date']}")
        else:
            print("  prices_daily: 0 rows")

        fund_res = (
            supabase.table("fundamentals")
            .select("fiscal_year_end_date, total_revenue, net_income, total_debt, stockholders_equity")
            .eq("asset_id", asset_id)
            .order("fiscal_year_end_date")
            .execute()
        )
        fund = fund_res.data
        if fund:
            print(f"  fundamentals: {len(fund)} rows")
            for row in fund:
                print(f"    {row}")
        else:
            print("  fundamentals: 0 rows")


if __name__ == "__main__":
    main()
