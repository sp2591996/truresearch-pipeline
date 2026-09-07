# TrueResearch V2 — Product Requirements Document (Phase A, Draft 1)

*Prepared for Avdhoot. Source of truth for scope: `PROJECT_STATE.md` (locked decisions) + `Feature_Universe_Scope_v2_Response.xlsx` (feature-by-feature detail). This PRD turns that spreadsheet into buildable specs for every L1 (launch/MVP) feature, and defines exactly what every "placeholder" should say for L2–L4 features, per your rule that no placeholder is ever a blank message.*

**How to read this document:** Each feature area (A–K) below lists every L1 feature with: what it does, what goes in and comes out, tricky cases to handle, and how we'll know it's done ("Acceptance Criteria" — read this as "the checklist I'll test the feature against before calling it finished"). Deferred (L2/L3/L4) features are listed briefly at the end of each section with their placeholder text, so you can see the whole page even before it's fully built.

---

## 0. Scope confirmation (carried over from PROJECT_STATE.md — do not re-litigate here)

- Equity universe: **Nifty 500**
- Additional asset classes at launch: **Gold** (full L1), **Mutual Funds** (pulled up to L1, scope now narrowed — see J3: NAV + category + expense ratio + AUM only, holdings-based overlap deferred), **Debt** (L1 = static reference rates only), **REIT** (L1 = placeholder only), **International Equity** (L1 = placeholder only)
- Mobile: **Progressive Web App**, not native app
- TrueScore ML: validate/back-test on current data **before** expanding coverage or auto-retraining
- Regulatory framing: everything is a "research signal," never "advice" or "recommendation" — this line appears on every relevant page, not just a disclaimer page
- Branding (name/logo/color) is proposed in the Design System document (companion to this PRD), not decided yet

**Timeline flag — RESOLVED (Phase C decision).** The original concern was that Mutual Funds is "genuinely comparable in size to the entire original equity Phase 1," because portfolio-holdings overlap requires scraping/aggregating monthly factsheet PDFs across every fund house — there is no free, structured, cross-fund holdings API in India (unlike NAV, which AMFI publishes free and several wrapper APIs already expose cleanly). **Decision: keep Mutual Funds in L1, but narrow its L1 scope to NAV + category + expense ratio + AUM only** (all confirmed free via AMFI-based APIs, e.g. MFapi.in for NAV/category, captnemo.in-style APIs for expense ratio/AUM). **Portfolio-holdings overlap is explicitly deferred to L2** (already tracked as C6, Mutual Fund Overlap Detector) — this removes the one genuinely hard, potentially-paid-data piece from the L1 timeline, so Mutual Funds no longer needs the "extend timeline or hold back" trade-off the way it originally did. Any other pulled-up L1 item still gets evaluated the same way if it turns out to hide a similar hard dependency.

---

## A. Discovery

### A1. Curated Lists (Top Rated / Growth / Value / Quality / Momentum / Undervalued, + expanded list types)
- **What it does:** Auto-updating, no-input lists of assets ranked by a single TrueScore component or a simple rule (e.g. "Top 20 by Quality"). Shown on Home and a dedicated Stocks section.
- **Inputs:** Latest `scores` table snapshot (per asset, per formula version); a config file defining each list's ranking rule.
- **Outputs:** Ranked table (ticker, name, sector, relevant score/metric, 1-line "why it's here").
- **Beyond the original scope, per your feedback:** every stock/sector/score name mentioned anywhere in the list is a link to that asset's/sector's page (site-wide rule, not just here). List variety expands beyond the original 6 (e.g. add "Low Volatility," "Recently Turned Profitable," "High Dividend Yield" as additional presets).
- **Edge cases:** a sector with too few qualifying stocks (show fewer than the target count rather than padding with weak matches); a stock missing the underlying data point (excluded from that specific list, not shown with a blank score).
- **Acceptance criteria:** every list renders in <1s from cached data; every name in every list is a working link; at least 8 distinct list types exist at launch (up from 6).
- **Data depth note:** launches on the 5-year history already in the database; 10-year backfill is an ongoing background research task in Phase 4, not a launch blocker (yfinance doesn't reliably go back further; deeper history means manual re-keying from annual reports).

### A2. Curated List / Persona Generator
- **What it does:** A short onboarding quiz (a handful of questions) shown on first visit, mapping the user to one of 15–20 pre-built personas (e.g. "cautious beginner," "growth-focused experienced investor"), which biases which curated lists surface first for that user.
- **Inputs:** Quiz answers (finance familiarity, investing stage, product interest).
- **Outputs:** A persona ID stored client-side (or against the account once logged in) + a reordered/highlighted set of curated lists on Home.
- **Edge cases:** user skips the quiz (default to a neutral "Discoverer" persona, never block the homepage); user retakes the quiz (latest answer wins).
- **Acceptance criteria:** quiz completes in under 30 seconds; every one of the 15–20 personas maps to a visibly different Home experience (not just a label).
- **Deferred to L3:** expanding to 100+ personas and linking to actual holdings for deeper personalization.

### A3. Sector & Industry Pages
- **What it does:** One page per sector — all constituent stocks, sector-average ratios, sector trend chart, plus (new, per your feedback) a written sector overview: size, growth, product landscape, government policy, current events, and the top stocks *and* top mutual funds exposed to that sector.
- **Mutual fund list, scope correction (Phase C):** since holdings-based overlap is deferred (see J3), "top mutual funds exposed to this sector" ships in L1 as a **category-based** match, not a true holdings-based one — i.e. funds whose AMFI category aligns with the sector (e.g. a Banking & Financial Services fund category surfacing on the Financial Services sector page), ranked by AUM. This is honest and fully buildable from the confirmed-free NAV+category+AUM data; it is not the same as "funds that actually hold stocks in this sector," and should be labeled as such in the UI (e.g. "Funds investing in this space" rather than "Funds holding these stocks").
- **Inputs:** Sector mapping (from `sectors`/`industries` tables), aggregated ratios, manually written sector overview content, mutual fund category/AUM data (J3).
- **Outputs:** Sector page with data table + written overview + top-10 stock list + top-5 category-matched mutual-fund list.
- **Edge cases:** a sector with very few Nifty 500 constituents still gets a full page, just a shorter stock list.
- **Acceptance criteria:** every sector has a written overview (India-focused depth at launch; deeper global context added over time — this is real research-writing time, tiered the same way as stock research); every sector page links from every stock in it.

### A4. Market Movers (Gainers/Losers/Most Active)
- **What it does:** Daily-updated widget/page of biggest gainers, losers, most-traded-by-volume stocks.
- **Inputs:** Live/near-live price feed.
- **Outputs:** Three ranked mini-tables.
- **Change from original scope:** refresh interval is **5 minutes**, not 15 — trivial change to the existing job.
- **Acceptance criteria:** data on the page is never more than 5 minutes stale; each row links to its stock page.

### A5. Thematic Discovery Hub
- **What it does:** Editorially curated collections beyond mechanical score lists (e.g. "Debt-free companies," "Recently turned profitable").
- **Launch scope:** **3 major themes only** at launch (the most popular/requested); expand to 10+ post-launch.
- **Acceptance criteria:** the 3 launch themes are picked and documented before Phase 2 build starts; each reuses existing filter/score logic (no new pipeline).

### A6. Market Mood / Sentiment Index
- **What it does:** A single daily gauge summarizing overall market sentiment (blend of volatility, advance/decline breadth, momentum), shown with a short daily written commentary line.
- **Inputs:** Daily price/volume data across the Nifty 500 universe.
- **Outputs:** A number/gauge (0–100 or similar) + one sentence of commentary, both dated.
- **Methodology requirement:** this gets the same rigor as TrueScore — a documented, versioned formula, validated before it goes live (not launched as an arbitrary number).
- **Acceptance criteria:** formula is written down and back-tested against at least one visibly volatile historical period before shipping; commentary is generated (or written) daily without fail for 2 consecutive weeks in staging before launch.

### Deferred in Section A (with required placeholder text)
- **A7. Personalized "For You" Discovery (L3)** — needs real per-user behavioral history; not a placeholder feature (no meaningful UI exists yet without users).
- **A8. AI-Driven Discovery Tuned to Risk Profile (L4)** — advisory-adjacent, vision-stage; no placeholder needed at L1.

---

## B. Research & Analysis

### B1. Company/Asset Detail Page
- **What it does:** The hero page. Price, market cap, sector, P/E, P/B, ROE, ROCE, debt/equity, margins, historical charts — **expanded per your feedback** to also show: TrueScore + its component breakdown inline (not just a link), whether it's in today's Market Movers, historic returns (1M/1Y/3Y/5Y), and sector-specific ratios (not generic ones — a bank's key ratios differ from a manufacturer's).
- **Scope correction (Phase C):** "the stock's exposure across mutual funds that hold it" is **removed from L1** — this requires portfolio-holdings data, which is explicitly deferred (see J3, C6). This section becomes a Placeholder Panel on the stock page instead (see Wireframes.md), not a live section, until holdings data exists.
- **Inputs:** `assets`, `prices`, `fundamentals`, `ratios_snapshot`, `scores`, `peers` tables.
- **Outputs:** Full page per the layout in the companion Wireframes document.
- **Site-wide rule (applies everywhere, not just here):** every mention of a stock's name or ticker, anywhere on the site, is a link to this page.
- **Edge cases:** newly listed stock with <1 year of history (show what exists, label the gap, never fake a 5-year chart); sector-specific ratio not applicable to a given stock's sector (hide that ratio row, don't show "N/A").
- **Acceptance criteria:** all 500 Nifty 500 stocks render a complete page with no missing required field silently blank; sector-relative ratios visibly differ in which ratios are shown across at least 3 different sectors (proving the logic is sector-aware, not copy-pasted).

### B2. TrueScore with Component Breakdown
- **What it does:** 0–100 composite score from Quality/Growth/Valuation/Momentum/Risk, each shown with a plain-English explanation, sector-relative percentile based, versioned formula. Separately, a **TrueScore Rating** blends the ML "Model Signal" with relative valuation and other indicators into its own distinct rating (kept visually and structurally separate from the core TrueScore, per the original plan's "don't blend an unvalidated model into the headline number" rule).
- **Sequencing (locked, do not build out of order):** (1) back-test/validate the existing ML model on the current 200-stock, 5-year dataset first → (2) only then expand daily scoring to the full Nifty 500 → (3) only then consider monthly auto-retraining. Do not skip to step 2 or 3.
- **Inputs:** `fundamentals`, `ratios_snapshot`, `prices`, sector mapping, the ML model's own feature set.
- **Outputs:** `scores` row per asset per run: quality, growth, valuation, momentum, risk, model_signal, cs_rating, overall, formula_version.
- **Edge cases:** missing underlying data point → component weight reduced proportionally, never a silent zero (documented in Section D of the original master plan); a company in default or clearly distressed must not score in the 80s+ — this is a required manual sanity check before every model change ships.
- **Acceptance criteria:** back-test report exists and is reviewed by you before any coverage expansion; formula versions are stored with every score row so "why did this change" is always answerable; TrueScore Rating is visually distinguishable (different badge/color) from core TrueScore everywhere it appears.

### B3. Written Research Reports (bull/bear case)
- **What it does:** Structured qualitative report per stock — business overview, growth drivers, financials, competitive position, key risks, bull/bear case, conclusion. Tiered: flagship depth for top ~50 stocks, faster "Auto Research Summary" (1–2 pages, still human-reviewed) for the rest.
- **New requirement per your feedback:** **one standardized report template**, defined before any more reports are written, with sector-appropriate variants (a bank template ≠ a manufacturer template) — the current 20 decks are not standardized and should be re-aligned to the new template.
- **Inputs:** Financials, manually researched qualitative content, sector template.
- **Outputs:** Published research report page, linked from the stock detail page.
- **Acceptance criteria:** the template itself (page-by-page structure, per sector variant) is written and approved before a single new report is drafted against it; all future reports pass a template-conformance check.

### B4. 10+ Year Historical Financial Data + Excel Export
- **What it does:** Long-run revenue/profit/margin/ratio history per company, downloadable as a spreadsheet.
- **Sequencing change:** moved up — build shortly after the Phase 1 (5-year) foundation is solid, not deferred to a separate later phase, since it's cheap once that foundation exists.
- **Acceptance criteria:** export produces a correctly formatted spreadsheet (via the xlsx skill/pipeline, not a raw CSV dump) for any stock with available history.

### B5. Corporate Actions Calendar
- **What it does:** Upcoming/past dividends, splits, bonuses, buybacks, results dates — per-stock widget + a dedicated calendar page.
- **New scope per your feedback, folded into Phase 4 (research), not built as a separate real-time feed:** annual-report findings, management-discussion summaries, and stock/sector news become a "Recent Developments" section refreshed each time a stock's research is revisited — this is manual research effort, same bucket as B3, not a live news pipeline.
- **Acceptance criteria:** the calendar itself (dates/actions) is live-data-driven and correct for all 500 stocks; "Recent Developments" sections exist for every stock that has had its research revisited at least once.

### B6. Insider/Promoter Buying-Selling Alerts (display only at launch)
- **What it does:** Shows insider/promoter buy/sell activity on the stock page (not yet as push/email alerts — that's L2 alerting infrastructure).
- **Acceptance criteria:** appears as a section on every applicable stock's detail page, not a standalone page only.

### B7. Shareholding Pattern Trends
- **What it does:** Chart of promoter/FII/DII/public shareholding **over the last several quarters** (expanded from a current-snapshot-only view), shown on every stock page (not just in decks).
- **Acceptance criteria:** at least 4 historical quarters visible per stock where data exists; present on all 500 stock pages, not only the ones with flagship research.
- **Status (Session 11): data pipeline live.** `25_shareholding_refresh.py` ingests NSE XBRL filings; 497/500 Nifty 500 stocks now have at least one quarter saved. Fixed a real bug this session: NSE added a new "Employee Benefit Trusts" XBRL category (schema version "2025-10") that isn't part of the Public total — without accounting for it, promoter+DII+FII+public no longer summed to ~100%, tripping the pipeline's own sanity check and silently rejecting the quarter. This was causing SWIGGY, FIRSTCRY, and THERMAX (among others) to fail; fixed by folding the employee-trust % into `public_pct`. Promoter % now also feeds the Compare page's Shareholding section (latest vs. ~4 quarters back). Still failing, different unresolved cause: MCX, ABBOTINDIA, BAYERCROP. The shareholding *chart itself* on the stock detail page (B1) is not yet confirmed built — only the data pipeline and its use in Compare are confirmed.

### Deferred in Section B (placeholder text required)
- **B8. Credit Rating Change Tracking (L2)** — Placeholder: labeled "Credit Rating: Coming Soon" section on banks/NBFCs/debt-heavy company pages.
- **B9. Management & Board Profiles (L2)** — Placeholder: a "Leadership" section showing name + title only (sourced from existing research), full bios/compensation later.
- **B10. ESG / Governance Red-Flag Indicators (L3)** — Placeholder: labeled section noting "in development."
- **B11. Analyst Ratings & Price-Target Aggregation (L3)** — Placeholder must be honest that this typically requires paid/licensed data: "Third-party analyst views: coming as we evaluate data partnerships" (not implied as "just a matter of time on free data").

---

## C. Comparison & Screening

### C1. Screener with Filters
- **What it does:** Filterable table across market cap, sector, growth, quality, valuation, momentum, TrueScore.
- **New per your feedback:** support comparing **3+ companies** (not just 2) from within the screener, and a **sector-vs-sector comparison** mode (reusing the Section A3 sector aggregates — no new pipeline).
- **Acceptance criteria:** a user can select 3–4 stocks from screener results and land on a working comparison page (C3); a sector-vs-sector view exists and pulls from the same aggregate data as the sector pages.
- **Status (Session 11): BUILT.** Checkbox multi-select (max 4) added to the results table, plus 3 preset filter chips ("Top Rated" — score ≥80, "Undervalued (by P/E)" — bottom quartile positive P/E, "Large Cap" — top quartile market cap). A "Compare selected" action bar links straight to `/compare`. Sector-vs-sector mode is **not yet built** — still open.

### C2. Preset Screens
- **What it does:** One-click named filter combinations (High Growth, Undervalued, QARP, etc.) on top of C1. No change from original scope.

### C3. Multi-Stock Comparison Page (X vs Y vs Z)
- **What it does:** Side-by-side comparison across growth, margins, ROE, debt, P/E, performance, TrueScore, with a shareable URL — also a key SEO page type.
- **Acceptance criteria:** supports 2–4 stocks per comparison; URL is stable/shareable; page is server-rendered for SEO.
- **Status (Session 11): BUILT.** Live at `/compare?tickers=A,B,C,D`, server-rendered. Metrics are grouped into 5 sections — TrueScore & Performance, Profitability, Valuation & Size, Shareholding, TrueScore Breakdown — covering valuation ratios (P/E, P/B, EV/EBITDA, price/sales, 52-week range), profitability stats (net margin, ROA, FCF margin, YoY growth), shareholding pattern (promoter %, latest vs. ~4 quarters back), and a TrueScore component breakdown. A metric row is dropped entirely if none of the selected stocks have data for it, rather than showing blank dashes — an honest-data-gap rule worth carrying into other pages (B1, A3) that show sparse fields. The best value in each row gets a small "✓ Best" badge next to the cell, not a full-cell highlight. Header row is sticky within its own scrolling container so it stays visible while scrolling through metrics. A user can add a 3rd/4th stock directly from the page (search box, no trip back to Screener) via `AddStockToCompare`.

### C4. Custom User-Defined Ratios/Formulas — **launch scope is fixed filters only**
- **What it does at L1:** the standard filter set from C1. The flexible "define your own formula" builder is **explicitly L2**, not launch scope — confirming, not changing, the original plan.

### C5. Cross-Asset Comparison — de-scoped to a buildable version
- **What it does at L1:** a **basic bundle comparison** — "if you'd invested equally across a stock bundle vs. Gold vs. a Bank FD over a selected historical period, here's what each would be worth." Uses Gold (already L1) + FD static reference rates (no live feed needed) + existing stock price history.
- **Acceptance criteria:** user can pick a historical start date and a set of stocks, and see a 3-way comparison chart (bundle / gold / FD) for that period. Full L3 cross-asset comparison (bonds, REITs, etc.) waits for those asset classes to exist.

### Deferred in Section C (placeholder text required)
- **C6. Mutual Fund Overlap Detector (L2)** — Placeholder: UI slot + "activates once mutual fund data coverage is live" (tracks the Mutual Funds feature directly, not an independent build).
- **C7. Natural-Language Screener (L3/L4)** — Placeholder: a mention only (e.g. near the search bar), not a working input.

---

## D. Portfolio

### D1. Watchlist
- **What it does:** Logged-in users save stocks to a personal, cross-session list.
- **New per your feedback:** show a **combined-bundle return summary** — "if you'd bought one of each stock on your watchlist, here's your 1M/1Y/5Y return" — computed from existing watchlist + price history data.
- **Acceptance criteria:** watchlist persists across sessions/devices for a logged-in user; bundle-return summary recalculates whenever the watchlist changes.

### D2. Manual Portfolio Entry + Tracking
- **What it does:** User manually enters ticker + quantity + buy price/date; app shows current value, gain/loss, portfolio-level TrueScore.
- **New per your feedback:** support **incremental entry** — a user can add one holding, leave, and come back to add more, rather than a forced one-shot full-portfolio form.
- **Acceptance criteria:** a user can add a single holding and see a valid (if partial) portfolio view immediately, without being forced to complete a multi-field form first.

### D3. Diversification Score / Concentration Risk / Sector Overlap
- **What it does:** Analyzes a manually-entered portfolio's sector/stock concentration, flags over-exposure.
- **New per your feedback:** also show the **portfolio's return vs. other asset classes** (vs. Nifty, vs. Gold, vs. FD) over the same period — reuses C5's cross-asset comparison logic.
- **Acceptance criteria:** every portfolio with ≥2 holdings shows a concentration flag (or a clean "well diversified" state) and a same-period comparison line against at least Nifty, Gold, and FD.

### D4. XIRR / True Returns — **L1 placeholder only**
- **Placeholder:** show simple absolute return, clearly labeled as such (not XIRR); proper time/money-weighted XIRR calculation follows shortly after in L2.

### D5. Dividend Income Tracker — **L1 placeholder only**
- **Placeholder:** shown in the portfolio view as "coming soon," ties to the Corporate Actions data once dividend history is flowing reliably.

### Deferred in Section D (placeholder text required)
- **D6. Multi-Broker Auto-Import (L3)** — Placeholder: "manual entry now, broker auto-import coming."
- **D7. Family/Household Aggregation (L4)** — Placeholder: mention only.

---

## E. Calculators & Planning

All of these are pure-computation, no-new-data-dependency tools — genuinely cheap once the underlying price/rate data exists, and strong SEO traffic magnets. **All pulled up to L1:**

### E1. Return Calculator ("if I'd invested ₹X on this date...")
- Pure computation on stored historical price data. **Acceptance criteria:** works for any Nifty 500 stock and any past date with available price data; shareable/linkable result.

### E2. SIP / Lumpsum / SWP Calculators
- Standard generic financial math, no company-specific data. **Acceptance criteria:** all three modes produce mathematically correct results verified against a known reference calculator.

### E3. Retirement / Goal-Based Planner — **generic version at launch**
- **What it does at L1:** a standalone version (not yet linked to a user's real portfolio, since portfolio tracking is also brand-new) — user inputs a goal and assumed return, gets a projection.
- **Follow-up:** wire it to real portfolio data (D2) a few weeks after launch once portfolio data is flowing.
- **Acceptance criteria:** generic version ships at launch; portfolio-linked version is a tracked follow-up item in PROJECT_STATE.md, not silently forgotten.

### E4. Risk-Profiling Questionnaire → Suggested Allocation
- **Framing requirement (non-negotiable):** output is explicitly educational/illustrative ("investors with your profile often consider...") — never a personalized recommendation. This keeps it on the right side of the "not advice" line.
- **Acceptance criteria:** output copy never uses "recommend," "should," or "advice"-flavored language; always includes the standard research-signal disclaimer.

### E5. EMI / Home Loan / Tax Calculators (old vs. new regime)
- Pure-formula tools, no stock-specific data. **Acceptance criteria:** tax calculator correctly implements both regimes for at least individual (non-business) income as of the current tax year.

### Deferred in Section E (placeholder text required)
- **E6. "What-If" Portfolio Backtesting (L2)** — Placeholder: "coming soon," real build follows once simpler calculators prove demand.
- **E7. Robo-Advisory-Lite (L4)** — Placeholder: mention only — this borders on regulated advice and needs legal review first.

---

## F. Alerts & Monitoring

**Shared infrastructure decision (applies to all 6 items below):** none of these are built individually. A single alerting infrastructure (scheduled comparison jobs + an email-sending service) is built once in L2, after Phase 6 (accounts/watchlists) is live. **Every item below is an L1 placeholder** — a visible, correctly-labeled UI element (a toggle, a "Get notified" button) that is not yet wired to real notifications:

- **F1. Saved-Screen New-Match Alerts** — placeholder toggle on saved screens.
- **F2. TrueScore Change Alerts** — placeholder toggle on watchlist items.
- **F3. Price Alerts** — placeholder "set a price alert" UI on stock pages.
- **F4. Earnings/Results-Date Reminders** — placeholder toggle tied to the Corporate Actions Calendar (B5).
- **F5. Portfolio-Level Risk Alerts (L3)** — placeholder mention only; needs both infrastructure and D3 to be mature first.
- **F6. Real-Time Multi-Channel Alerting — SMS/WhatsApp/push (L3/L4)** — placeholder mention only; real recurring cost, waits for revenue.

**Acceptance criteria for all six:** every placeholder explains, in one sentence, what will happen once it's live (per your Note 7 — never a mystery blank space).

---

## G. Education & Community

### G1. Jargon Glossary / "Learn" Section
- **What it does:** Plain-English explanations of every financial term used elsewhere on the site, linked contextually wherever that term appears.
- **New per your feedback, both added to L1:**
  1. A full beginner course — finance / stock market / asset classes explained "as if teaching a child," i.e. maximally simple language, building up gradually.
  2. A separate "how to use TrueResearch" product guide (not a finance topic — literally how to use the site itself).
- **Acceptance criteria:** every jargon term used on any live page has a Learn-section entry it links to; the beginner course covers at minimum: what a stock is, what a share price means, what P/E/ROE/market cap are, what a mutual fund is, what gold/FD/bonds are as alternatives — each as its own short lesson; the product guide covers every core feature (screener, watchlist, portfolio, comparison) with a screenshot or simple diagram per point (per PROJECT_STATE.md's hard rule: **every educational point must be paired with a picture/graph/graphic/flowchart — text alone is never acceptable**).

### G2. Newsletter / Article Section — **cadence RESOLVED (Phase C)**
- **What it does:** An on-site, **SEO-driven** article section (not just an email digest) — each article written and structured to actually rank in search (target keyword focus, proper headings, internal links to the stock/sector/term pages it mentions — reusing the site-wide "every mention is a link" rule), each with embedded images (text+image format, video/story formats deferred).
- **Cadence, decided:** **average twice a week** (not daily — the original "daily" framing is replaced by this figure, decided directly rather than left as a range). This is a sustainable, realistic commitment given the same person is also writing stock/sector research (B3/A3) and DRHP assessments (H1) — same writing-hours pool.
- **SEO requirement, made explicit (this is new detail, not in the original draft):** every article needs a defined target keyword/topic before writing starts, proper on-page structure (H1/H2 hierarchy, meta description, alt text on every image), and links out to relevant stock/sector/glossary pages already live on the site — this is what makes "SEO-driven" a real requirement and not just a description of format.
- **Acceptance criteria:** publishes at an average of 2x/week, sustained (a slow week and a faster week are fine, but track the rolling average, don't silently drift below it); every article has a defined target keyword, correct on-page SEO structure, and at least one embedded image; every stock/sector/term mentioned links to its page.

### Deferred in Section G (placeholder text required)
- **G3. Structured Free Courses/Varsity-style (L2)** — Placeholder: "Courses coming soon" under Learn.
- **G4. Community Discussion/Narratives (L2)** — Placeholder only; needs a moderation plan first.
- **G5. Verified-Analyst Contributions (L3)** — Placeholder only; needs a vetting process + legal review first.

---

## H. Execution & Monetization Hooks

### H1. IPO Tracker with GMP & Prospectus Summary — **pulled up to L1**
- **What it does:** Dedicated section listing upcoming/recent IPOs — subscription status, grey-market premium, prospectus summary, post-listing performance.
- **New per your feedback:** a **detailed DRHP (draft prospectus) assessment per new IPO, framed with no recommendations** — same "research signal, not advice" framing as everything else.
- **Effort flag:** the DRHP assessment is written-research work — same time-cost category as stock research reports (B3), competing for the same research hours. **Recommendation, carried into this PRD as the actual plan:** the IPO tracker's data/listing infrastructure ships at launch in full; DRHP assessments are tiered and ongoing (not all IPOs get flagship depth on day one), the same way stock research is tiered.
- **Acceptance criteria:** every current/upcoming IPO in the tracker at minimum has a data listing (dates, price band, subscription status); DRHP assessments are added progressively, tracked as their own backlog (not silently expected to appear instantly for every IPO).

### Deferred in Section H (placeholder text required)
- **H2. Affiliate Links (L2)** — Placeholder: infrastructure/disclosure UI exists, no live links yet — trust and traffic come first, as originally sequenced.
- **H3. Model Portfolios/"Baskets" (L4)** — Placeholder: mention only — SEBI-regulated territory (Smallcase's business model), needs legal clearance before any engineering.
- **H4. Direct Broker Order Execution (L4)** — Placeholder: mention only — needs market-intermediary registration or broker partnerships first.

---

## I. Compliance & Tax

### I1. Basic Legal Disclaimers
- **What it does:** Standard disclosure text ("not investment advice," methodology disclosure) on every relevant page.
- **Non-negotiable, day one.** This is the specific thing that lets TrueScore/research be published without SEBI Research Analyst registration.
- **Acceptance criteria:** the disclaimer (or a clear link to it) appears on every page that shows a score, a research report, a calculator output, or an IPO assessment — audited as a checklist item before every phase ships, not assumed present.

### Deferred in Section I (placeholder text required)
- **I2. Capital Gains/Tax Reporting (L2)** — Placeholder only; needs high-precision, ideally broker-linked transaction data before it's trustworthy enough to ship (a wrong tax number is a severe trust failure).

---

## J. Multi-Asset Coverage

### J1. Equities (Nifty 500)
- Full data, scoring, and research coverage for all 500 constituents — the core of the entire MVP.

### J2. Gold (proof-of-concept second asset class)
- Spot price tracking, a gold-specific score adapted from the equity TrueScore framework, and a short explainer on investment routes (physical, digital, SGB, ETF).
- **Acceptance criteria:** gold has its own detail page structurally similar to a stock detail page (price, score, explainer), proving the architecture genuinely generalizes beyond equities.

### J3. Mutual Funds — **scope finalized (Phase C decision)**
- **What it does, final L1 scope:** NAV tracking, category classification, expense ratio, AUM — a fund detail page structurally analogous to the stock detail page (same pattern J2/Gold already proved out). **Category-relative scoring** (comparing a fund to peers in its own category) is L1; **portfolio-holdings overlap with direct stocks is explicitly OUT of L1**, deferred to L2 (tracked as C6).
- **Why this scope, and why it's no longer the biggest open risk:** the original concern was that this is "comparable in size to the entire original equity Phase 1." Investigating the actual data landscape found that NAV (via AMFI, and free wrapper APIs like MFapi.in), category (bundled with NAV data), and expense ratio + AUM (via a second free API, keyed by ISIN) are all genuinely free and no harder than the equity price/fundamentals pipeline already built. The one piece that IS as hard as originally flagged — portfolio holdings, which India only publishes as monthly PDF factsheets per fund house, no free structured API — is the piece being deferred. This mirrors the Screener.in decision already made for equity fundamentals: don't block launch on the one data source that needs paid aggregation or heavy scraping.
- **Data sourcing plan:** two free APIs combined (one for NAV+category, one for expense ratio+AUM+ISIN lookup) — same "data provider abstraction layer" pattern as `market_data_provider.py` for equities: build one file that's the only place either API gets called directly.
- **Product/wireframe implications (see Wireframes.md for the actual layout):** a new **Mutual Fund Detail Page** is added, reusing existing components (Score Badge, Asset Card, Disclaimer Bar) rather than one-off design. Anywhere the original plan assumed holdings-based fund-to-stock linking (Stock Detail Page's "held by these funds" section, Sector Page's "top funds exposed to this sector"), that link is either removed to a Placeholder Panel (stock page) or downgraded to a category-based approximation, clearly labeled as such (sector page) — see B1 and A3 above.
- **Acceptance criteria:** NAV + category + expense ratio + AUM + a category-relative score exist for a defined initial universe of funds (recommend starting with the top N funds by AUM per category, same "depth before breadth" logic as the equity side, not every fund in India on day one); every fund page is structurally consistent with the stock detail page; nowhere on the site implies holdings-based fund/stock linking exists until C6 actually ships.

### J4. Debt Instruments — **static reference rates only**
- **What it does at L1:** current FD rates by major bank, current government bond/SGB yields — static reference data, refreshed periodically, not a live per-security feed. Exists specifically to power Cross-Asset Comparison (C5).
- **Explicitly out of scope for L1:** dynamic, per-instrument bond data (real-time yields, per-security detail) — still the weakest free-data category in India; a later-stage project.
- **Acceptance criteria:** at least FD rates (major banks) and current SGB/G-Sec yields are available and refresh on a defined schedule (e.g. weekly), feeding directly into C5.

### Deferred in Section J (placeholder text required)
- **J5. REITs (L2)** — Placeholder only; weakest free-data category, needs data-source investigation first.
- **J6. International Equities/Global Markets (L2)** — Placeholder only; separate data-sourcing + jurisdiction project.
- **J7. Any Asset Class, Any Geography (L3/L4)** — Placeholder: a "roadmap" mention, not a feature — the vision-slide destination.

---

## K. Platform-Level

### K1. Mobile-Responsive Web
- The site works well on phone browsers. Table stakes, no separate app needed for this.

### K2. Public Read-Only API
- A rate-limited, free-tier API for scores/fundamentals, layered on top of the API already being built for the frontend. **Acceptance criteria:** documented endpoints, sane rate limits, at minimum read access to asset fundamentals + current score.

### K3. Progressive Web App (resolves the Native Mobile App decision item)
- **Decision, recorded here as final for L1:** a fast, installable PWA — home-screen icon, app-like feel, zero app-store process — **not** a true native app. A native app is a separate codebase/skillset (iOS/Android-specific dev, app-store review, ongoing dual-platform maintenance) and directly conflicts with the free/solo/pre-revenue constraint your own original brief set. Revisit native only once there's a proven user base to justify the cost.
- **Acceptance criteria:** the site is installable as a PWA (manifest + service worker), adds a home-screen icon, and feels app-like (fast transitions, no visible browser chrome) on a phone.

### K4. Login via Google or Email
- Supabase Auth, both methods, out of the box.

### Deferred in Section K (placeholder text required)
- **K5. Multi-Language Support (L3)** — Placeholder only; substantial localization effort, waits for the English product to be fully proven.
- **K6. AI Assistant answering portfolio/research questions (L4)** — Placeholder only; genuinely achievable given your Claude-native setup, but deliberately sequenced *after* core data/scoring trust is fully established — a wrong AI answer about someone's money is a serious, reputation-defining risk on shaky underlying data.

---

## Appendix: cross-cutting rules that apply to every feature above (do not restate per-feature, but do not skip)

1. **Every stock/sector/score mention anywhere is a link** to that thing's page.
2. **Every "coming soon" placeholder explains what's coming**, in one sentence, in the UI itself — never a blank or generic message.
3. **Every score/research/calculator output uses "research signal" framing**, never "advice" or "recommendation" language.
4. **Every educational content point is paired with a visual** (picture/graph/graphic/flowchart) — text-only education content is a hard no per PROJECT_STATE.md.
5. **New ideas raised mid-build get a direct answer** — "same session" or "later phase," with reasoning — never silently deferred or silently accepted (this PRD is itself the record of that decision for everything already raised).

---

## What this PRD deliberately does NOT yet cover
- Exact page-by-page visual layout — see the companion `Wireframes.md`.
- Color palette, typography, component naming — see the companion `Design_System.md`.
- User journey maps (persona → entry point → path → outcome) — next deliverable after this one, per the Phase A sequence in `Updated_Project_Plan.md`.
- Branding (name/logo) — proposed inside the Design System document as directions for your decision, not decided here.

## Immediate open decisions needing your written call (tracked in PROJECT_STATE.md going forward)
1. ~~Mutual Funds in the same L1 window — extend timeline, or hold back?~~ **RESOLVED (Phase C):** stays in L1, scope narrowed to NAV + category + expense ratio + AUM; holdings-overlap deferred to L2. See Section 0 / J3.
2. ~~Newsletter cadence — literally daily, or a more sustainable 3–5x/week?~~ **RESOLVED (Phase C):** average 2x/week, SEO-driven articles + images. See G2.
3. ~~Confirm PWA (not native app) as final for L1~~ **RECONFIRMED (Phase C):** Avdhoot confirmed PWA remains final — no override. See K3.

All three "Immediate open decisions" items are now resolved.
