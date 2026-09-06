# TrueResearch V2 — Design System & Branding Proposal (Phase A, Draft 1 — superseded in part, see Section 2b)

*Companion to `PRD.md`. Covers: name/logo direction, color palette, typography, and the reusable component library.*

---

## 1. Naming — **DECIDED: TrueResearch**

Chosen from a shortlist blending "clarity-first" and "confidence/judgment" naming directions: **TrueResearch** — *ClearVerdict*, *ClearRead*, and *ClearSignal* were the other finalists.

**Naming overlap, resolved:** the platform is TrueResearch; the 0-100 composite score feature is renamed **TrueScore** (previously "ClearScore" — this also resolves the earlier "TrueScore/TrueRank" naming pass, since the platform is no longer called TrueScore). The blended ML+valuation rating (previously "CS Rating Score") is now **TrueScore Rating**. This rename has been applied throughout `PRD.md`, `Wireframes.md`, and all wireframe/journey-map/logo artifacts.

**Logo — Concept B, "TR Monogram," still the shape.** A rounded-square badge with an interlocked T/R geometric mark — see Section 2b below for its updated coloring (the navy/gold fill described in the original Concept B is superseded; the interlocked-TR shape itself is unchanged). Works both as a full lockup (icon + "TrueResearch" wordmark) and as a standalone icon — the latter is what should be used for the app icon, browser favicon, and PWA home-screen icon (see `PRD.md` K3), since it reads clearly at small sizes without the wordmark.

---

## 2. Color palette — SUPERSEDED, see Section 2b

~~**DECIDED: Navy & Gold** (Direction 1)~~ — this was locked after Session 3/4 and used to build the first version of the Home page in Session 10. **Overridden later in Session 10**, at Avdhoot's request, in favor of matching the look of his older ClearStocks site — see Section 2b for the palette actually in use.

Original Navy & Gold values, kept here for history only (no longer applied anywhere in the codebase):

| Token | Light | Dark |
|---|---|---|
| Background | `#FAF8F4` | `#0A1826` |
| Surface / nav | `#0F2A4A` | `#081522` |
| Accent (gold) | `#C9A24B` | `#D9B96C` |
| Positive | `#1E7A46` | `#3E9A62` |
| Negative | `#B23B3B` | `#E07070` |
| Text (primary) | `#232323` | `#EDEAE3` |
| Text (muted) | `#5A5A5A` | `#A9A499` |

## 2a. Color palette — original two "classic finance" directions (reference only, superseded)

Both were built to pass accessibility contrast checks (WCAG AA) in both light and dark mode, and both avoid pure green/red as the *only* signal for gains/losses (colorblind-safe — paired with up/down icons, not color alone).

### Direction 1 — "Navy & Gold" (traditional, trust-forward)
- Primary: deep navy `#0F2A4A` (headers, primary buttons, nav)
- Accent: muted gold `#C9A24B` (TrueScore badges, highlights, CTAs)
- Background (light): warm off-white `#FAF8F4`
- Background (dark): near-black navy `#0A1826`
- Positive: forest green `#1E7A46` — Negative: brick red `#B23B3B`
- Neutral text: charcoal `#232323` (light mode) / off-white `#EDEAE3` (dark mode)
- **Feel:** established, bank-like, serious. Closest to Morningstar/traditional research houses.

### Direction 2 — "Slate & Teal" (modern, still credible)
- Primary: slate `#1E2A38` (headers, nav)
- Accent: teal `#2A9D8F` (scores, CTAs, links)
- Background (light): cool off-white `#F5F7F8`
- Background (dark): deep slate `#111820`
- Positive: teal-green `#2A9D6F` — Negative: coral-red `#D64545`
- Neutral text: dark slate `#20272E` (light) / light grey `#E3E7EA` (dark)
- **Feel:** cleaner, slightly more startup/fintech-modern. Closest to Tickertape/Groww's newer visual language.

---

## 2b. Color palette — **CURRENT, LOCKED: "Deep Space & Violet"** (matched from the old ClearStocks site, Session 10)

**Decision:** partway through building the Home page, Avdhoot asked to match the visual design and color scheme of his older ClearStocks static site (`https://sp2591996.github.io/clearstocks-website/`) instead of the Navy & Gold direction above. Confirmed explicitly (not a silent swap) — see `PROJECT_STATE.md` Session 10 for the decision record. This is now the locked palette; Navy & Gold is fully retired, not just deprioritized.

**Single dark theme — no separate light mode.** The old site never had a light variant, so unlike Navy & Gold this palette is dark-only for now. If a light mode is ever wanted, it needs its own design pass, not a token swap.

Exact hex values (pulled directly from the old site's live stylesheet, not re-guessed):

| Token | Value | Used for |
|---|---|---|
| Background | `#0A0A12` | Page background |
| Card | `#131320` | Card/panel background, search box, buttons |
| Card (raised) | `#1C1C2E` | Hover states, nav-link hover, neutral pills |
| Border | `#26263B` | Card borders, dividers, table lines |
| Text (primary) | `#F3F1FA` | Headings, body text |
| Text (muted) | `#8D89A6` | Secondary text, labels, placeholders |
| Green (positive) | `#22C55E` | Gains, "Strong"-tier scores |
| Green background | `rgba(34,197,94,.14)` | Positive pill fill |
| Red (negative) | `#F43F5E` | Losses, weak-tier scores |
| Red background | `rgba(244,63,94,.14)` | Negative pill fill |
| Accent (violet) | `#8B5CF6` | Primary accent — links, active nav, focus rings, score dial |
| Accent 2 (pink) | `#EC4899` | Paired with violet in the brand gradient (buttons, logo mark, nav underline) |
| Accent background | `rgba(139,92,246,.16)` | Active/selected state fill |
| Gold (amber) | `#F59E0B` | Mid-tier scores, sample/notice banners (incl. the Disclaimer Bar) |
| Gold background | `rgba(245,158,11,.14)` | Notice banner fill |

**Brand gradient:** `linear-gradient(120deg, #8B5CF6, #EC4899)` — used for the logo mark, primary buttons, active filter chips, and the 3px strip under the top nav.

**Score badge band** (unchanged rule, updated colors): red `#F43F5E` below 40, amber `#F59E0B` 40–69, green `#22C55E` at 70+ — rendered as a small conic-gradient dial (see the old site's `.score-badge .dial`), never color alone (the numeric score and, where relevant, a text label are always shown alongside).

**Logo mark, updated coloring:** the interlocked-TR badge now fills with the brand gradient (violet → pink) instead of navy/gold, white "TR" lettering on top — same shape as the original Concept B, new fill only.

---

## 3. Typography — updated (Session 10, matches Section 2b)

- **Headings & logo wordmark:** **Manrope**, weight 700–800 (matches the old ClearStocks site exactly). Superseded the earlier Georgia/Merriweather-style recommendation, which was written for the Navy & Gold direction.
- **Body & UI text:** **Inter**, weight 400–700 — a highly legible sans-serif, tabular figures for anything numeric (numbers align in columns — non-negotiable for a data-heavy product; numbers that don't align in a table look unprofessional immediately).
- **Numbers, tickers, scores, timestamps:** **IBM Plex Mono** with tabular figures, so "72" and "8" don't visually jump around next to each other — matches the old site's `.num` utility.

All three are loaded via Google Fonts, same mechanism as the earlier Geist fonts they replaced.

---

## 4. Core component library (built once, reused on every page)

| Component | Where it's used | Key states |
|---|---|---|
| **Score Badge** | TrueScore, TrueScore Rating, Market Mood gauge | 0–100 with color gradient (not just one color — red→amber→green band), rendered as a small conic-gradient dial (Section 2b); "Model Signal (experimental)" gets a visually distinct badge style (dashed outline) so it's never confused with a validated score |
| **Asset Card** | Curated lists, screener rows, watchlist | Ticker, name, price, 1-day change (icon + color), score badge, "why it's here" one-liner |
| **Sector Chip** | Everywhere a sector is mentioned | Small pill, links to sector page |
| **Placeholder Panel** | Every L2–L4 "coming soon" feature | Icon + one-sentence explanation of what's coming (never blank) |
| **Disclaimer Bar** | Every page with a score/research/calculator output | Compact, dismissible-per-session but never permanently hidden, "research signal, not advice"; styled amber/gold (Section 2b) since it's a notice, not an error |
| **Comparison Table** | Multi-stock/sector/cross-asset comparison | Supports 2–4 columns, sticky first column (asset name) on scroll |
| **Learn Callout** | Attached to any jargon term | Small "?" icon → inline plain-English explainer + link to full Learn article, always paired with a simple visual per the hard content rule |
| **Chart (line/candlestick)** | Price history, score history, sector trend | Consistent axis styling, consistent positive/negative color coding across every chart on the site |

Built so far (Session 10, in `trueresearch-frontend/components/`): Score Badge, Asset Card, Placeholder Panel, Disclaimer Bar, Learn Callout, plus a site-wide Nav and Footer. Not yet built: Sector Chip, Comparison Table, Chart.

---

## 5. Accessibility & consistency rules (apply everywhere)

- Never use color alone to convey gain/loss, risk, or score tier — always pair with an icon, label, or pattern.
- Every numeric table uses tabular figures and right-aligns numbers.
- Every score badge uses the same 0–100 scale and the same color band across the entire site (a "72" always means the same relative thing wherever it appears).
- **Dark mode is now the only mode** (Section 2b) — this replaces the earlier "dark mode is a first-class target, not an afterthought" rule, which assumed both a light and dark variant would exist.

---

## Next step
Naming, color (now Section 2b), typography, and the logo shape are all locked. Remaining component types (Sector Chip, Comparison Table, Chart) get built as the pages that need them are built — see `PROJECT_STATE.md` for the current build order.
