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

business_segments = [
    {
        "name": "Specialty Industrial Machinery",
        "market_cap_share_pct": 35.6,
        "top_companies": "BHEL (~5.1%), ABB India (~4.9%), Cummins India (~4.5%), Siemens Ltd (~4.3%), GE Vernova T&D (~3.6%), Suzlon Energy (~1.8%)",
        "description": "The sector's largest segment by market cap: power/electrical majors, thermal-power EPC (BHEL), engines and compressors (Cummins India, Kirloskar Oil Engines), wind equipment (Suzlon, Inox Wind), aerospace-precision castings (PTC Industries), grinding media (AIA Engineering) and a long tail of pumps, bearings and railway-wagon makers. Demand runs on several independent capex cycles at once -- grid modernization, thermal EPC, wind tendering and railway expansion -- rather than one theme.",
    },
    {
        "name": "Aerospace & Defense",
        "market_cap_share_pct": 28.2,
        "top_companies": "Hindustan Aeronautics / HAL (~10.5%), Bharat Electronics / BEL (~9.1%), Mazagon Dock Shipbuilders (~2.7%), Bharat Dynamics (~1.3%), Cochin Shipyard (~1.1%)",
        "description": "Dominated by two government-owned majors, HAL and BEL, which together account for close to a fifth of the whole Capital Goods sector's market cap on their own. Manufactures fighter aircraft, radar/electronics, warships, submarines and defence-grade precision components. Demand is driven almost entirely by Ministry of Defence procurement and import-substitution mandates (such as the Positive Indigenisation Lists) rather than private industrial capex.",
    },
    {
        "name": "Electrical Equipment & Parts",
        "market_cap_share_pct": 25.5,
        "top_companies": "Hitachi Energy India (~4.6%), CG Power and Industrial Solutions (~4.6%), Polycab India (~4.2%), Apar Industries (~2.5%), KEI Industries (~1.5%)",
        "description": "Cables and wires (Polycab, KEI Industries, RR Kabel, Finolex Cables), transformers and power equipment (Hitachi Energy India, CG Power, Apar Industries, Schneider Electric Infrastructure), and electronics manufacturing services/industrial automation (Honeywell Automation, Kaynes Technologies, Syrma SGS). Demand tracks grid build-out and housing/construction wiring, with the EMS names specifically also benefiting from the roughly Rs 23,000 crore PLI scheme for electronic components.",
    },
    {
        "name": "Solar Equipment Manufacturing",
        "market_cap_share_pct": 8.1,
        "top_companies": "Waaree Energies (~2.3%), Premier Energies (~1.4%), EMMVEE Photovoltaic (~0.7%)",
        "description": "Manufactures solar modules and cells, benefiting from India's renewable capacity-addition targets and PLI-linked domestic cell/module manufacturing incentives. Global panel pricing -- heavily influenced by Chinese manufacturing oversupply -- remains a real swing factor for this segment's margins, even as domestic policy support stays strong.",
    },
    {
        "name": "Conglomerates",
        "market_cap_share_pct": 2.5,
        "top_companies": "Thermax (~1.2%), Carborundum Universal (~0.8%), BEML (~0.5%)",
        "description": "The smallest segment by market cap, but genuinely diversified: Thermax spans industrial boilers and heating equipment, Carborundum Universal spans abrasives and ceramics, and BEML spans earthmoving equipment, defence and rail products. Because each is a multi-business manufacturer rather than a single-product company, their fortunes are harder to tie to any one capex theme than the rest of the sector.",
    },
]

result = rest_patch("sector_overviews", {"sector_id": "eq.2"}, {"business_segments": business_segments})
print("UPDATE RESULT:")
print(json.dumps(result, indent=2, ensure_ascii=False))
