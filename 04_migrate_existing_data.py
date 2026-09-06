"""
04_migrate_existing_data.py
-------------------------------------------------------------------
Phase B, Step 4: one-time migration of your existing 199-stock data
(from the sibling "Old Files" folder) into the new Supabase database.

What this loads:
  - nifty200_list.csv          -> sectors, assets
  - fundamentals_history/*.csv -> fundamentals
  - dashboard_data.json        -> ratios_snapshot (P/E, P/B, market cap,
                                   52-week high/low) + a LEGACY baseline
                                   score (labeled "legacy_interim_v1" --
                                   NOT real TrueScore, see note below)
  - live_prices.json           -> live_prices

Safe to run more than once -- everything uses "upsert" (update if it
already exists, insert if it doesn't), so re-running won't create
duplicates.

IMPORTANT: run 03_add_ratio_columns.sql in Supabase's SQL Editor BEFORE
running this script -- it adds 3 columns this script needs.

Run with:
    python 04_migrate_existing_data.py
-------------------------------------------------------------------
"""
import csv
import json
import os
from datetime import date

from db_client import get_client

OLD_FILES = os.path.join(os.path.dirname(__file__), "..", "Old Files")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def register_formula_version(supabase):
    supabase.table("score_formula_versions").upsert({
        "formula_version": "legacy_interim_v1",
        "description": (
            "The pre-Phase-B interim automated score from compute_auto_scores.py: "
            "60% sector-relative valuation percentile + 40% sector-relative ROE "
            "percentile. This is NOT the real TrueScore ML model -- migrated purely "
            "as a historical baseline for comparison once real TrueScore is validated."
        ),
        "changed_by_note": "Migrated during Phase B, Step 4.",
    }, on_conflict="formula_version").execute()


def upsert_sectors_and_assets(supabase):
    with open(os.path.join(OLD_FILES, "nifty200_list.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    sector_ids = {}
    sector_names = sorted({r["Industry"] for r in rows if r.get("Industry")})
    for name in sector_names:
        existing = supabase.table("sectors").select("sector_id").eq("name", name).execute()
        if existing.data:
            sector_ids[name] = existing.data[0]["sector_id"]
        else:
            res = supabase.table("sectors").insert({"name": name}).execute()
            sector_ids[name] = res.data[0]["sector_id"]
    print(f"Sectors ready: {len(sector_ids)}")

    asset_ids = {}
    for r in rows:
        ticker = r["Symbol"]
        payload = {
            "ticker": ticker,
            "name": r["Company Name"],
            "asset_type": "equity",
            "sector_id": sector_ids.get(r.get("Industry")),
            "isin": r.get("ISIN Code"),
            "yfinance_symbol": r.get("yfinance_symbol"),
        }
        existing = (
            supabase.table("assets")
            .select("asset_id")
            .eq("ticker", ticker)
            .eq("asset_type", "equity")
            .execute()
        )
        if existing.data:
            asset_id = existing.data[0]["asset_id"]
            supabase.table("assets").update(payload).eq("asset_id", asset_id).execute()
        else:
            res = supabase.table("assets").insert(payload).execute()
            asset_id = res.data[0]["asset_id"]
        asset_ids[ticker] = asset_id
    print(f"Assets ready: {len(asset_ids)}")
    return asset_ids


def migrate_fundamentals(supabase, asset_ids):
    folder = os.path.join(OLD_FILES, "fundamentals_history")
    count = 0
    skipped = []
    for filename in sorted(os.listdir(folder)):
        if not filename.endswith("_fundamentals.csv"):
            continue
        ticker = filename[: -len("_fundamentals.csv")]
        asset_id = asset_ids.get(ticker)
        if not asset_id:
            skipped.append(ticker)
            continue
        with open(os.path.join(folder, filename), encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("Year"):
                    continue
                payload = {
                    "asset_id": asset_id,
                    "fiscal_year_end_date": row["Year"],
                    "total_revenue": _num(row.get("Total Revenue")),
                    "net_income": _num(row.get("Net Income")),
                    "ebit": _num(row.get("EBIT")),
                    "ebitda": _num(row.get("EBITDA")),
                    "total_debt": _num(row.get("Total Debt")),
                    "stockholders_equity": _num(row.get("Stockholders Equity")),
                    "cash": _num(row.get("Cash And Cash Equivalents")),
                    "total_assets": _num(row.get("Total Assets")),
                    "free_cash_flow": _num(row.get("Free Cash Flow")),
                    "operating_cash_flow": _num(row.get("Operating Cash Flow")),
                    "capex": _num(row.get("Capital Expenditure")),
                    "roe": _num(row.get("ROE")),
                }
                supabase.table("fundamentals").upsert(
                    payload, on_conflict="asset_id,fiscal_year_end_date"
                ).execute()
                count += 1
    print(f"Fundamentals rows migrated: {count}")
    if skipped:
        print(f"  ! {len(skipped)} fundamentals files had no matching asset (skipped): {skipped[:10]}{'...' if len(skipped) > 10 else ''}")


def migrate_ratios_and_legacy_scores(supabase, asset_ids):
    with open(os.path.join(OLD_FILES, "dashboard_data.json"), encoding="utf-8") as f:
        records = json.load(f)
    today = date.today().isoformat()
    ratio_count = 0
    score_count = 0
    for r in records:
        asset_id = asset_ids.get(r.get("symbol"))
        if not asset_id:
            continue
        supabase.table("ratios_snapshot").upsert({
            "asset_id": asset_id,
            "as_of_date": today,
            "pe_ratio": r.get("pe_ratio"),
            "pb_ratio": r.get("pb_ratio"),
            "market_cap": r.get("market_cap"),
            "week52_high": r.get("week52_high"),
            "week52_low": r.get("week52_low"),
        }, on_conflict="asset_id,as_of_date").execute()
        ratio_count += 1

        if r.get("ml_percentile") is not None:
            supabase.table("scores").upsert({
                "asset_id": asset_id,
                "run_date": today,
                "formula_version": "legacy_interim_v1",
                "overall_score": r.get("ml_percentile"),
            }, on_conflict="asset_id,run_date,formula_version").execute()
            score_count += 1
    print(f"Ratios snapshots migrated: {ratio_count}")
    print(f"Legacy baseline score rows migrated: {score_count}")


def migrate_live_prices(supabase, asset_ids):
    with open(os.path.join(OLD_FILES, "live_prices.json"), encoding="utf-8") as f:
        payload = json.load(f)
    count = 0
    for p in payload.get("prices", []):
        asset_id = asset_ids.get(p["symbol"])
        if not asset_id:
            continue
        price = p.get("price")
        pct = p.get("day_change_pct")
        prev_close = round(price / (1 + pct / 100), 2) if (price is not None and pct not in (None, 0)) else price
        supabase.table("live_prices").upsert({
            "asset_id": asset_id,
            "price": price,
            "prev_close": prev_close,
            "day_change_pct": pct,
        }, on_conflict="asset_id").execute()
        count += 1
    print(f"Live prices migrated: {count}")


if __name__ == "__main__":
    supabase = get_client()
    print("Starting migration...\n")
    register_formula_version(supabase)
    asset_ids = upsert_sectors_and_assets(supabase)
    migrate_fundamentals(supabase, asset_ids)
    migrate_ratios_and_legacy_scores(supabase, asset_ids)
    migrate_live_prices(supabase, asset_ids)
    print("\nMigration complete.")
