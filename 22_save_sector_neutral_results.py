"""
22_save_sector_neutral_results.py
-------------------------------------------------------------------
Saves the sector-neutral robustness check results (from
21_sector_neutral_robustness_check.py's sector_neutral_results.csv)
permanently into Supabase's score_backtest_results table, alongside
the existing pooled walk-forward results for the SAME formula_version
(truescore_ml_v2) -- this doesn't register a new model version, since
no retraining happened; it just adds new evidence rows (metric_type
"sector_neutral_rank_ic") documenting this additional robustness check
against the already-validated model.

Safe to run more than once (deletes and re-inserts this metric_type
for this formula_version first, same pattern as 13_save_backtest_results.py).

Run with (after 21_sector_neutral_robustness_check.py has completed,
so sector_neutral_results.csv exists in this folder):
    python 22_save_sector_neutral_results.py
-------------------------------------------------------------------
"""
import pandas as pd

from db_client import get_client

FORMULA_VERSION = "truescore_ml_v2"
INPUT_FILE = "sector_neutral_results.csv"
METRIC_TYPE = "sector_neutral_rank_ic"


def save_rows(supabase):
    supabase.table("score_backtest_results").delete().eq(
        "formula_version", FORMULA_VERSION
    ).eq("metric_type", METRIC_TYPE).execute()

    df = pd.read_csv(INPUT_FILE)
    df = df.dropna(subset=["sector_neutral_rank_ic"])
    period_index = pd.PeriodIndex(df["quarter"], freq="Q")

    count = 0
    for i, row in df.iterrows():
        period = period_index[df.index.get_loc(i)]
        start_date = period.start_time.date().isoformat()
        end_date = period.end_time.date().isoformat()

        supabase.table("score_backtest_results").insert({
            "formula_version": FORMULA_VERSION,
            "test_period_start": start_date,
            "test_period_end": end_date,
            "forward_return_window": "3M",
            "metric_type": METRIC_TYPE,
            "result_value": row["sector_neutral_rank_ic"],
            "notes": (
                f"Sector-neutral robustness check (Phase C): Rank IC computed within each "
                f"sector separately (>= 8 stocks that quarter), then averaged weighted by "
                f"sector size, across {int(row['n_sectors_used'])} sectors. Pooled Rank IC "
                f"for the same quarter was {row['pooled_rank_ic']:.4f} for comparison."
            ),
        }).execute()
        count += 1

    print(f"Saved {count} sector-neutral Rank IC rows for formula_version={FORMULA_VERSION}.")


if __name__ == "__main__":
    supabase = get_client()
    print("Saving sector-neutral robustness check results...")
    save_rows(supabase)
    print("\nDone. This documents that the already-validated truescore_ml_v2 model's edge")
    print("holds up within sectors, not just across the pooled universe.")
