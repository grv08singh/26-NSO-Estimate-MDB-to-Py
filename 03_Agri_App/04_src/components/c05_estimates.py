"""5. Estimates — the old AS 2.0 ESTIMATE.accdb (as copied in KrishiSoft_V0.1), state + year wise, plus the
T-test and the Confidential sheet the office adds in its own workbooks.

Old flow and what each step is here:
  query / info setting  season / sample / crop of 1 part, or up to 4 parts for a COMBINED estimate (old
                        'conversion type 2': e.g. 1611 + 1612 -> 1600, or Central + State of one crop)
  estimate query final  every planned experiment (master list) with its RC-7 (corrections of 4. Data Validation
                        applied): STAGIN, REJ, QTYP (= NETWEIGHT, grams per plot), STYPE, IRR, FERTC, MANUR, PEST,
                        CROPCON, AFFECT                                                           -> experiments()
  central harvest       plots used: STAGIN 1 (harvested); rejected plots (REJ 1) are used too, as the old tool
  Query1 / Query4 /     per district: villages (sel. orders 01–30 with 1 or 2 plots), plots n, Σy, Σy²,
  COL11NIJ2 / Query2    col11 = Σ over sel. orders (Σy)²/n_j, nij2 = Σ n_j²                     -> district_base()
  AREA SHEET            area per district, merge-into code ('1' = left out), CF / driage / recovery
  finalquery            per district row (with its merged district added): mi-1, ni-mi, i, ai²/ni, green yield,
                        dry yield, Avy×Area, col12, check                                          -> calculate()
  INTERMEDIATE TABLE    yield = Round(Σ(Avy×Area) / ΣArea); CCF = average of the non-zero CCFs
  variance / %se        Text0 … Text6: between- / within-village mean squares, variance, SE, %SE
  (T-test, information accompanying and the Confidential sheet are kept here for a later module.)
Access rounds half to even (banker's rounding); Python's round() does the same.

Saved inputs (area sheets, factors) are CSV in 00_database/05_estimates/<STATE>/<YEAR>/; the export is ONE Excel
workbook (c05_estimates_report.py, the office printout's six sheets) in
02_artifacts/05_estimates/<STATE>/<YEAR>/<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/.
"""
from __future__ import annotations

import math
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils import folders as F

DB = Path("00_database") / F.ESTIMATES
ART = Path("02_artifacts") / F.ESTIMATES
BACKUP = Path("05_backup") / F.ESTIMATES
INPUTS_FILE, AREAS_FILE = "estimate_inputs.csv", "area_sheets.csv"
NA = "Not Applicable"
MAX_PARTS = 4
MIN_EXPTS = 4                 # districts with fewer expts are shown in red on the area sheet
SAMPLE_NAME = {"1": "CENTRAL", "2": "STATE"}


def _code(s: pd.Series) -> pd.Series:
    """'1' / '1.0' / ' 1' -> '1' (codes as text)."""
    return s.astype("string").fillna("").str.strip().str.replace(r"\.0+$", "", regex=True)


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", str(name)).strip()


# ------------------------------------------------------------------ what is estimated

@dataclass(frozen=True)
class Selection:
    parts: tuple[tuple[str, str, str], ...]          # (season code, sample 1/2, crop code), 1 to 4 parts

    @property
    def combined(self) -> bool:
        return len(self.parts) > 1

    @property
    def season(self) -> str:
        return self.parts[0][0]

    @property
    def crop_label_code(self) -> str:
        """Old 'basic name' query: combined -> first two digits of the (first) crop + '00'."""
        crop = self.parts[0][2]
        return crop[:2] + "00" if self.combined else crop

    @property
    def sample_label(self) -> str:
        return "COMBINED" if self.combined else SAMPLE_NAME.get(self.parts[0][1], self.parts[0][1])

    @property
    def sample_code(self) -> str:
        return "12" if self.combined else self.parts[0][1]

    @property
    def key(self) -> str:
        """Saved-inputs key: the parts, e.g. '3-1-0623' or '4-2-1611+4-2-1612'."""
        return "+".join("-".join(p) for p in self.parts)


def names(ml: pd.DataFrame, sel: Selection) -> dict:
    """Season / crop names for headings and folders."""
    def first(col, season, crop):
        r = ml[(ml["SEASONCODE"] == season) & (ml["CROPCODE"] == crop)]
        return str(r[col].iloc[0]) if len(r) else ""
    s, _, c = sel.parts[0]
    cropname = first("CROPNAME", s, c) or c
    crops = [first("CROPNAME", p[0], p[2]) or p[2] for p in sel.parts]
    return {"season": first("SEASONNAME", s, c) or s, "cropname": cropname,
            "crop": sel.crop_label_code if sel.combined else cropname,
            "parts": " + ".join(f"{n} {SAMPLE_NAME.get(p[1], p[1]).title()}" for n, p in zip(crops, sel.parts))}


# ------------------------------------------------------------------ data

RC7_COLUMNS = {"STAGIN": "INSPSTATE", "REJ": "REJ", "QTYP": "NETWEIGHT", "STYPE": "SEEDTYPE", "IRR": "IFAPPLIED",
               "FERTC": "FERTAPPLIED", "MANUR": "MANRAPPLIED", "PEST": "PESTAPPLIED", "CROPCON": "CROPCOND",
               "AFFECT": "AFF"}


def experiments(ml: pd.DataFrame, rc7: pd.DataFrame, sel: Selection) -> pd.DataFrame:
    """Every planned experiment of the selection with its RC-7 values (old table `estimate`)."""
    keep = pd.Series(False, index=ml.index)
    for season, sample, crop in sel.parts:
        keep |= (ml["SEASONCODE"] == season) & (ml["SAMPLE"] == sample) & (ml["CROPCODE"] == crop)
    ml = ml[keep]
    if rc7 is None or rc7.empty:
        rc7 = pd.DataFrame(columns=["EXPTID", *RC7_COLUMNS])
    r = rc7.drop_duplicates("EXPTID", keep="last").reindex(columns=["EXPTID", "SOURCE", *RC7_COLUMNS])
    r = r.rename(columns=RC7_COLUMNS)
    df = ml.merge(r, on="EXPTID", how="left")
    for c in RC7_COLUMNS.values():
        if c != "NETWEIGHT":
            df[c] = _code(df[c])
    df["NETWEIGHT"] = pd.to_numeric(df["NETWEIGHT"], errors="coerce")
    return df.sort_values(["DISTRICT", "SELORDER", "EXPT"]).reset_index(drop=True)


def harvested(exps: pd.DataFrame) -> pd.DataFrame:
    """Plots used in the estimate: harvested (STAGIN 1), rejected ones included – the old `central harvest`."""
    return exps[exps["INSPSTATE"] == "1"].copy()


def district_base(harv: pd.DataFrame) -> pd.DataFrame:
    """Per district: villages, plots, Σy, Σy², col11, nij2 (old Query1 → Query4 → COL11NIJ2 → Query2).
    Plots are grouped by district + selection order (all parts together, as the old tables)."""
    cols = ["DISTRICT", "DISTRICTNAME", "VILLAGES", "EXPT", "SUM_Y", "SUM_Y2", "COL11", "NIJ2"]
    if harv.empty:
        return pd.DataFrame(columns=cols)
    h = harv.assign(Y=harv["NETWEIGHT"].fillna(0.0))
    h["Y2"] = h["Y"] ** 2
    vil = h.groupby(["DISTRICT", "DISTRICTNAME", "SELORDER"], as_index=False).agg(n=("Y", "size"), sy=("Y", "sum"))
    vil["col11"] = vil["sy"] ** 2 / vil["n"]
    vil["nij2"] = vil["n"] ** 2
    so = pd.to_numeric(vil["SELORDER"], errors="coerce")
    vil["counted"] = vil["n"].isin([1, 2]) & so.between(1, 30)     # old flags o/s1 … o/s30 = -1 or -2
    d = vil.groupby(["DISTRICT", "DISTRICTNAME"], as_index=False).agg(
        VILLAGES=("counted", "sum"), COL11=("col11", "sum"), NIJ2=("nij2", "sum"))
    t = h.groupby(["DISTRICT", "DISTRICTNAME"], as_index=False).agg(EXPT=("Y", "size"), SUM_Y=("Y", "sum"),
                                                                    SUM_Y2=("Y2", "sum"))
    out = t.merge(d, on=["DISTRICT", "DISTRICTNAME"])
    out["VILLAGES"] = out["VILLAGES"].astype(int)
    return out[cols].sort_values("DISTRICT").reset_index(drop=True)


# ------------------------------------------------------------------ inputs (AREA SHEET), saved as CSV

INFO_TYPED = (["CES YIELD", "CES %SE", "CES REFF YEAR", "PRE YIELD (C)", "PRE VARIANCE (C)"]
              + [f"{k}{i}" for i in range(1, 6) for k in ("YEAR ", "ICS YIELD ", "CES YIELD ")])
INPUT_COLUMNS = ["KEY", "CROP", "SAMPLE", "CF", "DRIAGE", "RECOVERY", "PREPARED_BY", *INFO_TYPED, "SAVED_ON"]
AREA_COLUMNS = ["KEY", "DISTRICT", "DISTRICTNAME", "AREA", "MERGE"]


@dataclass
class Inputs:
    cf: float | None = None
    driage: float | None = None
    recovery: float | None = None
    prepared_by: str = ""
    areas: dict[str, float] = field(default_factory=dict)      # district code -> area
    merges: dict[str, str] = field(default_factory=dict)       # district code -> merge-into code or '1'
    info: dict[str, str] = field(default_factory=dict)         # typed fields of the information sheet / T-test
    saved_on: str = ""


def _num(v) -> float | None:
    try:
        f = float(str(v).strip())
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _read(f: Path, cols: list[str]) -> pd.DataFrame:
    if not f.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig").reindex(columns=cols,
                                                                                         fill_value="")


def folder(state: str, year: str) -> Path:
    return DB / state / year


def load_inputs(state: str, year: str, sel: Selection) -> Inputs:
    d = folder(state, year)
    inp = _read(d / INPUTS_FILE, INPUT_COLUMNS)
    row = inp[inp["KEY"] == sel.key]
    areas = _read(d / AREAS_FILE, AREA_COLUMNS)
    areas = areas[areas["KEY"] == sel.key]
    out = Inputs(areas={r.DISTRICT: a for r in areas.itertuples() if (a := _num(r.AREA)) is not None},
                 merges={r.DISTRICT: r.MERGE for r in areas.itertuples() if r.MERGE})
    if len(row):
        r = row.iloc[0]
        out.cf, out.driage, out.recovery = _num(r["CF"]), _num(r["DRIAGE"]), _num(r["RECOVERY"])
        out.prepared_by, out.saved_on = r["PREPARED_BY"], r["SAVED_ON"]
        out.info = {k: r[k] for k in INFO_TYPED if r[k]}
    return out


def _backup(state: str, year: str, files: list[Path]) -> None:
    there = [f for f in files if f.exists()]
    if there:
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        for f in there:
            shutil.copy2(f, b / f.name)


def save_inputs(state: str, year: str, sel: Selection, inputs: Inputs, base: pd.DataFrame, crop: str) -> None:
    """Replace this selection's rows in estimate_inputs.csv and area_sheets.csv (old copies to 05_backup)."""
    d = folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    fi, fa = d / INPUTS_FILE, d / AREAS_FILE
    _backup(state, year, [fi, fa])
    g = lambda v: "" if v is None else f"{v:g}"          # noqa: E731
    inputs.saved_on = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    row = {"KEY": sel.key, "CROP": crop, "SAMPLE": sel.sample_label, "CF": g(inputs.cf), "DRIAGE": g(inputs.driage),
           "RECOVERY": g(inputs.recovery), "PREPARED_BY": inputs.prepared_by,
           **{k: inputs.info.get(k, "") for k in INFO_TYPED}, "SAVED_ON": inputs.saved_on}
    inp = _read(fi, INPUT_COLUMNS)
    inp = pd.concat([inp[inp["KEY"] != sel.key], pd.DataFrame([row])], ignore_index=True)
    names_ = dict(zip(base["DISTRICT"], base["DISTRICTNAME"])) if len(base) else {}
    dists = sorted(set(names_) | set(inputs.areas) | set(inputs.merges))
    rows = [{"KEY": sel.key, "DISTRICT": dd, "DISTRICTNAME": names_.get(dd, ""), "AREA": g(inputs.areas.get(dd)),
             "MERGE": inputs.merges.get(dd, "")} for dd in dists]
    ar = _read(fa, AREA_COLUMNS)
    ar = pd.concat([ar[ar["KEY"] != sel.key], pd.DataFrame(rows, columns=AREA_COLUMNS)], ignore_index=True)
    for df, f in ((inp, fi), (ar, fa)):
        tmp = f.with_suffix(".tmp")
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
        tmp.replace(f)


# ------------------------------------------------------------------ the calculation

@dataclass
class Result:
    districts: pd.DataFrame          # old `final table` (one row per district of the area sheet)
    yield_kg_ha: float
    total_area: float
    avg_ccf: float
    se_steps: dict                   # Text0 … Text6 and the column totals they use
    variance: float | str
    se: float | str
    pct_se: float | str
    analysed: int
    warnings: list[str]


def calculate(base: pd.DataFrame, inputs: Inputs) -> Result:
    """Old finalquery + the variance / %se / INTERMEDIATE TABLE report formulas."""
    warnings = []
    cf, dr, rr = (inputs.cf or 0.0), (inputs.driage or 0.0), (inputs.recovery or 0.0)
    rows = {r.DISTRICT: r for r in base.itertuples(index=False)}
    merge = {}
    for d in rows:
        m = str(inputs.merges.get(d) or "").strip()
        merge[d] = m if m in ("", "1") else m.zfill(2)
    own_cf = {d: (0.0 if merge[d] == "1" else cf) for d in rows}      # old form: merge '1' sets cf = 0
    own_dr = {d: (0.0 if merge[d] == "1" else dr) for d in rows}
    own_rr = {d: (0.0 if merge[d] == "1" else rr) for d in rows}
    area = {d: float(inputs.areas.get(d) or 0.0) for d in rows}

    out = []
    for d, r in rows.items():
        m = merge[d]
        rec = {"DISTRICT": d, "DISTRICTNAME": r.DISTRICTNAME, "MERGE": m,
               "MERGE_NAME": rows[m].DISTRICTNAME if m in rows else ""}
        if m == "1":
            vals = dict(village=0, netweight=0.0, netweight2=0.0, expt=0, area=0.0, cf=0.0, col11=0.0, nij2=0.0)
        else:
            t = rows.get(m) if m and m != d else None
            if m and m != d and t is None:
                warnings.append(f"District {d} {r.DISTRICTNAME}: merge code {m} is not a district of this sheet "
                                "– ignored.")
            if t is not None and merge.get(m) != "1":
                warnings.append(f"District {d} {r.DISTRICTNAME} takes in {m} {t.DISTRICTNAME}, but {m} is not marked "
                                "'1' – its plots are counted twice and its CF added (as the old tool would).")
            vals = dict(
                village=r.VILLAGES + (t.VILLAGES if t is not None else 0),
                netweight=r.SUM_Y + (t.SUM_Y if t is not None else 0.0),
                netweight2=r.SUM_Y2 + (t.SUM_Y2 if t is not None else 0.0),
                expt=r.EXPT + (t.EXPT if t is not None else 0),
                area=area[d] + (area[m] if t is not None else 0.0),
                cf=own_cf[d] + (own_cf[m] if t is not None else 0.0),
                col11=r.COL11 + (t.COL11 if t is not None else 0.0),
                nij2=r.NIJ2 + (t.NIJ2 if t is not None else 0.0))
        ccf = own_dr[d] * own_rr[d] * vals["cf"]
        n, v = vals["expt"], vals["village"]
        mi_1 = 0 if v == 0 else v - 1
        ni_mi = n - v
        i = round((n ** 2 - vals["nij2"]) / (n * mi_1), 2) if n and mi_1 else 0.0
        ai2ni = round(vals["area"] ** 2 / n, 0) if n else 0.0
        green = round(vals["netweight"] / n, 0) if n else 0.0
        dry = round(green * ccf, 0) if n else 0.0
        out.append({**rec, **vals, "ccf": ccf, "mi-1": mi_1, "ni-mi": ni_mi, "i": i, "ai2/ni": ai2ni,
                    "agreenyield": green, "dryyield": dry, "avy*area": (dry * vals["area"]) if n else 0.0,
                    "col12": round(vals["netweight"] ** 2 / n, 0) if n else 0.0, "check": 2 if n > 0 else 0})
        if m != "1" and n and not area[d]:
            warnings.append(f"District {d} {r.DISTRICTNAME}: no area – it adds nothing to the yield.")
    df = pd.DataFrame(out)

    # INTERMEDIATE TABLE
    A = float(df["area"].sum()) if len(df) else 0.0
    yld = round(float(df["avy*area"].sum()) / A, 0) if A else 0.0
    nz = df.loc[df["ccf"] != 0, "ccf"] if len(df) else pd.Series(dtype=float)
    avg_ccf = float(nz.mean()) if len(nz) else 0.0

    # variance report totals
    s = {c: float(df[c].sum()) if len(df) else 0.0 for c in
         ("mi-1", "ni-mi", "col11", "col12", "ai2/ni", "i", "check", "netweight2", "expt", "area")}
    equal = round(s["i"], 2) == round(s["check"], 2)
    text46 = 0.0
    if not equal:
        for r in out:
            if r["expt"] and r["i"]:
                text46 += round(r["ai2/ni"] * r["nij2"] / (r["expt"] * r["i"]), 0)
    text48 = 0.0 if equal else s["netweight2"]
    if len(df):          # per-district values of the variance report's col.11 (Text771) and col.12 (Text781)
        df["rep_col11"] = [0.0 if (equal or not r["expt"] or not r["i"]) else
                           round(r["ai2/ni"] * r["nij2"] / (r["expt"] * r["i"]), 0) for r in out]
        df["rep_col12"] = [0.0 if equal else r["netweight2"] for r in out]
    # %se report
    text0 = round((s["col11"] - s["col12"]) / s["mi-1"], 0) if s["mi-1"] else 0.0
    if text48 == 0 or not s["ni-mi"]:
        text1 = text2 = NA
        text3 = round(text0 * s["ai2/ni"] / (A * A), 0) if A else 0.0
    else:
        text1 = round((text48 - s["col11"]) / s["ni-mi"], 0)
        text2 = text0 - text1
        text3 = round((text1 * s["ai2/ni"] + text2 * text46) / (A * A), 0) if A else 0.0
    text4 = round(text3 * avg_ccf * avg_ccf, 0)
    if text4 < 0:
        warnings.append("The variance came out negative, so SE and %SE cannot be worked out "
                        "(the old report would show #Error).")
        se, pct = NA, NA
    else:
        se = round(math.sqrt(text4), 2)
        pct = round(se * 100 / yld, 1) if yld else NA
    steps = {"col.6 Σ(mi-1)": s["mi-1"], "col.7 Σ(ni-mi)": s["ni-mi"], "col.9 Σ area": A,
             "col.10 Σ(ai²/ni)": s["ai2/ni"], "col.11": text46, "col.12": text48,
             "col.13 Σ col11": s["col11"], "col.14 Σ col12": s["col12"], "CCF (average)": avg_ccf,
             "Sb2 between-village MS (Text0)": text0, "Sw2 within-village MS (Text1)": text1,
             "Sb2 − Sw2 (Text2)": text2, "Variance, green (Text3)": text3, "Variance, dry (Text4)": text4,
             "SE (Text5)": se, "%SE (Text6)": pct}
    return Result(districts=df, yield_kg_ha=yld, total_area=A, avg_ccf=avg_ccf, se_steps=steps, variance=text4,
                  se=se, pct_se=pct, analysed=int(s["expt"]), warnings=warnings)


# ------------------------------------------------------------------ information accompanying

YIELD_CLASSES = [("0-1000", 0, 1000), ("1000-5000", 1000, 5000), ("5000-10000", 5000, 10000),
                 ("10000-15000", 10000, 15000), ("15000-20000", 15000, 20000), ("20000-25000", 20000, 25000),
                 ("ABOVE 25000", 25000, None)]


def information(exps: pd.DataFrame) -> dict[str, int]:
    """Counts for the 'information accompanying' sheet (old CURRENTINFORMATIONACCOMP), from the planned
    experiments and the harvested ones. Three old slips are corrected: NR does not subtract rejected plots
    again, yield classes are not double-subtracted, and 'affected by' counts AFF (not CROPCOND)."""
    harv = harvested(exps)
    st = exps["INSPSTATE"].fillna("")
    out = {"PLANNED": len(exps), "ANALYSED": int((st == "1").sum()), "MISSED": int((st == "2").sum()),
           "LOST": int((st == "3").sum()), "REJECTED": int((exps["REJ"] == "1").sum())}
    out["NR"] = out["PLANNED"] - out["ANALYSED"] - out["MISSED"] - out["LOST"]
    y = harv["NETWEIGHT"]
    for name, lo, hi in YIELD_CLASSES:          # old edges: NETWEIGHT < 1001, < 5001, … , > 25000 (grams)
        hit = y.notna()
        if lo:
            hit &= y > lo
        if hi is not None:
            hit &= y <= hi
        out[name] = int(hit.sum())
    for name, col in (("IRRIGATED", "IFAPPLIED"), ("HY SEED", "SEEDTYPE"), ("FERTILIZER", "FERTAPPLIED"),
                      ("MANURE", "MANRAPPLIED"), ("PESTICIDE", "PESTAPPLIED")):
        out[name] = int((harv[col] == "1").sum())
    for name, code in (("GOOD", "1"), ("NORMAL", "2"), ("BELOW NORMAL", "3"), ("DAMAGED", "4")):
        out[name] = int((harv["CROPCOND"] == code).sum())
    for name, code in (("HEAVY RAIN", "1"), ("FLOOD", "2"), ("DROUGHT", "3"), ("PESTS", "4"), ("OTHERS", "9")):
        out[name] = int((harv["AFF"] == code).sum())
    return out


# ------------------------------------------------------------------ T-test and Confidential sheet (office)

def t_test(res: Result, info: dict[str, str]) -> list[dict]:
    """Current vs previous year and current vs CES: t = |Y1 − Y2| / √(V1 + V2), significant above 1.96.
    Previous: typed yield + variance; CES: typed yield + %SE (variance = (yield × %SE / 100)²)."""
    out = []
    y, v = res.yield_kg_ha, res.variance
    pre_y, pre_v = _num(info.get("PRE YIELD (C)")), _num(info.get("PRE VARIANCE (C)"))
    ces_y, ces_se = _num(info.get("CES YIELD")), _num(info.get("CES %SE"))
    ces_v = (ces_y * ces_se / 100) ** 2 if ces_y is not None and ces_se is not None else None
    for name, y2, v2 in (("Current vs previous year", pre_y, pre_v), ("Current vs CES", ces_y, ces_v)):
        if isinstance(v, str) or y2 is None or v2 is None or (v + v2) <= 0:
            out.append({"Test": name, "Current yield": y, "Current variance": v, "Other yield": y2 if y2 is not
                        None else "", "Other variance": "" if v2 is None else round(v2, 2), "t": NA,
                        "Result": "Data not available"})
            continue
        t = abs(round((y - y2) / math.sqrt(v + v2), 2))
        out.append({"Test": name, "Current yield": y, "Current variance": v, "Other yield": y2,
                    "Other variance": round(v2, 2), "t": t,
                    "Result": f"{'Significant' if t > 1.96 else 'Insignificant'} ({'>' if t > 1.96 else '<'} 1.96)"})
    return out


def confidential(res: Result, info_counts: dict, info: dict[str, str], sel: Selection, year: str) -> dict:
    """One row of the office's Confidential sheet: yield (SE%) this year, previous year, CES (with its year);
    % difference (* = significant by the T-test); planned, analysed, % response."""
    tt = {t["Test"]: t for t in t_test(res, info)}
    y = res.yield_kg_ha
    pre_y, pre_v = _num(info.get("PRE YIELD (C)")), _num(info.get("PRE VARIANCE (C)"))
    ces_y, ces_se = _num(info.get("CES YIELD")), _num(info.get("CES %SE"))
    star = lambda name: "*" if str(tt[name]["Result"]).startswith("Significant") else ""   # noqa: E731
    prev_year = f"{int(year[:4]) - 1}-{year[2:4]}" if year[:4].isdigit() else ""
    planned, analysed = info_counts.get("PLANNED", 0), res.analysed
    return {
        "Agency (sample)": sel.sample_label,
        f"Yield {year} (SE%)": f"{y:g} ({res.pct_se})",
        f"Yield {prev_year} (SE%)": (f"{pre_y:g} ({round(math.sqrt(pre_v) * 100 / pre_y, 1)})"
                                    if pre_y and pre_v is not None else ""),
        "CES yield (SE%)": f"{ces_y:g} ({ces_se:g})" if ces_y is not None and ces_se is not None else "",
        "CES year": info.get("CES REFF YEAR", ""),
        "% difference vs previous year": (f"{round((y - pre_y) * 100 / pre_y, 1)}{star('Current vs previous year')}"
                                          if pre_y else ""),
        "% difference vs CES": f"{round((y - ces_y) * 100 / ces_y, 1)}{star('Current vs CES')}" if ces_y else "",
        "Planned": planned, "Analysed": analysed,
        "% response": round(analysed * 100 / planned) if planned else "",
    }


# ------------------------------------------------------------------ the sheets (screen + Excel), in the office's order
#   Area Sheet -> Intermediate Table -> Variance (columns 1-14) -> (%) S.E. -> Compiled Data -> Estimate BD
# The same tables are shown in the app and written to the workbook (c05_estimates_report.py).

TOTAL_LABEL = "Total"
WEIGHTED_LABEL = "Weighted average yield (kg/ha)"


def area_sheet_table(base: pd.DataFrame, inputs: Inputs, crop_code: str) -> pd.DataFrame:
    names_ = dict(zip(base["DISTRICT"], base["DISTRICTNAME"]))
    rows = []
    for r in base.itertuples(index=False):
        m = str(inputs.merges.get(r.DISTRICT) or "").strip()
        out = m == "1"
        area = inputs.areas.get(r.DISTRICT)
        rows.append({"Crop code": crop_code, "District code": r.DISTRICT, "District name": r.DISTRICTNAME,
                     "Area": "" if area is None else area, "Expts": int(r.EXPT), "Merge district code": m,
                     "Merge district name": "Left out" if out else names_.get(m.zfill(2), "") if m else "",
                     "Conversion factor": 0 if out else inputs.cf, "Driage ratio": 0 if out else inputs.driage,
                     "Recovery ratio": 0 if out else inputs.recovery})
    return pd.DataFrame(rows)


INTERMEDIATE_COLUMNS = ["District", "+", "Merged district", "Expts", "Average yield (g per plot)", "CCF",
                        "Average yield, dry (kg/ha)", "Area", "Avy × Area"]


def intermediate_table(res: Result) -> pd.DataFrame:
    """Per district: expts, average green yield, CCF, average dry yield, area, Avy × Area; total; weighted yield."""
    d = res.districts
    rows = [dict(zip(INTERMEDIATE_COLUMNS, (r["DISTRICTNAME"], "+", r["MERGE_NAME"], r["expt"], r["agreenyield"],
                                            r["ccf"], r["dryyield"], r["area"], r["avy*area"])))
            for r in d.to_dict("records")]
    blank = dict.fromkeys(INTERMEDIATE_COLUMNS, "")
    tot = float(d["avy*area"].sum()) if len(d) else 0.0
    rows.append({**blank, "District": TOTAL_LABEL, "Expts": int(d["expt"].sum()) if len(d) else 0,
                 "Area": res.total_area, "Avy × Area": tot})
    rows.append({**blank, "District": WEIGHTED_LABEL, "Merged district": "Σ(Avy × Area) ÷ Σ Area",
                 "Average yield, dry (kg/ha)": res.yield_kg_ha})
    return pd.DataFrame(rows, columns=INTERMEDIATE_COLUMNS)


VARIANCE = {"DISTRICTNAME": "1. District", "+": "2. +", "MERGE_NAME": "3. Merged district", "expt": "4. ni",
            "nij2": "5. Σnij²", "mi-1": "6. mi − 1", "ni-mi": "7. ni − mi", "i": "8. (ni² − Σnij²) ÷ (ni × (mi − 1))",
            "area": "9. ai", "ai2/ni": "10. ai² ÷ ni", "rep_col11": "11. ai² × Σnij² ÷ (ni × i)",
            "rep_col12": "12. Σyijk² ÷ jk", "col11": "13. Σ(yijk)² ÷ nij", "col12": "14. (Σyik)² ÷ ni"}


def variance_table(res: Result) -> pd.DataFrame:
    d = res.districts.assign(**{"+": "+"}).reindex(columns=list(VARIANCE)).rename(columns=VARIANCE)
    total = dict.fromkeys(d.columns, "")
    total["1. District"] = TOTAL_LABEL
    for k, v in VARIANCE.items():
        if k not in ("DISTRICTNAME", "+", "MERGE_NAME"):
            total[v] = float(res.districts[k].sum()) if len(d) else 0.0
    return pd.concat([d, pd.DataFrame([total])], ignore_index=True)


def se_table(res: Result) -> pd.DataFrame:
    """Calculation of (%) S.E. (old %se report, Text0 … Text6); Col. = a column of the Variance sheet."""
    s = res.se_steps
    return pd.DataFrame([
        {"Item": "Sb²", "Formula": "(Col. 13 − Col. 14) ÷ Col. 6", "Value": s["Sb2 between-village MS (Text0)"]},
        {"Item": "Sw²", "Formula": "(Col. 12 − Col. 13) ÷ Col. 7", "Value": s["Sw2 within-village MS (Text1)"]},
        {"Item": "Sb² − Sw²", "Formula": "Sb² − Sw²", "Value": s["Sb2 − Sw2 (Text2)"]},
        {"Item": "Variance", "Formula": "(Sw² × Col. 10 + (Sb² − Sw²) × Col. 11) ÷ (Col. 9)²",
         "Value": s["Variance, green (Text3)"]},
        {"Item": "Variance (dry)", "Formula": "Variance × CCF²", "Value": s["Variance, dry (Text4)"]},
        {"Item": "SE", "Formula": "√ Variance (dry)", "Value": s["SE (Text5)"]},
        {"Item": "% SE", "Formula": "SE ÷ Yield × 100", "Value": s["%SE (Text6)"]},
    ])


def compiled_table(res: Result, planned: int) -> pd.DataFrame:
    """Compiled data: the results (what was estimated and the factors are in the heading lines)."""
    items = [("Yield (kg/ha)", res.yield_kg_ha), ("Variance", res.variance), ("SE (kg/ha)", res.se),
             ("% SE", res.pct_se), ("Area", res.total_area), ("Planned", planned), ("Analysed", res.analysed)]
    return pd.DataFrame([{"Item": k, "Value": "" if v is None else v} for k, v in items])


BD_COLUMNS = {"SEASONCODE": "Season", "CROPCODE": "Crop code", "CROPNAME": "Crop name", "SAMPLE": "Sample",
              "STATE": "State", "DISTRICT": "District", "DISTRICTNAME": "District name",
              "SELORDER": "Order of selection", "EXPT": "Expt", "INSPSTATE": "Inspection status", "REJ": "Rejected",
              "NETWEIGHT": "Net weight (g)", "SEEDTYPE": "Seed type", "IFAPPLIED": "Irrigation",
              "FERTAPPLIED": "Fertiliser", "MANRAPPLIED": "Manure", "PESTAPPLIED": "Pesticide",
              "CROPCOND": "Crop condition", "AFF": "Affected by"}


def bd_table(exps: pd.DataFrame) -> pd.DataFrame:
    """Estimate BD: every planned experiment of the selection with its RC-7 values."""
    return exps.reindex(columns=list(BD_COLUMNS)).rename(columns=BD_COLUMNS)


def information_table(counts: dict, info: dict) -> pd.DataFrame:
    return pd.DataFrame([{"Item": k, "Value": v} for k, v in {**counts, **{k: info.get(k, "") for k in INFO_TYPED}}.items()])


# ------------------------------------------------------------------ where the workbook goes (c05_estimates_report.py writes it)

def report_folder(state: str, year: str, sel: Selection, nm: dict, day: datetime | None = None) -> Path:
    """<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/ under 02_artifacts/05_estimates/<STATE>/<YEAR>/."""
    return (ART / state / year / sel.sample_label.title() / _safe(nm["crop"])
            / f"{(day or datetime.now()):%d.%m.%Y}")
