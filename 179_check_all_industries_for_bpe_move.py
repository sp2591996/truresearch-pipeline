"""
check_all_industries_for_bpe_move.py
-------------------------------------------------------------------
READ-ONLY check script. "Building Products & Equipment" (SUPREMEIND,
ASTRAL, CPPLUS/Aditya Infotech) is about to be dissolved -- CPPLUS
(CCTV/surveillance electronics) is a genuine poor fit there, and once
it leaves, only 2 stocks (SUPREMEIND, ASTRAL -- both pipe/building-
materials makers) would remain, below the 3-stock Deep Dive rollup
floor. So all 3 stocks need a new, genuinely-fitting home -- possibly
in DIFFERENT industries/sectors from each other (SUPREMEIND/ASTRAL
are building-materials/pipe makers; CPPLUS is security electronics --
no reason to assume they share a destination).

Lists every industry across EVERY sector (not just Capital Goods),
with stock counts and tickers, so the best real fit can be picked
from what actually exists -- never guessed.

Run manually from the TrueResearch Code folder:
    python check_all_industries_for_bpe_move.py
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
    sectors = rest_get("sectors", {"select": "sector_id,name", "order": "name"})

    for sec in sectors:
        industries = rest_get("industries", {
            "select": "industry_id,name",
            "sector_id": f"eq.{sec['sector_id']}",
            "market": f"eq.{MARKET}",
            "order": "name",
        })
        if not industries:
            continue
        print(f"\n=== {sec['name']} (sector_id={sec['sector_id']}) ===")
        for ind in industries:
            assets = rest_get("assets", {
                "select": "ticker",
                "industry_id": f"eq.{ind['industry_id']}",
                "market": f"eq.{MARKET}",
                "asset_type": "eq.equity",
                "order": "ticker",
            })
            tickers = ", ".join(a["ticker"] for a in assets) if assets else "(no stocks)"
            print(f"  [{ind['industry_id']}] {ind['name']} -- {len(assets)}: {tickers}")

    # Also print SUPREMEIND / ASTRAL / CPPLUS's own current tag for reference
    print("\n=== Stocks being moved (current tag) ===")
    for ticker in ["SUPREMEIND", "ASTRAL", "CPPLUS"]:
        a = rest_get("assets", {
            "select": "ticker,name,sector_id,industry_id",
            "ticker": f"eq.{ticker}",
            "market": f"eq.{MARKET}",
            "asset_type": "eq.equity",
        })
        if a:
            print(f"  {a[0]['ticker']} ({a[0]['name']}): sector_id={a[0]['sector_id']}, industry_id={a[0]['industry_id']}")
        else:
            print(f"  {ticker}: NOT FOUND")


if __name__ == "__main__":
    main()
