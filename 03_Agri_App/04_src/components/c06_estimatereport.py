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
Typed figures: 00_database/06_estimatereport/<STATE>/<YEAR>/report_inputs.csv. Export: one Excel workbook in
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
         + [f"ICS {i}" for i in range(1, YEARS_BACK + 1)] + [f"CES {i}" for i in range(1, YEARS_BACK + 1)]
         + [f"PREV {c}" for c in COUNTS])
INPUT_COLUMNS = ["KEY", *TYPED, "SAVED_ON"]


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


def load_typed(state: str, year: str, sel: est.Selection) -> dict[str, str]:
    f = folder(state, year) / INPUTS_FILE
    if not f.exists():
        return {}
    df = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig").reindex(columns=INPUT_COLUMNS,
                                                                                         fill_value="")
    row = df[df["KEY"] == sel.key]
    return {k: v for k, v in row.iloc[0].items() if k in TYPED and v} if len(row) else {}


def save_typed(state: str, year: str, sel: est.Selection, typed: dict[str, str]) -> None:
    """Replace this selection's row of report_inputs.csv (old copy to 05_backup first)."""
    d = folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    f = d / INPUTS_FILE
    if f.exists():
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
        df = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=INPUT_COLUMNS)
    row = {"KEY": sel.key, **{k: typed.get(k, "") for k in TYPED}, "SAVED_ON": f"{datetime.now():%Y-%m-%d %H:%M:%S}"}
    df = pd.concat([df[df["KEY"] != sel.key], pd.DataFrame([row])], ignore_index=True).reindex(columns=INPUT_COLUMNS)
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)


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


def _yield_se(res: est.Result | None) -> str:
    if res is None:
        return ""
    return f"{res.yield_kg_ha:g} ({res.pct_se})" if not isinstance(res.pct_se, str) else f"{res.yield_kg_ha:g}"


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
    for i in range(1, YEARS_BACK + 1):                 # ICS yields (SE%) of the previous years saved in the app
        y = prev if i == 1 else year_estimate(state, previous_year(year, i), sel)
        if y is not None and y.result is not None:
            auto[f"ICS {i}"] = _yield_se(y.result)
    return Report(state, year, sel, nm, now, prev, auto, load_typed(state, year, sel))


# ------------------------------------------------------------------ Information Accompanying (tables)

def _pct(n, total) -> int | str:
    n, total = _num(n), _num(total)
    return round(n * 100 / total) if n is not None and total else ""


def yield_rate_table(rep: Report) -> pd.DataFrame:
    return pd.DataFrame([{"Year": previous_year(rep.year, i), "ICS yield (SE%)": rep.value(f"ICS {i}"),
                          "CES yield (SE%)": rep.value(f"CES {i}")} for i in range(1, YEARS_BACK + 1)])


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
