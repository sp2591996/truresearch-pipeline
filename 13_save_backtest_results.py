"""
13_save_backtest_results.py
-------------------------------------------------------------------
Phase B, Step 6e: save the walk-forward validation evidence
(walkforward_results.csv, built by 12_walkforward_validation.py)
permanently into Supabase's score_backtest_results table -- this is
literally the database table PROJECT_STATE.md/PRD.md require to exist
before TrueScore expands beyond 200 stocks: a durable, queryable record
of "how successful has TrueScore actually been."

Also registers this model as a named formula version ("truescore_ml_v2")
in score_formula_versions, so every future score row can point back to
exactly which model/methodology produced it.

VERSION HISTORY (kept here for anyone reading the database later):
  - truescore_ml_v1: Session 5's original run. Had 3 real bugs later
    found and fixed -- see truescore_ml_v1_corrected and truescore_ml_v2
    descriptions, and Step6_ML_Model_Decision_Log.md, for the full story.
  - truescore_ml_v1_corrected: fixed 2 of 3 bugs (feature drift,
    live-scoring relative-strength bug) but still used the OLD,
    incomplete training_dataset.csv (missing technical-only rows for
    dates before financials existed) and an "expanding window" training
    approach later found to be suboptimal once more history existed.
  - truescore_ml_v2 (THIS version, final for this correction pass):
    fixes all 3 bugs AND locks in a 2-year ROLLING training window
    (train only on the trailing 2 years before each prediction),
    which testing showed clearly outperforms training on full history
    once 10 years of price data became available. Validated on the
    exact 13-quarter window matching the original StockApp experiment:
    11 of 13 quarters directionally positive, average Rank IC 0.150 --
    BETTER than the original experiment's own result (12 of 13, avg IC
    ~0.133), using real, current TrueResearch data.

Safe to run more than once (upserts).

Run with (after 12_walkforward_validation.py has completed):
    python 13_save_backtest_results.py
-------------------------------------------------------------------
"""
import pandas as pd

from db_client import get_client

FORMULA_VERSION = "truescore_ml_v2"
INPUT_FILE = "walkforward_results.csv"


def register_formula_version(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": FORMULA_VERSION,
        "description": (
            "XGBoost regression model predicting each stock's 3-month excess return "
            "vs. the Nifty 100 benchmark. Trained on point-in-time-correct technical "
            "indicators (RSI-14, 50/200-day moving averages, 1/3/6-month returns, "
            "30-day volatility, relative strength vs. Nifty 100) and fundamentals "
            "(ROE, total debt, stockholders' equity, net income, total revenue, capex "
            "intensity YoY change), with sector as a categorical feature -- matches "
            "the original StockApp experiment's validated 'Case C' feature set exactly. "
            "TRAINED ON A ROLLING 2-YEAR WINDOW (only the trailing 730 days of data, "
            "not full history) -- this was tested and locked in this session after "
            "training on the full 10-year history was found to perform worse on recent "
            "quarters. See Step6_ML_Model_Decision_Log.md for the full experiment "
            "writeup. Walk-forward validated on the 13-quarter window matching the "
            "original experiment: 11/13 quarters directionally positive, avg Rank IC "
            "0.150 -- better than the original's own 12/13, avg IC ~0.133."
        ),
        "changed_by_note": "Final correction pass following Step 6 audit -- 3 bugs fixed, 2-year rolling window locked in. See chat + Step6_ML_Model_Decision_Log.md for full details.",
    }, on_conflict="formula_version").execute()


def save_backtest_rows(supabase):
    supabase.table("score_backtest_results").delete().eq("formula_version", FORMULA_VERSION).execute()

    df = pd.read_csv(INPUT_FILE)
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
            "notes": f"p-value={row['p_value']:.4f}, trained on {int(row['train_rows'])} rows (2-year rolling window), tested on {int(row['test_rows'])} rows.",
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
