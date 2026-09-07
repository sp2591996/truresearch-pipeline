"""
29_check_debt_equity_units.py
-------------------------------------------------------------------
Sanity check for the Debt/Equity fix in 06_weekly_fundamentals_refresh.py.
That script divides yfinance's raw `debtToEquity` by 100, on the
assumption that yfinance reports it as a percentage (e.g. 41.5 meaning
a 0.415 ratio). A stock's Debt/Equity showing as 0.01 on the site
looks suspiciously low for a real company, so this prints the RAW
yfinance value (before any division) for a handful of well-known
large-caps with roughly known real-world Debt/Equity ratios, so we can
tell whether the /100 assumption is actually correct or needs fixing.

Run from the TrueResearch Code folder (same venv as the other
numbered scripts):
    python 29_check_debt_equity_units.py
-------------------------------------------------------------------
"""
from market_data_provider import get_fundamentals

# A handful of large, well-known Nifty stocks with roughly known
# real-world Debt/Equity ratios, so the raw number can be sanity
# checked against reality:
#   RELIANCE   ~0.35-0.45 (moderate debt)
#   TCS        ~0.0-0.1   (almost debt-free)
#   TATASTEEL  ~0.6-1.0   (heavier debt, capital-intensive)
#   ITC        ~0.0-0.05  (almost debt-free)
SAMPLE = ["RELIANCE.NS", "TCS.NS", "TATASTEEL.NS", "ITC.NS"]

for symbol in SAMPLE:
    info = get_fundamentals(symbol)
    raw = info.get("debtToEquity")
    print(f"{symbol:<16} raw debtToEquity = {raw!r}   (if /100: {raw/100 if raw is not None else None})")
