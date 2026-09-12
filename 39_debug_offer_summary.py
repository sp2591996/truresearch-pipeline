"""
39_debug_offer_summary.py
-------------------------------------------------------------------
One-off diagnostic (not part of the regular pipeline). Dumps the raw
"Offer Document Summary" section text pdfplumber extracts for the
Pranav Constructions DRHP, plus what the business/industry heading
matcher sees for each candidate line -- written to a text file so it
can be inspected without pasting huge blocks into chat.

Run:
    venv\\Scripts\\python.exe 39_debug_offer_summary.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import importlib.util
spec = importlib.util.spec_from_file_location("parse_drhp", str(Path(__file__).parent / "37_parse_drhp.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

import pdfplumber

pdf_path = Path(__file__).parent / "drhp_pdfs" / "Registration_28022025232849_PCPLDRHP.pdf"
out_path = Path(__file__).parent / "drhp_debug_output.txt"

lines_out = []

with pdfplumber.open(str(pdf_path)) as pdf:
    ipos = [{"ipo_id": 1, "company_name": "Pranav Constructions Limited", "symbol": "PRANAV"}]
    cover_text = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(3, len(pdf.pages))))
    ipo = m.match_company(cover_text, ipos)
    lines_out.append(f"matched: {ipo}")

    toc_pages = m.find_toc_pages(pdf)
    toc_entries = m.extract_toc_entries(pdf, toc_pages)
    offset = m.detect_page_offset(pdf, toc_entries, toc_pages)
    lines_out.append(f"offset: {offset}")

    sections = m.locate_sections(toc_entries, offset, len(pdf.pages))
    for k, v in sections.items():
        lines_out.append(f"{k}: {v}")

    s = sections["offer_summary"]
    summary_text = m.extract_section_text(pdf, s["start"], s["end"])

    lines_out.append("\n=== RAW OFFER_SUMMARY TEXT ===")
    lines_out.append(summary_text)

    lines_out.append("\n=== LINE-BY-LINE (with length) ===")
    for idx, line in enumerate(summary_text.splitlines()):
        lines_out.append(f"[{idx}] (len={len(line.strip())}) {line!r}")

    lines_out.append("\n=== BUSINESS EXTRACTION RESULT ===")
    biz = m.extract_paragraph_after_heading(
        summary_text,
        ["summary of primary business", "primary business of our company", "business overview", "overview of our business", "our business"],
    )
    lines_out.append(repr(biz))

    lines_out.append("\n=== INDUSTRY EXTRACTION RESULT ===")
    ind = m.extract_paragraph_after_heading(
        summary_text,
        ["summary of the industry", "industry in which our company operates", "industry overview", "overview of the industry"],
    )
    lines_out.append(repr(ind))

out_path.write_text("\n".join(lines_out), encoding="utf-8")
print(f"Written to {out_path}")
