"""The imported schedules of ONE state + year, for the modules (Control Register, View Schedule, Data Validation, …).

Every module reads schedules through these functions only. Everything is state-wise and year-wise:
  02_artifacts/01_importschedules/<STATE>/<YEAR>/ingested_sch.csv    RC-7 of the .mdb files of that state + year
  02_artifacts/01_importschedules/<STATE>/<YEAR>/mdb/<block>.csv     Schedule 2.0 block tables of the .mdb files
  02_artifacts/01_importschedules/<STATE>/<YEAR>/dgces/DGCES_ID.csv  DGCES experiments (no EXPTID yet)
  00_database/04_datavalidation/<STATE>/<YEAR>/corrections.csv      corrections made in 4. Data Validation
The corrections (one line per changed value: Date, EXPTID, Table, SRL, Field, Old, New) are applied whenever schedules
are read here, so every module sees the corrected value (9.5, not the 7.45 it replaced) and re-importing the same
file never undoes it. When a REVISED file brings a new value for that field, the new value is kept (the correction
only applies while the value is still the one it corrected).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.utils import folders as F
from src.utils.schedule20 import BLOCK_TABLES

ART = Path("02_artifacts") / F.IMPORT_SCHEDULES
CORRECTIONS = Path("00_database") / F.DATA_VALIDATION
CORR_FILE = "corrections.csv"
_CACHE: dict = {}


def _read(path: Path) -> pd.DataFrame:
    """CSV as text, cached until the file changes."""
    try:
        stamp_ = path.stat().st_mtime_ns
    except OSError:
        return pd.DataFrame()
    hit = _CACHE.get(path)
    if hit and hit[0] == stamp_:
        return hit[1]
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, OSError, UnicodeDecodeError):
        df = pd.DataFrame()
    _CACHE[path] = (stamp_, df)
    return df


def _num(s: pd.Series) -> pd.Series:
    """'08' / '8.0' / '8' -> '8' (codes compared as numbers)."""
    return s.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True).str.lstrip("0").replace("", "0")


def folder(state: str, year: str) -> Path:
    """02_artifacts/01_importschedules/<STATE>/<YEAR>/"""
    return ART / state.upper() / year


def stamp(state: str, year: str) -> tuple:
    """Changes whenever this state + year's schedules or corrections change (to know when to rebuild a page)."""
    out = []
    for f in (folder(state, year) / "ingested_sch.csv", folder(state, year) / "mdb" / "Sch20Block1.csv",
              folder(state, year) / "dgces" / "DGCES_ID.csv", CORRECTIONS / state.upper() / year / CORR_FILE):
        try:
            out.append(f.stat().st_mtime_ns)
        except OSError:
            out.append(0)
    return tuple(out)


def corrections(state: str, year: str) -> pd.DataFrame:
    """Every correction of this state + year, oldest first (later ones win)."""
    df = _read(CORRECTIONS / state.upper() / year / CORR_FILE)
    if df.empty or "EXPTID" not in df.columns:
        return pd.DataFrame(columns=["Date", "EXPTID", "Table", "SRL", "Field", "Old", "New"])
    return df


def _same(a, b) -> bool:
    """Same value? numbers compared as numbers (7450 = 7450.0)."""
    a, b = str(a if a is not None else "").strip(), str(b if b is not None else "").strip()
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def _num1(v) -> str:
    """_num for one value."""
    t = re.sub(r"\.0+$", "", str(v).strip()).lstrip("0")
    return t or "0"


def _apply(df: pd.DataFrame, table: str, corr: pd.DataFrame) -> pd.DataFrame:
    """The table with its corrections applied (in order). A correction is used only while the value is still the
    one it corrected (Old): when a revised file brings a new value for that field, the new value is kept.
    Each correction touches only the rows of its Exp-ID (found through an index built once), so thousands of
    corrections take a fraction of a second."""
    mine = corr[corr["Table"] == table] if not corr.empty else corr
    if df.empty or mine.empty:
        return df
    df = df.copy()
    where: dict[str, list[int]] = {}
    for i, e in enumerate(df["EXPTID"].tolist()):
        where.setdefault(e, []).append(i)
    srl = [_num1(v) for v in df["SRL"].tolist()] if "SRL" in df.columns else None
    edited: dict[str, list] = {}                         # field -> its values, edited in place
    for rec in mine.to_dict("records"):
        field = rec["Field"]
        if field not in df.columns:
            continue
        rows = where.get(rec["EXPTID"])
        if not rows:
            continue
        want = _num1(rec["SRL"]) if rec.get("SRL") and srl is not None else None
        vals = edited.get(field)
        if vals is None:
            vals = edited[field] = df[field].tolist()
        old = rec.get("Old", "")
        for i in rows:
            if (want is None or srl[i] == want) and _same(vals[i], old):
                vals[i] = rec["New"]
    for field, vals in edited.items():
        df[field] = vals
    return df


_RC7_DONE: dict = {}                                     # (state, year) -> (stamp, corrected RC-7)


def rc7(state: str, year: str, corrected: bool = True) -> pd.DataFrame:
    """RC-7 of this state + year (one row per experiment; newest file already won), corrections applied."""
    df = _read(folder(state, year) / "ingested_sch.csv")
    if df.empty:
        return pd.DataFrame()
    if not corrected:
        return df
    key, st = (state.upper(), year), stamp(state, year)
    hit = _RC7_DONE.get(key)
    if hit is None or hit[0] != st:                      # corrections applied once per change of the files
        hit = _RC7_DONE[key] = (st, _apply(df, "Sch20RC7", corrections(state, year)))
    return hit[1].copy()


def blocks(state: str, year: str, exptid: str | None = None, corrected: bool = True) -> dict[str, pd.DataFrame]:
    """{block table: rows} of this state + year (all experiments, or one Exp-ID), corrections applied."""
    corr = corrections(state, year) if corrected else pd.DataFrame()
    out = {}
    for t in BLOCK_TABLES:
        df = _read(folder(state, year) / "mdb" / f"{t}.csv")
        if exptid is not None and not df.empty and "EXPTID" in df.columns:
            df = df[df["EXPTID"] == exptid]
        if not df.empty:
            out[t] = _apply(df.reset_index(drop=True), t, corr)
    return out


def blocks_by_exptid(state: str, year: str) -> dict[str, dict[str, pd.DataFrame]]:
    """{block table: {exptid: rows}} – read once for a batch of schedules."""
    return {t: dict(tuple(df.groupby("EXPTID", sort=False))) for t, df in blocks(state, year).items()}


def dgces_ids(state: str, year: str) -> pd.DataFrame:
    """DGCES experiments of this state + year (identity rows; no EXPTID yet)."""
    return _read(folder(state, year) / "dgces" / "DGCES_ID.csv")
