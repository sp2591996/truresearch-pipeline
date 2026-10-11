"""
check_capital_goods_industries.py
-------------------------------------------------------------------
READ-ONLY check script. Lists every industry currently under the
"Capital Goods" sector, with its stock count and the tickers in it --
so ESCORTS and ACE can be moved into the most genuinely fitting
existing industry (not a guessed name), per Avdhoot's request to keep
them within Capital Goods while moving them out of "Farm & Heavy
Construction Machinery" (which would otherwise drop to 0 stocks).

Uses the same urllib-only approach as check_automotive_classification.py
and 173_reclassify_ashokley_to_automotive.py (no `supabase` package,
since its `cryptography` dependency is blocked by this machine's
Application Control policy).

Run manually from the TrueResearch Code folder:
    python check_capital_goods_industries.py
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
    sector = rest_get("sectors", {"select": "sector_id", "name": f"eq.{SECTOR_NAME}"})
    if not sector:
        raise RuntimeError(f"Sector '{SECTOR_NAME}' not found")
    sector_id = sector[0]["sector_id"]

    industries = rest_get("industries", {
        "select": "industry_id,name",
        "sector_id": f"eq.{sector_id}",
        "market": f"eq.{MARKET}",
        "order": "name",
    })

    print(f"Industries under '{SECTOR_NAME}' sector (sector_id={sector_id}):\n")
    for ind in industries:
        assets = rest_get("assets", {
            "select": "ticker,name",
            "industry_id": f"eq.{ind['industry_id']}",
            "market": f"eq.{MARKET}",
            "asset_type": "eq.equity",
            "order": "ticker",
        })
        tickers = ", ".join(a["ticker"] for a in assets) if assets else "(no stocks)"
        print(f"  [{ind['industry_id']}] {ind['name']} -- {len(assets)} stock(s): {tickers}")


if __name__ == "__main__":
    main()
