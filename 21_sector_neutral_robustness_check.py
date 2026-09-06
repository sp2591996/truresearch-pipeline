"""
21_sector_neutral_robustness_check.py
-------------------------------------------------------------------
Phase C: sector-neutral robustness check for the TrueScore ML model
(formula_version truescore_ml_v2). This is the "sector-neutral"
check flagged as an open item since Session 4/6 -- "should happen
before ever expanding past 200 stocks" (which has now happened, so
this was overdue).

WHAT THIS CHECKS, IN PLAIN ENGLISH:
12_walkforward_validation.py already proved the model's ranking beats
random chance when ALL stocks (across every sector) are pooled together
each quarter (avg Rank IC 0.150). But that alone doesn't rule out the
model just being a sector bet in disguise -- e.g. always favoring IT or
Banks whenever that sector happens to do well, rather than genuinely
telling good stocks apart from bad ones WITHIN a sector.

This script re-runs the exact same validated methodology (same features,
same 2-year rolling training window, same XGBoost settings, same input
file) but adds two new measurements per quarter:

  1. SECTOR-NEUTRAL RANK IC: within each sector that has enough stocks
     that quarter (>= MIN_STOCKS_PER_SECTOR), compute the Rank IC
     separately (predicted vs. actual return, stocks in that sector
     only), then average across sectors, weighted by how many stocks
     were in each sector. If this is still solidly positive, the model
     is genuinely differentiating stocks WITHIN sectors, not just
     riding a sector's overall performance.

  2. TOP-DECILE SECTOR CONCENTRATION: what fraction of the model's
     top-10%-ranked stocks that quarter came from a single sector,
     compared to that sector's actual share of the whole universe that
     quarter. A big, persistent gap (e.g. one sector is 8% of the
     universe but 40% of the top decile, quarter after quarter) is a
     warning sign of a sector bet even if the pooled IC looks good.

This does NOT retrain or change the live model in any way -- it is a
read-only evidence-gathering script, exactly like 12's walk-forward
validation. Nothing in `scores` or the live app changes.

Uses the same INPUT_FILE (training_dataset.csv) as
12_walkforward_validation.py -- built from the original 200 stocks used
for the signed-off truescore_ml_v2 validation. Expanding this same
check to the full Nifty 500 is a natural next step, but requires first
rebuilding training_dataset.csv against all 500 stocks (a separate,
longer-running task) -- flagged here, not done in this script.

Run with (after 09_build_training_data.py has been run at least once,
so training_dataset.csv exists in this folder):
    python 21_sector_neutral_robustness_check.py

Output: prints a plain-English summary to the screen, and saves full
quarter-by-quarter + per-sector detail to two new CSV files:
    sector_neutral_results.csv   (one row per quarter: pooled IC vs.
                                   sector-neutral IC, side by side)
    sector_concentration_detail.csv (one row per quarter per sector:
                                   sector's share of top decile vs.
                                   its share of the whole universe)
-------------------------------------------------------------------
"""
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

INPUT_FILE = "training_dataset.csv"
RESULTS_FILE = "sector_neutral_results.csv"
CONCENTRATION_FILE = "sector_concentration_detail.csv"

NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]
TARGET = "Excess_Return_3M"
MIN_TRAIN_ROWS = 500
MIN_TEST_ROWS = 30
ROLLING_WINDOW_QUARTERS = 8       # matches 12_walkforward_validation.py -- keep in sync
MIN_STOCKS_PER_SECTOR = 8         # don't compute a sector's IC off too few stocks in one quarter
TOP_DECILE_FRACTION = 0.10


def build_features(df):
    sector_dummies = pd.get_dummies(df["Sector"], prefix="Sector")
    X = pd.concat([df[NUMERIC_FEATURES], sector_dummies], axis=1)
    return X


def pooled_rank_ic(predicted, actual):
    ic, p_value = spearmanr(predicted, actual)
    return ic, p_value


def sector_neutral_rank_ic(test_df, predicted):
    """Returns (weighted_avg_ic, n_sectors_used, per_sector_rows) for one quarter."""
    tmp = test_df.copy()
    tmp["_pred"] = predicted
    per_sector_rows = []
    weighted_sum = 0.0
    total_weight = 0

    for sector, group in tmp.groupby("Sector"):
        n = len(group)
        if n < MIN_STOCKS_PER_SECTOR:
            continue
        ic, p_value = spearmanr(group["_pred"], group[TARGET])
        if pd.isna(ic):
            continue
        per_sector_rows.append({"sector": sector, "n_stocks": n, "rank_ic": ic, "p_value": p_value})
        weighted_sum += ic * n
        total_weight += n

    if total_weight == 0:
        return None, 0, per_sector_rows
    return weighted_sum / total_weight, len(per_sector_rows), per_sector_rows


def top_decile_sector_concentration(test_df, predicted, quarter_label):
    tmp = test_df.copy()
    tmp["_pred"] = predicted
    n = len(tmp)
    decile_size = max(1, int(n * TOP_DECILE_FRACTION))
    top = tmp.sort_values("_pred", ascending=False).iloc[:decile_size]

    universe_share = tmp["Sector"].value_counts(normalize=True)
    top_share = top["Sector"].value_counts(normalize=True)

    rows = []
    for sector in universe_share.index:
        rows.append({
            "quarter": quarter_label,
            "sector": sector,
            "share_of_universe": universe_share.get(sector, 0.0),
            "share_of_top_decile": top_share.get(sector, 0.0),
            "gap": top_share.get(sector, 0.0) - universe_share.get(sector, 0.0),
        })
    return rows


def main():
    print(f"Loading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["Quarter"] = df["Date"].dt.to_period("Q")

    quarters = sorted(df["Quarter"].unique())
    print(f"Data spans {len(quarters)} calendar quarters: {quarters[0]} to {quarters[-1]}")
    print(f"Same 2-year rolling-window methodology as 12_walkforward_validation.py.\n")

    results = []
    concentration_rows = []

    for q in quarters:
        train_df = df[(df["Quarter"] < q) & (df["Quarter"] >= q - ROLLING_WINDOW_QUARTERS)]
        test_df = df[df["Quarter"] == q]

        if len(train_df) < MIN_TRAIN_ROWS or len(test_df) < MIN_TEST_ROWS:
            print(f"{q}: skipped (train={len(train_df)} rows, test={len(test_df)} rows -- not enough data yet)")
            continue

        X_train_raw = build_features(train_df)
        X_test_raw = build_features(test_df)
        X_train, X_test = X_train_raw.align(X_test_raw, join="outer", axis=1, fill_value=0)

        y_train = train_df[TARGET]
        y_test = test_df[TARGET]

        model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        pooled_ic, pooled_p = pooled_rank_ic(preds, y_test)
        sn_ic, n_sectors, per_sector = sector_neutral_rank_ic(test_df, preds)

        print(f"{q}: pooled Rank IC={pooled_ic:.3f} (p={pooled_p:.3f})  |  "
              f"sector-neutral Rank IC={('n/a' if sn_ic is None else f'{sn_ic:.3f}')} "
              f"(across {n_sectors} sectors with >= {MIN_STOCKS_PER_SECTOR} stocks)")

        results.append({
            "quarter": str(q),
            "test_rows": len(test_df),
            "pooled_rank_ic": pooled_ic,
            "pooled_p_value": pooled_p,
            "sector_neutral_rank_ic": sn_ic,
            "n_sectors_used": n_sectors,
        })

        concentration_rows.extend(top_decile_sector_concentration(test_df, preds, str(q)))

    results_df = pd.DataFrame(results)
    results_df.to_csv(RESULTS_FILE, index=False)
    concentration_df = pd.DataFrame(concentration_rows)
    concentration_df.to_csv(CONCENTRATION_FILE, index=False)

    print(f"\n{'=' * 70}")
    print("SUMMARY (plain English)")
    print(f"{'=' * 70}")

    if results_df.empty:
        print("Not enough historical data to run even one quarter yet.")
        return

    valid = results_df.dropna(subset=["sector_neutral_rank_ic"])
    n_quarters = len(results_df)
    n_sn_quarters = len(valid)
    avg_pooled_ic = results_df["pooled_rank_ic"].mean()
    avg_sn_ic = valid["sector_neutral_rank_ic"].mean() if n_sn_quarters else float("nan")
    n_sn_positive = (valid["sector_neutral_rank_ic"] > 0).sum() if n_sn_quarters else 0

    print(f"Quarters tested: {n_quarters} ({n_sn_quarters} had enough stocks per sector to compute a sector-neutral score)")
    print(f"Average POOLED Rank IC (all stocks mixed together, matches 12_walkforward_validation.py): {avg_pooled_ic:.3f}")
    print(f"Average SECTOR-NEUTRAL Rank IC (comparing stocks only within their own sector): {avg_sn_ic:.3f}")
    print(f"Quarters where sector-neutral IC was still positive: {n_sn_positive} of {n_sn_quarters}")

    if n_sn_quarters:
        gap = avg_pooled_ic - avg_sn_ic
        print(f"\nGap between pooled and sector-neutral average IC: {gap:.3f}")
        if avg_sn_ic > 0 and gap < 0.05:
            print("READING: sector-neutral IC is close to the pooled IC and still clearly positive --")
            print("the model's edge looks like genuine stock-picking within sectors, not a sector bet.")
        elif avg_sn_ic > 0 and gap >= 0.05:
            print("READING: sector-neutral IC is positive but noticeably weaker than the pooled IC --")
            print("some of the model's edge does appear to come from sector-level bets, not just")
            print("stock-picking within sectors. Not necessarily disqualifying, but worth knowing.")
        else:
            print("READING: sector-neutral IC is flat or negative even though the pooled IC looked good --")
            print("this is the exact failure mode this check exists to catch. The model's apparent edge")
            print("may be substantially a sector bet rather than real stock-picking skill. Recommend")
            print("reviewing before relying further on TrueScore rankings for cross-sector decisions.")

    # Sector concentration flag: sectors whose average gap (top-decile share minus universe
    # share) is large and consistently positive across quarters.
    if not concentration_df.empty:
        sector_avg_gap = (
            concentration_df.groupby("sector")["gap"]
            .agg(["mean", "count"])
            .sort_values("mean", ascending=False)
        )
        flagged = sector_avg_gap[(sector_avg_gap["mean"] > 0.10) & (sector_avg_gap["count"] >= max(3, n_quarters // 3))]
        print(f"\nSectors persistently over-represented in the top decile (by >10 percentage points, on average):")
        if flagged.empty:
            print("  None -- no single sector consistently dominates the model's top picks.")
        else:
            for sector, row in flagged.iterrows():
                print(f"  {sector}: averages {row['mean']*100:.1f} percentage points more of the top decile than its share of the universe, across {int(row['count'])} quarters")

    print(f"\nSaved quarter-by-quarter pooled-vs-sector-neutral detail to {RESULTS_FILE}")
    print(f"Saved per-sector top-decile concentration detail to {CONCENTRATION_FILE}")


if __name__ == "__main__":
    main()
