"""
value_chain_data/consumer_services.py
-------------------------------------------------------------------
All researched Value Chain data for the Consumer Services sector
(India), organized by industry. This is a living data file -- Claude
adds a new INDUSTRIES entry (or appends companies to an existing one)
as each industry gets researched, and Avdhoot re-runs the ONE shared
runner script (run_value_chain_seed.py) each time, instead of a new
numbered script per company. Keeps the TrueResearch Code folder from
filling up with one-off scripts.

Each company entry is one REVENUE-BEARING LEAF node (a brand, segment,
or the whole company if it only has one disclosed business line) --
flat, directly under its industry. (Earlier version of this nested a
company "wrapper" node with brand children underneath -- that broke
the Index calculation, which only weights node_type="company" leaves.
Flat is correct; see 163_fix_trent_node_structure.py for the one-off
fix of the original mistake.)

Fields per company entry:
  slug, name, ticker        -- identity; ticker looked up against `assets`
  revenue                   -- Rs Cr, for the period below
  past_cagr, next_growth    -- % growth, past and Claude/sourced projection
  source                    -- "sourced" (from a real filing/press release/
                                investor presentation) or "claude_estimate"
                                (Claude's own bottom-up/top-down guess,
                                always flagged as such in `notes` too)
  notes                     -- citation + methodology, always present
  pct (optional)            -- override for revenue_pct_of_company_total;
                                if omitted, the runner auto-computes it as
                                this entry's revenue / the sum of every
                                entry sharing the same ticker (i.e. "what
                                share of THIS company's total revenue is
                                sitting at this node")

PERIOD / AS_OF below apply to every entry currently in this file (all
FY2025 data so far) -- bump these if a later entry uses a different
period.
-------------------------------------------------------------------
"""

PERIOD = "FY2025"
AS_OF = "2025-03-31"

INDUSTRIES = [
    {
        "slug": "apparel-fashion-retail",
        "name": "Apparel & Fashion Retail",
        "display_order": 2,
        "companies": [
            {
                "slug": "trent-westside", "name": "Trent — Westside", "ticker": "TRENT",
                "revenue": 8624, "past_cagr": 18.0, "next_growth": 16.0, "source": "claude_estimate",
                "notes": "Residual of Trent's disclosed Rs 17,624 Cr Fashion Portfolio total (FY25 press release) after subtracting the Zudio estimate. Claude estimate -- not an exact disclosed split.",
            },
            {
                "slug": "trent-zudio", "name": "Trent — Zudio", "ticker": "TRENT",
                "revenue": 9000, "past_cagr": 55.0, "next_growth": 35.0, "source": "claude_estimate",
                "notes": "Press release says Zudio 'exceeded a billion dollars' in FY25 (~Rs 8,550 Cr+ at ~85.5 INR/USD); Rs 9,000 Cr is Claude's point estimate within that floor.",
            },
            {
                "slug": "abfrl-post-demerger", "name": "ABFRL (Pantaloons & other businesses)", "ticker": "ABFRL",
                "revenue": 7355, "past_cagr": 14.0, "next_growth": 13.0, "source": "sourced", "pct": 1.0,
                "notes": "FY25 revenue Rs 7,355 Cr, +14% YoY -- official post-demerger Q4 FY25 results press release. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "ablbl-lifestyle-brands", "name": "ABLBL (Louis Philippe, Van Heusen, Allen Solly, Peter England)", "ticker": "ABLBL",
                "revenue": 7619, "past_cagr": 1.0, "next_growth": 6.0, "source": "sourced", "pct": 1.0,
                "notes": "FY25 revenue Rs 7,619 Cr, +1% YoY -- official post-demerger Q4 FY25 results press release. Brand-level split not disclosed and deliberately not estimated (too wide a margin of error for a 4-way guess). Next-3yr is a Claude estimate.",
            },
        ],
    },
    {
        "slug": "internet-retail",
        "name": "Internet Retail",
        "display_order": 3,
        "companies": [
            {
                "slug": "nykaa-beauty", "name": "Nykaa — Beauty", "ticker": "NYKAA",
                "revenue": 7251, "past_cagr": 25.0, "next_growth": 20.0, "source": "sourced",
                "notes": "FY25 revenue Rs 7,251 Cr, +25% YoY -- official Q4/FY25 investor presentation. Includes BPC e-commerce, stores, House of Nykaa owned brands, eB2B. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "nykaa-fashion", "name": "Nykaa — Fashion", "ticker": "NYKAA",
                "revenue": 675, "past_cagr": 19.0, "next_growth": 22.0, "source": "sourced",
                "notes": "FY25 revenue Rs 675 Cr, +19% YoY -- official Q4/FY25 investor presentation. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "firstcry-india", "name": "FirstCry — India Multi-Channel", "ticker": "FIRSTCRY",
                "revenue": 5278.5, "past_cagr": 15.0, "next_growth": 13.0, "source": "sourced",
                "notes": "FY25 revenue Rs 5,278.5 Cr, +15% YoY -- official Q4 FY25 investor presentation. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "firstcry-international", "name": "FirstCry — International (UAE/KSA)", "ticker": "FIRSTCRY",
                "revenue": 858.6, "past_cagr": 14.0, "next_growth": 18.0, "source": "sourced",
                "notes": "FY25 revenue Rs 858.6 Cr, +14% YoY -- official Q4 FY25 investor presentation. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "firstcry-globalbees", "name": "FirstCry — Globalbees (D2C brands)", "ticker": "FIRSTCRY",
                "revenue": 1577.7, "past_cagr": 30.0, "next_growth": 22.0, "source": "sourced",
                "notes": "FY25 revenue Rs 1,577.7 Cr, +30% YoY -- official Q4 FY25 investor presentation. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "firstcry-others", "name": "FirstCry — Others (preschool partnerships)", "ticker": "FIRSTCRY",
                "revenue": 42.5, "past_cagr": 27.0, "next_growth": 20.0, "source": "sourced",
                "notes": "FY25 revenue Rs 42.5 Cr, +27% YoY -- official Q4 FY25 investor presentation (363 preschools, 18,470 students). Next-3yr is a rough Claude estimate.",
            },
            {
                "slug": "indiamart-marketplace", "name": "IndiaMART — B2B Marketplace", "ticker": "INDIAMART",
                "revenue": 1320.1, "past_cagr": 16.0, "next_growth": 14.0, "source": "sourced",
                "notes": "FY25 revenue Rs 1,320.1 Cr, +16% YoY -- official Annual Report FY2024-25. 217K paying suppliers. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "indiamart-busy-infotech", "name": "IndiaMART — Busy Infotech (accounting software)", "ticker": "INDIAMART",
                "revenue": 65.8, "past_cagr": 22.0, "next_growth": 20.0, "source": "sourced",
                "notes": "FY25 revenue Rs 65.8 Cr, +22% YoY -- official Annual Report FY2024-25. 396K cumulative licenses. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "meesho", "name": "Meesho", "ticker": "MEESHO",
                "revenue": 9389.9, "past_cagr": 28.0, "next_growth": 20.0, "source": "sourced", "pct": 1.0,
                "notes": "FY25 revenue Rs 9,389.9 Cr, +23.3% YoY -- HDFC Securities IPO note, Dec 2025. 'Past 3yr' is actually disclosed 2yr (FY23-25) CAGR ~28% (no true 3yr figure available). No stream-level breakdown disclosed. Next-3yr is a Claude estimate.",
            },
            {
                "slug": "urbancompany-india", "name": "Urban Company — India Consumer Services", "ticker": "URBANCO",
                "revenue": 881.4, "past_cagr": 24.2, "next_growth": 22.0, "source": "sourced",
                "notes": "FY25 revenue Rs 881.4 Cr, +24.2% YoY -- core marketplace (beauty, wellness, repair). Next-3yr is a Claude estimate.",
            },
            {
                "slug": "urbancompany-native", "name": "Urban Company — Native (own-brand products)", "ticker": "URBANCO",
                "revenue": 116.0, "past_cagr": 303.3, "next_growth": 60.0, "source": "sourced",
                "notes": "FY25 revenue Rs 116 Cr, +303.3% YoY -- water purifiers, electronic locks. Extreme growth off small base; next-3yr Claude estimate assumes sharp deceleration.",
            },
            {
                "slug": "urbancompany-international", "name": "Urban Company — International (Saudi/UAE/Singapore)", "ticker": "URBANCO",
                "revenue": 147.0, "past_cagr": 63.9, "next_growth": 40.0, "source": "sourced",
                "notes": "FY25 revenue Rs 147 Cr, +63.9% YoY. Saudi moved to 50:50 JV with SMASCO from Jan 2025. Next-3yr is a Claude estimate.",
            },
        ],
    },
]

INDUSTRIES.append({
    "slug": "lodging",
    "name": "Lodging",
    "display_order": 4,
    "companies": [
        {
            "slug": "ihcl", "name": "Indian Hotels Company (Taj, Vivanta, Ginger, SeleQtions)", "ticker": "INDHOTEL",
            "revenue": 8565, "past_cagr": 12.0, "next_growth": 13.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 consolidated revenue Rs 8,565 Cr, +12% YoY -- official Q4/full-year FY25 results (ihcltata.com). Brand-level split (Taj/Vivanta/Ginger/SeleQtions) not disclosed -- kept as one node, same as ABLBL. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "eih-oberoi", "name": "EIH (Oberoi, Trident)", "ticker": "EIHOTEL",
            "revenue": 2743, "past_cagr": 16.5, "next_growth": 14.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 consolidated revenue Rs 2,743 Cr, +9.2% YoY, 3yr CAGR (FY23-25) 16.5% -- screener.in financials. Brand-level split (Oberoi vs Trident) not disclosed. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "lemontree", "name": "Lemon Tree Hotels", "ticker": "LEMONTREE",
            "revenue": 1286, "past_cagr": 18.0, "next_growth": 17.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 consolidated revenue Rs 1,286 Cr, +20% YoY, 3yr CAGR (FY23-25) 18% -- screener.in financials. Spans upscale/midscale/economy brands, not separately disclosed. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "chalet-hotels", "name": "Chalet Hotels", "ticker": "CHALET",
            "revenue": 1750, "past_cagr": 24.0, "next_growth": 18.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue Rs 1,750 Cr, +24% YoY -- Simply Wall St coverage of FY25 results. Next-3yr is a Claude estimate (some deceleration from FY25's pace).",
        },
        {
            "slug": "leela-hotels", "name": "The Leela (Schloss Bangalore)", "ticker": "THELEELA",
            "revenue": 1301, "past_cagr": 23.0, "next_growth": 18.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue Rs 1,301 Cr, 2yr CAGR (FY23-25) 23% -- IPO note (Religare), ahead of its FY25 IPO. 'Past 3yr' uses this 2yr CAGR as the closest available figure. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "resorts-casinos",
    "name": "Resorts & Casinos",
    "display_order": 5,
    "companies": [
        {
            "slug": "itc-hotels", "name": "ITC Hotels", "ticker": "ITCHOTELS",
            "revenue": 3333, "past_cagr": 44.0, "next_growth": 20.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue Rs 3,333 Cr, +44% YoY -- widely reported FY25 results (BW Hotelier headline figure), first full year post-demerger from ITC Ltd. The 44% growth is partly a demerger/base-year effect, not pure organic growth -- flagged here. Next-3yr is a Claude estimate assuming normalization to a more typical hotel-industry growth rate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "restaurants",
    "name": "Restaurants",
    "display_order": 6,
    "companies": [
        {
            "slug": "jubilant-india", "name": "Jubilant FoodWorks — India (Domino's, Dunkin, Popeyes, Hong's Kitchen, COFFY)", "ticker": "JUBLFOOD",
            "revenue": 6104.7, "past_cagr": 14.3, "next_growth": 13.0, "source": "sourced",
            "notes": "FY25 India segment revenue Rs 6,104.7 Cr, +14.3% YoY -- official Q4/FY25 press release. Domino's India alone grew 18.8% (absolute figure not disclosed). Brand-level split (Domino's/Dunkin/Popeyes/Hong's Kitchen/COFFY) not disclosed -- kept as one India node. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "jubilant-international", "name": "Jubilant FoodWorks — International (Turkey, Azerbaijan, Georgia, Sri Lanka, Bangladesh)", "ticker": "JUBLFOOD",
            "revenue": 2037.0, "past_cagr": None, "next_growth": 15.0, "source": "sourced",
            "notes": "FY25 international segment revenue ~Rs 2,037 Cr -- official Q4/FY25 press release; the segment's own YoY isn't separately disclosed (total company grew 44% YoY, boosted by the DP Eurasia/Turkey master-franchise consolidation entering the base this year, so that 44% is not a clean organic rate). Past-growth left blank rather than guessed; next-3yr is a Claude estimate.",
        },
        {
            "slug": "devyani-kfc", "name": "Devyani International — KFC India", "ticker": "DEVYANI",
            "revenue": 2179.0, "past_cagr": 6.6, "next_growth": 10.0, "source": "sourced",
            "notes": "FY25 revenue Rs 2,179 Cr, +6.6% YoY -- Q4 FY25 earnings call transcript. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "devyani-pizzahut", "name": "Devyani International — Pizza Hut India", "ticker": "DEVYANI",
            "revenue": 732.0, "past_cagr": 3.2, "next_growth": 8.0, "source": "sourced",
            "notes": "FY25 revenue Rs 732 Cr, +3.2% YoY -- Q4 FY25 earnings call transcript. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "devyani-costacoffee", "name": "Devyani International — Costa Coffee India", "ticker": "DEVYANI",
            "revenue": 199.0, "past_cagr": 30.8, "next_growth": 25.0, "source": "sourced",
            "notes": "FY25 revenue Rs 199 Cr, +30.8% YoY -- Q4 FY25 earnings call transcript. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "devyani-international-other", "name": "Devyani International — International & Other Brands (Thailand KFC, Nepal, Nigeria, Vaango, Food Street)", "ticker": "DEVYANI",
            "revenue": 1841.0, "past_cagr": None, "next_growth": 15.0, "source": "claude_estimate",
            "notes": "Residual: FY25 consolidated total Rs 4,951 Cr (+39.2% YoY) minus the three disclosed India brands (KFC+Pizza Hut+Costa = Rs 3,110 Cr) = ~Rs 1,841 Cr. Covers the Thailand KFC acquisition plus Nepal/Nigeria/Vaango/Food Street, none individually disclosed. Claude estimate by subtraction, not a sourced breakdown. Past-growth left blank; next-3yr is a Claude estimate.",
        },
        {
            "slug": "sapphire-foods", "name": "Sapphire Foods (KFC & Pizza Hut — South/West India, Sri Lanka, UAE)", "ticker": "SAPPHIRE",
            "revenue": 2882.0, "past_cagr": 12.6, "next_growth": 12.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 consolidated revenue Rs 2,882 Cr, +11.1% YoY, 3yr CAGR (FY23-25) 12.6% -- screener.in financials. Brand split (KFC vs Pizza Hut) and geography split not found in a quick pass -- kept as one node. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "travelfood-lounges", "name": "Travel Food Services — Airport Lounges", "ticker": "TRAVELFOOD",
            "revenue": 779.06, "past_cagr": None, "next_growth": 18.0, "source": "sourced",
            "notes": "FY25: lounges were 46.14% of operational revenue (~Rs 779.06 Cr of the Rs 1,687.73 Cr total) -- IPO note (Chittorgarh), ahead of FY25 IPO. Segment-level YoY not separately disclosed; next-3yr is a Claude estimate.",
        },
        {
            "slug": "travelfood-airport-qsr", "name": "Travel Food Services — Airport Travel QSR", "ticker": "TRAVELFOOD",
            "revenue": 832.70, "past_cagr": None, "next_growth": 18.0, "source": "claude_estimate",
            "notes": "Residual: airport operations were 95.55% of total (~Rs 1,611.76 Cr) minus the lounges figure above (~Rs 779.06 Cr) = ~Rs 832.70 Cr -- Claude estimate by subtraction, not a directly disclosed figure. 442 QSR outlets as of Mar 2025, mostly partner brands (54.37%) vs in-house (45.63%). Next-3yr is a Claude estimate.",
        },
        {
            "slug": "travelfood-other", "name": "Travel Food Services — Highway & Other Sites", "ticker": "TRAVELFOOD",
            "revenue": 75.97, "past_cagr": None, "next_growth": 15.0, "source": "claude_estimate",
            "notes": "Residual: total Rs 1,687.73 Cr minus airport operations (~Rs 1,611.76 Cr) = ~Rs 75.97 Cr -- highway sites were separately noted as 4.45% of total, which matches closely. Claude estimate by subtraction. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "internet-content-information",
    "name": "Internet Content & Information",
    "display_order": 7,
    "companies": [
        {
            "slug": "infoedge-naukri", "name": "Info Edge — Naukri (Recruitment)", "ticker": "NAUKRI",
            "revenue": 1982.6, "past_cagr": 13.0, "next_growth": 13.0, "source": "sourced",
            "notes": "FY25 standalone revenue Rs 1,982.6 Cr, +13.0% YoY -- official May 2025 earnings presentation. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "infoedge-99acres", "name": "Info Edge — 99acres (Real Estate)", "ticker": "NAUKRI",
            "revenue": 410.8, "past_cagr": 16.9, "next_growth": 18.0, "source": "sourced",
            "notes": "FY25 standalone revenue Rs 410.8 Cr, +16.9% YoY -- official May 2025 earnings presentation. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "infoedge-jeevansathi", "name": "Info Edge — Jeevansathi (Matrimony)", "ticker": "NAUKRI",
            "revenue": 109.8, "past_cagr": 28.8, "next_growth": 20.0, "source": "sourced",
            "notes": "FY25 standalone revenue Rs 109.8 Cr, +28.8% YoY -- official May 2025 earnings presentation. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "infoedge-shiksha", "name": "Info Edge — Shiksha (Education)", "ticker": "NAUKRI",
            "revenue": 150.4, "past_cagr": 8.1, "next_growth": 10.0, "source": "sourced",
            "notes": "FY25 standalone revenue Rs 150.4 Cr, +8.1% YoY -- official May 2025 earnings presentation. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "discount-stores",
    "name": "Discount Stores",
    "display_order": 8,
    "companies": [
        {
            "slug": "dmart", "name": "Avenue Supermarts (DMart)", "ticker": "DMART",
            "revenue": 53333.2, "past_cagr": 24.7, "next_growth": 18.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue Rs 53,333.2 Cr, +16.7% YoY; 5yr CAGR 24.7% (used here as the 'past 3yr' proxy -- closest sourced figure found) -- Annual Report FY2024-25 analysis (Equitymaster). Format split (physical stores vs DMart Ready online) and category mix (Foods/Non-Foods FMCG/General Merchandise & Apparel) not found in a quick pass -- kept as one node. Next-3yr is a Claude estimate (deceleration as the base grows).",
        },
    ],
})

INDUSTRIES.append({
    "slug": "auto-truck-dealerships",
    "name": "Auto & Truck Dealerships",
    "display_order": 9,
    "companies": [
        {
            "slug": "cartrade-consumer", "name": "CarTrade Tech — Consumer (CarWale, CarTrade, BikeWale)", "ticker": "CARTRADE",
            "revenue": 2377.2, "past_cagr": 20.0, "next_growth": 18.0, "source": "claude_estimate",
            "notes": "FY25 segment revenue Rs 2,377.2 Cr -- sourced from FY25 results coverage. Individual segment YoY not separately disclosed (only total company growth of 30.8% and Classifieds' 75.3% were given) -- past/next growth here are Claude estimates, positioned below the company-wide rate since Classifieds grew fastest.",
        },
        {
            "slug": "cartrade-remarketing", "name": "CarTrade Tech — Remarketing (Shriram Automall)", "ticker": "CARTRADE",
            "revenue": 2123.8, "past_cagr": 22.0, "next_growth": 20.0, "source": "claude_estimate",
            "notes": "FY25 segment revenue Rs 2,123.8 Cr -- sourced from FY25 results coverage. Individual segment YoY not separately disclosed -- past/next growth are Claude estimates.",
        },
        {
            "slug": "cartrade-classifieds", "name": "CarTrade Tech — Classifieds (OLX India)", "ticker": "CARTRADE",
            "revenue": 1918.8, "past_cagr": 75.3, "next_growth": 35.0, "source": "sourced",
            "notes": "FY25 segment revenue Rs 1,918.8 Cr, +75.3% YoY (the one segment growth rate the company did disclose) -- FY25 results coverage. Next-3yr is a Claude estimate (deceleration from this unusually high rate, likely boosted by the OLX India acquisition anniversary effect).",
        },
    ],
})

INDUSTRIES.append({
    "slug": "department-stores",
    "name": "Department Stores",
    "display_order": 10,
    "companies": [
        {
            "slug": "vishalmegamart-apparel", "name": "Vishal Mega Mart — Apparel", "ticker": "VMM",
            "revenue": 4715.2, "past_cagr": 20.2, "next_growth": 18.0, "source": "sourced",
            "notes": "FY25 total revenue Rs 10,716.3 Cr, +20.2% YoY; Apparel is 44% of revenue (~Rs 4,715.2 Cr) -- FY25 results coverage. Category-level YoY not separately disclosed, so past-growth uses the company-wide rate as a proxy. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "vishalmegamart-generalmerch", "name": "Vishal Mega Mart — General Merchandise", "ticker": "VMM",
            "revenue": 3000.6, "past_cagr": 20.2, "next_growth": 17.0, "source": "sourced",
            "notes": "28% of FY25's Rs 10,716.3 Cr total (~Rs 3,000.6 Cr) -- FY25 results coverage. Category-level YoY not separately disclosed, company-wide rate used as proxy. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "vishalmegamart-fmcg", "name": "Vishal Mega Mart — FMCG", "ticker": "VMM",
            "revenue": 3000.6, "past_cagr": 20.2, "next_growth": 17.0, "source": "sourced",
            "notes": "28% of FY25's Rs 10,716.3 Cr total (~Rs 3,000.6 Cr) -- FY25 results coverage. Category-level YoY not separately disclosed, company-wide rate used as proxy. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "education-training-services",
    "name": "Education & Training Services",
    "display_order": 11,
    "companies": [
        {
            "slug": "physicswallah-online", "name": "PhysicsWallah — Online Coaching", "ticker": "PWL",
            "revenue": 1404.0, "past_cagr": 45.5, "next_growth": 30.0, "source": "sourced",
            "notes": "FY25 revenue Rs 1,404 Cr, +45.5% YoY (from Rs 965 Cr in FY24) -- FY25 results coverage. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "physicswallah-offline", "name": "PhysicsWallah — Offline Centers (Vidyapeeth)", "ticker": "PWL",
            "revenue": 1352.0, "past_cagr": 45.7, "next_growth": 35.0, "source": "sourced",
            "notes": "FY25 revenue Rs 1,352 Cr, +45.7% YoY (from Rs 928 Cr in FY24) -- FY25 results coverage; offline ARPU Rs 40,405 (up from Rs 34,467 in FY23). Next-3yr is a Claude estimate.",
        },
        {
            "slug": "physicswallah-hostel-transport", "name": "PhysicsWallah — Hostel Fees & Transportation", "ticker": "PWL",
            "revenue": 88.0, "past_cagr": None, "next_growth": 25.0, "source": "sourced",
            "notes": "FY25 revenue Rs 88 Cr -- FY25 results coverage. Past-growth not disclosed; next-3yr is a Claude estimate.",
        },
        {
            "slug": "physicswallah-products", "name": "PhysicsWallah — Product Sales (books, merchandise)", "ticker": "PWL",
            "revenue": 259.0, "past_cagr": 74.0, "next_growth": 30.0, "source": "sourced",
            "notes": "FY25 revenue Rs 259 Cr, +74% YoY -- FY25 results coverage. Note: these 4 segments sum to ~Rs 3,103 Cr vs. the company's disclosed total operating revenue of Rs 2,887 Cr -- a reconciliation gap likely from how 'Coaching Services' (Rs 2,498.5 Cr) was itself reported as a sub-total; used the more granular figures as given rather than force a match. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "specialty-business-services",
    "name": "Specialty Business Services",
    "display_order": 12,
    "companies": [
        {
            "slug": "bls-international", "name": "BLS International (visa/consular outsourcing)", "ticker": "BLS",
            "revenue": 2193.0, "past_cagr": 20.3, "next_growth": 22.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 consolidated revenue Rs 2,193 Cr, +30.8% YoY, 3yr CAGR (FY23-25) 20.3% -- screener.in financials. India vs international split not found in a quick pass. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "igi-india", "name": "International Gemological Institute (IGI) India", "ticker": "IGIL",
            "revenue": 1229.1, "past_cagr": 17.0, "next_growth": 18.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue Rs 1,229.1 Cr, +17% YoY -- FY25 results coverage (growth across natural diamonds, lab-grown diamonds, jewelry, gemstones all mentioned qualitatively, no rupee split disclosed). Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "specialty-retail",
    "name": "Specialty Retail",
    "display_order": 13,
    "companies": [
        {
            "slug": "lenskart-india", "name": "Lenskart — India", "ticker": "LENSKART",
            "revenue": 4014.5, "past_cagr": None, "next_growth": 22.0, "source": "claude_estimate",
            "notes": "Residual: FY25 total revenue Rs 6,652.5 Cr minus the disclosed International figure (Rs 2,638 Cr) = ~Rs 4,014.5 Cr. India-specific YoY not separately disclosed. Next-3yr is a Claude estimate.",
        },
        {
            "slug": "lenskart-international", "name": "Lenskart — International (Japan, Singapore, Taiwan, Thailand, Saudi Arabia, SE Asia)", "ticker": "LENSKART",
            "revenue": 2638.0, "past_cagr": 17.0, "next_growth": 25.0, "source": "sourced",
            "notes": "FY25 international revenue Rs 2,638 Cr, +17% YoY -- FY25 results coverage ahead of IPO; 52 new overseas stores added in FY25, 2.5M international customers. Next-3yr is a Claude estimate.",
        },
    ],
})

INDUSTRIES.append({
    "slug": "travel-services",
    "name": "Travel Services",
    "display_order": 14,
    "companies": [
        {
            "slug": "irctc-catering", "name": "IRCTC — Catering", "ticker": "IRCTC",
            "revenue": 2230.9, "past_cagr": 19.2, "next_growth": 15.0, "source": "claude_estimate",
            "notes": "FY25 total revenue Rs 4,903 Cr, +10% YoY -- official Q4/FY25 results. Segment split not found for the full FY25 year itself, so this uses the Q3 FY26 segment-mix percentage (Catering 45.5% of revenue) applied to the FY25 total as a Claude estimate, not a directly disclosed FY25 figure. Past-growth borrows the segment's Q3 YoY rate as the closest available proxy.",
        },
        {
            "slug": "irctc-ticketing", "name": "IRCTC — Internet Ticketing", "ticker": "IRCTC",
            "revenue": 1348.3, "past_cagr": 13.3, "next_growth": 12.0, "source": "claude_estimate",
            "notes": "Q3 FY26 segment mix (27.5% of revenue) applied to the FY25 total (Rs 4,903 Cr) -- Claude estimate, not a directly disclosed FY25 figure. Past-growth borrows the segment's Q3 YoY rate as the closest available proxy.",
        },
        {
            "slug": "irctc-tourism", "name": "IRCTC — Tourism", "ticker": "IRCTC",
            "revenue": 975.9, "past_cagr": 29.3, "next_growth": 25.0, "source": "claude_estimate",
            "notes": "Q3 FY26 segment mix (19.9% of revenue) applied to the FY25 total (Rs 4,903 Cr) -- Claude estimate, not a directly disclosed FY25 figure. Past-growth borrows the segment's Q3 YoY rate as the closest available proxy.",
        },
        {
            "slug": "irctc-railneer", "name": "IRCTC — Rail Neer (packaged water)", "ticker": "IRCTC",
            "revenue": 348.1, "past_cagr": 6.6, "next_growth": 8.0, "source": "claude_estimate",
            "notes": "Q3 FY26 segment mix (7.1% of revenue) applied to the FY25 total (Rs 4,903 Cr) -- Claude estimate, not a directly disclosed FY25 figure. Past-growth borrows the segment's Q3 YoY rate as the closest available proxy.",
        },
        {
            "slug": "tbotek", "name": "TBO Tek (B2B travel distribution)", "ticker": "TBOTEK",
            "revenue": 1737.0, "past_cagr": 25.0, "next_growth": 22.0, "source": "sourced", "pct": 1.0,
            "notes": "FY25 revenue from operations Rs 1,737 Cr, +25% YoY -- official Q4/FY25 earnings. Segment split (Hotels & Ancillaries vs Air) not disclosed, described only qualitatively. Next-3yr is a Claude estimate.",
        },
    ],
})
