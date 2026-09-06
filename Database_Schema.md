# TrueResearch V2 — Database Schema (Phase B, Draft 1)

*Companion to `PRD.md`, `Design_System.md`, `Wireframes.md`, `PROJECT_STATE.md`. This is the full list of database tables Phase B will create in Supabase (Postgres), derived from a line-by-line pass through every PRD section. You don't need to know SQL to review this — just read the plain-English description of each table and flag anything you want changed before I create them.*

**How to read this:** each table lists its columns in plain language (not exact SQL types yet — that comes when I actually create them). "PRD ref" tells you which feature this supports, so you can cross-check against `PRD.md` if anything looks off. Tables marked **(populated later)** get their structure created now but stay empty until their own build phase — this satisfies PROJECT_STATE.md's "sized for" requirement without pretending we have data we don't.

---

## 1. Reference data (the backbone everything else links to)

### `sectors`
PRD ref: A3, B1
- sector_id, name, description (short), created_at

### `assets`
PRD ref: J1-J4 (every asset class is a row here)
- asset_id, ticker, name, asset_type (equity / gold / mutual_fund / debt / reit / intl_equity), sector_id, isin, yfinance_symbol, listed_date, is_active, created_at

### `sector_ratio_config`
PRD ref: B1 ("sector-specific ratios, not generic ones")
- sector_id, ratio_name, display_order — controls which ratios show/hide per sector on the stock detail page

---

## 2. Market data

### `prices_daily`
PRD ref: B1, B4, E1, C5 (5-year charts, historical export, return calculator, cross-asset comparison)
- asset_id, date, open, high, low, close, volume
- **One-time 5-year historical backfill planned for Phase B**, per our agreed decision

### `live_prices`
PRD ref: A4 (Market Movers, refreshed every 5 min)
- asset_id, price, prev_close, day_change_pct, updated_at

---

## 3. Fundamentals & scoring

### `fundamentals`
PRD ref: B1, B4 (migrated from your existing fundamentals_history CSVs)
- asset_id, fiscal_year_end_date, total_revenue, net_income, ebit, ebitda, total_debt, stockholders_equity, cash, total_assets, free_cash_flow, operating_cash_flow, capex, roe

### `ratios_snapshot`
PRD ref: B1
- asset_id, as_of_date, pe_ratio, pb_ratio, ev_ebitda, price_to_sales, roce, debt_equity, margin

### `scores`
PRD ref: B2 (TrueScore + TrueScore Rating — the core of the whole platform)
- asset_id, run_date, formula_version, relative_valuation_score, ml_rank_score, overall_score, truescore_rating
- **Design note (updated per your feedback):** the exact mix of factors that makes up `overall_score` is still to be decided and may differ stock to stock — so instead of hardcoding fixed columns for quality/growth/momentum/risk, only the two factors you're sure of today (relative valuation, ML rank) get dedicated columns here. Every other factor — current or future, universal or stock-specific — lives in the two flexible tables below, so adding, removing, or customizing factors later never requires changing this table's structure again.
- This table is inherently historical: a new row is added every `run_date`, nothing is overwritten, so "what did TrueScore say about Reliance on any past date" is always answerable directly from this table.

### `score_components` (NEW — flexible factor storage)
PRD ref: B2
- asset_id, run_date, formula_version, component_name (e.g. "relative_valuation", "ml_rank", or any future factor), component_value, component_weight_used
- One row per factor per stock per run. Today this means 2 rows per stock per run (relative_valuation, ml_rank). Adding a 3rd factor later — even just for one sector — never needs a schema change, just more rows.

### `score_component_weights` (NEW — the config for which factors apply where)
PRD ref: B2 ("to be decided for each stock")
- formula_version, sector_id (nullable = default for all sectors), asset_id (nullable = overrides the sector default for one specific stock), component_name, weight_pct
- This is where "the mix differs stock to stock" actually lives — a data change, not a code change.

### `score_formula_versions`
PRD ref: B2 ("formula versions stored so 'why did this change' is always answerable")
- formula_version, description, effective_date, changed_by_note

### `score_backtest_results` (NEW — your "how successful has TrueScore been" question)
PRD ref: B2, and PROJECT_STATE.md's "validate before expanding" rule
- backtest_id, formula_version, test_period_start, test_period_end, forward_return_window (e.g. 1M/3M/1Y), metric_type (e.g. "top-decile vs bottom-decile return spread", "rank correlation"), result_value, sector_id (nullable = whole universe), notes, run_at
- This is the one-time validation gate your PRD requires before TrueScore expands from 200 to 500 stocks.

### `score_performance_tracking` (NEW — the ongoing, living version of the same question)
PRD ref: B2
- date, formula_version, decile (1-10, stocks bucketed by score that day), avg_forward_return_1m, avg_forward_return_3m, avg_forward_return_1y
- Keeps building forever as new data comes in — this is also what eventually lets you show users an honest, continuously-updated "has this actually worked" answer, not a one-off report that goes stale.

### `peers`
PRD ref: B1 (top 3-5 peer stocks per stock)
- asset_id, peer_asset_id, rank

---

## 4. Written/qualitative content

### `sector_overviews`
PRD ref: A3
- sector_id, overview_text, size_growth_notes, policy_notes, last_updated

### `asset_qualitative`
PRD ref: A1 ("why it's here" one-liners), B5 (Recent Developments)
- asset_id, why_here_note, recent_developments_text, last_updated

### `management_profiles`
PRD ref: B9 (L1 placeholder: name+title only)
- asset_id, name, title, bio_text (nullable until fuller bios are researched)

### `insider_transactions`
PRD ref: B6
- asset_id, transaction_date, insider_name, transaction_type (buy/sell), quantity, price

### `shareholding_pattern`
PRD ref: B7
- asset_id, quarter_end_date, promoter_pct, fii_pct, dii_pct, public_pct

### `research_report_templates`
PRD ref: B3 (must exist before any report is drafted)
- template_id, sector_id (nullable = generic), structure_json, approved_at

### `research_reports`
PRD ref: B3
- report_id, asset_id, template_id, tier (flagship/summary), business_overview, growth_drivers, financials_summary, competitive_position, bull_case, bear_case, conclusion, published_at, last_reviewed_at

### `corporate_actions`
PRD ref: B5
- asset_id, action_type (dividend/split/bonus/buyback/results_date), action_date, details_text

### `glossary_terms`
PRD ref: G1
- term, plain_english_explanation, paired_visual_ref, related_page_links

### `learn_content`
PRD ref: G1 (beginner course + "how to use TrueResearch" guide)
- content_id, content_type (course_lesson/product_guide), title, body_text, order_index, paired_visual_ref

### `articles`
PRD ref: G2
- article_id, title, body_text, images, published_at

### `ipos`
PRD ref: H1
- ipo_id, company_name, sector_id, open_date, close_date, price_band, subscription_status, gmp, post_listing_performance

### `ipo_assessments`
PRD ref: H1 (DRHP write-ups, tiered/ongoing)
- ipo_id, assessment_text, status (in_progress/complete), last_updated

### `site_content_blocks` **(new, your catch)**
PRD ref: I1 (editable disclaimer text and similar copy, without a code deploy)
- block_key, text_content, last_updated

### `placeholder_copy` **(new, your catch)**
PRD ref: cross-cutting rule 2 ("every placeholder explains what's coming, never blank")
- feature_code (e.g. F1, B8, D6), placeholder_text

---

## 5. Discovery/browsing configuration

### `curated_list_configs`
PRD ref: A1
- list_key, display_name, ranking_rule_json, min_qualifying_stocks

### `themes`
PRD ref: A5 (3 launch themes)
- theme_key, display_name, filter_logic_json, launched_at

### `market_mood_daily`
PRD ref: A6
- date, mood_score, commentary_text, formula_version

### `preset_screens`
PRD ref: C2
- screen_key, display_name, filter_config_json

### `saved_comparisons`
PRD ref: C3 (shareable comparison URLs)
- share_slug, asset_ids (list), created_at

### `calculator_shares`
PRD ref: E1 (shareable calculator results)
- share_slug, calculator_type, inputs_json, created_at

---

## 6. Users, personas, and personalization

### `personas`
PRD ref: A2
- persona_key, display_name, description, biased_list_keys

### `questionnaire_questions` / `questionnaire_options`
PRD ref: A2 (persona quiz) and E4 (risk-profiling questionnaire) — **shared structure, tagged by type**, per your decision
- questionnaire_questions: question_id, questionnaire_type (persona/risk_profile), question_text, order_index
- questionnaire_options: option_id, question_id, option_text, maps_to_persona_or_risk_band

### `users`
PRD ref: K4 (extends Supabase's built-in auth with app-specific fields)
- user_id (from Supabase Auth), display_name, persona_key, risk_band, created_at

### `user_persona_responses`
PRD ref: A2
- user_id, question_id, selected_option_id, answered_at

### `watchlists`
PRD ref: D1
- user_id, asset_id, added_at

### `portfolio_holdings`
PRD ref: D2 (incremental entry — one row per holding, added one at a time)
- holding_id, user_id, asset_id, quantity, buy_price, buy_date

### `alert_subscriptions` **(new, placeholder toggle states)**
PRD ref: Section F (all 6 alert types, L1 = placeholder UI, but toggle state must persist)
- user_id, alert_type, target_id (e.g. saved_screen_id or asset_id), enabled

---

## 7. Multi-asset coverage (Gold, Mutual Funds, Debt)

Gold: no separate table — gold is simply a row in `assets` (asset_type = gold), using the same `prices_daily` table as equities. This is deliberate — it's the proof that the architecture generalizes beyond equities (per PRD J2's acceptance criteria).

### `mutual_funds` **(populated later, structure now)**
PRD ref: J3
- fund_id, name, category, expense_ratio, amc_name, aum

### `mutual_fund_nav_history` **(populated later)**
PRD ref: J3
- fund_id, date, nav

### `mutual_fund_holdings` **(populated later)**
PRD ref: J3 (category-relative scoring), B1 ("held by these N funds"), future C6 (overlap detector)
- fund_id, asset_id, weight_pct, as_of_date

### `debt_reference_rates` **(populated later)**
PRD ref: J4
- rate_type (fd_rate/sgb_yield/gsec_yield), bank_or_instrument_name, rate_pct, effective_date

---

## 8. Platform / operational

### `ingestion_runs`
PRD ref: replaces your existing `status.json`
- run_id, run_type (daily_prices/weekly_fundamentals/scoring), started_at, finished_at, ok_count, failed_count, failed_symbols

### `api_keys` **(populated later)**
PRD ref: K2 (public read-only API)
- api_key, owner_label, rate_limit_per_min, created_at

### `api_usage_log` **(populated later)**
PRD ref: K2
- api_key, endpoint, called_at

---

## Explicitly NOT built yet (deferred features, per PRD's own L2-L4 sequencing)
No tables for: credit rating tracking (B8), ESG indicators (B10), analyst ratings (B11), custom user formulas (C4), multi-broker import (D6), household aggregation (D7), what-if backtesting (E6), robo-advisory (E7), REIT/international equity real data (J5/J6 — placeholder only), structured courses beyond `learn_content` (G3), community discussion (G4), verified analyst contributions (G5), affiliate links (H2), model portfolios (H3), broker execution (H4), capital gains/tax reporting (I2), multi-language (K5), AI assistant (K6). These stay as UI-only placeholders until their own phase, per PROJECT_STATE.md.

## What happens next
Once you've reviewed this and flagged any changes, I'll create these tables in Supabase's SQL editor — I'll do this myself (Supabase lets me connect and run the setup directly), showing you each step so you can see exactly what's being created and why.
