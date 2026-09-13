"""
81_us_save_backtest_results.py
-------------------------------------------------------------------
The USA equivalent of 13_save_backtest_results.py -- this was a real
gap (India has always had this, USA never did) found while building
the monthly automated retrain-and-promote pipeline. Saves the
walk-forward validation evidence (us_walkforward_results.csv, built
by 72_us_walkforward_validation.py) permanently into Supabase's
score_backtest_results table, and registers the US ML sub-model as a
named formula version ("truescore_ml_us_v1", matching the exact tag
73_score_us_stocks.py already references) in score_formula_versions.

DIFFERENCE from the India version: 72_us_walkforward_validation.py
tests FIVE training-window lengths per run (1/1.5/2/2.5/3 years),
because the best window for the US market was decided separately from
India's. This script only saves the rows for window_quarters == 4
(the 1-year window actually used in production by
71_train_us_model.py / us_trueresearch_model.json) -- the other four
window lengths in that CSV were exploratory and are not meant to be
treated as "the model's" validated evidence.

Safe to run more than once (upserts the formula version, replaces the
saved backtest rows for this formula_version each time).

Run with (after 72_us_walkforward_validation.py has completed):
    python 81_us_save_backtest_results.py
-------------------------------------------------------------------
"""
import pandas as pd

from db_client import get_client

FORMULA_VERSION = "truescore_ml_us_v1"
INPUT_FILE = "us_walkforward_results.csv"

# Must match CHOSEN_WINDOW_QUARTERS in 80_us_evaluate_and_promote_model.py
# and TRAILING_WINDOW_DAYS (365 days) in 71_train_us_model.py.
CHOSEN_WINDOW_QUARTERS = 4


def register_formula_version(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": FORMULA_VERSION,
        "description": (
            "XGBoost regression model predicting each US stock's 3-month excess "
            "return vs. the S&P 500 benchmark. Same 14-feature methodology already "
            "validated for India (RSI-14, 50/200-day moving averages, 1/3/6-month "
            "returns, 30-day volatility, relative strength vs. S&P 500, ROE, total "
            "debt, stockholders' equity, net income, total revenue, capex intensity "
            "YoY change), with US GICS sector as a categorical feature. TRAINED ON A "
            "ROLLING 1-YEAR WINDOW (not India's 2-year window) -- this was tested "
            "directly against 1/1.5/2/2.5/3-year windows on real US market history "
            "and the 1-year window won clearly (avg Rank IC 0.081 vs 0.062 for a "
            "2-year window, 23 of 35 quarters statistically significant vs 20 of 35). "
            "See 71_train_us_model.py and 72_us_walkforward_validation.py for the full "
            "methodology. Uses its own formula_version so India and USA never mix."
        ),
        "changed_by_note": "Filled a gap found while building the monthly automated retrain-and-promote pipeline: USA had never had its walk-forward evidence saved to Supabase before, unlike India.",
    }, on_conflict="formula_version").execute()


def save_backtest_rows(supabase):
    supabase.table("score_backtest_results").delete().eq("formula_version", FORMULA_VERSION).execute()

    df = pd.read_csv(INPUT_FILE)
    df = df[df["window_quarters"] == CHOSEN_WINDOW_QUARTERS].reset_index(drop=True)
    if df.empty:
        raise SystemExit(
            f"No rows for window_quarters == {CHOSEN_WINDOW_QUARTERS} in {INPUT_FILE} -- nothing to save."
        )

    period_index = pd.PeriodIndex(df["quarter"], freq="Q")

    count = 0
    for i, row in df.iterrows():
        period = period_index[i]
        start_date = period.start_time.date().isoformat()
        end_date = period.end_time.date().isoformat()

        supabase.table("score_backtest_results").insert({
            "formula_version": FORMULA_VERSION,
            "test_period_start": start_date,
            "test_period_end": end_date,
            "forward_return_window": "3M",
            "metric_type": "rank_ic",
            "result_value": row["rank_ic"],
            "notes": f"p-value={row['p_value']:.4f}, trained on {int(row['train_rows'])} rows (1-year rolling window), tested on {int(row['test_rows'])} rows.",
        }).execute()
        count += 1

        supabase.table("score_backtest_results").insert({
            "formula_version": FORMULA_VERSION,
            "test_period_start": start_date,
            "test_period_end": end_date,
            "forward_return_window": "3M",
            "metric_type": "top_vs_bottom_decile_spread",
            "result_value": row["decile_spread"],
            "notes": "Average actual return of top-10%-predicted stocks minus bottom-10%-predicted stocks.",
        }).execute()
        count += 1

    print(f"Saved {count} backtest result rows for {len(df)} quarters (formula_version={FORMULA_VERSION}).")


if __name__ == "__main__":
    supabase = get_client()
    print("Registering formula version...")
    register_formula_version(supabase)
    print("Saving walk-forward backtest results...")
    save_backtest_rows(supabase)
    print("\nDone.")
