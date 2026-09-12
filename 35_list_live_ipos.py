"""
35_list_live_ipos.py
-------------------------------------------------------------------
Quick listing of just the company names + symbols for currently-open
and upcoming IPOs -- used to look up their real DRHP prospectus PDFs
by hand (there's no reliable free API that maps a company to its
prospectus link, so this step is manual/search-based, same as the
PRD's own "DRHP assessments are written research, tiered" framing).

Avdhoot wants SME-platform IPOs excluded (NSE Emerge is a separate,
smaller-company listing platform from the main board) -- this prints
the raw `series` value NSE gives each IPO so we can see the REAL code
it uses to mark SME vs mainboard before filtering anything out in the
real ingestion script. Guessing that code wrong risks wrongly hiding a
real mainboard IPO or wrongly showing an SME one -- so this step
checks first rather than assuming.

Run from the TrueResearch Code folder (same venv as the other
numbered scripts):
    python 35_list_live_ipos.py
-------------------------------------------------------------------
"""
import tempfile
from nse import NSE

with tempfile.TemporaryDirectory() as tmp_dir, NSE(download_folder=tmp_dir) as nse:
    print("=== Currently open ===")
    for row in nse.listCurrentIPO() or []:
        if row.get("category") in (None, "Total"):
            print(f"  {row.get('symbol')!s:<12} series={row.get('series')!s:<6} {row.get('companyName')}")

    print("\n=== Upcoming ===")
    for row in nse.listUpcomingIPO() or []:
        print(f"  {row.get('symbol')!s:<12} series={row.get('series')!s:<6} {row.get('companyName')}")

    print("\n=== Recently listed (past) ===")
    for row in nse.listPastIPO() or []:
        print(f"  {row.get('symbol')!s:<12} type={row.get('securityType')!s:<6} {row.get('company')}")
