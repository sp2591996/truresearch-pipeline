"""
17_score_performance_tracking.py
-------------------------------------------------------------------
Phase C, Step 1: the ONGOING, ever-growing answer to "has TrueScore
actually worked" -- as opposed to `13_save_backtest_results.py`,
which was a one-time report you already reviewed and signed off on.

This script does NOT re-run any backtest logic. It looks at scores
TrueScore has ALREADY given out in the past (rows already sitting in
the `scores` table, from any run -- truescore_v1, truescore_v2,
whatever comes next), and asks a simple, honest question for each one:
"now that real time has passed since that score was given, how did
the stocks that scored highest actually do, versus the ones that
scored lowest?"

How it works, for every distinct (formula_version, run_date) pair
already sitting in `scores`:
  1. Split that day's ~200 scored stocks into 10 equal-ish groups
     ("deciles") by their overall_score -- decile 10 = highest scores,
     decile 1 = lowest.
  2. For each of the three forward windows (1 month / 3 months / 1
     year) that have ALREADY passed since that score's run_date (a
     score given last week obviously can't have a 1-year-forward
     result yet -- that field is simply left blank until a year from
     now actually arrives), compute each stock's real price return
     from the score date to that future date, then average it across
     every stock in the decile.
  3. Save one row per (date, formula_version, decile) into
     `score_performance_tracking` -- e.g. "on 2026-09-06, truescore_v2,
     decile 10, stocks averaged +2.1% over the next month."

Because it's keyed on (date, formula_version, decile) and safely
UPSERTS, running this script again later doesn't duplicate anything --
it just fills in whichever forward windows have newly become
available since the last run (e.g. the first time a score is old
enough to finally have a real 1-year forward result).

**Important, honest expectation-setting:** the very first time you run
this (right after Phase B just finished), EVERY score in the database
was run today -- so there is no "the future" yet for any of them. This
run will find nothing to compute yet, and that is correct, expected
behavior, not a bug. Real numbers start appearing here automatically,
a little at a time, as the weeks and months pass and this job keeps
running on its weekly schedule.

Run manually:
    python 17_score_performance_tracking.py
-------------------------------------------------------------------
"""
from datetime import date, timedelta

import pandas as pd

from db_client import get_client
from ingestion_log import start_run, finish_run

# Calendar-day windows. We don't require an exact trading day match --
# for each target date we use the closest available price ON OR BEFORE
# it (see `price_on_or_before`), same tolerant approach as the rest of
# the pipeline.
HORIZONS = {
    "avg_forward_return_1m": 30,
    "avg_forward_return_3m": 91,
    "avg_forward_return_1y": 365,
}
NUM_DECILES = 10
PRICE_PAGE_SIZE = 1000
ASSET_ID_CHUNK = 50
# If the closest available price is more than this many days away from
# the date we asked for, treat it as "no usable price" rather than
# silently using a stale number (a stock that stopped trading, or a
# gap in the historical backfill).
MAX_PRICE_STALENESS_DAYS = 10


def fetch_scored_runs(supabase) -> pd.DataFrame:
    """Every (formula_version, run_date) pair that has ever been scored,
    with each stock's asset_id + overall_score."""
    PAGE = 1000
    all_rows = []
    start = 0
    while True:
        res = (
            supabase.table("scores")
            .select("asset_id, run_date, formula_version, overall_score")
            .order("run_date")
            .range(start, start + PAGE - 1)
            .execute()
        )
        page = res.data
        all_rows.extend(page)
        if len(page) < PAGE:
            break
        start += PAGE
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    df["run_date"] = pd.to_datetime(df["run_date"]).dt.date
    df = df.dropna(subset=["overall_score"])
    return df


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_prices_in_range(supabase, asset_ids, start_date, end_date) -> pd.DataFrame:
    """asset_id, date, close for the given assets, between start_date and
    end_date inclusive -- paginated (Supabase caps any single query at
    1000 rows) and chunked by asset_id (a very long IN-list is slow/risky)."""
    all_rows = []
    for chunk in chunk_list(asset_ids, ASSET_ID_CHUNK):
        start = 0
        while True:
            res = (
                supabase.table("prices_daily")
                .select("asset_id, date, close")
                .in_("asset_id", chunk)
                .gte("date", start_date.isoformat())
                .lte("date", end_date.isoformat())
                .order("date")
                .range(start, start + PRICE_PAGE_SIZE - 1)
                .execute()
            )
            page = res.data
            all_rows.extend(page)
            if len(page) < PRICE_PAGE_SIZE:
                break
            start += PRICE_PAGE_SIZE
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def price_on_or_before(price_series: pd.Series, target_date) -> float | None:
    """price_series: a pandas Series of close prices indexed by date
    (already sorted ascending) for ONE asset. Returns the closest price
    on or before target_date, or None if nothing usable is within
    MAX_PRICE_STALENESS_DAYS of it."""
    usable = price_series[price_series.index <= target_date]
    if usable.empty:
        return None
    last_date = usable.index[-1]
    if (target_date - last_date).days > MAX_PRICE_STALENESS_DAYS:
        return None
    return usable.iloc[-1]


def compute_one_run(supabase, run_date, formula_version, group: pd.DataFrame, today: date) -> list[dict]:
    """Returns the score_performance_tracking rows for one (run_date,
    formula_version) pair -- one row per decile, with only the forward
    windows that have already passed filled in."""
    reached_horizons = {
        col: days for col, days in HORIZONS.items()
        if run_date + timedelta(days=days) <= today
    }
    if not reached_horizons:
        return []  # this score is too recent -- not even 1 month has passed yet

    asset_ids = group["asset_id"].tolist()
    furthest_days = max(reached_horizons.values())
    prices_df = fetch_prices_in_range(
        supabase, asset_ids,
        start_date=run_date - timedelta(days=MAX_PRICE_STALENESS_DAYS),
        end_date=min(run_date + timedelta(days=furthest_days + MAX_PRICE_STALENESS_DAYS), today),
    )
    if prices_df.empty:
        return []

    # Decile assignment: 10 = highest overall_score, 1 = lowest.
    # qcut needs unique bin edges -- duplicates='drop' handles the rare
    # case of many identical scores by merging bins rather than erroring.
    try:
        group = group.copy()
        group["decile"] = pd.qcut(
            group["overall_score"], NUM_DECILES, labels=False, duplicates="drop"
        ) + 1
    except ValueError:
        return []  # not enough distinct scores that day to form deciles at all

    rows_out = []
    for decile, decile_group in group.groupby("decile"):
        decile = int(decile)
        result_row = {"date": run_date.isoformat(), "formula_version": formula_version, "decile": decile}
        for col, days in reached_horizons.items():
            target_date = run_date + timedelta(days=days)
            returns = []
            for asset_id in decile_group["asset_id"]:
                series = prices_df[prices_df["asset_id"] == asset_id].set_index("date")["close"].sort_index()
                base_price = price_on_or_before(series, run_date)
                future_price = price_on_or_before(series, target_date)
                if base_price and future_price and base_price > 0:
                    returns.append((future_price / base_price) - 1)
            result_row[col] = (sum(returns) / len(returns)) if returns else None
        rows_out.append(result_row)
    return rows_out


def main():
    supabase = get_client()
    today = date.today()
    run_id = start_run("performance_tracking")

    print("Loading every score TrueResearch has ever given out...")
    scored = fetch_scored_runs(supabase)
    if scored.empty:
        print("No scores found in the database yet -- nothing to track. (Run the scoring script first.)")
        finish_run(run_id, ok_count=0, failed_symbols=[])
        return

    all_output_rows = []
    failed = []
    grouped = list(scored.groupby(["run_date", "formula_version"]))
    print(f"Found {len(grouped)} distinct (run_date, formula_version) score runs to check.\n")

    for (run_date, formula_version), group in grouped:
        label = f"{run_date} / {formula_version}"
        try:
            rows = compute_one_run(supabase, run_date, formula_version, group, today)
            if rows:
                print(f"  {label}: writing {len(rows)} decile rows.")
                all_output_rows.extend(rows)
            else:
                print(f"  {label}: nothing new yet (too recent, or no usable prices) -- skipped.")
        except Exception as e:
            print(f"  ! {label}: failed -- {e}")
            failed.append(label)

    if all_output_rows:
        CHUNK = 500
        for i in range(0, len(all_output_rows), CHUNK):
            supabase.table("score_performance_tracking").upsert(
                all_output_rows[i:i + CHUNK], on_conflict="date,formula_version,decile"
            ).execute()

    finish_run(run_id, ok_count=len(all_output_rows), failed_symbols=failed)
    print(f"\nDone. Saved/updated {len(all_output_rows)} decile-performance rows. Failed run-checks: {failed if failed else 'none'}.")


if __name__ == "__main__":
    main()
