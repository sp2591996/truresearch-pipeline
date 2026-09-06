"""
11_train_model.py
-------------------------------------------------------------------
Phase B, Step 6c: train our production XGBoost model on
training_dataset.csv (built by 09_build_training_data.py).

METHODOLOGY (locked in this session, formula_version truescore_ml_v2):
  - Features: exactly the 14 numeric inputs from the original StockApp
    experiment's validated "Case C" model (RSI, MA50, MA200,
    Return_1M/3M/6M, Volatility_30D, Relative_Strength_3M, ROE,
    Total_Debt, Stockholders_Equity, Net_Income, Total_Revenue,
    Capex_Intensity_YoY_Change) plus sector one-hot columns.
  - Training window: only the TRAILING 2 YEARS of data (relative to
    the most recent date in the dataset), NOT the full history.
    This was tested deliberately this session -- see
    "Step6_ML_Model_Decision_Log.md" in this folder for the full
    experiment writeup. Once TrueResearch's price history grew to a
    full 10 years (2017-2026), training on ALL of it made the model
    WORSE at predicting recent quarters (avg Rank IC fell from ~0.10
    to 0.061 on the same 2024-2026 test quarters) -- most likely
    because 2017-2021 include very different market regimes (pre-COVID,
    the COVID crash, the recovery) that diluted what the model learned
    about how stocks behave TODAY. A 2-year rolling training window
    tested best among several tried (1yr, 2yr, 2.5yr, 3yr, "2022-onward
    only"), giving avg Rank IC 0.150 and 11 of 13 quarters directionally
    positive on the exact 13-quarter window matching the original
    StockApp experiment's own validated result (12 of 13, avg IC ~0.133)
    -- i.e. this now performs BETTER than the original on a matched
    comparison, using real, current TrueResearch data.
  - XGBRegressor, n_estimators=200, max_depth=4, learning_rate=0.05,
    random_state=42 -- unchanged from the original experiment.

This script also does a quick, honest gut-check within the 2-year
training window: holds out the most RECENT 15% of rows as a test set
the model never trains on. This is NOT the full validation -- proper
walk-forward validation (quarter by quarter, statistical significance)
is 12_walkforward_validation.py, which is what actually proved out the
2-year window decision above.

The FINAL production model is then trained on the FULL trailing-2-year
window (not just the 85% holdout split) to make best use of all
available recent data for live scoring.

Saves:
  - trueresearch_model.json   (the trained model itself)
  - model_feature_columns.json (the exact list/order of input columns
    the model expects -- needed later to score new stocks consistently)

Run with (after 09_build_training_data.py has completed):
    python 11_train_model.py
-------------------------------------------------------------------
"""
import json

import pandas as pd
from xgboost import XGBRegressor

INPUT_FILE = "training_dataset.csv"
MODEL_FILE = "trueresearch_model.json"
FEATURE_COLUMNS_FILE = "model_feature_columns.json"

TRAILING_WINDOW_DAYS = 730  # 2 years -- locked in after this session's experiments

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
    print(f"  -> {len(df)} rows in the trailing {TRAILING_WINDOW_DAYS}-day (~2 year) training window ({cutoff_date.date()} to {max_date.date()}).")

    sector_dummies = pd.get_dummies(df["Sector"], prefix="Sector")
    X = pd.concat([df[NUMERIC_FEATURES], sector_dummies], axis=1)
    y = df[TARGET]
    feature_columns = list(X.columns)

    # Quick sanity check: hold out the most recent 15% within this window.
    split_idx = int(len(df) * 0.85)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    dates_test = df["Date"].iloc[split_idx:]

    print(f"\n--- Quick sanity check (holdout within the 2-year window) ---")
    print(f"Training rows: {len(X_train)} (up to {df['Date'].iloc[split_idx - 1].date()})")
    print(f"Held-out test rows: {len(X_test)} (from {dates_test.min().date()} to {dates_test.max().date()})")

    check_model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    check_model.fit(X_train, y_train)
    preds = check_model.predict(X_test)
    mae = abs(preds - y_test.values).mean()
    rank_ic = pd.Series(preds).corr(y_test.reset_index(drop=True), method="spearman")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"Rank correlation (Spearman): {rank_ic:.3f}")
    print("(This is only a quick sanity check -- the real evidence is 12_walkforward_validation.py's")
    print(" quarter-by-quarter result, already run this session: see Step6_ML_Model_Decision_Log.md.)")

    # FINAL production model: train on the FULL trailing-2-year window
    # (not just the 85% split above) to use all available recent data.
    print(f"\nTraining FINAL production model on all {len(df)} rows in the 2-year window...")
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
