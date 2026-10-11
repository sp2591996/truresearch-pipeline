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

INDUSTRIES = {
    22: "Electrical Equipment & Parts",
    28: "Aerospace & Defense",
    48: "Conglomerates",
    54: "Farm & Heavy Construction Machinery",
    79: "Solar",
}

for industry_id, label in INDUSTRIES.items():
    print(f"\n{'='*70}\n{industry_id} = {label}\n{'='*70}")
    assets = rest_get("assets", {"select": "asset_id,ticker,name,industry_id", "industry_id": f"eq.{industry_id}", "asset_type": "eq.equity", "is_active": "eq.true"})
    asset_ids = [a["asset_id"] for a in assets]
    asset_by_id = {a["asset_id"]: a for a in assets}
    print(f"Total assets: {len(assets)}")
    if not asset_ids:
        continue

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

    rows_with_mc = []
    for aid, r in latest.items():
        mc = r.get("market_cap")
        if mc is None:
            continue
        a = asset_by_id.get(aid, {})
        rows_with_mc.append((a.get("ticker"), a.get("name"), mc))

    total_mc = sum(x[2] for x in rows_with_mc)
    rows_with_mc.sort(key=lambda x: -x[2])
    print(f"Stocks with market cap data: {len(rows_with_mc)} / {len(assets)}")
    if total_mc > 0:
        print(f"Total industry market cap: {total_mc:,.0f}\n")
        for ticker, name, mc in rows_with_mc:
            print(f"{ticker:15s} {(name or ''):40s} {mc:>18,.0f}  {mc/total_mc*100:5.2f}%")
    missing = set(a["ticker"] for a in assets) - set(x[0] for x in rows_with_mc)
    print(f"Missing market cap data: {sorted(missing)}")
