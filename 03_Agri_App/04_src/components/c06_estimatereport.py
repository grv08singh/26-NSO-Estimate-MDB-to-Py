"""6. Estimate Report — what goes out with an estimate of 5. Estimates (the office's workbook sheets):

  Information Accompanying   current year vs previous year: receipt of schedules, distribution of the green yield per
                             plot, ancillary information (irrigation, HY seed, fertiliser, manure, pesticides), crop
                             condition, reasons for crop damage; ICS and CES yields (SE%) of the 5 previous years; due
                             date, date of submission, ID
  T-test                     |Y1 − Y2| / √(V1 + V2) against 1.96: current vs previous year, current vs CES
  Confidential Sheet         the Hindi letter: yield (SE%) this year, previous year, CES; % difference (* = significant);
                             planned, analysed, % response

The estimate itself comes from 5. Estimates (its saved area sheet for the same selection). Previous-year figures are
filled from the app when last year's master list / schedules / saved estimate are in it; anything typed wins.
Typed figures: 00_database/06_estimatereport/<STATE>/<YEAR>/report_inputs.csv; the details on yield rate of the 5
previous years (ICS and CES yield, %SE – from the app or typed, all of them): yield_history.csv in the same folder,
one row per estimate + year (next year's report starts from it). Export: one Excel workbook in
02_artifacts/06_estimatereport/<STATE>/<YEAR>/<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/.
"""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.components import c05_estimates as est
from src.utils import folders as F
from src.utils import schedules

DB = Path("00_database") / F.ESTIMATE_REPORT
ART = Path("02_artifacts") / F.ESTIMATE_REPORT
BACKUP = Path("05_backup") / F.ESTIMATE_REPORT
ML = Path("00_database") / F.MASTER_LIST
INPUTS_FILE = "report_inputs.csv"
YEARS_BACK = 5

# the counts of the Information Accompanying sheet (est.information keys), in the sheet's order
RECEIPT = ["PLANNED", "ANALYSED", "MISSED", "LOST", "REJECTED", "NR"]
CLASSES = [c[0] for c in est.YIELD_CLASSES]
ANCILLARY = ["IRRIGATED", "HY SEED", "FERTILIZER", "MANURE", "PESTICIDE"]
CONDITION = ["GOOD", "NORMAL", "BELOW NORMAL", "DAMAGED"]
REASONS = ["HEAVY RAIN", "FLOOD", "DROUGHT", "PESTS", "OTHERS"]
COUNTS = RECEIPT + CLASSES + ANCILLARY + CONDITION + REASONS
LABELS = {"PLANNED": "Planned", "ANALYSED": "Analysed", "MISSED": "Missed", "LOST": "Lost", "REJECTED": "Rejected",
          "NR": "Not received", "IRRIGATED": "Irrigated", "HY SEED": "HY seed", "FERTILIZER": "Fertiliser",
          "MANURE": "Manure", "PESTICIDE": "Pesticides", "GOOD": "Good", "NORMAL": "Normal",
          "BELOW NORMAL": "Below normal", "DAMAGED": "Damaged", "HEAVY RAIN": "Heavy rain", "FLOOD": "Flood",
          "DROUGHT": "Drought", "PESTS": "Pests", "OTHERS": "Others",
          **{c: f"Yield {c} g" for c in CLASSES}}
CLASS_HEADS = ["0–1,000", "1,001–5,000", "5,001–10,000", "10,001–15,000", "15,001–20,000", "20,001–25,000",
               "Above 25,000"]

TYPED = (["CES YIELD", "CES %SE", "CES YEAR", "PREVIOUS YIELD", "PREVIOUS VARIANCE", "DUE DATE", "SUBMISSION DATE"]
         + [f"PREV {c}" for c in COUNTS])
INPUT_COLUMNS = ["KEY", *TYPED, "SAVED_ON"]

# Details on yield rate: ICS and CES yield (kg/ha) and %SE of the 5 previous years – their own CSV, one row per
# estimate + year: 00_database/06_estimatereport/<STATE>/<YEAR>/yield_history.csv
HISTORY_FILE = "yield_history.csv"
HISTORY_FIELDS = {"ICS": "ICS_YIELD", "ICS SE": "ICS_SE", "CES": "CES_YIELD", "CES SE": "CES_SE"}
HISTORY_COLUMNS = ["KEY", "SEASON", "CROP", "SAMPLE", "YEAR_BACK", "YEAR", *HISTORY_FIELDS.values(), "SAVED_ON"]
HISTORY = [f"{f} {i}" for i in range(1, YEARS_BACK + 1) for f in HISTORY_FIELDS]     # value keys, e.g. 'ICS SE 3'


def previous_year(year: str, back: int = 1) -> str:
    """'2025-26' -> '2024-25' (back = 1), '2023-24' (back = 2) …"""
    try:
        y = int(year[:4]) - back
    except ValueError:
        return ""
    return f"{y}-{str(y + 1)[2:]}"


def _num(v) -> float | None:
    return est._num(v)


# ------------------------------------------------------------------ the estimate of a year (from 5. Estimates)

@dataclass
class YearEstimate:
    year: str
    exps: pd.DataFrame                 # planned experiments of the selection with RC-7 ('' when no master list)
    counts: dict                       # est.information(exps)
    result: est.Result | None          # None when no area sheet is saved in 5. Estimates for that year
    inputs: est.Inputs


def master_list(state: str, year: str) -> pd.DataFrame:
    f = ML / state / year / "master_list.csv"
    if not f.exists():
        return pd.DataFrame()
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def year_estimate(state: str, year: str, sel: est.Selection) -> YearEstimate | None:
    """The selection in another year (same season / sample / crop codes), or None when that year is not in the app."""
    ml = master_list(state, year)
    if ml.empty:
        return None
    exps = est.experiments(ml, schedules.rc7(state, year), sel)
    if exps.empty:
        return None
    inputs = est.load_inputs(state, year, sel)
    res = None
    if inputs.areas and inputs.cf and inputs.driage and inputs.recovery:
        res = est.calculate(est.district_base(est.harvested(exps)), inputs)
    return YearEstimate(year, exps, est.information(exps), res, inputs)


# ------------------------------------------------------------------ typed figures

def folder(state: str, year: str) -> Path:
    return DB / state / year


def _read(f: Path, cols: list[str]) -> pd.DataFrame:
    if not f.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig").reindex(columns=cols, fill_value="")


def _write(f: Path, df: pd.DataFrame, state: str, year: str, stamp: str) -> None:
    """Write a CSV of the store (old copy to 05_backup/…/<stamp>/ first)."""
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        b = BACKUP / state / year / stamp
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)


def load_history(state: str, year: str, key: str) -> dict[str, str]:
    """The 5 previous years saved for an estimate (yield_history.csv), as value keys ('ICS 1', 'CES SE 2' …)."""
    df = _read(folder(state, year) / HISTORY_FILE, HISTORY_COLUMNS)
    out = {}
    for r in df[df["KEY"] == key].itertuples(index=False):
        for f, col in HISTORY_FIELDS.items():
            if getattr(r, col):
                out[f"{f} {r.YEAR_BACK}"] = getattr(r, col)
    return out


def history_by_year(state: str, year: str, key: str) -> dict[str, dict[str, str]]:
    """The same rows by calendar year: {'2022-23': {'ICS': '2210', 'ICS SE': '3.4', …}}."""
    df = _read(folder(state, year) / HISTORY_FILE, HISTORY_COLUMNS)
    return {r.YEAR: {f: getattr(r, col) for f, col in HISTORY_FIELDS.items() if getattr(r, col)}
            for r in df[df["KEY"] == key].itertuples(index=False)}


def saved_history(state: str, year: str, key: str) -> dict[str, str]:
    """Details on yield rate of the 5 previous years, ONLY from saved yield_history.csv files: for each of those years
    the newest earlier report that has it (e.g. for 2025-26, year 2022-23 from the 2024-25 file, else the 2023-24
    file …). Nothing found = blank on the screen, to be typed and saved. This year's own file wins (load_typed)."""
    out: dict[str, str] = {}
    for back in range(1, YEARS_BACK + 1):                     # the reports of the earlier years, newest first
        rows = history_by_year(state, previous_year(year, back), key)
        for i in range(1, YEARS_BACK + 1):
            for f, v in rows.get(previous_year(year, i), {}).items():
                out.setdefault(f"{f} {i}", v)
    return out


def load_typed(state: str, year: str, sel: est.Selection) -> dict[str, str]:
    """Saved figures: report_inputs.csv (typed) + yield_history.csv (the 5 previous years)."""
    df = _read(folder(state, year) / INPUTS_FILE, INPUT_COLUMNS)
    row = df[df["KEY"] == sel.key]
    out = {k: v for k, v in row.iloc[0].items() if k in TYPED and v} if len(row) else {}
    out.update(load_history(state, year, sel.key))
    return out


def save_typed(state: str, year: str, sel: est.Selection, typed: dict[str, str],
               history: dict[str, str] | None = None, crop: str = "") -> None:
    """Replace this selection's row of report_inputs.csv and, with `history` (every value of the 5-year table, from
    the app or typed), its 5 rows of yield_history.csv. Old copies to 05_backup first."""
    now = datetime.now()
    stamp, saved_on = f"{now:%Y-%m-%d_%H%M%S}", f"{now:%Y-%m-%d %H:%M:%S}"
    f = folder(state, year) / INPUTS_FILE
    df = _read(f, INPUT_COLUMNS)
    row = {"KEY": sel.key, **{k: typed.get(k, "") for k in TYPED}, "SAVED_ON": saved_on}
    df = pd.concat([df[df["KEY"] != sel.key], pd.DataFrame([row])], ignore_index=True).reindex(columns=INPUT_COLUMNS)
    _write(f, df, state, year, stamp)
    if history is None:
        return
    f = folder(state, year) / HISTORY_FILE
    df = _read(f, HISTORY_COLUMNS)
    rows = [{"KEY": sel.key, "SEASON": sel.season, "CROP": crop, "SAMPLE": sel.sample_label, "YEAR_BACK": str(i),
             "YEAR": previous_year(year, i), **{col: history.get(f"{fl} {i}", "") for fl, col in HISTORY_FIELDS.items()},
             "SAVED_ON": saved_on} for i in range(1, YEARS_BACK + 1)]
    df = pd.concat([df[df["KEY"] != sel.key], pd.DataFrame(rows, columns=HISTORY_COLUMNS)], ignore_index=True)
    _write(f, df.sort_values(["KEY", "YEAR_BACK"], key=lambda s: s.str.zfill(3)), state, year, stamp)


# ------------------------------------------------------------------ the report

@dataclass
class Report:
    state: str
    year: str
    sel: est.Selection
    nm: dict
    now: YearEstimate
    prev: YearEstimate | None                         # previous year in the app (or None)
    auto: dict = field(default_factory=dict)           # values filled from the app (same keys as TYPED)
    typed: dict = field(default_factory=dict)          # values typed (they win)

    def value(self, key: str) -> str:
        return self.typed.get(key) or self.auto.get(key, "")

    def prev_count(self, item: str) -> float | None:
        return _num(self.value(f"PREV {item}"))

    @property
    def info(self) -> dict:
        """The figures est.t_test / est.confidential read."""
        return {"PRE YIELD (C)": self.value("PREVIOUS YIELD"), "PRE VARIANCE (C)": self.value("PREVIOUS VARIANCE"),
                "CES YIELD": self.value("CES YIELD"), "CES %SE": self.value("CES %SE"),
                "CES REFF YEAR": self.value("CES YEAR")}

    @property
    def ident(self) -> str:
        code = str(self.now.exps["STATE"].iloc[0]) if len(self.now.exps) else ""
        return f"{code}{self.sel.season}{self.sel.sample_code}{self.sel.crop_label_code}{self.year}"


def build(state: str, year: str, sel: est.Selection) -> Report | None:
    """The report of a selection, or None when 5. Estimates has no saved estimate for it."""
    now = year_estimate(state, year, sel)
    if now is None or now.result is None:
        return None
    nm = est.names(master_list(state, year), sel)
    prev = year_estimate(state, previous_year(year), sel)
    auto = {}
    if prev is not None:
        auto.update({f"PREV {c}": str(prev.counts.get(c, "")) for c in COUNTS})
        if prev.result is not None:
            auto["PREVIOUS YIELD"] = f"{prev.result.yield_kg_ha:g}"
            if not isinstance(prev.result.variance, str):
                auto["PREVIOUS VARIANCE"] = f"{prev.result.variance:g}"
    auto.update(saved_history(state, year, sel.key))
    return Report(state, year, sel, nm, now, prev, auto, load_typed(state, year, sel))


# ------------------------------------------------------------------ Information Accompanying (tables)

def _pct(n, total) -> int | str:
    n, total = _num(n), _num(total)
    return round(n * 100 / total) if n is not None and total else ""


def history_values(rep: Report) -> dict[str, str]:
    """Every value of the 5-year table as shown (from the app or typed) – what yield_history.csv keeps."""
    return {k: rep.value(k) for k in HISTORY if rep.value(k)}


def yield_rate_table(rep: Report) -> pd.DataFrame:
    def pair(i, f):
        y, se = rep.value(f"{f} {i}"), rep.value(f"{f} SE {i}")
        return f"{y} ({se})" if y and se else y
    return pd.DataFrame([{"Year": previous_year(rep.year, i), "ICS yield (SE%)": pair(i, "ICS"),
                          "CES yield (SE%)": pair(i, "CES")} for i in range(1, YEARS_BACK + 1)])


def receipt_table(rep: Report) -> pd.DataFrame:
    rows = []
    for name, get in (("Current", lambda c: rep.now.counts.get(c)), ("Previous", rep.prev_count)):
        v = {c: get(c) for c in RECEIPT}
        rows.append({"Year": name, "Planned": v["PLANNED"], "Analysed": v["ANALYSED"],
                     "% analysed": _pct(v["ANALYSED"], v["PLANNED"]), "Missed": v["MISSED"], "Lost": v["LOST"],
                     "Rejected": v["REJECTED"], "Not received": v["NR"]})
    return pd.DataFrame(rows)


def distribution_table(rep: Report) -> pd.DataFrame:
    """Expts per class of green yield (grams per plot), % of analysed and cumulative %."""
    rows = []
    for name, get in (("Current", lambda c: rep.now.counts.get(c)), ("Previous", rep.prev_count)):
        n = [get(c) for c in CLASSES]
        total = get("ANALYSED")
        pct = [_pct(x, total) for x in n]
        cum, run = [], 0
        for x in n:
            run += _num(x) or 0
            cum.append(_pct(run, total) if total else "")
        rows += [{"Year": f"{name} expts", **dict(zip(CLASS_HEADS, n))},
                 {"Year": "% age", **dict(zip(CLASS_HEADS, pct))},
                 {"Year": "Cum. %", **dict(zip(CLASS_HEADS, cum))}]
    return pd.DataFrame(rows, columns=["Year", *CLASS_HEADS])


def _count_rows(rep: Report, items: list[str], total_col: bool) -> pd.DataFrame:
    rows = []
    for name, get in (("Current year", lambda c: rep.now.counts.get(c)), ("Previous year", rep.prev_count)):
        total = get("ANALYSED")
        rows.append({"Year": name, "No. / %": "Actual no.", **{LABELS[c]: get(c) for c in items},
                     **({"Total no. of expts": total} if total_col else {})})
        rows.append({"Year": "", "No. / %": "Percentage", **{LABELS[c]: _pct(get(c), total) for c in items},
                     **({"Total no. of expts": ""} if total_col else {})})
    return pd.DataFrame(rows)


def ancillary_table(rep: Report) -> pd.DataFrame:
    return _count_rows(rep, ANCILLARY, True)


def condition_table(rep: Report) -> pd.DataFrame:
    return _count_rows(rep, CONDITION, False)


def reasons_table(rep: Report) -> pd.DataFrame:
    return pd.DataFrame([{"Year": name, **{LABELS[c]: get(c) for c in REASONS}}
                         for name, get in (("Current year", lambda c: rep.now.counts.get(c)),
                                           ("Previous year", rep.prev_count))])


def t_test_table(rep: Report) -> pd.DataFrame:
    return pd.DataFrame(est.t_test(rep.now.result, rep.info))


# ------------------------------------------------------------------ Confidential Sheet (Hindi, as the office's)

HI_AGENCY = {"CENTRAL": "केन्द्रीय", "STATE": "राज्य", "COMBINED": "सम्मिलित"}


def hindi_names(rep: Report) -> dict:
    ml = master_list(rep.state, rep.year)
    s, _, c = rep.sel.parts[0]
    r = ml[(ml["SEASONCODE"] == s) & (ml["CROPCODE"] == c)]
    get = lambda col, fallback: (str(r[col].iloc[0]).strip() if len(r) and col in r and str(r[col].iloc[0]).strip()  # noqa: E731
                                 else fallback)
    return {"state": get("HSTATENAME", rep.state), "season": get("HSEASONNAME", rep.nm["season"]),
            "crop": get("HCROPNAME", rep.nm["crop"])}


def confidential_row(rep: Report) -> dict:
    """The row of the agency (Central / State / Combined): columns (1) – (9) of the office's sheet."""
    res, info = rep.now.result, rep.info
    tt = {t["Test"]: t for t in est.t_test(res, info)}
    star = lambda name: "*" if str(tt[name]["Result"]).startswith("Significant") else ""   # noqa: E731
    y = res.yield_kg_ha
    pre_y, pre_v = _num(info["PRE YIELD (C)"]), _num(info["PRE VARIANCE (C)"])
    ces_y, ces_se = _num(info["CES YIELD"]), _num(info["CES %SE"])
    planned, analysed = rep.now.counts.get("PLANNED", 0), res.analysed
    return {
        "agency": HI_AGENCY.get(rep.sel.sample_label, rep.sel.sample_label),
        "now": f"{y:g} ({res.pct_se})",
        "prev": f"{pre_y:g} ({round(math.sqrt(pre_v) * 100 / pre_y, 1)})" if pre_y and pre_v is not None else "",
        "ces": f"{ces_y:g} ({ces_se:g})" if ces_y is not None and ces_se is not None else "",
        "diff_prev": f"{round((y - pre_y) * 100 / pre_y, 1)}{star('Current vs previous year')}" if pre_y else "",
        "diff_ces": f"{round((y - ces_y) * 100 / ces_y, 1)}{star('Current vs CES')}" if ces_y else "",
        "planned": planned, "analysed": analysed,
        "response": round(analysed * 100 / planned) if planned else "",
    }


# ------------------------------------------------------------------ where the workbook goes

def report_folder(rep: Report, day: datetime | None = None) -> Path:
    """<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/ under 02_artifacts/06_estimatereport/<STATE>/<YEAR>/."""
    return (ART / rep.state / rep.year / rep.sel.sample_label.title() / est._safe(rep.nm["crop"])
            / f"{(day or datetime.now()):%d.%m.%Y}")
