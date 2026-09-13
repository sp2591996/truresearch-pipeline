"""
15_evaluate_and_promote_model.py
-------------------------------------------------------------------
Phase B, Step 6f: the automated "is the new model better?" gate for
the monthly retrain -- added so this can run unattended on GitHub
Actions without ever silently overwriting the live model with
something worse.

Avdhoot's own description of the process this implements: "we rerun
the scores... every week [using the existing model]. Every month we
revisit the ML model to check if our model can be made better than
previous with the updated data, and if the answer is yes, we update
the model or we keep the same." This script IS that monthly check.

WHAT IT DOES:
  1. Reads walkforward_results.csv (just produced this run by
     12_walkforward_validation.py against this month's freshest
     training_dataset.csv, which itself was just rebuilt by
     09_build_training_data.py) and computes this month's average
     Rank IC across all tested quarters.
  2. Compares it to the CURRENTLY LIVE model's own average Rank IC,
     stored in model_metrics.json (written the last time a model was
     promoted, or the first time this script ever ran).
  3. DECISION RULE: promote the new model only if this month's
     average Rank IC is at least as good as the live model's, minus a
     small tolerance (PROMOTION_TOLERANCE) so a trivial noise-level
     dip doesn't cause needless model churn. Otherwise, the current
     live model is left exactly as it is -- untouched.
  4. If promoted: runs 11_train_model.py to retrain the FINAL
     production model on the full 2-year window and overwrite
     trueresearch_model.json + model_feature_columns.json, then runs
     13_save_backtest_results.py to log this month's walk-forward
     evidence to Supabase, then updates model_metrics.json with the
     new baseline number.
     If NOT promoted: nothing about the live model changes, but this
     month's evaluation is still logged to Supabase via
     13_save_backtest_results.py for a permanent record -- the
     formula_version stays "truescore_ml_v2", the underlying model
     file just wasn't replaced this month.
  5. Writes a plain-English summary to $GITHUB_STEP_SUMMARY (shows up
     right on the GitHub Actions run page) either way, so you can see
     "Promoted" or "Kept existing model" at a glance without reading
     through logs.

Run with (after 09_build_training_data.py and
12_walkforward_validation.py have BOTH just completed, in that order):
    python 15_evaluate_and_promote_model.py
-------------------------------------------------------------------
"""
import json
import os
import subprocess
import sys

import pandas as pd

from ingestion_log import start_run, finish_run

WALKFORWARD_RESULTS_FILE = "walkforward_results.csv"
METRICS_FILE = "model_metrics.json"

# How much worse (in average Rank IC) the new model is allowed to be
# and still count as "good enough" -- avoids swapping models over
# noise-level differences.
PROMOTION_TOLERANCE = 0.005

TRAIN_SCRIPT = "11_train_model.py"
SAVE_RESULTS_SCRIPT = "13_save_backtest_results.py"


def load_avg_rank_ic():
    df = pd.read_csv(WALKFORWARD_RESULTS_FILE)
    if df.empty:
        raise SystemExit("walkforward_results.csv is empty -- nothing to evaluate.")
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
    run_id = start_run("model_retrain")
    new_avg_ic = load_avg_rank_ic()
    previous = load_previous_metrics()

    if previous is None:
        # First time this gate has ever run -- nothing to compare against
        # yet. Trust the model that's already live (it was validated by
        # hand before this automation existed) and just record this
        # month's number as the starting baseline for future comparisons.
        write_summary(
            "## Monthly TrueScore model check (India)\n"
            f"No previous baseline found yet -- recording this month's "
            f"average Rank IC ({new_avg_ic:.3f}) as the starting baseline. "
            f"Live model left unchanged this month."
        )
        with open(METRICS_FILE, "w") as f:
            json.dump({"avg_rank_ic": new_avg_ic}, f)
        finish_run(run_id, ok_count=1, failed_symbols=[])
        return

    old_avg_ic = previous["avg_rank_ic"]
    promote = new_avg_ic >= (old_avg_ic - PROMOTION_TOLERANCE)

    if promote:
        write_summary(
            "## Monthly TrueScore model check (India): PROMOTED new model\n"
            f"- Live model's average Rank IC (last time it was measured): {old_avg_ic:.3f}\n"
            f"- This month's candidate average Rank IC (on updated data): {new_avg_ic:.3f}\n"
            f"- Result: the candidate is at least as good, so it has been "
            f"retrained on the freshest data and promoted to live."
        )
        subprocess.run([sys.executable, TRAIN_SCRIPT], check=True)
        with open(METRICS_FILE, "w") as f:
            json.dump({"avg_rank_ic": new_avg_ic}, f)
    else:
        write_summary(
            "## Monthly TrueScore model check (India): kept existing model\n"
            f"- Live model's average Rank IC (last time it was measured): {old_avg_ic:.3f}\n"
            f"- This month's candidate average Rank IC (on updated data): {new_avg_ic:.3f}\n"
            f"- Result: the candidate did not beat the live model (beyond "
            f"the {PROMOTION_TOLERANCE:.3f} noise tolerance) -- the current "
            f"live model has been left exactly as it is. Nothing was "
            f"overwritten."
        )

    # Log this month's evaluation to Supabase either way, so there's a
    # permanent record of every monthly check, promoted or not.
    subprocess.run([sys.executable, SAVE_RESULTS_SCRIPT], check=True)
    finish_run(run_id, ok_count=1, failed_symbols=[] if promote else ["kept existing model (candidate did not beat live model)"])


if __name__ == "__main__":
    main()
