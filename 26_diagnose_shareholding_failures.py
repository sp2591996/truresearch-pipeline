"""
26_diagnose_shareholding_failures.py
-------------------------------------------------------------------
One-off diagnostic script -- Session 11, part 12. Avdhoot asked why
SWIGGY, FIRSTCRY, and THERMAX specifically fail in
25_shareholding_refresh.py.

Round 2: round 1 confirmed the filings download fine (HTTP 200, real
XBRL content) -- so the failure is in parsing/the sum-sanity-check, not
network/fetching. Working theory, from the raw NSE filing records
themselves (each has an `employeeTrusts` field: 5.08% for SWIGGY,
6.98% for FIRSTCRY, 5.46% for THERMAX): NSE's shareholding XBRL schema
was revised (the file references schema version "2025-10", newer than
whatever version 25_shareholding_refresh.py was originally built and
tested against) and now reports "Employee Benefit Trusts" as its OWN
top-level category, separate from Promoter/DII/FII/Public. The script
doesn't know about this 5th category, so for any company with a
nonzero employee-trust holding, promoter+dii+fii+public no longer sums
to ~100% -- it lands a few % short (roughly the size of the missing
employee-trust slice), which trips the script's own 95-105% sum sanity
check and causes the whole quarter (and therefore the whole stock, if
every recent quarter has this) to be silently rejected.

This script dumps EVERY (contextRef, value) pair found for the
percentage tag in one real filing per ticker, so we can see the exact
contextRef NSE uses for the employee-trust category before changing
the real ingestion script to handle it.

Run:
    venv\\Scripts\\python.exe 26_diagnose_shareholding_failures.py
-------------------------------------------------------------------
"""
import tempfile
import traceback
import xml.etree.ElementTree as ET

import requests

TICKERS = ["SWIGGY", "FIRSTCRY", "THERMAX"]
PCT_TAG_LOCALNAME = "ShareholdingAsAPercentageOfTotalNumberOfShares"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main():
    from nse import NSE

    with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
        for ticker in TICKERS:
            print(f"\n{'=' * 60}")
            print(f"{ticker}")
            print("=" * 60)

            try:
                records = nse.shareholding(ticker)
            except Exception:
                traceback.print_exc()
                continue

            if not records:
                print("No filings found.")
                continue

            xbrl_url = records[0].get("xbrl")
            print(f"Downloading: {xbrl_url}")
            try:
                resp = requests.get(xbrl_url, headers=REQUEST_HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception:
                traceback.print_exc()
                continue

            try:
                root = ET.fromstring(resp.content)
            except Exception:
                traceback.print_exc()
                continue

            print(f"\nAll '{PCT_TAG_LOCALNAME}' (contextRef -> value) pairs found:")
            total = 0.0
            found_any = False
            for el in root.iter():
                if local_tag(el.tag) != PCT_TAG_LOCALNAME:
                    continue
                if el.text is None:
                    continue
                found_any = True
                context_ref = el.attrib.get("contextRef", "(none)")
                raw = el.text.strip()
                print(f"  {context_ref:65s} {raw}")
                try:
                    v = float(raw)
                    total += v if v > 1 else v * 100
                except ValueError:
                    pass

            if not found_any:
                print("  (none found)")
            print(f"\n  Sum of all values above (as %): {total:.2f}")


if __name__ == "__main__":
    main()
