"""
175_reclassify_building_products_equipment_stocks.py
-------------------------------------------------------------------
Dissolves "Building Products & Equipment" (industry_id 56, Capital
Goods sector) -- it had only 3 stocks (SUPREMEIND, ASTRAL, CPPLUS),
and CPPLUS (Aditya Infotech Ltd., the CP Plus CCTV/video-surveillance
brand) was a genuine poor fit there: a security-electronics company,
not a building-materials/construction-equipment business. Once it
moves out, the remaining 2 stocks would be below the Deep Dive
rollup's 3-stock floor, so per Avdhoot's explicit instruction
(2026-10-10) all 3 move to genuinely-fitting existing industries,
confirmed live via check_all_industries_for_bpe_move.py:

  - CPPLUS (Aditya Infotech / CP Plus, CCTV & video surveillance
    hardware) -> Consumer Electronics (industry_id 65, Consumer
    Durables sector, sector_id 6) -- joins DIXON, HAVELLS, LGEINDIA,
    PGEL, all consumer/commercial electronics hardware makers. A much
    closer match than anything in Capital Goods.
  - SUPREMEIND (Supreme Industries -- plastic piping systems) and
    ASTRAL (Astral -- pipes, adhesives, building materials) ->
    Building Materials (industry_id 5, Construction Materials sector,
    sector_id 5) -- joins ACC, AMBUJACEM, DALBHARAT, GRASIM, etc.
    Not a perfect match (those are cement makers, these are pipes/
    adhesives), but it is the closest genuine "building materials"
    bucket that already exists on the site, and a better fit than
    Capital Goods' generic industrial-machinery catch-all.

"Building Products & Equipment" (industry_id 56) is left in place
with 0 stocks, same as "Farm & Heavy Construction Machinery" --
not deleted, just stops appearing anywhere stock counts are shown.

Same mechanism as 163/173/174: upsert a row per ticker into
sector_industry_ticker_overrides, then PATCH each ticker's own
`assets` row, marked sector_source='manual'. Plain urllib (no
`supabase` package) -- see 173's header comment for why.

Run manually from the TrueResearch Code folder:
    python 175_reclassify_building_products_equipment_stocks.py
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

# Each entry: ticker -> (target sector name, target industry name, note)
MOVES = {
    "CPPLUS": (
        "Consumer Durables",
        "Consumer Electronics",
        "Aditya Infotech Ltd. (CP Plus brand) makes CCTV/video-surveillance "
        "hardware -- a consumer/commercial electronics business, not a "
        "building-materials or construction-equipment company. Moved out of "
        "'Building Products & Equipment' (Capital Goods), which it never "
        "genuinely fit, into Consumer Electronics alongside DIXON, HAVELLS, "
        "LGEINDIA, PGEL.",
    ),
    "SUPREMEIND": (
        "Construction Materials",
        "Building Materials",
        "Supreme Industries makes plastic piping systems for construction/"
        "plumbing. Moved from 'Building Products & Equipment' (Capital "
        "Goods, dissolved after CPPLUS -- a poor fit -- moved out, leaving "
        "only 2 stocks) to the existing Building Materials industry -- the "
        "closest genuine building-materials bucket on the site, even though "
        "its current members (ACC, AMBUJACEM, etc.) are cement makers.",
    ),
    "ASTRAL": (
        "Construction Materials",
        "Building Materials",
        "Astral makes pipes, fittings and adhesives for construction. Same "
        "move as SUPREMEIND, for the same reason.",
    ),
}


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
    # Cache sector_id / industry_id lookups so we don't re-query per ticker
    resolved = {}

    for ticker, (sector_name, industry_name, note) in MOVES.items():
        key = (sector_name, industry_name)
        if key not in resolved:
            sector = rest_get("sectors", {"select": "sector_id", "name": f"eq.{sector_name}"})
            if not sector:
                raise RuntimeError(f"Sector '{sector_name}' not found -- aborting, nothing changed for {ticker}.")
            sector_id = sector[0]["sector_id"]

            industry = rest_get("industries", {
                "select": "industry_id",
                "name": f"eq.{industry_name}",
                "sector_id": f"eq.{sector_id}",
                "market": f"eq.{MARKET}",
            })
            if not industry:
                raise RuntimeError(f"Industry '{industry_name}' not found under '{sector_name}' -- aborting, nothing changed for {ticker}.")
            industry_id = industry[0]["industry_id"]
            resolved[key] = (sector_id, industry_id)
            print(f"Resolved '{sector_name}' / '{industry_name}' -> sector_id={sector_id}, industry_id={industry_id}")

        sector_id, industry_id = resolved[key]

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
            "corrected_sector_name": sector_name,
            "corrected_industry_name": industry_name,
            "is_diversified": False,
            "note": note,
        }], on_conflict="ticker,market")

        print(f"  Updating {ticker}'s asset row (sector_id={sector_id}, industry_id={industry_id}, sector_source='manual')...")
        rest_patch("assets", {"asset_id": f"eq.{asset_id}"}, {
            "sector_id": sector_id,
            "industry_id": industry_id,
            "sector_source": "manual",
        })
        print(f"  {ticker}: -> {sector_name} / {industry_name}")

    print("\nDone. CPPLUS -> Consumer Durables / Consumer Electronics. "
          "SUPREMEIND and ASTRAL -> Construction Materials / Building Materials. "
          "'Building Products & Equipment' (industry_id 56, Capital Goods) is left "
          "in place with 0 stocks -- not deleted.")


if __name__ == "__main__":
    main()
