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
    "overview_text": "India's Capital Goods sector spans diversified industrial conglomerates, electrical equipment (cables, transformers, switchgear and industrial automation) and specialty industrial machinery (pumps, engines, construction/farm equipment, wind turbines, railway wagons, aerospace & defence precision components, and niche materials like grinding media, refractories and graphite electrodes). Revenue is driven by a mix of government and private capex, replacement/aftermarket demand, and, for several sub-segments, structural multi-year tailwinds rather than a single capex cycle.",
    "size_growth_notes": "Growth across the sector is currently being driven by several concurrent, largely independent capex themes rather than one cycle: data-centre and power-reliability-linked demand for diesel/gas gensets; grid-modernization and renewable-integration spending on transformers and switchgear; a renewed cycle of government wind-capacity tendering; railway rolling-stock and track-equipment expansion; a resumption of large thermal (coal) power EPC ordering; and a build-out of defence and aerospace precision-component manufacturing tied to import substitution. Because these themes run on different timelines, the sector's overall growth tends to be more diversified than a single capex-cycle read would suggest, even though individual sub-segments remain cyclical on their own.",
    "policy_notes": "Government policy is a meaningful demand driver across multiple sub-segments: renewed coal-based power capacity awards benefit thermal EPC players; India's wind-energy tendering push benefits turbine makers; defence indigenization and import-substitution policy supports the aerospace & defence precision-component segment; and large government-funded water-infrastructure and railway-modernization programmes support pump and wagon/bearing makers respectively. Partnerships with global technology majors (for example Kubota's majority stake in Escorts, now Escorts Kubota) are also a recurring theme, bringing in foreign technology and distribution access alongside policy-linked domestic demand.",
    "strengths": "Multiple independent structural demand drivers (data-centre power reliability, grid modernization, wind-capacity tendering, railway expansion, defence indigenization) reduce reliance on any single capex cycle\nSeveral niche sub-segments (grinding media, cryogenic equipment, titanium/superalloy precision casting) have global-scale, moat-like positioning rather than commodity competition\nMNC-parented players bring technology access and brand trust alongside domestic manufacturing scale\nInstalled equipment bases across cables, pumps, bearings and turbines support recurring aftermarket and services revenue",
    "weaknesses": "Orders remain lumpy and project-driven, especially for large PSU EPC and defence/aerospace qualification-based contracts\nRaw-material cost exposure (copper, aluminium, magnesite, needle coke) can compress margins independent of demand strength\nWorking-capital intensity is high for large government-linked EPC contracts\nSeveral companies' own quarterly disclosures this research cycle contained unreconciled figures (growth-rate claims, EPS-PAT divergences, or profit figures that didn't tie to their own stated components), underscoring the need to verify headline numbers against official filings rather than relying on summarized figures alone",
    "key_risks": "A slowdown in government infrastructure, defence or railway capex could affect order inflows across several sub-segments simultaneously\nCommodity and raw-material price volatility (copper/aluminium for cables, needle coke for graphite electrodes, magnesite for refractories) can erode margins even when volumes hold up\nExecution delays and working-capital stress on large legacy PSU EPC contracts remain a recurring risk for thermal-power equipment makers\nGlobal cyclicality (mining capex, EAF steel utilization, global wind-tendering) affects the sector's more export-oriented and niche-materials players\nReporting inconsistencies surfaced in multiple companies' recent quarterly disclosures (growth-rate mismatches, unreconciled profit figures) warrant direct verification against official filings before relying on headline numbers",
    "why_invest": "The sector offers exposure to several concurrent, policy-supported capex themes -- grid modernization, renewed wind tendering, railway expansion, defence indigenization and data-centre-driven power-reliability demand -- rather than dependence on a single cycle\nA number of sub-segments (grinding media, cryogenic equipment, precision titanium casting) have genuinely moat-like, globally-scaled positioning rather than being pure commodity plays\nMNC-parented and PSU majors alike are benefiting from renewed domestic capex momentum, offering a mix of technology-led and scale-led investment angles",
    "why_not_invest": "Capex-driven order books can swing sharply when government or private investment cycles turn, and lumpy project timing can make quarterly results volatile\nRaw-material cost volatility and working-capital intensity on large contracts can compress margins independent of underlying demand strength\nSeveral companies' own disclosures this research cycle showed real, unresolved inconsistencies in reported figures, meaning sector-level analysis needs company-by-company verification rather than relying on headline growth or profit numbers alone",
    "key_things_to_watch": "Pace of government capex execution across railways, defence, grid-modernization and thermal-power EPC awards\nRaw-material cost trends (copper, aluminium, needle coke, magnesite) and their pass-through to margins\nMargin-recovery trajectory at large-cap names following recent input-cost pressure\nResolution of flagged reporting discrepancies (growth-rate and profit-reconciliation gaps) against official company filings in upcoming quarters",
}

result = rest_patch("sector_overviews", {"sector_id": "eq.2"}, body)
print("UPDATE RESULT:")
print(json.dumps(result, indent=2, ensure_ascii=False))
