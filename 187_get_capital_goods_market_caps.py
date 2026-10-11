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

# All active equity assets in Capital Goods sector (sector_id=2)
assets = rest_get("assets", {"select": "asset_id,ticker,name,industry_id", "sector_id": "eq.2", "asset_type": "eq.equity", "is_active": "eq.true"})
asset_ids = [a["asset_id"] for a in assets]
asset_by_id = {a["asset_id"]: a for a in assets}

# Fetch market caps in chunks (URL length safety), most recent snapshot per asset
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

# Keep only the most recent snapshot per asset_id
latest = {}
for r in all_ratios:
    aid = r["asset_id"]
    if aid not in latest or r["as_of_date"] > latest[aid]["as_of_date"]:
        latest[aid] = r

rows_out = []
total_cap = 0.0
for aid, r in latest.items():
    cap = r.get("market_cap")
    if cap is None:
        continue
    a = asset_by_id.get(aid, {})
    rows_out.append({"ticker": a.get("ticker"), "name": a.get("name"), "industry_id": a.get("industry_id"), "market_cap": cap})
    total_cap += cap

rows_out.sort(key=lambda x: x["market_cap"], reverse=True)

print(f"Total Capital Goods sector stocks found: {len(assets)}; with market cap data: {len(rows_out)}")
print(f"Sector total market cap (sum of available): {total_cap:,.0f}\n")
print(f"{'Ticker':<14}{'Industry':<10}{'Market Cap':>18}{'% of sector':>14}")
for r in rows_out:
    pct = (r["market_cap"] / total_cap * 100) if total_cap > 0 else 0
    print(f"{r['ticker']:<14}{str(r['industry_id']):<10}{r['market_cap']:>18,.0f}{pct:>13.2f}%")
