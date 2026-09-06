-- ============================================================================
-- TrueResearch V2 — Phase B, Script 1: Create all tables
-- ============================================================================
-- What this does: creates every table from Database_Schema.md, empty, ready
-- to be filled in later steps. Safe to run once. If you ever need to run it
-- again after partial success, it's written so it won't error on tables
-- that already exist.
-- ============================================================================

create extension if not exists pgcrypto;

-- ----------------------------------------------------------------------------
-- 1. Reference data
-- ----------------------------------------------------------------------------

create table if not exists sectors (
  sector_id serial primary key,
  name text not null unique,
  description text,
  created_at timestamptz not null default now()
);

create table if not exists assets (
  asset_id serial primary key,
  ticker text not null,
  name text not null,
  asset_type text not null check (asset_type in ('equity','gold','mutual_fund','debt','reit','intl_equity')),
  sector_id integer references sectors(sector_id),
  isin text,
  yfinance_symbol text,
  listed_date date,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (ticker, asset_type)
);

create table if not exists sector_ratio_config (
  id serial primary key,
  sector_id integer not null references sectors(sector_id),
  ratio_name text not null,
  display_order integer not null default 0
);

-- ----------------------------------------------------------------------------
-- 2. Market data
-- ----------------------------------------------------------------------------

create table if not exists prices_daily (
  asset_id integer not null references assets(asset_id),
  date date not null,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume bigint,
  primary key (asset_id, date)
);

create table if not exists live_prices (
  asset_id integer primary key references assets(asset_id),
  price numeric,
  prev_close numeric,
  day_change_pct numeric,
  updated_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 3. Fundamentals & scoring
-- ----------------------------------------------------------------------------

create table if not exists fundamentals (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  fiscal_year_end_date date not null,
  total_revenue numeric,
  net_income numeric,
  ebit numeric,
  ebitda numeric,
  total_debt numeric,
  stockholders_equity numeric,
  cash numeric,
  total_assets numeric,
  free_cash_flow numeric,
  operating_cash_flow numeric,
  capex numeric,
  roe numeric,
  unique (asset_id, fiscal_year_end_date)
);

create table if not exists ratios_snapshot (
  asset_id integer not null references assets(asset_id),
  as_of_date date not null,
  pe_ratio numeric,
  pb_ratio numeric,
  ev_ebitda numeric,
  price_to_sales numeric,
  roce numeric,
  debt_equity numeric,
  margin numeric,
  primary key (asset_id, as_of_date)
);

create table if not exists scores (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  run_date date not null,
  formula_version text not null,
  relative_valuation_score numeric,
  ml_rank_score numeric,
  overall_score numeric,
  truescore_rating numeric,
  unique (asset_id, run_date, formula_version)
);

create table if not exists score_components (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  run_date date not null,
  formula_version text not null,
  component_name text not null,
  component_value numeric,
  component_weight_used numeric,
  unique (asset_id, run_date, formula_version, component_name)
);

create table if not exists score_component_weights (
  id serial primary key,
  formula_version text not null,
  sector_id integer references sectors(sector_id),
  asset_id integer references assets(asset_id),
  component_name text not null,
  weight_pct numeric not null
);

create table if not exists score_formula_versions (
  formula_version text primary key,
  description text,
  effective_date date not null default current_date,
  changed_by_note text
);

create table if not exists score_backtest_results (
  backtest_id serial primary key,
  formula_version text not null,
  test_period_start date not null,
  test_period_end date not null,
  forward_return_window text not null,
  metric_type text not null,
  result_value numeric,
  sector_id integer references sectors(sector_id),
  notes text,
  run_at timestamptz not null default now()
);

create table if not exists score_performance_tracking (
  id serial primary key,
  date date not null,
  formula_version text not null,
  decile integer not null check (decile between 1 and 10),
  avg_forward_return_1m numeric,
  avg_forward_return_3m numeric,
  avg_forward_return_1y numeric,
  unique (date, formula_version, decile)
);

create table if not exists peers (
  asset_id integer not null references assets(asset_id),
  peer_asset_id integer not null references assets(asset_id),
  rank integer not null,
  primary key (asset_id, peer_asset_id)
);

-- ----------------------------------------------------------------------------
-- 4. Written / qualitative content
-- ----------------------------------------------------------------------------

create table if not exists sector_overviews (
  sector_id integer primary key references sectors(sector_id),
  overview_text text,
  size_growth_notes text,
  policy_notes text,
  last_updated timestamptz not null default now()
);

create table if not exists asset_qualitative (
  asset_id integer primary key references assets(asset_id),
  why_here_note text,
  recent_developments_text text,
  last_updated timestamptz not null default now()
);

create table if not exists management_profiles (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  name text not null,
  title text,
  bio_text text
);

create table if not exists insider_transactions (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  transaction_date date not null,
  insider_name text,
  transaction_type text check (transaction_type in ('buy','sell')),
  quantity numeric,
  price numeric
);

create table if not exists shareholding_pattern (
  asset_id integer not null references assets(asset_id),
  quarter_end_date date not null,
  promoter_pct numeric,
  fii_pct numeric,
  dii_pct numeric,
  public_pct numeric,
  primary key (asset_id, quarter_end_date)
);

create table if not exists research_report_templates (
  template_id serial primary key,
  sector_id integer references sectors(sector_id),
  structure_json jsonb not null,
  approved_at timestamptz
);

create table if not exists research_reports (
  report_id serial primary key,
  asset_id integer not null references assets(asset_id),
  template_id integer references research_report_templates(template_id),
  tier text check (tier in ('flagship','summary')),
  business_overview text,
  growth_drivers text,
  financials_summary text,
  competitive_position text,
  bull_case text,
  bear_case text,
  conclusion text,
  published_at timestamptz,
  last_reviewed_at timestamptz
);

create table if not exists corporate_actions (
  id serial primary key,
  asset_id integer not null references assets(asset_id),
  action_type text check (action_type in ('dividend','split','bonus','buyback','results_date')),
  action_date date not null,
  details_text text
);

create table if not exists glossary_terms (
  term text primary key,
  plain_english_explanation text not null,
  paired_visual_ref text,
  related_page_links text[]
);

create table if not exists learn_content (
  content_id serial primary key,
  content_type text check (content_type in ('course_lesson','product_guide')),
  title text not null,
  body_text text,
  order_index integer not null default 0,
  paired_visual_ref text
);

create table if not exists articles (
  article_id serial primary key,
  title text not null,
  body_text text,
  images text[],
  published_at timestamptz
);

create table if not exists ipos (
  ipo_id serial primary key,
  company_name text not null,
  sector_id integer references sectors(sector_id),
  open_date date,
  close_date date,
  price_band text,
  subscription_status text,
  gmp numeric,
  post_listing_performance jsonb
);

create table if not exists ipo_assessments (
  ipo_id integer primary key references ipos(ipo_id),
  assessment_text text,
  status text check (status in ('in_progress','complete')) default 'in_progress',
  last_updated timestamptz not null default now()
);

create table if not exists site_content_blocks (
  block_key text primary key,
  text_content text not null,
  last_updated timestamptz not null default now()
);

create table if not exists placeholder_copy (
  feature_code text primary key,
  placeholder_text text not null
);

-- ----------------------------------------------------------------------------
-- 5. Discovery / browsing configuration
-- ----------------------------------------------------------------------------

create table if not exists curated_list_configs (
  list_key text primary key,
  display_name text not null,
  ranking_rule_json jsonb not null,
  min_qualifying_stocks integer default 1
);

create table if not exists themes (
  theme_key text primary key,
  display_name text not null,
  filter_logic_json jsonb not null,
  launched_at timestamptz
);

create table if not exists market_mood_daily (
  date date primary key,
  mood_score numeric,
  commentary_text text,
  formula_version text
);

create table if not exists preset_screens (
  screen_key text primary key,
  display_name text not null,
  filter_config_json jsonb not null
);

create table if not exists saved_comparisons (
  share_slug text primary key,
  asset_ids integer[] not null,
  created_at timestamptz not null default now()
);

create table if not exists calculator_shares (
  share_slug text primary key,
  calculator_type text not null,
  inputs_json jsonb not null,
  created_at timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 6. Users, personas, personalization
-- ----------------------------------------------------------------------------

create table if not exists personas (
  persona_key text primary key,
  display_name text not null,
  description text,
  biased_list_keys text[]
);

create table if not exists questionnaire_questions (
  question_id serial primary key,
  questionnaire_type text not null check (questionnaire_type in ('persona','risk_profile')),
  question_text text not null,
  order_index integer not null default 0
);

create table if not exists questionnaire_options (
  option_id serial primary key,
  question_id integer not null references questionnaire_questions(question_id),
  option_text text not null,
  maps_to text
);

-- Note: `users` links to Supabase's built-in auth.users table via user_id.
create table if not exists users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  persona_key text references personas(persona_key),
  risk_band text,
  created_at timestamptz not null default now()
);

create table if not exists user_persona_responses (
  id serial primary key,
  user_id uuid not null references users(user_id),
  question_id integer not null references questionnaire_questions(question_id),
  selected_option_id integer not null references questionnaire_options(option_id),
  answered_at timestamptz not null default now()
);

create table if not exists watchlists (
  user_id uuid not null references users(user_id),
  asset_id integer not null references assets(asset_id),
  added_at timestamptz not null default now(),
  primary key (user_id, asset_id)
);

create table if not exists portfolio_holdings (
  holding_id serial primary key,
  user_id uuid not null references users(user_id),
  asset_id integer not null references assets(asset_id),
  quantity numeric not null,
  buy_price numeric not null,
  buy_date date not null
);

create table if not exists alert_subscriptions (
  id serial primary key,
  user_id uuid not null references users(user_id),
  alert_type text not null,
  target_id text,
  enabled boolean not null default true
);

-- ----------------------------------------------------------------------------
-- 7. Multi-asset coverage (Gold uses `assets` + `prices_daily` directly)
-- ----------------------------------------------------------------------------

create table if not exists mutual_funds (
  fund_id serial primary key,
  name text not null,
  category text,
  expense_ratio numeric,
  amc_name text,
  aum numeric
);

create table if not exists mutual_fund_nav_history (
  fund_id integer not null references mutual_funds(fund_id),
  date date not null,
  nav numeric not null,
  primary key (fund_id, date)
);

create table if not exists mutual_fund_holdings (
  fund_id integer not null references mutual_funds(fund_id),
  asset_id integer not null references assets(asset_id),
  weight_pct numeric,
  as_of_date date not null,
  primary key (fund_id, asset_id, as_of_date)
);

create table if not exists debt_reference_rates (
  id serial primary key,
  rate_type text not null check (rate_type in ('fd_rate','sgb_yield','gsec_yield')),
  bank_or_instrument_name text not null,
  rate_pct numeric not null,
  effective_date date not null
);

-- ----------------------------------------------------------------------------
-- 8. Platform / operational
-- ----------------------------------------------------------------------------

create table if not exists ingestion_runs (
  run_id serial primary key,
  run_type text not null check (run_type in ('daily_prices','weekly_fundamentals','scoring')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  ok_count integer,
  failed_count integer,
  failed_symbols text[]
);

create table if not exists api_keys (
  api_key text primary key default encode(gen_random_bytes(24), 'hex'),
  owner_label text,
  rate_limit_per_min integer not null default 60,
  created_at timestamptz not null default now()
);

create table if not exists api_usage_log (
  id bigserial primary key,
  api_key text not null references api_keys(api_key),
  endpoint text not null,
  called_at timestamptz not null default now()
);

-- ============================================================================
-- Done. Next script will load your existing 199-stock data into these tables.
-- ============================================================================
