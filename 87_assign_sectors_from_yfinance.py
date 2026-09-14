"""
87_assign_sectors_from_yfinance.py
-------------------------------------------------------------------
Stage 2, Step 3: fills in `sector_id` for every active India equity
that doesn't have one yet (currently the 2,068 stocks
86_add_full_nse_universe.py just added, which NSE's own list doesn't
classify by industry).

Uses Yahoo Finance's own sector data (via get_fundamentals(), the same
market_data_provider.py function the weekly fundamentals refresh
already uses) -- Avdhoot's explicit choice over hand-classifying 2,000+
companies, since it's automatic, consistent with how every other fact
in this project is sourced, and doesn't rely on anyone's memory of
what business a small/obscure company is actually in.

How it works, per stock:
  1. Calls get_fundamentals(yf_symbol) and reads the "sector" field
     Yahoo Finance returns (e.g. "Technology", "Financial Services",
     "Consumer Cyclical" -- Yahoo's own GICS-like taxonomy, similar
     in spirit to but NOT identical wording to this project's existing
     India sector names).
  2. Looks for an existing India sector whose name already matches
     (case-insensitive). If found, uses it.
  3. If not found, creates a NEW sector row for that exact Yahoo sector
     name (market='india') -- this project's own Growth/Sector Score
     features work fine with more sectors than the original ~20; new
     sectors just mean smaller peer groups for those stocks.
  4. If Yahoo Finance has no sector for this stock at all (some very
     small/inactive/delisted-adjacent tickers return nothing), it's
     put in a single shared "Unclassified" sector (created once) and
     recorded in this run's failed list -- never silently left NULL,
     and never guessed.

Resumable and safe to re-run: only ever processes stocks where
sector_id IS NULL, so an interrupted run just picks up where it left
off, and a completed run has nothing left to do.

This is the slow step (one Yahoo Finance call per stock, ~2,000
stocks) -- expect roughly 30-90 minutes depending on Yahoo's response
time. Fine to run in the background/overnight.

Run manually:
    python 87_assign_sectors_from_yfinance.py

    python 87_assign_sectors_from_yfinance.py --retry-unclassified
        A normal run never revisits a stock once it's been assigned a
        sector -- including the "Unclassified" fallback bucket, since
        that IS a sector_id, not NULL. This flag instead re-checks
        every stock CURRENTLY sitting in Unclassified (a transient
        Yahoo Finance hiccup on the first pass is a common reason, not
        necessarily "this stock truly has no sector data") and moves
        any that now get a real answer out of Unclassified. Stocks
        still unmatched after a retry stay in Unclassified -- that's
        an honest outcome, not a bug to keep chasing forever.
-------------------------------------------------------------------
"""
import sys
import time

from db_client import get_client
from market_data_provider import get_fundamentals

MARKET = "india"
UNCLASSIFIED_SECTOR_NAME = "Unclassified"


def get_or_create_sector(supabase, sector_cache: dict, name: str) -> int:
    key = name.strip().lower()
    if key in sector_cache:
        return sector_cache[key]
    res = supabase.table("sectors").upsert(
        {"name": name, "market": MARKET}, on_conflict="name,market"
    ).execute()
    sector_id = res.data[0]["sector_id"]
    sector_cache[key] = sector_id
    return sector_id


def main():
    supabase = get_client()

    existing_sectors = (
        supabase.table("sectors").select("sector_id, name").eq("market", MARKET).execute()
    ).data
    sector_cache = {s["name"].strip().lower(): s["sector_id"] for s in existing_sectors}
    print(f"Found {len(sector_cache)} existing India sectors.")

    retry_mode = "--retry-unclassified" in sys.argv
    if retry_mode:
        unclassified_id = sector_cache.get(UNCLASSIFIED_SECTOR_NAME.lower())
        if unclassified_id is None:
            print("No Unclassified sector exists yet -- nothing to retry.")
            return
        sector_filter = ("sector_id", unclassified_id)
    else:
        sector_filter = None

    # Supabase/PostgREST silently caps any .select() at 1000 rows unless
    # you page through it with .range() -- the same gotcha this project
    # already hit and fixed for the Gold chart (Session 28) and Market
    # Mood's price fetch. With 2,000+ stocks needing a sector, a single
    # un-paginated query here would only ever process the first 1,000.
    assets = []
    page_size = 1000
    offset = 0
    while True:
        query = (
            supabase.table("assets")
            .select("asset_id, ticker, yfinance_symbol")
            .eq("asset_type", "equity")
            .eq("market", MARKET)
            .eq("is_active", True)
        )
        if retry_mode:
            query = query.eq("sector_id", unclassified_id)
        else:
            query = query.is_("sector_id", "null")
        resp = query.range(offset, offset + page_size - 1).execute()
        batch = resp.data or []
        assets.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    if retry_mode:
        print(f"{len(assets)} stocks currently sitting in Unclassified -- retrying each one.\n")
    else:
        print(f"{len(assets)} stocks need a sector assigned.\n")

    if not assets:
        print("Nothing to do -- every active India equity already has a sector.")
        return

    # Not logged to ingestion_runs -- this is a one-time setup script,
    # same as 19_add_nifty500_expansion.py / 67_add_sp500_stocks.py /
    # 86_add_full_nse_universe.py before it.
    ok_count = 0
    failed = []

    for i, a in enumerate(assets, 1):
        ticker = a["ticker"]
        yf_symbol = a.get("yfinance_symbol")
        if not yf_symbol:
            print(f"  [{i}/{len(assets)}] {ticker}: no yfinance_symbol on file -- skipped")
            failed.append(f"{ticker} (no yfinance_symbol)")
            continue

        info = get_fundamentals(yf_symbol)
        yahoo_sector = (info or {}).get("sector")

        try:
            if yahoo_sector:
                sector_id = get_or_create_sector(supabase, sector_cache, yahoo_sector)
                supabase.table("assets").update({"sector_id": sector_id}).eq("asset_id", a["asset_id"]).execute()
                ok_count += 1
                print(f"  [{i}/{len(assets)}] {ticker}: {yahoo_sector}")
            else:
                sector_id = get_or_create_sector(supabase, sector_cache, UNCLASSIFIED_SECTOR_NAME)
                supabase.table("assets").update({"sector_id": sector_id}).eq("asset_id", a["asset_id"]).execute()
                print(f"  [{i}/{len(assets)}] {ticker}: no sector data from Yahoo Finance -- put in Unclassified")
                failed.append(f"{ticker} (no sector data available)")
        except Exception as e:
            print(f"  [{i}/{len(assets)}] {ticker}: FAILED -- {e}")
            failed.append(f"{ticker} (save failed: {e})")

        time.sleep(0.3)

    if retry_mode:
        print(f"\nDone. {ok_count}/{len(assets)} previously-Unclassified stocks now have a real sector.")
        print(f"{len(failed)} still have no sector data from Yahoo Finance -- staying in Unclassified.")
    else:
        print(f"\nDone. {ok_count}/{len(assets)} stocks assigned a real Yahoo Finance sector.")
        print(f"{len(failed)} put in Unclassified or failed -- see list above.")
        print(
            "\nNext step (not done by this script): run "
            "20_backfill_new_stocks_price_history.py (already generic, no changes "
            "needed) to backfill 5 years of price history for these same new stocks."
        )


if __name__ == "__main__":
    main()
