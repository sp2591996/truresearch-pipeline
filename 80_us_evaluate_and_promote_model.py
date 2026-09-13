"""
80_us_evaluate_and_promote_model.py
-------------------------------------------------------------------
The USA equivalent of 15_evaluate_and_promote_model.py -- the
automated "is the new model better?" gate for the monthly USA model
retrain, so it can run unattended without ever silently overwriting
the live US model with something worse.

DIFFERENCE from the India version: 72_us_walkforward_validation.py
tests FIVE different training-window lengths every time it runs
(1, 1.5, 2, 2.5, 3 years), because the best window for the US market
was only decided once, separately, by hand (1 year / 4 quarters won).
This monthly automation does NOT re-decide the window length every
month -- that stays a deliberate, occasional exercise, same as it
would be for a person. It only re-evaluates the ALREADY-CHOSEN 1-year
window (matching 71_train_us_model.py's TRAILING_WINDOW_DAYS) against
this month's freshest data, and compares that to the live model's own
baseline -- exactly the same rule India's gate uses.

Also logs this month's evidence to Supabase via the new
81_us_save_backtest_results.py (the US twin of India's
13_save_backtest_results.py, built alongside this script to close
that gap), so USA gets the same permanent audit trail India already
had.

WHAT IT DOES:
  1. Reads us_walkforward_results.csv (just produced by
     72_us_walkforward_validation.py against this month's freshest
     us_training_dataset.csv), filters to window_quarters == 4 (the
     1-year window 71_train_us_model.py actually uses), and computes
     this month's average Rank IC for that window.
  2. Compares it to the live US model's own average Rank IC, stored
     in us_model_metrics.json.
  3. Promotes (retrains + overwrites us_trueresearch_model.json via
     71_train_us_model.py) only if this month's number is at least as
     good, minus a small noise tolerance. Otherwise, the current live
     US model is left untouched.
  4. Writes a plain-English summary to $GITHUB_STEP_SUMMARY either
     way.

Run with (after 70_build_us_training_data.py and
72_us_walkforward_validation.py have BOTH just completed, in that
order):
    python 80_us_evaluate_and_promote_model.py
-------------------------------------------------------------------
"""
import json
import os
import subprocess
import sys

import pandas as pd

from ingestion_log import start_run, finish_run

WALKFORWARD_RESULTS_FILE = "us_walkforward_results.csv"
METRICS_FILE = "us_model_metrics.json"

# Must match TRAILING_WINDOW_DAYS (365 days = ~4 quarters) chosen in
# 71_train_us_model.py from real evidence. If that ever changes, update
# this to match.
CHOSEN_WINDOW_QUARTERS = 4

PROMOTION_TOLERANCE = 0.005

TRAIN_SCRIPT = "71_train_us_model.py"
SAVE_RESULTS_SCRIPT = "81_us_save_backtest_results.py"


def load_avg_rank_ic():
    df = pd.read_csv(WALKFORWARD_RESULTS_FILE)
    df = df[df["window_quarters"] == CHOSEN_WINDOW_QUARTERS]
    if df.empty:
        raise SystemExit(
            f"No rows for window_quarters == {CHOSEN_WINDOW_QUARTERS} in "
            f"{WALKFORWARD_RESULTS_FILE} -- nothing to evaluate."
        )
    return float(df["rank_ic"].mean())


def load_previous_metrics():
    if not os.path.exists(METRICS_FILE):
        return None
    with open(METRICS_FILE) as f:
        return json.load(f)


def write_summary(text):
    print(text)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(text + "\n")


def main():
    run_id = start_run("us_model_retrain")
    new_avg_ic = load_avg_rank_ic()
    previous = load_previous_metrics()

    if previous is None:
        write_summary(
            "## Monthly TrueScore model check (USA)\n"
            f"No previous baseline found yet -- recording this month's "
            f"average Rank IC ({new_avg_ic:.3f}, 1-year window) as the "
            f"starting baseline. Live US model left unchanged this month."
        )
        with open(METRICS_FILE, "w") as f:
            json.dump({"avg_rank_ic": new_avg_ic}, f)
        finish_run(run_id, ok_count=1, failed_symbols=[])
        return

    old_avg_ic = previous["avg_rank_ic"]
    promote = new_avg_ic >= (old_avg_ic - PROMOTION_TOLERANCE)

    if promote:
        write_summary(
            "## Monthly TrueScore model check (USA): PROMOTED new model\n"
            f"- Live US model's average Rank IC (last measured): {old_avg_ic:.3f}\n"
            f"- This month's candidate average Rank IC (1-year window, updated data): {new_avg_ic:.3f}\n"
            f"- Result: the candidate is at least as good, so it has been "
            f"retrained on the freshest data and promoted to live."
        )
        subprocess.run([sys.executable, TRAIN_SCRIPT], check=True)
        with open(METRICS_FILE, "w") as f:
            json.dump({"avg_rank_ic": new_avg_ic}, f)
    else:
        write_summary(
            "## Monthly TrueScore model check (USA): kept existing model\n"
            f"- Live US model's average Rank IC (last measured): {old_avg_ic:.3f}\n"
            f"- This month's candidate average Rank IC (1-year window, updated data): {new_avg_ic:.3f}\n"
            f"- Result: the candidate did not beat the live model (beyond "
            f"the {PROMOTION_TOLERANCE:.3f} noise tolerance) -- the current "
            f"live US model has been left exactly as it is. Nothing was "
            f"overwritten."
        )

    # Log this month's evaluation to Supabase either way, so there's a
    # permanent record of every monthly check, promoted or not -- same as
    # India already does.
    subprocess.run([sys.executable, SAVE_RESULTS_SCRIPT], check=True)
    finish_run(run_id, ok_count=1, failed_symbols=[] if promote else ["kept existing model (candidate did not beat live model)"])


if __name__ == "__main__":
    main()
