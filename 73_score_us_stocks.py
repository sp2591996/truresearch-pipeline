"""
73_score_us_stocks.py
-------------------------------------------------------------------
Phase 3 (US expansion): score the S&P 500 with the validated US
model.

UPDATED (Session 38, Avdhoot's explicit request: "On USA lets do it
the same way we did for India, and everything we did for india") --
this file now mirrors 14_score_current_stocks.py's TrueScore v5
methodology exactly, just scoped to `market = "usa"`, using the US
model (71_train_us_model.py's output) and the S&P 500 as the
benchmark instead of the Nifty 100. Every India improvement this
project has made is now here too:

  1. Relative Valuation Score -- sector-relative P/E percentile.
  2. ML Rank Score -- from the validated US model
     (us_trueresearch_model.json).
  3. Growth Score -- 3-year CAGR of Revenue/EBIT/EBITDA/Net Income
     (falls back to 2-year YoY-average per metric when a real 3-year
     CAGR isn't available or reads as an outlier) -- same
     CAGR_OUTLIER_BOUNDS / growth_rate_from_years() logic as India,
     copied verbatim from 14_score_current_stocks.py.
  4. Volatility Score (NEW for USA) -- 30-day annualized volatility
     (min_periods=20, same as India), inverted, ranked sector-relative.
  5. Legacy Score (NEW for USA) -- listing tenure (`listed_date`),
     ranked market-wide (not sector-relative).
  6. Market Cap Score (NEW for USA) -- market cap, ranked market-wide.

overall_score = ML Rank 25% + Growth 20% + Relative Valuation 20% +
Volatility 10% + Legacy 15% + Market Cap 10% -- IDENTICAL weights to
India's truescore_v5 (V5_WEIGHTS below).

Sector-level scoring also now matches India's corrected methodology
exactly (see compute_and_save_sector_scores()):
  - sector_ml_score: market-cap-weighted average within the sector
    (NOT ranked against other sectors).
  - sector_growth_score / sector_valuation_score: this sector's
    REAL aggregate growth-rate / P/E, ranked 10-100 against every
    OTHER US sector (never an average of already-sector-relative
    per-stock scores).
  - sector_growth_raw / sector_pe: the real underlying numbers are
    saved too (not just the 0-100 rank), so the sector page can show
    an actual growth % / P/E instead of only a score -- same columns
    added for India by migration 123_add_sector_raw_growth_and_pe.sql
    (already exist on `sector_scores`, no new migration needed here).

Distress guardrail: kept as this file's OWN US-specific version
(is_financially_distressed below), NOT a blind copy of India's --
see the existing, still-correct comment on why India's "negative
equity = distress" rule doesn't transfer to the US market (share
buybacks push perfectly healthy US mega-caps like McDonald's/
AutoZone into negative book equity). A company is only ever flagged
here if it is CURRENTLY LOSING MONEY.

Only ONE formula_version is written now -- "truescore_us_v5" -- since
this is a same-session full-parity upgrade, not an incremental
v1->v4->v5 review process like India went through. The old 3-component
"truescore_us_v1" rows already in the database are left alone (old
history, harmless) but this script no longer writes them; the
frontend's formulaVersionForCountry() (components/MarketSelector.tsx)
is updated alongside this file to point USA at "truescore_us_v5" too,
so the switch is instant and automatic on the next successful run --
no other frontend changes needed, since every USA page already reads
through that one shared function.

Writes to:
  - score_formula_versions (registers "truescore_us_v5")
  - score_component_weights (25/20/20/10/15/10, identical to India)
  - score_components (6 rows per stock)
  - scores (1 row per stock, 6 component columns + overall_score)
  - sector_scores (1 row per US sector, including sector_growth_raw/sector_pe)

Safe to re-run (upserts + a fresh run_date each time you run it).
Runs on the exact same schedule as before -- no changes needed to
.github/workflows/us-weekly-truescore-refresh.yml, since that
workflow just calls `python 73_score_us_stocks.py` and doesn't care
which formula_version the script writes internally.

Run with (after 71_train_us_model.py has completed):
    python 73_score_us_stocks.py
-------------------------------------------------------------------
"""
import json
import time
from datetime import date

import pandas as pd
from xgboost import XGBRegressor

from db_client import get_client
from ingestion_log import start_run, finish_run

MARKET = "usa"
FORMULA_VERSION = "truescore_us_v5"
V5_WEIGHTS = {"ml_rank": 25, "growth": 20, "relative_valuation": 20, "volatility": 10, "legacy": 15, "market_cap": 10}
ML_SUBMODEL_VERSION = "truescore_ml_us_v1"
MODEL_FILE = "us_trueresearch_model.json"
FEATURE_COLUMNS_FILE = "us_model_feature_columns.json"
FISCAL_LAG_DAYS = 120


def execute_with_retry(query_builder, max_retries=3, delay_sec=3):
    """Retries a Supabase call on a transient network error before
    giving up -- same helper as 14_score_current_stocks.py's, copied
    here because with 500 stocks x 6 components the save step also
    makes thousands of sequential requests."""
    for attempt in range(1, max_retries + 1):
        try:
            return query_builder.execute()
        except Exception as e:
            if attempt == max_retries:
                raise
            print(f"    ! network hiccup, retrying ({attempt}/{max_retries}): {e}")
            time.sleep(delay_sec)


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
    # Volatility_30D_Scoring (for Volatility Score only -- the ML
    # model's own Volatility_30D input feature above is left
    # untouched): only needs 20 good days out of 30, same relaxed
    # min_periods fix India needed for stocks with an occasional blank
    # close price in their recent history.
    df["Volatility_30D_Scoring"] = daily_returns.rolling(window=30, min_periods=20).std() * (252 ** 0.5)
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


# --- Growth Score: 3-year CAGR with 2-year-YoY fallback -- identical
# methodology and thresholds to 14_score_current_stocks.py, copied
# verbatim so USA gets exactly the same growth math as India, not a
# simplified version. ---------------------------------------------
GROWTH_METRICS = ["total_revenue", "ebit", "ebitda", "net_income"]
MIN_GROWTH_YEARS = 4
CAGR_OUTLIER_BOUNDS = (-0.60, 1.50)  # -60% to +150% annualized


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


def cagr(latest, earliest, years: int):
    if latest is None or earliest is None or pd.isna(latest) or pd.isna(earliest):
        return None
    if earliest <= 0 or latest <= 0:
        return None
    return (latest / earliest) ** (1 / years) - 1


def growth_rate_from_years(years: list):
    if len(years) < 2:
        return None

    has_4_years = len(years) >= 4
    latest_year = years[-1]
    year_3_back = years[-4] if has_4_years else None

    growth_readings = []
    for metric in GROWTH_METRICS:
        reading = None
        if has_4_years:
            g = cagr(latest_year.get(metric), year_3_back.get(metric), 3)
            if g is not None and CAGR_OUTLIER_BOUNDS[0] <= g <= CAGR_OUTLIER_BOUNDS[1]:
                reading = g
        if reading is None:
            yoy_readings = []
            for i in range(max(1, len(years) - 2), len(years)):
                g = yoy_growth(years[i].get(metric), years[i - 1].get(metric))
                if g is not None:
                    yoy_readings.append(g)
            if yoy_readings:
                reading = sum(yoy_readings) / len(yoy_readings)
        if reading is not None:
            growth_readings.append(reading)

    if not growth_readings:
        return None
    return sum(growth_readings) / len(growth_readings)


def compute_growth_rate(fundamentals: pd.DataFrame, as_of_date):
    years = usable_fundamentals_years(fundamentals, as_of_date, MIN_GROWTH_YEARS)
    return growth_rate_from_years(years)


def sector_growth_rate(asset_ids: list, years_by_asset: dict):
    """Sector-level Growth Score input: sums each of the 4 metrics
    ACROSS every stock in the sector first (aligned by how-many-years-
    back), then hands those sector-wide yearly totals to
    growth_rate_from_years() -- identical to India's method."""
    sums = {offset: {m: None for m in GROWTH_METRICS} for offset in (1, 2, 3, 4)}
    for asset_id in asset_ids:
        years = years_by_asset.get(asset_id, [])
        n = len(years)
        for offset in range(1, n + 1):
            row = years[n - offset]
            for metric in GROWTH_METRICS:
                v = row.get(metric)
                if v is not None and pd.notna(v):
                    sums[offset][metric] = (sums[offset][metric] or 0.0) + v

    sector_years = [sums[4], sums[3], sums[2], sums[1]]
    return growth_rate_from_years(sector_years)


def linear_rank_score(series: pd.Series) -> pd.Series:
    """10-100 scale by RANK -- identical to India's version."""
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


# Distress guardrail, US-specific (kept exactly as this file already
# had it -- see the long comment this replaces below for the full
# McDonald's/AutoZone/O'Reilly/buyback reasoning). A company can only
# ever be "distressed" here if it is CURRENTLY LOSING MONEY --
# negative book equity or a very poor ROE only count as CONFIRMING
# signals within that group, never on their own.
DISTRESS_ROE_THRESHOLD = -0.50
DISTRESS_SCORE_CAP = 15


def is_financially_distressed(latest_fund) -> bool:
    net_income = latest_fund.get("net_income")
    equity = latest_fund.get("stockholders_equity")
    roe = latest_fund.get("roe")

    if net_income is None or pd.isna(net_income) or net_income >= 0:
        return False

    if pd.notna(equity) and equity is not None and equity < 0:
        return True

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
            "TrueScore v5 for the US market (S&P 500): SIX components, identical "
            "weighting and methodology to India's truescore_v5 -- ML Rank Score 25% "
            f"(from the validated US model, formula_version {ML_SUBMODEL_VERSION}, "
            "trained on a 1-year rolling window -- chosen from real US walk-forward "
            "evidence, not copied from India's 2-year window), Growth Score 20% "
            "(3-year CAGR of Revenue/EBIT/EBITDA/Net Income with a 2-year YoY-average "
            "fallback, ranked 10-100 within sector), Relative Valuation Score 20% "
            "(sector-relative P/E percentile), Volatility Score 10% (30-day annualized "
            "volatility, inverted, sector-relative), Legacy Score 15% (listing tenure, "
            "ranked market-wide), and Market Cap Score 10% (market cap, ranked "
            "market-wide). Replaces the earlier 3-component truescore_us_v1 as the "
            "live US formula, per the full USA/India parity pass."
        ),
        "changed_by_note": "Full parity upgrade with India's TrueScore v5 (Avdhoot's request): added Volatility, Legacy and Market Cap Score, moved Growth Score to 3-year CAGR with fallback, rebalanced weights to 25/20/20/10/15/10.",
    }, on_conflict="formula_version").execute()

    supabase.table("score_component_weights").delete().eq("formula_version", FORMULA_VERSION).is_("sector_id", "null").is_("asset_id", "null").execute()
    supabase.table("score_component_weights").insert([
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "ml_rank", "weight_pct": V5_WEIGHTS["ml_rank"]},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "growth", "weight_pct": V5_WEIGHTS["growth"]},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "relative_valuation", "weight_pct": V5_WEIGHTS["relative_valuation"]},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "volatility", "weight_pct": V5_WEIGHTS["volatility"]},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "legacy", "weight_pct": V5_WEIGHTS["legacy"]},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "market_cap", "weight_pct": V5_WEIGHTS["market_cap"]},
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

    # Page through in batches of 1000 -- same Supabase/PostgREST cap
    # India's script already had to work around; the S&P 500 list
    # itself is under 1000, but this keeps both scripts identical in
    # shape and safety-proofs it if the US universe ever grows.
    assets = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, sector_id, listed_date, sectors(name)")
            .eq("asset_type", "equity")
            .eq("is_active", True)
            .eq("market", MARKET)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    print(f"Scoring {len(assets)} US stocks...\n")

    ratios_rows = []
    offset = 0
    while True:
        resp = (
            supabase.table("ratios_snapshot")
            .select("asset_id, pe_ratio, market_cap, as_of_date")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        ratios_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    ratios_df = pd.DataFrame(ratios_rows)
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
            "Volatility_30D_Scoring": latest_tech["Volatility_30D_Scoring"],
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
            "is_distressed": distressed, "growth_rate": growth_rate,
            "listed_date": a.get("listed_date"), **feature_row,
        })

    features_df = pd.DataFrame(rows)
    sector_dummies = pd.get_dummies(features_df["Sector"], prefix="Sector")
    X = pd.concat([features_df[NUMERIC_FEATURES], sector_dummies], axis=1)
    X = X.reindex(columns=feature_columns, fill_value=0)

    print("\nRunning predictions...")
    features_df["predicted_excess_return"] = model.predict(X)
    features_df["ml_rank_score"] = percentile_rank(features_df["predicted_excess_return"])

    features_df["pe_ratio"] = pd.to_numeric(features_df["asset_id"].map(pe_by_asset), errors="coerce")
    features_df["inv_pe"] = features_df["pe_ratio"].apply(lambda x: -x if pd.notna(x) and x > 0 else None)
    features_df["relative_valuation_score"] = features_df.groupby("sector_id")["inv_pe"].transform(percentile_rank)

    features_df["growth_score"] = features_df.groupby("sector_id")["growth_rate"].transform(linear_rank_score)

    # Legacy Score: ranked market-wide (this script only ever scores
    # USA, so a plain, non-grouped percentile_rank is already market-wide).
    features_df["listed_date"] = features_df["listed_date"].apply(
        lambda d: pd.to_datetime(d) if d else pd.NaT
    )
    features_df["tenure_days"] = (today_ts - features_df["listed_date"]).dt.days
    features_df["legacy_score"] = percentile_rank(features_df["tenure_days"])

    # Volatility Score: invert + sector-relative percentile, identical
    # pattern to Relative Valuation.
    features_df["inv_volatility"] = features_df["Volatility_30D_Scoring"].apply(
        lambda v: -v if pd.notna(v) else None
    )
    features_df["volatility_score"] = features_df.groupby("sector_id")["inv_volatility"].transform(percentile_rank)
    n_no_volatility = int(features_df["Volatility_30D_Scoring"].isna().sum())
    print(f"Volatility Score: {n_no_volatility} stock(s) had no usable recent price data and got the neutral midpoint (50) instead of a real ranked volatility score.")

    # Market Cap Score: ranked market-wide.
    features_df["market_cap"] = features_df["asset_id"].map(market_cap_by_asset)
    features_df["market_cap_score"] = percentile_rank(features_df["market_cap"])

    features_df["overall_score"] = (
        features_df["ml_rank_score"] * (V5_WEIGHTS["ml_rank"] / 100)
        + features_df["growth_score"] * (V5_WEIGHTS["growth"] / 100)
        + features_df["relative_valuation_score"] * (V5_WEIGHTS["relative_valuation"] / 100)
        + features_df["volatility_score"] * (V5_WEIGHTS["volatility"] / 100)
        + features_df["legacy_score"] * (V5_WEIGHTS["legacy"] / 100)
        + features_df["market_cap_score"] * (V5_WEIGHTS["market_cap"] / 100)
    )

    distressed_mask = features_df["is_distressed"]
    features_df.loc[distressed_mask, "overall_score"] = features_df.loc[distressed_mask, "overall_score"].clip(upper=DISTRESS_SCORE_CAP)
    features_df["truescore_rating"] = features_df["overall_score"].apply(rating_band)

    print("Saving scores to the database...")
    supabase.table("score_components").delete().eq("formula_version", FORMULA_VERSION).eq("run_date", run_date).execute()

    component_rows = []
    for _, row in features_df.iterrows():
        asset_id = int(row["asset_id"])

        execute_with_retry(supabase.table("scores").upsert({
            "asset_id": asset_id,
            "run_date": run_date,
            "formula_version": FORMULA_VERSION,
            "relative_valuation_score": row["relative_valuation_score"],
            "ml_rank_score": row["ml_rank_score"],
            "growth_score": row["growth_score"],
            "volatility_score": row["volatility_score"],
            "legacy_score": row["legacy_score"],
            "market_cap_score": row["market_cap_score"],
            "overall_score": row["overall_score"],
            "truescore_rating": row["truescore_rating"],
        }, on_conflict="asset_id,run_date,formula_version"))

        for comp_name, comp_value in [
            ("relative_valuation", row["relative_valuation_score"]),
            ("ml_rank", row["ml_rank_score"]),
            ("growth", row["growth_score"]),
            ("volatility", row["volatility_score"]),
            ("legacy", row["legacy_score"]),
            ("market_cap", row["market_cap_score"]),
        ]:
            component_rows.append({
                "asset_id": asset_id, "run_date": run_date, "formula_version": FORMULA_VERSION,
                "component_name": comp_name, "component_value": comp_value,
                "component_weight_used": V5_WEIGHTS[comp_name],
            })

    CHUNK = 500
    for i in range(0, len(component_rows), CHUNK):
        execute_with_retry(supabase.table("score_components").insert(component_rows[i:i + CHUNK]))

    finish_run(run_id, ok_count=len(features_df), failed_symbols=skipped)
    print(f"\nDone. Scored {len(features_df)} US stocks and saved to the database (run_date={run_date}, formula_version={FORMULA_VERSION}).")
    n_distressed = int(features_df["is_distressed"].sum())
    print(f"Distress guardrail: {n_distressed} stock(s) flagged (currently loss-making AND negative equity or ROE < {DISTRESS_ROE_THRESHOLD:.0%}), score capped at {DISTRESS_SCORE_CAP}.")
    if n_distressed:
        print("  Flagged tickers: " + ", ".join(features_df.loc[features_df["is_distressed"], "ticker"].tolist()))
    n_no_growth = int(features_df["growth_rate"].isna().sum())
    print(f"Growth Score: {n_no_growth} stock(s) had no usable multi-year fundamentals and got the neutral midpoint (55) instead of a real ranked growth score.")
    print("\nTop 10 by overall score:")
    top10 = features_df.sort_values("overall_score", ascending=False).head(10)
    for _, r in top10.iterrows():
        print(
            f"  {r['ticker']}: overall={r['overall_score']:.1f} "
            f"(ml={r['ml_rank_score']:.1f}, growth={r['growth_score']:.1f}, valuation={r['relative_valuation_score']:.1f}, "
            f"volatility={r['volatility_score']:.1f}, legacy={r['legacy_score']:.1f}, market_cap={r['market_cap_score']:.1f}) "
            f"-> {r['truescore_rating']}"
        )

    # ---- Sectoral Score -- identical methodology to India's corrected
    # compute_and_save_sector_scores(): sector_ml_score is a market-cap-
    # weighted average within the sector; sector_growth_score/
    # sector_valuation_score are this sector's REAL aggregate growth
    # rate/P/E, ranked 10-100 against every OTHER US sector. The real
    # underlying numbers (sector_growth_raw/sector_pe) are saved too.
    print("\nComputing Sectoral Scores (3 sector-level components)...")

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
            "sector_growth_raw": None if pd.isna(srow["sector_growth_raw"]) else float(srow["sector_growth_raw"]),
            "sector_pe": None if pd.isna(srow["sector_pe"]) else float(srow["sector_pe"]),
        }, on_conflict="sector_id,run_date,formula_version").execute()

    print(f"Saved sector_scores for {len(sector_agg)} US sectors under formula_version={FORMULA_VERSION}.")
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
