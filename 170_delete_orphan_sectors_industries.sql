-- =====================================================================
-- 170_delete_orphan_sectors_industries.sql
--
-- Run this ONLY AFTER 169_reclassify_unclassified_stocks.sql has been
-- run and its verify query returned zero rows.
--
-- v2: a first attempt at this (deleting straight from industries/
-- sectors) failed with a foreign-key error, because other tables
-- still point at the industries/sectors we're removing. Found via
-- find_dependent_tables.sql:
--   industries  <- industry_scores (industry_id)
--   sectors     <- assets, industries, ipos, research_report_templates,
--                   score_backtest_results, score_component_weights,
--                   sector_overviews, sector_ratio_config, sector_scores,
--                   value_chain_nodes (root_sector_id)
--
-- Policy used below:
--   - industry_scores / sector_scores / sector_overviews /
--     sector_ratio_config are PURELY DERIVED FROM the sector/industry
--     itself (scores, display config, overview text) -- if the
--     sector/industry is gone, this content is meaningless, so we
--     DELETE those rows.
--   - ipos / research_report_templates / score_backtest_results /
--     score_component_weights / value_chain_nodes hold real content
--     of their own (an actual IPO record, a template, a backtest
--     result, a weighting rule, a value-chain pilot) that would still
--     be meaningful without a sector tag -- the schema already treats
--     sector_id as nullable/optional on these. So we just SET
--     sector_id (or root_sector_id) TO NULL there instead of deleting
--     the row, to avoid losing real data.
--
-- SAFE ORDER: run the two PREVIEW selects first and read them. Only
-- run the DELETE/UPDATE statements once you're happy with what
-- they'll affect.
-- =====================================================================

-- PREVIEW: industries that would be deleted (0 stocks after Phase 1)
select i.industry_id, i.name, s.name as sector_name, i.market
from industries i
left join sectors s on s.sector_id = i.sector_id
where not exists (select 1 from assets a where a.industry_id = i.industry_id)
order by i.market, sector_name, i.name;

-- PREVIEW: sectors that would be deleted (0 stocks after Phase 1,
-- directly or via any industry)
select s.sector_id, s.name, s.market
from sectors s
where not exists (select 1 from assets a where a.sector_id = s.sector_id)
order by s.market, s.name;

-- -------- once the previews above look right, run everything below --------

-- 1) Derived/display content tied to the dying industries/sectors --
--    delete it, it has no meaning once the industry/sector is gone.

delete from industry_scores
where industry_id in (
  select i.industry_id from industries i
  where not exists (select 1 from assets a where a.industry_id = i.industry_id)
);

delete from sector_scores
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

delete from sector_overviews
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

delete from sector_ratio_config
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

-- 2) Real content that just happens to reference a dying sector --
--    keep the row, just detach it from the sector (NULL it out).

update ipos
set sector_id = null
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

update research_report_templates
set sector_id = null
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

update score_backtest_results
set sector_id = null
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

update score_component_weights
set sector_id = null
where sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

update value_chain_nodes
set root_sector_id = null
where root_sector_id in (
  select s.sector_id from sectors s
  where not exists (select 1 from assets a where a.sector_id = s.sector_id)
);

-- 3) Now it's safe to delete the orphaned industries themselves
delete from industries i
where not exists (select 1 from assets a where a.industry_id = i.industry_id);

-- 4) ...and then the orphaned sectors (must run AFTER the industries
--    delete above, since industries.sector_id also references these)
delete from sectors s
where not exists (select 1 from assets a where a.sector_id = s.sector_id);
