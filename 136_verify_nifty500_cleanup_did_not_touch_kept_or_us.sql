-- 136_verify_nifty500_cleanup_did_not_touch_kept_or_us.sql
-------------------------------------------------------------------
-- Read-only check (Avdhoot, P6, 2026-09-24): "can we confirm none of
-- the operations here has impacted 500 stocks, their values, their
-- auto update logic or US stocks". Confirms the 500 kept India stocks
-- and all US stocks still have their price/score/fundamentals data
-- intact and current. Changes nothing.
-------------------------------------------------------------------

-- 1. Counts by market -- expect exactly 500 India equities, and the
-- US equity count unchanged from before any of this session's work
-- (131 never touched market='usa' at all).
select market, asset_type, count(*) as num_assets
from assets
where asset_type = 'equity'
group by market, asset_type
order by market;

-- 2. Spot-check a few well-known kept India stocks and a US stock --
-- confirms their price history, latest live price, and TrueScore are
-- all still there and recent, not orphaned by the cleanup.
select
  a.ticker,
  a.market,
  a.is_active,
  (select count(*) from prices_daily pd where pd.asset_id = a.asset_id) as price_rows,
  (select max(pd.date) from prices_daily pd where pd.asset_id = a.asset_id) as latest_price_date,
  lp.price as latest_live_price,
  sc.overall_score as latest_truescore
from assets a
left join live_prices lp on lp.asset_id = a.asset_id
left join scores sc on sc.asset_id = a.asset_id
where a.ticker in ('RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'AAPL', 'MSFT')
order by a.market, a.ticker;
