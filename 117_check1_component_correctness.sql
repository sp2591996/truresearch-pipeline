-- 117_check1_component_correctness.sql
-------------------------------------------------------------------
-- Validation Check #1: internal correctness of the two NEW rating
-- components (Legacy Score, Volatility Score) in truescore_v4.
--
-- These are not predictions -- they're descriptive ratings, so the
-- right test isn't "did the stock go up", it's "does the ranking
-- make sense for real companies you'd recognize". This pulls a
-- deliberately mixed set: well-known old, large, stable blue chips
-- (should get HIGH Legacy and usually HIGH-ish Volatility scores,
-- since they trade calmly) alongside recently listed / smaller,
-- choppier names (should get LOWER Legacy scores, and often lower
-- Volatility scores if they swing around a lot).
--
-- Run this in Supabase's SQL Editor and share the table it returns.
-------------------------------------------------------------------

select
  a.ticker,
  a.name,
  a.listed_date,
  (current_date - a.listed_date) as days_listed,
  s.legacy_score,
  s.volatility_score,
  s.ml_rank_score,
  s.growth_score,
  s.relative_valuation_score,
  s.overall_score,
  s.truescore_rating
from scores s
join assets a on a.asset_id = s.asset_id
where s.formula_version = 'truescore_v4'
  and a.ticker in (
    -- well-known, old, large, stable blue chips -- expect HIGH legacy_score
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ITC', 'HINDUNILVR', 'SBIN', 'ONGC',
    -- recently listed / smaller, choppier, less established names -- expect LOWER legacy_score
    'IRCTC', 'NYKAA', 'ZOMATO', 'PAYTM', 'IDEA', 'YATRA', 'AWFIS', 'JIOFIN'
  )
order by s.legacy_score desc;
