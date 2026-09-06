"""
09_build_training_data.py
-------------------------------------------------------------------
Phase B, Step 6b: build our OWN training dataset from OUR Supabase
database (not the old CSV files), replicating the original model's
methodology exactly:

  - Technical indicators computed from prices_daily (RSI-14, 50/200-day
    moving averages, 1/3/6-month returns, 30-day annualized volatility)
  - Fundamentals looked up "point-in-time correct" -- for any historical
    snapshot date, we only use a fundamentals row if its fiscal year end
    + 120 days has ALREADY PASSED as of that date. This matches how long
    it actually takes a company to publish results in real life, so the
    model never accidentally "sees the future" during training.
  - Label = "did this stock beat the Nifty 100 benchmark over the NEXT
    3 months" (excess return), not just "did the stock go up"
  - One training snapshot taken every ~21 trading days (~monthly) per
    stock, so one stock contributes many rows across its 10-year history

FIX (this session): a prior version of this script SKIPPED any snapshot
date entirely if fundamentals weren't usable yet for that stock at that
point in time. That's NOT what the original StockApp experiment did --
comparing row-by-row against the original training_dataset.csv showed
it kept those early "technical-only" snapshots (price/momentum data
exists, fundamentals columns just left blank/NaN), from as far back as
August 2022, and let XGBoost handle the missing values natively (it's
built to do this). Skipping those rows entirely cut the original's
2022 Q3-2023 Q2 row count from 900+ down to about 70, which meant the
walk-forward validation couldn't even start testing until 2024 Q1
instead of the original's 2023 Q2 -- a full three quarters of already-
proven validation history lost for no real reason. This version now
KEEPS a snapshot row even when fundamentals aren't usable yet, leaving
those columns blank, exactly matching the original's approach.

NOTE on scope: the original StockApp project also used macro data
(USD/INR, Brent crude, gold, repo rate). We do not have a macro data
table/ingestion pipeline in TrueResearch yet, so this version leaves
macro features out. Everything else is replicated faithfully. We can
add macro data as a later enhancement if it proves valuable.

Output: writes "training_dataset.csv" in this same folder. This is a
one-time, throwaway intermediate file used only to train the model in
the next script -- it is not loaded into Supabase.

Run with (after 08_backfill_price_history.py has completed):
    python 09_build_training_data.py
-------------------------------------------------------------------
"""
import pandas as pd

from db_client import get_client

OUTPUT_FILE = "training_dataset.csv"
FORWARD_WINDOW_DAYS = 63   # ~3 trading months, matches the original model
SAMPLE_EVERY = 21          # ~1 trading month between snapshots
MIN_HISTORY_DAYS = 264     # need at least this many days of price history to bother
FISCAL_LAG_DAYS = 120      # a fiscal year's results aren't public until ~120 days after year-end


def fetch_price_history(supabase, asset_id: int) -> pd.DataFrame:
    # Supabase caps each request at 1000 rows regardless of .limit(), so a
    # stock with 10 years of daily history (~2500 rows) needs multiple pages
    # fetched with .range() -- otherwise only the OLDEST 1000 rows come back
    # and recent years silently go missing.
    PAGE_SIZE = 1000
    all_rows = []
    start = 0
    while True:
        res = (
            supabase.table("prices_daily")
            .select("date, open, high, low, close, volume")
            .eq("asset_id", asset_id)
            .order("date")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        page = res.data
        all_rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def compute_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["MA50"] = df["close"].rolling(window=50).mean()
    df["MA200"] = df["close"].rolling(window=200).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["Return_1M"] = df["close"].pct_change(21)
    df["Return_3M"] = df["close"].pct_change(63)
    df["Return_6M"] = df["close"].pct_change(126)

    daily_returns = df["close"].pct_change()
    df["Volatility_30D"] = daily_returns.rolling(window=30).std() * (252 ** 0.5)
    return df


def fetch_fundamentals(supabase, asset_id: int) -> pd.DataFrame:
    res = (
        supabase.table("fundamentals")
        .select("*")
        .eq("asset_id", asset_id)
        .order("fiscal_year_end_date")
        .execute()
    )
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    df["fiscal_year_end_date"] = pd.to_datetime(df["fiscal_year_end_date"])
    df = df.sort_values("fiscal_year_end_date").reset_index(drop=True)

    df["Revenue_Growth_YoY"] = df["total_revenue"].pct_change().clip(-1, 2)
    df["NetIncome_Growth_YoY"] = df["net_income"].pct_change().clip(-2, 3)
    df["Debt_to_Equity"] = df["total_debt"] / df["stockholders_equity"]
    return df


def latest_usable_fundamentals(fundamentals: pd.DataFrame, snapshot_date):
    if fundamentals.empty:
        return None, None
    usable = fundamentals[
        fundamentals["fiscal_year_end_date"] + pd.Timedelta(days=FISCAL_LAG_DAYS) <= snapshot_date
    ]
    if usable.empty:
        return None, None
    latest = usable.iloc[-1]
    prior = usable.iloc[-2] if len(usable) >= 2 else None
    return latest, prior


def capex_intensity_yoy_change(latest, prior):
    if latest is None or prior is None:
        return None
    try:
        latest_capex_pct = None
        prior_capex_pct = None
        if pd.notna(latest.get("capex")) and pd.notna(latest.get("total_revenue")) and latest.get("total_revenue"):
            latest_capex_pct = abs(latest["capex"]) / latest["total_revenue"]
        if pd.notna(prior.get("capex")) and pd.notna(prior.get("total_revenue")) and prior.get("total_revenue"):
            prior_capex_pct = abs(prior["capex"]) / prior["total_revenue"]
        if latest_capex_pct is not None and prior_capex_pct is not None and prior_capex_pct:
            return (latest_capex_pct - prior_capex_pct) / prior_capex_pct
    except Exception:
        pass
    return None


def main():
    supabase = get_client()

    print("Loading Nifty 100 benchmark price history...")
    bench_asset = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", "NIFTY100")
        .eq("asset_type", "index")
        .execute()
    )
    if not bench_asset.data:
        print("ERROR: Nifty 100 benchmark asset not found. Run 08_backfill_price_history.py first.")
        return
    benchmark_asset_id = bench_asset.data[0]["asset_id"]
    benchmark = fetch_price_history(supabase, benchmark_asset_id)
    if benchmark.empty:
        print("ERROR: Benchmark has no price history.")
        return
    print(f"  -> {len(benchmark)} days of benchmark history loaded.\n")

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, sector_id, sectors(name)")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Building training rows for {len(assets)} stocks...\n")

    all_rows = []
    error_count = 0
    rows_without_fundamentals = 0

    for i, a in enumerate(assets, 1):
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        sector_name = (a.get("sectors") or {}).get("name") if a.get("sectors") else None
        print(f"[{i}/{len(assets)}] {ticker} ...")

        try:
            prices = fetch_price_history(supabase, asset_id)
            if prices.empty or len(prices) < MIN_HISTORY_DAYS:
                print(f"  -> skipped (not enough price history: {len(prices)} days)")
                continue

            indicators = compute_indicators(prices)
            fundamentals = fetch_fundamentals(supabase, asset_id)

            valid_dates = indicators.index[
                (indicators.index >= indicators.index[200])
                & (indicators.index <= indicators.index[-64])
            ]
            sampled_dates = valid_dates[::SAMPLE_EVERY]

            rows_this_stock = 0
            for snapshot_date in sampled_dates:
                tech_row = indicators.loc[snapshot_date]

                # FIX: no longer skip the row when fundamentals aren't usable
                # yet -- keep the technical-only snapshot with blank
                # fundamentals fields, matching the original methodology.
                latest_fund, prior_fund = latest_usable_fundamentals(fundamentals, snapshot_date)
                if latest_fund is None:
                    rows_without_fundamentals += 1

                future_idx = indicators.index.get_loc(snapshot_date) + FORWARD_WINDOW_DAYS
                if future_idx >= len(indicators.index):
                    continue
                future_date = indicators.index[future_idx]

                stock_return = (indicators.loc[future_date, "close"] / indicators.loc[snapshot_date, "close"]) - 1

                bench_now_series = benchmark.loc[benchmark.index <= snapshot_date, "close"]
                bench_future_series = benchmark.loc[benchmark.index <= future_date, "close"]
                if bench_now_series.empty or bench_future_series.empty:
                    continue
                bench_now = bench_now_series.iloc[-1]
                bench_future = bench_future_series.iloc[-1]
                benchmark_return = (bench_future / bench_now) - 1

                past_bench_series = benchmark.loc[benchmark.index <= (snapshot_date - pd.Timedelta(days=90)), "close"]
                benchmark_past_return = (bench_now / past_bench_series.iloc[-1]) - 1 if not past_bench_series.empty else 0

                relative_strength_3M = tech_row["Return_3M"] - benchmark_past_return
                excess_return = stock_return - benchmark_return

                row = {
                    "Symbol": ticker,
                    "Sector": sector_name,
                    "Date": snapshot_date,
                    "RSI": tech_row["RSI"],
                    "MA50": tech_row["MA50"],
                    "MA200": tech_row["MA200"],
                    "Return_1M": tech_row["Return_1M"],
                    "Return_3M": tech_row["Return_3M"],
                    "Return_6M": tech_row["Return_6M"],
                    "Volatility_30D": tech_row["Volatility_30D"],
                    "Relative_Strength_3M": relative_strength_3M,
                    "ROE": latest_fund.get("roe") if latest_fund is not None else None,
                    "Debt_to_Equity": latest_fund.get("Debt_to_Equity") if latest_fund is not None else None,
                    "Revenue_Growth_YoY": latest_fund.get("Revenue_Growth_YoY") if latest_fund is not None else None,
                    "NetIncome_Growth_YoY": latest_fund.get("NetIncome_Growth_YoY") if latest_fund is not None else None,
                    "Net_Income": latest_fund.get("net_income") if latest_fund is not None else None,
                    "Total_Revenue": latest_fund.get("total_revenue") if latest_fund is not None else None,
                    "Total_Debt": latest_fund.get("total_debt") if latest_fund is not None else None,
                    "Stockholders_Equity": latest_fund.get("stockholders_equity") if latest_fund is not None else None,
                    "Capex_Intensity_YoY_Change": capex_intensity_yoy_change(latest_fund, prior_fund),
                    "Stock_Return_3M": stock_return,
                    "Benchmark_Return_3M": benchmark_return,
                    "Excess_Return_3M": excess_return,
                    "Label_Outperformed": 1 if stock_return > benchmark_return else 0,
                }
                all_rows.append(row)
                rows_this_stock += 1

            print(f"  -> {rows_this_stock} rows built")

        except Exception as e:
            print(f"  ERROR for {ticker}: {type(e).__name__}: {e}")
            error_count += 1

    training_df = pd.DataFrame(all_rows)
    training_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nDone! Built {len(training_df)} training rows across {len(assets)} stocks.")
    print(f"Rows built with blank/no fundamentals yet (technical-only, expected for early dates): {rows_without_fundamentals}")
    print(f"Stocks with errors: {error_count}")
    if len(training_df) > 0:
        print(f"Outperformed: {training_df['Label_Outperformed'].sum()} | Underperformed: {len(training_df) - training_df['Label_Outperformed'].sum()}")
        print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
