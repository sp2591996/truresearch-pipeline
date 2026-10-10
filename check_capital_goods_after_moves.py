"""
check_capital_goods_after_moves.py
-------------------------------------------------------------------
READ-ONLY verification. Confirms, directly from the database, that:
  1) Capital Goods sector's total stock count correctly excludes
     ASHOKLEY (moved to Automobile and Auto Components / Auto
     Manufacturers via 173_reclassify_ashokley_to_automotive.py).
  2) ESCORTS and ACE are now correctly tagged under "Specialty
     Industrial Machinery" (industry_id 15) within Capital Goods.
  3) "Farm & Heavy Construction Machinery" (industry_id 54) now
     has 0 stocks.

Run manually from the TrueResearch Code folder:
    python check_capital_goods_after_moves.py
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


def rest_get(table: str, params: dict):
    query = urllib.parse.urlencode(params, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    sector = rest_get("sectors", {"select": "sector_id", "name": "eq.Capital Goods"})
    sid = sector[0]["sector_id"]

    assets = rest_get("assets", {
        "select": "ticker,industry_id",
        "sector_id": f"eq.{sid}",
        "market": f"eq.{MARKET}",
        "asset_type": "eq.equity",
    })
    print(f"Capital Goods (sector_id={sid}) total stocks right now: {len(assets)}")

    ashokley_here = [a for a in assets if a["ticker"] == "ASHOKLEY"]
    print(f"  ASHOKLEY still in Capital Goods? {'YES -- PROBLEM' if ashokley_here else 'No (correctly moved out)'}")

    ind15 = sorted(a["ticker"] for a in assets if a["industry_id"] == 15)
    ind54 = sorted(a["ticker"] for a in assets if a["industry_id"] == 54)
    print(f"\n  Specialty Industrial Machinery (industry_id=15): {len(ind15)} stocks -> {ind15}")
    print(f"  Farm & Heavy Construction Machinery (industry_id=54): {len(ind54)} stocks -> {ind54}")

    # Also directly confirm ASHOKLEY's current home
    ashokley = rest_get("assets", {
        "select": "ticker,sector_id,industry_id",
        "ticker": "eq.ASHOKLEY",
        "market": f"eq.{MARKET}",
        "asset_type": "eq.equity",
    })
    if ashokley:
        a = ashokley[0]
        sec = rest_get("sectors", {"select": "name", "sector_id": f"eq.{a['sector_id']}"})
        ind = rest_get("industries", {"select": "name", "industry_id": f"eq.{a['industry_id']}"})
        print(f"\n  ASHOKLEY is currently in: {sec[0]['name']} / {ind[0]['name']}")


if __name__ == "__main__":
    main()
