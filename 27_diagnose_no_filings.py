"""
27_diagnose_no_filings.py
-------------------------------------------------------------------
Follow-up diagnostic to 26_diagnose_shareholding_failures.py.
MCX, ABBOTINDIA, and BAYERCROP came back "No filings found" -- a
different failure mode than the earlier SWIGGY/FIRSTCRY/THERMAX bug
(those DID get filings, they just failed the sum sanity check).

This script checks two things per ticker, to tell apart "NSE genuinely
has no shareholding filings on this endpoint for this symbol" from
"the symbol itself isn't being recognized correctly":

1. Confirms the ticker is a real, currently-listed NSE symbol (via
   nse.equityMetaInfo, a basic company-info lookup).
2. Calls nse.shareholding() again but prints the raw return value's
   type and content directly (not just "empty/non-empty"), and
   prints the exact exception (with full traceback) if the call
   raises one instead of returning an empty list -- the first script
   only printed tracebacks for exceptions, and skipped straight past
   an empty-list return without showing what came back internally.

Run:
    venv\\Scripts\\python.exe 27_diagnose_no_filings.py
-------------------------------------------------------------------
"""
import tempfile
import traceback

TICKERS = ["MCX", "ABBOTINDIA", "BAYERCROP"]


def main():
    from nse import NSE

    with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
        for ticker in TICKERS:
            print(f"\n{'=' * 60}")
            print(f"{ticker}")
            print("=" * 60)

            # Step 1: is this symbol recognized as a live listing at all?
            print("-- equityMetaInfo --")
            try:
                meta = nse.equityMetaInfo(ticker)
                if meta:
                    print(f"  Found. Company name (per NSE): {meta.get('companyName', '(not returned)')}")
                    print(f"  Status: {meta.get('status', '(not returned)')}")
                    print(f"  ISIN: {meta.get('isin', '(not returned)')}")
                else:
                    print("  equityMetaInfo returned nothing (empty/None).")
            except Exception:
                print("  equityMetaInfo raised an exception:")
                traceback.print_exc()

            # Step 2: what does shareholding() actually return, raw?
            print("\n-- shareholding() raw result --")
            try:
                records = nse.shareholding(ticker)
                print(f"  Type returned: {type(records)}")
                print(f"  Value returned: {records}")
            except Exception:
                print("  shareholding() raised an exception:")
                traceback.print_exc()


if __name__ == "__main__":
    main()
