import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

INPUT_FILE = "training_dataset.csv"

NUMERIC_FEATURES = [
    "RSI", "MA50", "MA200", "Return_1M", "Return_3M", "Return_6M",
    "Volatility_30D", "Relative_Strength_3M", "ROE", "Total_Debt",
    "Stockholders_Equity", "Net_Income", "Total_Revenue",
    "Capex_Intensity_YoY_Change",
]
TARGET = "Excess_Return_3M"
MIN_TRAIN_ROWS = 500
MIN_TEST_ROWS = 30

df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
df = df.sort_values("Date").reset_index(drop=True)
df["Quarter"] = df["Date"].dt.to_period("Q")


def build_features(sub):
    sector_dummies = pd.get_dummies(sub["Sector"], prefix="Sector")
    return pd.concat([sub[NUMERIC_FEATURES], sector_dummies], axis=1)


def decile_spread(predicted, actual):
    ranked = pd.DataFrame({"pred": predicted, "actual": actual}).sort_values("pred")
    n = len(ranked)
    size = max(1, n // 10)
    return ranked.iloc[-size:]["actual"].mean() - ranked.iloc[:size]["actual"].mean()


def run_walkforward(train_selector, label, quarters_to_report=None):
    """train_selector(df, q) -> train_df for testing quarter q"""
    quarters = sorted(df["Quarter"].unique())
    results = []
    for q in quarters:
        test_df = df[df["Quarter"] == q]
        train_df = train_selector(df, q)
        if len(train_df) < MIN_TRAIN_ROWS or len(test_df) < MIN_TEST_ROWS:
            continue
        X_train_raw, X_test_raw = build_features(train_df), build_features(test_df)
        X_train, X_test = X_train_raw.align(X_test_raw, join="outer", axis=1, fill_value=0)
        y_train, y_test = train_df[TARGET], test_df[TARGET]

        model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        ic, p = spearmanr(preds, y_test)
        spread = decile_spread(preds, y_test.values)
        results.append({"quarter": str(q), "rank_ic": ic, "p_value": p, "decile_spread": spread,
                         "train_rows": len(train_df), "test_rows": len(test_df)})

    rdf = pd.DataFrame(results)
    if quarters_to_report:
        focus = rdf[rdf["quarter"].isin(quarters_to_report)]
    else:
        focus = rdf

    n = len(focus)
    sig_pos = ((focus["rank_ic"] > 0) & (focus["p_value"] < 0.05)).sum()
    pos = (focus["rank_ic"] > 0).sum()
    avg_ic = focus["rank_ic"].mean()
    avg_spread = focus["decile_spread"].mean() * 100
    print(f"\n=== {label} ===")
    print(f"Quarters in focus window: {n}, sig+positive: {sig_pos}, directional+: {pos}, avg IC: {avg_ic:.3f}, avg spread: {avg_spread:.1f}pp")
    return rdf


TARGET_QUARTERS = [str(q) for q in pd.period_range("2024Q1", "2026Q2", freq="Q")]

# Variant A: expanding window, ALL history (what we already ran -- baseline for comparison)
run_walkforward(lambda d, q: d[d["Quarter"] < q], "A: Expanding window, full 2017-2026 history", TARGET_QUARTERS)

# Variant B: exclude 2017-2021 entirely, train only on 2022+ data
run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= pd.Period("2022Q1"))],
    "B: Train only on 2022 onward (drop 2017-2021 entirely)",
    TARGET_QUARTERS,
)

# Variant C: rolling 3-year (12-quarter) trailing window
run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= q - 12)],
    "C: Rolling 3-year trailing window",
    TARGET_QUARTERS,
)

# Variant D: rolling 2-year (8-quarter) trailing window
run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= q - 8)],
    "D: Rolling 2-year trailing window",
    TARGET_QUARTERS,
)

# Variant E: rolling 1-year (4-quarter) trailing window
run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= q - 4)],
    "E: Rolling 1-year trailing window",
    TARGET_QUARTERS,
)

# Variant F: rolling 2.5-year (10-quarter) trailing window
run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= q - 10)],
    "F: Rolling 2.5-year trailing window",
    TARGET_QUARTERS,
)

print("\n\n--- Full per-quarter detail for Variant D (2-year rolling), the current best ---")
rdf_d = run_walkforward(
    lambda d, q: d[(d["Quarter"] < q) & (d["Quarter"] >= q - 8)],
    "D again (for detail)",
    TARGET_QUARTERS,
)
print(rdf_d[rdf_d["quarter"].isin(TARGET_QUARTERS)].to_string(index=False))
