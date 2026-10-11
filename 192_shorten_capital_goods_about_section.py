import json, os, urllib.parse, urllib.request
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")

def rest_patch(table, params, body):
    query = urllib.parse.urlencode(params, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("URL:", url)
        print("ERROR BODY:", e.read().decode())
        raise

body = {
    "overview_text": "India's Capital Goods sector spans defence & aerospace, electrical equipment, specialty industrial machinery, solar manufacturing and diversified conglomerates. It's top-heavy: HAL (~10.5%) and BEL (~9.1%) alone are near a fifth of the sector's market cap, with BHEL, ABB India, Hitachi Energy, CG Power, Cummins India, Siemens and Polycab next (4-5% each).",
    "size_growth_notes": "Growth right now rides on three parallel, dated programmes rather than one cycle: India's ~8 GW FY27 wind-capacity target, a revived NTPC thermal-power ordering cycle, and the Ministry of Defence's latest indigenisation mandate -- each benefiting a different set of companies.",
    "policy_notes": "Key policy drivers: the 6th Positive Indigenisation List (405 items, ~Rs 3,070 crore, Aug 2026) locks in demand for HAL and BEL; SECI's Tranche XXI wind tender (1,200 MW, Oct 2026) benefits Suzlon and Inox Wind; BHEL's Rs 13,500 crore NTPC Telangana order (2026) reflects the thermal-power revival; and the ~Rs 23,000 crore electronics PLI scheme benefits Kaynes Technologies and Syrma SGS.",
}

result = rest_patch("sector_overviews", {"sector_id": "eq.2"}, body)
print("UPDATE RESULT:")
print(json.dumps(result, indent=2, ensure_ascii=False))
