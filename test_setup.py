"""
test_setup.py
-------------------------------------------------------------------
A one-time sanity check for Phase B, Step 3. Run this once to confirm:
  1. market_data_provider.py can successfully reach Yahoo Finance
  2. db_client.py can successfully reach your Supabase database

This script doesn't save anything permanent -- it just prints results
so you (and I) can see everything is wired up correctly before we
build the real ingestion pipeline on top of it.

Run with:
    python test_setup.py
-------------------------------------------------------------------
"""
from market_data_provider import get_live_price
from db_client import get_client

print("=" * 60)
print("TEST 1: Can we reach Yahoo Finance via our data provider layer?")
print("=" * 60)
result = get_live_price("RELIANCE.NS")
if result:
    print(f"SUCCESS: RELIANCE current price = {result['price']}, "
          f"day change = {result['day_change_pct']}%")
else:
    print("FAILED: got no price back. Check your internet connection and try again.")

print()
print("=" * 60)
print("TEST 2: Can we reach the Supabase database?")
print("=" * 60)
try:
    supabase = get_client()
    response = supabase.table("sectors").select("*").execute()
    print(f"SUCCESS: connected to Supabase. 'sectors' table currently has "
          f"{len(response.data)} rows (0 is expected -- we haven't loaded data yet).")
except Exception as e:
    print(f"FAILED: could not reach Supabase. Error detail:\n  {e}")

print()
print("If both tests say SUCCESS, Step 3 is complete.")
