"""Module 1: raw schedules -> RC-7 + all Schedule A.S. 2.0 block tables (block-wise, like the .mdb).

ONE state + year at a time: the files of 01_raw_data/01_importschedules/<STATE>/<YEAR>/ (MDB/ and DGCES/) are read
and only the rows of that state + year are kept (rows of other states / years in a file are left out and named in
the report). Outputs go to 02_artifacts/01_importschedules/<STATE>/<YEAR>/.

Files:
  .mdb / .accdb / .zip (with .mdb inside)  ESCH field files or whole-year NSSAS databases:
        Sch20RC7  -> ingested_sch.csv (as before: 61 RC-7 columns + UID + CROPCODE)
        Sch20Block1 … Sch20Block12 -> mdb/<table>.csv, every value as text, exactly the .mdb columns
  DGCES Excel (sheets FinalNSOFieldData + FinalNSO_PW_FieldData):
        converted into the same block tables + Sch20RC7 -> dgces/<table>.csv; clubbed/ = mdb + DGCES together (components/c01_importschedules_dgces.py,
        RC-7 codes by components/c01_dgces_rc7, taken from KrishiStat). The sample (Central 1 / State 2) is given by
        the user. EXPTID stays blank until the order of selection is known; DGCES_KEY + dgces/DGCES_ID.csv
        identify each experiment. Problems go to report/DGCES issues <file>.csv.
  other .csv / .xlsx                      RC-7 tables (as before)
Every output is rebuilt from all raw files on each run (no appending). The same experiment in several files:
the newer file (date modified) wins — for RC-7 and all its block rows together.
"""
import hashlib
import json
import pickle
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from src.logger import logging
from src.utils.common import load_csv, load_excel
from src.utils.schedule20 import BLOCKS, BLOCK_TABLES, RC7_COLUMNS, RC7_TABLE, rc7_text

# Required columns for detailed experiment data (RC7 format)
REQUIRED_COLUMNS = RC7_COLUMNS
DGCES_SHEETS = ("FinalNSOFieldData", "FinalNSO_PW_FieldData")
CACHE_VERSION = 1                      # raise when the reading / conversion code changes: every file is read again
ACCESS_DRIVER = "{Microsoft Access Driver (*.mdb, *.accdb)}"


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has all required columns, adding missing ones as NaN."""
    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_cols:
        missing_df = pd.DataFrame(np.nan, index=df.index, columns=list(missing_cols))
        df = pd.concat([df, missing_df], axis=1)
        logging.warning(f"Added missing columns with NaN: {missing_cols}")
    return df[REQUIRED_COLUMNS]


def _why(e: Exception) -> str:
    """A reading error in plain words (the full message stays in the log)."""
    msg = str(e)
    low = msg.lower()
    if "cannot open database" in low or "not a database" in low or "unrecognized database format" in low:
        return "Not a readable Access database – the file is damaged or is not an .mdb"
    if "could not find file" in low or "no such file" in low:
        return "File not found"
    if "being used by another process" in low or "permission denied" in low or "exclusively locked" in low:
        return "File is open in another program – close it and choose it again"
    if "data source name not found" in low or "im002" in low:
        return "Microsoft Access driver is not installed on this computer"
    if isinstance(e, zipfile.BadZipFile):
        return "Not a readable .zip file"
    first = re.sub(r"^\(?'?[A-Z0-9]{5}'?,\s*", "", (msg.splitlines() or [type(e).__name__])[0])
    first = re.sub(r"\[[^\]]*\]\s*", "", first).strip(" \"'()")
    return (first or type(e).__name__)[:200]


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return str(v)


@dataclass
class ImportSchedulesParams:
    input_path: Path
    mdb_table: str = RC7_TABLE
    dgces_sample: str | None = None        # "1" Central / "2" State, for DGCES files without a remembered sample
    dgces_samples: dict | None = None      # {DGCES file (path in the raw folder): sample it was imported with}
    dgces_codes: dict | None = None        # config.yaml DGCES_codes (codes still to be decided)
    cache_dir: Path | None = None          # each file's result, so an unchanged file is not read again
    state: str = ""                        # the state + year imported (rows of others are left out)
    state_code: str = ""
    year: str = ""
    names: dict | None = None              # state code -> name (to name the rows left out)


@dataclass
class FileResult:
    file: str
    kind: str
    mtime: float
    rc7: pd.DataFrame = field(default_factory=pd.DataFrame)
    blocks: dict = field(default_factory=dict)
    rows: int = 0
    note: str = ""
    error: str = ""
    kept: int = 0                          # rows / experiments of this state + year
    left: str = ""                         # what was left out (other states / years)


class ImportSchedules:
    def __init__(self, params: ImportSchedulesParams):
        self.params = params
        self.files: list[FileResult] = []
        self.blocks: dict[str, pd.DataFrame] = {}          # mdb block tables (after "newer file wins")
        self.dgces: dict[str, pd.DataFrame] = {}           # DGCES -> block tables, Sch20RC7, DGCES_ID
        self.dgces_issues: list[tuple] = []                # (file, Recorder)
        self._used_keys: set = set()
        self.n_cached = self.n_read = 0
        self.files_report = pd.DataFrame()

    def _discover_files(self) -> list[Path]:
        """Every schedule file in the raw folder and its sub-folders (<STATE>/<YEAR>/ when brought in by the app)."""
        root = Path(self.params.input_path)
        files = [p for p in root.rglob("*") if p.is_file() and not p.name.startswith("~$")
                 and p.suffix.lower() in (".csv", ".mdb", ".accdb", ".xlsx", ".xls", ".zip")]
        files.sort(key=lambda p: p.stat().st_mtime)          # oldest first
        logging.info(f"Discovered {len(files)} schedule files in {root} (with sub-folders)")
        return files

    def _label(self, path: Path) -> str:
        """The file as shown and stored in SOURCE_FILE: its path inside the raw folder (unique)."""
        return path.relative_to(self.params.input_path).as_posix()

    # ------------------------------------------------------------ readers

    def _read_access(self, path: Path) -> tuple[pd.DataFrame, dict]:
        """(Sch20RC7, {block table: DataFrame of text}) of one Access database."""
        import pyodbc
        conn = pyodbc.connect(f"DRIVER={ACCESS_DRIVER};DBQ={path};ReadOnly=1", readonly=True)
        try:
            cur = conn.cursor()
            tables = {t.table_name.lower(): t.table_name for t in cur.tables(tableType="TABLE")}
            name = tables.get(self.params.mdb_table.lower())
            if name is None:
                raise ValueError(f"No {self.params.mdb_table} table in this database")
            rc7 = pd.read_sql(f"SELECT * FROM [{name}]", conn)
            blocks = {}
            for table in BLOCK_TABLES:
                real = tables.get(table.lower())
                if real is None:
                    continue
                cur.execute(f"SELECT * FROM [{real}]")
                cols = [d[0] for d in cur.description]
                df = pd.DataFrame([[_text(v) for v in r] for r in cur.fetchall()], columns=cols)
                if not df.empty and "EXPTID" in df.columns:
                    blocks[table] = df
            return rc7, blocks
        finally:
            conn.close()

    def _read_zip(self, path: Path) -> tuple[pd.DataFrame, dict]:
        rc7s, parts = [], []
        with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
            members = [m for m in zf.namelist() if Path(m).suffix.lower() in (".mdb", ".accdb")]
            if not members:
                raise ValueError("ZIP has no .mdb/.accdb file inside")
            for m in members:
                target = Path(tmp) / Path(m).name          # flatten: never write outside tmp
                target.write_bytes(zf.read(m))
                rc7, blocks = self._read_access(target)
                rc7s.append(rc7)
                parts.append(blocks)
        merged = {}
        for p in parts:
            for t, df in p.items():
                merged.setdefault(t, []).append(df)
        return pd.concat(rc7s, ignore_index=True), {t: pd.concat(d, ignore_index=True) for t, d in merged.items()}

    @staticmethod
    def _is_dgces(path: Path) -> bool:
        if path.suffix.lower() != ".xlsx":
            return False
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            return all(s in wb.sheetnames for s in DGCES_SHEETS)
        finally:
            wb.close()

    # ------------------------------------------------------------ RC-7 shaping (as before)

    @staticmethod
    def _exptid_str(x) -> str:
        if pd.isna(x):
            return ""
        if isinstance(x, float):
            return f"{x:.0f}"
        s = str(x).strip()
        return s[:-2] if s.endswith(".0") else s

    @staticmethod
    def _clean_val(v) -> str:
        """Value as text without leading zeros (for the UID)."""
        if pd.isna(v):
            return ""
        s = str(v).strip()
        if s.replace(".", "", 1).isdigit():
            num = float(s)
            return str(int(num)) if num == int(num) else str(num)
        return s

    def _shape_rc7(self, df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        df = df.dropna(how="all")
        df = _standardize_columns(df)
        df = df.dropna(subset=REQUIRED_COLUMNS, how="all")
        if df.empty:
            return df
        df = df.copy()
        df["EXPTID"] = df["EXPTID"].apply(self._exptid_str)
        df["CROPCODE"] = df["EXPTID"].str[7:11]
        uid_cols = ["YR", "STAT", "SESON", "ST", "CROPCODE", "DIST", "VILL", "EXPNO"]
        df["UID"] = df[uid_cols].apply(lambda r: "_".join(self._clean_val(v) for v in r), axis=1)
        return df[["UID"] + [c for c in df.columns if c != "UID"]]

    # ------------------------------------------------------------ one file (cached)

    def sample_for(self, path: Path) -> str | None:
        """The DGCES sample of this file: the one it was imported with, else the one given now."""
        return (self.params.dgces_samples or {}).get(self._label(path)) or self.params.dgces_sample

    def _cache_key(self, path: Path) -> str:
        """Changes when the file, its place, the DGCES sample / codes or this reader change."""
        st = path.stat()
        parts = [CACHE_VERSION, self._label(path), st.st_size, st.st_mtime_ns, self.params.mdb_table]
        if path.suffix.lower() == ".xlsx":
            parts += [self.sample_for(path), json.dumps(self.params.dgces_codes or {}, sort_keys=True)]
        return hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()

    def _load_file(self, path: Path, order: int = 0) -> FileResult:
        """One file's result: from the cache when the file is unchanged, else read (and cached unless it failed)."""
        cache = self.params.cache_dir
        key = self._cache_key(path) if cache else ""
        self._used_keys.add(key)
        hit = cache / f"{key}.pkl" if cache else None
        if hit is not None and hit.exists():
            try:
                with open(hit, "rb") as fh:
                    c = pickle.load(fh)
                res = FileResult(self._label(path), c["kind"], path.stat().st_mtime + order * 1e-6, c["rc7"],
                                 c["blocks"], c["rows"], c["note"])
                if not res.rc7.empty and "FILE_TIME" in res.rc7.columns:      # "newer file wins" uses this run's order
                    res.rc7 = res.rc7.assign(FILE_TIME=res.mtime)
                res.blocks = {t: (b.assign(FILE_TIME=res.mtime) if "FILE_TIME" in b.columns else b)
                              for t, b in res.blocks.items()}
                if c.get("rec") is not None:
                    self.dgces_issues.append((res.file, c["rec"]))
                self.n_cached += 1
                return res
            except Exception:                        # a damaged cache entry: read the file again
                hit.unlink(missing_ok=True)
        res = self._read_file(path, order)
        self.n_read += 1
        if hit is not None and not res.error and not res.note.startswith("skipped"):
            rec = self.dgces_issues[-1][1] if res.kind == "DGCES" and self.dgces_issues and \
                self.dgces_issues[-1][0] == res.file else None
            try:
                hit.parent.mkdir(parents=True, exist_ok=True)
                with open(hit, "wb") as fh:
                    pickle.dump({"kind": res.kind, "rc7": res.rc7, "blocks": res.blocks, "rows": res.rows,
                                 "note": res.note, "rec": rec}, fh, protocol=pickle.HIGHEST_PROTOCOL)
            except OSError as e:
                logging.warning(f"Could not cache {res.file}: {e}")
        return res

    def _prune_cache(self) -> None:
        """Remove cache entries of files that are gone or changed."""
        cache = self.params.cache_dir
        if cache and cache.exists():
            for f in cache.glob("*.pkl"):
                if f.stem not in self._used_keys:
                    f.unlink(missing_ok=True)

    def _read_file(self, path: Path, order: int = 0) -> FileResult:
        ext = path.suffix.lower()
        # FILE_TIME decides "newer file wins"; the reading order breaks ties (a copied file keeps its date)
        res = FileResult(self._label(path), "", path.stat().st_mtime + order * 1e-6)
        try:
            if ext in (".mdb", ".accdb"):
                res.kind = "mdb"
                raw, res.blocks = self._read_access(path)
                res.rc7 = self._shape_rc7(raw, self._label(path))
            elif ext == ".zip":
                res.kind = "zip (mdb)"
                raw, res.blocks = self._read_zip(path)
                res.rc7 = self._shape_rc7(raw, self._label(path))
            elif self._is_dgces(path):
                res.kind = "DGCES"
                self._convert_dgces(path, res)
                return res
            elif ext == ".csv":
                res.kind = "csv (RC-7)"
                res.rc7 = self._shape_rc7(load_csv(path), self._label(path))
            else:
                res.kind = "excel (RC-7)"
                res.rc7 = self._shape_rc7(load_excel(path), self._label(path))
            # the Exp-ID has no year in it (the same Exp-ID is used again next year): every block row gets the
            # YR of its RC-7 record in the same file (or the file's usual YR), and rows are kept per Exp-ID + YR
            yr_map = dict(zip(res.rc7["EXPTID"], res.rc7["YR"].map(self._clean_val))) if not res.rc7.empty else {}
            usual_yr = pd.Series(list(yr_map.values())).mode().iloc[0] if yr_map else ""
            for t, b in res.blocks.items():
                res.blocks[t] = b.assign(YR=b["EXPTID"].map(yr_map).fillna(usual_yr), SOURCE="MDB",
                                         SOURCE_FILE=self._label(path), FILE_TIME=res.mtime)
            if not res.rc7.empty:
                res.rc7 = res.rc7.assign(SOURCE="MDB" if "mdb" in res.kind else "RC-7 file", SOURCE_FILE=self._label(path),
                                         FILE_TIME=res.mtime)
            res.rows = len(res.rc7)
            res.note = f"{len(res.blocks)} block table(s)" if res.blocks else ""
            if res.rc7.empty:
                res.note = (res.note + "; " if res.note else "") + "no RC-7 rows"
            logging.info(f"Loaded {self._label(path)}: {res.rows} RC-7 rows, {len(res.blocks)} block tables")
        except Exception as e:                       # one bad file must not stop the rest
            res.error = _why(e)
            logging.warning(f"Failed {self._label(path)}: {res.error} ({(str(e).splitlines() or [''])[0][:300]})")
        return res

    # ------------------------------------------------------------ DGCES

    def _convert_dgces(self, path: Path, res: FileResult) -> None:
        from src.components import c01_importschedules_dgces
        from src.components.c01_dgces_rc7 import loader
        from src.components.c01_dgces_rc7.builder import build
        from src.components.c01_dgces_rc7.report import Recorder

        sample = self.sample_for(path)
        if sample not in ("1", "2"):
            res.note = "skipped: choose the sample (Central / State) for DGCES files"
            logging.warning(f"{self._label(path)}: DGCES file skipped - no sample given (1 Central / 2 State)")
            return
        data = loader.load(str(path))                 # checks the columns, joins Supervisor + PW rows
        rec = Recorder()
        conv = c01_importschedules_dgces.Converter(self.params.dgces_codes)
        tables: dict[str, list[dict]] = {t: [] for t in BLOCKS}
        ids = []
        for row in data.rows:
            key = c01_importschedules_dgces.dgces_key(row)
            for t, recs in conv.convert(row, rec).items():
                for r in recs:
                    r["DGCES_KEY"] = key
                tables[t] += recs
            ids.append(c01_importschedules_dgces.identity(row, sample, self._label(path)))
        for k in data.duplicate_pw_keys:
            rec.issue("Duplicate PW join key (first PW row used)", None, " / ".join(k))
        rc7 = build(data.rows, rec)                   # KrishiStat rules -> RC-7 codes (59 columns)
        rc7_df = pd.DataFrame(rc7.rows, columns=rc7.columns)
        rc7_df["ST"] = int(sample)
        rc7_df["DIST"] = None                         # LGD codes are not AS 2.0 codes: kept in DGCES_ID instead
        rc7_df["VILL"] = None
        rc7_df.insert(0, "SRL", 1)
        rc7_df.insert(0, "EXPTID", "")
        rc7_df = rc7_df.reindex(columns=RC7_COLUMNS).astype(object)
        for c in RC7_COLUMNS:                         # written as the .mdb holds it: CROP 08, ADH 0404 …
            rc7_df[c] = [rc7_text(c, v) for v in rc7_df[c]]
        rc7_df["DGCES_KEY"] = [i["DGCES_KEY"] for i in ids]

        yr_of = {i["DGCES_KEY"]: i["YEAR"][:4] for i in ids}       # 2025-26 -> 2025, as RC-7 YR
        meta = dict(SOURCE="DGCES", SOURCE_FILE=self._label(path), FILE_TIME=res.mtime)
        for t, recs in tables.items():
            b = pd.DataFrame(recs, columns=BLOCKS[t] + ["DGCES_KEY"])
            res.blocks[t] = b.assign(YR=b["DGCES_KEY"].map(yr_of), **meta)
        res.blocks[RC7_TABLE] = rc7_df.assign(**meta)
        res.blocks["DGCES_ID"] = pd.DataFrame(ids).assign(FILE_TIME=res.mtime)
        res.rows = len(ids)
        res.note = (f"{len(ids)} experiments ({len(data.unmatched)} without PW row), sample "
                    f"{'Central' if sample == '1' else 'State'}; EXPTID waits for the order of selection; "
                    f"{len(rec.issues)} issue(s)")
        self.dgces_issues.append((self._label(path), rec))
        logging.info(f"DGCES {self._label(path)}: {res.note}")

    # ------------------------------------------------------------ all files

    @staticmethod
    def _newest(frames: list[pd.DataFrame], key: str) -> pd.DataFrame:
        """Join frames; the same key in several files: rows of the newest file only."""
        frames = [f for f in frames if f is not None and not f.empty]
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        newest = df.groupby(key)["FILE_TIME"].transform("max")
        return df[df["FILE_TIME"] == newest].reset_index(drop=True)

    def _keep_this(self, res: "FileResult") -> None:
        """Keep only the rows of this state + year; note what is left out."""
        from collections import Counter
        from src.utils.raw_inbox import _year_label, describe

        p = self.params
        res.kept = res.rows
        if not p.state or res.error or res.note.startswith("skipped"):
            return
        code, yr = str(p.state_code).zfill(2), str(p.year)[:4]
        names = p.names or {}
        if res.kind == "DGCES":
            ids = res.blocks.get("DGCES_ID")
            if ids is None or ids.empty:
                res.kept = 0
                return
            mine = (ids["STATENAME"].str.upper() == p.state.upper()) & (ids["YEAR"] == p.year)
            keys = set(ids.loc[mine, "DGCES_KEY"])
            res.left = describe(Counter(zip(ids.loc[~mine, "STATENAME"].str.upper(), ids.loc[~mine, "YEAR"])))
            res.blocks = {t: (b[b["DGCES_KEY"].isin(keys)].reset_index(drop=True) if "DGCES_KEY" in b.columns else b)
                          for t, b in res.blocks.items()}
            res.kept = int(mine.sum())
            return
        r = res.rc7
        if r.empty:
            res.kept = 0
            return
        st = r["STAT"].map(self._clean_val).str.zfill(2)
        yy = r["YR"].map(self._clean_val)
        mine = (st == code) & (yy == yr)
        res.left = describe(Counter((names.get(s, f"STATE-{s}"), _year_label(y)) for s, y in zip(st[~mine], yy[~mine])))
        res.rc7 = r[mine].reset_index(drop=True)
        res.blocks = {t: b[(b["EXPTID"].str[1:3] == code) & (b["YR"].astype(str) == yr)].reset_index(drop=True)
                      for t, b in res.blocks.items()}
        res.kept = int(mine.sum())

    def ingest_data(self) -> pd.DataFrame:
        logging.info("Entered ingest_data method of ImportSchedules class")
        ingestion_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.files = [self._load_file(p, i) for i, p in enumerate(self._discover_files())]
        for f in self.files:
            self._keep_this(f)
        self._prune_cache()
        logging.info(f"Files: {self.n_read} read, {self.n_cached} unchanged (taken from the cache)")
        ok = [f for f in self.files if not f.error]

        # RC-7 (mdb / RC-7 files): newest file per UID
        df = self._newest([f.rc7 for f in ok], "UID")
        if not df.empty:
            before = len(df)
            df = df.drop_duplicates("UID", keep="last")
            if len(df) < before:
                logging.info(f"Removed {before - len(df)} duplicate UID rows inside one file")
            df["created_at"] = ingestion_timestamp
        # Blocks of mdb files: for each Exp-ID + YR the rows of the newest file that has it
        mdb = [f for f in ok if f.kind != "DGCES"]
        winner = self._newest([b[["EXPTID", "YR", "SOURCE_FILE", "FILE_TIME"]].assign(_K=b["EXPTID"] + "|" + b["YR"])
                               for f in mdb for b in f.blocks.values()], "_K")
        winner = winner[["EXPTID", "YR", "SOURCE_FILE"]].drop_duplicates() if not winner.empty else winner
        self.blocks = {}
        for t in BLOCK_TABLES:
            parts = [f.blocks[t] for f in mdb if t in f.blocks]
            if parts:
                b = pd.concat(parts, ignore_index=True).merge(winner, on=["EXPTID", "YR", "SOURCE_FILE"])
                self.blocks[t] = b.reset_index(drop=True)
        # DGCES: newest file per DGCES_KEY
        dg = [f for f in ok if f.kind == "DGCES" and f.blocks]
        self.dgces = {}
        if dg:
            wins = self._newest([f.blocks["DGCES_ID"][["DGCES_KEY", "SOURCE_FILE", "FILE_TIME"]] for f in dg],
                                "DGCES_KEY")[["DGCES_KEY", "SOURCE_FILE"]].drop_duplicates()
            for t in list(BLOCKS) + [RC7_TABLE, "DGCES_ID"]:
                b = pd.concat([f.blocks[t] for f in dg], ignore_index=True)
                self.dgces[t] = b.merge(wins, on=["DGCES_KEY", "SOURCE_FILE"]).reset_index(drop=True)

        if "EXPTID" in df.columns:
            df["EXPTID"] = df["EXPTID"].astype(str)
        logging.info(f"Exited ingest_data method of ImportSchedules class (RC-7 rows: {len(df)}, block tables: "
                     f"{len(self.blocks)}, DGCES experiments: {len(self.dgces.get('DGCES_ID', []))})")
        return df

    # ------------------------------------------------------------ outputs

    def write_tables(self, mdb_dir: Path, dgces_dir: Path, clubbed_dir: Path, rc7: pd.DataFrame) -> None:
        """mdb/<table>.csv (block tables + Sch20RC7 from .mdb), dgces/<table>.csv (the same tables made from DGCES,
        + DGCES_ID) and clubbed/<table>.csv (mdb and DGCES rows together; SOURCE tells them apart). Files of tables
        no longer present are removed."""
        mdb = dict(self.blocks)
        if not rc7.empty:
            mdb[RC7_TABLE] = rc7
        clubbed = {}
        for t in [RC7_TABLE] + BLOCK_TABLES:
            parts = [x for x in (mdb.get(t), self.dgces.get(t)) if x is not None and not x.empty]
            if parts:
                clubbed[t] = pd.concat(parts, ignore_index=True, sort=False)
        for folder, tables in ((mdb_dir, mdb), (dgces_dir, self.dgces), (clubbed_dir, clubbed)):
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.csv"):
                if old.stem not in tables:
                    old.unlink()
            for t, df in tables.items():
                df.drop(columns=["FILE_TIME"], errors="ignore").to_csv(folder / f"{t}.csv", index=False,
                                                                       encoding="utf-8-sig")
                logging.info(f"Saved {folder.name}/{t}.csv ({len(df)} rows)")

    def write_report(self, folder: Path, rc7: pd.DataFrame) -> None:
        """The report as CSV files in folder/: Files.csv, Tables.csv, and per DGCES file
        'DGCES issues <file>.csv', 'DGCES codes <file>.csv', 'PW vs S <file>.csv'. Earlier reports are replaced."""
        folder.mkdir(parents=True, exist_ok=True)
        for old in list(folder.glob("*.csv")) + [folder.parent / "schedule_ingestion_report.xlsx"]:   # (older: Excel)
            if old.exists():
                old.unlink()

        def save(df: pd.DataFrame, name: str) -> None:
            df.to_csv(folder / f"{name}.csv", index=False, encoding="utf-8-sig")

        def place(label: str) -> dict:
            """MDB|DGCES/<file> (inside <STATE>/<YEAR>/) -> source, this state + year, file name."""
            p = label.split("/")
            return {"Source": p[0] if len(p) > 1 else "", "State": self.params.state, "Year": self.params.year,
                    "File name": p[-1]}

        def result(f) -> str:
            if f.error:
                return "Failed"
            if f.note.startswith("skipped"):
                return "Not imported"
            return "Imported" if f.kept else "Nothing for this state + year"

        def why(f) -> str:
            text = f.error or f.note
            if f.left and not f.error:
                text += f"; left out (other states / years): {f.left}"
            return text

        files = pd.DataFrame([{"File": f.file, **place(f.file),
                               "Imported on": datetime.fromtimestamp(int(f.mtime)).strftime("%Y-%m-%d %H:%M"),
                               "Type": f.kind, "Rows (RC-7 / DGCES experiments)": f.kept,
                               "Result": result(f), "Why / details": why(f)} for f in self.files])
        self.files_report = files
        counts =pd.DataFrame([{"Table": t, "MDB rows": len(self.blocks.get(t, [])),
                                "MDB Exp-IDs (per YR)": (self.blocks[t]["EXPTID"] + self.blocks[t]["YR"]).nunique()
                                if t in self.blocks else 0,
                                "DGCES rows": len(self.dgces.get(t, []))}
                               for t in [RC7_TABLE] + BLOCK_TABLES])
        counts.loc[counts.Table == RC7_TABLE, "MDB rows"] = len(rc7)
        counts.loc[counts.Table == RC7_TABLE, "MDB Exp-IDs (per YR)"] = rc7["UID"].nunique() if not rc7.empty else 0
        save(files, "Files")
        save(counts, "Tables")
        for name, rec in self.dgces_issues:
            tag = re.sub(r'[\\/:*?"<>|]', "", Path(name).stem).strip()      # file names: no \ / : * ? " < > |
            for title, df in (("DGCES issues", pd.DataFrame(rec.issues)),
                              ("DGCES codes", pd.DataFrame(rec.unmapped_rows())),
                              ("PW vs S", pd.DataFrame(rec.comparisons))):
                if not df.empty:
                    save(df, f"{title} {tag}")
        logging.info(f"Schedule ingestion report written: {folder}")
