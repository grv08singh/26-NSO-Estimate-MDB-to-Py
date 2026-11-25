"""5. Estimates — the estimate as ONE Excel workbook, a sheet per table, in the office's order:

    Area Sheet -> Intermediate Table -> Variance (columns 1-14) -> (%) S.E. -> Compiled Data -> Estimate BD

Every sheet: a title, what was estimated (state · year · season · crop · sample), the factors, then a plain table
(bold heading row, thin borders, number formats, bold total row, heading frozen, A4 landscape printing with page
numbers). The tables are the ones the app shows (c05_estimates.py), so screen and workbook always agree.
Saved in 02_artifacts/05_estimates/<STATE>/<YEAR>/<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/.

Also writes a consolidated summary CSV (configured in config.yaml: estimates_report.summary_csv_path) with columns:
Year, State code, Season code, Sample code, Crop code, Yield (kg/ha), %SE, Variance, Area (ha).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.components import c05_estimates as est
from src.utils.config_loader import load_config

OFFICE = "NSO (FOD), Agricultural Statistics HQ, Faridabad"
FONT = "Calibri"
EDGE = Side(style="thin", color="B7C3B0")
BOX = Border(left=EDGE, right=EDGE, top=EDGE, bottom=EDGE)
TOP = Border(left=EDGE, right=EDGE, top=Side(style="medium", color="1D6B3A"), bottom=EDGE)
HEAD_FILL = PatternFill("solid", fgColor="1D6B3A")             # the app's green
TOTAL_FILL = PatternFill("solid", fgColor="E8F0E4")
RED_FILL = PatternFill("solid", fgColor="FDE2E1")
HEAD = Font(name=FONT, bold=True, color="FFFFFF")
BOLD = Font(name=FONT, bold=True)
BODY = Font(name=FONT)
GREY = Font(name=FONT, color="595959")
TITLE = Font(name=FONT, bold=True, size=14, color="1D6B3A")
WRAP = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")
NUMBER = Alignment(horizontal="right", vertical="center")
CENTER = Alignment(horizontal="center", vertical="center")
CENTRED = {"2. +", "+"}                               # columns shown centred

INT = "#,##0"
DEC2 = "#,##0.00#"
DEC4 = "0.0000"
FORMATS = {                                       # column -> number format (others: whole numbers / 2 decimals)
    "CCF": DEC4, "Conversion factor": "0.0###", "Driage ratio": DEC4, "Recovery ratio": DEC4,
    "8. (ni² − Σnij²) ÷ (ni × (mi − 1))": "#,##0.00",
}
ITEM_FORMATS = {"% SE": "0.0", "SE": "#,##0.00", "SE (kg/ha)": "#,##0.00"}   # Item / Value tables
TEXT_COLUMNS = {"Crop code", "District code", "Merge district code", "Season", "Sample", "State", "District",
                "Order of selection", "Expt", "Inspection status", "Rejected", "Seed type", "Irrigation",
                "Fertiliser", "Manure", "Pesticide", "Crop condition", "Affected by"}

SUMMARY_CSV_COLUMNS = ["Year", "State code", "Season code", "Sample code", "Crop code",
                       "Yield (kg/ha)", "%SE", "Variance", "Area (ha)"]


def _value(v):
    """Numbers as numbers (whole ones as int), blanks as empty cells, text as it is."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, str):
        return v if v != "" else None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return int(f) if f.is_integer() else f


def _sheet(wb, name: str, title: str, lines: list[str]):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws["A1"] = title
    ws["A1"].font = TITLE
    for i, text in enumerate(lines, 2):
        ws.cell(row=i, column=1, value=text).font = GREY
    return ws, len(lines) + 3                       # first row of the table


def _table(ws, row: int, df: pd.DataFrame, fmt_rows=None, widths: dict | None = None, min_width: int = 8,
           filters: bool = False) -> int:
    """Write df from `row` (heading + rows); fmt_rows(record) -> fill for a row or None. Returns the next free row."""
    cols = list(df.columns)
    for c, name in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=name)
        cell.font, cell.fill, cell.alignment, cell.border = HEAD, HEAD_FILL, WRAP, BOX
    r = row
    for rec in df.to_dict("records"):
        r += 1
        first = str(rec.get(cols[0], ""))
        is_total = first in (est.TOTAL_LABEL, est.WEIGHTED_LABEL)
        fill = TOTAL_FILL if is_total else (fmt_rows(rec) if fmt_rows else None)
        for c, name in enumerate(cols, 1):
            v = rec[name]
            if name in TEXT_COLUMNS and _value(v) is not None:
                v = str(v)[:-2] if str(v).endswith(".0") else str(v)
            cell = ws.cell(row=r, column=c, value=_value(v))
            cell.font = BOLD if is_total else BODY
            cell.border = TOP if first == est.TOTAL_LABEL else BOX
            if isinstance(cell.value, (int, float)):
                cell.alignment = NUMBER
                item_fmt = ITEM_FORMATS.get(str(rec.get("Item"))) if name == "Value" else None
                cell.number_format = item_fmt or FORMATS.get(name, INT if float(cell.value).is_integer() else DEC2)
            else:
                cell.alignment = CENTER if name in CENTRED else LEFT
            if fill:
                cell.fill = fill
    lines = 1
    for c, name in enumerate(cols, 1):              # width: the longest heading word / value
        vals = [f"{v:,.2f}" if isinstance(v, float) else str(v) for v in df[name].tolist()
                if _value(v) is not None]
        longest = max([len(w) for w in str(name).split()] + [len(v) for v in vals])
        w = (widths or {}).get(name, min(max(min_width, longest + 3), 46))
        ws.column_dimensions[get_column_letter(c)].width = w
        lines = max(lines if c > 1 else 1, -(-len(str(name)) // max(1, int(w) - 2)))
    ws.row_dimensions[row].height = 15 * lines + 6          # the heading row tall enough for wrapped headings
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    if filters and len(df):
        ws.auto_filter.ref = f"A{row}:{get_column_letter(len(cols))}{r}"
    _print(ws, row)
    return r + 1


def _print(ws, head_row: int):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.print_title_rows = f"{head_row}:{head_row}"
    ws.oddFooter.left.text = OFFICE
    ws.oddFooter.right.text = "Page &P of &N"


def _note(ws, row: int, text: str) -> int:
    ws.cell(row=row, column=1, value=text).font = GREY
    return row + 1


# ------------------------------------------------------------------ the workbook

def export(state: str, year: str, sel: est.Selection, nm: dict, inputs: est.Inputs, base: pd.DataFrame,
           res: est.Result, exps: pd.DataFrame) -> Path:
    """Write the workbook; returns its path."""
    made = datetime.now()
    what = (f"{state.title()}  ·  {year}  ·  {str(nm['season']).title()}  ·  {nm['crop']}  ·  "
            f"{sel.sample_label.title()} sample" + (f"  ({nm['parts']})" if sel.combined else ""))
    g = lambda v: "" if v is None else f"{v:g}"          # noqa: E731
    factors = (f"Conversion factor {g(inputs.cf)}  ·  Driage ratio {g(inputs.driage)}  ·  Recovery ratio "
               f"{g(inputs.recovery)}  ·  Prepared by {inputs.prepared_by or '–'}  ·  {made:%d-%m-%Y %H:%M}")
    lines = [what, factors]
    wb = Workbook()
    wb.remove(wb.active)

    ws, r = _sheet(wb, "Area Sheet", "Area Sheet", lines + ["Please check that the areas are the latest."])
    area = est.area_sheet_table(base, inputs, sel.crop_label_code)
    _table(ws, r, area, lambda rec: RED_FILL if rec.get("Merge district code") == "1" or
           int(rec.get("Expts") or 0) < est.MIN_EXPTS else None)

    ws, r = _sheet(wb, "Intermediate Table", "Intermediate Table", lines)
    _table(ws, r, est.intermediate_table(res), widths={"+": 5})

    ws, r = _sheet(wb, "Variance", "Variance", lines)
    r = _table(ws, r, est.variance_table(res), min_width=9, widths={"2. +": 6})
    _note(ws, r + 1, "ni = expts, mi = villages, ai = area, i = column 8. Columns 11 and 12 are used only when the "
                     "villages do not all have the same number of expts.")

    ws, r = _sheet(wb, "(%) S.E.", "Calculation of (%) S.E.", lines)
    r = _table(ws, r, est.se_table(res), widths={"Item": 18, "Formula": 50, "Value": 18})
    _note(ws, r + 1, "Col. = a numbered column of the Variance sheet.")

    ws, r = _sheet(wb, "Compiled Data", "Compiled Data", lines)
    _table(ws, r, est.compiled_table(res, len(exps)), widths={"Item": 22, "Value": 30})

    ws, r = _sheet(wb, "Estimate BD", "Estimate BD", lines)
    _table(ws, r, est.bd_table(exps), lambda rec: RED_FILL if str(rec.get("Rejected")) == "1" else None,
           filters=True)                                       # rejected plots highlighted

    folder = est.report_folder(state, year, sel, nm, made)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / (f"{made:%Y-%m-%d_%H%M%S}_{est._safe(nm['season'])}_{est._safe(nm['crop'])}_"
                    f"{sel.sample_label.title()}.xlsx")
    wb.save(out)
    return out


def _summary_csv_path() -> Path:
    """Get the summary CSV path from config."""
    config = load_config()
    path_str = config.get("estimates_report", {}).get("summary_csv_path",
                                                        "02_artifacts/06_estimatereport/estimates_summary.csv")
    return Path(path_str)


def append_summary_csv(state: str, year: str, sel: est.Selection, nm: dict, res: est.Result, state_code: str = "") -> Path:
    """
    Append one row to the consolidated estimates summary CSV.
    Columns: Year, State code, Season code, Sample code, Crop code, Yield (kg/ha), %SE, Variance, Area (ha)
    """
    csv_path = _summary_csv_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine season code and crop code from selection
    season_code = sel.season
    sample_code = sel.sample_code  # "1", "2", or "12" for combined
    crop_code = sel.crop_label_code  # e.g., "1600" for combined, or "1611" for single

    # Use state code from master list (STATE column), fallback to state name
    state_code_val = state_code if state_code else state.upper()

    # Format values
    yield_val = res.yield_kg_ha
    pct_se = res.pct_se if res.pct_se != "Not Applicable" else ""
    variance = res.variance if res.variance != "Not Applicable" else ""
    area = res.total_area

    row = {
        "Year": year,
        "State code": state_code_val,
        "Season code": season_code,
        "Sample code": sample_code,
        "Crop code": crop_code,
        "Yield (kg/ha)": yield_val,
        "%SE": pct_se,
        "Variance": variance,
        "Area (ha)": area,
    }

    # Read existing CSV if it exists
    if csv_path.exists():
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        # Remove any existing row with same key (Year, State code, Season, Sample, Crop)
        mask = ~((df["Year"] == year) &
                 (df["State code"] == state_code_val) &
                 (df["Season code"] == season_code) &
                 (df["Sample code"] == sample_code) &
                 (df["Crop code"] == crop_code))
        df = df[mask]
    else:
        df = pd.DataFrame(columns=SUMMARY_CSV_COLUMNS)

    # Append new row
    df = pd.concat([df, pd.DataFrame([row], columns=SUMMARY_CSV_COLUMNS)], ignore_index=True)

    # Write back (atomic)
    tmp = csv_path.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(csv_path)

    return csv_path
