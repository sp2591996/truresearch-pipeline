import json, os, urllib.parse, urllib.request
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")

def rest_get(table, params):
    query = urllib.parse.urlencode(params, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("URL:", url)
        print("ERROR BODY:", e.read().decode())
        raise

sectors = rest_get("sectors", {"select": "sector_id,name", "name": "eq.Construction"})
print("Construction sector row:", sectors)
if not sectors:
    raise SystemExit("not found")
sector_id = sectors[0]["sector_id"]

industries = rest_get("industries", {"select": "industry_id,name,sector_id", "sector_id": f"eq.{sector_id}"})
print(f"\nIndustries under sector_id={sector_id}:")
for i in industries:
    print(" ", i)

assets = rest_get("assets", {"select": "asset_id,ticker,name,industry_id", "sector_id": f"eq.{sector_id}", "asset_type": "eq.equity", "is_active": "eq.true"})
asset_ids = [a["asset_id"] for a in assets]
asset_by_id = {a["asset_id"]: a for a in assets}
print(f"\nTotal assets in sector_id={sector_id}: {len(assets)}")

all_ratios = []
chunk = 80
for i in range(0, len(asset_ids), chunk):
    ids = asset_ids[i:i+chunk]
    id_list = ",".join(str(x) for x in ids)
    rows = rest_get("ratios_snapshot", {
        "select": "asset_id,market_cap,as_of_date",
        "asset_id": f"in.({id_list})",
        "order": "as_of_date.desc",
    })
    all_ratios.extend(rows)

latest = {}
for r in all_ratios:
    aid = r["asset_id"]
    if aid not in latest:
        latest[aid] = r

industry_by_id = {i["industry_id"]: i["name"] for i in industries}
from collections import defaultdict
by_industry = defaultdict(list)
for a in assets:
    aid = a["asset_id"]
    mc = latest.get(aid, {}).get("market_cap")
    by_industry[industry_by_id.get(a["industry_id"], "?")].append((a["ticker"], a["name"], mc))

for ind, rows in sorted(by_industry.items(), key=lambda x: -len(x[1])):
    rows.sort(key=lambda r: -(r[2] or 0))
    total = sum(r[2] or 0 for r in rows)
    print(f"\n=== {ind} ({len(rows)} stocks, total mcap {total:,.0f}) ===")
    for ticker, name, mc in rows:
        mc_str = f"{mc:,.0f}" if mc else "NO DATA"
        print(f"  {ticker:15s} {(name or ''):40s} {mc_str}")
