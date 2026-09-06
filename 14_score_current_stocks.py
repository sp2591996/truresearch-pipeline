"""
14_score_current_stocks.py
-------------------------------------------------------------------
Phase B, Step 6f (final step of Step 6): score today's stocks with
the validated model, and save real TrueScore rows into the database.

TrueScore is designed (per Database_Schema.md) as a combination of
factors, with only 2 confirmed today:
  1. Relative valuation  -- how cheap/expensive a stock is vs. its own
     sector peers, using P/E ratio (lower P/E among sector peers = higher
     score). Simple, transparent, sector-relative -- not the ML model.
  2. ML rank score -- this is where 11_train_model.py's trained model
     comes in: it predicts each stock's likely 3-month excess return,
     and stocks are ranked against each other on that prediction.

Both components are converted to a 0-100 percentile scale so they can
be combined consistently. Today's default weighting is 50% / 50% --
stored as DATA in `score_component_weights` (not hardcoded in this
script), so it can be changed per sector or per stock later without
touching any code, exactly per the flexible design in Database_Schema.md.

THIS IS formula_version truescore_v2 -- the final version after this
session's full Step 6 correction pass. Three real bugs were found and
fixed (see Step6_ML_Model_Decision_Log.md for the complete story):
  1. Feature drift -- now trains on exactly the 14 features of the
     original StockApp experiment's validated "Case C" model.
  2. Live-scoring bug -- Relative_Strength_3M is now correctly computed
     against the Nifty 100 benchmark's own return, matching training.
  3. Dataset-building bug -- 09_build_training_data.py now keeps
     technical-only rows (blank fundamentals) instead of dropping them,
     which combined with TrueResearch's full 10-year price history
     surfaced a 4th finding: training on ALL that history performed
     WORSE on recent quarters than a 2-YEAR ROLLING training window.
     That rolling window is now locked in (see 11_train_model.py) and
     out-performs the original StockApp experiment on a matched
     13-quarter comparison (11/13 positive, avg Rank IC 0.150 vs. the
     original's 12/13, avg IC ~0.133).

`truescore_rating` uses neutral, non-advisory band labels (Strong /
Above Average / Average / Below Average / Weak) -- per the locked
regulatory framing rule: "research signal, never advice."

Writes to:
  - score_formula_versions (registers "truescore_v2", the COMBINED
    formula for this run)
  - score_component_weights (the default 50/50 weighting, as data)
  - score_components (2 rows per stock: relative_valuation, ml_rank)
  - scores (1 row per stock: the combined overall_score + rating)

Safe to re-run (upserts + a fresh run_date each time you run it).

Run with (after 11_train_model.py has been retrained and the validation
report has been reviewed):
    python 14_score_current_stocks.py
-------------------------------------------------------------------
"""
import json
from datetime import date

import pandas as pd
from xgboost import XGBRegressor

from db_client import get_client

FORMULA_VERSION = "truescore_v2"
ML_SUBMODEL_VERSION = "truescore_ml_v2"
MODEL_FILE = "trueresearch_model.json"
FEATURE_COLUMNS_FILE = "model_feature_columns.json"
FISCAL_LAG_DAYS = 120

# Matches the original StockApp experiment's validated "Case C" feature
# list exactly -- must always match the list 11_train_model.py trained on.
NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]


def fetch_price_history(supabase, asset_id: int) -> pd.DataFrame:
    PAGE_SIZE = 1000
    all_rows = []
    start = 0
    while True:
        res = (
            supabase.table("prices_daily")
            .select("date, close")
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
    return df.set_index("date").sort_index()


def compute_latest_indicators(prices: pd.DataFrame):
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
    if df.empty:
        return None
    return df.iloc[-1]


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
    return df


def latest_usable_fundamentals(fundamentals: pd.DataFrame, as_of_date):
    if fundamentals.empty:
        return None, None
    usable = fundamentals[fundamentals["fiscal_year_end_date"] + pd.Timedelta(days=FISCAL_LAG_DAYS) <= as_of_date]
    if usable.empty:
        return None, None
    latest = usable.iloc[-1]
    prior = usable.iloc[-2] if len(usable) >= 2 else None
    return latest, prior


def capex_intensity_yoy_change(latest, prior):
    if latest is None or prior is None:
        return None
    try:
        latest_pct = abs(latest["capex"]) / latest["total_revenue"] if pd.notna(latest.get("capex")) and latest.get("total_revenue") else None
        prior_pct = abs(prior["capex"]) / prior["total_revenue"] if pd.notna(prior.get("capex")) and prior.get("total_revenue") else None
        if latest_pct is not None and prior_pct is not None and prior_pct:
            return (latest_pct - prior_pct) / prior_pct
    except Exception:
        pass
    return None


def percentile_rank(series: pd.Series) -> pd.Series:
    """0-100 scale, higher = better. NaNs get a neutral 50."""
    ranked = series.rank(pct=True, na_option="keep") * 100
    return ranked.fillna(50)


def rating_band(score: float) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Above Average"
    if score >= 40:
        return "Average"
    if score >= 20:
        return "Below Average"
    return "Weak"


def register_formula_and_weights(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": FORMULA_VERSION,
        "description": (
            "Final corrected TrueScore: default 50% relative valuation (sector-relative "
            "P/E percentile) + 50% ML rank score (from validated model, formula_version "
            f"{ML_SUBMODEL_VERSION}, trained on a 2-year rolling window -- see "
            "Step6_ML_Model_Decision_Log.md for the full story of the 3 bugs fixed and "
            "the rolling-window decision). Weights are stored as data in "
            "score_component_weights, not hardcoded -- can be changed per sector or "
            "per stock without a code change."
        ),
        "changed_by_note": "Final Step 6 correction pass, following full audit and rolling-window experiment. See chat + Step6_ML_Model_Decision_Log.md.",
    }, on_conflict="formula_version").execute()

    supabase.table("score_component_weights").delete().eq("formula_version", FORMULA_VERSION).is_("sector_id", "null").is_("asset_id", "null").execute()
    supabase.table("score_component_weights").insert([
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "relative_valuation", "weight_pct": 50},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "ml_rank", "weight_pct": 50},
    ]).execute()


def main():
    supabase = get_client()
    run_date = date.today().isoformat()

    print("Loading trained model...")
    model = XGBRegressor()
    model.load_model(MODEL_FILE)
    with open(FEATURE_COLUMNS_FILE) as f:
        feature_columns = json.load(f)

    print("Loading Nifty 100 benchmark price history (needed for Relative_Strength_3M)...")
    bench_asset = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", "NIFTY100")
        .eq("asset_type", "index")
        .execute()
    )
    if not bench_asset.data:
        print("ERROR: Nifty 100 benchmark asset not found. Cannot compute Relative_Strength_3M correctly. Aborting.")
        return
    benchmark_asset_id = bench_asset.data[0]["asset_id"]
    benchmark = fetch_price_history(supabase, benchmark_asset_id)
    if benchmark.empty:
        print("ERROR: Benchmark has no price history. Aborting.")
        return
    print(f"  -> {len(benchmark)} days of benchmark history loaded.\n")

    print("Registering formula version + default component weights...")
    register_formula_and_weights(supabase)

    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker, sector_id, sectors(name)")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Scoring {len(assets)} stocks...\n")

    ratios_res = supabase.table("ratios_snapshot").select("asset_id, pe_ratio, as_of_date").execute()
    ratios_df = pd.DataFrame(ratios_res.data)
    if not ratios_df.empty:
        ratios_df = ratios_df.sort_values("as_of_date").drop_duplicates("asset_id", keep="last")
    pe_by_asset = dict(zip(ratios_df.get("asset_id", []), ratios_df.get("pe_ratio", [])))

    today_ts = pd.Timestamp(date.today())
    rows = []

    for i, a in enumerate(assets, 1):
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        sector_name = (a.get("sectors") or {}).get("name") if a.get("sectors") else None
        print(f"[{i}/{len(assets)}] {ticker} ...")

        prices = fetch_price_history(supabase, asset_id)
        if prices.empty or len(prices) < 200:
            print("  -> skipped (not enough price history)")
            continue
        latest_tech = compute_latest_indicators(prices)
        latest_date = latest_tech.name  # the date of the latest usable price row

        fundamentals = fetch_fundamentals(supabase, asset_id)
        latest_fund, prior_fund = latest_usable_fundamentals(fundamentals, today_ts)
        if latest_fund is None:
            print("  -> skipped (no usable point-in-time fundamentals yet)")
            continue

        # Relative_Strength_3M: this stock's 3-month return minus the
        # benchmark's own 3-month return over the same window -- matches
        # exactly how 09_build_training_data.py computes it during training.
        past_date_target = latest_date - pd.Timedelta(days=90)
        bench_now_series = benchmark.loc[benchmark.index <= latest_date, "close"]
        bench_past_series = benchmark.loc[benchmark.index <= past_date_target, "close"]
        if bench_now_series.empty or bench_past_series.empty:
            benchmark_past_return = 0
        else:
            benchmark_past_return = (bench_now_series.iloc[-1] / bench_past_series.iloc[-1]) - 1
        relative_strength_3M = latest_tech["Return_3M"] - benchmark_past_return

        feature_row = {
            "RSI": latest_tech["RSI"],
            "MA50": latest_tech["MA50"],
            "MA200": latest_tech["MA200"],
            "Return_1M": latest_tech["Return_1M"],
            "Return_3M": latest_tech["Return_3M"],
            "Return_6M": latest_tech["Return_6M"],
            "Volatility_30D": latest_tech["Volatility_30D"],
            "Relative_Strength_3M": relative_strength_3M,
            "ROE": latest_fund.get("roe"),
            "Total_Debt": latest_fund.get("total_debt"),
            "Stockholders_Equity": latest_fund.get("stockholders_equity"),
            "Net_Income": latest_fund.get("net_income"),
            "Total_Revenue": latest_fund.get("total_revenue"),
            "Capex_Intensity_YoY_Change": capex_intensity_yoy_change(latest_fund, prior_fund),
            "Sector": sector_name,
        }
        rows.append({"asset_id": asset_id, "ticker": ticker, "sector_id": a.get("sector_id"), **feature_row})

    features_df = pd.DataFrame(rows)
    sector_dummies = pd.get_dummies(features_df["Sector"], prefix="Sector")
    X = pd.concat([features_df[NUMERIC_FEATURES], sector_dummies], axis=1)
    X = X.reindex(columns=feature_columns, fill_value=0)

    print("\nRunning predictions...")
    features_df["predicted_excess_return"] = model.predict(X)
    features_df["ml_rank_score"] = percentile_rank(features_df["predicted_excess_return"])

    features_df["pe_ratio"] = features_df["asset_id"].map(pe_by_asset)
    features_df["inv_pe"] = features_df["pe_ratio"].apply(lambda x: -x if pd.notna(x) and x and x > 0 else None)
    features_df["relative_valuation_score"] = features_df.groupby("sector_id")["inv_pe"].transform(percentile_rank)

    features_df["overall_score"] = (features_df["relative_valuation_score"] * 0.5) + (features_df["ml_rank_score"] * 0.5)
    features_df["truescore_rating"] = features_df["overall_score"].apply(rating_band)

    print("Saving scores to the database...")
    supabase.table("score_components").delete().eq("formula_version", FORMULA_VERSION).eq("run_date", run_date).execute()

    component_rows = []
    for _, row in features_df.iterrows():
        asset_id = int(row["asset_id"])

        supabase.table("scores").upsert({
            "asset_id": asset_id,
            "run_date": run_date,
            "formula_version": FORMULA_VERSION,
            "relative_valuation_score": row["relative_valuation_score"],
            "ml_rank_score": row["ml_rank_score"],
            "overall_score": row["overall_score"],
            "truescore_rating": row["truescore_rating"],
        }, on_conflict="asset_id,run_date,formula_version").execute()

        component_rows.append({
            "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
            "component_name": "relative_valuation", "component_value": row["relative_valuation_score"],
            "component_weight_used": 50,
        })
        component_rows.append({
            "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
            "component_name": "ml_rank", "component_value": row["ml_rank_score"],
            "component_weight_used": 50,
        })

    CHUNK = 500
    for i in range(0, len(component_rows), CHUNK):
        supabase.table("score_components").insert(component_rows[i:i + CHUNK]).execute()

    print(f"\nDone. Scored {len(features_df)} stocks and saved to the database (run_date={run_date}, formula_version={FORMULA_VERSION}).")
    print("\nTop 10 by overall score:")
    top10 = features_df.sort_values("overall_score", ascending=False).head(10)
    for _, r in top10.iterrows():
        print(f"  {r['ticker']}: overall={r['overall_score']:.1f} (valuation={r['relative_valuation_score']:.1f}, ml_rank={r['ml_rank_score']:.1f}) -> {r['truescore_rating']}")


if __name__ == "__main__":
    main()
