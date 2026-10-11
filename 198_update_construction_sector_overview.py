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

# Construction sector (sector_id=4) has exactly 1 industry --
# Engineering & Construction (industry_id=19, 13 stocks) -- so this
# sector-level overview mirrors the industry-level segmentation
# (lib/industryBusinessSegments.ts, industry_id=19), per the standing
# rule to refresh the sector-level card whenever the sector's
# industries/stocks are built. Market caps as of 2026-10-11
# (197_scope_construction_sector.py). Total sector market cap:
# Rs 7,071,493,545,984.

business_segments = [
    {
        "name": "Diversified EPC Conglomerate",
        "market_cap_share_pct": 72.0,
        "top_companies": "Larsen & Toubro (72.0%)",
        "description": "L&T alone is nearly three-quarters of the entire sector's market cap -- a diversified infrastructure, hydrocarbon, defence and IT-services conglomerate whose order book and execution pace set the tone for how this whole sector is read.",
    },
    {
        "name": "Rail Infrastructure PSUs",
        "market_cap_share_pct": 8.4,
        "top_companies": "Rail Vikas Nigam / RVNL (5.6%), Ircon International (1.4%), RITES (1.4%)",
        "description": "Government-owned rail-project executors (RVNL, IRCON) and a rail-consultancy/leasing PSU (RITES), all levered to Indian Railways' capex cycle and dedicated freight-corridor and electrification rollouts.",
    },
    {
        "name": "Private EPC & Construction Contractors",
        "market_cap_share_pct": 8.5,
        "top_companies": "Kalpataru Projects International (3.4%), Cemindia Projects / formerly ITD Cementation (2.7%), Afcons Infrastructure (1.3%), NCC (1.1%)",
        "description": "Privately-run EPC contractors spanning power transmission, marine/ports, metro and general civil construction -- order-book and execution-driven businesses with margins more exposed to input-cost and project-delay risk than the PSU names above.",
    },
    {
        "name": "PSU Project Management & Consultancy",
        "market_cap_share_pct": 5.1,
        "top_companies": "NBCC India (2.8%), Engineers India (2.3%)",
        "description": "Government-owned project-management-consultancy and real-estate-development PSUs, earning fee/consultancy income on public infrastructure and PSU capex projects rather than taking on construction-contracting risk directly.",
    },
    {
        "name": "Infrastructure Developer (Toll Roads)",
        "market_cap_share_pct": 3.0,
        "top_companies": "IRB Infrastructure Developers (3.0%)",
        "description": "A BOT/toll-road asset owner-operator rather than a pure contractor -- its economics depend on traffic volumes and toll-collection rights on its road assets, not just on winning new construction orders.",
    },
    {
        "name": "Power T&D EPC",
        "market_cap_share_pct": 3.0,
        "top_companies": "KEC International (1.4%), Techno Electric & Engineering (1.6%)",
        "description": "Power transmission-and-distribution EPC specialists, riding India's grid-modernization and renewable-evacuation infrastructure buildout.",
    },
]

overview_text = "India's Construction sector is, in practice, a single industry -- Engineering & Construction -- and is extraordinarily top-heavy: Larsen & Toubro alone is ~72% of the sector's entire market cap, more than every other one of its 12 peers combined. The rest splits across rail-infrastructure PSUs (RVNL, IRCON, RITES), project-management PSUs (NBCC, Engineers India), private EPC/construction contractors (Kalpataru Projects, NCC, Afcons Infrastructure, Cemindia Projects) and smaller power-T&D EPC names (KEC International, Techno Electric)."

size_growth_notes = "Growth here tracks India's public infrastructure capex cycle directly -- Indian Railways' electrification and dedicated-freight-corridor rollout (RVNL, IRCON), National Highways Authority of India's road-award pipeline (L&T, IRB, KPIL, NCC, AFCONS), and grid transmission build-out (KEC, Techno Electric). L&T's own order-book growth and execution pace is, given its ~72% weight, the single biggest swing factor for the sector's reported numbers."

policy_notes = "Key policy drivers: NHAI's road-project ordering pace (benefits L&T, IRB, KPIL, NCC, AFCONS); Indian Railways' capex allocation and dedicated freight-corridor progress (benefits RVNL, IRCON, RITES); and the pace of PSU project-management mandates routed through NBCC and Engineers India. Government capex announcements in the Union Budget are the primary catalyst to watch for this sector as a whole."

strengths = "L&T (72.0% of the sector) is a diversified, well-capitalized conglomerate with exposure across infrastructure, hydrocarbons, defence and IT services -- a structurally different risk profile from a pure construction-contracting peer\nRVNL, IRCON and RITES (8.4% combined) sit on government-guaranteed rail-infrastructure demand tied to Indian Railways' multi-year electrification and dedicated-freight-corridor programmes\nIRB Infrastructure Developers (3.0%) earns toll-collection revenue on operating road assets, a different and generally more predictable cash-flow profile than pure EPC-contracting revenue"

weaknesses = "The sector's reported numbers are, in practice, mostly a read on L&T given its ~72% weight -- any slowdown in L&T's own order-book growth or execution pace would dominate the sector-level picture regardless of how its 12 smaller peers perform\nPrivate EPC contractors (KPIL, NCC, AFCONS, CEMPRO) carry order-book execution-delay and input-cost risk typical of construction-contracting businesses, with margins more exposed to commodity-price swings than the PSU names\nReliable, independently-confirmed recent financial figures were not available for at least one constituent (Cemindia Projects / formerly ITD Cementation) this research cycle -- flagged explicitly rather than estimated"

key_risks = "A slowdown in L&T's own order inflow or execution pace would disproportionately hit this sector's combined numbers, given its ~72% weight -- a risk concentration unusual even by Indian-market standards\nAny pullback in NHAI's road-award pace or Indian Railways' capex allocation (in the Union Budget or mid-year revisions) would directly hit the EPC contractors and rail PSUs that depend on that order flow\nWorking-capital and execution-delay risk, typical of EPC/construction-contracting businesses, could weigh on reported revenue recognition for the private contractors (KPIL, NCC, AFCONS, CEMPRO) if project timelines slip"

why_invest = "L&T (72.0% of the sector) offers diversified exposure across infrastructure, hydrocarbons, defence and IT services inside a single name, with an order book that is a widely-tracked proxy for India's overall capex cycle\nRVNL, IRCON and RITES offer direct, government-guaranteed exposure to Indian Railways' multi-year electrification and dedicated-freight-corridor capex programme -- a named, trackable catalyst rather than a generic infrastructure theme\nIRB Infrastructure Developers' toll-road model gives exposure to India's road-infrastructure buildout with a different, generally steadier cash-flow profile than pure EPC-contracting revenue"

why_not_invest = "This sector's combined numbers are overwhelmingly a read on one company (L&T, ~72% weight) -- investors wanting diversified construction-sector exposure should look closely at how much of any sector-level statistic is really just L&T\nPrivate EPC contractors (KPIL, NCC, AFCONS, CEMPRO) carry the execution-delay and working-capital risk typical of construction-contracting businesses, with margins more exposed to input-cost swings than diversified industrial names\nAt least one constituent (Cemindia Projects) lacked independently-confirmed recent financial figures this research cycle -- verify company-level numbers against official filings before relying on sector-level summaries"

key_things_to_watch = "L&T's own quarterly order-inflow and execution commentary, given its ~72% weight on this sector's combined numbers\nNHAI's road-project award pace and Indian Railways' capex allocation in the Union Budget, the key policy catalysts for the EPC contractors and rail PSUs here\nResolution, in official company filings, of this cycle's flagged data gaps (Cemindia Projects' recent financials) and figure discrepancies (Engineers India's Q1 FY27 PAT, NCC's order-book size) noted in the stock-level Deep Dive content"

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

result = rest_patch("sector_overviews", {"sector_id": "eq.4"}, payload)
print("UPDATE RESULT:")
print(json.dumps(result, indent=2))
