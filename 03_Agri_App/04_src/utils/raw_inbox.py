"""Bring files the user picked (from anywhere on the PC) into 01_raw_data — ALWAYS state-wise and year-wise:

  master lists  ->  01_raw_data/00_masterlist/<STATE>/<YEAR>/<file>            (state + year read from the file)
  schedules     ->  01_raw_data/01_importschedules/<STATE>/<YEAR>/MDB/<file>   (.mdb / .accdb / .zip / RC-7 csv)
                    01_raw_data/01_importschedules/<STATE>/<YEAR>/DGCES/<file> (DGCES Excel)
                    <STATE> + <YEAR> = the state + year open in the app (schedules are imported for one state + year;
                    rows of other states / years in a file are left out when it is read)
A file with the same name already there is first moved to 05_backup/<module>/<STATE>/<YEAR>/raw/<date-time>/.
The picked file itself is only copied, never moved or changed.
"""
from __future__ import annotations

from src.utils import folders as F
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

UNSORTED = "UNSORTED"


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", str(name)).strip()


def _year_label(yr: str) -> str:
    """2025 -> 2025-26 (RC-7 YR is the first year)."""
    yr = str(yr).strip().split(".")[0]
    return f"{yr}-{str(int(yr) + 1)[-2:]}" if yr.isdigit() and len(yr) == 4 else ""


def state_names(database_root: Path) -> dict[str, str]:
    """State code -> name: the stored master lists first, then the app's list of states."""
    out = {}
    try:
        from src.app.states import STATES
        out.update({str(c).zfill(2): n.upper() for n, c in STATES})
    except Exception:
        pass
    for f in (database_root / F.MASTER_LIST).glob("*/*/info.json"):
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
            out[str(info.get("state_code", "")).zfill(2)] = str(info.get("state", "")).upper()
        except (OSError, ValueError):
            continue
    return out


def backup_dir(backup_root: Path, module: str, state: str, year: str, stamp: str) -> Path:
    """05_backup/<module>/<STATE>/<YEAR>/raw/<date-time>/ — where a replaced raw file goes."""
    return backup_root / module / (_safe(state) or UNSORTED) / (_safe(year) or "UNKNOWN-YEAR") / "raw" / stamp


# ------------------------------------------------------------ what a file holds

def master_list_place(path: Path) -> tuple[str, str]:
    from src.utils import masterlist_checks
    res = masterlist_checks.read_excel(path)
    if not res.data.empty:
        masterlist_checks._guess_state_year(res)
    return res.state.upper(), res.year


def _mdb_stat_yr(path: Path) -> list[tuple]:
    import pyodbc
    conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};ReadOnly=1", readonly=True)
    try:
        cur = conn.cursor()
        return [tuple(r) for r in cur.execute("SELECT STAT, YR FROM [Sch20RC7]").fetchall()]
    finally:
        conn.close()


def is_dgces(path: Path) -> bool:
    """A DGCES workbook has the supervisor sheet FinalNSOFieldData."""
    if path.suffix.lower() != ".xlsx":
        return False
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            return "FinalNSOFieldData" in wb.sheetnames
        finally:
            wb.close()
    except Exception:
        return False


def contents(path: Path, names: dict) -> Counter:
    """{(STATE, YEAR): rows} of a schedule file (RC-7 rows of an .mdb / .zip; experiments of a DGCES Excel).
    Empty when the file cannot be read here (the import itself then says why)."""
    ext = path.suffix.lower()

    def from_pairs(pairs) -> Counter:
        c = Counter()
        for s, y in pairs:
            if s in (None, ""):
                continue
            code = str(s).strip().split(".")[0].zfill(2)
            c[(names.get(code, f"STATE-{code}"), _year_label(y))] += 1
        return c

    try:
        if ext in (".mdb", ".accdb"):
            return from_pairs(_mdb_stat_yr(path))
        if ext == ".zip":
            rows = []
            with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
                for m in zf.namelist():
                    if Path(m).suffix.lower() in (".mdb", ".accdb"):
                        target = Path(tmp) / Path(m).name
                        target.write_bytes(zf.read(m))
                        rows += _mdb_stat_yr(target)
            return from_pairs(rows)
        if ext in (".xlsx", ".xls", ".csv"):
            import pandas as pd
            if is_dgces(path):                          # DGCES: State / Year columns of the supervisor sheet
                d = pd.read_excel(path, sheet_name="FinalNSOFieldData", dtype=str, usecols=["State", "Year"])
                d = d.dropna(subset=["State"])
                return Counter(zip(d["State"].str.strip().str.upper(), d["Year"].fillna("").str.strip()))
            d = pd.read_csv(path, dtype=str) if ext == ".csv" else pd.read_excel(path, dtype=str)
            if {"STAT", "YR"} <= set(d.columns):
                return from_pairs(zip(d["STAT"], d["YR"]))
    except Exception:
        return Counter()
    return Counter()


def schedule_place(path: Path, names: dict) -> tuple[str, str]:
    """The (STATE, YEAR) most of the file's rows belong to ('', '' if unreadable)."""
    c = contents(path, names)
    return c.most_common(1)[0][0] if c else ("", "")


def describe(c: Counter, skip: tuple | None = None) -> str:
    """'BIHAR 2025-26: 1,630, TAMIL NADU 2025-26: 2' (leaving out `skip`)."""
    return ", ".join(f"{s} {y or '?'}: {n:,}" for (s, y), n in c.most_common() if (s, y) != skip)


# ------------------------------------------------------------ copy in

def bring_in(paths: list[str], raw_dir: Path, backup_root: Path, kind: str, database_root: Path,
             state: str | None = None, year: str | None = None) -> list[dict]:
    """Copy picked files into raw_dir/<STATE>/<YEAR>/ (schedules: …/MDB or …/DGCES/).
    kind 'master_list': state + year read from each file. kind 'schedules': state + year = the ones given (the open
    state + year). Returns one line per file: {file, to, replaced_backup, note}."""
    raw_dir = raw_dir.resolve()
    module = raw_dir.name
    out = []
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for p in paths:
        src = Path(p)
        if kind == "master_list":
            st, yr = master_list_place(src)
            folder = raw_dir / (_safe(st) or UNSORTED) / (_safe(yr) or "UNKNOWN-YEAR")
        else:
            st, yr = (state or "").upper(), year or ""
            folder = raw_dir / (_safe(st) or UNSORTED) / (_safe(yr) or "UNKNOWN-YEAR") / \
                ("DGCES" if is_dgces(src) else "MDB")
        if src.resolve().is_relative_to(raw_dir):          # already inside the raw folder: leave it there
            out.append({"file": src.name, "to": str(src), "replaced_backup": "", "note": "already in the raw folder"})
            continue
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / src.name
        backup = ""
        if target.exists():
            bdir = backup_dir(backup_root, module, st, yr, stamp)
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(bdir / src.name))
            backup = str(bdir / src.name)
        shutil.copy2(src, target)
        os.utime(target, None)          # date = import time, so 'newer file wins' means 'imported later'
        out.append({"file": src.name, "to": str(target), "replaced_backup": backup,
                    "note": "" if st else "state / year not readable"})
    return out
