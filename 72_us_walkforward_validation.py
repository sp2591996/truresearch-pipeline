"""
72_us_walkforward_validation.py
-------------------------------------------------------------------
Phase 2 (US ML model), Step 3: the REAL validation test for the US
model -- "walk-forward" validation, same idea as
12_walkforward_validation.py did for India.

  For each calendar quarter Q:
    1. Train a model using ONLY data from N years immediately BEFORE
       that quarter (never anything from Q itself or later -- exactly
       like real life, you never get to see the future)
    2. Use that model to predict excess returns for all US stocks in Q
    3. Compare predictions to what ACTUALLY happened in Q
    4. Record: Rank IC (did higher-predicted stocks actually do
       better?), whether that's statistically meaningful (p-value),
       and the "decile spread" (if you'd bought the top 20% most
       highly-rated stocks and avoided the bottom 20%, how big was the
       gap in actual returns?)

DIFFERENCE from the India version: India's script tests only ONE fixed
window (2 years / 8 quarters), because that window was already proven
best for India through a separate round of experiments. We have NOT
yet done that experiment for the US market -- US stocks could behave
differently. So THIS script tests several window lengths in one run
(1, 1.5, 2, 2.5, and 3 years) and prints a side-by-side comparison at
the end, so the best-performing window for the US market can be picked
using real evidence, exactly the same rigor India's model went
through -- rather than assuming India's answer (2 years) automatically
transfers to a completely different market.

Run with (after 70_build_us_training_data.py has completed -- does
not need 71_train_us_model.py to have run first, this trains its own
models per quarter per window length):
    python 72_us_walkforward_validation.py
-------------------------------------------------------------------
"""
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

INPUT_FILE = "us_training_dataset.csv"
OUTPUT_FILE = "us_walkforward_results.csv"

NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]
TARGET = "Excess_Return_3M"
MIN_TRAIN_ROWS = 500   # don't bother testing a quarter if we'd be training on too little
MIN_TEST_ROWS = 30     # don't bother testing a quarter with too few stocks in it

# Window lengths to try, in quarters -- 1yr, 1.5yr, 2yr (India's chosen
# window), 2.5yr, 3yr. Whichever comes out best on real US data wins.
WINDOW_OPTIONS_QUARTERS = [4, 6, 8, 10, 12]


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


def run_walkforward(df, quarters, window_quarters):
    results = []
    for q in quarters:
        train_df = df[(df["Quarter"] < q) & (df["Quarter"] >= q - window_quarters)]
        test_df = df[df["Quarter"] == q]

        if len(train_df) < MIN_TRAIN_ROWS or len(test_df) < MIN_TEST_ROWS:
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

        results.append({
            "window_quarters": window_quarters,
            "quarter": str(q),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "rank_ic": ic,
            "p_value": p_value,
            "decile_spread": spread,
        })
    return results


def main():
    print(f"Loading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["Quarter"] = df["Date"].dt.to_period("Q")

    quarters = sorted(df["Quarter"].unique())
    print(f"Data spans {len(quarters)} calendar quarters: {quarters[0]} to {quarters[-1]}")
    print(f"Testing {len(WINDOW_OPTIONS_QUARTERS)} different training-window lengths: "
          f"{[f'{w/4:.1f}yr' for w in WINDOW_OPTIONS_QUARTERS]}\n")

    all_results = []
    for window_quarters in WINDOW_OPTIONS_QUARTERS:
        print(f"--- Testing {window_quarters} quarters (~{window_quarters/4:.1f} years) training window ---")
        window_results = run_walkforward(df, quarters, window_quarters)
        for r in window_results:
            print(f"  {r['quarter']}: train={r['train_rows']} rows, test={r['test_rows']} rows "
                  f"-> Rank IC={r['rank_ic']:.3f} (p={r['p_value']:.3f}), "
                  f"top-vs-bottom decile spread={r['decile_spread']*100:.1f}pp")
        all_results.extend(window_results)
        print()

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print(f"{'=' * 70}")
    print("SUMMARY -- comparing training-window lengths (plain English)")
    print(f"{'=' * 70}")

    if results_df.empty:
        print("Not enough historical data to run even one walk-forward quarter yet.")
        return

    summary_rows = []
    for window_quarters in WINDOW_OPTIONS_QUARTERS:
        subset = results_df[results_df["window_quarters"] == window_quarters]
        if subset.empty:
            continue
        n_quarters = len(subset)
        n_significant_positive = ((subset["rank_ic"] > 0) & (subset["p_value"] < 0.05)).sum()
        n_positive = (subset["rank_ic"] > 0).sum()
        avg_ic = subset["rank_ic"].mean()
        avg_spread = subset["decile_spread"].mean()
        summary_rows.append({
            "window_years": window_quarters / 4,
            "quarters_tested": n_quarters,
            "statistically_significant_positive": n_significant_positive,
            "directionally_positive": n_positive,
            "avg_rank_ic": avg_ic,
            "avg_decile_spread_pp": avg_spread * 100,
        })

    summary_df = pd.DataFrame(summary_rows)
    for _, row in summary_df.iterrows():
        print(f"{row['window_years']:.1f} year window: "
              f"{int(row['statistically_significant_positive'])}/{int(row['quarters_tested'])} quarters statistically significant, "
              f"{int(row['directionally_positive'])}/{int(row['quarters_tested'])} directionally positive, "
              f"avg Rank IC={row['avg_rank_ic']:.3f}, avg decile spread={row['avg_decile_spread_pp']:.1f}pp")

    best = summary_df.sort_values("avg_rank_ic", ascending=False).iloc[0]
    print(f"\nBest-performing window on this evidence: {best['window_years']:.1f} years "
          f"(avg Rank IC={best['avg_rank_ic']:.3f}).")
    print("If this isn't the 2-year window India's model uses, update TRAILING_WINDOW_DAYS in "
          "71_train_us_model.py to match before training the final US production model.")
    print(f"\nSaved full quarter-by-quarter, window-by-window results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
