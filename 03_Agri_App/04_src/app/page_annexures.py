"""8. Annexures page (components/c08_annexures.py) – export the RC-7 annexures and Y-tables of a report.

A line under the title: Kharif report / Rabi report (one of them; none picked to start with). Their seasons come from
the master list – Kharif: codes 1 – 3 (Kharif, or Bhadai + Agahani), Rabi: the others (Rabi, or Rabi + Summer). The status line says where this year's and last year's RC-7 come from.
Previous year: the app's own RC-7 of that year; only when the app does not have it, the file loaded with
'Load previous year RC-7…'.
Export: asks English / Hindi / Bilingual, then makes 1Annexures(Eng / Hi / Bi) (XIX – XXIV), the Y-tables as
'1Tables S-1 / S-2 …' (one per season) and '1Tables 8,9,10-Y' – exact copies of the old books – and a CSV per
table. The workbooks just made are shown
made for this state + year (double-click opens one). XVI, XVII and XXV are filled in the workbook.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime

from src.components import c05_estimates as est
from src.components import c06_estimatereport as er
from src.components import c07_rc7 as rc7m
from src.components import c08_annexures as A
from src.components import c08_annexures_excel as X
from src.utils import folders as F
from src.utils import schedules

from .look import AutoLabel, button, fit_columns, flow_box, label, toast
from .qt import QtCore, QtGui, QtWidgets, Qt
from .window import ART, RAW, StepTab, master_list

RC7_FILTER = "RC-7 files (*.xlsx *.xls *.csv *.dbf *.mdb *.accdb);;All files (*)"
CONF_HEADS = ["Season", "Crop", "Sample", "Harvested", "CONFAC", "From"]
CONF = CONF_HEADS.index("CONFAC")
GREY = QtGui.QBrush(QtGui.QColor("#eef1f4"))
WHITE = QtGui.QBrush(QtGui.QColor("#ffffff"))
MISSING = QtGui.QBrush(QtGui.QColor("#fde2e1"))


class AnnexuresTab(StepTab):
    number, title, tab = 8, "Annexures", "Annexures"
    uses_season_crop = False                  # its own season ticks; all crops

    @property
    def folder(self):                       # 02_artifacts/08_annexures/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.ANNEXURES / sc.state / sc.year if sc.ok else ART / F.ANNEXURES

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self._key = None
        self.rep: A.Report | None = None

        # --- Season ticks, on a line under the title
        picks, self.picks = flow_box(spacing=10)
        self.picks.addWidget(label("Report", "muted", wrap=False))
        self.report_group = QtWidgets.QButtonGroup(self)      # one report at a time
        self.report_group.setExclusive(True)
        self.season_cbs: list[QtWidgets.QCheckBox] = []
        self._seasons_for = None
        self.end_lb = label("", "muted", wrap=False)
        self.picks.addWidget(self.end_lb)
        self.status.parentWidget().layout().insertWidget(1, picks)

        self.b_prev = button("Load previous year RC-7…", icon="SP_DialogOpenButton",
                             tip="Last year's RC-7 when the app does not have it: the old 'PY State Details' Excel "
                                 "(sheet RC-7), rc7.dbf, CSV or .mdb / .accdb (Sch20RC7)")
        self.b_prev.clicked.connect(self.load_previous)
        self.add_action(self.b_prev)
        self.b_export = button("Export", primary=True, icon="SP_DialogSaveButton",
                               tip="Asks English / Hindi / Bilingual, then makes 1Annexures(…) + 1Tables S-1 / "
                                   "S-2 … + 1Tables 8,9,10-Y (exact copies of the old books) + CSV files")
        self.b_export.clicked.connect(self.export)
        self.add_action(self.b_export)
        self.more.addAction("Remove the loaded previous-year file", self.remove_previous)
        self.k_cy = self.kpi("schedules this year")
        self.k_py = self.kpi("schedules last year")

        # --- what Export just made (only right after it), then the CONFAC of each crop
        conf = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(conf)
        cl.setContentsMargins(4, 8, 4, 4)
        self.made_lb = AutoLabel("")
        self.made_lb.setWordWrap(True)
        self.made_lb.setTextFormat(Qt.TextFormat.RichText)
        self.made_lb.linkActivated.connect(lambda link: os.startfile(link))     # noqa: S606 (Windows)
        cl.addWidget(self.made_lb)
        self.conf_table = QtWidgets.QTableWidget(0, len(CONF_HEADS))
        self.conf_table.setHorizontalHeaderLabels(CONF_HEADS)
        self.conf_table.verticalHeader().setVisible(False)
        self.conf_table.verticalHeader().setDefaultSectionSize(24)
        T = QtWidgets.QAbstractItemView.EditTrigger
        self.conf_table.setEditTriggers(T.CurrentChanged | T.SelectedClicked | T.AnyKeyPressed | T.DoubleClicked)
        self.conf_table.itemChanged.connect(self._confac_typed)
        cl.addWidget(self.conf_table, 1)
        self.body.addTab(conf, "CONFAC")
        self._conf_rows: list[dict] = []
        self._langs: list[str] = []                         # annexure languages ticked at the last Export

    # ------------------------------------------------------------------ seasons
    def _seasons(self) -> list[str]:
        return next((list(cb.property("codes")) for cb in self.season_cbs if cb.isChecked()), [])

    def _build_seasons(self, ml) -> None:
        """Two choices: the Kharif report and the Rabi report of the year (their seasons from the master list)."""
        for cb in self.season_cbs:
            self.report_group.removeButton(cb)
            i = self.picks.indexOf(cb)
            if i >= 0:
                self.picks.takeAt(i)
            cb.hide()
            cb.setParent(None)
            cb.deleteLater()
        self.season_cbs = []
        at = self.picks.indexOf(self.end_lb)
        for i, (rep_name, seasons) in enumerate(A.report_seasons(ml).items()):
            n = sum(x[2] for x in seasons)
            cb = QtWidgets.QCheckBox(f"{rep_name} report: {' + '.join(x[1] for x in seasons)} ({n:,})")
            cb.setProperty("codes", [x[0] for x in seasons])
            cb.setToolTip(f"The {rep_name} report – season(s) {', '.join(x[0] for x in seasons)}: {n:,} planned "
                          f"experiments")
            cb.setChecked(False)                              # the user picks the report
            cb.toggled.connect(lambda on, cb=cb: self._season_toggled(cb, on))
            self.report_group.addButton(cb)
            self.picks.insertWidget(at + i, cb)
            self.season_cbs.append(cb)
        self.picks.invalidate()
        self.picks.parentWidget().updateGeometry()

    def _season_toggled(self, cb, on: bool) -> None:
        if on:
            self.refresh()

    # ------------------------------------------------------------------ data
    def _mtime(self, f) -> int:
        try:
            return f.stat().st_mtime_ns
        except OSError:
            return 0

    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        ml = master_list(sc, all_seasons=True)
        if self._seasons_for != (sc.state, sc.year):
            self._seasons_for = (sc.state, sc.year)
            self._build_seasons(ml)
            self.made_lb.setText("")                         # what Export made: only until another state / year
        py = er.previous_year(sc.year, 1)
        d = A.prev_folder(sc.state, sc.year)
        key = (sc.state, sc.year, tuple(self._seasons()), schedules.stamp(sc.state, sc.year),
               schedules.stamp(sc.state, py), self._mtime(d / A.PREV_FILE),
               self._mtime(rc7m.DB / sc.state / sc.year / rc7m.FINAL_FILE),
               self._mtime(est.folder(sc.state, sc.year) / est.INPUTS_FILE), self._mtime(d / A.CONFAC_FILE))
        if key == self._key:
            return
        self._key = key
        self.rep = None
        if ml.empty:
            self.status.setText("No master list for this state + year.")
        elif not self._seasons():
            self.status.setText("Pick the report: Kharif or Rabi.")
        else:
            try:
                self.rep = A.build(sc.state, sc.year, ml, self._seasons())
                self.status.setText("")
            except Exception as e:                            # noqa: BLE001 – show it, keep the page usable
                self.status.setText(f"Could not read the RC-7: {e}")
        n_cy = len(self.rep.cy.rows) if self.rep else 0
        n_py = len(self.rep.py.rows) if self.rep and self.rep.py is not None else None
        self.k_cy.set(f"{n_cy:,}")
        self.k_py.set("–" if n_py is None else f"{n_py:,}")
        self.b_export.setEnabled(n_cy > 0)
        self._fill_confac()

    # ------------------------------------------------------------------ CONFAC
    def _fill_confac(self) -> None:
        t = self.conf_table
        t.blockSignals(True)
        self._conf_rows = A.confac_rows(self.rep) if self.rep is not None else []
        t.setRowCount(len(self._conf_rows))
        for r, row in enumerate(self._conf_rows):
            src = row["From"]
            where = A.CONFAC_SOURCES.get(src, src)
            if row["Missing"] and src:
                where += f" – {row['Missing']} schedule(s) without it"
            if row["Mixed"]:
                where += " – not the same in every schedule"
            vals = [row["Season"], row["Crop"], row["Sample"], f"{row['Harvested']:,}",
                    "" if row["CONFAC"] is None else str(row["CONFAC"]), where]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                editable = c == CONF and src != "rc7"
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                it.setFlags(flags | Qt.ItemFlag.ItemIsEditable if editable else flags)
                it.setBackground(MISSING if not src and c in (CONF, CONF + 1) else WHITE if editable else GREY)
                if c in (3, CONF):
                    it.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                if c == CONF:
                    it.setToolTip("In the RC-7 already (7. RC7) – change it there" if src == "rc7" else
                                  "Type the CONFAC (e.g. 1239 for CCF 0.1239); empty it to drop a typed value")
                t.setItem(r, c, it)
        t.blockSignals(False)
        fit_columns(t)
        t.horizontalHeader().setStretchLastSection(True)

    def _confac_typed(self, it) -> None:
        if it.column() != CONF or it.row() >= len(self._conf_rows):
            return
        row = self._conf_rows[it.row()]
        text = it.text().strip().replace(",", "")
        if text and not text.isdigit():
            QtWidgets.QMessageBox.warning(self, "CONFAC", "Type a whole number, e.g. 1239 (= CCF 0.1239 × 10,000).")
            self._fill_confac()
            return
        try:
            A.save_confac(self.scope.state, self.scope.year, row["KEY"], int(text) if text else None)
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"Could not keep the CONFAC:\n\n{e}")
            return
        toast(self, f"CONFAC {row['Crop']} {row['Sample']}: "
              + (f"{int(text):,} saved." if text else "typed value removed."))
        self._key = None
        QtCore.QTimer.singleShot(0, self.refresh)

    # ------------------------------------------------------------------ previous year
    def load_previous(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        py = er.previous_year(sc.year, 1)
        paths = self.win.pick_files(f"Previous year ({py}) RC-7 for {sc.state.title()}", RC7_FILTER)
        if not paths:
            return
        path = paths[0]
        try:
            df = A.read_rc7_file(path)
        except Exception as e:                                # noqa: BLE001 – tell the user what was wrong
            QtWidgets.QMessageBox.warning(self, "Not an RC-7 file", str(e))
            return
        if "STAT" in df.columns and sc.code:
            mine = df["STAT"].map(A.code).map(lambda v: str(int(v)) if v.isdigit() else v) == str(int(sc.code))
            if mine.any():
                df = df[mine].reset_index(drop=True)
        seasons = df["SESON"].map(A.code).value_counts().sort_index()
        yrs = sorted(set(df["YR"].map(A.code))) if "YR" in df.columns else []
        msg = (f"{os.path.basename(path)}: {len(df):,} RC-7 record(s)\n\nSeasons: "
               + ", ".join(f"{s or '?'} ({n:,})" for s, n in seasons.items())
               + (f"\nYear code (YR): {', '.join(yrs)}" if yrs else "")
               + f"\n\nUse it as the previous year ({py}) of {sc.state.title()} {sc.year}?")
        if (A.prev_folder(sc.state, sc.year) / A.PREV_FILE).exists():
            msg += "\n\nIt replaces the file loaded before (kept in 05_backup)."
        if schedules.rc7(sc.state, py).shape[0]:
            msg += (f"\n\nNote: the app already has its own RC-7 of {py}, and that is used first. The file is kept "
                    f"and used only if the app's {py} data is removed.")
        if QtWidgets.QMessageBox.question(self, "Load previous year RC-7", msg) != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            raw = RAW / F.ANNEXURES / sc.state / sc.year
            raw.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, raw / f"{datetime.now():%Y-%m-%d_%H%M%S}_{os.path.basename(path)}")
            A.save_previous(sc.state, sc.year, df)
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"Could not keep the file:\n\n{e}")
            return
        toast(self, f"Previous year loaded: {len(df):,} RC-7 records.")
        self._key = None
        self.refresh()

    def remove_previous(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        if not (A.prev_folder(sc.state, sc.year) / A.PREV_FILE).exists():
            toast(self, "No previous-year file is loaded.")
            return
        if QtWidgets.QMessageBox.question(self, "Remove the loaded file",
                                          "Stop using the loaded previous-year RC-7? (It is moved to 05_backup.)") \
                != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        A.remove_previous(sc.state, sc.year)
        self._key = None
        self.refresh()

    # ------------------------------------------------------------------ export
    def _ask_languages(self) -> list[str] | None:
        """Which annexure workbooks to make: English / Hindi / Bilingual (any of them). None = cancelled."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export")
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.addWidget(label("Make the annexures (XIX – XXIV) in:", "h3"))
        boxes = {}
        for code_, name in (("Eng", "English  –  1Annexures(Eng).xlsx"), ("Hi", "Hindi  –  1Annexures(Hi).xlsx"),
                            ("Bi", "Bilingual  –  1Annexures(Bi).xlsx")):
            cb = QtWidgets.QCheckBox(name)
            cb.setChecked(code_ in self._langs)
            lay.addWidget(cb)
            boxes[code_] = cb
        many = len(self.rep.seasons) > 2
        if many:
            lay.addWidget(label("The old annexure books have room for two seasons – with "
                                f"{len(self.rep.seasons)} seasons ticked only the Y-tables are made.", "muted"))
            for cb in boxes.values():
                cb.setEnabled(False)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        self._langs = [c for c, cb in boxes.items() if cb.isChecked()]
        return [] if many else list(self._langs)

    def export(self) -> None:
        if self.rep is None:
            return
        langs = self._ask_languages()
        if langs is None:
            return
        ml = master_list(self.scope, all_seasons=True)
        hi = str(ml["HSTATENAME"].iloc[0]).strip() if len(ml) and "HSTATENAME" in ml else ""
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            made = X.export(self.rep, hi, self.scope.code, langs)
        except (OSError, ValueError) as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.warning(self, "Export failed", "Could not write the workbooks (is one of them "
                                          f"open in Excel?):\n\n{e}")
            return
        QtWidgets.QApplication.restoreOverrideCursor()
        links = "  ·  ".join(f'<a href="{f.resolve()}">{f.name}</a>' for f in made)
        self.made_lb.setText(f"<b>Made just now</b> (click to open): {links}  ·  "
                             f'<a href="{made[0].parent.resolve()}">open the folder</a>')
        toast(self, f"Saved {len(made)} workbook(s).")
