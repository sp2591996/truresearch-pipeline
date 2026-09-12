"""
38_check_drhp_parse.py
-------------------------------------------------------------------
Quick sanity-check viewer: prints out what 37_parse_drhp.py actually
saved into ipo_assessments for a given IPO symbol, so you can read
the extracted text/tables in full in the terminal (Supabase's table
editor truncates long text and doesn't format jsonb nicely).

Run:
    python 38_check_drhp_parse.py PRANAV
-------------------------------------------------------------------
"""
import json
import sys

from db_client import get_client


def main():
    if len(sys.argv) < 2:
        print("Usage: python 38_check_drhp_parse.py <SYMBOL>")
        sys.exit(1)

    symbol = sys.argv[1].strip().upper()
    supabase = get_client()

    ipo_res = supabase.table("ipos").select("ipo_id, company_name, symbol").eq("symbol", symbol).maybe_single().execute()
    if not ipo_res or not ipo_res.data:
        print(f"No IPO found with symbol {symbol}")
        sys.exit(1)

    ipo = ipo_res.data
    print(f"=== {ipo['company_name']} ({ipo['symbol']}) ===\n")

    assess_res = supabase.table("ipo_assessments").select("*").eq("ipo_id", ipo["ipo_id"]).maybe_single().execute()
    if not assess_res or not assess_res.data:
        print("No ipo_assessments row found for this IPO yet.")
        sys.exit(0)

    a = assess_res.data

    print(f"status: {a.get('status')}")
    print(f"source_pdf_filename: {a.get('source_pdf_filename')}")
    print(f"parsed_at: {a.get('parsed_at')}\n")

    print("--- business_summary ---")
    print(a.get("business_summary") or "(none)")
    print()

    print("--- industry_summary ---")
    print(a.get("industry_summary") or "(none)")
    print()

    print("--- objects_of_offer ---")
    print(a.get("objects_of_offer") or "(none)")
    print()

    print("--- key_risks ---")
    risks = a.get("key_risks")
    if risks:
        risks = json.loads(risks) if isinstance(risks, str) else risks
        for i, r in enumerate(risks, 1):
            print(f"  {i}. {r}")
    else:
        print("(none)")
    print()

    print("--- financial_summary ---")
    fin = a.get("financial_summary")
    if fin:
        fin = json.loads(fin) if isinstance(fin, str) else fin
        cols = fin.get("columns", [])
        print(f"  columns: {cols}")
        for label, values in fin.get("rows", {}).items():
            print(f"  {label}: {values}")
    else:
        print("(none)")


if __name__ == "__main__":
    main()
