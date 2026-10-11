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

rows = rest_get("value_chain_nodes", {"select": "*", "root_sector_id": "eq.2"})
print("value_chain_nodes rows for sector_id=2 (Capital Goods):", json.dumps(rows, indent=2))

sample = rest_get("value_chain_nodes", {"select": "*", "node_type": "eq.sector", "limit": "3"})
print("\nSample sector-level nodes from any sector:", json.dumps(sample, indent=2))
