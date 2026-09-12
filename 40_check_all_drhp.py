"""
40_check_all_drhp.py
-------------------------------------------------------------------
Same idea as 38_check_drhp_parse.py, but prints every IPO that has a
completed DRHP parse in one go, instead of one symbol at a time.

Run:
    venv\\Scripts\\python.exe 40_check_all_drhp.py
-------------------------------------------------------------------
"""
import json

from db_client import get_client


def main():
    supabase = get_client()

    assess_res = supabase.table("ipo_assessments").select("*, ipos(company_name, symbol)").eq("status", "complete").execute()
    rows = assess_res.data or []
    if not rows:
        print("No completed DRHP parses found yet.")
        return

    for a in rows:
        ipo = a.get("ipos") or {}
        print(f"\n{'=' * 70}")
        print(f"=== {ipo.get('company_name')} ({ipo.get('symbol')}) ===")
        print(f"source_pdf_filename: {a.get('source_pdf_filename')}")

        print("\n--- business_summary ---")
        print(a.get("business_summary") or "(none)")

        print("\n--- industry_summary ---")
        print(a.get("industry_summary") or "(none)")

        print("\n--- objects_of_offer ---")
        print(a.get("objects_of_offer") or "(none)")

        print("\n--- key_risks ---")
        risks = a.get("key_risks")
        if risks:
            risks = json.loads(risks) if isinstance(risks, str) else risks
            for i, r in enumerate(risks, 1):
                print(f"  {i}. {r}")
        else:
            print("(none)")

        print("\n--- financial_summary ---")
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
