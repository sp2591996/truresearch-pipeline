"""
Builds the v3 admin upload templates from the v2 ones (keeps the pre-filled
name / acronym / ticker columns) and the single guideline source
trueresearch-frontend/lib/uploadGuidelines.json:
  row 1 = headers, row 2 = strict guidelines per column, data from row 3,
  plus a "READ ME FIRST" sheet of general rules for whoever fills the sheet.
Run:  python build_v3_templates.py
"""
import json, os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "..", "..", "trueresearch-frontend", "lib", "uploadGuidelines.json"), encoding="utf-8"))

def build(v2, v3, guidelines, sheet_title):
    src = openpyxl.load_workbook(os.path.join(HERE, v2)).worksheets[0]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    ncols = len(guidelines)
    head_fill = PatternFill("solid", fgColor="1F6F4A")
    guide_fill = PatternFill("solid", fgColor="EAF3EC")
    for c in range(1, ncols + 1):
        h = ws.cell(1, c, src.cell(1, c).value)
        h.font = Font(bold=True, color="FFFFFF")
        h.fill = head_fill
        h.alignment = Alignment(wrap_text=True, vertical="top")
        g = ws.cell(2, c, guidelines[c - 1])
        g.font = Font(italic=True, size=9, color="444444")
        g.fill = guide_fill
        g.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 55
    ws.row_dimensions[2].height = 330
    r_out = 3
    for r in range(2, src.max_row + 1):
        vals = [src.cell(r, c).value for c in range(1, ncols + 1)]
        if not any(vals):
            continue
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r_out, c, v)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        r_out += 1
    ws.freeze_panes = "C3"
    rules = wb.create_sheet("READ ME FIRST")
    rules.column_dimensions["A"].width = 120
    for i, t in enumerate(G["rules"], 1):
        rules.cell(i, 1, t).alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(os.path.join(HERE, v3))
    print(v3, r_out - 3, "rows")

build("stock_detail_upload_india_v2.xlsx", "stock_detail_upload_india_v4.xlsx", G["stock"], "Stock Detail Upload")
build("stock_detail_upload_us_v2.xlsx", "stock_detail_upload_us_v4.xlsx", G["stock"], "Stock Detail Upload")
build("sector_upload_india_v2.xlsx", "sector_upload_india_v4.xlsx", G["sector"], "Sector Upload")
build("sector_upload_us_v2.xlsx", "sector_upload_us_v4.xlsx", G["sector"], "Sector Upload")
