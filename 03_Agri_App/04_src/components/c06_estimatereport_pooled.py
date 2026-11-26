"""6. Estimate Report — Combined & Pooled: the office's two workbooks (01_raw_data/est_rep_calc/01 Central.xlsx and
02 State.xlsx) worked out in the app.

For one crop of one season (a crop GROUP: the crop codes with the same first two digits, e.g. 0611 MAIZE_UI +
0612 MAIZE_IR, or 0623 MAIZE_HYBRID + 0624 MAIZE_L; a single code such as 9100 PADDY_KAR is a group of one):

  comb (Central), comb (State)      "INTERMEDIATE TABLE 4" – the estimate of the sample from its two strata
        Yc = (Y1·A1 + Y2·A2) / (A1 + A2)                       rounded to 0
        Vc = (A1²·V1 + A2²·V2) / (A1 + A2)²                     rounded to 0
        SE = √Vc (2 dec.)    %SE = SE × 100 / Yc (2 dec.)
        T-test current vs previous year, current vs CES
  pool                              the pooled estimate of Central (1) and State (2)
        Yp = (Y1·V2 + Y2·V1) / (V1 + V2)                        rounded to 0
        Vp = V1·V2 / (V1 + V2)                                  rounded to 0
        T-test pooled vs previous pooled, pooled vs CES, Central vs State
  T-test       t = |round((Y1 − Y2) / √(V1 + V2), 2)|, significant when t > 1.96; CES variance = (CES × %SE / 100)²
  Confidential Sheets (Hindi)       Central, State, and all three rows (केन्द्रीय, राज्य, एकीकृत)

Inputs come from the app where it has them (tinted on the page; typing over a value keeps the typed one):
  Y, V, A of each stratum + analysed = the estimate saved in 5. Estimates (A = its total area);
  planned = master list; previous year = the same worked out from last year's saved estimates.
CES, previous figures not in the app and the names are typed.
Typed figures: 00_database/06_estimatereport/<STATE>/<YEAR>/pooled_inputs.csv (one row per season + crop group).
Export: the office's workbook (six sheets, live formulas – 04_src/resources/est_rep_pooled.xlsx, made by
utils/make_pooled_template.py) in 02_artifacts/06_estimatereport/<STATE>/<YEAR>/Pooled/<CROP>/<dd.mm.yyyy>/.
"""
from __future__ import annotations

import math
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from src.components import c05_estimates as est
from src.components import c06_estimatereport as er
from src.utils import schedules

INPUTS_FILE = "pooled_inputs.csv"
TEMPLATE = Path("04_src") / "resources" / "est_rep_pooled.xlsx"
CRITICAL = 1.96
NA = "N.A."
SAMPLES = (("1", "Central"), ("2", "State"))

# typed / filled figures; per sample: <field> <1|2> (1 = Central, 2 = State)
PER_SAMPLE = ["Y1", "V1", "A1", "Y2", "V2", "A2", "PLANNED", "ANALYSED", "PREV YIELD", "PREV VARIANCE"]
COMMON = ["CES YIELD", "CES %SE", "CES YEAR", "PREV POOLED YIELD", "PREV POOLED VARIANCE",
          "STATE HI", "SEASON HI", "CROP HI", "LABEL 1", "LABEL 2", "PREPARED BY", "LETTER DATE"]
FIELDS = [f"{f} {s}" for s, _ in SAMPLES for f in PER_SAMPLE] + COMMON
INPUT_COLUMNS = ["KEY", "CROP", *FIELDS, "SAVED_ON"]
TEXT_FIELDS = {"CES YEAR", "STATE HI", "SEASON HI", "CROP HI", "LABEL 1", "LABEL 2", "PREPARED BY", "LETTER DATE"}


def xround(x: float, nd: int = 0) -> float:
    """Excel's ROUND (half away from zero), not Python's banker's rounding."""
    q = Decimal(1).scaleb(-nd)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))     # HALF_UP = away from zero


def _num(v) -> float | None:
    return est._num(v)


def _g(v) -> str:
    return "" if v is None else f"{v:.15g}"          # all digits ('{:g}' turns 1283170 into 1.28317e+06)


# ------------------------------------------------------------------ the crop group

@dataclass(frozen=True)
class Group:
    season: str
    group: str                       # first two digits of the crop codes
    codes: tuple[str, ...]           # 1 or 2 crop codes (stratum 1, stratum 2)

    @property
    def key(self) -> str:
        return f"{self.season}-{self.group}"


def group_of(ml: pd.DataFrame, season: str, crop: str) -> tuple[Group | None, str]:
    """The group of a crop code in a season, and a warning ('' when none)."""
    if ml.empty or not crop or not season:
        return None, ""
    codes = sorted(set(ml.loc[(ml["SEASONCODE"] == season) & (ml["CROPCODE"].str[:2] == crop[:2]), "CROPCODE"]))
    if not codes:
        return None, ""
    warn = ""
    if len(codes) > 2:
        # more than two codes share the digits (e.g. cotton A / B): keep the pair of the chosen code
        pair = [c for c in codes if c[:3] == crop[:3]] or [crop]
        warn = (f"Crop codes {', '.join(codes)} share the digits {crop[:2]}: only {' + '.join(pair[:2])} are "
                "combined.")
        codes = pair[:2]
    return Group(season, crop[:2], tuple(codes)), warn


_IRR = re.compile(r"_(UI|IR|I)(?=$|_)")
_HI_IRR = re.compile(r"\s*-\s*(असिंचित|सिंचित)")
_SEP = " _-"


def _common(names: list[str], strip: re.Pattern) -> str:
    """The crop's name without the stratum part: COTTON_UI_A + COTTON_IR_A -> COTTON_A, MAIZE_HYBRID + MAIZE_L ->
    MAIZE (मक्का- अ.उ. + मक्का-स्था. -> मक्का)."""
    if len(names) == 1:
        return names[0]
    bare = [strip.sub("", n).strip(_SEP) for n in names]
    if len(set(bare)) == 1:
        return bare[0]
    prefix = os.path.commonprefix(names).strip(_SEP)
    return prefix or names[0]


def stratum_label(name: str, crop: str) -> str:
    n = name.upper()
    if re.search(r"(^|_)UI($|_)", n):
        return "UNIRRIGATED"
    if re.search(r"(^|_)(IR|I)($|_)", n):
        return "IRRIGATED"
    rest = n[len(crop):].strip(_SEP) if crop and n.startswith(crop.upper()) else ""
    return {"HY": "HYBRID", "L": "LOCAL"}.get(rest, rest or n)


def group_names(ml: pd.DataFrame, g: Group) -> dict:
    """English / Hindi names of the state, season, crop (without the irrigated / unirrigated part)."""
    r = ml[(ml["SEASONCODE"] == g.season) & (ml["CROPCODE"].isin(g.codes))]

    def first(col: str, code: str | None = None) -> str:
        rows = r[r["CROPCODE"] == code] if code else r
        return str(rows[col].iloc[0]).strip() if len(rows) and col in rows else ""

    crops = [first("CROPNAME", c) for c in g.codes]
    crop_en = _common(crops, _IRR)
    crop_hi = _common([first("HCROPNAME", c) for c in g.codes], _HI_IRR)
    return {"state": first("STATENAME"), "season": first("SEASONNAME"), "crop": crop_en,
            "state_hi": first("HSTATENAME"), "season_hi": first("HSEASONNAME"), "crop_hi": crop_hi,
            "crops": crops, "labels": [stratum_label(c, crop_en) for c in crops]}


# ------------------------------------------------------------------ figures filled from the app

def _estimate(state: str, year: str, season: str, sample: str, code: str):
    """The estimate saved in 5. Estimates for one crop code + sample (YearEstimate), or None."""
    return er.year_estimate(state, year, est.Selection(((season, sample, code),)))


def app_figures(state: str, year: str, g: Group) -> tuple[dict[str, str], dict]:
    """Figures the app has for a year: Y/V/A per stratum and sample, planned, analysed. Also the estimates."""
    out, found = {}, {}
    for s, _ in SAMPLES:
        planned = analysed = 0
        have_planned = False
        for i, code in enumerate(g.codes, 1):
            ye = _estimate(state, year, g.season, s, code)
            found[(s, code)] = ye
            if ye is None:
                continue
            have_planned = True
            planned += int(ye.counts.get("PLANNED", 0) or 0)
            res = ye.result
            if res is not None:
                analysed += res.analysed
                out[f"Y{i} {s}"] = _g(res.yield_kg_ha)
                if not isinstance(res.variance, str):
                    out[f"V{i} {s}"] = _g(res.variance)
                out[f"A{i} {s}"] = _g(res.total_area)
        if have_planned:
            out[f"PLANNED {s}"] = str(planned)
        if all(found[(s, c)] is not None and found[(s, c)].result is not None for c in g.codes):
            out[f"ANALYSED {s}"] = str(analysed)
    if len(g.codes) == 1:                                      # one stratum: nothing to add
        for s, _ in SAMPLES:
            out.update({f"Y2 {s}": "0", f"V2 {s}": "0", f"A2 {s}": "0"})
    return out, found


# ------------------------------------------------------------------ the calculation (as the workbook's formulas)

@dataclass
class Combined:
    sample: str
    y1: float | None
    v1: float | None
    a1: float | None
    y2: float | None
    v2: float | None
    a2: float | None
    yc: float | None = None
    vc: float | None = None
    se: float | None = None
    pct_se: float | None = None
    problem: str = ""


@dataclass
class TTest:
    name: str
    y1: float | None
    v1: float | None
    y2: float | None
    v2: float | None
    t: float | None = None

    @property
    def significant(self) -> bool:
        return self.t is not None and self.t > CRITICAL

    @property
    def result(self) -> str:
        if self.t is None:
            return NA
        return "Significant" if self.significant else "Insignificant"

    @property
    def sign(self) -> str:
        return NA if self.t is None else (">" if self.significant else "<")


def t_test(name: str, y1, v1, y2, v2) -> TTest:
    tt = TTest(name, y1, v1, y2, v2)
    if None not in (y1, v1, y2, v2) and v1 + v2 > 0:
        tt.t = abs(xround((y1 - y2) / math.sqrt(v1 + v2), 2))
    return tt


def combine(sample: str, y1, v1, a1, y2, v2, a2) -> Combined:
    c = Combined(sample, y1, v1, a1, y2, v2, a2)
    if None in (y1, v1, a1, y2, v2, a2):
        c.problem = "yield, variance and area of both strata are needed"
        return c
    a = a1 + a2
    if a <= 0:
        c.problem = "the area is 0"
        return c
    c.yc = xround((y1 * a1 + y2 * a2) / a, 0)
    c.vc = xround((v1 * a1 * a1 + v2 * a2 * a2) / (a * a), 0)
    c.se = xround(math.sqrt(c.vc), 2)
    c.pct_se = xround(c.se * 100 / c.yc, 2) if c.yc else None
    return c


@dataclass
class Pooled:
    yp: float | None = None
    vp: float | None = None
    se: float | None = None
    pct_se: float | None = None
    problem: str = ""


def pool(c: Combined, s: Combined) -> Pooled:
    p = Pooled()
    if c.yc is None or s.yc is None:
        p.problem = "both combined estimates (Central and State) are needed"
        return p
    if c.vc + s.vc <= 0:
        p.problem = "the variances are 0"
        return p
    p.yp = xround((c.yc * s.vc + s.yc * c.vc) / (c.vc + s.vc), 0)
    p.vp = xround(c.vc * s.vc / (c.vc + s.vc), 0)
    p.se = xround(math.sqrt(p.vp), 2)
    p.pct_se = xround(p.se * 100 / p.yp, 2) if p.yp else None
    return p


# ------------------------------------------------------------------ the report

@dataclass
class PooledReport:
    state: str
    year: str
    group: Group
    names: dict
    auto: dict = field(default_factory=dict)            # filled from the app
    typed: dict = field(default_factory=dict)           # typed (wins)
    prev_auto_from: str = ""                            # which previous-year figures came from the app
    warning: str = ""

    def value(self, key: str) -> str:
        return self.typed.get(key) or self.auto.get(key, "")

    def num(self, key: str) -> float | None:
        return _num(self.value(key))

    # --- results
    def combined(self, s: str) -> Combined:
        n = lambda f: self.num(f"{f} {s}")                                  # noqa: E731
        return combine(s, n("Y1"), n("V1"), n("A1"), n("Y2"), n("V2"), n("A2"))

    @property
    def ces_variance(self) -> float | None:
        y, se = self.num("CES YIELD"), self.num("CES %SE")
        return (y * se / 100) ** 2 if y is not None and se is not None else None

    def tests(self, s: str) -> list[TTest]:
        c = self.combined(s)
        return [t_test("Current vs Previous", c.yc, c.vc, self.num(f"PREV YIELD {s}"), self.num(f"PREV VARIANCE {s}")),
                t_test("Current vs CES", c.yc, c.vc, self.num("CES YIELD"), self.ces_variance)]

    @property
    def pooled(self) -> Pooled:
        return pool(self.combined("1"), self.combined("2"))

    def pooled_tests(self) -> list[TTest]:
        c, s, p = self.combined("1"), self.combined("2"), self.pooled
        return [t_test("Current Pooled vs Previous Pooled", p.yp, p.vp, self.num("PREV POOLED YIELD"),
                       self.num("PREV POOLED VARIANCE")),
                t_test("Pooled vs CES", p.yp, p.vp, self.num("CES YIELD"), self.ces_variance),
                t_test("Central vs State", c.yc, c.vc, s.yc, s.vc)]

    # --- confidential sheet rows
    def conf_row(self, which: str) -> dict:
        """Columns (2) – (9) for 'Central', 'State' or 'Pooled'."""
        if which == "Pooled":
            p, tests = self.pooled, self.pooled_tests()
            y, se = p.yp, p.pct_se
            py, pv = self.num("PREV POOLED YIELD"), self.num("PREV POOLED VARIANCE")
            planned = [self.num(f"PLANNED {s}") for s, _ in SAMPLES]
            analysed = [self.num(f"ANALYSED {s}") for s, _ in SAMPLES]
            planned = sum(planned) if None not in planned else None
            analysed = sum(analysed) if None not in analysed else None
        else:
            s = "1" if which == "Central" else "2"
            c, tests = self.combined(s), self.tests(s)
            y, se = c.yc, c.pct_se
            py, pv = self.num(f"PREV YIELD {s}"), self.num(f"PREV VARIANCE {s}")
            planned, analysed = self.num(f"PLANNED {s}"), self.num(f"ANALYSED {s}")
        ces_y, ces_se = self.num("CES YIELD"), self.num("CES %SE")
        prev_se = xround(math.sqrt(pv) * 100 / py, 2) if py and pv is not None else None
        diff = lambda a, b: xround((a - b) * 100 / b, 2) if a is not None and b else None        # noqa: E731
        return {"yield": y, "se": se, "prev": py, "prev_se": prev_se, "ces": ces_y, "ces_se": ces_se,
                "diff_prev": diff(y, py), "star_prev": "*" if tests[0].significant else "",
                "diff_ces": diff(y, ces_y), "star_ces": "*" if tests[1].significant else "",
                "planned": planned, "analysed": analysed,
                "response": xround(analysed * 100 / planned, 1) if planned and analysed is not None else None}

    @property
    def letter_ref(self) -> str:
        return (f"टी-14011 / {self.value('STATE HI')} / प्राक्क. / {self.value('CROP HI')} / {self.year} / कृ.सां.")


AGENCY_HI = {"Central": "केन्द्रीय", "State": "राज्य", "Pooled": "एकीकृत"}


# ------------------------------------------------------------------ typed figures

def load_typed(state: str, year: str, g: Group) -> dict[str, str]:
    f = er.folder(state, year) / INPUTS_FILE
    if not f.exists():
        return {}
    df = est._read(f, INPUT_COLUMNS)
    row = df[df["KEY"] == g.key]
    return {k: v for k, v in row.iloc[0].items() if k in FIELDS and v} if len(row) else {}


def save_typed(state: str, year: str, g: Group, crop: str, typed: dict[str, str]) -> None:
    """Replace this group's row of pooled_inputs.csv (old copy to 05_backup first)."""
    d = er.folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    f = d / INPUTS_FILE
    if f.exists():
        b = er.BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
    df = est._read(f, INPUT_COLUMNS)
    row = {"KEY": g.key, "CROP": crop, **{k: typed.get(k, "") for k in FIELDS},
           "SAVED_ON": f"{datetime.now():%Y-%m-%d %H:%M:%S}"}
    df = pd.concat([df[df["KEY"] != g.key], pd.DataFrame([row])], ignore_index=True).reindex(columns=INPUT_COLUMNS)
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)


# ------------------------------------------------------------------ build

def build(state: str, year: str, season: str, crop: str) -> PooledReport | None:
    """The report of the crop group of a crop code in a season, or None when the crop is not in the master list."""
    ml = er.master_list(state, year)
    g, warn = group_of(ml, season, crop)
    if g is None:
        return None
    nm = group_names(ml, g)
    auto, _ = app_figures(state, year, g)
    auto.update({"STATE HI": nm["state_hi"], "SEASON HI": nm["season_hi"], "CROP HI": nm["crop_hi"],
                 "LABEL 1": nm["labels"][0], "LABEL 2": nm["labels"][1] if len(nm["labels"]) > 1 else ""})
    # previous year from the app: the same group worked out from last year's saved estimates
    prev_year = er.previous_year(year)
    pml = er.master_list(state, prev_year)
    pg, _ = group_of(pml, season, crop)
    prev_from = []
    if pg is not None and pg.codes == g.codes:
        pauto, _ = app_figures(state, prev_year, pg)
        ptyped = load_typed(state, prev_year, pg)
        prev = PooledReport(state, prev_year, pg, {}, pauto, ptyped)
        for s, name in SAMPLES:
            c = prev.combined(s)
            if c.yc is not None:
                auto[f"PREV YIELD {s}"], auto[f"PREV VARIANCE {s}"] = _g(c.yc), _g(c.vc)
                prev_from.append(name)
        p = prev.pooled
        if p.yp is not None:
            auto["PREV POOLED YIELD"], auto["PREV POOLED VARIANCE"] = _g(p.yp), _g(p.vp)
            prev_from.append("Pooled")
    # a crop with one code: the CES typed for its per-estimate report (Information Accompanying) is the same CES
    if len(g.codes) == 1:
        t = er.load_typed(state, year, est.Selection(((season, "1", g.codes[0]),)))
        auto.update({k: t[k] for k in ("CES YIELD", "CES %SE", "CES YEAR") if t.get(k)})
    inp = est.load_inputs(state, year, est.Selection(((season, "1", g.codes[0]),)))
    if inp.prepared_by:
        auto["PREPARED BY"] = inp.prepared_by
    rep = PooledReport(state, year, g, nm, {k: v for k, v in auto.items() if v != ""}, load_typed(state, year, g),
                       ", ".join(prev_from), warn)
    return rep


def stamp(state: str, year: str) -> tuple:
    """Changes when anything the report reads changes (refresh key for the page)."""
    files = [est.folder(state, year) / est.INPUTS_FILE, est.folder(state, year) / est.AREAS_FILE,
             er.folder(state, year) / INPUTS_FILE, er.folder(state, year) / er.INPUTS_FILE]
    py = er.previous_year(year)
    files += [est.folder(state, py) / est.INPUTS_FILE, est.folder(state, py) / est.AREAS_FILE,
              er.folder(state, py) / INPUTS_FILE]
    return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files) + (schedules.stamp(state, year),)


# ------------------------------------------------------------------ tables (the page and the pipeline)

def _f(v, nd=None):
    if v is None:
        return NA
    return v if nd is None else xround(v, nd)


def combined_table(rep: PooledReport, s: str) -> pd.DataFrame:
    c = rep.combined(s)
    l1, l2 = rep.value("LABEL 1") or "Stratum 1", rep.value("LABEL 2") or "Stratum 2"
    rows = [{"": f"{l1} (1)", "Yield rate (kg/ha)": _f(c.y1), "Variance": _f(c.v1), "Area (ha)": _f(c.a1)},
            {"": f"{l2} (2)", "Yield rate (kg/ha)": _f(c.y2), "Variance": _f(c.v2), "Area (ha)": _f(c.a2)},
            {"": "Combined", "Yield rate (kg/ha)": _f(c.yc), "Variance": _f(c.vc),
             "Area (ha)": _f(None if c.a1 is None or c.a2 is None else c.a1 + c.a2)}]
    return pd.DataFrame(rows)


def steps_table(yc, vc, se, pct, kind: str) -> pd.DataFrame:
    """The formula lines of the intermediate table, with their values."""
    if kind == "combined":
        rows = [("Combined yield Yc", "(Y1 × A1 + Y2 × A2) ÷ (A1 + A2)", yc, "kg/ha"),
                ("Combined variance Vc", "(A1² × V1 + A2² × V2) ÷ (A1 + A2)²", vc, "")]
    else:
        rows = [("Pooled yield Yp", "(Y1 × V2 + Y2 × V1) ÷ (V1 + V2)", yc, "kg/ha"),
                ("Pooled variance Vp", "(V1 × V2) ÷ (V1 + V2)", vc, "")]
    rows += [("SE", "√ Variance", se, ""), ("% SE", "SE × 100 ÷ Yield", pct, "")]
    return pd.DataFrame([{"": a, "Formula": b, "Value": _f(c), "Unit": d} for a, b, c, d in rows])


def tests_table(tests: list[TTest]) -> pd.DataFrame:
    return pd.DataFrame([{"Test": t.name, "Y1": _f(t.y1), "Y2": _f(t.y2), "V1": _f(t.v1, 2), "V2": _f(t.v2, 2),
                          "t = |Y1 − Y2| ÷ √(V1 + V2)": _f(t.t), "": t.sign, "Critical": CRITICAL,
                          "Result": t.result} for t in tests])


CONF_HEADS = ["(1) एजेंसी", "(2) चालू वर्ष", "(3) पिछला वर्ष", "(4) जी.सी.ई.एस.", "(5) % अंतर (2)-(3)",
              "(6) % अंतर (2)-(4)", "(7) नियोजित", "(8) विश्लेषित", "(9) % प्रत्युत्तर"]


def _pair(y, se) -> str:
    if y is None:
        return NA
    return f"{y:g} ({se:.2f})" if se is not None else f"{y:g} (NA)"


def conf_table(rep: PooledReport, which: list[str]) -> pd.DataFrame:
    rows = []
    for w in which:
        r = rep.conf_row(w)
        d = lambda v, star: NA if v is None else f"{v:.2f}{star}"           # noqa: E731
        rows.append(dict(zip(CONF_HEADS, [
            AGENCY_HI[w], _pair(r["yield"], r["se"]), _pair(r["prev"], r["prev_se"]), _pair(r["ces"], r["ces_se"]),
            d(r["diff_prev"], r["star_prev"]), d(r["diff_ces"], r["star_ces"]),
            "" if r["planned"] is None else f"{r['planned']:g}", "" if r["analysed"] is None else f"{r['analysed']:g}",
            NA if r["response"] is None else f"{r['response']:.1f}"])))
    return pd.DataFrame(rows, columns=CONF_HEADS)


# ------------------------------------------------------------------ export (the office's workbook)

def report_folder(rep: PooledReport, day: datetime | None = None) -> Path:
    return (er.ART / rep.state / rep.year / "Pooled" / est._safe(rep.names["crop"])
            / f"{(day or datetime.now()):%d.%m.%Y}")


def export(rep: PooledReport) -> Path:
    """The six sheets of the office's two workbooks in one file, the figures filled in, formulas live."""
    from openpyxl import load_workbook
    wb = load_workbook(TEMPLATE)
    c, s = wb["comb('c)"], wb["comb('S)"]

    def num(key):                       # missing figures -> "N.A." (the formulas show N.A. / NA)
        v = rep.num(key)
        return NA if v is None else (int(v) if float(v).is_integer() else v)

    def count(key):
        v = rep.num(key)
        return None if v is None else (int(v) if float(v).is_integer() else v)

    c["B5"], c["D5"], c["F5"] = rep.value("STATE HI"), rep.year, rep.value("CROP HI")
    c["B6"], c["E6"] = rep.value("SEASON HI"), rep.value("PREPARED BY")
    c["C18"], c["C19"], c["C20"] = num("CES YIELD"), num("CES %SE"), rep.value("CES YEAR") or NA
    for ws, smp in ((c, "1"), (s, "2")):
        ws["A9"] = rep.value("LABEL 1") or "STRATUM 1"
        ws["D9"] = rep.value("LABEL 2") or "-"
        for ref, f in (("C11", "Y1"), ("F11", "Y2"), ("C13", "V1"), ("F13", "V2"), ("C15", "A1"), ("F15", "A2")):
            ws[ref] = num(f"{f} {smp}")
        ws["H18"], ws["H19"] = count(f"PLANNED {smp}"), count(f"ANALYSED {smp}")
        ws["C22"], ws["C23"] = num(f"PREV YIELD {smp}"), num(f"PREV VARIANCE {smp}")
    s["H22"], s["H23"] = num("PREV POOLED YIELD"), num("PREV POOLED VARIANCE")
    for name in ("conf('C)", "conf('S)", "conf('P)"):
        if rep.value("LETTER DATE"):
            wb[name]["V24"] = rep.value("LETTER DATE")
    wb.calculation.fullCalcOnLoad = True
    made = datetime.now()
    folder = report_folder(rep, made)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{made:%Y-%m-%d_%H%M%S}_{rep.names['season']}_{rep.names['crop']}_combined_pooled.xlsx"
    wb.save(out)
    return out
