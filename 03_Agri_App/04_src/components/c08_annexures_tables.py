"""8. Annexures — the RC-7 Y-tables as exact copies of the office's old workbooks:

  1Tables S-<n>.xlsx      RC7-Y1 … RC7-Y7, RC7-Y11, RC7-Y12, RC7-Y13 of the report's n-th season (S-1 = first season,
                          S-2 = second …), Central and State, exactly as `1Tables S-1.xlsx` / `1Tables S-2.xlsx`
  1Tables 8,9,10-Y.xlsx   Tab 8 / 9 / 10 of every season (I, II, …), as the old `1Tables 8,9,10-Y.xlsx`

How: the old print sheets are the templates (resources/annex_tables_S.xlsx, annex_tables_8910.xlsx: fonts, merged
headings, column numbers, borders, page set-up untouched). In the old books each print cell is a formula on the
calculation sheets (Table-Y1(o) … of `RC-7 Tables CYS-1`, Table Y-8(I) … of `7RC-7 TY-series`). Here those
calculation sheets are rebuilt in memory: their numbers from c08_annexures (the checked engine), their titles /
crop names from their old formulas (resources/annex_tables_cells.json) over a 'Crops' sheet made from the master
list. Every print formula is then worked out and written as a value, so the workbooks have no formulas and no links.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string as ci
from openpyxl.utils import get_column_letter as cl

from src.components import c08_annexures as A

RES = Path(__file__).resolve().parents[1] / "resources"
TEMPLATE_S = RES / "annex_tables_S.xlsx"
TEMPLATE_8910 = RES / "annex_tables_8910.xlsx"
CELLS = RES / "annex_tables_cells.json"
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
SLOTS = 15                                    # crop rows of the old sheets (Crops rows 7 – 21)

# calculation sheet -> (engine table, first crop row, value columns, column offset of the State half, total row(s))
LAYOUT = {
    "Table-Y1(o)": ("Y-1", 7, 6, 8, [22]),
    "Table-Y2(o)": ("Y-2", 6, 15, 17, [21]),
    "Table-Y3(o)": ("Y-3", 7, 13, 15, [22]),
    "Table-Y4(o)": ("Y-4", 7, 15, 17, [22]),
    "Table-Y5(o)": ("Y-5", 9, 18, 20, [24]),
    "Table-Y7(o)": ("Y-7", 6, 5, 7, [21]),
    "Table-Y12(o)": ("Y-12", 9, 19, 21, [24]),
    "Table-Y13(o)": ("Y-13", 7, 6, 8, [22]),
}


# ------------------------------------------------------------------ a small Excel formula evaluator

class V:
    """A cell value with Excel's &, =, <>, + – * / (text and numbers, blanks as "")."""

    def __init__(self, v):
        self.blank = v is None or (isinstance(v, V) and v.blank)      # an empty cell (= 0 and = "" in Excel)
        self.v = "" if v is None else (v.v if isinstance(v, V) else v)

    @staticmethod
    def text(x) -> str:
        x = x.v if isinstance(x, V) else x
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return "" if x is None else str(x)

    def num(self) -> float:
        if self.v in ("", None):
            return 0.0
        try:
            return float(self.v)
        except (TypeError, ValueError):
            return 0.0

    def __and__(self, o):
        return V(V.text(self) + V.text(o))

    def __rand__(self, o):
        return V(V.text(o) + V.text(self))

    def _cmp(self, o):
        """Excel: an empty cell equals 0 and ""; a number never equals a text (0 = "" is FALSE)."""
        o = o if isinstance(o, V) else V(o)
        a, b = self.v, o.v
        num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)   # noqa: E731
        if self.blank:
            a = 0 if num(b) else ""
        if o.blank:
            b = 0 if num(a) else ""
        if num(a) and num(b):
            return a, b
        if num(a) != num(b):
            return ("n", a), ("s", b)
        return str(a), str(b)

    def __eq__(self, o):
        a, b = self._cmp(o)
        return V(a == b)

    def __ne__(self, o):
        a, b = self._cmp(o)
        return V(a != b)

    def __lt__(self, o):
        a, b = self._cmp(o)
        return V(a < b if type(a) is type(b) or (not isinstance(a, tuple) and not isinstance(b, tuple)) else False)

    def __gt__(self, o):
        a, b = self._cmp(o)
        return V(a > b if not isinstance(a, tuple) and not isinstance(b, tuple) else False)

    def __le__(self, o):
        return V(bool(self < o) or bool(self == o))

    def __ge__(self, o):
        return V(bool(self > o) or bool(self == o))

    def __bool__(self):
        return bool(self.v) and self.v != 0

    def __add__(self, o):
        return V(self.num() + V(o).num())

    __radd__ = __add__

    def __sub__(self, o):
        return V(self.num() - V(o).num())

    def __rsub__(self, o):
        return V(V(o).num() - self.num())

    def __mul__(self, o):
        return V(self.num() * V(o).num())

    __rmul__ = __mul__

    def __truediv__(self, o):
        d = V(o).num()
        return V(self.num() / d if d else 0)

    def __neg__(self):
        return V(-self.num())

    __hash__ = None


REF = re.compile(r"(?:'(?:\[(\d+)\])?([^']+)'!|(?:\[(\d+)\])?([A-Za-z_][A-Za-z0-9_.]*)!)?"
                 r"\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?")
STR = re.compile(r'"((?:[^"]|"")*)"')


class Book:
    """Sheets of values / formulas: {sheet: {cell: value or '=formula'}}; get() works formulas out (memoised).
    Sheets of several old books are kept apart as 'NS|Sheet' (NS = the book); links[NS] maps a formula's [n] (the old
    book's link number) to the NS of the book it pointed at. Plain names (no '|') are one book."""

    def __init__(self) -> None:
        self.cells: dict[str, dict] = {}
        self.done: dict[tuple, V] = {}
        self.links: dict[str, dict[int, str]] = {}

    def sheet(self, ns: str, name: str) -> dict:
        return self.cells.setdefault(f"{ns}|{name}" if ns else name, {})

    def _target(self, key: str, idx, name) -> str:
        ns = key.split("|", 1)[0] if "|" in key else ""
        if not name:
            return key
        if idx:
            ns = self.links.get(ns, {}).get(int(idx), ns)
        return f"{ns}|{name}" if ns else name

    def get(self, sheet: str, cell: str) -> V:
        key = (sheet, cell)
        if key in self.done:
            return self.done[key]
        raw = self.cells.get(sheet, {}).get(cell)
        self.done[key] = V("")                         # guards against loops
        val = self.evaluate(sheet, raw[1:]) if isinstance(raw, str) and raw.startswith("=") else V(raw)
        self.done[key] = val
        return val

    def rng(self, sheet: str, a: str, b: str) -> list[V]:
        (c1, r1), (c2, r2) = _split(a), _split(b)
        return [self.get(sheet, f"{cl(c)}{r}") for r in range(r1, r2 + 1) for c in range(ci(c1), ci(c2) + 1)]

    def evaluate(self, sheet: str, f: str) -> V:
        strings: list[str] = []

        def keep(m):
            strings.append(m.group(1).replace('""', '"'))
            return f"\x01{len(strings) - 1}\x02"             # no letters + digits: not taken for a cell
        f = STR.sub(keep, f)

        def ref(m):
            sh = self._target(sheet, m.group(1) or m.group(3), m.group(2) or m.group(4))
            a = f"{m.group(5)}{m.group(6)}"
            if m.group(7):
                return f"_RNG({sh!r},{a!r},'{m.group(7)}{m.group(8)}')"
            return f"_R({sh!r},{a!r})"
        f = REF.sub(ref, f)
        f = re.sub(r"\x01(\d+)\x02", lambda m: f"V({strings[int(m.group(1))]!r})", f)
        f = f.replace("<>", "!=").replace(">=", "__GE__").replace("<=", "__LE__")
        f = re.sub(r"(?<![=!<>])=(?!=)", "==", f).replace("__GE__", ">=").replace("__LE__", "<=")
        env = {"V": V, "_R": self.get, "_RNG": self.rng, "IF": _if, "OR": lambda *a: V(any(bool(x) for x in a)),
               "AND": lambda *a: V(all(bool(x) for x in a)), "SUM": _sum, "ROUND": _round, "FIXED": _fixed,
               "MAX": lambda *a: V(max(_nums(a) or [0])), "MIN": lambda *a: V(min(_nums(a) or [0])),
               "ABS": lambda x: V(abs(V(x).num())), "INT": lambda x: V(float(math.floor(V(x).num()))),
               "LEN": lambda x: V(len(V.text(x))), "TRIM": lambda x: V(" ".join(V.text(x).split())),
               "UPPER": lambda x: V(V.text(x).upper()), "CONCATENATE": lambda *a: V("".join(V.text(x) for x in a)),
               "IFERROR": lambda a, b=V(""): a, "VALUE": lambda x: V(V(x).num()), "NOT": lambda x: V(not bool(x)),
               "TRUE": V(True), "FALSE": V(False)}
        try:
            out = eval(f, {"__builtins__": {}}, env)          # noqa: S307 – our own templates' formulas only
        except Exception:                                       # noqa: BLE001 – a formula we cannot work out: blank
            return V("")
        return out if isinstance(out, V) else (V(out[0]) if isinstance(out, list) and out else V(out))


def _split(a: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", a)
    return m.group(1), int(m.group(2))


def _if(c, a=V(False), b=V(False)):
    return a if bool(c) else b


def _nums(args) -> list[float]:
    out = []
    for a in args:
        for x in (a if isinstance(a, list) else [a]):
            v = V(x).v
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(v)
    return out


def _sum(*args):
    t = 0.0
    for a in args:
        for x in (a if isinstance(a, list) else [a]):
            if isinstance(V(x).v, (int, float)) and not isinstance(V(x).v, bool):
                t += V(x).v
    return V(t)


def _round(x, n=0):
    return V(A.xround(V(x).num(), int(V(n).num())))


def _fixed(x, n=2):
    return V(f"{A.xround(V(x).num(), int(V(n).num())):.{int(V(n).num())}f}")


# ------------------------------------------------------------------ the in-memory calculation sheets

def _crops_sheet(rep: A.Report, season: str, sample_hint: str = "1") -> dict:
    """The old 'Crops' sheet, with the season in A5 / B5 and its crops in A7 / B7 …"""
    name = rep.season_name(season)
    cells = {"A1": "STATE", "B1": "Code", "C1": "Sample Type ", "D1": "code",
             "A2": rep.state.upper() or "STATE",
             "B2": int(rep.info["state_code"]) if str(rep.info.get("state_code", "")).isdigit() else "",
             "C2": "CENTRAL", "D2": 1, "A3": "YEAR", "B3": rep.year, "C3": "STATE", "D3": 2,
             "A4": "Season", "B4": "code", "A5": name.upper(), "B5": int(season) if season.isdigit() else season,
             "A6": "Crop", "B6": "Code"}
    for i, (c, n) in enumerate(rep.crops(season)[:SLOTS]):
        cells[f"A{7 + i}"] = n.upper()
        cells[f"B{7 + i}"] = int(c)
    return cells


def _slot(rep: A.Report, season: str) -> dict[str, int]:
    return {c: i for i, (c, _) in enumerate(rep.crops(season)[:SLOTS])}


def _code(label: str) -> str | None:
    m = re.search(r"\((\d+)\)\s*$", str(label))
    return f"{int(m.group(1)):02d}" if m else None


def _put_rows(book: dict, df, slot: dict, r0: int, col0: int, ncols: int, totals: list[int], skip: int = 0) -> None:
    """Crop rows of an engine table at r0 + slot, values from column col0 (B = 2) on; the total row(s)."""
    d = df[df["_kind"] != "total"]
    t = df[df["_kind"] == "total"]
    vals = [c for c in df.columns if c not in ("_kind",)][1 + skip:]
    for _, r in d.iterrows():
        k = slot.get(_code(r.iloc[1]))
        if k is None:
            continue
        for j, name in enumerate(vals[:ncols]):
            book[f"{cl(col0 + j)}{r0 + k}"] = _cell(r[name])
    for row, (_, r) in zip(totals, t.iterrows()):
        for j, name in enumerate(vals[:ncols]):
            book[f"{cl(col0 + j)}{row}"] = _cell(r[name])


def _cell(v):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f.is_integer() else f


def _calc_sheets(rep: A.Report, season: str, cells: dict, book: Book | None = None, ns: str = "") -> Book:
    """The old calculation sheets of one season: titles / names from their formulas, numbers from the engine."""
    b = book or Book()
    b.cells[f"{ns}|Crops" if ns else "Crops"] = _crops_sheet(rep, season)
    slot = _slot(rep, season)
    for sh, base in cells.items():
        b.cells[f"{ns}|{sh}" if ns else sh] = {k: v for k, v in base.items()}
    for sh, (t, r0, ncols, off, totals) in LAYOUT.items():
        for smp, shift in (("1", 0), ("2", off)):
            df = A.y_table(rep, t, season, smp)
            _put_rows(b.sheet(ns, sh), df, slot, r0, 2 + shift, ncols, totals)
    # Y-6: 4 rows per crop (D … P), totals 68 – 71
    for smp, shift in (("1", 0), ("2", 17)):
        df = A.y_table(rep, "Y-6", season, smp)
        g = b.sheet(ns, "Table-Y6(o)")
        rows = df[df["_kind"] != "total"].reset_index(drop=True)
        k = None
        for i, r in rows.iterrows():
            if r["Crop"]:
                k = slot.get(_code(r["Crop"]))
            if k is None:
                continue
            e = i % 4
            for j, v in enumerate(list(r.values)[3:]):
                g[f"{cl(4 + shift + j)}{8 + k * 4 + e}"] = _cell(v)
        tot = df[df["_kind"] == "total"].reset_index(drop=True)
        for e, r in tot.iterrows():
            for j, v in enumerate(list(r.values)[3:]):
                g[f"{cl(4 + shift + j)}{68 + e}"] = _cell(v)
    # Y-11: a block of 37 rows per crop (classes 7 – 29, total 30, mean 31)
    for smp, shift in (("1", 0), ("2", 7)):
        df = A.y_table(rep, "Y-11", season, smp)
        g = b.sheet(ns, "Table-Y11(o)")
        k, line = None, 0
        for _, r in df.iterrows():
            if r["_kind"] == "head":
                k, line = slot.get(_code(r["Class (kg/ha)"])), 0
                continue
            if k is None:
                continue
            row = 7 + k * 37 + line
            for j, name in enumerate(["Irrigated", "% irrigated", "Unirrigated", "% unirrigated", "Total"]):
                if r["_kind"] == "sub" and name in ("% irrigated", "% unirrigated"):
                    continue
                g[f"{cl(2 + shift + j)}{row}"] = _cell(r[name])
            line += 1
    # Y-8, Y-9, Y-10 (Central, as the old TY-series)
    for sh, t, ncols in (("Table Y-8(I)", "Y-8", 19), ("Table Y-9(I)", "Y-9", 26)):
        for smp, r0 in (("1", 10), ("2", 27)):                 # the pooled block (row 44 on) is worked out
            _put_rows(b.sheet(ns, sh), A.y_table(rep, t, season, smp), slot, r0, 3, ncols, [])
    g = b.sheet(ns, "Table Y-10(I)")
    for smp, r0 in (("1", 10), ("2", 61)):
        df = A.y_table(rep, "Y-10", season, smp).reset_index(drop=True)
        k, line = None, 0
        for _, r in df.iterrows():
            if r["Crop"]:
                k, line = slot.get(_code(r["Crop"])), 0
            if k is None:
                continue
            for j, v in enumerate(list(r.values)[3:]):
                g[f"{cl(5 + j)}{r0 + k * 4 + line}"] = _cell(v)
            line += 1
    return b


# ------------------------------------------------------------------ the workbooks

def _register(ws, book: Book, ns: str = "") -> str:
    """The template sheet's cells (values and formulas) into the book; returns its key."""
    key = f"{ns}|{ws.title}" if ns else ws.title
    cells = book.cells.setdefault(key, {})
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None:
                cells[c.coordinate] = c.value
    return key


def _fill(ws, book: Book, sheet_map: dict[str, str], ns: str = "", hide: bool | None = None) -> None:
    """Every formula of the template sheet -> its value (references to the old books -> our sheets)."""
    key = _register(ws, book, ns)
    for alias, real in sheet_map.items():
        book.cells[alias] = book.cells[real]
    hide_blank = any(d.hidden for d in ws.row_dimensions.values()) if hide is None else hide   # unused crop rows
    for row in ws.iter_rows():
        has_formula, shown = False, False
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                v = book.get(key, c.coordinate).v
                c.value = None if v == "" else (bool(v) if isinstance(v, bool) else v)
                has_formula = True
                if hide is True and c.column == 1 and isinstance(c.value, (int, float)):
                    continue                                   # a serial number alone does not show a row
                shown = shown or (c.value is not None and str(c.value).strip(" /()%\n") != "")
        if hide_blank and has_formula:                       # rows of crops this season has: shown; others: hidden
            ws.row_dimensions[row[0].row].hidden = not shown


def _y11_blocks(ws, n: int, block: int = 37) -> None:
    """RC7-Y11 has a block of 37 rows per crop: the season's crops shown (a page each), the other blocks hidden."""
    from openpyxl.worksheet.pagebreak import Break, RowBreak
    for k in range(SLOTS):
        for r in range(1 + k * block, 1 + (k + 1) * block):
            ws.row_dimensions[r].hidden = k >= n
    ws.print_area = f"A1:O{max(1, n) * block}"
    ws.row_breaks = RowBreak()
    for k in range(1, n):
        ws.row_breaks.append(Break(id=k * block))


def _cells() -> dict:
    return json.loads(CELLS.read_text(encoding="utf-8"))


def export(rep: A.Report, folder: Path, state_code: str = "", made: datetime | None = None) -> list[Path]:
    """1Tables S-<n>.xlsx per season of the report and 1Tables 8,9,10-Y.xlsx, in folder. Returns their paths."""
    made = made or datetime.now()
    if state_code:
        rep.info["state_code"] = state_code
    folder.mkdir(parents=True, exist_ok=True)
    base = _cells()
    out = []
    for n, (s, _) in enumerate(rep.seasons, 1):
        wb = load_workbook(TEMPLATE_S)
        book = _calc_sheets(rep, s, base)
        for ws in wb.worksheets:
            _fill(ws, book, {})
        _y11_blocks(wb["RC7-Y11"], len(rep.crops(s)[:SLOTS]))
        p = folder / f"1Tables S-{n}.xlsx"
        wb.save(p)
        out.append(p)
    wb = load_workbook(TEMPLATE_8910)
    sheets = {}                                              # copies first (from the untouched templates) …
    for n in range(len(rep.seasons)):
        for name in ("Tab 8-I", "Tab 9-I", "Tab 10-I"):
            ws = wb[name] if n == 0 else wb.copy_worksheet(wb[name])
            if n:
                ws.title = name.replace("-I", f"-{ROMAN[n]}")
                ws.page_setup.orientation = wb[name].page_setup.orientation
                ws.page_setup.paperSize = wb[name].page_setup.paperSize
                ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = (wb[name].page_setup.fitToWidth,
                                                                       wb[name].page_setup.fitToHeight)
                ws.sheet_properties.pageSetUpPr = wb[name].sheet_properties.pageSetUpPr
                ws.page_margins = wb[name].page_margins
            sheets.setdefault(n, []).append(ws)
    for n, (s, _) in enumerate(rep.seasons):                 # … then the values of each season
        book = _calc_sheets(rep, s, base)
        for ws in sheets[n]:
            _fill(ws, book, {})
    order = [f"Tab {t}-{ROMAN[n]}" for n in range(len(rep.seasons)) for t in ("8", "9", "10")]
    wb._sheets = [wb[name] for name in order if name in wb.sheetnames]
    p = folder / "1Tables 8,9,10-Y.xlsx"
    wb.save(p)
    out.append(p)
    return out
