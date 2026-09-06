"""
ingestion_log.py
-------------------------------------------------------------------
Small helper so every pipeline script records itself into the
`ingestion_runs` table -- this replaces your old status.json, and
means the database itself always has an honest, queryable answer to
"when did this last run, and what failed."

Usage from a pipeline script:
    from ingestion_log import start_run, finish_run
    run_id = start_run("daily_prices")
    ... do the work, track ok_count / failed list ...
    finish_run(run_id, ok_count=195, failed_symbols=["XYZ", "ABC"])
-------------------------------------------------------------------
"""
from datetime import datetime, timezone

from db_client import get_client


def start_run(run_type: str) -> int:
    """run_type must be one of: daily_prices, weekly_fundamentals, scoring
    (matches the check constraint on the ingestion_runs table)."""
    supabase = get_client()
    res = supabase.table("ingestion_runs").insert({
        "run_type": run_type,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return res.data[0]["run_id"]


def finish_run(run_id: int, ok_count: int, failed_symbols: list[str]):
    supabase = get_client()
    supabase.table("ingestion_runs").update({
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "ok_count": ok_count,
        "failed_count": len(failed_symbols),
        "failed_symbols": failed_symbols,
    }).eq("run_id", run_id).execute()
