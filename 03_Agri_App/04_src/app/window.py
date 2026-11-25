"""The app window (KrishiStat's look).

  Welcome page ->  logos, name, Start (nothing else)
  States page  ->  one card per state with its years; 'Import Master List…' (once a year) creates a state + year
  Work page    ->  left: the modules (1. Import Schedules … 8. Annexures)
                   right: Season / Crop (from the stored master list), the chosen module, the log;
                   'Master list' opens 00. Master List of the state + year (view only)
Modules run their pipeline in the background (the same code as run_step.py) and show what it wrote in 02_artifacts/.
"""
from __future__ import annotations

from src.utils import folders as F
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .look import (fit_columns, C, STYLE, AutoLabel, FrontPage, Kpi, Table, Toast, button, card, chip, fit_to_screen, flow_box, label,
                   open_folder,
                   run_exec, std_icon, toast, wheat_pixmap)
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .states_page import StatesPage, all_years, default_year

ROOT = Path(__file__).resolve().parents[2]            # 03_Agri_App
ART = ROOT / "02_artifacts"
RAW = ROOT / "01_raw_data"
DB = ROOT / "00_database"
BACKUP = ROOT / "05_backup"
RED = QtGui.QColor(C["red_bg"])
GREEN = QtGui.QColor(C["green_bg"])
YELLOW = QtGui.QColor("#FFF1C9")
MAX_ROWS = 50000                                       # rows shown in one table (the CSV keeps everything)
_CACHE: dict = {}


def read_csv(path: Path) -> pd.DataFrame:
    """CSV as text (cached until the file changes); empty table if missing / empty / open elsewhere."""
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return pd.DataFrame()
    hit = _CACHE.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, OSError, UnicodeDecodeError):
        df = pd.DataFrame()
    _CACHE[path] = (stamp, df)
    return df


def read_folder(folder: Path) -> dict:
    """{file name without .csv: table} for every CSV in a report folder."""
    return {p.stem: read_csv(p) for p in sorted(folder.glob("*.csv"))} if folder.exists() else {}


def _num(s: pd.Series) -> pd.Series:
    """'2025.0' / '08' / '8' -> '2025' / '8' / '8' (for comparing codes written differently)."""
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.lstrip("0")


# ---------------------------------------------------------------------------
# What is chosen: state + year (top bar), season / crop (work page)
# ---------------------------------------------------------------------------
@dataclass
class Scope:
    state: str = ""          # e.g. BIHAR
    code: str = ""           # e.g. 10
    year: str = ""           # e.g. 2025-26
    season: str = ""         # season code, '' = all
    season_name: str = ""
    crop: str = ""           # crop code (4 digits), '' = all
    crop_name: str = ""

    @property
    def yr(self) -> str:     # RC-7 YR = the first year
        return self.year[:4]

    @property
    def ok(self) -> bool:
        return bool(self.state and self.year)

    def text(self) -> str:
        parts = [self.state, self.year] + ([self.season_name] if self.season else []) + \
                ([self.crop_name] if self.crop else [])
        return "  ›  ".join(p for p in parts if p)


def _busy_refresh(page) -> None:
    """page.refresh() with the hourglass cursor, so a module that takes a moment does not look stuck."""
    QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        page.refresh()
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def master_list(scope: Scope, all_seasons: bool = False) -> pd.DataFrame:
    """The stored master list of the scope's state + year (season / crop applied unless all_seasons)."""
    df = read_csv(DB / F.MASTER_LIST / scope.state / scope.year / "master_list.csv")
    if df.empty or all_seasons:
        return df
    if scope.season:
        df = df[df["SEASONCODE"] == scope.season]
    if scope.crop:
        df = df[df["CROPCODE"] == scope.crop]
    return df


# ---------------------------------------------------------------------------
# Background run of a pipeline, with its log lines sent to the window
# ---------------------------------------------------------------------------
class _LogBridge(QtCore.QObject):
    line = Signal(str)


class _QtLog(logging.Handler):
    def __init__(self, bridge: _LogBridge) -> None:
        super().__init__(logging.INFO)
        self.bridge = bridge
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%H:%M:%S"))

    def emit(self, record) -> None:
        msg = record.getMessage()
        if msg.startswith(("Entered Method", "Exited Method", "Directory created")):
            return
        self.bridge.line.emit(self.format(record))


class Worker(QtCore.QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], bridge: _LogBridge) -> None:
        super().__init__()
        self.fn, self.bridge = fn, bridge

    def run(self) -> None:
        handler = _QtLog(self.bridge)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            self.done.emit(self.fn())
        except Exception as e:                         # shown to the user, never crashes the app
            import traceback
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")
        finally:
            root.removeHandler(handler)


def bring_in_then(paths: list, raw_sub: str, kind: str, step_fn: Callable[..., object],
                  pass_targets: bool = False, state: Optional[str] = None,
                  year: Optional[str] = None) -> Callable[[], object]:
    """Copy picked files into 01_raw_data/<raw_sub>/… (old copy of the same name to 05_backup/raw), then run the step
    (given the copied files' paths when pass_targets)."""
    def fn():
        from src.utils import raw_inbox
        lines = raw_inbox.bring_in(paths, RAW / raw_sub, BACKUP, kind, DB, state, year)
        for line in lines:
            logging.getLogger().info(
                f"Copied {line['file']} -> {Path(line['to']).relative_to(ROOT) if line['to'] else ''}"
                + (f" (old copy moved to {Path(line['replaced_backup']).relative_to(ROOT)})" if line["replaced_backup"] else "")
                + (f" - {line['note']}" if line["note"] else ""))
        return step_fn([line["to"] for line in lines if line["to"]]) if pass_targets else step_fn()
    return fn


def master_list_job() -> Callable[[], object]:
    """Master list run; returns what happened to each state + year (New / Replaced / Unchanged / Kept)."""
    from src.pipelines.p00_masterlist_pipeline import MasterListPipeline

    def run():
        p = MasterListPipeline()
        p.main()
        return p.ingestion.stored
    return run


# ---------------------------------------------------------------------------
# A table of a CSV / DataFrame with search and one filter list
# ---------------------------------------------------------------------------
class DataView(QtWidgets.QWidget):
    def __init__(self, filter_label: str = "", col_width: int = 110) -> None:
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        bar = QtWidgets.QHBoxLayout()
        self.count = chip("", "blue")
        bar.addWidget(self.count)
        bar.addStretch(1)
        self.filter_col = ""
        self.filter = QtWidgets.QComboBox()
        self.filter.setMinimumWidth(110)
        self.filter_lb = QtWidgets.QLabel(filter_label)
        bar.addWidget(self.filter_lb)
        bar.addWidget(self.filter)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search any value …")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(130)
        bar.addWidget(self.search)
        lay.addLayout(bar)
        self.view = Table(col_width)
        lay.addWidget(self.view, 1)
        self.df = pd.DataFrame()
        self._text: Optional[pd.Series] = None             # each row as one lower-case string (for the search)
        self._fit = True                                     # size the columns on the next refresh (new data)
        self.bg: Optional[Callable] = None
        self.filter.currentIndexChanged.connect(self.refresh)
        self._wait = QtCore.QTimer(self)                     # search when typing pauses, not on every key
        self._wait.setSingleShot(True)
        self._wait.setInterval(250)
        self._wait.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda *_: self._wait.start())
        self.filter.setVisible(bool(filter_label))
        self.filter_lb.setVisible(bool(filter_label))

    def set_frame(self, df: pd.DataFrame, filter_col: str = "", bg: Optional[Callable] = None) -> None:
        self.df, self.filter_col, self.bg = df, filter_col, bg
        self._text, self._fit = None, True
        keep = self.filter.currentText()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("All")
        if filter_col and filter_col in df.columns:
            self.filter.addItems(sorted(v for v in df[filter_col].astype(str).unique() if v != ""))
        if keep and self.filter.findText(keep) > 0:
            self.filter.setCurrentText(keep)
        self.filter.blockSignals(False)
        self.refresh()

    def refresh(self) -> None:
        df = self.df
        if df.empty:
            self.view.set(list(df.columns), [])
            self.count.setText("0 rows")
            return
        if self.filter_col and self.filter.currentIndex() > 0 and self.filter_col in df.columns:
            df = df[df[self.filter_col].astype(str) == self.filter.currentText()]
        q = self.search.text().strip().lower()
        if q:
            if self._text is None:                           # built once per table, then every search is quick
                self._text = self.df.astype(str).agg(" | ".join, axis=1).str.lower()
            df = df[self._text.loc[df.index].str.contains(q, regex=False)]
        shown = df.head(MAX_ROWS)
        rows = shown.astype(str).values.tolist()
        bg = None
        if self.bg is not None:
            recs = shown.to_dict("records")
            fn = self.bg
            bg = (lambda r, c: fn(recs[r], shown.columns[c]))
        self.view.set([str(c) for c in df.columns], rows, bg)
        if self._fit:                                 # new data: columns as wide as their text (max 420 px)
            self._fit = False
            fit_columns(self.view)
            hh = self.view.horizontalHeader()
            for i in range(hh.count()):
                hh.resizeSection(i, min(hh.sectionSize(i) + 8, 420))
        more = f" (first {MAX_ROWS:,} shown)" if len(df) > MAX_ROWS else ""
        self.count.setText(f"{len(df):,} of {len(self.df):,} rows{more}")


# ---------------------------------------------------------------------------
# One module
# ---------------------------------------------------------------------------
class StepTab(QtWidgets.QWidget):
    number = 0
    title = ""
    tab = ""
    what = ""
    run_text = "Run"
    folder: Path = ART
    # files the user picks are copied into 01_raw_data/<raw_sub>/… and then the module runs
    raw_sub = ""
    raw_kind = ""
    pick_filter = ""
    pass_targets = False                   # the module's job takes the copied files' paths

    def __init__(self, win: "MainWindow") -> None:
        super().__init__()
        self.win = win
        self.worker: Optional[Worker] = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(10)
        # compact header: title + actions (+ 'More' menu for folders etc.); then counts and small options
        head, hl = card(12, 6)
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(label(f"{self.number}. {self.title}", "h2", wrap=False), 0, Qt.AlignmentFlag.AlignVCenter)
        acts, self.actions = flow_box(right=True)         # module buttons, right-aligned; wrap only when narrow
        acts.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        top.addWidget(acts, 1)
        self.b_run = button(self.run_text, primary=True, icon="SP_MediaPlay")
        self.actions.addWidget(self.b_run)
        self.b_more = QtWidgets.QToolButton()
        self.b_more.setText("More ▾")
        self.b_more.setObjectName("more")
        self.b_more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.b_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more = QtWidgets.QMenu(self.b_more)
        self.more.addAction(std_icon("SP_DirOpenIcon"), "Open output folder", lambda: open_folder(str(self.folder)))
        self.b_more.setMenu(self.more)
        self.actions.addWidget(self.b_more)
        hl.addLayout(top)
        if self.what:
            hl.addWidget(label(self.what, "muted"))
        mid, self.kpis = flow_box()                        # counts, then small options; they wrap too
        self._extra_box = QtWidgets.QWidget()
        self.extra = QtWidgets.QHBoxLayout(self._extra_box)   # small options (e.g. DGCES sample)
        self.extra.setContentsMargins(8, 0, 0, 0)
        self.kpis.addWidget(self._extra_box)
        hl.addWidget(mid)
        self.status = AutoLabel("")                        # shown only when it has something to say
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.status.setVisible(False)
        hl.addWidget(self.status)
        lay.addWidget(head)
        self.body = QtWidgets.QTabWidget()
        self.body.setDocumentMode(True)
        self.body.setTabBarAutoHide(True)                 # a single tab needs no tab bar
        lay.addWidget(self.body, 1)
        self.b_run.clicked.connect(lambda: self.run())

    @property
    def scope(self) -> Scope:
        return self.win.scope

    def kpi(self, caption: str) -> Kpi:
        k = Kpi(caption, compact=True)
        self.kpis.insertWidget(self.kpis.count() - 1, k)    # before the options box
        return k

    def add_action(self, w: QtWidgets.QWidget) -> None:
        """A module button, placed before Run / More."""
        self.actions.insertWidget(self.actions.count() - 2, w)

    def job(self, picked: Optional[list] = None) -> Optional[Callable[[], object]]:
        raise NotImplementedError

    def pick_and_run(self) -> None:
        paths = self.win.pick_files(f"Choose files for {self.number}. {self.title}", self.pick_filter)
        if not paths:
            return
        step_fn = self.job(paths)
        if step_fn is not None:
            self.run(bring_in_then(paths, self.raw_sub, self.raw_kind, step_fn, self.pass_targets))

    def run(self, fn: Optional[Callable[[], object]] = None) -> None:
        fn = fn or self.job()
        if fn is None:
            return
        self.b_run.setEnabled(False)
        self.b_run.setText("Running …")
        self.status.setText("Working … please wait.")
        self.win.log_clear(f"{self.number}. {self.title}")
        self.worker = Worker(fn, self.win.bridge)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        self.worker.start()

    def _finish(self) -> None:
        QtWidgets.QApplication.restoreOverrideCursor()
        self.b_run.setEnabled(True)
        self.b_run.setText(self.run_text)

    def _done(self, _result) -> None:
        self._finish()
        self.win.after_run(self)
        toast(self, f"{self.number}. {self.title} finished.")

    def _failed(self, msg: str) -> None:
        self._finish()
        self.status.setText("Stopped with an error – see the log.")
        self.win.log_line("ERROR: " + msg)
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        box.setWindowTitle(f"{self.number}. {self.title}")
        box.setText(msg.split("\n\n")[0])
        box.setDetailedText(msg)
        run_exec(box)

    def refresh(self) -> None:
        pass


class MasterListTab(StepTab):
    number, title, tab = "00", "Master List", "Master List"
    what = ("The master list of the chosen state + year – view only. It is imported once a year on the States page "
            "(a later file replaces only the seasons it contains, after you confirm). Season / Crop narrow it.")
    folder = ART / F.MASTER_LIST

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()                         # view only: importing is on the States page
        self.k_exp, self.k_c, self.k_s, self.k_d = (self.kpi("experiments"), self.kpi("central"),
                                                    self.kpi("state sample"), self.kpi("districts"))

        self.more.addAction(std_icon("SP_DirOpenIcon"), "Open backup folder", lambda: open_folder(
            str(BACKUP / F.MASTER_LIST / self.scope.state / self.scope.year) if self.scope.ok else str(BACKUP)))
        self.data = DataView("District")
        self.crops = DataView()
        self.dists = DataView()
        self.checks = DataView()
        self.backups = DataView()
        self.body.addTab(self.data, "Master list")
        self.body.addTab(self.crops, "Crop-wise")
        self.body.addTab(self.dists, "District-wise")
        self.body.addTab(self.checks, "Files and checks")
        self.body.addTab(self.backups, "Backups")
        self.checks.view.doubleClicked.connect(self._open_report)

    def job(self, picked=None):
        return master_list_job()

    def _open_report(self, *_):
        r = self.checks.view.source_row()
        if r is None:
            return
        rec = dict(zip(self.checks.view.src.headers, self.checks.view.src.rows[r]))
        path = rec.get("Error report") or ""
        if path and (ROOT / path).exists():
            os.startfile(str(ROOT / path))             # noqa: S606 (Windows)

    def refresh(self) -> None:
        sc = self.scope
        df = master_list(sc)
        self.data.set_frame(df, "DISTRICTNAME")
        if not df.empty:
            from src.utils import masterlist_checks
            crop, dist = masterlist_checks.summary_tables(df)
            self.crops.set_frame(crop.drop(columns=["STATENAME", "YEAR"]).astype(str))
            self.dists.set_frame(dist.drop(columns=["STATENAME", "YEAR"]).astype(str))
        else:
            self.crops.set_frame(pd.DataFrame())
            self.dists.set_frame(pd.DataFrame())
        files = read_csv(self.folder / sc.state / sc.year / "ML_check_report_files.csv")   # this state + year only
        self.checks.set_frame(files, bg=lambda rec, col: RED if rec.get("Result") == "REJECTED" else
                              (GREEN if col == "Result" else None))
        bdir = BACKUP / F.MASTER_LIST / sc.state / sc.year
        backs = sorted((p for p in bdir.iterdir() if p.is_dir()), reverse=True) if bdir.exists() else []
        self.backups.set_frame(pd.DataFrame([{"Backup (old list, newest first)": p.name,
                                              "Folder": str(p.relative_to(ROOT))} for p in backs]))
        self.k_exp.set(f"{len(df):,}")
        self.k_c.set(f"{int((df.get('SAMPLE', pd.Series(dtype=str)) == '1').sum()):,}")
        self.k_s.set(f"{int((df.get('SAMPLE', pd.Series(dtype=str)) == '2').sum()):,}")
        self.k_d.set(str(df["DISTRICT"].nunique()) if not df.empty else "0")
        rej = int((files.get("Result", pd.Series(dtype=str)) == "REJECTED").sum()) if not files.empty else 0
        self.status.setText(f"{rej} rejected file(s) for this state + year – double-click to open its error report."
                            if rej else "")


class SchedulesTab(StepTab):
    """1. Import Schedules for the OPEN state + year only. Picked files are copied into
    01_raw_data/01_importschedules/<STATE>/<YEAR>/MDB|DGCES/ and read; rows of other states / years in a file are left
    out (named in the import log); a file with nothing for this state + year is not copied at all. Everything it
    writes is in 02_artifacts/01_importschedules/<STATE>/<YEAR>/ and 00_database/01_importschedules/<STATE>/<YEAR>/."""
    number, title, tab = 1, "Import Schedules", "Import Schedules"
    raw_sub, raw_kind = F.IMPORT_SCHEDULES, "schedules"
    pick_filter = "Schedules (*.mdb *.accdb *.zip *.xlsx *.xls *.csv)"
    pass_targets = True
    shows_log = False                         # its own plain import log instead of the technical run log

    @property
    def folder(self) -> Path:                 # 02_artifacts/01_importschedules/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.IMPORT_SCHEDULES / sc.state / sc.year if sc.ok else ART / F.IMPORT_SCHEDULES

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()                         # importing = choosing files; they are read at once
        b_hist = button("Import history", icon="SP_FileDialogDetailedView",
                        tip="Every import of this state + year (saved in import_history.csv)")
        b_hist.clicked.connect(self.show_history)
        self.add_action(b_hist)
        b_esch = button("Import ESch…", primary=True, icon="SP_DialogOpenButton",
                        tip="Pick ESch / NSSAS .mdb or .zip files from anywhere: they are copied into "
                            "01_raw_data/01_importschedules/<STATE>/<YEAR>/MDB/ and read (this state + year only)")
        b_esch.clicked.connect(self.import_esch)
        self.add_action(b_esch)
        b_dgces = button("Import DGCES…", primary=True, icon="SP_DialogOpenButton",
                         tip="Pick a DGCES Excel file; you are asked whether it is the Central or the State sample")
        b_dgces.clicked.connect(self.import_dgces)
        self.add_action(b_dgces)
        self.more.addAction(std_icon("SP_DirOpenIcon"), "Open raw schedules folder", lambda: self._open_raw())
        self.k_ok, self.k_bad, self.k_rc7, self.k_dg, self.k_iss = (
            self.kpi("files imported"), self.kpi("files not imported"), self.kpi("ESch experiments"),
            self.kpi("DGCES experiments"), self.kpi("DGCES issues"))

        self.log_box = QtWidgets.QTextBrowser()             # the last import, file by file, in plain words
        self.log_box.setOpenLinks(False)
        self.log_box.setStyleSheet("QTextBrowser { background: white; border: 1px solid #D5E2D0; border-radius: 8px;"
                                   " padding: 10px; font-size: 10.5pt; }")
        self.body.addTab(self.log_box, "Import log")
        self._imported_now: set = set()                     # (state, year) imported in this session

    def _done(self, result) -> None:
        sc = self.scope
        self._imported_now.add((sc.state, sc.year))       # show this import's log (not at the next start)
        super()._done(result)

    def _open_raw(self) -> None:
        sc = self.scope
        f = RAW / F.IMPORT_SCHEDULES / sc.state / sc.year if sc.ok else RAW / F.IMPORT_SCHEDULES
        f.mkdir(parents=True, exist_ok=True)
        open_folder(str(f))

    def job(self, picked=None, sample=None):
        """Read this state + year's schedules again. Every DGCES file keeps the sample it was imported with;
        `sample` is for the DGCES file(s) picked now (Import DGCES…)."""
        from src.pipelines.p01_importschedules_pipeline import ImportSchedulesPipeline
        sc = self.scope
        return lambda targets=None: ImportSchedulesPipeline(sc.state, sc.code, sc.year, dgces_sample=sample) \
            .main(just_imported=targets)

    def _only_this_state(self, paths: list) -> list:
        """Files with rows of the open state + year. The others are not copied; the user is told what they hold."""
        from src.utils.raw_inbox import contents, describe, state_names
        sc = self.scope
        names = state_names(DB)
        keep, refused, partly = [], [], []
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        try:
            for p in paths:
                c = contents(Path(p), names)
                n = c.get((sc.state, sc.year), 0)
                if c and n == 0:
                    refused.append(f"{Path(p).name}  –  holds {describe(c)}")
                    continue
                keep.append(p)
                if n and len(c) > 1:
                    partly.append(f"{Path(p).name}  –  {n:,} of {sc.state} {sc.year}; left out: "
                                  f"{describe(c, skip=(sc.state, sc.year))}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if refused:
            QtWidgets.QMessageBox.warning(
                self, "Not this state + year",
                f"Not imported – no schedule of {sc.state} {sc.year} in:\n\n" + "\n".join(refused)
                + "\n\nOpen that state + year and import the file there.")
        if partly:
            toast(self, "Only this state + year's rows are taken from: " + "; ".join(partly))
        return keep

    def _import(self, paths: list, sample=None) -> None:
        paths = self._only_this_state(paths) if paths else []
        if paths:
            sc = self.scope
            self.run(bring_in_then(paths, self.raw_sub, self.raw_kind, self.job(paths, sample), self.pass_targets,
                                   state=sc.state, year=sc.year))

    def import_esch(self) -> None:
        """ESch field files and whole-year NSSAS databases (.mdb / .accdb, or .zip with .mdb inside)."""
        sc = self.scope
        paths = self.win.pick_files(f"Import ESch schedules (.mdb / .zip) for {sc.state} {sc.year}",
                                    "ESch schedules (*.mdb *.accdb *.zip)")
        self._import(paths)

    def import_dgces(self) -> None:
        """DGCES Excel files: checked to be DGCES, then the sample (Central / State) is asked once."""
        from src.utils.raw_inbox import is_dgces
        sc = self.scope
        paths = self.win.pick_files(f"Import DGCES Excel for {sc.state} {sc.year}", "DGCES Excel (*.xlsx)")
        if not paths:
            return
        not_dg = [Path(p).name for p in paths if not is_dgces(Path(p))]
        paths = [p for p in paths if is_dgces(Path(p))]
        if not_dg:
            QtWidgets.QMessageBox.warning(
                self, "Not DGCES", "Not a DGCES Excel file (no FinalNSOFieldData sheet), left out:\n\n"
                + "\n".join(not_dg))
        if not paths:
            return
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("DGCES sample")
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setText("Which sample is this DGCES data?\n\n" + "\n".join(Path(p).name for p in paths))
        b_c = box.addButton("Central (1)", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        b_s = box.addButton("State (2)", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
        run_exec(box)
        sample = "1" if box.clickedButton() is b_c else "2" if box.clickedButton() is b_s else None
        if sample:
            self._import(paths, sample)

    @staticmethod
    def _import_log(files: pd.DataFrame, rc7: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
        """The files (all of this state + year), newest first: when imported, the file, result, experiments of
        this state in it, and why it failed / was not imported / what was left out."""
        if files.empty or "File" not in files.columns:
            return pd.DataFrame()
        n_mdb = rc7.groupby("SOURCE_FILE").size() if not rc7.empty else pd.Series(dtype=int)
        n_dg = ids.groupby("SOURCE_FILE").size() if not ids.empty else pd.Series(dtype=int)
        used = [int((n_dg if s == "DGCES" else n_mdb).get(f, 0)) for f, s in zip(files["File"], files["Source"])]
        why = []
        for d, res, n, rows in zip(files["Why / details"], files["Result"], used,
                                   pd.to_numeric(files["Rows (RC-7 / DGCES experiments)"], errors="coerce").fillna(0)):
            if res == "Imported" and n == 0 and rows > 0:
                d += "; its experiments are also in a newer file – the newer one is used"
            why.append(d)
        out = pd.DataFrame({
            "Imported on": files["Imported on"], "File": files["File name"], "Source": files["Source"],
            "Result": files["Result"], "Experiments (this state)": [str(n) for n in used], "Why / details": why})
        return out.sort_values("Imported on", ascending=False, kind="stable")

    @staticmethod
    def _log_html(last: pd.DataFrame, rc7_all: pd.DataFrame, ids_all: pd.DataFrame) -> str:
        """The last import, one line per file: ✓ imported (how many, what was left out) or ✗ not imported (why)."""
        import html
        import re as _re
        if last.empty or "File" not in last.columns:
            return "<p style='color:#56685A'>Nothing imported yet for this state + year.</p>"
        n_mdb = rc7_all.groupby("SOURCE_FILE").size() if not rc7_all.empty and "SOURCE_FILE" in rc7_all else {}
        n_dg = ids_all.groupby("SOURCE_FILE").size() if not ids_all.empty and "SOURCE_FILE" in ids_all else {}
        ok = int((last["Result"] == "Imported").sum())
        when = last["Import run"].iloc[0] if "Import run" in last.columns else ""
        out = [f"<p><b>Last import {html.escape(str(when))}</b> &nbsp;·&nbsp; {ok} imported, "
               f"{len(last) - ok} not imported</p>"]
        for r in last.to_dict("records"):
            name = html.escape(str(r.get("File name", "")))
            why = str(r.get("Why / details", "") or "")
            rows = int(pd.to_numeric(r.get("Rows (RC-7 / DGCES experiments)", 0), errors="coerce") or 0)
            left = why.split("left out (other states / years): ", 1)[1] if "left out (other states" in why else ""
            if r.get("Result") == "Imported":
                src = r.get("Source", "")
                used = int((n_dg if src == "DGCES" else n_mdb).get(r.get("File", ""), 0))
                extra = []
                m = _re.search(r"sample (Central|State)", why)
                if m:
                    extra.append(f"sample {m.group(1)}")
                m = _re.search(r"(\d+) issue", why)
                if m and m.group(1) != "0":
                    extra.append(f"{m.group(1)} DGCES issues")
                line = (f"<span style='color:#1D6B3A'>✓</span> <b>{name}</b> — imported: {rows:,} experiment(s)"
                        + (f" ({', '.join(extra)})" if extra else ""))
                if rows and used == 0:
                    line += ". The same experiments are in a newer file – the newer one is used"
                if left:
                    line += f". Left out (other states / years): {html.escape(left)}"
            else:
                reason = why.split("; left out")[0] if r.get("Result") != "Nothing for this state + year" else \
                    f"no experiment of this state + year in it (it has: {left})"
                if reason.startswith("skipped"):
                    reason = "the DGCES sample (Central / State) is not known – import it again with Import DGCES…"
                line = (f"<span style='color:#8A1C1C'>✗</span> <b>{name}</b> — <b style='color:#8A1C1C'>not "
                        f"imported</b>: {html.escape(reason)}")
            out.append(f"<p style='margin:6px 0'>{line}.</p>")
        return "".join(out)

    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        from src.utils import schedules
        rep = read_folder(self.folder / "report")
        files = rep.get("Files", pd.DataFrame())
        rc7 = rc7_all = schedules.rc7(sc.state, sc.year)
        ids_all = schedules.dgces_ids(sc.state, sc.year)
        if not rc7.empty:
            keep = pd.Series(True, index=rc7.index)
            if sc.season:
                keep &= _num(rc7["SESON"]) == sc.season.lstrip("0")
            if sc.crop:
                keep &= rc7["CROPCODE"].str.zfill(4) == sc.crop
            rc7 = rc7[keep]
        ids = schedules.dgces_ids(sc.state, sc.year)
        if not ids.empty and sc.season:
            ids = ids[ids["SEASON"].str.upper() == sc.season_name.upper()]
        log = self._import_log(files, rc7, ids)                       # every file of this state + year
        if (sc.state, sc.year) in self._imported_now:                     # only right after importing
            self.log_box.setHtml(self._log_html(rep.get("Last_import", pd.DataFrame()), rc7_all, ids_all))
        else:
            self.log_box.setHtml("<p style='color:#56685A'>The result of an import (what was imported, what was not and "
                                 "why) is shown here after you import files. Earlier imports: Import history.</p>")
        res = log.get("Result", pd.Series(dtype=str))
        n_bad = int((res != "Imported").sum())
        self.k_ok.set(str(int((res == "Imported").sum())))
        self.k_bad.set(str(n_bad), C["red"] if n_bad else None)
        self.k_rc7.set(f"{len(rc7):,}")
        self.k_dg.set(f"{len(ids):,}")
        n_iss = sum(len(v) for k, v in rep.items() if k.startswith("DGCES issues "))
        self.k_iss.set(str(n_iss), C["orange"] if n_iss else None)
        self.status.setText(
            f"No schedules imported for {sc.state} {sc.year} yet – use 'Import ESch…' or 'Import DGCES…'." if log.empty
            else "")

    def show_history(self) -> None:
        """Every import of this state + year (its import_history.csv), newest first."""
        sc = self.scope
        hist = read_csv(self.folder / "import_history.csv")
        if not hist.empty:
            hist = hist.drop(columns=[c for c in ("File", "State", "Year", "Imported on") if c in hist.columns])
            hist = hist.iloc[::-1]
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Import history – {sc.state} {sc.year}")
        fit_to_screen(dlg, 1150, 620)
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.addWidget(label(f"Every import of {sc.state} {sc.year}, newest first. Saved in "
                            f"{(self.folder / 'import_history.csv').relative_to(ROOT)}.", "muted"))
        view = DataView("Result", 120)
        view.set_frame(hist, "Result", bg=lambda rec, col: (
            RED if rec.get("Result") == "Failed" else YELLOW if rec.get("Result") not in ("Imported", None) else None))
        lay.addWidget(view, 1)
        b = button("Close")
        b.clicked.connect(dlg.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        run_exec(dlg)


class LaterTab(QtWidgets.QWidget):
    def __init__(self, number: int, title: str) -> None:
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.addStretch(1)
        c, cl = card(28, 12)
        c.setFixedWidth(520)
        ic = QtWidgets.QLabel()
        ic.setPixmap(wheat_pixmap(56, stem="#B9A46A", leaf="#9CC77A"))
        cl.addWidget(ic, 0, Qt.AlignmentFlag.AlignHCenter)
        t = label(f"{number}. {title}", "h2")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(t)
        m = label("Not built yet.", "muted")
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(m)
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(2)


# ---------------------------------------------------------------------------
# Work page: the modules on the left; Season / Crop and the module on the right
# ---------------------------------------------------------------------------
class MasterListDialog(QtWidgets.QDialog):
    """The stored master list of the open state + year (00. Master List, view only): list, crop-wise,
    district-wise, files and checks, backups. Season / Crop of the work page apply."""

    def __init__(self, win: "MainWindow") -> None:
        super().__init__(win)
        sc = win.scope
        self.setWindowTitle(f"Master list – {sc.text()}")
        fit_to_screen(self, 1250, 780)
        lay = QtWidgets.QVBoxLayout(self)
        self.tab = MasterListTab(win)
        lay.addWidget(self.tab, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        b = button("Close")
        b.clicked.connect(self.accept)
        bar.addWidget(b)
        lay.addLayout(bar)
        self.tab.refresh()


class WorkPage(QtWidgets.QWidget):
    def __init__(self, win: "MainWindow") -> None:
        super().__init__()
        self.win = win
        self.setObjectName("page")
        self.ml = pd.DataFrame()                     # the open state + year's master list
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        split = QtWidgets.QSplitter()
        split.setHandleWidth(8)
        split.setChildrenCollapsible(True)                 # drag the edge to fold the module list away
        outer.addWidget(split)

        left, ll = card(10, 6)
        self.state_lb = label("", "h2", wrap=True)
        ll.addWidget(self.state_lb)
        self.state_sub = label("", "muted")
        ll.addWidget(self.state_sub)
        ll.addSpacing(6)
        ll.addWidget(label("Modules", "h3"))
        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("moduleNav")
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ll.addWidget(self.nav, 1)
        b_states = button("All states", icon="SP_ArrowBack")
        b_states.clicked.connect(win.go_states)
        ll.addWidget(b_states)
        left.setMinimumWidth(150)
        split.addWidget(left)

        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 4, 0)
        rl.setSpacing(6)
        top = QtWidgets.QHBoxLayout()
        self.path_lb = label("", "h1", wrap=True)
        top.addWidget(self.path_lb, 1)
        self.b_ml = button("Master list", icon="SP_FileDialogContentsView",
                           tip="00. Master List of this state + year: the list, crop-wise, district-wise, files and "
                               "checks, backups (view only; import it on the States page)")
        self.b_ml.clicked.connect(self.open_master_list)
        top.addWidget(self.b_ml, 0, Qt.AlignmentFlag.AlignTop)
        rl.addLayout(top)
        fil_w, fil = flow_box(spacing=8)                   # Season / Crop wrap onto two lines when narrow
        self.season_box = QtWidgets.QComboBox()
        self.crop_box = QtWidgets.QComboBox()
        for name, box, chars in (("Season", self.season_box, 18), ("Crop", self.crop_box, 24)):
            box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(chars)
            pair = QtWidgets.QWidget()
            pl = QtWidgets.QHBoxLayout(pair)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.addWidget(QtWidgets.QLabel(name))
            pl.addWidget(box)
            fil.addWidget(pair)
        rl.addWidget(fil_w)
        self.filters_w = fil_w                             # hidden for modules that pick their own (uses_season_crop)
        vsplit = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.pages = QtWidgets.QStackedWidget()
        vsplit.addWidget(self.pages)
        logc, lgl = card(10, 4)
        lgl.addWidget(label("Log", "h3"))
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        lgl.addWidget(self.log)
        vsplit.addWidget(logc)
        self.log_card = logc                         # run log: shown only for modules that run something
        vsplit.setSizes([700, 140])
        rl.addWidget(vsplit, 1)
        right.setMinimumHeight(460)                        # below this the page scrolls instead of squashing
        scroll = QtWidgets.QScrollArea()                   # on a very small screen: scroll, never cut off
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(right)
        split.addWidget(scroll)
        split.setSizes([220, 1150])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setCollapsible(1, False)
        self.nav.currentRowChanged.connect(self._open_module)
        self.season_box.currentIndexChanged.connect(self._season_picked)
        self.crop_box.currentIndexChanged.connect(self._crop_picked)

    # ---- modules
    def _open_module(self, row: int) -> None:
        """Show a module and bring it up to date (data may have changed while another module was open)."""
        self.pages.setCurrentIndex(row)
        page = self.pages.currentWidget()
        self.log_card.setVisible(getattr(page, "shows_log", False))
        self.filters_w.setVisible(getattr(page, "uses_season_crop", True))
        self._show_path()
        if hasattr(page, "refresh") and self.win.scope.ok:          # show the page first, then bring it up to date
            QtCore.QTimer.singleShot(0, lambda: _busy_refresh(page) if self.pages.currentWidget() is page else None)

    def add_module(self, number: int, title: str, page: QtWidgets.QWidget, built: bool) -> None:
        item = QtWidgets.QListWidgetItem(f"{number}.  {title}")
        if not built:
            item.setForeground(QtGui.QColor(C["muted"]))
            item.setToolTip("Not built yet")
        self.nav.addItem(item)
        self.pages.addWidget(page)
        if self.nav.currentRow() < 0:
            self.nav.setCurrentRow(0)

    # ---- state + year, season, crop
    def load_state(self, state: str, code: str, year: Optional[str] = None) -> None:
        """Open a state for the chosen year: Season / Crop lists from its stored master list."""
        state = state.upper()                     # stored as STATENAME in capitals (00_database/00_masterlist/BIHAR/…)
        year = year or self.win.year
        self.win.scope = Scope(state, code, year)
        self.ml = read_csv(DB / F.MASTER_LIST / state / year / "master_list.csv")
        self.state_lb.setText(state)
        self.state_sub.setText(f"State code {code} · {year}")
        self.b_ml.setText(f"Master list · {len(self.ml):,}")
        self.b_ml.setEnabled(not self.ml.empty)
        keep = self.season_box.currentData()
        self.season_box.blockSignals(True)
        self.season_box.clear()
        self.season_box.addItem(f"All seasons · {len(self.ml):,}", ("", ""))
        if not self.ml.empty:
            for (sc, sn), g in self.ml.groupby(["SEASONCODE", "SEASONNAME"], sort=False):
                self.season_box.addItem(f"{sn.title()} ({sc}) · {len(g):,}", (sc, sn.title()))
            order = sorted(range(1, self.season_box.count()),
                           key=lambda i: int(self.season_box.itemData(i)[0]) if self.season_box.itemData(i)[0].isdigit() else 99)
            items = [(self.season_box.itemText(i), self.season_box.itemData(i)) for i in order]
            while self.season_box.count() > 1:
                self.season_box.removeItem(1)
            for t, d in items:
                self.season_box.addItem(t, d)
        i = self.season_box.findData(keep) if keep else -1
        self.season_box.setCurrentIndex(i if i > 0 else 0)
        self.season_box.blockSignals(False)
        self._season_picked()

    def _season_picked(self, *_):
        sc = self.win.scope
        sc.season, sc.season_name = self.season_box.currentData() or ("", "")
        ml = self.ml[self.ml["SEASONCODE"] == sc.season] if sc.season and not self.ml.empty else self.ml
        keep = self.crop_box.currentData()
        self.crop_box.blockSignals(True)
        self.crop_box.clear()
        self.crop_box.addItem(f"All crops · {len(ml):,}", ("", ""))
        if not ml.empty:
            for (cc, cn), g in ml.groupby(["CROPCODE", "CROPNAME"], sort=True):
                self.crop_box.addItem(f"{cn} · {cc} · {len(g):,}", (cc, cn))
        i = self.crop_box.findData(keep) if keep else -1
        self.crop_box.setCurrentIndex(i if i > 0 else 0)
        self.crop_box.blockSignals(False)
        self._crop_picked()

    def _crop_picked(self, *_):
        sc = self.win.scope
        sc.crop, sc.crop_name = self.crop_box.currentData() or ("", "")
        self._show_path()
        self.win.refresh_modules()

    def _show_path(self) -> None:
        """State › year (› season › crop when the open module uses the work page's Season / Crop)."""
        sc = self.win.scope
        page = self.pages.currentWidget()
        if getattr(page, "uses_season_crop", True):
            self.path_lb.setText(sc.text() or sc.state)
        else:
            self.path_lb.setText("  ›  ".join(x for x in (sc.state, sc.year) if x))

    def open_master_list(self) -> None:
        run_exec(MasterListDialog(self.win))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KrishiStat – Agri App for AS 2.0")
        self.setWindowIcon(QtGui.QIcon(wheat_pixmap(64)))
        fit_to_screen(self, 1440, 900)
        self.scope = Scope()
        self.year = default_year(DB)                     # the agricultural year everything shows
        self.bridge = _LogBridge()
        self.bridge.line.connect(self.log_line)

        tb = QtWidgets.QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        logo = QtWidgets.QLabel()
        logo.setPixmap(wheat_pixmap(26))
        tb.addWidget(logo)
        title = QtWidgets.QLabel(" KrishiStat  ")
        title.setStyleSheet("font-weight: 800; font-size: 14pt; color: white; letter-spacing: 1px;")
        tb.addWidget(title)
        tb.addAction("Home").triggered.connect(lambda: self.stack.setCurrentWidget(self.front))
        tb.addAction("All States").triggered.connect(self.go_states)
        tb.addWidget(QtWidgets.QLabel("    Year "))
        self.year_box = QtWidgets.QComboBox()
        self.year_box.setObjectName("barYear")
        self.year_box.setToolTip("Agricultural year: the States page and the modules show this year")
        self.year_box.currentTextChanged.connect(self._year_picked)
        tb.addWidget(self.year_box)
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addAction("Raw data folder").triggered.connect(lambda: open_folder(str(RAW)))
        tb.addAction("Artifacts folder").triggered.connect(lambda: open_folder(str(ART)))
        self.toolbar = tb

        self.front = FrontPage()
        self.states = StatesPage(DB)
        self.work = WorkPage(self)
        from .page_controlregister import ControlRegisterTab     # module pages in their own files
        from .page_viewschedule import ViewScheduleTab
        from .page_datavalidation import DataValidationTab
        from .page_estimates import EstimatesTab
        from .page_estimatereport import EstimateReportTab
        from .page_rc7 import RC7Tab
        from .page_annexures import AnnexuresTab
        self.steps = [SchedulesTab(self), ControlRegisterTab(self), ViewScheduleTab(self), DataValidationTab(self),
                      EstimatesTab(self), EstimateReportTab(self), RC7Tab(self), AnnexuresTab(self)]
        modules = {1: self.steps[0], 2: self.steps[1], 3: self.steps[2], 4: self.steps[3], 5: self.steps[4],
                   6: self.steps[5], 7: self.steps[6], 8: self.steps[7]}   # 00. Master List: States page + 'Master list' button
        for n, m in modules.items():
            if isinstance(m, str):
                self.work.add_module(n, m, LaterTab(n, m), built=False)
            else:
                self.work.add_module(n, m.tab, m, built=True)
        self.log = self.work.log

        self.stack = QtWidgets.QStackedWidget()
        for w in (self.front, self.states, self.work):
            self.stack.addWidget(w)
        self.setCentralWidget(self.stack)
        self.statusBar().addWidget(QtWidgets.QLabel(f"Folder: {ROOT}"))
        self.toast = Toast(self)
        self.front.start.connect(self.go_states)
        self.states.state_chosen.connect(self.open_state)
        self.states.import_clicked.connect(self.import_master_list)
        self.stack.currentChanged.connect(self._front_mode)
        self._refresh_years()
        self._front_mode()

    # ---- navigation
    def _front_mode(self, *_):
        on_front = self.stack.currentWidget() is self.front
        self.toolbar.setVisible(not on_front)
        self.statusBar().setVisible(not on_front)

    # ---- the year (top bar)
    def _refresh_years(self) -> None:
        """Fill the top bar's year list from the stored master lists (after start-up or an import)."""
        years = all_years(DB)
        if self.year not in years:
            self.year = default_year(DB)
        self.year_box.blockSignals(True)
        self.year_box.clear()
        self.year_box.addItems(years)
        self.year_box.setCurrentText(self.year)
        self.year_box.blockSignals(False)
        self.year_box.setEnabled(bool(years))
        self.states.set_year(self.year)

    def _year_picked(self, year: str) -> None:
        if year and year != self.year:
            self.set_year(year)

    def set_year(self, year: str) -> None:
        """Show `year` everywhere. On the work page the same state stays open if it has that year."""
        self.year = year
        self.year_box.blockSignals(True)
        self.year_box.setCurrentText(year)
        self.year_box.blockSignals(False)
        self.states.set_year(year)
        sc = self.scope
        if self.stack.currentWidget() is self.work and sc.state:
            if (DB / F.MASTER_LIST / sc.state / year / "master_list.csv").exists():
                self.work.load_state(sc.state, sc.code, year)
            else:
                self.stack.setCurrentWidget(self.states)
                toast(self.states, f"{sc.state} has no master list for {year} – choose a state")

    def go_states(self) -> None:
        from src.logger import logging as applog
        applog.use_folder()                              # no state open: 03_logs/app/
        self.states.refresh()
        self.stack.setCurrentWidget(self.states)

    def open_state(self, state: str, code: str, year: Optional[str] = None) -> None:
        if year and year != self.year:
            self.set_year(year)
        from src.logger import logging as applog
        applog.use_folder(state, self.year)              # 03_logs/<STATE>/<YEAR>/
        self.work.load_state(state, code, self.year)
        self.stack.setCurrentWidget(self.work)
        self.refresh_modules()                           # the module shown: its numbers right away
    def refresh_modules(self) -> None:
        """Bring the module on screen up to date. The others are refreshed when they are opened (_open_module), so
        picking a state / season / crop does not work out all eight modules at once."""
        page = self.work.pages.currentWidget()
        if self.stack.currentWidget() is self.work and page in self.steps and self.scope.ok:
            _busy_refresh(page)

    def after_run(self, step: StepTab) -> None:
        """A module finished (e.g. schedules imported): every module shows the new data."""
        self.refresh_modules()

    def pick_files(self, caption: str, filt: str) -> list:
        start = getattr(self, "last_pick_dir", "") or str(Path.home())
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, caption, start, filt)
        if paths:
            self.last_pick_dir = str(Path(paths[0]).parent)
        return paths

    # ---- master list import (once a year, from the States page): check -> review -> confirm -> store
    def import_master_list(self) -> None:
        paths = self.pick_files("Import master list(s) – state and year are read from the file", "Excel (*.xlsx *.xlsm)")
        if not paths:
            return
        from .ml_import import check_files
        self.log_clear("Import master list – checking")
        self._busy(True)
        self._chk = Worker(lambda: check_files(paths, ART, DB), self.bridge)
        self._chk.done.connect(self._review)
        self._chk.failed.connect(self._import_failed)
        self._chk.start()

    def _busy(self, on: bool) -> None:
        if on:
            QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _import_failed(self, msg: str) -> None:
        self._busy(False)
        self.log_line("ERROR: " + msg)
        QtWidgets.QMessageBox.critical(self, "Import master list", msg.split(chr(10) * 2)[0])

    def _review(self, results: list) -> None:
        from .ml_import import ImportReview
        self._busy(False)
        dlg = ImportReview(results, self)
        if not run_exec(dlg) or not dlg.to_import:
            self.log_line("Import master list: nothing stored")
            return
        self.log_clear("Import master list – storing")
        self._busy(True)
        self._imp = Worker(bring_in_then(dlg.to_import, F.MASTER_LIST, "master_list", master_list_job()), self.bridge)
        self._imp.done.connect(self._imported)
        self._imp.failed.connect(self._import_failed)
        self._imp.start()

    def _imported(self, stored) -> None:
        self._busy(False)
        rows = [r for r in (stored or []) if r["Action"] != "Unchanged"]
        changed = [f"{r['State']} {r['Year']}: {r['Action']}" for r in rows]
        self._refresh_years()
        if rows and rows[0]["Year"] != self.year:          # show the year just imported
            self.set_year(rows[0]["Year"])
        if self.scope.ok and self.stack.currentWidget() is self.work:
            self.work.load_state(self.scope.state, self.scope.code, self.year)
        toast(self.states, "Imported – " + ("; ".join(changed) or "nothing changed"))

    # ---- log
    def log_clear(self, title: str) -> None:
        self.log.appendPlainText(f"\n===== {title} =====")

    def log_line(self, text: str) -> None:
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())


def main() -> int:
    os.chdir(ROOT)                       # the pipelines use paths relative to 03_Agri_App
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    return run_exec(app)
