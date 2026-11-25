"""8. Annexures — 1Annexures(Bi / Hi / Eng).xlsx, Annex-XIX … XXIV, in the office's final standard.

The template is the office's own final Bilingual book (resources/annex_final_Bi.xlsx – Gujarat Kharif 2024-25, made
by hand). Each sheet is written the way that book was made: its heading block, then season / crop / agency blocks
copied from its rows (fonts, borders, row heights, two-line Hindi + English text, the cells' own padding), a new page
with the repeated heading ("Contd..") when a page is full, and the closing double line.
The headings of the template read a hidden 'Common' sheet (state, years, season); here they are its shown text with
this report's state, years and season put in.
A second season is added in the same style: XIX a second Central / State / Pooled column set, XX / XXI / XXIII / XXIV
a block per season, XXII a page per season.
The Hindi and English books are the Bilingual one with each cell keeping only its Hindi or only its English text.
The numbers are those of c08_annexures (checked against the old RC-7 TAnnex), written as the old books did:
'750', '( 95.5)', '6(  2.5)'.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter as cl
from openpyxl.worksheet.pagebreak import Break, RowBreak

from src.components import c06_estimatereport as er
from src.components import c08_annexures as A
from src.components import c08_annexures_tables as T

TEMPLATE = T.RES / "annex_final_Bi.xlsx"
SHEETS = ("Annex-XIX", "Annex-XX", "Annex-XXI", "Annex-XXII", "Annex-XXIII", "Annex-XXIV")
AGENCY = [("Central", ["1"]), ("State", ["2"]), ("Pooled", ["1", "2"])]
# what the template shows for its own report (Gujarat, Kharif, 2024-25 and 2023-24) – replaced by this report's
TPL = {"cy": "2024-25", "py": "2023-24", "state_hi": "गुजरात", "state_en": "GUJARAT", "season_hi": "खरीफ",
       "season_en": "KHARIF"}
DEV = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")
KEEP_LATIN = re.compile(r"^\s*([IVX]+\.?|Contd\.*)\s*$")          # roman item numbers, "Contd.." stay in Hindi


# ------------------------------------------------------------------ formats of the old books

def pct(p) -> str:
    return f"({0.0 if p is None else p:5.1f})"


def npc(n, p) -> str:
    return f"{n}{pct(p)}"


# ------------------------------------------------------------------ names (state, seasons, crops)

FIRST_PAGE = 18                     # the template's page labels run अ-18/A-18 (XIX) … अ-25/A-25 (XXIV, page 2)
IRRIGATION = {"UI", "IR", "I", "U", "UNIRR", "IRR", "सिंचित", "असिंचित"}    # left out of a crop's name (by crop code)


def _common(names, sep: str) -> list[str]:
    """The words all names of a crop share: JOWAR_UI + JOWAR_IR -> JOWAR, COTTON_UI_A + COTTON_IR_A -> COTTON A,
    PADDY_KAR alone -> PADDY KAR (the annexures are by the crop code's first two digits)."""
    words = [[w.strip() for w in str(n).split(sep) if w.strip()] for n in names if str(n).strip()]
    if not words:
        return ""
    keep = [w for w in words[0] if all(w in x for x in words[1:]) and w.upper() not in IRRIGATION] or words[0][:1]
    return keep


def _hindi(state: str, year: str) -> dict:
    """Hindi names of the master list: state, seasons {code}, crops {(season, crop2)}."""
    ml = er.master_list(state, year)
    out = {"state": "", "season": {}, "crop": {}}
    if ml.empty:
        return out

    def mode(s):
        s = s.astype(str).str.strip()
        s = s[s != ""]
        return str(s.mode().iloc[0]) if len(s) else ""

    if "HSTATENAME" in ml:
        out["state"] = mode(ml["HSTATENAME"])
    for s, g in ml.groupby("SEASONCODE"):
        if "HSEASONNAME" in g:
            out["season"][A.code(s)] = mode(g["HSEASONNAME"])
        if "HCROPNAME" in g:
            for c, gc in g.groupby(g["CROPCODE"].astype(str).str[:2]):
                out["crop"][(A.code(s), c)] = mode(gc["HCROPNAME"]).split("_")[0].strip()
    return out


class Names:
    def __init__(self, rep: A.Report) -> None:
        self.rep = rep
        self.page = FIRST_PAGE
        self.py_year = er.previous_year(rep.year, 1)
        self.hi = _hindi(rep.state, rep.year)
        hp = _hindi(rep.state, self.py_year)
        for k in ("season", "crop"):
            self.hi[k] = {**hp[k], **self.hi[k]}
        self.hi["state"] = self.hi["state"] or hp["state"]
        self.crops: dict[tuple[str, str], tuple[str, str]] = {}
        for year in (self.py_year, rep.year):              # this year's names win
            ml = er.master_list(rep.state, year)
            if ml.empty:
                continue
            ml = ml.assign(C2=ml["CROPCODE"].astype(str).str[:2], S=ml["SEASONCODE"].map(A.code))
            for (s, c), g in ml.groupby(["S", "C2"]):
                hi = "-".join(_common(g["HCROPNAME"].unique(), "-")) if "HCROPNAME" in g else ""
                en = " ".join(_common(g["CROPNAME"].unique(), "_")).upper()
                self.crops[(s, c)] = (hi, en)

    def season(self, s: str) -> tuple[str, str]:
        return self.hi["season"].get(s, ""), self.rep.season_name(s).upper()

    def crop(self, s: str, c: str) -> str:
        hi, en = self.crops.get((s, c), ("", ""))
        return f"{hi or self.hi['crop'].get((s, c), '')}/{en or self.rep.name(s, c).upper()}"

    def next_page(self) -> str:
        n, self.page = self.page, self.page + 1
        return f"अ-{n}/A-{n}"


# ------------------------------------------------------------------ writing a sheet from the template's rows

class Out:
    """A new sheet written from blocks of the template sheet's rows (same workbook, so styles copy exactly)."""

    def __init__(self, wb, tpl, shown, rep: A.Report, nm: Names) -> None:
        self.tpl, self.shown, self.nm = tpl, shown, nm
        self.ws = wb.create_sheet(tpl.title + " (new)")
        self.r = 0
        self.page_h = 0.0                                   # height written on the page so far (points)
        self.pad: dict[tuple[int, int], str] = {}
        self.sub = {TPL["cy"]: rep.year, TPL["py"]: nm.py_year, TPL["state_hi"]: nm.hi["state"],
                    TPL["state_en"]: rep.state.upper()}
        self.set_season(rep.seasons[0][0])
        ws = self.ws
        for k, d in tpl.column_dimensions.items():
            nd = ws.column_dimensions[k]
            nd.width, nd.hidden = d.width, d.hidden
            nd.min, nd.max = d.min, d.max
        ws.sheet_format = copy.copy(tpl.sheet_format)
        ws.page_setup = copy.copy(tpl.page_setup)
        ws.sheet_properties.pageSetUpPr = copy.copy(tpl.sheet_properties.pageSetUpPr)
        ws.page_margins = copy.copy(tpl.page_margins)
        ws.print_options = copy.copy(tpl.print_options)
        ws.sheet_view.showGridLines = tpl.sheet_view.showGridLines
        ws.sheet_view.zoomScale = tpl.sheet_view.zoomScale
        ws.row_breaks = RowBreak()

    def set_season(self, s: str) -> None:
        hi, en = self.nm.season(s)
        self.sub[TPL["season_hi"]], self.sub[TPL["season_en"]] = hi, en

    def _shown(self, r: int, c: int):
        """A formula cell of the template: the text it shows, with this report's state, years and season."""
        v = self.shown.cell(r, c).value
        if not isinstance(v, str):
            return v
        keys = list(self.sub)
        for i, k in enumerate(keys):                        # two steps, so a new value is never replaced again
            v = v.replace(k, f"\x01{i}\x02")
        for i, k in enumerate(keys):
            v = v.replace(f"\x01{i}\x02", self.sub[k])
        return v

    def block(self, r1: int, r2: int | None = None) -> int:
        """Copy template rows r1..r2 (values, styles, heights, merges inside them) below what is written. Returns the
        first new row."""
        r2 = r2 or r1
        start = self.r + 1
        tpl, ws = self.tpl, self.ws
        for i, r in enumerate(range(r1, r2 + 1)):
            dst = start + i
            h = tpl.row_dimensions[r].height
            if h is not None:
                ws.row_dimensions[dst].height = h
            for c in range(1, tpl.max_column + 1):
                s = tpl.cell(r, c)
                v = s.value
                if isinstance(v, str) and v.startswith("="):
                    v = self._shown(r, c)
                d = ws.cell(dst, c)
                d.value = v
                if s.has_style:
                    d._style = copy.copy(s._style)
                if isinstance(v, str):
                    self.pad[(dst, c)] = v[len(v.rstrip(" ")):]
        for m in tpl.merged_cells.ranges:
            if m.min_row >= r1 and m.max_row <= r2:
                ws.merge_cells(start_row=m.min_row - r1 + start, end_row=m.max_row - r1 + start,
                               start_column=m.min_col, end_column=m.max_col)
        self.r = start + (r2 - r1)
        self.page_h += self.height(r1, r2)
        return start

    def height(self, r1: int, r2: int | None = None) -> float:
        """Height of template rows r1..r2 in points."""
        dflt = self.tpl.sheet_format.defaultRowHeight or 15
        return sum(self.tpl.row_dimensions[r].height or dflt for r in range(r1, (r2 or r1) + 1))

    def put(self, row: int, col: int, value) -> None:
        """A value written as the template wrote that cell (a number as text, with the cell's trailing spaces)."""
        if isinstance(value, str):
            value = value + self.pad.get((row, col), "") if value else (self.pad.get((row, col)) or None)
        self.ws.cell(row, col).value = value

    def heading(self, r1: int, r2: int) -> int:
        """A page's heading block, its page label (अ-n/A-n) the next of the book."""
        self.page_h = 0.0
        start = self.block(r1, r2)
        self.put(start, 1, self.nm.next_page())
        return start

    def page_break(self) -> None:
        self.ws.row_breaks.append(Break(id=self.r))


# ------------------------------------------------------------------ the six annexures

def _y1(yd, s, smp, c=None):
    return None if yd is None else A._y1_counts(yd, s, smp, c)


def xix(o: Out, rep, nm):
    seasons = rep.seasons[:2]
    o.heading(1, 8)
    for k, (s, _) in enumerate(seasons):
        o.set_season(s)
        o.put(6, 3 + 6 * k, o._shown(6, 3))
    for yd, r1 in ((rep.cy, 9), (rep.py, 21)):
        start = o.block(r1, r1 + 11)
        for k, (s, _) in enumerate(seasons):
            for j, (_, smp) in enumerate(AGENCY):
                col = 3 + 2 * j + 6 * k
                v = _y1(yd, s, smp)
                if v is None or not v["Planned"]:
                    for r in range(start + 1, start + 12):
                        o.put(r, col, "")
                    continue
                o.put(start + 1, col, f"{v['Planned']}")
                for i in range(5):
                    show = i == 0 or v["counts"][i]
                    o.put(start + 2 + 2 * i, col, f"{v['counts'][i]}" if show else "")
                    o.put(start + 3 + 2 * i, col, pct(v["pcts"][i]) if show else "")
    o.block(33)
    if len(seasons) == 2:
        _xix_second_season(o)


def _xix_second_season(o: Out) -> None:
    """Season II: columns I – N in the style of C – H (headings, borders, widths), the heading merges widened."""
    ws = o.ws
    for r in range(4, o.r + 1):
        for c in range(3, 9):
            s_, d = ws.cell(r, c), ws.cell(r, c + 6)
            if s_.has_style:
                d._style = copy.copy(s_._style)
            if r in (7, 33) and d.value is None:
                d.value = s_.value
    for j, n in enumerate((6, 7, 8)):
        ws.cell(8, 9 + 2 * j).value = f"({n})"
    for c in range(3, 9):
        w = ws.column_dimensions[cl(c)].width or o.tpl.column_dimensions[cl(c)].width
        ws.column_dimensions[cl(c + 6)].width = w
    for m in list(ws.merged_cells.ranges):
        if m.max_col != 8 or m.min_row > 8:
            continue
        if m.min_row in (1, 3, 4, 5):                       # the full-width headings
            ws.unmerge_cells(str(m))
            ws.merge_cells(start_row=m.min_row, end_row=m.max_row, start_column=m.min_col, end_column=14)
        elif m.min_row == 2:                                # 'अनुलग्नक-XIX/ANNEX-XIX' moves to the right edge
            ws.unmerge_cells(str(m))
            src = ws.cell(2, m.min_col)
            dst = ws.cell(2, m.min_col + 6)
            dst.value, dst._style, src.value = src.value, copy.copy(src._style), None
            ws.merge_cells(start_row=2, end_row=2, start_column=m.min_col + 6, end_column=14)
    for m in list(ws.merged_cells.ranges):
        if 6 <= m.min_row <= 8 and m.min_col >= 3 and m.max_col <= 8:
            ws.merge_cells(start_row=m.min_row, end_row=m.max_row, start_column=m.min_col + 6,
                           end_column=m.max_col + 6)
    ws.sheet_properties.pageSetUpPr.fitToPage = True        # one page wide
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0


def _crop_pages(o: Out, rep, head, contd, season_row, crop_block, end_row, fill, total=None):
    """XX / XXIV: the heading; per season a season row and its crop blocks; a page holds what page 1 of the template
    holds (rows 1 .. end_row), ends with the closing row (end_row), and the next starts with the 'Contd..' heading."""
    cap = o.height(1, end_row)
    o.heading(*head)
    block_h = o.height(*crop_block)

    def room(h: float):
        if o.page_h + h + o.height(end_row) > cap + 0.5:
            o.block(end_row)
            o.page_break()
            o.heading(*contd)

    for s, _ in rep.seasons[:2]:
        o.set_season(s)
        room(o.height(season_row) + block_h)                # a season row never ends a page alone
        r = o.block(season_row)
        if not str(o.tpl.cell(season_row, 1).value).startswith("="):   # XX: typed 'खरीफ/KHARIF' in the template
            o.put(r, 1, "/".join(o.nm.season(s)))
        for k, (c, _) in enumerate(rep.crops(s)):
            room(block_h)
            fill(o.block(*crop_block), s, c, k)
        if total:
            room(o.height(*total[0]))
            total[1](s)
    o.block(end_row)


def xx(o: Out, rep, nm):
    def fill(r, s, c, k):
        o.put(r, 1, nm.crop(s, c))
        for j, (_, smp) in enumerate(AGENCY):
            row = r + 1 + 2 * j
            for yd, c0 in ((rep.cy, 2), (rep.py, 8)):
                v = _y1(yd, s, smp, c)
                if v is None or not v["Planned"]:
                    for i in range(6):
                        o.put(row, c0 + i, "")
                        o.put(row + 1, c0 + i, "")
                    continue
                o.put(row, c0, f"{v['Planned']}")
                for i in range(5):
                    o.put(row, c0 + 1 + i, f"{v['counts'][i]}")
                    o.put(row + 1, c0 + 1 + i, pct(v["pcts"][i]))

    _crop_pages(o, rep, (1, 7), (38, 44), 8, (9, 15), 37, fill)


def _a24(g) -> list[str]:
    """Annex-XXIV cells of one crop / agency (as c08_annexures._y3_a24, written 'n(  p)')."""
    checked = A._n(g, STAGIN=1) + A._n(g, STAGIN=2)
    eq, ju, de = ([A._n(g, CCE=k) for k in grp] for grp in ("123", "456", "789"))
    vals = [sum(eq), eq[1], sum(ju), ju[1], sum(de), de[1]]
    if not checked:
        return [npc(v, 0.0) for v in vals]
    tot = A.fix100([A.pct(sum(eq), checked, 3), A.pct(sum(ju), checked, 3), A.pct(sum(de), checked, 3)])
    ps = [tot[0], A.pct(eq[1], checked), tot[1], A.pct(ju[1], checked), tot[2], A.pct(de[1], checked)]
    return [npc(v, p) for v, p in zip(vals, ps)]


def xxiv(o: Out, rep, nm):
    def agencies(r, s, c=None):
        for j, (_, smp) in enumerate(AGENCY):
            for yd, c0 in ((rep.cy, 3), (rep.py, 9)):
                vals = _a24(A._g(yd, s, smp, c)) if yd is not None else [""] * 6
                for i, v in enumerate(vals):
                    o.put(r + 1 + j, c0 + i, v)

    def fill(r, s, c, k):
        o.put(r, 1, k + 1)
        o.put(r, 2, nm.crop(s, c))
        agencies(r, s, c)

    def total(s):
        r = o.block(139, 142)
        if len(rep.seasons) > 1:
            hi, en = nm.season(s)
            o.put(r, 2, f"कुल-{hi}/TOTAL-{en}")
        agencies(r, s)

    _crop_pages(o, rep, (1, 7), (30, 36), 8, (9, 12), 29, fill, ((139, 142), total))


def xxi(o: Out, rep, nm):
    o.heading(1, 7)
    cols = [("RSV", r) for r in A.SUBST] + [("RCSSN", r) for r in A.SUBST]
    blocks = [(rep.cy, 8, s) for s, _ in rep.seasons[:2]] + [(rep.py, 25, s) for s, _ in rep.seasons[:2]]
    for b, (yd, title_row, s) in enumerate(blocks):
        o.set_season(s)
        o.block(title_row)
        tot, chk = [0] * 8, 0
        for k, (c, _) in enumerate(rep.crops(s), 1):
            r = o.block(9)
            o.put(r, 1, k)
            o.put(r, 2, nm.crop(s, c))
            if yd is None:
                for i in range(8):
                    o.put(r, 3 + i, "")
                continue
            g = A._g(yd, s, ["1", "2"], c)
            ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
            checked = A._n(g, STAGIN=1) + A._n(g, STAGIN=2)
            chk += checked
            for i, (fld, code_) in enumerate(cols):
                v = A._n(ok, **{fld: code_})
                tot[i] += v
                o.put(r, 3 + i, npc(v, A.pct(v, checked)))
        r = o.block(41 if b == len(blocks) - 1 else 24)
        for i in range(8):
            o.put(r, 3 + i, npc(tot[i], A.pct(tot[i], chk)) if yd is not None else "")
    o.block(42, 48)


XXII_ROWS = [(8, "checked"), (9, "E0"), (12, "E1"), (14, "E2"), (16, "E9"), (18, "E10"), (20, "E11"), (22, "E12"),
             (24, "E13"), (27, "E3"), (29, "E4"), (31, "E5"), (33, "E6"), (35, "E7"), (37, "E8"), (39, "E14"),
             (41, "E15"), (43, "E16")]


def xxii(o: Out, rep, nm):
    for k, (s, _) in enumerate(rep.seasons[:2]):
        if k:
            o.page_break()
        o.set_season(s)
        start = o.heading(1, 45)
        for yd, c0 in ((rep.cy, 3), (rep.py, 6)):
            for j, (_, smp) in enumerate(AGENCY):
                t = A._y5_totals(yd, s, smp) if yd is not None else None
                for row, key in XXII_ROWS:
                    r = start + row - 1
                    o.put(r, c0 + j, f"{t[key]}" if t else "")
                    if key != "checked":
                        o.put(r + 1, c0 + j, pct(A.pct(t[key], t["checked"])) if t else "")


def xxiii(o: Out, rep, nm):
    o.heading(1, 7)
    blocks = [(rep.cy, (8, 11), s) for s, _ in rep.seasons[:2]] + [(rep.py, (16, 19), s) for s, _ in rep.seasons[:2]]
    for yd, rows, s in blocks:
        o.set_season(s)
        r = o.block(*rows)
        for j, (_, smp) in enumerate(AGENCY):
            g = A._g(yd, s, smp) if yd is not None else None
            for i, (_, fld) in enumerate(A.EQUIPMENT):
                if g is None:
                    o.put(r + 1 + j, 2 + i, "")
                    o.put(r + 1 + j, 6 + i, "")
                    continue
                v = A._y6_counts(g, fld)
                total = v[-1]
                not_sup, not_use = v[10], v[1] + v[2] + v[3]
                p_use = A.xround(sum(A.pct(x, total) for x in v[1:4]), 1) if total else 0.0   # rounded one by one (old)
                o.put(r + 1 + j, 2 + i, npc(not_sup, A.pct(not_sup, total)))
                o.put(r + 1 + j, 6 + i, npc(not_use, p_use))
    o.block(24)
    if len(blocks) > 2:                                     # two seasons: the four blocks on one page
        o.ws.sheet_properties.pageSetUpPr.fitToPage = True
        o.ws.page_setup.fitToWidth, o.ws.page_setup.fitToHeight = 1, 1


BUILD = {"Annex-XIX": xix, "Annex-XX": xx, "Annex-XXI": xxi, "Annex-XXII": xxii, "Annex-XXIII": xxiii,
         "Annex-XXIV": xxiv}


# ------------------------------------------------------------------ Hindi / English books from the Bilingual one

def _part(p: str, lang: str) -> str | None:
    """One '/'-separated part of a line in one language: None when it belongs to the other language only."""
    dev, lat = bool(DEV.search(p)), bool(LATIN.search(p))
    if dev and lat:                                         # both in one part: drop the other language's words
        drop = LATIN if lang == "Hi" else DEV
        return " ".join(w for w in p.split() if not drop.search(w))
    if lang == "Hi" and lat and not KEEP_LATIN.match(p):
        return None
    if lang == "Eng" and dev:
        return None
    return p


def one_language(v, lang: str):
    if not isinstance(v, str) or not (DEV.search(v) or (lang == "Hi" and LATIN.search(v))):
        return v
    pad = v[len(v.rstrip(" ")):]
    lines = []
    for line in v.split("\n"):
        parts = [_part(p, lang) for p in line.split("/")]
        kept = [p.strip() for p in parts if p is not None and p.strip()]
        if kept:
            lines.append("/ ".join(kept))
    return "\n".join(lines) + pad if lines else None


def _to_language(wb, lang: str) -> None:
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str):
                    c.value = one_language(c.value, lang)


# ------------------------------------------------------------------ export

def export(rep: A.Report, folder: Path, variants: list[str], state_code: str = "") -> list[Path]:
    """1Annexures(<variant>).xlsx for each of 'Bi', 'Hi', 'Eng' asked, in the final standard. Returns their paths."""
    if len(rep.seasons) > 2:
        raise ValueError("The annexure books have room for two seasons – a report has one or two.")
    folder.mkdir(parents=True, exist_ok=True)
    nm = Names(rep)
    shown = load_workbook(TEMPLATE, data_only=True)
    out = []
    for v in variants:
        nm.page = FIRST_PAGE
        wb = load_workbook(TEMPLATE)
        for name in SHEETS:
            BUILD[name](Out(wb, wb[name], shown[name], rep, nm), rep, nm)
        for ws in list(wb.worksheets):                      # the template sheets go; the new ones take their names
            if not ws.title.endswith(" (new)"):
                wb.remove(ws)
        for ws in wb.worksheets:
            ws.title = ws.title[:-len(" (new)")]
        if v != "Bi":
            _to_language(wb, v)
        wb.active = 0
        p = folder / f"1Annexures({v}).xlsx"
        wb.save(p)
        out.append(p)
    return out
