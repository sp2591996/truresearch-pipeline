# TrueResearch V2 — Wireframes, Text Layout (Phase A, Draft 1)

*Companion to `PRD.md` and `Design_System.md`. **A visual version of this document (numbered boxes, click-through per page) is published separately — use that one to actually see the layout; use this file as the written backup/reference.** Each page lists its blocks in the order they appear, top to bottom, with what's in each block.*

**Nav change (Session 3):** dropped "Stocks" from the top nav — Screener already covers browsing (no filters applied = the full list), so a separate "Stocks" link was redundant. Top nav is now: **Home / Screener / Research / IPOs / Learn / My TrueResearch**.

---

## Home
1. **Top nav:** logo/name, Home / Screener / Research / IPOs / Learn / My TrueResearch, search bar (always visible, top priority — most users arrive knowing a company name), login/account.
2. **Hero band:** one-line value prop + big search bar (duplicated from nav for prominence).
3. **Persona quiz prompt** (first visit only, dismissible): "Answer 3 quick questions so we show you the right stuff."
4. **Curated lists row:** 3–4 cards (Top Rated / Undervalued / High Growth / High Quality), each a mini-table of 5 stocks with a "see all" link.
5. **Market Movers strip:** Gainers / Losers / Most Active, compact 3-column.
6. **Market Mood gauge:** single number + one-line commentary.
7. **Learn teaser:** "New to investing? Start here" card linking to the beginner course.
8. **Footer:** disclaimer bar, links to Learn/glossary, About, links to sector pages.

---

## Stock / Asset Detail Page
*Order matters — conclusion before evidence, per the original plan.*
1. **Header:** name, ticker, exchange, live price, day change (icon+color), sector chip (linked), "add to watchlist" button.
2. **TrueScore + Why:** big score badge, one-paragraph plain-English "why this score," component breakdown (Quality/Growth/Valuation/Momentum/Risk) as 5 small bars/badges, TrueScore Rating shown as a visually distinct second badge.
3. **Financial health:** margins, debt/equity, ROE/ROCE — sector-appropriate ratio set only.
4. **Valuation:** P/E, P/B, EV/EBITDA vs. own 5-yr median and vs. sector median, side by side.
5. **Performance:** price chart with 1M/6M/1Y/5Y toggles, historic returns table, "is this a Market Mover today?" flag if applicable.
6. **Shareholding pattern:** stacked-area chart, last 4+ quarters (promoter/FII/DII/public).
7. **Mutual fund exposure:** **Placeholder Panel** (per Design_System.md's component library) reading something like "Fund holdings data coming soon" — this section is NOT a live list at launch. It requires portfolio-holdings data, which is explicitly deferred to L2 (Phase C scope decision — see `PRD.md` J3/C6): India has no free, structured, cross-fund holdings API (only monthly PDF factsheets per fund house), so this can't ship honestly at L1. Do not build this as a live section until C6 (Mutual Fund Overlap Detector) actually ships.
8. **Corporate actions & recent developments:** upcoming dates + "Recent Developments" written notes.
9. **Insider/promoter activity:** recent buy/sell entries.
10. **Peers:** top 3–5 peer stocks, linked.
11. **Written research:** flagship report or auto-summary, whichever tier applies, clearly labeled which tier it is.
12. **Disclaimer bar** (sticky or repeated near every score/valuation block).

---

## Mutual Fund Detail Page (new, Phase C — J3 scope: NAV + category + expense ratio + AUM)
*Deliberately structured to mirror the Stock/Asset Detail Page above, since J2 (Gold) already proved the architecture generalizes across asset types — reuses the same components (Score Badge, Asset Card, Disclaimer Bar) rather than a one-off design.*
1. **Header:** fund name, fund house (AMC), category chip (linked to a category-filtered fund list, same pattern as a Sector Chip), current NAV + day change, "add to watchlist" button.
2. **Category-relative score:** score badge showing how this fund ranks within its own category (not cross-category — a Large Cap fund is only meaningfully compared to other Large Cap funds), one-paragraph plain-English "why this score," same visual language as TrueScore but a distinct badge style so it's never confused with equity TrueScore.
3. **Key facts strip:** AUM, expense ratio, fund category, launch date — sector-appropriate style, tabular figures per `Design_System.md` rules.
4. **NAV performance:** NAV history chart with 1M/6M/1Y/5Y toggles (same chart component as the stock page's price chart), historic returns table.
5. **Category peers:** top 3–5 other funds in the same category, linked — mirrors the stock page's Peers block.
6. **Portfolio holdings:** **Placeholder Panel** — "Holdings data coming soon" (same honesty rule as the stock page's mutual-fund-exposure placeholder; this is the same underlying gap, viewed from the fund's side instead of the stock's side). Do not build as a live section until C6 ships.
7. **Disclaimer bar** (sticky or repeated, same as every score/valuation page).

---

## Sector Page
1. Sector name + one-paragraph written overview (size, growth, landscape, policy context).
2. Sector-average ratio strip.
3. Sector trend chart.
4. Top 10 stocks in sector (table, linked).
5. Top 5 mutual funds **investing in this space** — labeled this way deliberately, not "exposed to" or "holding": this is a **category-based match** (fund's AMFI category aligns with the sector, ranked by AUM), not true holdings-based overlap, since holdings data doesn't exist yet at L1 (see `PRD.md` J3/A3 scope note). Each fund name links to its Mutual Fund Detail Page.
6. "This sector appears in: [curated lists]" internal-linking block.

---

## Screener
1. Filter panel (left sidebar or top drawer on mobile): market cap, sector, growth, quality, valuation, momentum, TrueScore range sliders/dropdowns.
2. Preset screen chips above the results table (High Growth, Undervalued, QARP, etc.).
3. Results table: sortable columns, checkbox per row to add to a comparison (3–4 max).
4. "Compare selected" button → C3 comparison page.
5. Sector-vs-sector toggle (switches the whole screener into sector-aggregate mode).
6. **Asset-type toggle (new, Phase C):** Equities / Mutual Funds / Gold — switching to Mutual Funds swaps the filter set to category, AUM, expense ratio, category-relative score (reuses the same table/filter-panel component, different columns and filter fields only, not a separate page).

**Built (Session 11):** items 2 and 3 above are live — checkbox multi-select (max 4) plus 3 preset chips (Top Rated / Undervalued by P/E / Large Cap) with a "Compare selected" action bar linking to `/compare`. Sector-vs-sector toggle and the asset-type toggle are not yet built.

---

## Comparison Page (X vs Y [vs Z, vs W])
1. Header row: each stock's name/ticker/price as a column.
2. Metric rows: growth, margins, ROE, debt, P/E, TrueScore, performance — one row per metric, one column per stock.
3. Shareable URL shown/copyable.
4. "Add another" (up to 4 total).

**Built (Session 11) — actual shipped layout, supersedes the sketch above:**
1. Header row: page title, "← Back to Screener" link, and the Add-stock control (see below) inline.
2. Table header row is **sticky** within its own scroll container (`max-h-[70vh] overflow-auto` on the table wrapper, not the page) — first column is the metric label, one column per stock (ticker, name, sector chip).
3. Rows are grouped into 5 labeled sections rather than a flat metric list: **TrueScore & Performance**, **Profitability**, **Valuation & Size**, **Shareholding**, **TrueScore Breakdown**. A metric row is omitted entirely (not shown as blank dashes) if not one of the selected stocks has data for it; an empty section is omitted too.
4. The best value in a row gets a small **"✓ Best" badge** next to the cell — no full-cell background highlight (the earlier version did this and looked unprofessional; changed per feedback).
5. Scrollbar inside the table container is custom-styled (`.tr-scroll-thin` in `Design_System.md`) to match the dark theme instead of the OS-default scrollbar.
6. **"Add stock to compare"** (replaces item 4's plain "Add another"): a dashed-border button that reveals a live search box (ticker/name match) right on the Compare page itself — no trip back to Screener needed. Disabled with a "Comparing the max of 4 stocks" message once at the cap.
7. Shareable URL (`/compare?tickers=...`) — as originally planned, no extra work needed since state lives in the URL.

---

## Research Report Page
1. Standardized template header: company name, report tier (Flagship/Summary), last-updated date.
2. Business overview.
3. Growth drivers.
4. Financial performance summary.
5. Competitive position + peer table.
6. Bull case / Bear case (two clearly separated columns or stacked blocks).
7. Recent developments (annual report findings, management commentary, news — refreshed each revisit).
8. Conclusion — framed as "research signal," never "buy/sell."
9. Disclaimer bar.

---

## IPO Tracker
1. Upcoming IPOs list: name, expected date, price band, sector, subscription status, GMP.
2. Recent/listed IPOs: post-listing performance chart.
3. Per-IPO detail page: prospectus summary, DRHP assessment (where written — tiered, may show "assessment in progress" for newer IPOs), financials, valuation vs. peers, risk factors — no recommendation language anywhere.

**Status (Session 12): built.** `/ipos` and `/ipos/[ipoId]` are live against real NSE data, mainboard IPOs only (SME/NSE-Emerge excluded). DRHP assessment content (business summary, industry summary, objects of the offer, top risks, financial summary table) is populated automatically by a document-parsing script rather than written by hand — see PRD.md H1's status note for how. Still outstanding: the visual redesign of both pages (logos, less plain card layout) flagged as a follow-up.

---

## Learn / Glossary
1. Search/filter bar for terms.
2. Term list grouped alphabetically or by topic (Basics / Ratios / Asset Classes / How TrueResearch Works).
3. Each term page: plain-English explanation + one paired visual (mandatory), links to where this term appears live on the site.
4. Beginner course as its own structured section (lesson list, progress indicator once logged in).
5. "How to use TrueResearch" product guide as a separate sub-section.

---

## Watchlist / Portfolio ("My TrueResearch")
1. Tabs: Watchlist / Portfolio / Saved Screens / Recently Viewed.
2. **Watchlist tab:** table of saved stocks + combined-bundle return summary (1M/1Y/5Y) at the top.
3. **Portfolio tab:** "add a holding" quick-entry (ticker, qty, buy price/date — one at a time, no forced full form), current value/gain-loss summary, diversification/concentration flags, vs.-other-assets comparison line, absolute-return figure (labeled, XIRR placeholder noted as coming).
4. **Saved Screens tab:** list of saved filter presets, each with a "Get notified" placeholder toggle.
5. **Recently Viewed tab:** simple chronological list.

---

## Calculators (Return / SIP / Lumpsum / SWP / Retirement / Risk-Profile / EMI / Tax)
1. Shared calculator page shell: input form (left or top) → result panel (right or below) with a chart where relevant.
2. Each calculator is its own URL (SEO value), linked from a central "Calculators" hub page listing all of them with a one-line description each.
3. Risk-profiling calculator's result panel explicitly uses illustrative/educational framing copy, not recommendation language.

---

## Cross-cutting notes for whoever builds these (you, future sessions, or me in Phase B/C)
- Every wireframe above assumes the Disclaimer Bar and Learn Callout components from `Design_System.md` are available site-wide — build those two components first, before any individual page.
- Every placeholder panel referenced in `PRD.md` (Section F alerts, B8–B11, etc.) uses the same **Placeholder Panel** component — one component, many instances, not one-off designs per feature.
- Mobile layout: stacks these blocks vertically in the same order; the filter panel on Screener becomes a slide-up drawer rather than a sidebar.

## Next step
Once you've picked a naming/color direction from `Design_System.md`, the next deliverable in the Phase A sequence is the **user journey maps** (persona → entry point → path through the product → outcome, for all 5 personas) — say the word and I'll build those next, referencing these wireframes directly.
