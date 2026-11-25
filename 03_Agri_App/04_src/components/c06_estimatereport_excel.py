"""6. Estimate Report — ONE Excel workbook: Information Accompanying, T-test, Confidential Sheet (Hindi, as the
office's letter). Same plain style as the 5. Estimates workbook (c05_estimates_report.py).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from src.components import c05_estimates_report as xl
from src.components import c06_estimatereport as er

HINDI = "Nirmala UI"                     # a Windows font with Devanagari
H_BODY = Font(name=HINDI, size=11)
H_BOLD = Font(name=HINDI, size=11, bold=True)
H_TITLE = Font(name=HINDI, size=13, bold=True)
SECTION = Font(name=xl.FONT, bold=True, size=12, color="1D6B3A")
THIN = Side(style="thin", color="7F7F7F")
GRID = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MID = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _section(ws, row: int, title: str, df: pd.DataFrame) -> int:
    """A titled block: heading row + rows (thin borders, numbers right). Returns the next free row (one blank)."""
    ws.cell(row=row, column=1, value=title).font = SECTION
    row += 1
    for c, name in enumerate(df.columns, 1):
        cell = ws.cell(row=row, column=c, value=name)
        cell.font, cell.fill, cell.alignment, cell.border = xl.HEAD, xl.HEAD_FILL, xl.WRAP, xl.BOX
    ws.row_dimensions[row].height = 32
    for rec in df.to_dict("records"):
        row += 1
        for c, name in enumerate(df.columns, 1):
            cell = ws.cell(row=row, column=c, value=xl._value(rec[name]))
            cell.font, cell.border = xl.BODY, xl.BOX
            cell.alignment = xl.NUMBER if isinstance(cell.value, (int, float)) else xl.LEFT
            if isinstance(cell.value, (int, float)):
                cell.number_format = xl.INT if float(cell.value).is_integer() else xl.DEC2
    return row + 2


def _information(wb, rep: er.Report, lines: list[str]):
    ws, r = xl._sheet(wb, "Information Accompanying", "Information Accompanying",
                      [f"Yield estimate while submitting for approval for year {rep.year}"] + lines)
    r = _section(ws, r, "Details on yield rate (kg/ha)", er.yield_rate_table(rep))
    r = _section(ws, r, "Details of receipt of schedules", er.receipt_table(rep))
    r = _section(ws, r, "Distribution of green yield rate (grams per plot)", er.distribution_table(rep))
    r = _section(ws, r, "Ancillary information", er.ancillary_table(rep))
    r = _section(ws, r, "Crop condition", er.condition_table(rep))
    r = _section(ws, r, "Reasons for crop damage / below normal", er.reasons_table(rep))
    _section(ws, r, "Submission", pd.DataFrame([{"Due date": rep.value("DUE DATE"),
                                                 "Date of submission": rep.value("SUBMISSION DATE"),
                                                 "ID": rep.ident}]))
    for c, w in zip("ABCDEFGHI", (20, 16, 16, 16, 16, 16, 16, 16, 16)):
        ws.column_dimensions[c].width = w
    xl._print(ws, 1)
    ws.print_title_rows = None
    ws.page_setup.orientation = "portrait"


def _t_test(wb, rep: er.Report, lines: list[str]):
    ws, r = xl._sheet(wb, "T-test", "T-test", lines + ["|Y1 − Y2| ÷ √(V1 + V2); significant above 1.96. CES "
                                                        "variance = (CES yield × CES %SE ÷ 100)²."])
    xl._table(ws, r, er.t_test_table(rep), widths={"Test": 26, "Result": 26})


def _put(ws, ref, value, font=H_BODY, align=None, border=None):
    c = ws[ref]
    c.value = value
    c.font = font
    if align:
        c.alignment = align
    if border:
        c.border = border
    return c


def _confidential(wb, rep: er.Report):
    """The office's Hindi letter (गोपनीय): the table (1) – (9) with the row of this estimate's agency."""
    ws = wb.create_sheet("Confidential Sheet")
    ws.sheet_view.showGridLines = False
    hi = er.hindi_names(rep)
    row = er.confidential_row(rep)
    prev, ces_year = er.previous_year(rep.year), rep.value("CES YEAR")
    _put(ws, "B1", "राष्ट्रीय सांख्यिकी कार्यालय (क्षे.सं.प्र.)", H_TITLE, MID)
    ws.merge_cells("B1:H1")
    _put(ws, "I1", "गोपनीय", H_BOLD, MID)
    _put(ws, "B2", "कृषि सांख्यिकी मुख्यालय, फरीदाबाद", H_BOLD, MID)
    ws.merge_cells("B2:H2")
    _put(ws, "A4", "फसल सांख्यिकी सुधार योजना के अंतर्गत फसल कटाई प्रयोग के प्रतिदर्श जांच पर आधारित अनुमानित उपज दर",
         H_BOLD, MID)
    ws.merge_cells("A4:I4")
    _put(ws, "A6", f"राज्य: {hi['state']}")
    _put(ws, "C6", f"वर्ष: {rep.year}")
    _put(ws, "E6", f"मौसम: {hi['season']}")
    _put(ws, "G6", f"फसल: {hi['crop']}")
    heads = [("A8:A10", "एजेंसी"), ("B8:D8", "अनुमानित औसत उपज (कि.ग्राम/हैकटेयर) प्रतिदर्श जांच के अनुसार"),
             ("B9", "चालू वर्ष"), ("C9", "पिछला वर्ष"), ("D9", f"वर्ष {ces_year} के लिए जी.सी.ई.एस." if ces_year
                                                       else "जी.सी.ई.एस."),
             ("B10", rep.year), ("C10", prev), ("D10", ""),
             ("E8:F8", "प्रतिशत अंतर"), ("E9:E10", "(2) − (3)\n÷ (3) × 100"), ("F9:F10", "(2) − (4)\n÷ (4) × 100"),
             ("G8:H8", "प्रयोगों की संख्या"), ("G9:G10", "नियोजित"), ("H9:H10", "विश्लेषित"),
             ("I8:I10", "प्रतिशत प्रत्युत्तर")]
    for ref, text in heads:
        first = ref.split(":")[0]
        _put(ws, first, text, H_BOLD, MID)
        if ":" in ref:
            ws.merge_cells(ref)
    for r in range(8, 12):
        for c in range(1, 10):
            ws.cell(row=r, column=c).border = GRID
    for c in range(1, 10):
        _put(ws, f"{get_column_letter(c)}11", f"({c})", H_BODY, MID, GRID)
    keys = ["now", "prev", "ces", "diff_prev", "diff_ces", "planned", "analysed", "response"]
    for i, agency in enumerate(("केन्द्रीय", "राज्य", "सम्मिलित")):
        r = 12 + i
        _put(ws, f"A{r}", agency, H_BOLD, MID, GRID)
        for c, k in enumerate(keys, 2):
            v = row[k] if agency == row["agency"] else None
            _put(ws, f"{get_column_letter(c)}{r}", v, H_BODY, MID, GRID)
        ws.row_dimensions[r].height = 24
    ws.row_dimensions[8].height = 36
    ws.row_dimensions[9].height = 36
    notes = [("A17", "टिप्पणी:", H_BOLD), ("B17", "स्तम्भ (2), (3) तथा (4) में कोष्ठक के आंकडे़ मानक त्रुटि को दर्शाते हैं ।", H_BODY),
             ("A18", "अभ्युक्तिः", H_BOLD),
             ("B18", "(1) स्तम्भ (5) तथा (6) में तारा (*) का चिन्ह संकेत करता है कि अन्तर गण्य है ।", H_BODY),
             ("B19", "(2) पिछले वर्ष की तुलना में विचलन के कारण, यदि कोई है :", H_BODY),
             ("B20", "(3) अन्य अभ्युक्तियां :", H_BODY),
             ("A23", f"टी-14011 / {hi['state']} / प्राक्क. / {hi['crop']} / {rep.year} / कृ.सां.", H_BODY),
             ("G23", "दिनांक :", H_BODY),
             ("G26", "निदेशक / उप निदेशक", H_BOLD),
             ("A28", "प्रतिलिपि सूचनार्थ : -", H_BODY),
             ("A29", "1. समन्वय एवं प्रशिक्षण एकक, रा.सां.का.(क्षे.सं.प्र.) फरीदाबाद ।", H_BODY)]
    for ref, text, font in notes:
        _put(ws, ref, text, font)
    for c, w in zip("ABCDEFGHI", (16, 16, 16, 20, 14, 14, 12, 12, 13)):
        ws.column_dimensions[c].width = w
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1                       # the letter on one page
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True


def export(rep: er.Report) -> Path:
    """Write the workbook; returns its path."""
    made = datetime.now()
    sel, nm = rep.sel, rep.nm
    lines = [f"{rep.state.title()}  ·  {rep.year}  ·  {str(nm['season']).title()}  ·  {nm['crop']}  ·  "
             f"{sel.sample_label.title()} sample" + (f"  ({nm['parts']})" if sel.combined else ""),
             f"Prepared by {rep.now.inputs.prepared_by or '–'}  ·  {made:%d-%m-%Y %H:%M}"]
    wb = Workbook()
    wb.remove(wb.active)
    _information(wb, rep, lines)
    _t_test(wb, rep, lines)
    _confidential(wb, rep)
    folder = er.report_folder(rep, made)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{made:%Y-%m-%d_%H%M%S}_{nm['season']}_{nm['crop']}_{sel.sample_label.title()}_report.xlsx"
    wb.save(out)
    return out
