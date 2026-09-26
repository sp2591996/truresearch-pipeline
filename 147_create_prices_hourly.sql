-- 147_create_prices_hourly.sql
-------------------------------------------------------------------
-- Hourly price bars for the last 7 days only (stock page 1 Day / 1 Week
-- chart, and the sector index's 1 Day / 1 Week chart, which is computed
-- from these same stock bars -- no separate sector table).
--
-- Memory stays small on purpose: rows older than 7 days are deleted by
-- roll_up_and_purge_prices_hourly() below. Nothing is lost by that,
-- because prices_daily already holds each day's OHLC bar (written by the
-- normal daily price refresh); the function also fills in any day that
-- has hourly bars but is missing its daily bar, so a day always ends up
-- as a daily row before its hourly rows are removed.
--
-- Run this whole file once in the Supabase SQL Editor. Safe to re-run.
-------------------------------------------------------------------

create table if not exists prices_hourly (
  asset_id integer not null references assets(asset_id),
  ts timestamptz not null,          -- start of the hourly bar, stored in UTC
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume bigint,
  primary key (asset_id, ts)
);

create index if not exists prices_hourly_ts_idx on prices_hourly (ts);

alter table prices_hourly enable row level security;
drop policy if exists "Hourly prices are public to read" on prices_hourly;
create policy "Hourly prices are public to read" on prices_hourly for select using (true);
grant select on prices_hourly to anon, authenticated;
grant all on prices_hourly to service_role;

-- Turns hourly bars into daily bars where a daily bar is missing, then
-- deletes hourly rows older than 7 days. Only completed days (before
-- today in each exchange's own timezone) are converted. Idempotent.
create or replace function roll_up_and_purge_prices_hourly()
returns void
language plpgsql
security definer
as $$
begin
  insert into prices_daily (asset_id, date, open, high, low, close, volume)
  select h.asset_id,
         h.d,
         (array_agg(h.open  order by h.ts asc))[1],
         max(h.high),
         min(h.low),
         (array_agg(h.close order by h.ts desc))[1],
         sum(h.volume)
  from (
    select ph.*,
           (ph.ts at time zone case when a.market = 'india' then 'Asia/Kolkata' else 'America/New_York' end)::date as d,
           (now() at time zone case when a.market = 'india' then 'Asia/Kolkata' else 'America/New_York' end)::date as today_local
    from prices_hourly ph
    join assets a on a.asset_id = ph.asset_id
  ) h
  where h.d < h.today_local
  group by h.asset_id, h.d
  on conflict (asset_id, date) do nothing;

  delete from prices_hourly where ts < now() - interval '7 days';
end;
$$;

revoke all on function roll_up_and_purge_prices_hourly() from public, anon, authenticated;
grant execute on function roll_up_and_purge_prices_hourly() to service_role;
