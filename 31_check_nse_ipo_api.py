"""
31_check_nse_ipo_api.py
-------------------------------------------------------------------
Before writing an IPO ingestion script, this checks exactly what the
`nse` PyPI package (already used for shareholding_pattern, see
25_shareholding_refresh.py) actually exposes for IPO data -- rather
than guessing a method name and having it fail. Prints every public
method on the NSE client whose name suggests it's IPO-related, then
tries calling the most likely one and prints a sample of what comes
back (or the error, if it doesn't work) so we know the real shape of
the data before building the real ingestion script around it.

Run from the TrueResearch Code folder (same venv as the other
numbered scripts):
    python 31_check_nse_ipo_api.py
-------------------------------------------------------------------
"""
import tempfile
from nse import NSE

with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
    all_methods = [m for m in dir(nse) if not m.startswith("_")]
    ipo_like = [m for m in all_methods if "ipo" in m.lower()]

    print("All public methods on the NSE client:")
    for m in all_methods:
        print(f"  {m}")

    print(f"\nMethods that look IPO-related: {ipo_like}")

    for method_name in ipo_like:
        print(f"\n--- Trying nse.{method_name}() ---")
        try:
            method = getattr(nse, method_name)
            result = method()
            print(f"Type: {type(result)}")
            if isinstance(result, list):
                print(f"Count: {len(result)}")
                print(f"First item: {result[0] if result else '(empty list)'}")
            elif isinstance(result, dict):
                print(f"Keys: {list(result.keys())}")
                print(f"Sample: {result}")
            else:
                print(f"Value: {result}")
        except Exception as e:
            print(f"Failed: {e}")
