"""
73_score_us_stocks.py
-------------------------------------------------------------------
Phase 3 (US expansion): score the S&P 500 with the validated US
model, using the EXACT SAME 3-component TrueScore + Sectoral Score
methodology already proven out for India in 14_score_current_stocks.py
-- just scoped to `market = "usa"`, using the US model
(71_train_us_model.py's output) and the S&P 500 as the benchmark
instead of the Nifty 100.

TrueScore is a combination of THREE factors, same as India:
  1. Relative valuation -- sector-relative P/E percentile.
  2. ML rank score -- from the validated US model
     (us_trueresearch_model.json, trained on a 1-YEAR rolling window --
     see 71_train_us_model.py's header for why 1 year, not 2, was the
     right choice for the US market specifically).
  3. Growth score -- avg YoY growth of Revenue/EBIT/EBITDA/Net Income
     over the last 2 fiscal years, ranked 10-100 within sector.

Uses its OWN formula_version ("truescore_us_v1") so US scores are
completely separate rows from India's "truescore_v3" scores in the
same `scores` / `score_components` tables -- no schema change needed,
since `formula_version` is already part of every uniqueness key there.
Sector-level rows in `sector_scores` are automatically kept separate
too, because US sectors already have their OWN sector_id values
(distinct from India's, even where the name matches -- e.g. "Energy"),
from 67_add_sp500_stocks.py's `market`-aware sector creation.

Writes to:
  - score_formula_versions (registers "truescore_us_v1")
  - score_component_weights (33.34/33.33/33.33, same weighting as India)
  - score_components (3 rows per stock)
  - scores (1 row per stock)
  - sector_scores (1 row per US sector)

Safe to re-run (upserts + a fresh run_date each time you run it).

Run with (after 71_train_us_model.py has completed):
    python 73_score_us_stocks.py
-------------------------------------------------------------------
"""
import json
from datetime import date

import pandas as pd
from xgboost import XGBRegressor

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "usa"
FORMULA_VERSION = "truescore_us_v1"
ML_SUBMODEL_VERSION = "truescore_ml_us_v1"
MODEL_FILE = "us_trueresearch_model.json"
FEATURE_COLUMNS_FILE = "us_model_feature_columns.json"
FISCAL_LAG_DAYS = 120

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


GROWTH_METRICS = ["total_revenue", "ebit", "ebitda", "net_income"]
MIN_GROWTH_YEARS = 3


def usable_fundamentals_years(fundamentals: pd.DataFrame, as_of_date, n_years: int = MIN_GROWTH_YEARS):
    if fundamentals.empty:
        return []
    usable = fundamentals[fundamentals["fiscal_year_end_date"] + pd.Timedelta(days=FISCAL_LAG_DAYS) <= as_of_date]
    if usable.empty:
        return []
    return [row for _, row in usable.tail(n_years).iterrows()]


def yoy_growth(curr, prev):
    if curr is None or prev is None or pd.isna(curr) or pd.isna(prev) or prev == 0:
        return None
    return (curr - prev) / abs(prev)


def growth_rate_from_years(years: list):
    if len(years) < 2:
        return None

    growth_readings = []
    for i in range(1, len(years)):
        prev_year, curr_year = years[i - 1], years[i]
        for metric in GROWTH_METRICS:
            g = yoy_growth(curr_year.get(metric), prev_year.get(metric))
            if g is not None:
                growth_readings.append(g)

    if not growth_readings:
        return None
    return sum(growth_readings) / len(growth_readings)


def sector_growth_rate(asset_ids: list, years_by_asset: dict):
    sums = {1: {m: None for m in GROWTH_METRICS}, 2: {m: None for m in GROWTH_METRICS}, 3: {m: None for m in GROWTH_METRICS}}
    for asset_id in asset_ids:
        years = years_by_asset.get(asset_id, [])
        n = len(years)
        for offset in range(1, n + 1):
            row = years[n - offset]
            for metric in GROWTH_METRICS:
                v = row.get(metric)
                if v is not None and pd.notna(v):
                    sums[offset][metric] = (sums[offset][metric] or 0.0) + v

    sector_years = [sums[3], sums[2], sums[1]]
    return growth_rate_from_years(sector_years)


def linear_rank_score(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    result = pd.Series(55.0, index=series.index)
    n = len(valid)
    if n == 0:
        return result
    if n == 1:
        result.loc[valid.index] = 100.0
        return result
    ranks = valid.rank(method="average", ascending=True)
    result.loc[valid.index] = 10 + (ranks - 1) / (n - 1) * 90
    return result


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


# Distress guardrail, adapted for the US market (PRD.md B2's original
# intent: "a company in default or clearly distressed must not score
# in the 80s+"). India's version (14_score_current_stocks.py) flags
# negative shareholders' equity -- correct there, since it reliably
# signals real distress (e.g. IDEA telecom). That signal does NOT
# transfer to the US market: a long list of financially dominant,
# healthy US mega-caps (McDonald's, Starbucks, AutoZone, O'Reilly, Yum
# Brands, Domino's, and others) run NEGATIVE book equity for a
# completely different, benign reason -- years of aggressive share
# buybacks mechanically push accounting equity below zero even though
# the underlying business is thriving and highly profitable.
#
# Round 1 fix (dropping the negative-equity check, keeping only the ROE
# floor) was NOT enough: the same buyback companies still got flagged,
# because dividing a strongly POSITIVE profit by a NEGATIVE equity
# number produces a hugely NEGATIVE "ROE" -- the exact sign-flip
# distortion this file's own India-inherited comment already warned
# about, just triggering through the other ratio instead.
#
# The actual fix: a company can only ever be "distressed" if it is
# currently LOSING money (negative net income). No profitable company
# -- regardless of what buybacks did to its book equity -- should ever
# be capped. Within that group (net_income < 0), negative equity or a
# very poor ROE (computed off equity that's still positive, so the
# sign is trustworthy) are both valid confirming signals of real
# financial distress.
DISTRESS_ROE_THRESHOLD = -0.50
DISTRESS_SCORE_CAP = 15


def is_financially_distressed(latest_fund) -> bool:
    net_income = latest_fund.get("net_income")
    equity = latest_fund.get("stockholders_equity")
    roe = latest_fund.get("roe")

    # A profitable company is never distressed, no matter what buybacks
    # did to its book equity -- this is the check that actually excludes
    # McDonald's/AutoZone/O'Reilly/Lowe's/etc.
    if net_income is None or pd.isna(net_income) or net_income >= 0:
        return False

    # From here on, the company is genuinely losing money. Negative
    # equity on top of that is textbook distress (e.g. IDEA telecom).
    if pd.notna(equity) and equity is not None and equity < 0:
        return True

    # Or: losing money badly relative to a still-POSITIVE equity base
    # (only trust the ROE sign when equity itself is positive -- when
    # equity is negative, ROE's sign is unreliable, which is exactly
    # why the equity check above exists as a separate, direct signal).
    if (
        pd.notna(roe) and roe is not None
        and pd.notna(equity) and equity is not None and equity > 0
        and roe < DISTRESS_ROE_THRESHOLD
    ):
        return True

    return False


def register_formula_and_weights(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": FORMULA_VERSION,
        "description": (
            "TrueScore for the US market (S&P 500): equal-weighted average of THREE "
            "components -- relative valuation (sector-relative P/E percentile), ML rank "
            f"score (from the validated US model, formula_version {ML_SUBMODEL_VERSION}, "
            "trained on a 1-year rolling window -- chosen from real US walk-forward "
            "evidence, not copied from India's 2-year window), and Growth Score (avg YoY "
            "growth of Revenue/EBIT/EBITDA/Net Income over the last 2 fiscal years, ranked "
            "10-100 within sector). Same methodology as India's truescore_v3, kept as a "
            "completely separate formula_version so the two markets' scores never mix."
        ),
        "changed_by_note": "Phase 3 of US market expansion: scoring the S&P 500 with the validated US model.",
    }, on_conflict="formula_version").execute()

    supabase.table("score_component_weights").delete().eq("formula_version", FORMULA_VERSION).is_("sector_id", "null").is_("asset_id", "null").execute()
    supabase.table("score_component_weights").insert([
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "relative_valuation", "weight_pct": 33.34},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "ml_rank", "weight_pct": 33.33},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "growth", "weight_pct": 33.33},
    ]).execute()


def main():
    supabase = get_client()
    run_date = date.today().isoformat()

    print("Loading trained US model...")
    model = XGBRegressor()
    model.load_model(MODEL_FILE)
    with open(FEATURE_COLUMNS_FILE) as f:
        feature_columns = json.load(f)

    print("Loading S&P 500 benchmark price history (needed for Relative_Strength_3M)...")
    bench_asset = (
        supabase.table("assets")
        .select("asset_id")
        .eq("ticker", "SPX500")
        .eq("asset_type", "index")
        .eq("market", MARKET)
        .execute()
    )
    if not bench_asset.data:
        print("ERROR: S&P 500 benchmark asset not found. Cannot compute Relative_Strength_3M correctly. Aborting.")
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
        .eq("market", MARKET)
        .execute()
    )
    assets = assets_res.data
    print(f"Scoring {len(assets)} US stocks...\n")

    ratios_res = supabase.table("ratios_snapshot").select("asset_id, pe_ratio, market_cap, as_of_date").execute()
    ratios_df = pd.DataFrame(ratios_res.data)
    if not ratios_df.empty:
        ratios_df = ratios_df.sort_values("as_of_date").drop_duplicates("asset_id", keep="last")
    pe_by_asset = dict(zip(ratios_df.get("asset_id", []), ratios_df.get("pe_ratio", [])))
    market_cap_by_asset = dict(zip(ratios_df.get("asset_id", []), ratios_df.get("market_cap", [])))

    today_ts = pd.Timestamp(date.today())
    rows = []
    years_by_asset = {}
    run_id = start_run("us_scoring")
    skipped = []

    for i, a in enumerate(assets, 1):
        asset_id = a["asset_id"]
        ticker = a["ticker"]
        sector_name = (a.get("sectors") or {}).get("name") if a.get("sectors") else None
        print(f"[{i}/{len(assets)}] {ticker} ...")

        prices = fetch_price_history(supabase, asset_id)
        if prices.empty or len(prices) < 200:
            print("  -> skipped (not enough price history)")
            skipped.append(f"{ticker} (not enough price history)")
            continue
        latest_tech = compute_latest_indicators(prices)
        latest_date = latest_tech.name

        fundamentals = fetch_fundamentals(supabase, asset_id)
        latest_fund, prior_fund = latest_usable_fundamentals(fundamentals, today_ts)
        if latest_fund is None:
            print("  -> skipped (no usable point-in-time fundamentals yet)")
            skipped.append(f"{ticker} (no usable point-in-time fundamentals yet)")
            continue

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
        distressed = is_financially_distressed(latest_fund)
        years_by_asset[asset_id] = usable_fundamentals_years(fundamentals, today_ts, MIN_GROWTH_YEARS)
        growth_rate = growth_rate_from_years(years_by_asset[asset_id])
        rows.append({
            "asset_id": asset_id, "ticker": ticker, "sector_id": a.get("sector_id"),
            "is_distressed": distressed, "growth_rate": growth_rate, **feature_row,
        })

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

    features_df["growth_score"] = features_df.groupby("sector_id")["growth_rate"].transform(linear_rank_score)

    features_df["overall_score"] = (
        features_df["relative_valuation_score"] + features_df["ml_rank_score"] + features_df["growth_score"]
    ) / 3

    distressed_mask = features_df["is_distressed"]
    features_df.loc[distressed_mask, "overall_score"] = features_df.loc[distressed_mask, "overall_score"].clip(upper=DISTRESS_SCORE_CAP)
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
            "growth_score": row["growth_score"],
            "overall_score": row["overall_score"],
            "truescore_rating": row["truescore_rating"],
        }, on_conflict="asset_id,run_date,formula_version").execute()

        component_rows.append({
            "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
            "component_name": "relative_valuation", "component_value": row["relative_valuation_score"],
            "component_weight_used": 33.34,
        })
        component_rows.append({
            "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
            "component_name": "ml_rank", "component_value": row["ml_rank_score"],
            "component_weight_used": 33.33,
        })
        component_rows.append({
            "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
            "component_name": "growth", "component_value": row["growth_score"],
            "component_weight_used": 33.33,
        })

    CHUNK = 500
    for i in range(0, len(component_rows), CHUNK):
        supabase.table("score_components").insert(component_rows[i:i + CHUNK]).execute()

    finish_run(run_id, ok_count=len(features_df), failed_symbols=skipped)
    print(f"\nDone. Scored {len(features_df)} US stocks and saved to the database (run_date={run_date}, formula_version={FORMULA_VERSION}).")
    n_distressed = int(features_df["is_distressed"].sum())
    print(f"Distress guardrail: {n_distressed} stock(s) flagged (negative equity or ROE < {DISTRESS_ROE_THRESHOLD:.0%}), score capped at {DISTRESS_SCORE_CAP}.")
    if n_distressed:
        print("  Flagged tickers: " + ", ".join(features_df.loc[features_df["is_distressed"], "ticker"].tolist()))
    n_no_growth = int(features_df["growth_rate"].isna().sum())
    print(f"Growth Score: {n_no_growth} stock(s) had no usable multi-year fundamentals and got the neutral midpoint (55) instead of a real ranked growth score.")
    print("\nTop 10 by overall score:")
    top10 = features_df.sort_values("overall_score", ascending=False).head(10)
    for _, r in top10.iterrows():
        print(
            f"  {r['ticker']}: overall={r['overall_score']:.1f} "
            f"(valuation={r['relative_valuation_score']:.1f}, ml_rank={r['ml_rank_score']:.1f}, growth={r['growth_score']:.1f}) "
            f"-> {r['truescore_rating']}"
        )

    print("\nComputing Sectoral Scores (3 sector-level components)...")
    features_df["market_cap"] = features_df["asset_id"].map(market_cap_by_asset)

    def weighted_avg(group: pd.DataFrame, value_col: str, weight_col: str = "market_cap"):
        weighted = group.dropna(subset=[value_col, weight_col])
        weighted = weighted[weighted[weight_col] > 0]
        if weighted.empty:
            return group[value_col].mean()
        return (weighted[value_col] * weighted[weight_col]).sum() / weighted[weight_col].sum()

    sector_ids = sorted(features_df["sector_id"].dropna().unique().tolist())
    sector_rows = []
    for sector_id in sector_ids:
        group = features_df[features_df["sector_id"] == sector_id]
        asset_ids_in_sector = group["asset_id"].tolist()

        sector_ml_score = weighted_avg(group, "ml_rank_score")
        sector_growth_raw = sector_growth_rate(asset_ids_in_sector, years_by_asset)

        valid = group.dropna(subset=["market_cap", "Net_Income"])
        valid = valid[(valid["market_cap"] > 0)]
        total_cap = valid["market_cap"].sum()
        total_net_income = valid["Net_Income"].sum()
        sector_pe = (total_cap / total_net_income) if (len(valid) > 0 and total_net_income and total_net_income > 0) else None

        sector_rows.append({
            "sector_id": int(sector_id),
            "avg_truescore": weighted_avg(group, "overall_score"),
            "stock_count": int(group["overall_score"].count()),
            "sector_ml_score": sector_ml_score,
            "sector_growth_raw": sector_growth_raw,
            "sector_pe": sector_pe,
        })

    sector_agg = pd.DataFrame(sector_rows)
    sector_agg["sector_growth_score"] = linear_rank_score(sector_agg["sector_growth_raw"])
    sector_agg["inv_sector_pe"] = sector_agg["sector_pe"].apply(lambda x: -x if pd.notna(x) and x else None)
    sector_agg["sector_valuation_score"] = linear_rank_score(sector_agg["inv_sector_pe"])
    sector_agg["sector_rank_score"] = (
        sector_agg["sector_ml_score"] + sector_agg["sector_growth_score"] + sector_agg["sector_valuation_score"]
    ) / 3

    for _, srow in sector_agg.iterrows():
        supabase.table("sector_scores").upsert({
            "sector_id": int(srow["sector_id"]),
            "run_date": run_date,
            "formula_version": FORMULA_VERSION,
            "avg_truescore": srow["avg_truescore"],
            "stock_count": int(srow["stock_count"]),
            "sector_ml_score": srow["sector_ml_score"],
            "sector_growth_score": srow["sector_growth_score"],
            "sector_valuation_score": srow["sector_valuation_score"],
            "sector_rank_score": srow["sector_rank_score"],
        }, on_conflict="sector_id,run_date,formula_version").execute()

    print(f"Saved sector_scores for {len(sector_agg)} US sectors.")
    print("\nSectors ranked highest to lowest (Sectoral Score):")
    for _, srow in sector_agg.sort_values("sector_rank_score", ascending=False).iterrows():
        pe_str = f"{srow['sector_pe']:.1f}" if pd.notna(srow["sector_pe"]) else "—"
        growth_str = f"{srow['sector_growth_raw']:.1%}" if pd.notna(srow["sector_growth_raw"]) else "—"
        print(
            f"  sector_id={int(srow['sector_id'])}: overall={srow['sector_rank_score']:.1f} "
            f"(ml={srow['sector_ml_score']:.1f}, growth_score={srow['sector_growth_score']:.1f} [raw growth {growth_str}], "
            f"valuation_score={srow['sector_valuation_score']:.1f} [sector P/E {pe_str}]) ({int(srow['stock_count'])} stocks)"
        )


if __name__ == "__main__":
    main()
