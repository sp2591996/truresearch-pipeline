"""
28_diagnose_missing_ratios.py
-------------------------------------------------------------------
Avdhoot noticed Debt/Equity, ROCE, and Price/Sales tiles are missing
from both the Stock Detail Page and the Sector Page's averages. This
script checks whether that's a real data gap (these columns are
mostly NULL in ratios_snapshot) or something else, by counting how
many of the most-recent-per-stock rows actually have a usable value
in each column.

Run from the TrueResearch Code folder (same venv as the other
numbered scripts):
    python 28_diagnose_missing_ratios.py
-------------------------------------------------------------------
"""
from db_client import get_client

supabase = get_client()

# Pull every row, newest-first, then keep only each stock's single
# most recent snapshot -- same "latest row per asset" approach the
# frontend pages use.
all_rows = []
page_size = 1000
frm = 0
while True:
    res = (
        supabase.table("ratios_snapshot")
        .select("asset_id, pe_ratio, pb_ratio, ev_ebitda, price_to_sales, roce, debt_equity, margin, market_cap, as_of_date")
        .order("as_of_date", desc=True)
        .range(frm, frm + page_size - 1)
        .execute()
    )
    rows = res.data or []
    all_rows.extend(rows)
    if len(rows) < page_size:
        break
    frm += page_size

latest = {}
for row in all_rows:
    if row["asset_id"] not in latest:
        latest[row["asset_id"]] = row

total = len(latest)
print(f"Total stocks with at least one ratios_snapshot row: {total}\n")

columns = ["pe_ratio", "pb_ratio", "ev_ebitda", "price_to_sales", "roce", "debt_equity", "margin", "market_cap"]
for col in columns:
    have = sum(1 for r in latest.values() if r.get(col) is not None)
    pct = (have / total * 100) if total else 0
    print(f"  {col:<16} {have:>4} / {total} stocks have a value ({pct:.0f}%)")
