"""Step 00: master lists, checked like KrishiSoft (lenient mode), kept STATE-WISE and YEAR-WISE like the app.

Every Excel file in 01_raw_data/00_masterlist is checked on its own (src/utils/masterlist_checks.py):
  - small things are cleaned and listed (spaces, extra / EXPTID columns, several sheets, exact repeats)
  - a file with real errors is NOT used; its error report goes to its state / year folder.
Files of the same state + year that pass are joined SEASON BY SEASON: for each season the newest file that has
that season gives all of its experiments (a file replaces only the seasons it contains). "Newest" = imported last
(the app sets a copied file's date to the import time).

Where things go (folders next to 01_raw_data, as in the KrishiSoft app):
  00_database/<STATE>/<YEAR>/          HIDDEN - the stored master list, not for people to browse
      master_list.csv, info.json      (files used, when stored, experiments)
  05_backup/<STATE>/<YEAR>/<date-time>/  the stored list as it was, copied just before it is replaced (last 20 kept)
  02_artifacts/00_masterlist/<STATE>/<YEAR>/      everything of one state + year, nothing outside it:
      ingested_ML.csv                 the stored list with UID / YR (read by module 2, Control Register)
      ML_check_report_summary.csv / _files.csv / _cleaned.csv   the last run for this state + year
      MasterList_Summary_<YEAR>.csv / _files.csv / _crop_wise.csv / _district_wise.csv
      errors/<date-time>_<file>_ERRORS/        rejected files: Read_me, Rules, Problem_count, Errors,
                                               Marked_data, Cleaned (.csv; kept from every run)
  Everything is CSV (no Excel limits).
  02_artifacts/00_masterlist/UNKNOWN-STATE/UNKNOWN-YEAR/   files whose state or year could not be read
A stored list is only replaced by a file that passes the checks and differs from it: a rejected file never
removes a good list, and a list whose file was taken out of 01_raw_data/00_masterlist stays stored.
Output columns: UID, the 26 master list columns, EXPTID, YR, SOURCE_FILE (UID / YR used by module 2, Control Register).
"""
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.logger import logging
from src.utils import masterlist_checks

UNKNOWN_STATE, UNKNOWN_YEAR = "UNKNOWN-STATE", "UNKNOWN-YEAR"
DATA_FILE, INFO_FILE = "master_list.csv", "info.json"
OUT_FILE, REPORT_STEM = "ingested_ML.csv", "ML_check_report"   # in 02_artifacts/00_masterlist/<STATE>/<YEAR>/
KEEP_BACKUPS = 20
SAME_COLUMNS = masterlist_checks.COLUMN_NAMES + [masterlist_checks.KEY]      # compared to decide "changed or not"


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", str(name)).strip()


def _hide(path: Path) -> None:
    """Windows 'hidden' attribute, so the database folder is not shown in Explorer by default."""
    if sys.platform == "win32":
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != -1 and not attrs & 0x2:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs | 0x2)


@dataclass
class MasterListParams:
    input_path: Path
    output_path: Path
    report_path: Path | None = None
    database_path: Path = Path("00_database")
    backup_path: Path = Path("05_backup")


@dataclass
class FileOutcome:
    file: str
    state: str = ""
    year: str = ""
    sheets: str = ""
    rows: int = 0
    fixes: int = 0
    errors: int = 0
    result: str = ""
    error_report: str = ""
    fix_list: list = field(default_factory=list)


class MasterList:
    def __init__(self, params: MasterListParams):
        self.params = params
        self.outcomes: list[FileOutcome] = []
        self.stored: list[dict] = []                        # what happened to each state + year this run
        self.base = self.params.output_path.parent          # 02_artifacts/00_masterlist

    # ------------------------------------------------------------ folders

    @staticmethod
    def _sy(state: str, year: str) -> tuple[str, str]:
        return (_safe(str(state).upper()) or UNKNOWN_STATE), (_safe(year) or UNKNOWN_YEAR)

    def report_dir(self, state: str, year: str) -> Path:
        return self.base.joinpath(*self._sy(state, year))

    def db_dir(self, state: str, year: str) -> Path:
        root = self.params.database_path
        root.mkdir(parents=True, exist_ok=True)
        _hide(root.parent if root.parent.name else root)      # the whole database/ folder
        return root.joinpath(*self._sy(state, year))

    def backup_dir(self, state: str, year: str) -> Path:
        return self.params.backup_path.joinpath(*self._sy(state, year))

    def _discover_files(self) -> list[Path]:
        """Every Excel file in the master list folder and its sub-folders (<STATE>/<YEAR>/ when brought in by the app)."""
        root = Path(self.params.input_path)
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm")
                 and not p.name.startswith("~$")]
        files.sort(key=lambda p: p.stat().st_mtime)          # oldest first: newer files win
        logging.info(f"Discovered {len(files)} Excel files in {root} (with sub-folders)")
        return files

    def _label(self, path: Path) -> str:
        return path.relative_to(self.params.input_path).as_posix()

    # ------------------------------------------------------------ the run

    def ingest_ML(self) -> pd.DataFrame:
        logging.info("Starting ML data ingestion (KrishiSoft checks, lenient, state / year wise)")
        frames = []
        for order, path in enumerate(self._discover_files()):          # oldest first
            res = masterlist_checks.check_file(path)
            out = FileOutcome(self._label(path), res.state.upper(), res.year, ", ".join(res.sheets), len(res.data),
                              len(res.fixes), len(res.issues), fix_list=res.fixes)
            if res.ok:
                df = masterlist_checks.with_exptid(res.data)
                df["SOURCE_FILE"] = self._label(path)
                df["_ORDER"] = order
                frames.append(df)
                out.result = "Used"
                logging.info(f"{self._label(path)}: OK - {res.state} {res.year}, {len(df)} experiments, "
                             f"{len(res.fixes)} item(s) cleaned")
            else:
                report = masterlist_checks.write_error_report(res, self.report_dir(res.state, res.year) / "errors")
                out.result = "REJECTED"
                out.error_report = str(report)
                logging.warning(f"{self._label(path)}: REJECTED - {len(res.issues)} problem(s); report {report}")
            self.outcomes.append(out)

        if frames:
            new = pd.concat(frames, ignore_index=True)
            new["_STATE"] = new["STATENAME"].str.upper()
            # a file replaces only the SEASONS it contains: for each state + year + season the newest file that has
            # that season gives all its experiments (a Kharif list and a later Rabi list both stay; a corrected
            # full list replaces every season)
            newest = new.groupby(["_STATE", "YEAR", "SEASONCODE"])["_ORDER"].transform("max")
            before = len(new)
            new = new[new["_ORDER"] == newest]
            for (st, yr, se), g in new.groupby(["_STATE", "YEAR", "SEASONCODE"]):
                logging.info(f"{st} {yr} season {se}: {len(g)} experiments from {g['SOURCE_FILE'].iloc[0]}")
            if len(new) < before:
                logging.info(f"{before - len(new)} row(s) of older files replaced by a newer file of the same season")
            new = new.drop(columns=["_ORDER", "_STATE"]).reset_index(drop=True)
        # a state + year with a rejected file is left exactly as stored: the files that passed may be only part
        # of it (e.g. a Kharif-only list next to the rejected full list) and must not replace the whole list
        rejected = {(o.state, o.year) for o in self.outcomes if o.result == "REJECTED"}
        if frames:
            for (state, year), g in new.groupby([new["STATENAME"].str.upper(), new["YEAR"]]):
                if (state, year) not in rejected:
                    self._store(state, year, g.reset_index(drop=True))
        else:
            logging.warning("No master list passed the checks in this run")
        for state, year in sorted(rejected):
            kept = (self.db_dir(state, year) / DATA_FILE).exists()
            self.stored.append({"State": state or UNKNOWN_STATE, "Year": year or UNKNOWN_YEAR,
                                "Action": "Kept the stored list (a file of this state + year was rejected)" if kept
                                else "Nothing stored (a file of this state + year was rejected)",
                                "Experiments": "", "Backup": ""})
            logging.warning(f"{state} {year}: not changed - a file of this state + year was rejected")

        df = self._load_all()
        self._write_summaries(df)
        self._write_report(df)
        logging.info(f"Completed ML data ingestion (stored state + years: {df.groupby(['STATENAME', 'YEAR']).ngroups if not df.empty else 0}, "
                     f"experiments: {len(df)})")
        return df

    # ------------------------------------------------------------ database + backup

    def _store(self, state: str, year: str, g: pd.DataFrame) -> None:
        """Save one state + year in the database; the old list is copied to backup first if it changes."""
        folder = self.db_dir(state, year)
        data = folder / DATA_FILE
        files = sorted(g["SOURCE_FILE"].unique())
        backup = ""
        if data.exists():
            old = pd.read_csv(data, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            same = (len(old) == len(g) and set(map(tuple, old.reindex(columns=SAME_COLUMNS).fillna("").values))
                    == set(map(tuple, g.reindex(columns=SAME_COLUMNS).fillna("").values)))
            if same:
                self.stored.append({"State": state, "Year": year, "Action": "Unchanged", "Experiments": len(g),
                                    "Backup": ""})
                logging.info(f"{state} {year}: unchanged ({len(g)} experiments)")
                return
            target = self.backup_dir(state, year) / datetime.now().strftime("%Y-%m-%d_%H%M%S")
            target.mkdir(parents=True, exist_ok=True)
            for f in folder.iterdir():
                if f.is_file():
                    shutil.copy2(f, target / f.name)
            backup = str(target)
            for extra in sorted(p for p in target.parent.iterdir() if p.is_dir())[:-KEEP_BACKUPS]:
                shutil.rmtree(extra)
            action = "Replaced (old list in backup)"
        else:
            action = "New"
        folder.mkdir(parents=True, exist_ok=True)
        g = self._add_uid_column(self._add_yr_column(g.copy()))
        tmp = data.with_suffix(".tmp")
        g.to_csv(tmp, index=False, encoding="utf-8-sig")
        tmp.replace(data)                                    # never leave a half-written list
        (folder / INFO_FILE).write_text(json.dumps(
            {"state": state, "year": year, "state_code": str(g["STATE"].iloc[0]), "files": files,
             "stored_at": f"{datetime.now():%d-%m-%Y %H:%M}", "experiments": len(g)}, indent=2), encoding="utf-8")
        self.stored.append({"State": state, "Year": year, "Action": action, "Experiments": len(g), "Backup": backup})
        logging.info(f"{state} {year}: {action.lower()} - {len(g)} experiments -> {data}"
                     + (f"; backup {backup}" if backup else ""))

    def _load_all(self) -> pd.DataFrame:
        """Every stored state + year (database/*/*/master_list.csv) together."""
        root = self.params.database_path
        parts = [pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
                 for f in sorted(root.glob(f"*/*/{DATA_FILE}"))] if root.exists() else []
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # ------------------------------------------------------------ UID / YR (used by module 2, Control Register)

    def _clean_uid_val(self, v) -> str:
        """Convert value to string without leading zeros."""
        if pd.isna(v):
            return ""
        s = str(v).strip()
        if s.replace(".", "", 1).isdigit():
            num = float(s)
            return str(int(num)) if num == int(num) else str(num)
        return s

    def _add_uid_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """UID = YR_STATE_SEASONCODE_SAMPLE_CROPCODE_DISTRICT_SELORDER_EXPT (leading zeros removed)."""
        parts = ["YR", "STATE", "SEASONCODE", "SAMPLE", "CROPCODE", "DISTRICT", "SELORDER", "EXPT"]
        df["UID"] = df[parts].apply(lambda r: "_".join(self._clean_uid_val(v) for v in r), axis=1)
        return df[["UID"] + [c for c in df.columns if c != "UID"]]

    def _add_yr_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """YR = the FIRST year of YEAR (2025-26 -> 2025), the same as RC-7 YR in the .mdb
        (NSSAS2024.mdb = 2024-25 has YR 2024; the 2025-26 ESCH files have YR 2025), so the UIDs of the master list and
        the schedules match. (It used to be the second year, 2026, which matched no RC-7 of the same year.)"""
        def extract_yr(year_val):
            s = str(year_val).strip()
            return s.split("-")[0].strip() if "-" in s else s
        df["YR"] = df["YEAR"].apply(extract_yr)
        return df

    # ------------------------------------------------------------ reports

    def _write_summaries(self, df: pd.DataFrame) -> None:
        """<STATE>/<YEAR>/ingested_ML.csv and MasterList_Summary_<YEAR>_*.csv (summary, files, crop-wise,
        district-wise) for every stored state + year. Outputs of earlier runs are replaced."""
        olds = list(self.base.glob("*/*/MasterList_Summary_*")) + list(self.base.glob(f"*/*/{OUT_FILE}")) + \
            [self.base / OUT_FILE, self.base / "ML_check_report.xlsx"]    # (older runs: Excel, or at the top)
        for old in olds:
            if old.exists():
                old.unlink()
        if df.empty:
            return
        for (state, year), g in df.groupby([df["STATENAME"].str.upper(), df["YEAR"]]):
            folder = self.report_dir(state, year)
            folder.mkdir(parents=True, exist_ok=True)
            g.to_csv(folder / OUT_FILE, index=False, encoding="utf-8-sig")
            crop, dist = masterlist_checks.summary_tables(g)
            info = {}
            info_file = self.db_dir(state, year) / INFO_FILE
            if info_file.exists():
                info = json.loads(info_file.read_text(encoding="utf-8"))
            stem = f"MasterList_Summary_{_safe(year)}"
            masterlist_checks.write_csv(pd.DataFrame([{"State": state, "Year": year, "Experiments": len(g),
                                               "Central": int((g["SAMPLE"] == "1").sum()),
                                               "State sample": int((g["SAMPLE"] == "2").sum()),
                                               "Stored on": info.get("stored_at", "")}]), folder / f"{stem}.csv")
            masterlist_checks.write_csv(g.groupby("SOURCE_FILE").size().rename("Experiments").reset_index()
                                .rename(columns={"SOURCE_FILE": "File"}), folder / f"{stem}_files.csv")
            masterlist_checks.write_csv(crop.drop(columns=["STATENAME", "YEAR"]), folder / f"{stem}_crop_wise.csv")
            masterlist_checks.write_csv(dist.drop(columns=["STATENAME", "YEAR"]), folder / f"{stem}_district_wise.csv")

    def _write_report(self, df: pd.DataFrame) -> None:
        """<STATE>/<YEAR>/ML_check_report_summary.csv, _files.csv, _cleaned.csv for every state + year that had a file
        in this run: its files (used / rejected), what happened to its stored list, and what was cleaned."""
        groups: dict = {}
        for o in self.outcomes:
            groups.setdefault(self._sy(o.state, o.year), []).append(o)
        actions = {self._sy(r["State"], r["Year"]): r for r in self.stored}
        for (st, yr), outs in groups.items():
            folder = self.base / st / yr
            for old in folder.glob(f"{REPORT_STEM}*"):
                old.unlink()
            act = actions.get((st, yr), {})
            stored_now = int(((df["STATENAME"].str.upper() == st) & (df["YEAR"] == yr)).sum()) if not df.empty else 0
            summary = {"State": st, "Year": yr, "Checked on": f"{datetime.now():%d-%m-%Y %H:%M}", "Files": len(outs),
                       "Used": sum(o.result == "Used" for o in outs), "Rejected": sum(o.result != "Used" for o in outs),
                       "Stored list": act.get("Action", ""), "Experiments stored": stored_now,
                       "Backup of the old list": act.get("Backup", "")}
            masterlist_checks.write_csv(pd.DataFrame(list(summary.items()), columns=["Item", "Value"]),
                                folder / f"{REPORT_STEM}_summary.csv")
            masterlist_checks.write_csv(pd.DataFrame([{"File": o.file, "Sheets read": o.sheets, "Rows": o.rows,
                                               "Cleaned items": o.fixes, "Errors": o.errors, "Result": o.result,
                                               "Error report": o.error_report} for o in outs]),
                                folder / f"{REPORT_STEM}_files.csv")
            cleaned = pd.DataFrame([{"File": o.file, "Sheet": i.sheet, "Excel row": i.row or "(file)",
                                     "Column": i.column, "Value": i.value, "What": i.problem}
                                    for o in outs for i in o.fix_list])
            if not cleaned.empty:
                masterlist_checks.write_csv(cleaned, folder / f"{REPORT_STEM}_cleaned.csv")
            logging.info(f"Check report written: {folder / REPORT_STEM}_*.csv")
