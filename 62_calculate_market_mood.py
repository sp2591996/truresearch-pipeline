"""
62_calculate_market_mood.py
-------------------------------------------------------------------
Computes the daily Market Mood gauge (PRD.md A6, marketmood_v1) and
writes one row to `market_mood` (see 61_add_market_mood_table.sql).

Deliberately built on ONE data source -- `prices_daily`'s existing
daily closes for the whole Nifty 500 equity universe -- so the exact
same formula either runs live for today, or backtests against any
past date, with no separate code path and nothing that only works
"live." That's what makes the --backtest mode below a genuine
validation of the real formula, not a simulation of it.

The three sub-scores (all 0-100, documented in 61_add_market_mood_table.sql):
  1. Breadth   -- % of stocks whose close rose vs the previous trading day.
  2. Momentum  -- % of stocks trading above their own trailing 50-day
                  simple moving average of daily closes.
  3. Volatility -- each stock's most recent 20-day realized volatility
                  (stdev of daily returns) is compared to its OWN
                  trailing ~1-year history of 20-day volatility
                  readings, giving a percentile (0=calmest ever,
                  1=most turbulent ever). The market-wide MEDIAN of
                  those percentiles is inverted (1 - median) * 100,
                  so a calmer-than-usual market scores higher.

overall_score is a plain, equal-weight average of the three -- v1,
documented as such, the same way TrueScore started at v1 before any
reweighting. A stock needs at least ~280 trading days of history to
count toward volatility_score (long enough for a trailing-year
percentile); stocks with less are still counted for breadth/momentum
if they have enough for those (2 days / 50 days respectively). Every
sub-score's denominator (universe_count) is tracked per-score
implicitly by only ever dividing by however many stocks actually had
enough data -- a stock missing data is left out, never counted as a
zero.

Usage:
    python 62_calculate_market_mood.py
        Computes and upserts today's row (run_date = latest trading
        day found in prices_daily).

    python 62_calculate_market_mood.py --backtest 90
        Recomputes the last 90 distinct trading days found in
        prices_daily and upserts all of them -- lets you SEE the
        formula's actual day-to-day behavior over real history before
        trusting it, same purpose as TrueScore_Validation_Report.md.
        Prints a summary table instead of just "done."
-------------------------------------------------------------------
"""
import sys
from datetime import datetime, timezone

import pandas as pd

from db_client import get_client

FORMULA_VERSION = "marketmood_v1"
MOMENTUM_WINDOW = 50
VOL_WINDOW = 20
VOL_HISTORY_TRADING_DAYS = 260  # ~1 trading year, for the volatility percentile


def _fetch_equity_asset_ids(supabase):
    rows = (
        supabase.table("assets")
        .select("asset_id")
        .eq("asset_type", "equity")
        .eq("is_active", True)
        .limit(1000)
        .execute()
    ).data
    return [r["asset_id"] for r in rows]


def _fetch_price_history(supabase, asset_ids, min_date):
    # Supabase caps each response at 1000 rows, and ~500 stocks x
    # ~280 trading days is ~140,000 rows -- paged with .range() the
    # same way other scripts in this project page through large pulls.
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("prices_daily")
            .select("asset_id, date, close")
            .in_("asset_id", asset_ids)
            .gte("date", min_date)
            .order("asset_id")
            .order("date")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return pd.DataFrame(all_rows)


def _trading_days_available(df: pd.DataFrame, upto_date=None) -> list:
    dates = sorted(df["date"].unique())
    if upto_date is not None:
        dates = [d for d in dates if d <= upto_date]
    return dates


def _compute_scores_for_date(df: pd.DataFrame, run_date: str):
    """df: full history (asset_id, date, close), run_date: the trading
    day to score. Returns dict of scores + counts, or None if there's
    no data at all for this date."""
    hist = df[df["date"] <= run_date]
    if hist.empty:
        return None

    advancers = 0
    decliners = 0
    breadth_n = 0
    above_sma = 0
    momentum_n = 0
    vol_percentiles = []

    for asset_id, g in hist.groupby("asset_id"):
        g = g.sort_values("date")
        closes = g["close"].dropna().to_numpy()
        if len(closes) < 2:
            continue

        # 1. Breadth: today's close vs previous trading day's close.
        if closes[-1] > closes[-2]:
            advancers += 1
            breadth_n += 1
        elif closes[-1] < closes[-2]:
            decliners += 1
            breadth_n += 1
        # unchanged (closes[-1] == closes[-2]) doesn't count either way

        # 2. Momentum: latest close vs trailing 50-day SMA.
        if len(closes) >= MOMENTUM_WINDOW:
            sma50 = closes[-MOMENTUM_WINDOW:].mean()
            momentum_n += 1
            if closes[-1] > sma50:
                above_sma += 1

        # 3. Volatility: today's 20-day realized vol vs its own
        # trailing-year distribution of 20-day vol readings.
        if len(closes) >= VOL_HISTORY_TRADING_DAYS:
            returns = pd.Series(closes).pct_change().dropna().to_numpy()
            if len(returns) >= VOL_HISTORY_TRADING_DAYS:
                # Rolling 20-day stdev across the trailing ~1yr of returns.
                rolling_vol = pd.Series(returns).rolling(VOL_WINDOW).std().dropna().to_numpy()
                if len(rolling_vol) >= VOL_HISTORY_TRADING_DAYS // 2:  # need a real distribution to rank against
                    current_vol = rolling_vol[-1]
                    percentile = (rolling_vol <= current_vol).mean()  # 0=calmest ever seen, 1=most turbulent ever seen
                    vol_percentiles.append(percentile)

    if breadth_n == 0 and momentum_n == 0 and not vol_percentiles:
        return None

    breadth_score = (advancers / breadth_n * 100) if breadth_n else None
    momentum_score = (above_sma / momentum_n * 100) if momentum_n else None
    volatility_score = ((1 - pd.Series(vol_percentiles).median()) * 100) if vol_percentiles else None

    components = [s for s in (breadth_score, momentum_score, volatility_score) if s is not None]
    overall_score = sum(components) / len(components) if components else None

    return {
        "breadth_score": breadth_score,
        "momentum_score": momentum_score,
        "volatility_score": volatility_score,
        "overall_score": overall_score,
        "advancers": advancers,
        "decliners": decliners,
        "universe_count": breadth_n,
    }


def _commentary(scores: dict) -> str:
    overall = scores["overall_score"]
    breadth = scores["breadth_score"]
    momentum = scores["momentum_score"]
    volatility = scores["volatility_score"]

    if overall is None:
        return "Not enough price history yet to compute a reading."

    if overall >= 65:
        mood = "Markets broadly positive"
    elif overall >= 45:
        mood = "Markets mixed"
    else:
        mood = "Markets broadly cautious"

    details = []
    if breadth is not None:
        details.append("breadth strong" if breadth >= 55 else ("breadth weak" if breadth <= 45 else "breadth balanced"))
    if momentum is not None:
        details.append("momentum firm" if momentum >= 55 else ("momentum soft" if momentum <= 45 else "momentum steady"))
    if volatility is not None:
        details.append("calmer than usual" if volatility >= 60 else ("choppier than usual" if volatility <= 40 else "typical volatility"))

    if details:
        return f"{mood} today — " + ", ".join(details) + "."
    return f"{mood} today."


def main():
    supabase = get_client()
    asset_ids = _fetch_equity_asset_ids(supabase)
    if not asset_ids:
        print("No active equity assets found.")
        return

    backtest_days = None
    if "--backtest" in sys.argv:
        idx = sys.argv.index("--backtest")
        backtest_days = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 30

    # Fetch enough history for the longest requirement (volatility's
    # ~1 trading year) plus, in backtest mode, enough extra days
    # before the earliest scored date to still have that full year
    # available for it too.
    calendar_lookback_days = 650 if backtest_days else 420
    min_date = (datetime.now(timezone.utc) - pd.Timedelta(days=calendar_lookback_days)).strftime("%Y-%m-%d")

    print(f"Fetching prices_daily for {len(asset_ids)} equities since {min_date}...")
    df = _fetch_price_history(supabase, asset_ids, min_date)
    if df.empty:
        print("No price history found -- has the daily refresh job run yet?")
        return
    print(f"Fetched {len(df)} rows.")

    all_dates = _trading_days_available(df)
    if not all_dates:
        print("No trading days found.")
        return

    target_dates = all_dates[-backtest_days:] if backtest_days else [all_dates[-1]]

    results = []
    for run_date in target_dates:
        scores = _compute_scores_for_date(df, run_date)
        if scores is None:
            continue
        commentary = _commentary(scores)
        row = {"run_date": run_date, "formula_version": FORMULA_VERSION, "commentary": commentary, **scores}
        results.append(row)

    if not results:
        print("Nothing to write -- not enough history for any target date yet.")
        return

    if backtest_days:
        print(f"\n{'date':<12}{'breadth':>9}{'momentum':>10}{'volatility':>12}{'overall':>9}  commentary")
        for r in results:
            def fmt(v):
                return f"{v:.0f}" if v is not None else "n/a"
            print(f"{r['run_date']:<12}{fmt(r['breadth_score']):>9}{fmt(r['momentum_score']):>10}{fmt(r['volatility_score']):>12}{fmt(r['overall_score']):>9}  {r['commentary']}")
        overall_values = [r["overall_score"] for r in results if r["overall_score"] is not None]
        if overall_values:
            print(f"\n{len(overall_values)} days scored. overall_score range: {min(overall_values):.0f}-{max(overall_values):.0f}, "
                  f"average: {sum(overall_values)/len(overall_values):.0f}. "
                  f"(If every day shows nearly the same number, or None, that's a sign the formula or the data needs a closer look before this goes live.)")

    supabase.table("market_mood").upsert(results, on_conflict="run_date,formula_version").execute()
    print(f"\nUpserted {len(results)} row(s) into market_mood.")


if __name__ == "__main__":
    main()
