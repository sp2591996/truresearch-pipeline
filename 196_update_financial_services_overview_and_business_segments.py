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

business_segments = [
    {
        "name": "Banks",
        "market_cap_share_pct": 51.1,
        "top_companies": "HDFC Bank (10.6%), ICICI Bank (9.5%), State Bank of India (8.6%), Kotak Mahindra Bank (4.3%), Axis Bank (3.8%)",
        "description": "Private and public-sector banks combined -- just over half the sector's market cap. The RBI held the repo rate at 5.25% at its February 2026 MPC meeting with a neutral stance, projecting FY26 GDP growth of 7.4% and inflation of 2.1%, a backdrop that keeps net interest margins broadly stable for now.",
    },
    {
        "name": "Credit Services (NBFCs)",
        "market_cap_share_pct": 19.9,
        "top_companies": "Bajaj Finance (5.8%), Shriram Finance (2.2%), Cholamandalam Investment & Finance (1.3%), Tata Capital (1.3%)",
        "description": "Non-bank lenders across consumer, vehicle and SME finance. The RBI relaxed risk-weight rules for NBFC infrastructure loans in January 2026, easing capital-provisioning pressure after its earlier 2023-24 tightening cycle on unsecured consumer credit.",
    },
    {
        "name": "Insurance (Life & General)",
        "market_cap_share_pct": 8.9,
        "top_companies": "LIC (2.4%), SBI Life (1.7%), HDFC Life (1.2%), ICICI Lombard General Insurance (0.8%)",
        "description": "The Insurance Laws (Amendment) Bill -- raising the FDI cap from 74% to 100% and introducing composite licences letting one insurer sell life, health and general policies -- was planned for introduction in Parliament's winter 2025 session; if passed, it would be the biggest insurance-sector overhaul in years.",
    },
    {
        "name": "Asset Management",
        "market_cap_share_pct": 5.9,
        "top_companies": "ICICI Prudential AMC (1.5%), Jio Financial Services (1.4%), HDFC AMC (1.0%)",
        "description": "Mutual-fund AMCs and wealth managers benefiting from India's rising retail-investor participation and SIP flows, plus Jio Financial Services' diversified NBFC-and-AMC push backed by Reliance and BlackRock.",
    },
    {
        "name": "Diversified Financials",
        "market_cap_share_pct": 5.2,
        "top_companies": "Bajaj Finserv (2.7%), Bajaj Holdings & Investment (1.2%), Aditya Birla Capital (1.0%)",
        "description": "Multi-business financial conglomerates and investment holding companies spanning lending, insurance and asset management under one listed entity.",
    },
    {
        "name": "Financial Data & Stock Exchanges",
        "market_cap_share_pct": 4.0,
        "top_companies": "BSE (1.3%), One 97 Communications / Paytm (1.0%)",
        "description": "Exchanges, ratings/research and payments-data platforms. BSE's equity-derivatives volumes and Paytm's merchant-payments scale are both sensitive to SEBI's periodic F&O-market regulatory tightening, a recurring swing factor for this segment's revenue.",
    },
    {
        "name": "Capital Markets",
        "market_cap_share_pct": 3.1,
        "top_companies": "Billionbrains Garage Ventures / Groww (1.2%), Motilal Oswal Financial Services (0.6%)",
        "description": "Broking, wealth management and discount-broking fintechs. Groww's November 2025 IPO was subscribed roughly 17.6-18x, the clearest recent signal of investor appetite for India's discount-broking growth story.",
    },
    {
        "name": "Mortgage Finance",
        "market_cap_share_pct": 2.0,
        "top_companies": "Bajaj Housing Finance (0.7%), LIC Housing Finance (0.3%)",
        "description": "Housing financiers, the sector's smallest segment by market cap, levered to India's home-loan demand and the RBI's repo-rate trajectory.",
    },
]

payload = {
    "overview_text": "India's Financial Services sector is bank-dominated: private and public-sector banks together are just over half its market cap, led by HDFC Bank (10.6%), ICICI Bank (9.5%) and SBI (8.6%). Credit Services/NBFCs (19.9%, led by Bajaj Finance at 5.8%) are the second-largest segment, followed by insurance, asset management, diversified financials, exchanges/data, capital markets and mortgage finance.",
    "size_growth_notes": "Growth rides on the RBI holding rates steady (5.25% repo rate, neutral stance, Feb 2026 MPC) against 7.4% projected FY26 GDP growth, alongside two pending structural shifts: the Insurance Amendment Bill's proposed 100% FDI cap and composite licences, and NBFCs' eased infrastructure-loan risk weights (Jan 2026) after the RBI's earlier unsecured-credit tightening.",
    "policy_notes": "Key policy drivers: the RBI's Feb 2026 MPC held the repo rate at 5.25% (neutral stance); the Insurance Laws (Amendment) Bill proposes raising FDI in insurance from 74% to 100% and introducing composite licences (planned for Parliament's winter 2025 session); and the RBI relaxed NBFC infrastructure-loan risk-weight rules in January 2026, easing capital pressure built up by its 2023-24 unsecured-credit tightening cycle.",
    "strengths": "Banks (just over half the sector's market cap) operate under a stable rate backdrop -- the RBI held the repo rate at 5.25% at its February 2026 MPC meeting with a neutral stance and projected 7.4% FY26 GDP growth, supporting broadly stable net interest margins\nNBFCs (19.9% of the sector, led by Bajaj Finance at 5.8%) got capital-provisioning relief when the RBI relaxed infrastructure-loan risk-weight rules in January 2026, partly reversing its 2023-24 unsecured-credit tightening\nGroww's (Billionbrains Garage Ventures) November 2025 IPO was subscribed roughly 17.6-18x, a concrete, dated signal of strong investor appetite for India's discount-broking and capital-markets growth story\nThe proposed Insurance Amendment Bill's composite-licence provision would let a single insurer sell life, health and general policies together, a structural cost and cross-sell advantage for LIC, SBI Life and HDFC Life if it passes",
    "weaknesses": "Banks and NBFCs together are over 70% of the sector, so a single RBI policy shift (on rates or risk weights) moves most of the sector's market cap at once rather than being diversified across unrelated businesses\nThe Insurance Amendment Bill's 100% FDI and composite-licence provisions were still pending introduction in Parliament as of the sector's last research cycle -- the sector's insurance names (8.9% of the market cap) are priced partly on a bill that has not yet passed\nExchanges and payments platforms (BSE, Paytm, 4.0% of the sector) remain exposed to SEBI's recurring F&O-market regulatory tightening, which has repeatedly hit derivatives-trading volumes in past cycles",
    "key_risks": "If the RBI shifts away from its current neutral stance -- for instance tightening rates again -- bank net interest margins and NBFC funding costs (over 70% of the sector combined) would be hit simultaneously, not just one segment\nIf the Insurance Amendment Bill (100% FDI, composite licences) stalls or is diluted in Parliament, insurance names (LIC, SBI Life, HDFC Life, ICICI Lombard) lose a thesis that's partly priced in already\nA renewed SEBI crackdown on F&O/derivatives trading, as seen in prior cycles, would directly hit exchange and payments-platform volumes (BSE, Paytm)\nNBFCs' January 2026 risk-weight relief could be partly or fully reversed if asset quality in unsecured consumer credit deteriorates again, repeating the RBI's 2023-24 tightening response",
    "why_invest": "Banks and NBFCs (over 70% of the sector combined) are currently operating under a supportive, stable-rate, growth-positive backdrop: 5.25% repo rate, neutral RBI stance, 7.4% projected FY26 GDP growth, and NBFC-specific risk-weight relief from January 2026\nGroww's November 2025 IPO, subscribed ~17.6-18x, is concrete evidence of strong investor demand for India's capital-markets and discount-broking growth theme\nThe pending Insurance Amendment Bill (100% FDI, composite licences) offers a dated, trackable catalyst for the sector's insurance names if and when it passes",
    "why_not_invest": "Banks and NBFCs' combined 70%+ weight means the sector's fortunes are closely tied to RBI rate and risk-weight decisions rather than diversified end-markets\nThe insurance-sector catalyst (the Amendment Bill) was still pending as of this research cycle -- a real risk that passage slips or its provisions get diluted\nExchanges and payments platforms carry recurring regulatory-tightening risk from SEBI's F&O-market rules, a pattern that has repeated across past cycles",
    "key_things_to_watch": "Whether the RBI holds its neutral stance and 5.25% repo rate through the rest of FY26, or shifts as inflation moves toward its projected 4.0-4.2% range in Q1-Q2 FY27\nWhether the Insurance Laws (Amendment) Bill -- 100% FDI, composite licences -- is actually introduced and passed in Parliament\nAny further RBI risk-weight changes for NBFC lending (after the January 2026 infrastructure-loan relief) as a signal of the regulator's view on sector asset quality\nSEBI's ongoing stance on F&O/derivatives-market regulation and its impact on exchange and payments-platform trading volumes",
    "business_segments": business_segments,
}

result = rest_patch("sector_overviews", {"sector_id": "eq.9"}, payload)
print(json.dumps(result, indent=2))
