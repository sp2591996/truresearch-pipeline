import json, os, urllib.parse, urllib.request
from dotenv import load_dotenv
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")

def rest_patch(table, params, payload):
    query = urllib.parse.urlencode(params, safe=",.&=")
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}?{query}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("URL:", url)
        print("ERROR BODY:", e.read().decode())
        raise

# Construction Materials sector (sector_id=5) has exactly 1 industry --
# Building Materials (industry_id=5, 13 stocks) -- so this sector-level
# overview mirrors the industry-level segmentation
# (lib/industryBusinessSegments.ts, industry_id=5). Market caps as of
# 2026-10-11 (199_scope_construction_materials_sector.py). Total sector
# market cap: Rs 9,074,551,209,984.

business_segments = [
    {
        "name": "Large-Cap Cement Majors",
        "market_cap_share_pct": 74.7,
        "top_companies": "UltraTech Cement (34.6%), Grasim Industries (21.6%), Ambuja Cements (9.6%), Shree Cement (8.8%)",
        "description": "The four largest names, together nearly three-quarters of the sector -- UltraTech is India's largest cement producer (Aditya Birla Group), Grasim is its majority owner plus a diversified holding company (VSF, chemicals, lending, paints), and Ambuja Cements/Shree Cement are the next-largest pure cement majors (Adani Group and an independent long-time cost leader respectively).",
    },
    {
        "name": "Plastic Pipes, Packaging & Adhesives (Poor Fit)",
        "market_cap_share_pct": 9.0,
        "top_companies": "Supreme Industries (4.9%), Astral (4.2%)",
        "description": "NOT cement companies -- Supreme Industries makes plastic piping, packaging and industrial products, and Astral makes PVC pipes, adhesives and paints. Both are grouped in this sector on the live screener (likely because pipes are a construction input) but should be read on their own terms, not as a cement-cycle signal.",
    },
    {
        "name": "Mid-Cap Cement Names",
        "market_cap_share_pct": 9.6,
        "top_companies": "J.K. Cement (4.2%), Dalmia Bharat (3.3%), ACC (2.3%)",
        "description": "Mid-sized cement makers -- J.K. Cement adds a differentiated, higher-margin white-cement/wall-putty business; Dalmia Bharat has been actively acquiring capacity (completing the Jaiprakash Associates cement-assets acquisition this quarter); ACC is the second Adani Group cement name alongside Ambuja.",
    },
    {
        "name": "Smaller / Regional Cement Names",
        "market_cap_share_pct": 6.7,
        "top_companies": "Ramco Cements (2.1%), JSW Cement (1.7%), India Cements (1.5%), Nuvoco Vistas (1.3%)",
        "description": "Smaller and more regionally-concentrated cement makers -- Ramco Cements and India Cements are South India-focused, JSW Cement is in an active capacity/geographic expansion phase (including a North India launch), and Nuvoco Vistas (Nirma Group) recently commissioned a new plant in Surat.",
    },
]

overview_text = "India's Construction Materials sector is, in practice, a single industry -- Building Materials -- led by the two Aditya Birla Group names, UltraTech Cement (34.6%) and Grasim Industries (21.6%), together over half the sector. Ambuja Cements and ACC (Adani Group) and Shree Cement round out the large-cap cement names. Two constituents, Supreme Industries and Astral, are NOT cement companies -- they make plastic pipes, packaging and adhesives -- a poor-fit tagging worth keeping in mind when reading this sector's combined numbers."

size_growth_notes = "Growth here tracks India's cement demand cycle -- construction, housing and infrastructure capex -- directly. This quarter (Q1 FY27) showed a genuinely mixed picture: UltraTech, Grasim, Astral, JSW Cement and Nuvoco Vistas all grew revenue and generally held or improved margins, while Ambuja Cements, Shree Cement, JK Cement, Dalmia Bharat, ACC and Ramco Cements all saw YoY profit declines despite revenue growth at several of them -- pointing to a broad, cost-driven (likely fuel/power/freight) margin-pressure quarter across much of the industry, not a demand problem."

policy_notes = "Key drivers are less policy-specific than for some other sectors and more about input-cost cycles (coal, pet coke, power, freight) and capacity-expansion programmes -- Ambuja Cements is targeting 119 MTPA capacity by FY27-end, Dalmia Bharat completed the Jaiprakash Associates cement-assets acquisition this quarter, and JSW Cement is expanding into North India. India's broader construction and housing capex cycle remains the primary demand driver for the 11 genuine cement names in this sector."

strengths = "UltraTech Cement (34.6% of the sector) combines India's largest cement capacity with renewable energy and waste-heat-recovery assets, a cost advantage smaller peers can't easily replicate\nGrasim Industries (21.6%) offers diversified exposure beyond cement alone -- VSF, chemicals, financial services and a paints growth option (Birla Opus) -- reducing single-cycle dependence\nAstral and Nuvoco Vistas both reported genuinely strong, broad-based quarters (revenue, margin and profit all growing) this period, standouts against a sector where several cement majors saw profit declines"

weaknesses = "A majority of the sector's pure cement names (Ambuja, Shree Cement, JK Cement, Dalmia Bharat, ACC, Ramco Cements) reported YoY profit declines this quarter despite revenue growth at several -- a broad, cost-driven margin-pressure pattern worth tracking into the next quarter\nTwo of the sector's 13 constituents (Supreme Industries, Astral) aren't cement companies at all, so any sector-wide average or trend should be read with that mix in mind\nRamco Cements posted the steepest margin compression (500 bps) in the sector this quarter, with India Cements' profitability turnaround confirmed for only one quarter so far -- both carry real near-term uncertainty"

key_risks = "A continuation of this quarter's broad cost-driven (fuel/power/freight) margin pressure would hit the large majority of the sector's pure cement names, not just one or two\nAmbuja Cements' and ACC's shared weak quarter (both Adani Group) raises the question of whether a group-level or regional issue is at play that could persist\nDalmia Bharat's and Ambuja's and JSW Cement's active capacity-expansion programmes all carry near-term integration/ramp-up execution risk that could keep weighing on reported margins for a few more quarters"

why_invest = "UltraTech Cement and Grasim Industries together offer diversified, large-scale exposure to India's cement cycle (directly and via Grasim's broader conglomerate structure) with industry-leading cost advantages\nAstral's and Nuvoco Vistas' genuinely strong, broad-based quarters this period show that not every name in the sector is struggling with the cost pressure affecting the larger cement majors\nSeveral names (Ambuja, Dalmia Bharat, JSW Cement) have concrete, dated capacity-expansion catalysts that could support renewed growth once near-term integration costs normalise"

why_not_invest = "A majority of the sector's pure cement names saw profit declines this quarter on what looks like a broad, cost-driven margin-pressure pattern -- worth confirming this reverses before assuming the worst is over\nTwo of the 13 constituents (Supreme Industries, Astral) aren't cement companies, so sector-level averages can be misleading without accounting for that mix\nSmaller, more regionally-concentrated names (Ramco Cements, India Cements) carry more concentrated risk than the diversified, pan-India majors"

key_things_to_watch = "Whether the broad, cost-driven margin pressure seen across most cement majors this quarter (fuel, power, freight costs) eases in the next 1-2 quarters\nCapacity-expansion progress at Ambuja Cements (119 MTPA target), Dalmia Bharat (Jaiprakash Associates integration) and JSW Cement (North India launch)\nWhether Astral's and Nuvoco Vistas' strong, broad-based quarters prove sustainable, and whether India Cements' profitability turnaround extends beyond a single quarter"

payload = {
    "overview_text": overview_text,
    "size_growth_notes": size_growth_notes,
    "policy_notes": policy_notes,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "key_risks": key_risks,
    "why_invest": why_invest,
    "why_not_invest": why_not_invest,
    "key_things_to_watch": key_things_to_watch,
    "business_segments": business_segments,
}

result = rest_patch("sector_overviews", {"sector_id": "eq.5"}, payload)
print("UPDATE RESULT:")
print(json.dumps(result, indent=2))
