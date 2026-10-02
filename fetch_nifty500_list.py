"""
fetch_nifty500_list.py
-------------------------------------------------------------------
Downloads the OFFICIAL, up-to-date list of all 500 companies in the
NIFTY 500 index directly from the NSE (National Stock Exchange of
India) website, and saves it as a clean CSV.

You already have a file called nifty500_master.csv in this same
folder from earlier -- this script is for when you want a FRESH copy
(NSE updates index membership a few times a year, so companies do
occasionally get added/removed).

WHAT THIS SCRIPT DOES, IN PLAIN STEPS:
  1. Pretends to be a normal web browser (NSE's website blocks plain
     scripts, so we send the same "headers" a browser would)
  2. Downloads NSE's own official list file
  3. Saves it here as nifty500_fresh.csv
  4. Prints a few lines so you can see it worked

HOW TO RUN THIS (if you're not sure):
  1. Open VS Code
  2. Open a terminal (Terminal menu -> New Terminal)
  3. Make sure you're in the "TrueResearch Code" folder (type: cd,
     then drag the TrueResearch Code folder into the terminal window,
     then press Enter)
  4. Type:  python fetch_nifty500_list.py
  5. Press Enter and wait a few seconds

If it fails with a "connection" or "403" type error, NSE's website is
blocking the request (it does this sometimes) -- just try again in a
minute or two, or run it from your own browser instead:
  https://www.nseindia.com/market-data/live-equity-market
  (Indices tab -> Nifty 500 -> Download CSV)
-------------------------------------------------------------------
"""
import csv
import sys
import time

import requests

# The exact file NSE's own website uses to show the Nifty 500 list.
NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

# NSE blocks requests that don't look like they came from a real
# browser -- these headers make our request look like one.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/csv,application/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

OUTPUT_FILE = "nifty500_fresh.csv"


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # NSE often wants you to visit the homepage first (sets cookies
        # it then checks on the actual file download) -- so we do that
        # first, same as a real browser would.
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)

        resp = session.get(NSE_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Could not download from NSE: {e}")
        print("NSE's website sometimes blocks automated requests. Try again in a "
              "minute, or download manually from nseindia.com (see the "
              "instructions at the top of this file) and save it as "
              f"{OUTPUT_FILE} in this folder.")
        sys.exit(1)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(resp.content)

    # Quick sanity check + preview, so you can see it worked.
    with open(OUTPUT_FILE, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    print(f"Saved {len(rows) - 1} companies to {OUTPUT_FILE}")
    print("\nFirst 5 rows (including header):")
    for row in rows[:6]:
        print("  ", row)


if __name__ == "__main__":
    main()
