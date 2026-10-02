-- 162_add_market_size_range_columns.sql
-- -------------------------------------------------------------------
-- Avdhoot's feedback on the Food Delivery / Quick Commerce value-chain
-- stages: a stage's "market size" (the manually-entered figure that's
-- meant to cover the WHOLE market, including unlisted/unorganized
-- players -- see market_size_is_manual on value_chain_nodes) should be
-- shown as a RANGE (a to b), and that range must sit above the sum of
-- the listed companies' revenue beneath it, not just a single point
-- estimate.
--
-- value_chain_node_financials only ever had one `revenue` column, so
-- the previous manual-market-size script (161_...) had to collapse an
-- approved range down to its midpoint before storing it, with the
-- full range only mentioned in the `notes` text. This adds two
-- explicit numeric columns so the range itself is real data the
-- frontend can display, not just prose buried in a notes field.
--
-- `revenue` is still populated (set to the range's midpoint) for any
-- row that also sets market_size_min/max -- it's what 160_calculate_
-- value_chain_index.py's rollup_node() sums into a parent's total,
-- same as before. market_size_min/max are purely for display.
--
-- Run this in Supabase's SQL Editor. Safe to re-run.
-- -------------------------------------------------------------------

alter table public.value_chain_node_financials
  add column if not exists market_size_min numeric,
  add column if not exists market_size_max numeric;

comment on column public.value_chain_node_financials.market_size_min is
  'Low end of the manually-entered total market size range (only set on market_size_is_manual=true nodes, e.g. a value_chain_stage covering unlisted/unorganized players too). NULL for ordinary rollup/company rows.';
comment on column public.value_chain_node_financials.market_size_max is
  'High end of the manually-entered total market size range. `revenue` on the same row is set to the midpoint of [market_size_min, market_size_max] and is what rollups to the parent use -- market_size_min/max are for display only.';
