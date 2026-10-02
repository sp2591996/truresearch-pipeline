-- 158_create_value_chain_tables.sql
-- -------------------------------------------------------------------
-- Value Chain feature (Avdhoot's Step 3/4 request, 2026-10-01).
-- Scope: India first. See /tmp (chat) "Value_Chain_Design.md" sent to
-- Avdhoot for the plain-English walkthrough this schema implements.
--
-- Core idea: Sector -> Industry -> Value-chain stage -> Segment ->
-- Sub-category -> Market pool -> Company is ONE generic tree
-- (adjacency list, parent_node_id), not fixed named columns -- this
-- is what lets Industry come before OR after the value-chain stage
-- depending on the sector, per Avdhoot's explicit requirement.
--
-- Run this in Supabase's SQL Editor. Safe to re-run.
-- -------------------------------------------------------------------

-- 1. The tree itself.
create table if not exists public.value_chain_nodes (
  node_id bigint generated always as identity primary key,
  parent_node_id bigint references public.value_chain_nodes(node_id),
  root_sector_id bigint references public.sectors(sector_id),  -- every node in a tree shares the same root sector, for fast "show me this whole tree" queries
  market text not null default 'india',
  node_type text not null check (node_type in (
    'sector', 'industry', 'value_chain_stage', 'segment', 'subcategory',
    'market_pool', 'company', 'unlisted_other'
  )),
  name text not null,
  slug text not null,                    -- used in the node's own page URL
  asset_id bigint references public.assets(asset_id),  -- set ONLY for node_type='company'; a company can have MULTIPLE node rows (one per offering), each with its own asset_id pointing to the same stock
  market_size_is_manual boolean not null default false,  -- true for 'market_pool' nodes where the number includes unlisted/unorganized market and so is typed in, not summed from children
  display_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.value_chain_nodes is
  'Generic tree for the Value Chain feature. Sector/Industry/Value-chain-stage/Segment/Sub-category/Market-pool/Company are all rows here, distinguished by node_type, linked by parent_node_id. A company appears as MULTIPLE rows (one per offering/segment it sits in) -- never one row holding its whole business.';

create index if not exists value_chain_nodes_parent_idx on public.value_chain_nodes(parent_node_id);
create index if not exists value_chain_nodes_root_sector_idx on public.value_chain_nodes(root_sector_id);
create index if not exists value_chain_nodes_asset_idx on public.value_chain_nodes(asset_id);

alter table public.value_chain_nodes enable row level security;
drop policy if exists "Public read access" on public.value_chain_nodes;
create policy "Public read access" on public.value_chain_nodes for select using (true);
grant select on public.value_chain_nodes to anon, authenticated;

-- 2. Financials for each node (revenue, growth) -- per period, so history
--    is kept rather than overwritten (same pattern as `scores`).
create table if not exists public.value_chain_node_financials (
  node_id bigint not null references public.value_chain_nodes(node_id),
  period_label text not null,            -- e.g. 'FY2026' or 'TTM-2026-09'
  as_of_date date not null,
  revenue numeric,                       -- this node's OWN attributed revenue (for a company node, the offering's revenue, NOT the company's total revenue)
  revenue_pct_of_company_total numeric,  -- company nodes only -- e.g. 0.75 for Swiggy's Food Delivery -- this IS the weight basis for the index
  past_3yr_cagr numeric,
  next_3yr_projected_growth numeric,
  data_source text,                      -- 'reported' / 'estimated' / 'admin_input'
  notes text,
  updated_at timestamptz not null default now(),
  primary key (node_id, period_label)
);

comment on table public.value_chain_node_financials is
  'Revenue + growth for a node, one row per reporting period. For category nodes (segment/sub-category/industry/sector), revenue is normally the SUM of children, computed and cached here by the scoring script. For market_pool nodes, revenue is typed in by hand (admin upload) and can exceed the sum of its company children, to account for unlisted/unorganized players.';

alter table public.value_chain_node_financials enable row level security;
drop policy if exists "Public read access" on public.value_chain_node_financials;
create policy "Public read access" on public.value_chain_node_financials for select using (true);
grant select on public.value_chain_node_financials to anon, authenticated;

-- 3. Index / TrueScore per node, computed daily (same cadence as the
--    main scoring pipeline).
create table if not exists public.value_chain_node_index (
  node_id bigint not null references public.value_chain_nodes(node_id),
  run_date date not null,
  index_value numeric,                   -- rebased to 100 at the node's first run_date
  day_change_pct numeric,
  weighted_truescore numeric,
  constituent_count integer,             -- how many LISTED companies contributed (unlisted/unorganized never counted here)
  created_at timestamptz not null default now(),
  primary key (node_id, run_date)
);

comment on table public.value_chain_node_index is
  'Daily index/TrueScore per node -- weighted average across only the LISTED company nodes in this subtree. Weight for each contributing company = (that company''s revenue_pct_of_company_total at ITS specific node) x (that company''s market cap). Unlisted companies and the unorganized/''Others'' bucket are shown on the page but never enter this weighted average.';

alter table public.value_chain_node_index enable row level security;
drop policy if exists "Public read access" on public.value_chain_node_index;
create policy "Public read access" on public.value_chain_node_index for select using (true);
grant select on public.value_chain_node_index to anon, authenticated;

-- 4. Qualitative content per node (the long list of questions Avdhoot
--    gave for stock-level offerings: positioning, branding, channels,
--    manufacturing, margins, regulatory moats, etc.) -- grouped into a
--    few logical JSON blocks rather than 20 separate columns, same
--    spirit as the existing stock_deepdive table's shape.
create table if not exists public.value_chain_node_content (
  node_id bigint primary key references public.value_chain_nodes(node_id),
  positioning_and_branding jsonb,        -- pricing/branding stance, key brands, price points, brand ambassadors
  manufacturing_and_sourcing jsonb,      -- own vs contracted, contractors + % split + price points, facility location/size/headcount (or, for services, where/contracted)
  channels_and_customers jsonb,          -- sales channel mix %, key B2B customers + their revenue share
  competitive_and_regulatory jsonb,      -- regulatory moats/challenges, margin quality vs competitors, business model notes
  updated_at timestamptz not null default now()
);

comment on table public.value_chain_node_content is
  'Qualitative write-up for a node (mainly company/offering-level nodes), grouped into 4 JSON blocks matching the admin upload''s tab structure. Feeds the stock-level thesis/scenarios/monitor/risks/management sections once enough of this is populated.';

alter table public.value_chain_node_content enable row level security;
drop policy if exists "Public read access" on public.value_chain_node_content;
create policy "Public read access" on public.value_chain_node_content for select using (true);
grant select on public.value_chain_node_content to anon, authenticated;
