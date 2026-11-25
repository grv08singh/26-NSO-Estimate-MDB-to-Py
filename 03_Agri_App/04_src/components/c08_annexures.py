"""8. Annexures — the RC-7 tables and annexures of the office's report (a copy of the old Annexure workbooks:
`RC-7 Tables CYS-1/-2`, `7RC-7 TY-series`, `RC-7 TAnnex`; only what is built from RC-7).

A report = the ticked seasons of the state + year (Bihar: Kharif = Bhadai + Agahani, Rabi = Rabi + Summer; any state:
1 to 5 or more seasons). This year (CY) is set against the previous year (PY).

  This year       RC-7 of the app (corrected): the rows marked final in 7. RC7 for final crops + samples, the
                  current rows for the others. Planned = the master list; CONFAC missing -> ⌊CCF × 10,000⌋ of the
                  area sheet saved in 5. Estimates (what 7. RC7 proposes).
  Previous year   the app's own RC-7 of that year; when the app does not have it, a file loaded on the page
                  (previous_rc7.csv: old 'PY State Details' Excel (sheet RC-7), rc7.dbf, CSV or .mdb / .accdb Sch20RC7). Planned = its master list
                  when the app has one, else the average NEXP (as the old workbooks).

Tables (per season and sample, every crop + 'All crops'), with the old formulas:
  Y-1  planned / checked at harvest (STAGIN 1), post harvest (2) / lost (3) / rejected (REJ 1) / not received
  Y-2  missed (STAGIN 2) and lost (3) by reason (REXML 1, 2, 3, 4, 9)
  Y-3  conducted by: equivalent (CCE 1–3), juniors (4–6), designated person (7–9); trained / untrained / n.a.
  Y-4  villages (DIST + VILL, not lost); no substitution (RSV 0, RCSSN 0); substitution by reason (1, 2, 3, 9)
  Y-5  no error (E0), errors E1–E15 (= 1), any item missing (E16: any E… = 9)
  Y-6  equipment tape / balance / weight / pegs (EQST / EQSB / EQSW / EQSP 0–9), not lost, not rejected
  Y-7  planned, at harvest, % response, yield = mean of CONFAC × QTYP / 10,000 (STAGIN 1), % SE = SD × 100 / mean
  Y-8  HY (STYPE 1) / other (2) varieties × irrigated (IRR 1) / unirrigated (0): number and yield
  Y-9  fertilizer (FERTC) / manure (MANUR): number and yield; N, P, K: number and rate (mean quantity ÷ 10)
  Y-10 irrigated / HY variety / fertilizer: at harvest, post harvest, total checked, total planned
  Y-11 plot yields in classes (kg/ha), irrigated / unirrigated (STAGIN 1, REJ 0); means
  Y-12 seed variety (SVARC 1–9) and irrigation particulars (IRRP 1–9)
  Y-13 yield with / without pesticide (PEST 1)
Annexures (Central / State / Pooled, CY and PY): XVIII supervision, XIX sample check (Y-1), XX response by crop (Y-1),
  XXI substitution (Y-4), XXII departure / ancillary (Y-5), XXIII equipment (Y-6), XXIV delegation (Y-3).
Typed (no RC-7 behind them): XVI training, XVII CES response and yield, XXV ICS vs CES yield – typed.csv.
"""
from __future__ import annotations

import math
import shutil
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.components import c06_estimatereport as er
from src.components import c07_rc7 as rc7m
from src.utils import folders as F
from src.utils import schedules

DB = Path("00_database") / F.ANNEXURES
ART = Path("02_artifacts") / F.ANNEXURES
BACKUP = Path("05_backup") / F.ANNEXURES
PREV_FILE, TYPED_FILE = "previous_rc7.csv", "typed.csv"
RC7_FIELDS = rc7m.RC7_FIELDS
SAMPLES = {"1": "Central", "2": "State"}
AGENCIES = ["Central", "State", "Pooled"]
ALL = "All crops"
OTHERS = "99"
E_ANY = ["E1", "E2", "E9", "E10", "E11", "E12", "E13", "E14", "E4", "E5", "E6", "E8", "E15", "E3", "E7"]
E_ORDER = ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14", "E15"]
EQUIPMENT = [("Tape", "EQST"), ("Balance", "EQSB"), ("Weight", "EQSW"), ("Pegs", "EQSP")]
CLASSES = ([("Less than 1", None, 1), ("1 to 50", 1, 50), ("51 to 100", 50, 100)]
           + [(f"{k * 100 + 1} to {(k + 1) * 100}", k * 100, (k + 1) * 100) for k in range(1, 20)]
           + [("Above 2000", 2000, None)])

code = rc7m.code
num = rc7m.num


# ------------------------------------------------------------------ the RC-7 rows of a year

def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """RC-7 rows -> text codes of every rc7.dbf field + SEASON / SAMPLE / CROP2 (from SESON / ST / CROP unless the
    master list's are there) and the helper columns of the old workbooks (FYIELD, E0, E16, …)."""
    d = df.copy()
    d.columns = [str(c).strip().upper() for c in d.columns]
    for c in RC7_FIELDS:
        d[c] = d[c].map(code) if c in d.columns else ""
    d["SEASON"] = d["SEASONCODE"].map(code) if "SEASONCODE" in d.columns else d["SESON"]
    d["SAMPLE"] = d["SAMPLE"].map(code) if "SAMPLE" in d.columns and d["SAMPLE"].astype(str).str.len().gt(0).all() \
        else d["ST"]
    if "CROPCODE" in d.columns and d["CROPCODE"].astype(str).str.len().ge(2).all():
        d["CROP2"] = d["CROPCODE"].astype(str).str[:2]
    else:
        d["CROP2"] = d["CROP"].map(lambda c: c.zfill(2) if c else "")
    for c in ("SEASON", "SAMPLE"):
        d[c] = d[c].map(lambda v: str(int(v)) if str(v).isdigit() else str(v))
    for c in ("CONFAC", "QTYP", "QTN", "QTP", "QTK"):
        d[c + "_N"] = pd.to_numeric(d[c].map(num), errors="coerce").fillna(0.0)
    d["FYIELD"] = d["CONFAC_N"] * d["QTYP_N"] / 10000
    bad = d[E_ANY].isin(["1", "9"]).any(axis=1)
    d["E0"] = ((d["STAGIN"] != "0") & ~bad).map(int).astype(str)
    d["E16"] = d[E_ANY].eq("9").any(axis=1).map(int).astype(str)
    fm = (d["FERTC"] == "1") | (d["MANUR"] == "1")
    d["NOFERTMAN"], d["FERTORMAN"] = (~fm).map(int).astype(str), fm.map(int).astype(str)
    return d.reset_index(drop=True)


@dataclass
class YearData:
    year: str
    rows: pd.DataFrame                                  # normalise()d
    planned: dict = field(default_factory=dict)         # (season, sample, crop2) -> planned experiments
    source: str = ""
    names: dict = field(default_factory=dict)           # (season, crop2) -> crop name

    def g(self, season: str, sample: str | None = None, crop: str | None = None) -> pd.DataFrame:
        r = self.rows
        m = r["SEASON"] == season
        if sample:
            m &= r["SAMPLE"] == sample
        if crop:
            m &= r["CROP2"] == crop
        return r[m]

    def plan(self, season: str, sample: str, crop: str | None = None) -> float:
        if crop:
            if (season, sample, crop) in self.planned:
                return self.planned[(season, sample, crop)]
            n = self.g(season, sample, crop)["NEXP"].map(num).dropna()
            return float(n.mean()) if len(n) and n.sum() else 0
        crops = {c for (s, smp, c) in self.planned if s == season and smp == sample} | \
            set(self.g(season, sample)["CROP2"])
        return sum(self.plan(season, sample, c) for c in crops)


def _crop_names(ml: pd.DataFrame) -> dict:
    out = {}
    if ml.empty:
        return out
    m = ml.assign(C2=ml["CROPCODE"].astype(str).str[:2],
                  N=ml["CROPNAME"].astype(str).str.split("_").str[0].str.strip())
    for (s, c), g in m.groupby(["SEASONCODE", "C2"]):
        out[(code(s), c)] = g["N"].mode().iloc[0]
    return out


def _planned(ml: pd.DataFrame) -> dict:
    if ml.empty:
        return {}
    m = ml.assign(C2=ml["CROPCODE"].astype(str).str[:2], S=ml["SEASONCODE"].map(code), SMP=ml["SAMPLE"].map(code))
    return {k: int(v) for k, v in m.groupby(["S", "SMP", "C2"]).size().items()}


CONFAC_FILE = "confac.csv"
CONFAC_SOURCES = {"rc7": "RC-7", "typed": "typed here", "est": "5. Estimates", "": "missing"}


def load_confac(state: str, year: str) -> dict[tuple, int]:
    """CONFAC typed on the 8. Annexures page: (season, sample, crop2) -> value."""
    f = prev_folder(state, year) / CONFAC_FILE
    if not f.exists():
        return {}
    df = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return {(r.SEASON, r.SAMPLE, r.CROP2): int(float(r.CONFAC)) for r in df.itertuples() if num(r.CONFAC)}


def save_confac(state: str, year: str, key: tuple, value: int | None) -> Path:
    """Keep (or, with None, drop) the typed CONFAC of one season + sample + crop; old file to 05_backup."""
    d = prev_folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    f = d / CONFAC_FILE
    vals = load_confac(state, year)
    if f.exists():
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
    if value:
        vals[key] = int(value)
    else:
        vals.pop(key, None)
    df = pd.DataFrame([{"SEASON": s, "SAMPLE": smp, "CROP2": c, "CONFAC": v} for (s, smp, c), v in vals.items()],
                      columns=["SEASON", "SAMPLE", "CROP2", "CONFAC"])
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)
    return f


def _fill_confac(d: pd.DataFrame, state: str, year: str, typed: dict | None = None) -> int:
    """CONFAC missing in the RC-7 -> typed on the page, else ⌊CCF × 10,000⌋ of 5. Estimates' area sheet (as 7. RC7
    proposes). CONFAC_SRC says where each value came from (rc7 / typed / est / '' = missing). Returns rows filled
    from 5. Estimates."""
    try:
        ccf = rc7m._ccf(state, year)
    except Exception:                                  # noqa: BLE001 – no area sheet saved: nothing to fill
        ccf = {}
    typed = typed or {}
    d["CONFAC_SRC"] = d["CONFAC_N"].map(lambda v: "rc7" if v > 0 else "")
    n = 0
    for i in d.index[d["CONFAC_N"] <= 0]:
        key = (d.at[i, "SEASON"], d.at[i, "SAMPLE"], d.at[i, "CROP2"])
        if typed.get(key):
            d.at[i, "CONFAC_N"], d.at[i, "CONFAC_SRC"] = typed[key], "typed"
        elif ccf.get(key):
            d.at[i, "CONFAC_N"], d.at[i, "CONFAC_SRC"] = math.floor(ccf[key] * 10000), "est"
            n += 1
    d["FYIELD"] = d["CONFAC_N"] * d["QTYP_N"] / 10000
    return n


def confac_rows(rep: "Report") -> list[dict]:
    """One line per season + crop + sample of this year: harvested schedules, the CONFAC used and where it is from."""
    out, d = [], rep.cy.rows
    for s, sn in rep.seasons:
        for c, name in rep.crops(s):
            for smp, smp_name in SAMPLES.items():
                g = d[(d["SEASON"] == s) & (d["SAMPLE"] == smp) & (d["CROP2"] == c)]
                if g.empty:
                    continue
                vals = g.loc[g["CONFAC_N"] > 0, "CONFAC_N"]
                src = g["CONFAC_SRC"].mode().iloc[0] if "CONFAC_SRC" in g and len(g) else ""
                if len(vals) and len(vals) < len(g):
                    src = src or "rc7"
                value = int(vals.mode().iloc[0]) if len(vals) else None
                out.append({"KEY": (s, smp, c), "Season": sn, "Crop": f"{name} ({int(c)})", "Sample": smp_name,
                            "Harvested": int((g["STAGIN"] == "1").sum()), "Schedules": len(g),
                            "Missing": int((g["CONFAC_N"] <= 0).sum()), "CONFAC": value,
                            "Mixed": vals.nunique() > 1, "From": src})
    return out


def this_year(state: str, year: str, ml: pd.DataFrame, seasons=()) -> tuple[YearData, dict]:
    """(YearData, info): final rows of 7. RC7 for final crops + samples, current rows for the others."""
    rc = schedules.rc7(state, year)
    cur = rc7m.rows(ml, rc, tuple(seasons), ("1", "2")) if len(rc) and len(ml) else pd.DataFrame()
    info = {"final": 0, "keys": 0, "confac": 0}
    if cur.empty:
        return YearData(year, normalise(pd.DataFrame(columns=RC7_FIELDS)), _planned(ml), "the app",
                        _crop_names(ml)), info
    cur = cur.assign(KEY=cur.apply(rc7m.key_of, axis=1))
    fin = rc7m.finals(state, year)
    keys = set(cur["KEY"])
    final_keys = keys & set(fin["KEY"])
    info.update(final=len(final_keys), keys=len(keys))
    if final_keys:
        fr = rc7m._final_rows(state, year)
        fr = fr[fr["KEY"].isin(final_keys)]
        meta = cur[["EXPTID", "SEASONCODE", "SAMPLE", "CROPCODE"]]
        fr = fr.drop(columns=[c for c in meta.columns if c != "EXPTID" and c in fr.columns]).merge(meta, on="EXPTID",
                                                                                                    how="left")
        cur = pd.concat([cur[~cur["KEY"].isin(final_keys)], fr], ignore_index=True)
    d = normalise(cur)
    info["confac"] = _fill_confac(d, state, year, load_confac(state, year))
    return YearData(year, d, _planned(ml), "the app", _crop_names(ml)), info


def prev_folder(state: str, year: str) -> Path:
    return DB / state / year


def previous_year(state: str, year: str) -> YearData | None:
    """The app's own RC-7 of the previous year; when the app does not have it, the file loaded on the page; else
    None."""
    py = er.previous_year(year, 1)
    f = prev_folder(state, year) / PREV_FILE
    ml = er.master_list(state, py)
    rc = schedules.rc7(state, py)
    if len(rc):
        cur = rc7m.rows(ml, rc) if len(ml) else rc
        d = normalise(cur)
        _fill_confac(d, state, py)
        return YearData(py, d, _planned(ml), "the app", _crop_names(ml))
    if f.exists():
        d = normalise(pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig"))
        return YearData(py, d, {}, f"the loaded file ({datetime.fromtimestamp(f.stat().st_mtime):%d.%m.%Y})",
                        _crop_names(ml))
    return None


# ------------------------------------------------------------------ loading the previous year's RC-7 from a file

def _read_dbf(path: Path) -> pd.DataFrame:
    """dBase III (rc7.dbf): header, field descriptors, fixed-width records."""
    raw = path.read_bytes()
    n, hlen, rlen = struct.unpack("<IHH", raw[4:12])
    fields, pos = [], 32
    while raw[pos] != 0x0D:
        name = raw[pos:pos + 11].split(b"\0")[0].decode("ascii", "ignore")
        fields.append((name, raw[pos + 16]))
        pos += 32
    rows = []
    for i in range(n):
        rec = raw[hlen + i * rlen: hlen + (i + 1) * rlen]
        if not rec or rec[:1] == b"*":                  # deleted
            continue
        at, row = 1, {}
        for name, width in fields:
            row[name] = rec[at:at + width].decode("latin-1").strip()
            at += width
        rows.append(row)
    return pd.DataFrame(rows, dtype=str)


def _read_access(path: Path) -> pd.DataFrame:
    import pyodbc
    from src.components.c01_importschedules import ACCESS_DRIVER
    conn = pyodbc.connect(f"DRIVER={ACCESS_DRIVER};DBQ={path};ReadOnly=1", readonly=True)
    try:
        tables = [t.table_name for t in conn.cursor().tables(tableType="TABLE")]
        name = next((t for t in tables if t.lower() in ("sch20rc7", "rc7", "rc-7")), None)
        if name is None:
            raise ValueError(f"No RC-7 table (Sch20RC7) in {path.name}; tables: {', '.join(tables[:12])}")
        return pd.read_sql(f"SELECT * FROM [{name}]", conn).astype(str).replace({"None": "", "nan": ""})
    finally:
        conn.close()


def read_rc7_file(path: str | Path) -> pd.DataFrame:
    """An RC-7 file: .csv, .xlsx / .xls (sheet 'RC-7' / 'RC-7(PY)' or the first with the RC-7 fields), .dbf,
    .mdb / .accdb (table Sch20RC7). Returns the rows with the rc7.dbf fields (text)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    elif ext in (".xlsx", ".xlsm", ".xls"):
        book = pd.read_excel(p, sheet_name=None, dtype=str)
        pick = None
        for name, sh in book.items():
            cols = {str(c).strip().upper() for c in sh.columns}
            if {"ST", "SESON", "CROP", "STAGIN"} <= cols:
                pick = sh if pick is None or name.upper().startswith("RC-7") else pick
        if pick is None:
            raise ValueError(f"No sheet with the RC-7 fields (ST, SESON, CROP, STAGIN …) in {p.name}")
        df = pick.fillna("")
    elif ext == ".dbf":
        df = _read_dbf(p)
    elif ext in (".mdb", ".accdb"):
        df = _read_access(p)
    else:
        raise ValueError(f"Not an RC-7 file: {p.name} (use .csv, .xlsx, .dbf, .mdb or .accdb)")
    df.columns = [str(c).strip().upper() for c in df.columns]
    missing = [c for c in ("ST", "SESON", "CROP", "STAGIN") if c not in df.columns]
    if missing:
        raise ValueError(f"{p.name} has no {', '.join(missing)} column – not an RC-7 file")
    df = df[df["RC"].map(code).isin(["7", ""]) if "RC" in df.columns else df.index == df.index]
    df = df[df["CROP"].map(code) != ""]
    keep = [c for c in ["EXPTID"] + RC7_FIELDS if c in df.columns]
    return df[keep].reset_index(drop=True)


def save_previous(state: str, year: str, df: pd.DataFrame) -> Path:
    d = prev_folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    f = d / PREV_FILE
    if f.exists():
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)
    return f


def remove_previous(state: str, year: str) -> bool:
    f = prev_folder(state, year) / PREV_FILE
    if not f.exists():
        return False
    b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
    b.mkdir(parents=True, exist_ok=True)
    shutil.move(str(f), b / f.name)
    return True


# ------------------------------------------------------------------ the report

@dataclass
class Report:
    state: str
    year: str
    seasons: list                         # [(code, name)]
    cy: YearData
    py: YearData | None
    info: dict = field(default_factory=dict)

    def crops(self, season: str) -> list[tuple[str, str]]:
        """(crop2, name) of the season: planned in the master list or found in either year's RC-7."""
        found = {c for (s, _, c) in self.cy.planned if s == season} | set(self.cy.g(season)["CROP2"])
        if self.py is not None:
            found |= set(self.py.g(season)["CROP2"])
        found.discard("")
        return [(c, self.name(season, c)) for c in sorted(found, key=lambda c: (c == OTHERS, c))]

    def name(self, season: str, crop: str) -> str:
        for yd in (self.cy, self.py):
            if yd is not None and (season, crop) in yd.names:
                return yd.names[(season, crop)].title()
        return "Others" if crop == OTHERS else f"Crop {crop}"

    def season_name(self, season: str) -> str:
        return next((n for c, n in self.seasons if c == season), season)

    def years(self) -> list[YearData]:
        return [self.cy] + ([self.py] if self.py is not None else [])


KHARIF_CODES = ("1", "2", "3")                # Kharif / Bhadai (autumn) / Agahani (winter); the rest: the Rabi report


def report_seasons(ml: pd.DataFrame) -> dict[str, list[tuple[str, str, int]]]:
    """{'Kharif': [(code, name, planned)], 'Rabi': [...]} – the seasons of the year's two reports (one or two each:
    Bihar Kharif = Bhadai + Agahani, Rabi = Rabi + Summer; Tamil Nadu Kharif, Rabi)."""
    out: dict[str, list] = {"Kharif": [], "Rabi": []}
    if ml.empty:
        return out
    g = ml.groupby(["SEASONCODE", "SEASONNAME"]).size().reset_index(name="n")
    g["C"] = g["SEASONCODE"].map(code)
    g = g.sort_values("C", key=lambda c: c.map(lambda x: int(x) if x.isdigit() else 99))
    for r in g.itertuples():
        out["Kharif" if r.C in KHARIF_CODES else "Rabi"].append((r.C, str(r.SEASONNAME).title(), int(r.n)))
    return {k: v for k, v in out.items() if v}


def build(state: str, year: str, ml: pd.DataFrame, seasons: list[str]) -> Report:
    sn = {}
    if len(ml):
        for r in ml[["SEASONCODE", "SEASONNAME"]].drop_duplicates().itertuples():
            sn[code(r.SEASONCODE)] = str(r.SEASONNAME).title()
    seasons = [code(s) for s in seasons]
    cy, info = this_year(state, year, ml, seasons)
    py = previous_year(state, year)
    if py is not None:
        py.rows = py.rows[py.rows["SEASON"].isin(seasons)].reset_index(drop=True)
    return Report(state, year, [(s, sn.get(s, f"Season {s}")) for s in seasons], cy, py, info)


def from_rows(year: str, rows: pd.DataFrame, seasons: list[tuple[str, str]], names: dict | None = None) -> Report:
    """A report from RC-7 rows alone (no master list): planned = average NEXP, as the old workbooks."""
    yd = YearData(year, normalise(rows), {}, "rows", names or {})
    return Report("", year, seasons, yd, None, {})


# ------------------------------------------------------------------ helpers

def _n(g: pd.DataFrame, **eq) -> int:
    m = pd.Series(True, index=g.index)
    for k, v in eq.items():
        if isinstance(v, tuple) and v[0] == "not":
            m &= ~g[k].isin(v[1:])
        else:
            m &= g[k] == str(v)
    return int(m.sum())


def _mean(s: pd.Series) -> float | None:
    return float(s.mean()) if len(s) else None


def xround(v: float, nd: int = 1) -> float:
    """Excel's ROUND / FIXED: halves away from zero (6.25 -> 6.3; Python's round gives 6.2)."""
    from decimal import ROUND_HALF_UP, Decimal
    return float(Decimal(repr(v)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


def pct(n, total, nd: int = 1) -> float | None:
    return xround(n * 100 / total, nd) if total else None


def fix100(values: list, total: float = 100) -> list:
    """Percentages rounded to one decimal, the largest put right so they add up to total (old workbooks)."""
    vals = [0.0 if v is None else xround(v, 1) for v in values]
    s = round(sum(vals), 1)
    if vals and s and s != total and max(vals) > 0:
        i = vals.index(max(vals))
        vals[i] = round(vals[i] + total - s, 1)
    return vals


def np_(n, p) -> str:
    """'n (p)' as in the old annexures."""
    return f"{n} ({p:.1f})" if p is not None else f"{n}"


def _rows(records: list[dict], cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(records).reindex(columns=["_kind", *cols]).fillna("")


def _crop_rows(rep: Report, yd: YearData, season: str, sample: str, fn, cols: list[str], total=True,
               skip_others=False) -> pd.DataFrame:
    """One row per crop (fn(g, crop) -> dict) + an 'All crops' row (sums, or fn(all rows, None))."""
    recs = []
    for c, name in rep.crops(season):
        if skip_others and c == OTHERS:
            continue
        r = fn(yd.g(season, sample, c), c)
        recs.append({"_kind": "", "Crop": f"{name} ({int(c)})", **r})
    if total and recs:
        t = fn(yd.g(season, sample), None)
        recs.append({"_kind": "total", "Crop": ALL, **t})
    return _rows(recs, ["Crop", *cols])


# ------------------------------------------------------------------ Y-tables (one season, one sample)

def y1(rep, yd, s, smp):
    cols = ["Planned", "Checked at harvest", "Checked at post harvest", "Lost", "Rejected for analysis",
            "Schedules not received"]

    def f(g, c):
        p = yd.plan(s, smp, c) if c else yd.plan(s, smp)
        h, ph, lo, rj = _n(g, STAGIN=1), _n(g, STAGIN=2), _n(g, STAGIN=3), _n(g, REJ=1)
        return dict(zip(cols, [_int(p), h, ph, lo, rj, _int(p - (h + ph + lo + rj))]))
    return _crop_rows(rep, yd, s, smp, f, cols)


def _int(v):
    return int(round(v)) if isinstance(v, float) and float(v).is_integer() else (round(v, 2) if isinstance(v, float)
                                                                                    else v)


REASONS = ["1", "2", "3", "4", "9"]


def y2(rep, yd, s, smp):
    cols = (["Planned", "Checked at harvest"] + [f"Missed: reason {r}" for r in REASONS] + ["Missed: total"]
            + [f"Lost: reason {r}" for r in REASONS] + ["Lost: total", "Missed and lost"])

    def f(g, c):
        p = yd.plan(s, smp, c) if c else yd.plan(s, smp)
        mi = [_n(g, STAGIN=2, REXML=r) for r in REASONS]
        lo = [_n(g, STAGIN=3, REXML=r) for r in REASONS]
        return dict(zip(cols, [_int(p), _n(g, STAGIN=1), *mi, sum(mi), *lo, sum(lo), sum(mi) + sum(lo)]))
    return _crop_rows(rep, yd, s, smp, f, cols)


Y3_GROUPS = [("Delegated to equivalent / senior person", "123"), ("Delegated to juniors", "456"),
             ("Designated person (no change in primary worker)", "789")]
Y3_KINDS = ["trained", "untrained", "training n.a."]


def y3(rep, yd, s, smp):
    cols = ["Checked (harvest + post harvest)"]
    for gname, _ in Y3_GROUPS:
        cols += [f"{gname}: {k}" for k in Y3_KINDS] + [f"{gname}: total"]

    def f(g, c):
        vals = [_n(g, STAGIN=1) + _n(g, STAGIN=2)]
        for _, codes in Y3_GROUPS:
            n = [_n(g, CCE=k) for k in codes]
            vals += n + [sum(n)]
        return dict(zip(cols, vals))
    return _crop_rows(rep, yd, s, smp, f, cols)


SUBST = ["1", "2", "3", "9"]


def y4(rep, yd, s, smp):
    cols = (["Villages", "Checked at harvest", "Checked at post harvest", "No substitution: villages",
             "No substitution: survey nos."] + [f"Village substituted: reason {r}" for r in SUBST]
            + ["Village substituted: subtotal"] + [f"Survey no. substituted: reason {r}" for r in SUBST]
            + ["Survey no. substituted: subtotal"])

    def f(g, c):
        live = g[g["STAGIN"] != "3"]
        ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
        vill = sum(len(x[["DIST", "VILL"]].drop_duplicates()) for _, x in live.groupby("CROP2")) if c is None else \
            len(live[["DIST", "VILL"]].drop_duplicates())
        v = [_n(ok, RSV=r) for r in SUBST]
        sv = [_n(ok, RCSSN=r) for r in SUBST]
        no_v = _n(ok[ok["STAGIN"] != "0"], RSV=0)
        no_s = _n(ok[ok["STAGIN"] != "0"], RCSSN=0)
        return dict(zip(cols, [vill, _n(g, STAGIN=1), _n(g, STAGIN=2), no_v, no_s, *v, sum(v), *sv, sum(sv)]))
    return _crop_rows(rep, yd, s, smp, f, cols)


def y5(rep, yd, s, smp):
    cols = ["Checked (harvest + post harvest)", "Without error (E0)"] + E_ORDER + ["E16"]

    def f(g, c):
        ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
        vals = [_n(g, STAGIN=1) + _n(g, STAGIN=2), _n(ok, E0=1)] + [_n(g, **{e: 1}) for e in E_ORDER]
        vals.append(_n(g[g["STAGIN"] != "3"], E16=1))
        return dict(zip(cols, vals))
    return _crop_rows(rep, yd, s, smp, f, cols)


Y6_COLS = ["Supplied: and used", "Supplied: used local one (standard)", "Supplied: used local one (non standard)",
           "Supplied: not used though required", "Supplied: not required", "Supplied: total",
           "Not supplied: used local one (standard)", "Not supplied: used local one (non standard)",
           "Not supplied: not used though required", "Not supplied: not required", "Not supplied: total",
           "Supply not known", "Total"]


def _y6_counts(g: pd.DataFrame, fld: str) -> list[int]:
    ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
    sup = [_n(ok, **{fld: k}) for k in "01234"]
    nos = [_n(ok, **{fld: k}) for k in "5678"]
    na = _n(ok, **{fld: 9})
    return sup + [sum(sup)] + nos + [sum(nos), na, sum(sup) + sum(nos) + na]


def y6(rep, yd, s, smp):
    recs = []
    for c, name in rep.crops(s):
        g = yd.g(s, smp, c)
        for i, (eq, fld) in enumerate(EQUIPMENT):
            recs.append({"_kind": "", "Crop": f"{name} ({int(c)})" if i == 0 else "", "Equipment": eq,
                         **dict(zip(Y6_COLS, _y6_counts(g, fld)))})
    if recs:
        g = yd.g(s, smp)
        for i, (eq, fld) in enumerate(EQUIPMENT):
            recs.append({"_kind": "total", "Crop": ALL if i == 0 else "", "Equipment": eq,
                         **dict(zip(Y6_COLS, _y6_counts(g, fld)))})
    return _rows(recs, ["Crop", "Equipment", *Y6_COLS])


def _yield_se(g: pd.DataFrame) -> tuple[float | None, float | None]:
    y = g.loc[g["STAGIN"] == "1", "FYIELD"]
    m = _mean(y)
    if not m:
        return m, None
    return m, (round(float(y.std(ddof=1)) * 100 / m, 2) if len(y) > 1 else None)


def y7(rep, yd, s, smp):
    cols = ["Planned", "Checked at harvest", "% response", "Estimated yield (kg/ha)", "% SE"]

    def f(g, c):
        p = yd.plan(s, smp, c) if c else yd.plan(s, smp)
        h = _n(g, STAGIN=1)
        y, se = _yield_se(g)
        return dict(zip(cols, [_int(p), h, pct(h, p, 2), _r(y), se if c else None]))
    return _crop_rows(rep, yd, s, smp, f, cols)


def _r(v, nd: int = 2):
    return None if v is None else round(v, nd)


def _ny(g: pd.DataFrame) -> tuple[int, float]:
    return len(g), (_r(_mean(g["FYIELD"])) or 0) if len(g) else 0


def _wavg(pairs) -> float:
    n = sum(p[0] for p in pairs)
    return round(sum(p[0] * p[1] for p in pairs) / n, 2) if n else 0


def y8(rep, yd, s, smp):
    cols = ["Checked at harvest"]
    for v in ("HY varieties", "Other varieties", "HY and other"):
        for i in ("irrigated", "unirrigated", "total"):
            cols += [f"{v}, {i}: number", f"{v}, {i}: yield"]

    def f(g, c):
        h = g[g["STAGIN"] == "1"]
        hy = [_ny(h[(h["STYPE"] == "1") & (h["IRR"] == k)]) for k in "10"]
        ot = [_ny(h[(h["STYPE"] == "2") & (h["IRR"] == k)]) for k in "10"]
        both = [(hy[0][0] + ot[0][0], _wavg([hy[0], ot[0]])), (hy[1][0] + ot[1][0], _wavg([hy[1], ot[1]]))]
        vals = [len(h)]
        for a, b in (hy, ot, both):
            tot = (a[0] + b[0], _wavg([a, b]))
            vals += [a[0], a[1], b[0], b[1], tot[0], tot[1]]
        return dict(zip(cols, vals))
    return _crop_rows(rep, yd, s, smp, f, cols, total=False, skip_others=True)


Y9_COLS = ["Checked at harvest: number", "Checked at harvest: yield", "Fertilizer only: number",
           "Fertilizer only: yield", "N applied: number", "P applied: number", "K applied: number",
           "Fertilizer: number", "Fertilizer: yield", "N rate (kg/ha)", "P rate (kg/ha)", "K rate (kg/ha)",
           "Manure only: number", "Manure only: yield", "Manure: number", "Manure: yield", "No manure: number",
           "No manure: yield", "Fertilizer and manure: number", "Fertilizer and manure: yield",
           "Neither: number", "Neither: yield", "Fertilizer or manure: number", "Fertilizer or manure: yield",
           "No fertilizer: number", "No fertilizer: yield"]


def y9(rep, yd, s, smp):
    def f(g, c):
        h = g[g["STAGIN"] == "1"]

        def rate(col):
            x = h.loc[h[col + "_N"] > 0, col + "_N"]
            return round(float(x.mean()) / 10, 2) if len(x) else 0
        fo = _ny(h[(h["FERTC"] == "1") & (h["MANUR"] == "0")])
        fe = _ny(h[h["FERTC"] == "1"])
        vals = [*_ny(h), *fo, int((h["QTN_N"] > 0).sum()), int((h["QTP_N"] > 0).sum()), int((h["QTK_N"] > 0).sum()),
                *fe, rate("QTN"), rate("QTP"), rate("QTK"),
                *_ny(h[(h["FERTC"] == "0") & (h["MANUR"] == "1")]), *_ny(h[h["MANUR"] == "1"]),
                *_ny(h[h["MANUR"] == "0"]), *_ny(h[(h["FERTC"] == "1") & (h["MANUR"] == "1")]),
                *_ny(h[h["NOFERTMAN"] == "1"]), *_ny(h[h["FERTORMAN"] == "1"]), *_ny(h[h["FERTC"] == "0"])]
        return dict(zip(Y9_COLS, vals))
    return _crop_rows(rep, yd, s, smp, f, Y9_COLS, total=False, skip_others=True)


Y10_COLS = ["Total", "Irrigated", "Unirrigated", "% irrigated", "HY variety", "Local variety", "% HY variety",
            "With fertilizer", "No fertilizer", "% with fertilizer"]


def y10(rep, yd, s, smp):
    recs = []
    for c, name in rep.crops(s):
        if c == OTHERS:
            continue
        g = yd.g(s, smp, c)
        parts = []
        for st in "12":
            x = g[g["STAGIN"] == st]
            parts.append([len(x), _n(x, IRR=1), _n(x, IRR=0), _n(x, STYPE=1), _n(x, STYPE=2), _n(x, FERTC=1)])
        tot = [a + b for a, b in zip(*parts)]
        planned = tot[0] + _n(g, STAGIN=3)
        for i, (item, v) in enumerate((("At harvest", parts[0]), ("Post harvest", parts[1]),
                                       ("Total checked", tot))):
            e, ir, un, hy, lo, fe = v
            recs.append({"_kind": "", "Crop": f"{name} ({int(c)})" if i == 0 else "", "Item": item,
                         **dict(zip(Y10_COLS, [e, ir, un, pct(ir, e, 2) or 0, hy, lo, pct(hy, e, 2) or 0, fe, e - fe,
                                               pct(fe, e, 2) or 0]))})
        ir, hy, fe = tot[1], tot[3], tot[5]
        recs.append({"_kind": "sub", "Crop": "", "Item": "Total planned",
                     **dict(zip(Y10_COLS, [planned, ir, planned - ir, pct(ir, planned, 2) or 0, hy, planned - hy,
                                           pct(hy, planned, 2) or 0, fe, planned - fe, pct(fe, planned, 2) or 0]))})
    return _rows(recs, ["Crop", "Item", *Y10_COLS])


def _in_class(y: pd.Series, lo, hi) -> pd.Series:
    if lo is None:
        return y < hi
    if hi is None:
        return y > lo
    return (y >= lo) & (y <= hi) if lo == 1 else (y > lo) & (y <= hi)


def y11(rep, yd, s, smp):
    """Per crop: a block of the yield classes."""
    recs = []
    for c, name in rep.crops(s):
        g = yd.g(s, smp, c)
        h = g[(g["STAGIN"] == "1") & (g["REJ"] == "0")]
        recs.append({"_kind": "head", "Class (kg/ha)": f"{name} ({int(c)})"})
        tot = [0, 0]
        for label_, lo, hi in CLASSES:
            ir = int(_in_class(h.loc[h["IRR"] == "1", "FYIELD"], lo, hi).sum())
            un = int(_in_class(h.loc[h["IRR"] == "0", "FYIELD"], lo, hi).sum())
            tot[0] += ir
            tot[1] += un
            recs.append({"_kind": "", "Class (kg/ha)": label_, "Irrigated": ir, "% irrigated": pct(ir, ir + un, 2) or 0,
                         "Unirrigated": un, "% unirrigated": pct(un, ir + un, 2) or 0, "Total": ir + un})
        t = tot[0] + tot[1]
        pi = pct(tot[0], t, 2) or 0
        recs.append({"_kind": "total", "Class (kg/ha)": "Total", "Irrigated": tot[0], "% irrigated": pi,
                     "Unirrigated": tot[1], "% unirrigated": round(100 - pi, 2) if t else 0, "Total": t})
        h1 = g[g["STAGIN"] == "1"]
        recs.append({"_kind": "sub", "Class (kg/ha)": "Mean (kg/ha)",
                     "Irrigated": _r(_mean(h1.loc[h1["IRR"] == "1", "FYIELD"])) if tot[0] else 0,
                     "Unirrigated": _r(_mean(h1.loc[h1["IRR"] == "0", "FYIELD"])) if tot[1] else 0,
                     "Total": _r(_mean(h1["FYIELD"])) if t else 0})

        def sd(x, n):                                    # old: IF(count < 2, 0, STDEV(...)) – sample SD
            return _r(float(x.std(ddof=1))) if n >= 2 and len(x) >= 2 else 0
        recs.append({"_kind": "sub", "Class (kg/ha)": "Standard deviation (kg/ha)",
                     "Irrigated": sd(h1.loc[h1["IRR"] == "1", "FYIELD"], tot[0]),
                     "Unirrigated": sd(h1.loc[h1["IRR"] == "0", "FYIELD"], tot[1]),
                     "Total": sd(h1["FYIELD"], t)})
    return _rows(recs, ["Class (kg/ha)", "Irrigated", "% irrigated", "Unirrigated", "% unirrigated", "Total"])


def y12(rep, yd, s, smp):
    cols = (["Checked (harvest + post harvest)"] + [f"Seed variety {k}" for k in "123456789"]
            + [f"Irrigation particulars {k}" for k in "123456789"])

    def f(g, c):
        return dict(zip(cols, [_n(g, STAGIN=1) + _n(g, STAGIN=2)] + [_n(g, SVARC=k) for k in "123456789"]
                        + [_n(g, IRRP=k) for k in "123456789"]))
    return _crop_rows(rep, yd, s, smp, f, cols)


def y13(rep, yd, s, smp):
    cols = ["At harvest: number", "At harvest: yield", "With pesticide: number", "With pesticide: yield",
            "Without pesticide: number", "Without pesticide: yield"]

    def f(g, c):
        h = g[g["STAGIN"] == "1"]
        return dict(zip(cols, [*_ny(h), *_ny(h[h["PEST"] == "1"]), *_ny(h[h["PEST"] != "1"])]))
    return _crop_rows(rep, yd, s, smp, f, cols)


Y_TABLES = {
    "Y-1": ("Crop-wise number of experiments planned, checked, lost, rejected and not received", y1),
    "Y-2": ("Crop-wise number of experiments missed and lost, by reason", y2),
    "Y-3": ("Crop-wise distribution of experiments by who conducted them", y3),
    "Y-4": ("Crop-wise distribution of experiments by substitution of village / survey number", y4),
    "Y-5": ("Crop-wise distribution of experiments by type of error", y5),
    "Y-6": ("Position of supply and use of equipment", y6),
    "Y-7": ("Crop-wise estimates of yield rate", y7),
    "Y-8": ("Estimated yield rates of HY and other varieties, irrigated and unirrigated", y8),
    "Y-9": ("Crop-wise rate of application of fertilizers and manures, and yield", y9),
    "Y-10": ("Comparison of crop-wise distribution of experiments by irrigation, HY variety and fertilizer", y10),
    "Y-11": ("Crop-wise frequency distribution of plot yield", y11),
    "Y-12": ("Distribution of experiments by reporting of ancillary data", y12),
    "Y-13": ("Crop-wise differential yield rate with and without pesticide", y13),
}


def y_table(rep: Report, name: str, season: str, sample: str, yd: YearData | None = None) -> pd.DataFrame:
    return Y_TABLES[name][1](rep, yd or rep.cy, season, sample)


# ------------------------------------------------------------------ annexures (Central / State / Pooled; CY and PY)

def _agency_rows(yd: YearData, season: str, crop: str | None = None):
    """[(agency, sample codes)] for Central, State, Pooled."""
    return [("Central", ["1"]), ("State", ["2"]), ("Pooled", ["1", "2"])]


def _g(yd: YearData, season: str, samples: list[str], crop: str | None = None) -> pd.DataFrame:
    r = yd.g(season, None, crop)
    return r[r["SAMPLE"].isin(samples)]


def _plan(yd: YearData, season: str, samples: list[str], crop: str | None = None) -> float:
    return sum(yd.plan(season, s, crop) for s in samples)


Y1_ITEMS = [("Planned", None), ("Checked at harvest stage", "1"), ("Checked at post harvest stage", "2"),
            ("Lost", "3"), ("Rejected for analysis", "rej"), ("Schedules not received", "nr")]


def _y1_counts(yd, season, samples, crop=None) -> dict:
    g = _g(yd, season, samples, crop)
    p = _plan(yd, season, samples, crop)
    h, ph, lo, rj = _n(g, STAGIN=1), _n(g, STAGIN=2), _n(g, STAGIN=3), _n(g, REJ=1)
    nr = p - (h + ph + lo + rj)
    vals = [h, ph, lo, rj, nr]
    pcts = fix100([pct(v, p, 3) for v in vals]) if p else [None] * 5
    return {"Planned": _int(p), "counts": [_int(v) for v in vals], "pcts": pcts}


def annex19(rep: Report) -> pd.DataFrame:
    cols = []
    for s, sn in rep.seasons:
        cols += [f"{sn}: {a}" for a in AGENCIES]
    recs = []
    for yd in rep.years():
        recs.append({"_kind": "head", "Item": f"Year {yd.year}"})
        cc = {}
        for s, sn in rep.seasons:
            for a, smp in _agency_rows(yd, s):
                cc[f"{sn}: {a}"] = _y1_counts(yd, s, smp)
        recs.append({"_kind": "", "Item": "1. Planned", **{k: v["Planned"] for k, v in cc.items()}})
        for i, (item, _) in enumerate(Y1_ITEMS[1:]):
            recs.append({"_kind": "", "Item": f"{i + 2}. {item}", **{k: v["counts"][i] or "" for k, v in cc.items()}})
            recs.append({"_kind": "pct", "Item": "   percentage",
                         **{k: f"({v['pcts'][i]:.1f})" if v["counts"][i] else "" for k, v in cc.items()}})
    return _rows(recs, ["Item", *cols])


A20_COLS = ["Planned", "At harvest (%)", "Post harvest (%)", "Lost (%)", "Rejected (%)", "Not received (%)"]


def annex20(rep: Report) -> pd.DataFrame:
    cols = [f"{yd.year}: {c}" for yd in rep.years() for c in A20_COLS]
    recs = []
    for s, sn in rep.seasons:
        recs.append({"_kind": "head", "Season / crop / agency": sn})
        for c, name in rep.crops(s):
            recs.append({"_kind": "sub", "Season / crop / agency": name})
            for a, smp in _agency_rows(rep.cy, s):
                row, prow = {"_kind": "", "Season / crop / agency": a}, {"_kind": "pct",
                                                                         "Season / crop / agency": "   (%)"}
                for yd in rep.years():
                    v = _y1_counts(yd, s, smp, c)
                    row[f"{yd.year}: Planned"] = v["Planned"]
                    for i, col in enumerate(A20_COLS[1:]):
                        row[f"{yd.year}: {col}"] = v["counts"][i]
                        prow[f"{yd.year}: {col}"] = f"({v['pcts'][i]:.1f})" if v["Planned"] else ""
                recs += [row, prow]
    return _rows(recs, ["Season / crop / agency", *cols])


def annex21(rep: Report) -> pd.DataFrame:
    cols = [f"Village: reason {r}" for r in SUBST] + [f"Survey no.: reason {r}" for r in SUBST]
    recs = []
    for yd in rep.years():
        for s, sn in rep.seasons:
            recs.append({"_kind": "head", "Season / crop": f"{sn} {yd.year}"})
            for i, (c, name) in enumerate(rep.crops(s), 1):
                g = _g(yd, s, ["1", "2"], c)
                ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
                checked = _n(g, STAGIN=1) + _n(g, STAGIN=2)
                vals = [_n(ok, RSV=r) for r in SUBST] + [_n(ok, RCSSN=r) for r in SUBST]
                recs.append({"_kind": "", "Sl.": i, "Season / crop": name,
                             **{col: np_(v, pct(v, checked)) if checked else 0 for col, v in zip(cols, vals)}})
    return _rows(recs, ["Sl.", "Season / crop", *cols])


A22_ITEMS = [("1.", "Number of experiments checked", "checked"), ("2.", "Experiments without error (E0)", "E0"),
             ("3.", "Departure from instructions in the conduct of experiments, in respect of:", None),
             ("i", "Selection of survey number (E1)", "E1"), ("ii", "Selection of field within survey number (E2)", "E2"),
             ("iii", "Measurement of field (E9)", "E9"), ("iv", "Choosing random number for location of plot (E10)",
                                                         "E10"),
             ("v", "Location of plot (E11)", "E11"), ("vi", "Dimension of plot (E12)", "E12"),
             ("vii", "Weighment of produce (E13)", "E13"),
             ("4.", "Experiments with discrepant reporting of ancillary particulars:", None),
             ("i", "Seed variety (E3)", "E3"), ("ii", "Seed rate (E4)", "E4"), ("iii", "Irrigation particulars (E5)", "E5"),
             ("iv", "Application of fertilizers (E6)", "E6"), ("v", "Application of manures (E7)", "E7"),
             ("vi", "Application of pesticides (E8)", "E8"),
             ("5.", "Experiments where inadequate arrangement for driage was made (E14)", "E14"),
             ("6.", "Experiments with incorrect reporting of constituents in crop mixture (E15)", "E15"),
             ("7.", "Any one of the items is missing (E16)", "E16")]


def _y5_totals(yd, season, samples) -> dict:
    g = _g(yd, season, samples)
    ok = g[(g["STAGIN"] != "3") & (g["REJ"] != "1")]
    out = {"checked": _n(g, STAGIN=1) + _n(g, STAGIN=2), "E0": _n(ok, E0=1),
           "E16": _n(g[g["STAGIN"] != "3"], E16=1)}
    out.update({e: _n(g, **{e: 1}) for e in E_ORDER})
    return out


def annex22(rep: Report) -> pd.DataFrame:
    cols = [f"{yd.year}: {a}" for yd in rep.years() for a in AGENCIES]
    recs = []
    for s, sn in rep.seasons:
        recs.append({"_kind": "head", "Particulars": f"Season: {sn}"})
        tot = {f"{yd.year}: {a}": _y5_totals(yd, s, smp) for yd in rep.years() for a, smp in _agency_rows(yd, s)}
        for no, item, key in A22_ITEMS:
            if key is None:
                recs.append({"_kind": "sub", "No.": no, "Particulars": item})
                continue
            recs.append({"_kind": "", "No.": no, "Particulars": item, **{k: t[key] for k, t in tot.items()}})
            if key != "checked":
                recs.append({"_kind": "pct", "Particulars": "",
                             **{k: f"({pct(t[key], t['checked']):.1f})" if t["checked"] else "" for k, t in tot.items()}})
    return _rows(recs, ["No.", "Particulars", *cols])


def annex23(rep: Report) -> pd.DataFrame:
    cols = [f"Not supplied: {e}" for e, _ in EQUIPMENT] + [f"Not using the supplied: {e}" for e, _ in EQUIPMENT]
    recs = []
    for yd in rep.years():
        for s, sn in rep.seasons:
            recs.append({"_kind": "head", "Season / agency": f"{sn} {yd.year}"})
            for a, smp in _agency_rows(yd, s):
                g = _g(yd, s, smp)
                row = {"_kind": "", "Season / agency": a}
                for i, (e, fld) in enumerate(EQUIPMENT):
                    v = _y6_counts(g, fld)
                    total = v[-1]
                    not_sup, not_use = v[10], v[1] + v[2] + v[3]
                    p_use = sum(pct(x, total) for x in v[1:4]) if total else None     # rounded one by one (old)
                    row[cols[i]] = np_(not_sup, pct(not_sup, total) if total else 0.0)
                    row[cols[4 + i]] = np_(not_use, xround(p_use, 1) if total else 0.0)
                recs.append(row)
    return _rows(recs, ["Season / agency", *cols])


A24_COLS = ["Delegated to equivalent / senior person", "Equivalent: untrained", "Delegated to juniors",
            "Juniors: untrained", "Designated person", "Designated: untrained"]


def _y3_a24(g: pd.DataFrame) -> list[str]:
    checked = _n(g, STAGIN=1) + _n(g, STAGIN=2)
    eq, ju, de = ([_n(g, CCE=k) for k in grp] for grp in ("123", "456", "789"))
    vals = [sum(eq), eq[1], sum(ju), ju[1], sum(de), de[1]]
    if not checked:
        return [str(v) for v in vals]
    totals = fix100([pct(sum(eq), checked, 3), pct(sum(ju), checked, 3), pct(sum(de), checked, 3)])
    p = [totals[0], pct(eq[1], checked), totals[1], pct(ju[1], checked), totals[2], pct(de[1], checked)]
    return [np_(v, q) for v, q in zip(vals, p)]


def annex24(rep: Report) -> pd.DataFrame:
    cols = [f"{yd.year}: {c}" for yd in rep.years() for c in A24_COLS]
    recs = []
    for s, sn in rep.seasons:
        recs.append({"_kind": "head", "Crop / agency": sn})
        for i, (c, name) in enumerate(rep.crops(s), 1):
            recs.append({"_kind": "sub", "Sl.": i, "Crop / agency": name})
            for a, smp in _agency_rows(rep.cy, s):
                row = {"_kind": "", "Crop / agency": a}
                k = 0
                for yd in rep.years():
                    for v in _y3_a24(_g(yd, s, smp, c)):
                        row[cols[k]] = v
                        k += 1
                recs.append(row)
    return _rows(recs, ["Sl.", "Crop / agency", *cols])


def annex18(rep: Report) -> pd.DataFrame:
    """Supervision of experiments: planned, supervised (harvest + post harvest) and at harvest, with %."""
    cols = [f"{yd.year}: {c}" for yd in rep.years() for c in ("Planned", "Supervised, total (%)",
                                                               "At harvest (%)")]
    recs = []
    for s, sn in rep.seasons:
        recs.append({"_kind": "head", "Season / agency": f"Season: {sn}"})
        for a, smp in _agency_rows(rep.cy, s):
            row = {"_kind": "total" if a == "Pooled" else "", "Season / agency": "Total" if a == "Pooled" else a}
            for yd in rep.years():
                g = _g(yd, s, smp)
                p = _plan(yd, s, smp)
                h, ph = _n(g, STAGIN=1), _n(g, STAGIN=2)
                row[f"{yd.year}: Planned"] = _int(p)
                row[f"{yd.year}: Supervised, total (%)"] = np_(h + ph, pct(h + ph, p)) if p else h + ph
                row[f"{yd.year}: At harvest (%)"] = np_(h, pct(h, p)) if p else h
            recs.append(row)
    return _rows(recs, ["Season / agency", *cols])


ANNEXURES = {
    "XVI": ("Training of primary workers", None),
    "XVII": ("Crop-wise response and level of precision of estimates under CES", None),
    "XVIII": ("Supervision of experiments", annex18),
    "XIX": ("Sample check on crop cutting experiments", annex19),
    "XX": ("Crop-wise response in sample check on crop cutting experiments", annex20),
    "XXI": ("Substitution of sampling units (pooled sample)", annex21),
    "XXII": ("Departure from prescribed procedure in experiments and discrepancies in reporting ancillary "
             "information", annex22),
    "XXIII": ("Supply and use of equipment for the conduct of crop cutting experiments", annex23),
    "XXIV": ("ICS scheme: delegation of work and conduct of crop cutting experiments by untrained workers", annex24),
    "XXV": ("Comparison of estimates of average yield of crops under ICS and CES", None),
}
TYPED_ANNEX = ("XVI", "XVII", "XXV")
HINDI = {   # the Hindi titles of the office's annexures ("वर्ष <CY> और <PY> के दौरान …")
    "XVI": "प्राथमिक कर्मियों का प्रशिक्षण",
    "XVII": "सीईएस के अंतर्गत फसलवार प्रत्युत्तर और आकलनों के बारे में शुद्धता का स्तर",
    "XVIII": "सीईएस के अंतर्गत प्रयोगों का पर्यवेक्षण",
    "XIX": "फसल कटाई प्रयोगों की प्रतिदर्श जांच",
    "XX": "फसल कटाई प्रयोगों की प्रतिदर्श जांच में फसलवार प्रत्युत्तर",
    "XXI": "प्रतिदर्श इकाईयों का प्रतिस्थापन (एकीकृत प्रतिदर्श)",
    "XXII": "प्रयोगों की निर्दिष्ट प्रक्रिया से विचलन और सहायक विवरण दर्ज़ करने में विसंगतियां",
    "XXIII": "फसल कटाई प्रयोग हेतु उपकरणों की आपूर्ति एवं प्रयोग",
    "XXIV": "आई.सी.एस. योजना: अप्रशिक्षित कर्मियों को कार्य का प्रत्यायोजन और फसल कटाई प्रयोगों का संचालन",
    "XXV": "आईसीएस और सीईएस के अंतर्गत शामिल फसलों की औसत उपज के आंकलनों की तुलना",
}


def titles(rep: "Report", name: str) -> tuple[str, str]:
    """(Hindi, English) title lines of an annexure."""
    py = er.previous_year(rep.year, 1)
    return (f"वर्ष {rep.year} और {py} के दौरान {HINDI[name]}",
            f"{ANNEXURES[name][0]} during {rep.year} and {py}")


def annexure(rep: Report, name: str) -> pd.DataFrame:
    fn = ANNEXURES[name][1]
    return fn(rep) if fn else typed_table(rep, name)


# ------------------------------------------------------------------ typed annexures (XVI, XVII, XXV)

def typed_layout(rep: Report, name: str) -> tuple[list[str], list[tuple[str, str]], set[str]]:
    """(columns, [(row key, label)], computed columns) of a typed annexure."""
    years = [rep.year, er.previous_year(rep.year, 1)]
    if name == "XVI":
        cols = [f"{y}: {c}" for y in years for c in ("CES training centres organised by SASA",
                                                     "Covered by NSO as training officer", "Attendance")]
        return cols, [("statistical", "Statistical agency")], set()
    if name == "XVII":
        cols = [f"{y}: {c}" for y in years for c in ("Planned", "Analysed", "% response", "Estimated yield (kg/ha)",
                                                     "% SE")]
        rows = []
        for s, sn in rep.seasons:
            rows.append((f"head|{s}", sn))
            rows += [(f"{s}|{c}", name_) for c, name_ in rep.crops(s)]
        return cols, rows, {c for c in cols if c.endswith("% response")}
    cols = [f"{y}: {c}" for y in years for c in ("ICS yield", "ICS % SE", "CES yield", "CES % SE", "Δ %")]
    rows = []
    for s, sn in rep.seasons:
        rows.append((f"head|{s}", sn))
        for c, name_ in rep.crops(s):
            rows.append((f"head2|{s}|{c}", name_))
            rows += [(f"{s}|{c}|{a}", a) for a in AGENCIES]
    return cols, rows, {c for c in cols if c.endswith("Δ %")}


def load_typed(state: str, year: str) -> dict[tuple[str, str, str], str]:
    f = prev_folder(state, year) / TYPED_FILE
    if not f.exists():
        return {}
    df = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return {(r.ANNEX, r.ROW, r.COLUMN): r.VALUE for r in df.itertuples() if r.VALUE != ""}


def save_typed(state: str, year: str, name: str, values: dict[tuple[str, str], str]) -> Path:
    """Replace the typed values of one annexure ({(row key, column): value})."""
    d = prev_folder(state, year)
    d.mkdir(parents=True, exist_ok=True)
    f = d / TYPED_FILE
    old = load_typed(state, year)
    if f.exists():
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / f.name)
    keep = {k: v for k, v in old.items() if k[0] != name}
    keep.update({(name, r, c): v for (r, c), v in values.items() if str(v).strip()})
    df = pd.DataFrame([{"ANNEX": a, "ROW": r, "COLUMN": c, "VALUE": v} for (a, r, c), v in keep.items()],
                      columns=["ANNEX", "ROW", "COLUMN", "VALUE"])
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)
    return f


def computed(name: str, col: str, vals: dict[str, str]) -> str:
    """% response = analysed × 100 / planned; Δ % = (ICS − CES) × 100 / CES – from the typed cells of the row."""
    y = col.split(": ")[0]
    if col.endswith("% response"):
        p, a = num(vals.get(f"{y}: Planned")), num(vals.get(f"{y}: Analysed"))
        return f"{a * 100 / p:.1f}" if p and a is not None else ""
    ics, ces = num(vals.get(f"{y}: ICS yield")), num(vals.get(f"{y}: CES yield"))
    return f"{(ics - ces) * 100 / ces:.1f}" if ics is not None and ces else ""


def typed_table(rep: Report, name: str) -> pd.DataFrame:
    cols, rows, calc = typed_layout(rep, name)
    typed = load_typed(rep.state, rep.year)
    first = {"XVI": "Agency", "XVII": "Season / crop", "XXV": "Season / crop / agency"}[name]
    recs = []
    for key, lab in rows:
        if key.startswith("head"):
            recs.append({"_kind": "head" if key.startswith("head|") else "sub", first: lab})
            continue
        vals = {c: typed.get((name, key, c), "") for c in cols if c not in calc}
        vals.update({c: computed(name, c, vals) for c in calc})
        recs.append({"_kind": "", first: lab, **vals})
    return _rows(recs, [first, *cols])


# ------------------------------------------------------------------ headline numbers (the KPI boxes)

def headline(rep: Report) -> dict:
    out = {}
    for tag, yd in (("cy", rep.cy), ("py", rep.py)):
        if yd is None:
            continue
        p = h = lo = chk = e0 = 0.0
        for s, _ in rep.seasons:
            c = _y1_counts(yd, s, ["1", "2"])
            p += c["Planned"] or 0
            h += c["counts"][0]
            lo += c["counts"][2]
            t = _y5_totals(yd, s, ["1", "2"])
            chk += t["checked"]
            e0 += t["E0"]
        out[tag] = {"planned": p, "harvest": pct(h, p), "lost": pct(lo, p), "e0": pct(e0, chk)}
    return out


def report_folder(state: str, year: str, rep: Report, day: datetime | None = None) -> Path:
    day = day or datetime.now()
    tag = "+".join(n.upper() for _, n in rep.seasons)
    return ART / state / year / tag / f"{day:%d.%m.%Y}"
