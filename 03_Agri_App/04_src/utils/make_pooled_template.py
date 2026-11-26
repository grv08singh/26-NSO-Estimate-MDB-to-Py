"""Build 04_src/resources/est_rep_pooled.xlsx — the template of 6. Estimate Report's "Combined & Pooled" workbook —
from the office's two workbooks (01_raw_data/est_rep_calc/01 Central.xlsx and 02 State.xlsx):

    comb('c)  conf('C)      combined estimate (unirrigated + irrigated) of the Central sample, its Confidential Sheet
    comb('S)  conf('S)      the same for the State sample
    pool(p)   conf('P)      pooled estimate (Central + State) and the Confidential Sheet of all three

Cells, formulas, styles, merged cells, column widths, row heights and page set-up are copied as they are, with:
  * the link to the other file ('[1]comb(''c)'!…) made a link inside this workbook, a range (…!$F$5:$G$5) one cell;
  * "N.A." handled everywhere: the office's t-test result cells said "Significant" (and the Confidential Sheet put
    a *) when a figure was missing, because Excel compares the text "N.A." as greater than 1.96;
  * the input cells (yields, variances, areas, CES, counts, previous year, names) emptied.

Run once when the office's layout changes:  python -m src.utils.make_pooled_template  (from 03_Agri_App, after
`import bootstrap; bootstrap.setup()`), or  python 04_src/utils/make_pooled_template.py.
"""
from __future__ import annotations

import re
import sys
from copy import copy
from pathlib import Path

from openpyxl import Workbook, load_workbook

SRC = Path("01_raw_data") / "est_rep_calc"
OUT = Path("04_src") / "resources" / "est_rep_pooled.xlsx"

# cells typed in the office's sheets (emptied in the template, filled by the app on export)
INPUTS = {
    "comb('c)": ["B5", "D5", "F5", "B6", "E6", "A9", "D9", "C11", "F11", "C13", "F13", "C15", "F15", "C18", "C19",
                 "C20", "H18", "H19", "C22", "C23"],
    "comb('S)": ["A9", "D9", "C11", "F11", "C13", "F13", "C15", "F15", "H18", "H19", "C22", "C23", "H22", "H23"],
}
# fixes of the office's formulas: in pool(p) the pooled planned / analysed only when both samples have them
PATCH = {
    "conf('P)": {
        "U18": "=IF(OR('comb(''c)'!H18=\"\",'comb(''S)'!H18=\"\"),\"\",U14+U16)",
        "V18": "=IF(OR('comb(''c)'!H19=\"\",'comb(''S)'!H19=\"\"),\"\",V14+V16)",
    },
}
_TEST = re.compile(r'IF\((J\d+)>(L\d+),("[^"]*"),("[^"]*")\)')


def _t_result(v):
    """T-test sign / result cells: the office's =IFERROR(IF(J39>L39,"Significant","Insignificant"),"N.A.") says
    "Significant" when t is "N.A." (text > 1.96 in Excel) and puts a * on the Confidential Sheet. Only a number is
    compared now."""
    if not (isinstance(v, str) and v.startswith("=")):
        return v
    m = _TEST.search(v.replace(" ", ""))
    if not m:
        return v
    j, l, yes, no = m.groups()
    return f'=IF(ISNUMBER({j}),IF({j}>{l},{yes},{no}),"N.A.")'
OFFICE = "राष्ट्रीय सांख्यिकी कार्यालय (क्षे.सं.प्र.)"
COPY_TO = "समन्वय एवं प्रशिक्षण एकक, रा.सां.का.(क्षे.सं.प्र.) फरीदाबाद ।"


def _formula(v):
    if not (isinstance(v, str) and v.startswith("=")):
        return v
    v = v.replace("[1]", "")                                   # the other file's sheets are in this workbook now
    # '…'!$F$5:$G$5  ->  '…'!$F$5   (a merged cell read as a range)
    return re.sub(r"(!\$?[A-Z]{1,2}\$?\d+):\$?[A-Z]{1,2}\$?\d+", r"\1", v)


def _conf_fixes(ws) -> None:
    """Confidential sheets: % difference and % response 'NA' instead of an error; one office name."""
    ws["H3"].value = OFFICE
    ws["C29"].value = COPY_TO
    for r in (14, 16, 18):
        if ws[f"Q{r}"].value:
            ws[f"Q{r}"].value = f'=IF($D{r}="","",IFERROR((D{r}-H{r})*100/H{r},"NA"))'
            ws[f"S{r}"].value = f'=IF($D{r}="","",IFERROR((D{r}-L{r})*100/L{r},"NA"))'
            ws[f"W{r}"].value = f'=IFERROR(V{r}*100/U{r},"NA")'
            # previous year's %SE: 2 decimals in every row (the office's sheets mix 1 and 2)
            j = ws[f"J{r}"].value
            if isinstance(j, str):
                ws[f"J{r}"].value = re.sub(r",1\),\"NA\"\)$", ',2),"NA")', j)


def _copy_sheet(src, wb: Workbook):
    ws = wb.create_sheet(src.title)
    for row in src.iter_rows():
        for c in row:
            if c.__class__.__name__ == "MergedCell":
                continue
            n = ws.cell(row=c.row, column=c.column, value=_formula(c.value))
            if c.has_style:
                n.font, n.border, n.fill = copy(c.font), copy(c.border), copy(c.fill)
                n.number_format, n.protection, n.alignment = c.number_format, copy(c.protection), copy(c.alignment)
    for m in src.merged_cells.ranges:
        ws.merge_cells(str(m))
    for k, d in src.column_dimensions.items():
        ws.column_dimensions[k].width = d.width
        ws.column_dimensions[k].hidden = d.hidden
    for k, d in src.row_dimensions.items():
        ws.row_dimensions[k].height = d.height
    ws.sheet_view.showGridLines = src.sheet_view.showGridLines
    ws.sheet_view.zoomScale = src.sheet_view.zoomScale
    ps, ws_ps = src.page_setup, ws.page_setup
    ws_ps.orientation, ws_ps.paperSize = ps.orientation, ps.paperSize or ws.PAPERSIZE_A4
    ws_ps.scale, ws_ps.fitToWidth, ws_ps.fitToHeight = ps.scale, ps.fitToWidth, ps.fitToHeight
    ws.sheet_properties.pageSetUpPr.fitToPage = src.sheet_properties.pageSetUpPr.fitToPage
    ws.print_options.horizontalCentered = src.print_options.horizontalCentered
    for side in ("left", "right", "top", "bottom", "header", "footer"):
        setattr(ws.page_margins, side, getattr(src.page_margins, side))
    if src.print_area:
        ws.print_area = src.print_area
    return ws


def build(src: Path = SRC, out: Path = OUT) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    for name in ("01 Central.xlsx", "02 State.xlsx"):
        for s in load_workbook(src / name).worksheets:
            ws = _copy_sheet(s, wb)
            for ref in INPUTS.get(ws.title, []):
                ws[ref].value = None
            for ref, f in PATCH.get(ws.title, {}).items():
                ws[ref].value = f
            for row in ws.iter_rows():
                for cell in row:
                    if cell.__class__.__name__ != "MergedCell" and cell.column_letter in "KM":
                        cell.value = _t_result(cell.value)
            if ws.title.startswith("conf"):
                _conf_fixes(ws)
    wb.calculation.fullCalcOnLoad = True
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(build())
