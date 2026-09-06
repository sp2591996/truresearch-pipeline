"""
12_walkforward_validation.py
-------------------------------------------------------------------
Phase B, Step 6d: the REAL validation test -- "walk-forward" validation.

METHODOLOGY (locked in this session, formula_version truescore_ml_v2):
each test quarter's model is trained on ONLY the trailing 2 years
(8 quarters) of data immediately before it -- NOT on all history
available up to that point. This was decided after directly testing
it against an "expanding window" (train on everything before the test
quarter) and several other trailing-window lengths (1yr, 2.5yr, 3yr)
and a simple "2022-onward only" cutoff. The 2-year rolling window won
clearly and consistently -- see "Step6_ML_Model_Decision_Log.md" in
this folder for the full experiment writeup and numbers.

  For each calendar quarter Q:
    1. Train a model using ONLY data from the 2 years immediately
       BEFORE that quarter (never anything from Q itself or later --
       exactly like real life, you never get to see the future, and
       now also never see market regimes too far in the past to still
       be representative of "how the market behaves today")
    2. Use that model to predict excess returns for all stocks in Q
    3. Compare predictions to what ACTUALLY happened in Q
    4. Record: Rank IC (did higher-predicted stocks actually do
       better?), whether that's statistically meaningful (p-value),
       and the "decile spread" (if you'd bought the top 20% most
       highly-rated stocks and shorted/avoided the bottom 20%, how
       big was the gap in actual returns?)

Run with (after 09_build_training_data.py has completed -- does not
need 11_train_model.py to have run first, this trains its own models
per quarter):
    python 12_walkforward_validation.py
-------------------------------------------------------------------
"""
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

INPUT_FILE = "training_dataset.csv"
OUTPUT_FILE = "walkforward_results.csv"

NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]
TARGET = "Excess_Return_3M"
MIN_TRAIN_ROWS = 500   # don't bother testing a quarter if we'd be training on too little
MIN_TEST_ROWS = 30     # don't bother testing a quarter with too few stocks in it
ROLLING_WINDOW_QUARTERS = 8  # 2 years -- locked in after this session's experiments


def build_features(df):
    sector_dummies = pd.get_dummies(df["Sector"], prefix="Sector")
    X = pd.concat([df[NUMERIC_FEATURES], sector_dummies], axis=1)
    return X


def decile_spread(predicted, actual):
    ranked = pd.DataFrame({"pred": predicted, "actual": actual}).sort_values("pred")
    n = len(ranked)
    decile_size = max(1, n // 10)
    bottom = ranked.iloc[:decile_size]["actual"].mean()
    top = ranked.iloc[-decile_size:]["actual"].mean()
    return top - bottom


def main():
    print(f"Loading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["Quarter"] = df["Date"].dt.to_period("Q")

    quarters = sorted(df["Quarter"].unique())
    print(f"Data spans {len(quarters)} calendar quarters: {quarters[0]} to {quarters[-1]}")
    print(f"Each test quarter trains on the trailing {ROLLING_WINDOW_QUARTERS} quarters (~2 years) only.\n")

    results = []

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

        ic, p_value = spearmanr(preds, y_test)
        spread = decile_spread(preds, y_test.values)

        print(f"{q}: train={len(train_df)} rows, test={len(test_df)} rows -> Rank IC={ic:.3f} (p={p_value:.3f}), top-vs-bottom decile spread={spread*100:.1f}pp")

        results.append({
            "quarter": str(q),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "rank_ic": ic,
            "p_value": p_value,
            "decile_spread": spread,
        })

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n{'=' * 70}")
    print("SUMMARY (plain English)")
    print(f"{'=' * 70}")

    if results_df.empty:
        print("Not enough historical data to run even one walk-forward quarter yet.")
        return

    n_quarters = len(results_df)
    n_significant_positive = ((results_df["rank_ic"] > 0) & (results_df["p_value"] < 0.05)).sum()
    n_positive = (results_df["rank_ic"] > 0).sum()
    avg_ic = results_df["rank_ic"].mean()
    avg_spread = results_df["decile_spread"].mean()

    print(f"Quarters tested: {n_quarters}")
    print(f"Quarters where the model's ranking beat random chance in a statistically meaningful way: {n_significant_positive} out of {n_quarters}")
    print(f"Quarters where the ranking was directionally positive (even if not statistically strong): {n_positive} out of {n_quarters}")
    print(f"Average Rank IC across all quarters: {avg_ic:.3f}")
    print(f"Average top-vs-bottom decile spread: {avg_spread*100:.1f} percentage points")
    print(f"\nSaved full quarter-by-quarter results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
