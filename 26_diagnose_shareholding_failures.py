"""
26_diagnose_shareholding_failures.py
-------------------------------------------------------------------
One-off diagnostic script -- Session 11, part 12 (re-used for the
MCX / ABBOTINDIA / BAYERCROP follow-up). Originally used to diagnose
why SWIGGY, FIRSTCRY, and THERMAX failed in 25_shareholding_refresh.py
(root cause found: NSE's "Employee Benefit Trusts" category, fixed).

Now re-pointed at the 3 remaining stocks that still fail:
MCX, ABBOTINDIA, BAYERCROP -- cause not yet known.

This script dumps EVERY (contextRef, value) pair found for the
percentage tag in one real filing per ticker, so we can see exactly
what NSE's filing looks like for these 3 and compare it against what
25_shareholding_refresh.py expects.

Run:
    venv\\Scripts\\python.exe 26_diagnose_shareholding_failures.py
-------------------------------------------------------------------
"""
import tempfile
import traceback
import xml.etree.ElementTree as ET

import requests

TICKERS = ["MCX", "ABBOTINDIA", "BAYERCROP"]
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
