"""
25_shareholding_refresh.py
-------------------------------------------------------------------
Session 11, part 3: fills in the `shareholding_pattern` table, which
has existed (with public read access, since Session 10 part 11) but
had zero rows for every stock -- no ingestion script existed until
now (Session 10 part 10/11 correctly flagged this as a missing data
source, not just a missing permission).

Data source decision (see PROJECT_STATE.md Session 11 for the full
discussion): NSE's own quarterly shareholding-pattern filings, which
every listed company must submit in a standardised XBRL format (SEBI
LODR Regulation 31). Unlike the Mutual Fund holdings problem, this is
genuinely free AND structured (XML, not scanned PDFs) -- same class
of "free, just needs a script" data source as prices/fundamentals.

What it does, per active equity:
  1. Uses the `nse` PyPI package (unofficial NSE API wrapper -- handles
     the cookie/session dance NSE's site requires) to fetch the list of
     this stock's quarterly shareholding filings, each with a link to
     its XBRL document.
  2. Downloads and parses the last few quarters' XBRL files directly
     (plain HTTPS GET -- no session needed for the static XBRL files
     themselves, only for the filing-list API call).
  3. Extracts 4 category percentages every SEBI shareholding filing
     reports under standard tag names: Promoter, DII ("Institutions
     Domestic"), FII ("Institutions Foreign"), and Public.
  4. Upserts one row per (asset_id, quarter_end_date) into
     `shareholding_pattern` -- exactly the shape
     components/ShareholdingChart.tsx on the frontend already expects
     (promoter_pct / fii_pct / dii_pct / public_pct, 0-100 scale).

Like every other ingestion script here: one stock failing (missing
filing, network hiccup, unexpected XBRL layout) never stops the run --
it's recorded in failed_symbols and everything else keeps going.

Setup (one-time):
    venv\\Scripts\\python.exe -m pip install nse

Run manually:
    venv\\Scripts\\python.exe 25_shareholding_refresh.py
    venv\\Scripts\\python.exe 25_shareholding_refresh.py --quarters 8   (default 4)
-------------------------------------------------------------------
"""
import re
import sys
import time
import argparse
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from db_client import get_client
from ingestion_log import start_run, finish_run

# The 4 categories Wireframes.md / ShareholdingChart.tsx expect, mapped
# to the standard SEBI XBRL contextRef IDs that identify them inside
# every company's filing (confirmed against a real filing before writing
# this script -- these are the same tag names for every company, since
# the format is SEBI-mandated, not company-specific).
#
# IMPORTANT (Session 11 part 5 fix): in SEBI's shareholding format,
# "Public Shareholding" (PublicShareholding_ContextI) is the TOTAL of
# every non-promoter shareholder -- DII and FII are sub-categories
# INSIDE that total, not separate from it. Storing that raw total
# directly as `public_pct` alongside separate dii_pct/fii_pct values
# double-counts institutional holders and made Promoter+DII+FII+Public
# sum to well over 100% (caught by Avdhoot testing the chart). The raw
# tag is now labelled "_total" and `public_pct` is computed as that
# total minus DII and FII, giving 4 genuinely mutually-exclusive
# categories that sum to ~100%.
#
# Session 11 part 12 fix: NSE revised this XBRL schema (this file now
# references schema version "2025-10") to add "Employee Benefit
# Trusts" as its OWN top-level category, separate from and NOT included
# inside PublicShareholding_ContextI's total (confirmed against real
# filings for SWIGGY/FIRSTCRY/THERMAX -- each has a nonzero employee-
# trust holding, and Promoter% + PublicShareholding% + EmployeeTrust%
# sums to ~100% on its own). Before this fix, that slice (5-7% for
# those 3 stocks) was silently missing from every category, so
# promoter+dii+fii+public landed a few % short of 100% and tripped the
# sum-sanity-check below -- rejecting every quarter for any stock with
# a nonzero employee-trust holding. Rather than add a 5th DB column/
# chart segment for what's usually a small, non-controlling holding,
# it's folded into `public_pct` below (the honest bucket for "not
# promoter-controlled, not a tracked institution").
CONTEXT_TO_COLUMN = {
    "ShareholdingOfPromoterAndPromoterGroup_ContextI": "promoter_pct",
    "InstitutionsDomestic_ContextI": "dii_pct",
    "InstitutionsForeign_ContextI": "fii_pct",
    "PublicShareholding_ContextI": "public_pct_total",  # raw total, corrected below
    "EmployeeBenefitsTrusts_ContextI": "employee_trust_pct_raw",  # folded into public below, never stored as its own column
}
PCT_TAG_LOCALNAME = "ShareholdingAsAPercentageOfTotalNumberOfShares"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def local_tag(tag: str) -> str:
    """Strips the XML namespace off a tag, e.g. '{http://...}Foo' -> 'Foo'."""
    return tag.rsplit("}", 1)[-1]


def parse_shareholding_xbrl(xml_bytes: bytes) -> dict:
    """Given one filing's raw XBRL bytes, returns
    {'promoter_pct': .., 'dii_pct': .., 'fii_pct': .., 'public_pct': ..}
    (values already converted to a 0-100 scale). Missing categories are
    left out of the dict rather than guessed.

    Session 11 part 5, second fix: NSE's filings are NOT perfectly
    consistent in how this percentage element encodes its value --
    most filings store it as a fraction (0.4387 = 43.87%), but at least
    one real filing was found storing it as an already-scaled percentage
    (50.80 meaning 50.80%, not 5080%). Multiplying that by 100 as if it
    were always a fraction produced the "5080.0%" nonsense Avdhoot
    caught. A shareholding percentage can never legitimately exceed
    100, so: treat any raw value > 1 as already being a percentage
    (don't re-multiply), and as a hard safety net, drop -- not clamp,
    not guess -- any value that's still outside 0-100 after that. A
    missing/dropped data point is honest; a fabricated one isn't."""
    root = ET.fromstring(xml_bytes)
    result = {}
    for el in root.iter():
        if local_tag(el.tag) != PCT_TAG_LOCALNAME:
            continue
        context_ref = el.attrib.get("contextRef", "")
        column = CONTEXT_TO_COLUMN.get(context_ref)
        if column is None or el.text is None:
            continue
        try:
            raw = float(el.text.strip())
        except ValueError:
            continue
        # A real shareholding fraction is always <= 1 (100%). If the
        # filing already reported it as a percentage (e.g. 50.80), raw
        # will be > 1 -- use it as-is instead of multiplying by 100.
        pct = raw if raw > 1 else raw * 100
        if not (0 <= pct <= 100):
            continue  # unparseable/garbage value -- skip, don't fabricate
        # Only keep the first occurrence per category (a filing can
        # legitimately repeat a context in footnote sections).
        result.setdefault(column, round(pct, 2))

    # Correct the raw "Public" total into a mutually-exclusive retail
    # figure -- see the CONTEXT_TO_COLUMN comment above for why. Only
    # do this if we actually found a total to correct; a filing missing
    # this tag entirely should stay missing, not become a fabricated 0.
    if "public_pct_total" in result:
        dii = result.get("dii_pct", 0)
        fii = result.get("fii_pct", 0)
        # Employee Benefit Trusts are reported as their OWN top-level
        # category by NSE (confirmed: NOT included inside
        # PublicShareholding_ContextI's total) -- folded in here rather
        # than given a 5th DB column/chart segment, since it's usually
        # small and isn't promoter-controlled or a tracked institution
        # either. `pop` (not `get`) so this temp key never leaks into
        # the row that gets saved to the database.
        employee_trust = result.pop("employee_trust_pct_raw", 0)
        public = result.pop("public_pct_total") - dii - fii + employee_trust
        # Final sanity net: if the corrected public share is still
        # outside a believable range, something upstream was wrong for
        # this filing -- drop it rather than save a suspicious number.
        if 0 <= public <= 100:
            result["public_pct"] = round(public, 2)
    else:
        # No public total tag at all -- still discard the raw employee-
        # trust value rather than accidentally saving it under a column
        # name (`employee_trust_pct_raw`) the database doesn't have.
        result.pop("employee_trust_pct_raw", None)

    return result


def fetch_quarterly_filings(nse, symbol: str, max_quarters: int) -> list:
    """Returns up to `max_quarters` filing records
    [{'date': 'YYYY-MM-DD', 'xbrl': url}, ...], newest first, as
    reported by NSE's own filing-list API for this symbol."""
    records = nse.shareholding(symbol)
    out = []
    for r in records[:max_quarters]:
        xbrl_url = r.get("xbrl")
        date_str = r.get("date")
        if not xbrl_url or not date_str:
            continue
        out.append({"date": date_str, "xbrl": xbrl_url})
    return out


def normalise_date(date_str: str) -> str:
    """NSE's filing-list date field has shown up in a couple of formats
    across different endpoints; this handles both 'YYYY-MM-DD' and
    'DD-Mon-YYYY' defensively rather than assuming one."""
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarters", type=int, default=4, help="How many recent quarters to fetch per stock (default 4).")
    args = parser.parse_args()

    try:
        from nse import NSE
    except ImportError:
        print("ERROR: the 'nse' package isn't installed. Run:")
        print("  venv\\Scripts\\python.exe -m pip install nse")
        sys.exit(1)

    supabase = get_client()
    assets_res = (
        supabase.table("assets")
        .select("asset_id, ticker")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .execute()
    )
    assets = assets_res.data
    print(f"Fetching shareholding pattern for {len(assets)} equities (last {args.quarters} quarters each)...\n")

    run_id = start_run("shareholding_refresh")
    ok_count = 0
    quarters_saved = 0
    failed_symbols = []

    with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
        for i, a in enumerate(assets, 1):
            asset_id = a["asset_id"]
            ticker = a["ticker"]
            print(f"[{i}/{len(assets)}] {ticker} ...", end=" ")

            try:
                filings = fetch_quarterly_filings(nse, ticker, args.quarters)
            except Exception as e:
                print(f"skipped (couldn't fetch filing list: {e})")
                failed_symbols.append(ticker)
                continue

            if not filings:
                print("skipped (no filings found)")
                failed_symbols.append(ticker)
                continue

            saved_this_stock = 0
            for filing in filings:
                try:
                    resp = requests.get(filing["xbrl"], headers=REQUEST_HEADERS, timeout=20)
                    resp.raise_for_status()
                    categories = parse_shareholding_xbrl(resp.content)
                except Exception:
                    continue  # one bad quarter shouldn't sink the whole stock

                if not categories:
                    continue

                # Last line of defence: even if every individual category
                # passed its own 0-100 check, they should still sum to
                # roughly 100% together. A wider gap means something
                # about this specific filing didn't parse the way this
                # script expects -- better to skip the quarter than save
                # numbers nobody should trust.
                total = sum(categories.values())
                if not (95 <= total <= 105):
                    continue

                supabase.table("shareholding_pattern").upsert({
                    "asset_id": asset_id,
                    "quarter_end_date": normalise_date(filing["date"]),
                    **categories,
                }, on_conflict="asset_id,quarter_end_date").execute()
                saved_this_stock += 1
                time.sleep(0.2)  # be polite to NSE's static file host

            if saved_this_stock:
                ok_count += 1
                quarters_saved += saved_this_stock
                print(f"saved {saved_this_stock} quarter(s)")
            else:
                failed_symbols.append(ticker)
                print("skipped (no quarter parsed successfully)")

    finish_run(run_id, ok_count, failed_symbols)
    print(f"\nDone. {ok_count}/{len(assets)} stocks got at least one quarter saved "
          f"({quarters_saved} quarter-rows total). Failed: {failed_symbols if failed_symbols else 'none'}")


if __name__ == "__main__":
    main()
