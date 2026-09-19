"""
14_score_current_stocks.py
-------------------------------------------------------------------
Phase B, Step 6f (final step of Step 6): score today's stocks with
the validated model, and save real TrueScore rows into the database.

TrueScore is a combination of THREE factors as of formula_version
truescore_v3 (previously 2 -- see the truescore_v2 history below):
  1. Relative valuation  -- how cheap/expensive a stock is vs. its own
     sector peers, using P/E ratio (lower P/E among sector peers = higher
     score). Simple, transparent, sector-relative -- not the ML model.
  2. ML rank score -- this is where 11_train_model.py's trained model
     comes in: it predicts each stock's likely 3-month excess return,
     and stocks are ranked against each other on that prediction.
  3. Growth score (NEW, truescore_v3) -- average YoY growth of Revenue,
     EBIT, EBITDA and PAT over the last 2 fiscal years, then ranked
     against every OTHER stock in the SAME sector on a 10-100 scale
     (highest grower in the sector = 100, lowest = 10, evenly spaced --
     a rank-based scale, deliberately different from the percentile
     scale the other two components use, per Avdhoot's own spec). See
     `compute_growth_rate()` and `linear_rank_score()` below.

`overall_score` is the plain (equal-weighted) average of all three --
each is worth roughly a third. Weights are stored as DATA in
`score_component_weights` (not hardcoded), so they can be changed per
sector or per stock later without touching any code, exactly per the
flexible design in Database_Schema.md.

NEW in truescore_v3: sector-level scoring. Once every stock has an
overall_score, sectors are aggregated (plain average of member stocks'
overall_score) and then ranked against EACH OTHER on the same 10-100
scale Growth Score uses within a sector -- "sectors fighting sectors"
the same way stocks fight within their sector. Written to the new
`sector_scores` table (see 64_add_growth_and_sector_scores.sql). This
is a distinct, new figure from the pre-existing frontend "Sector Score"
(a market-cap-weighted average shown on sector pages) -- both are kept.

truescore_v2 history (Step 6 correction pass) -- unchanged, still the
foundation truescore_v3 builds on. Three real bugs were found and
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
  - score_formula_versions (registers "truescore_v3", the COMBINED
    formula for this run)
  - score_component_weights (the default ~33/33/33 weighting, as data)
  - score_components (3 rows per stock: relative_valuation, ml_rank, growth)
  - scores (1 row per stock: the combined overall_score + rating + growth_score)
  - sector_scores (1 row per sector: avg_truescore + sector_rank_score)
  - (also writes a parallel truescore_v4 row + component-set per stock,
    under its own formula_version -- see V4_FORMULA_VERSION note above)

Safe to re-run (upserts + a fresh run_date each time you run it). Run
this yourself in your own terminal -- see PROJECT_STATE.md for why
Claude can't run it for you directly right now (`device_bash` outage).

NEW (in progress, not live anywhere on the frontend yet): a parallel
formula_version, truescore_v4, is also computed and saved every run
-- see V4_FORMULA_VERSION below. It adds two new components
(Volatility Score, Legacy Score) to the existing three, with weights
ML Rank 30% / Growth 20% / Relative Valuation 20% / Volatility 15% /
Legacy 15%. truescore_v3 stays exactly as before, completely
untouched -- v4 rows are written alongside it under their own
formula_version so Avdhoot can review/back-test before promoting it
to live anywhere on the frontend.

Run with (after 11_train_model.py has been retrained and the validation
report has been reviewed):
    python 14_score_current_stocks.py
-------------------------------------------------------------------
"""
import json
import time
from datetime import date

import pandas as pd
from xgboost import XGBRegressor

from db_client import get_client
from ingestion_log import start_run, finish_run

FORMULA_VERSION = "truescore_v3"
V4_FORMULA_VERSION = "truescore_v4"
V4_WEIGHTS = {"ml_rank": 30, "growth": 20, "relative_valuation": 20, "volatility": 15, "legacy": 15}
ML_SUBMODEL_VERSION = "truescore_ml_v2"
MODEL_FILE = "trueresearch_model.json"
FEATURE_COLUMNS_FILE = "model_feature_columns.json"
FISCAL_LAG_DAYS = 120


def execute_with_retry(query_builder, max_retries=3, delay_sec=3):
    """Retries a Supabase call on a transient network error (e.g. the
    connection getting dropped mid-request) before giving up. With
    2,500+ stocks now, the scoring save step makes thousands of
    sequential requests -- a one-off network blip somewhere in that
    run shouldn't kill the whole thing after 30-60 minutes of work."""
    for attempt in range(1, max_retries + 1):
        try:
            return query_builder.execute()
        except Exception as e:
            if attempt == max_retries:
                raise
            print(f"    ! network hiccup, retrying ({attempt}/{max_retries}): {e}")
            time.sleep(delay_sec)

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
    # Volatility_30D_Scoring (NEW, truescore_v4 only): same 30-day
    # window, but only needs 20 good days out of the 30 (min_periods),
    # not all 30. A small number of stocks (mostly newer, recently
    # added small-caps) have the occasional blank close price in their
    # history -- with the strict all-30-required version, ONE blank
    # day anywhere in the trailing window wipes out the whole number,
    # which is why ~90% of stocks were getting no Volatility Score at
    # all when this was first tried. Volatility_30D itself (used as
    # the ML model's input feature) is left completely untouched --
    # this new column is only for the new Volatility Score component.
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


# --- Growth Score (NEW, truescore_v3) ---------------------------------
# GROWTH_METRICS: the 4 fundamentals Avdhoot specified -- Revenue, EBIT,
# EBITDA, PAT (= net_income in this schema).
GROWTH_METRICS = ["total_revenue", "ebit", "ebitda", "net_income"]
MIN_GROWTH_YEARS = 3  # need 3 fiscal years on record to get 2 YoY growth rates


def usable_fundamentals_years(fundamentals: pd.DataFrame, as_of_date, n_years: int = MIN_GROWTH_YEARS):
    """Returns up to n_years most recent point-in-time-usable fiscal
    years, OLDEST FIRST (so [-1] is the latest, [-2] the year before,
    etc.) -- same FISCAL_LAG_DAYS point-in-time rule as
    latest_usable_fundamentals() above, just keeping more history."""
    if fundamentals.empty:
        return []
    usable = fundamentals[fundamentals["fiscal_year_end_date"] + pd.Timedelta(days=FISCAL_LAG_DAYS) <= as_of_date]
    if usable.empty:
        return []
    return [row for _, row in usable.tail(n_years).iterrows()]


def yoy_growth(curr, prev):
    """(curr - prev) / abs(prev). None if either value is missing, or
    prev is 0 (growth off a zero base is meaningless, not infinite)."""
    if curr is None or prev is None or pd.isna(curr) or pd.isna(prev) or prev == 0:
        return None
    return (curr - prev) / abs(prev)


def growth_rate_from_years(years: list):
    """Shared by stock-level and sector-level Growth Score: given a list
    of up to 3 fiscal-year rows (oldest first, each a dict-like with the
    4 GROWTH_METRICS), compute the YoY growth rate for the most recent
    fiscal year AND the year before that, then average ALL the YoY
    growth rates available (up to 2 years x 4 metrics = 8 numbers) into
    one growth_rate. Skips whichever individual (metric, year) pairs
    are missing rather than failing entirely -- e.g. only 2 usable
    fiscal years (1 YoY pair per metric, not 2) still gets a growth_rate
    from whatever it has. Returns None only if NOTHING is computable."""
    if len(years) < 2:
        return None  # need at least 2 fiscal years for even 1 YoY reading

    growth_readings = []
    # years is oldest-first; walk consecutive pairs (year[i-1] -> year[i])
    # so with 3 years we get 2 YoY pairs, with 2 years we get 1.
    for i in range(1, len(years)):
        prev_year, curr_year = years[i - 1], years[i]
        for metric in GROWTH_METRICS:
            # .get() works the same way on a pandas Series (stock-level
            # fiscal-year row) and a plain dict (sector-level summed
            # totals) -- both callers pass one of these two shapes.
            g = yoy_growth(curr_year.get(metric), prev_year.get(metric))
            if g is not None:
                growth_readings.append(g)

    if not growth_readings:
        return None
    return sum(growth_readings) / len(growth_readings)


def compute_growth_rate(fundamentals: pd.DataFrame, as_of_date):
    """Stock-level Growth Score input: fetch this one stock's usable
    fiscal years and hand them to growth_rate_from_years(). See that
    function's docstring for the actual calculation."""
    years = usable_fundamentals_years(fundamentals, as_of_date, MIN_GROWTH_YEARS)
    return growth_rate_from_years(years)


def sector_growth_rate(asset_ids: list, years_by_asset: dict):
    """Sector-level Growth Score input (Avdhoot's spec: 'sectoral values
    will be sum of the stock values'). Instead of averaging each stock's
    OWN growth rate, this sums each of the 4 metrics ACROSS every stock
    in the sector first (aligned by how-many-years-back, e.g. every
    stock's latest usable year is summed together, every stock's year-
    before-that is summed together), THEN computes YoY growth on those
    sector-wide totals -- exactly the same 2-year YoY-averaged-across-4-
    metrics method as growth_rate_from_years(), just fed sector totals
    instead of one stock's own numbers. A stock missing a given metric/
    year is simply left out of that one sum rather than zeroing it."""
    # sums[offset][metric]: offset 1 = every stock's latest usable
    # fiscal year, 2 = the year before that, 3 = the year before that.
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

    sector_years = [sums[3], sums[2], sums[1]]  # oldest-first, matches growth_rate_from_years' expectation
    return growth_rate_from_years(sector_years)


def linear_rank_score(series: pd.Series) -> pd.Series:
    """10-100 scale by RANK, not percentile -- e.g. within a 10-stock
    sector, the highest grower gets 100 and the lowest gets 10, evenly
    spaced in between (Avdhoot's explicit spec for Growth Score and,
    reused, for the cross-sector Sector Rank Score). Ties share the
    average score of the positions they span. A group of 1 gets 100
    (nothing to rank against). Missing values get the neutral midpoint,
    55, rather than being excluded or guessed at."""
    valid = series.dropna()
    result = pd.Series(55.0, index=series.index)
    n = len(valid)
    if n == 0:
        return result
    if n == 1:
        result.loc[valid.index] = 100.0
        return result
    ranks = valid.rank(method="average", ascending=True)  # 1 (lowest) .. n (highest)
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


# --- Distress guardrail (PRD.md B2: "a company in default or clearly
# distressed must not score in the 80s+" -- this was a written product
# rule that was never actually enforced in code until now. Session 10
# part 9 caught IDEA scoring 98/"Strong" with -96.6% ROE and negative
# book value; this is the fix. ---
#
# Why this is needed: neither scoring component (relative valuation via
# P/E, or the ML return-prediction rank) directly checks solvency. Worse,
# when a company has negative shareholders' equity, ratios like ROE and
# P/E are dividing by a negative number, which can distort or even flip
# their apparent meaning -- a deeply distressed company can look
# deceptively OK on these ratios alone.
#
# Rule (deliberately simple and conservative, not a new ML model):
# flag a stock as financially distressed if its shareholders' equity is
# negative (liabilities exceed assets -- the clearest, least ambiguous
# distress signal available in the current data), OR its ROE is worse
# than -50%. Flagged stocks have their combined score capped low enough
# to always land in the existing "Weak" band (no new rating label
# introduced, so the frontend's existing 5-band rendering needs no
# changes) -- regardless of how well the two components scored it.
DISTRESS_ROE_THRESHOLD = -0.50
DISTRESS_SCORE_CAP = 15


def is_financially_distressed(latest_fund) -> bool:
    equity = latest_fund.get("stockholders_equity")
    roe = latest_fund.get("roe")
    if pd.notna(equity) and equity is not None and equity < 0:
        return True
    if pd.notna(roe) and roe is not None and roe < DISTRESS_ROE_THRESHOLD:
        return True
    return False


def register_formula_and_weights(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": FORMULA_VERSION,
        "description": (
            "TrueScore v3: equal-weighted average of THREE components -- relative "
            "valuation (sector-relative P/E percentile), ML rank score (from validated "
            f"model, formula_version {ML_SUBMODEL_VERSION}, trained on a 2-year rolling "
            "window), and Growth Score (avg YoY growth of Revenue/EBIT/EBITDA/PAT over "
            "the last 2 fiscal years, ranked 10-100 within sector). Previously (v2) was "
            "50/50 valuation+ML only. See Step6_ML_Model_Decision_Log.md for the v2 "
            "history and this file's own header comment for the v3 change. Weights are "
            "stored as data in score_component_weights, not hardcoded -- can be changed "
            "per sector or per stock without a code change."
        ),
        "changed_by_note": "Added Growth Score as a 3rd component (Avdhoot's request) and sector-vs-sector Sector Rank Score. See chat + this file's header comment.",
    }, on_conflict="formula_version").execute()

    supabase.table("score_component_weights").delete().eq("formula_version", FORMULA_VERSION).is_("sector_id", "null").is_("asset_id", "null").execute()
    supabase.table("score_component_weights").insert([
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "relative_valuation", "weight_pct": 33.34},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "ml_rank", "weight_pct": 33.33},
        {"formula_version": FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "growth", "weight_pct": 33.33},
    ]).execute()


def register_formula_and_weights_v4(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": V4_FORMULA_VERSION,
        "description": (
            "TrueScore v4 (in review, not yet live on any frontend surface): "
            "FIVE components instead of three -- ML Rank Score 30%, Growth Score "
            "20%, Relative Valuation (Undervalued/P-E) Score 20%, Volatility "
            "Score 15% (30-day annualized volatility, inverted, sector-relative "
            "percentile -- lower volatility scores higher), and Legacy Score 15% "
            "(listing tenure in days, ranked market-wide, not sector-relative -- "
            "longer-listed scores higher). Computed and saved alongside the live "
            "truescore_v3 every run so Avdhoot can back-test and review before "
            "this replaces v3 anywhere. See this file's header comment."
        ),
        "changed_by_note": "TrueScore v2 redesign (Avdhoot's request): added Volatility Score and Legacy Score, rebalanced weights to 30/20/20/15/15.",
    }, on_conflict="formula_version").execute()

    supabase.table("score_component_weights").delete().eq("formula_version", V4_FORMULA_VERSION).is_("sector_id", "null").is_("asset_id", "null").execute()
    supabase.table("score_component_weights").insert([
        {"formula_version": V4_FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "ml_rank", "weight_pct": V4_WEIGHTS["ml_rank"]},
        {"formula_version": V4_FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "growth", "weight_pct": V4_WEIGHTS["growth"]},
        {"formula_version": V4_FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "relative_valuation", "weight_pct": V4_WEIGHTS["relative_valuation"]},
        {"formula_version": V4_FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "volatility", "weight_pct": V4_WEIGHTS["volatility"]},
        {"formula_version": V4_FORMULA_VERSION, "sector_id": None, "asset_id": None, "component_name": "legacy", "weight_pct": V4_WEIGHTS["legacy"]},
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
    register_formula_and_weights_v4(supabase)

    # Supabase/PostgREST silently caps any .select() at 1000 rows unless
    # you page through it with .range() -- the same gotcha this project
    # already hit and fixed elsewhere (Gold chart, sector assignment,
    # price/fundamentals refresh). With 2,000+ India equities now, a
    # single un-paginated query here would only ever score the first
    # 1,000.
    assets = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("assets")
            .select("asset_id, ticker, sector_id, listed_date, sectors(name)")
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
    print(f"Scoring {len(assets)} stocks...\n")

    # Same 1000-row cap applies here -- ratios_snapshot accumulates one
    # row per stock per week, so this table has many more than 1,000
    # rows total. Page through all of them so no stock's latest ratio
    # snapshot is silently missed.
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
    # market_cap, added for the sector-level weighting below (Sector Rank
    # Score is a market-cap-weighted average of member overall_scores,
    # matching the exact same weighting the frontend's pre-existing
    # "Sector Score" already uses on the sector pages -- Avdhoot's
    # explicit call, so one large company matters more than a tiny one).
    market_cap_by_asset = dict(zip(ratios_df.get("asset_id", []), ratios_df.get("market_cap", [])))

    today_ts = pd.Timestamp(date.today())
    rows = []
    years_by_asset = {}  # asset_id -> up to 3 fiscal-year rows (oldest first), reused for sector-level Growth Score
    run_id = start_run("scoring")
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
        latest_date = latest_tech.name  # the date of the latest usable price row

        fundamentals = fetch_fundamentals(supabase, asset_id)
        latest_fund, prior_fund = latest_usable_fundamentals(fundamentals, today_ts)
        if latest_fund is None:
            print("  -> skipped (no usable point-in-time fundamentals yet)")
            skipped.append(f"{ticker} (no usable point-in-time fundamentals yet)")
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

    features_df["pe_ratio"] = features_df["asset_id"].map(pe_by_asset)
    # Coerce to numeric first -- with 2,000+ new stocks now flowing
    # through here, an occasional odd/non-numeric pe_ratio value (e.g.
    # a stray string) would otherwise crash the whole run on the ">"
    # comparison below. Anything that isn't a real number becomes NaN,
    # same as if it were missing.
    features_df["pe_ratio"] = pd.to_numeric(features_df["pe_ratio"], errors="coerce")
    features_df["inv_pe"] = features_df["pe_ratio"].apply(lambda x: -x if pd.notna(x) and x > 0 else None)
    features_df["relative_valuation_score"] = features_df.groupby("sector_id")["inv_pe"].transform(percentile_rank)

    # Growth Score (NEW, truescore_v3): each stock's raw growth_rate,
    # ranked 10-100 against every OTHER stock in the SAME sector (rank-
    # based, not percentile -- see linear_rank_score()'s own docstring
    # for why, and Avdhoot's original spec: "highest gets 100, lowest
    # gets 10, in the same ratio").
    features_df["growth_score"] = features_df.groupby("sector_id")["growth_rate"].transform(linear_rank_score)

    # overall_score is now the equal-weighted average of all THREE
    # components (previously 50/50 valuation+ML only).
    features_df["overall_score"] = (
        features_df["relative_valuation_score"] + features_df["ml_rank_score"] + features_df["growth_score"]
    ) / 3

    # Apply the distress guardrail (see is_financially_distressed above)
    # before assigning the rating band -- this is what actually enforces
    # PRD.md B2's "must not score 80+" rule, rather than just flagging it
    # on the frontend after the fact.
    distressed_mask = features_df["is_distressed"]
    features_df.loc[distressed_mask, "overall_score"] = features_df.loc[distressed_mask, "overall_score"].clip(upper=DISTRESS_SCORE_CAP)
    features_df["truescore_rating"] = features_df["overall_score"].apply(rating_band)

    # ---- TrueScore v4 (NEW, in review): two new components on top of
    # the three above -- Volatility Score and Legacy Score. Reuses
    # relative_valuation_score, ml_rank_score and growth_score exactly
    # as already computed for v3; only these two are new.
    features_df["listed_date"] = features_df["listed_date"].apply(
        lambda d: pd.to_datetime(d) if d else pd.NaT
    )
    features_df["tenure_days"] = (today_ts - features_df["listed_date"]).dt.days
    # Legacy Score: ranked MARKET-WIDE (not sector-relative), per spec --
    # longer-listed = higher score. This script only ever scores India,
    # so a plain (non-grouped) percentile_rank is market-wide already.
    features_df["legacy_score"] = percentile_rank(features_df["tenure_days"])

    # Volatility Score: invert Volatility_30D (lower volatility = higher
    # score), then rank sector-relative -- same pattern as
    # relative_valuation_score above (invert + groupby(sector_id) +
    # percentile_rank).
    features_df["inv_volatility"] = features_df["Volatility_30D_Scoring"].apply(
        lambda v: -v if pd.notna(v) else None
    )
    features_df["volatility_score"] = features_df.groupby("sector_id")["inv_volatility"].transform(percentile_rank)
    n_no_volatility = int(features_df["Volatility_30D_Scoring"].isna().sum())
    print(f"Volatility Score: {n_no_volatility} stock(s) had no usable recent price data and got the neutral midpoint (50) instead of a real ranked volatility score.")

    features_df["overall_score_v4"] = (
        features_df["ml_rank_score"] * (V4_WEIGHTS["ml_rank"] / 100)
        + features_df["growth_score"] * (V4_WEIGHTS["growth"] / 100)
        + features_df["relative_valuation_score"] * (V4_WEIGHTS["relative_valuation"] / 100)
        + features_df["volatility_score"] * (V4_WEIGHTS["volatility"] / 100)
        + features_df["legacy_score"] * (V4_WEIGHTS["legacy"] / 100)
    )
    features_df.loc[distressed_mask, "overall_score_v4"] = features_df.loc[distressed_mask, "overall_score_v4"].clip(upper=DISTRESS_SCORE_CAP)
    features_df["truescore_rating_v4"] = features_df["overall_score_v4"].apply(rating_band)

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
            "overall_score": row["overall_score"],
            "truescore_rating": row["truescore_rating"],
        }, on_conflict="asset_id,run_date,formula_version"))

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
        execute_with_retry(supabase.table("score_components").insert(component_rows[i:i + CHUNK]))

    print("Saving truescore_v4 (in review) scores to the database...")
    supabase.table("score_components").delete().eq("formula_version", V4_FORMULA_VERSION).eq("run_date", run_date).execute()

    v4_component_rows = []
    for _, row in features_df.iterrows():
        asset_id = int(row["asset_id"])

        execute_with_retry(supabase.table("scores").upsert({
            "asset_id": asset_id,
            "run_date": run_date,
            "formula_version": V4_FORMULA_VERSION,
            "relative_valuation_score": row["relative_valuation_score"],
            "ml_rank_score": row["ml_rank_score"],
            "growth_score": row["growth_score"],
            "volatility_score": row["volatility_score"],
            "legacy_score": row["legacy_score"],
            "overall_score": row["overall_score_v4"],
            "truescore_rating": row["truescore_rating_v4"],
        }, on_conflict="asset_id,run_date,formula_version"))

        for comp_name, comp_value in [
            ("relative_valuation", row["relative_valuation_score"]),
            ("ml_rank", row["ml_rank_score"]),
            ("growth", row["growth_score"]),
            ("volatility", row["volatility_score"]),
            ("legacy", row["legacy_score"]),
        ]:
            v4_component_rows.append({
                "asset_id": asset_id, "run_date": run_date, "formula_version": V4_FORMULA_VERSION,
                "component_name": comp_name, "component_value": comp_value,
                "component_weight_used": V4_WEIGHTS[comp_name],
            })

    for i in range(0, len(v4_component_rows), CHUNK):
        execute_with_retry(supabase.table("score_components").insert(v4_component_rows[i:i + CHUNK]))

    print(f"Saved truescore_v4 for {len(features_df)} stocks (run_date={run_date}) -- NOT live on the frontend, for review/back-test only.")

    finish_run(run_id, ok_count=len(features_df), failed_symbols=skipped)
    print(f"\nDone. Scored {len(features_df)} stocks and saved to the database (run_date={run_date}, formula_version={FORMULA_VERSION}).")
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

    print("\nTop 10 by truescore_v4 overall score (in review, not live):")
    top10_v4 = features_df.sort_values("overall_score_v4", ascending=False).head(10)
    for _, r in top10_v4.iterrows():
        print(
            f"  {r['ticker']}: v4_overall={r['overall_score_v4']:.1f} "
            f"(ml={r['ml_rank_score']:.1f}, growth={r['growth_score']:.1f}, valuation={r['relative_valuation_score']:.1f}, "
            f"volatility={r['volatility_score']:.1f}, legacy={r['legacy_score']:.1f}) -> {r['truescore_rating_v4']}"
        )

    # ---- Sectoral Score (NEW, truescore_v3, redefined per Avdhoot's
    # correction): NOT just an aggregate of stocks' already-combined
    # overall_score. Instead, 3 components computed the SECTOR way,
    # mirroring exactly how stock-level TrueScore has 3 components:
    #   1. sector_ml_score -- market-cap-weighted average of the
    #      sector's stocks' ml_rank_score. Not ranked against other
    #      sectors -- a plain weighted average, per spec.
    #   2. sector_growth_score -- this sector's growth rate (computed
    #      from SUMMED Revenue/EBIT/EBITDA/PAT across its stocks, same
    #      method as stock Growth Score) ranked 10-100 against every
    #      OTHER sector.
    #   3. sector_valuation_score -- this sector's aggregate P/E
    #      (sum of member market caps / sum of member net income)
    #      ranked 10-100 against every OTHER sector -- cheaper scores
    #      higher.
    # sector_rank_score = equal-weighted average of these 3. avg_truescore
    # (market-cap-weighted average of member overall_score) is kept as
    # a separate, purely informational figure -- unchanged, not part of
    # this calculation, matching the frontend's pre-existing "Sector
    # Score" exactly.
    print("\nComputing Sectoral Scores (3 sector-level components)...")
    features_df["market_cap"] = features_df["asset_id"].map(market_cap_by_asset)

    def weighted_avg(group: pd.DataFrame, value_col: str, weight_col: str = "market_cap"):
        weighted = group.dropna(subset=[value_col, weight_col])
        weighted = weighted[weighted[weight_col] > 0]
        if weighted.empty:
            return group[value_col].mean()  # fall back to plain average rather than dropping the sector
        return (weighted[value_col] * weighted[weight_col]).sum() / weighted[weight_col].sum()

    sector_ids = sorted(features_df["sector_id"].dropna().unique().tolist())
    sector_rows = []
    for sector_id in sector_ids:
        group = features_df[features_df["sector_id"] == sector_id]
        asset_ids_in_sector = group["asset_id"].tolist()

        # 1. sector_ml_score: market-cap-weighted average of ml_rank_score.
        sector_ml_score = weighted_avg(group, "ml_rank_score")

        # 2. sector growth rate (raw, ranked into a score further below).
        sector_growth_raw = sector_growth_rate(asset_ids_in_sector, years_by_asset)

        # 3. sector aggregate P/E (raw, ranked into a score further below).
        # Only stocks with both a positive market cap AND usable net
        # income go into the sums -- a sector with net losses overall
        # (sum of net income <= 0) has no meaningful P/E, left as None.
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
    # Invert P/E before ranking -- same trick stock-level Relative
    # Valuation uses (inv_pe): lower P/E must produce a HIGHER score.
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

    print(f"Saved sector_scores for {len(sector_agg)} sectors.")
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
