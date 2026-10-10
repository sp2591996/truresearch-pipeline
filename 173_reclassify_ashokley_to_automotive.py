"""
173_reclassify_ashokley_to_automotive.py
-------------------------------------------------------------------
ASHOKLEY (Ashok Leyland) was tagged "Capital Goods" / "Farm & Heavy
Construction Machinery" -- a screener-classification quirk caught
while building that industry's Deep Dive: Ashok Leyland is
fundamentally a commercial-vehicle (truck & bus) manufacturer, not a
farm- or construction-equipment business, and was explicitly flagged
`isPoorFit: true` in the Deep Dive content rather than being force-
fit into that industry's schema. This moves it to where it actually
belongs: "Automobile and Auto Components" / "Auto Manufacturers" --
the same sector+industry M&M, MARUTI, EICHERMOT, BAJAJ-AUTO and
HEROMOTOCO already sit under (confirmed live via
check_automotive_classification.py on 2026-10-10).

Same mechanism as 163_reclassify_bank_industries.py: a row in
sector_industry_ticker_overrides (so no future automated sync
silently reverts this) plus a direct update to ASHOKLEY's own
`assets` row, marked sector_source='manual'.

Unlike 163 (and every other numbered script in this project), this
one does NOT import the `supabase` package via db_client.py -- on
this machine, that package pulls in a native `cryptography` library
whose DLL this computer's Application Control / security policy
blocks. Instead, this talks to the same Supabase database directly
over plain HTTPS (Supabase's REST API, "PostgREST"), using only
Python's built-in `urllib` -- nothing extra for the security policy
to object to. Same database, same .env credentials, same effect.

Run manually from the TrueResearch Code folder:
    python 173_reclassify_ashokley_to_automotive.py
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
TICKER = "ASHOKLEY"
CORRECTED_SECTOR_NAME = "Automobile and Auto Components"
CORRECTED_INDUSTRY_NAME = "Auto Manufacturers"
NOTE = ("Ashok Leyland is fundamentally a commercial-vehicle (truck & bus) OEM, not a "
        "farm- or construction-equipment business -- its prior 'Farm & Heavy Construction "
        "Machinery' tag was a screener-classification quirk, caught and explicitly flagged "
        "isPoorFit:true while building that industry's Deep Dive (2026-10-10). Moved to the "
        "same Automobile and Auto Components / Auto Manufacturers grouping as M&M, MARUTI, "
        "EICHERMOT, BAJAJ-AUTO and HEROMOTOCO.")


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
    print(f"Looking up '{CORRECTED_SECTOR_NAME}' sector...")
    sector = rest_get("sectors", {"select": "sector_id", "name": f"eq.{CORRECTED_SECTOR_NAME}"})
    if not sector:
        raise RuntimeError(f"Sector '{CORRECTED_SECTOR_NAME}' not found -- aborting, nothing changed.")
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

    print(f"Looking up {TICKER}'s asset row...")
    asset = rest_get("assets", {
        "select": "asset_id,ticker,sector_id,industry_id",
        "ticker": f"eq.{TICKER}",
        "market": f"eq.{MARKET}",
        "asset_type": "eq.equity",
        "limit": "1",
    })
    if not asset:
        raise RuntimeError(f"{TICKER} not found in assets table -- aborting, nothing changed.")
    asset_id = asset[0]["asset_id"]
    print(f"  asset_id = {asset_id} (currently sector_id={asset[0]['sector_id']}, industry_id={asset[0]['industry_id']})")

    print(f"\nUpserting override row into sector_industry_ticker_overrides...")
    rest_upsert("sector_industry_ticker_overrides", [{
        "ticker": TICKER, "market": MARKET,
        "corrected_sector_name": CORRECTED_SECTOR_NAME,
        "corrected_industry_name": CORRECTED_INDUSTRY_NAME,
        "is_diversified": False,
        "note": NOTE,
    }], on_conflict="ticker,market")
    print("  done.")

    print(f"\nUpdating {TICKER}'s asset row (sector_id={sector_id}, industry_id={industry_id}, sector_source='manual')...")
    updated = rest_patch("assets", {"asset_id": f"eq.{asset_id}"}, {
        "sector_id": sector_id,
        "industry_id": industry_id,
        "sector_source": "manual",
    })
    print(f"  done: {updated}")

    print(f"\n{TICKER} reclassified: Capital Goods / Farm & Heavy Construction Machinery "
          f"-> {CORRECTED_SECTOR_NAME} / {CORRECTED_INDUSTRY_NAME}, marked sector_source='manual' "
          f"so a future automated sync won't silently revert this.")


if __name__ == "__main__":
    main()
