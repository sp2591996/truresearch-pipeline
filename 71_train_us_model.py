"""
71_train_us_model.py
-------------------------------------------------------------------
Phase 2 (US ML model), Step 2: train a US-specific XGBoost model on
us_training_dataset.csv (built by 70_build_us_training_data.py).

This uses the same 14 numeric features already validated for India
(formula_version truescore_ml_v2, see 11_train_model.py): RSI, MA50,
MA200, Return_1M/3M/6M, Volatility_30D, Relative_Strength_3M, ROE,
Total_Debt, Stockholders_Equity, Net_Income, Total_Revenue,
Capex_Intensity_YoY_Change, plus sector one-hot columns (US GICS
sectors instead of India's sectors) -- and the same XGBRegressor
hyperparameters (n_estimators=200, max_depth=4, learning_rate=0.05,
random_state=42).

TRAINING WINDOW -- decided from real evidence, not assumed from
India: 72_us_walkforward_validation.py tested 5 window lengths (1,
1.5, 2, 2.5, 3 years) against actual US market history (2017-2026,
35 quarters). Results: the 1-YEAR window won clearly -- avg Rank IC
0.081 vs 0.062 for the 2-year window India uses, and 23 of 35
quarters statistically significant vs 20 of 35 for 2 years. This
makes sense: US markets are more efficient/faster-moving than India's,
so a shorter, more current training window captures "how the market
behaves today" better than a longer one that dilutes it with older
regimes. If new data later shifts this conclusion, re-run
72_us_walkforward_validation.py and update TRAILING_WINDOW_DAYS below
to match whatever wins.

This script also does a quick, honest gut-check: holds out the most
RECENT 15% of rows (within the 1-year window) as a test set the model
never trains on. The FINAL production model is then trained on the
FULL trailing-1-year window to make best use of all available recent
data for live scoring.

Saves:
  - us_trueresearch_model.json    (the trained model itself)
  - us_model_feature_columns.json (the exact list/order of input
    columns the model expects)
Both filenames are DIFFERENT from India's model files -- the two
markets never share a model.

Run with (after 70_build_us_training_data.py has completed):
    python 71_train_us_model.py
-------------------------------------------------------------------
"""
import json

import pandas as pd
from xgboost import XGBRegressor

INPUT_FILE = "us_training_dataset.csv"
MODEL_FILE = "us_trueresearch_model.json"
FEATURE_COLUMNS_FILE = "us_model_feature_columns.json"

TRAILING_WINDOW_DAYS = 365  # 1 year -- chosen from 72_us_walkforward_validation.py's real US evidence (best avg Rank IC among 1/1.5/2/2.5/3 year options tested)

NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]
TARGET = "Excess_Return_3M"


def main():
    print(f"Loading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    print(f"  -> {len(df)} total rows loaded (full available history).")

    df = df.sort_values("Date").reset_index(drop=True)

    max_date = df["Date"].max()
    cutoff_date = max_date - pd.Timedelta(days=TRAILING_WINDOW_DAYS)
    df = df[df["Date"] >= cutoff_date].reset_index(drop=True)
    print(f"  -> {len(df)} rows in the trailing {TRAILING_WINDOW_DAYS}-day (~{TRAILING_WINDOW_DAYS/365:.1f} year) training window ({cutoff_date.date()} to {max_date.date()}).")

    sector_dummies = pd.get_dummies(df["Sector"], prefix="Sector")
    X = pd.concat([df[NUMERIC_FEATURES], sector_dummies], axis=1)
    y = df[TARGET]
    feature_columns = list(X.columns)

    # Quick sanity check: hold out the most recent 15% within this window.
    split_idx = int(len(df) * 0.85)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    dates_test = df["Date"].iloc[split_idx:]

    print(f"\n--- Quick sanity check (holdout within the {TRAILING_WINDOW_DAYS/365:.1f}-year window) ---")
    print(f"Training rows: {len(X_train)} (up to {df['Date'].iloc[split_idx - 1].date()})")
    print(f"Held-out test rows: {len(X_test)} (from {dates_test.min().date()} to {dates_test.max().date()})")

    check_model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    check_model.fit(X_train, y_train)
    preds = check_model.predict(X_test)
    mae = abs(preds - y_test.values).mean()
    rank_ic = pd.Series(preds).corr(y_test.reset_index(drop=True), method="spearman")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"Rank correlation (Spearman): {rank_ic:.3f}")
    print("(This is only a quick sanity check -- the real evidence is 72_us_walkforward_validation.py's")
    print(" quarter-by-quarter result -- run that next before trusting this model for live scoring.)")

    # FINAL production model: train on the FULL trailing window
    # (not just the 85% split above) to use all available recent data.
    print(f"\nTraining FINAL production model on all {len(df)} rows in the {TRAILING_WINDOW_DAYS/365:.1f}-year window...")
    model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)

    print("\nTop 10 most important features:")
    importances = pd.Series(model.feature_importances_, index=feature_columns).sort_values(ascending=False)
    for name, score in importances.head(10).items():
        print(f"  {name}: {score:.4f}")

    model.save_model(MODEL_FILE)
    with open(FEATURE_COLUMNS_FILE, "w") as f:
        json.dump(feature_columns, f)

    print(f"\nSaved trained model to {MODEL_FILE}")
    print(f"Saved feature column list to {FEATURE_COLUMNS_FILE}")


if __name__ == "__main__":
    main()
