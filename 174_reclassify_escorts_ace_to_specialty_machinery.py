"""
174_reclassify_escorts_ace_to_specialty_machinery.py
-------------------------------------------------------------------
Follow-up to 173_reclassify_ashokley_to_automotive.py: once ASHOKLEY
was moved out of "Farm & Heavy Construction Machinery" (it was a
genuine misfit -- a commercial-vehicle OEM, not farm/construction
equipment), that industry was left with only 2 stocks (ESCORTS, ACE)
-- below the 3-stock floor this site's industry Deep Dive rollup
needs to show its richer per-company view. Per Avdhoot's explicit
instruction (2026-10-10), ESCORTS and ACE move to the existing
"Specialty Industrial Machinery" industry (industry_id 15, confirmed
live via check_capital_goods_industries.py) -- the general industrial/
equipment-manufacturer catch-all already used for ABB, BHEL,
CUMMINSIND, KIRLOSBROS, KSB, TIMKEN and others, and the closest
genuine fit among this sector's existing industries for a tractor
maker (ESCORTS) and a crane/construction-equipment maker (ACE).

This stays within the Capital Goods sector -- only industry_id
changes, not sector_id. "Farm & Heavy Construction Machinery"
(industry_id 54) is left in place with 0 stocks rather than deleted,
since deleting sector/industry rows isn't something this script
should do unprompted; it will simply stop appearing anywhere
stock counts are shown.

Same mechanism as 163/173: a row per ticker in
sector_industry_ticker_overrides, plus a direct update to each
ticker's own `assets` row, marked sector_source='manual'. Uses plain
urllib (no `supabase` package) for the same reason as 173 -- see that
script's header comment.

Run manually from the TrueResearch Code folder:
    python 174_reclassify_escorts_ace_to_specialty_machinery.py
-------------------------------------------------------------------
"""
import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY not found in .env")

MARKET = "india"
SECTOR_NAME = "Capital Goods"
CORRECTED_INDUSTRY_NAME = "Specialty Industrial Machinery"

TICKERS = [
    ("ESCORTS", "Tractor & farm/construction-equipment manufacturer -- grouped with this sector's other "
                "diversified industrial-equipment makers after 'Farm & Heavy Construction Machinery' (its "
                "prior tag) dropped to 2 stocks following ASHOKLEY's reclassification out of it."),
    ("ACE", "Cranes, material-handling & construction-equipment manufacturer -- same move as ESCORTS, for "
            "the same reason."),
]


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def rest_get(table: str, params: dict):
    query = urllib.parse.urlencode(params, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rest_upsert(table: str, rows: list, on_conflict: str):
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = _headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    data = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rest_patch(table: str, match: dict, updates: dict):
    query = urllib.parse.urlencode(match, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    headers = _headers()
    headers["Prefer"] = "return=representation"
    data = json.dumps(updates).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print(f"Looking up '{SECTOR_NAME}' sector...")
    sector = rest_get("sectors", {"select": "sector_id", "name": f"eq.{SECTOR_NAME}"})
    if not sector:
        raise RuntimeError(f"Sector '{SECTOR_NAME}' not found -- aborting, nothing changed.")
    sector_id = sector[0]["sector_id"]
    print(f"  sector_id = {sector_id}")

    print(f"Looking up '{CORRECTED_INDUSTRY_NAME}' industry under that sector...")
    industry = rest_get("industries", {
        "select": "industry_id",
        "name": f"eq.{CORRECTED_INDUSTRY_NAME}",
        "sector_id": f"eq.{sector_id}",
        "market": f"eq.{MARKET}",
    })
    if not industry:
        raise RuntimeError(f"Industry '{CORRECTED_INDUSTRY_NAME}' not found under that sector -- aborting, nothing changed.")
    industry_id = industry[0]["industry_id"]
    print(f"  industry_id = {industry_id}")

    for ticker, note in TICKERS:
        print(f"\nLooking up {ticker}'s asset row...")
        asset = rest_get("assets", {
            "select": "asset_id,ticker,sector_id,industry_id",
            "ticker": f"eq.{ticker}",
            "market": f"eq.{MARKET}",
            "asset_type": "eq.equity",
            "limit": "1",
        })
        if not asset:
            print(f"  {ticker}: NOT FOUND in assets table -- skipped")
            continue
        asset_id = asset[0]["asset_id"]
        print(f"  asset_id = {asset_id} (currently sector_id={asset[0]['sector_id']}, industry_id={asset[0]['industry_id']})")

        print(f"  Upserting override row into sector_industry_ticker_overrides...")
        rest_upsert("sector_industry_ticker_overrides", [{
            "ticker": ticker, "market": MARKET,
            "corrected_sector_name": SECTOR_NAME,
            "corrected_industry_name": CORRECTED_INDUSTRY_NAME,
            "is_diversified": False,
            "note": note,
        }], on_conflict="ticker,market")

        print(f"  Updating {ticker}'s asset row (sector_id={sector_id}, industry_id={industry_id}, sector_source='manual')...")
        rest_patch("assets", {"asset_id": f"eq.{asset_id}"}, {
            "sector_id": sector_id,
            "industry_id": industry_id,
            "sector_source": "manual",
        })
        print(f"  {ticker}: -> {SECTOR_NAME} / {CORRECTED_INDUSTRY_NAME}")

    print(f"\nDone. ESCORTS and ACE reclassified to {SECTOR_NAME} / {CORRECTED_INDUSTRY_NAME}, "
          f"marked sector_source='manual'. 'Farm & Heavy Construction Machinery' (industry_id 54) "
          f"is left in place with 0 stocks -- not deleted -- and will simply stop appearing "
          f"anywhere stock counts are shown.")


if __name__ == "__main__":
    main()
