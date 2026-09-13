"""
check_ownership_data.py -- ONE-OFF DIAGNOSTIC, not part of the pipeline.
-------------------------------------------------------------------
Checks whether Yahoo Finance (our existing data source -- no new
scraper needed if this works) exposes an institutional/insider
ownership % breakdown for US stocks, as a possible USA-appropriate
substitute for India's Promoter/FII/DII/Public shareholding chart.

Run manually:
    venv\\Scripts\\python.exe check_ownership_data.py
-------------------------------------------------------------------
"""
from market_data_provider import get_fundamentals

SAMPLE_TICKERS = [
    ("AAPL", "AAPL"),
    ("MSFT", "MSFT"),
    ("WMT", "WMT"),
]

FIELDS_OF_INTEREST = [
    "heldPercentInsiders",
    "heldPercentInstitutions",
    "sharesOutstanding",
    "floatShares",
    "impliedSharesOutstanding",
]

for ticker, yf_symbol in SAMPLE_TICKERS:
    print(f"\n--- {ticker} ({yf_symbol}) ---")
    info = get_fundamentals(yf_symbol)
    if not info:
        print("  (no data returned at all)")
        continue
    for field in FIELDS_OF_INTEREST:
        print(f"  {field} = {info.get(field, '<< not present >>')}")
