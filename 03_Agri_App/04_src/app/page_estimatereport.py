"""6. Estimate Report page — the sheets that go out with an estimate (components/c06_estimatereport.py):
Information Accompanying, T-test and the Hindi Confidential Sheet.

Crop / season at the top and Central / State / Combined as in 5. Estimates; the estimate is the one saved there.
Previous-year figures are filled from the app when last year is in it (tinted); typing over a value keeps the typed
one. Save keeps the typed figures; Export writes one Excel workbook (the three sheets).
"""
from __future__ import annotations

import os

from src.components import c05_estimates as est
from src.components import c06_estimatereport as er
from src.components import c06_estimatereport_excel as excel
from src.utils import folders as F
from src.utils import schedules

from .look import fit_columns, Table, button, label, toast
from .page_estimatereport_pooled import PooledPanel
from .page_estimates import NUM, SamplePicker, _box, _fmt, _show, _validator
from .qt import QtGui, QtWidgets, Qt
from .window import ART, StepTab

AUTO = "#EEF5EA"                      # filled from the app
AUTO_BRUSH = QtGui.QBrush(QtGui.QColor(AUTO))
WHITE = QtGui.QBrush(QtGui.QColor("#ffffff"))
GREY = QtGui.QBrush(QtGui.QColor("#eef1f4"))
GROUPS = [("Receipt of schedules", er.RECEIPT), ("Green yield per plot (grams)", er.CLASSES),
          ("Ancillary information", er.ANCILLARY), ("Crop condition", er.CONDITION),
          ("Reasons for crop damage / below normal", er.REASONS)]
CONF_HEADS = ["(1) एजेंसी", "(2) चालू वर्ष", "(3) पिछला वर्ष", "(4) जी.सी.ई.एस.", "(5) % अंतर (3)", "(6) % अंतर (4)",
              "(7) नियोजित", "(8) विश्लेषित", "(9) % प्रत्युत्तर"]


class _CountEdit(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        e = QtWidgets.QLineEdit(parent)
        e.setValidator(_validator(r"\d*"))
        return e


class EstimateReportTab(SamplePicker, StepTab):
    number, title, tab = 6, "Estimate Report", "Estimate Report"

    @property
    def folder(self):                       # 02_artifacts/06_estimatereport/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.ESTIMATE_REPORT / sc.state / sc.year if sc.ok else ART / F.ESTIMATE_REPORT

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self.rep: er.Report | None = None
        self.sel: est.Selection | None = None
        self._key = None
        self._filling = False
        self._dirty = False
        self._build_sample_picker()
        self.b_save = button("Save", icon="SP_DialogApplyButton", tip="Keep the typed figures of this estimate")
        self.b_save.clicked.connect(self.save)
        self.add_action(self.b_save)
        self.b_export = button("Export", icon="SP_DialogSaveButton",
                               tip="One Excel workbook: Information Accompanying, T-test, Confidential Sheet, in "
                                   "<sample>/<VARIETY>/<date>/")
        self.b_export.clicked.connect(self.export)
        self.add_action(self.b_export)
        self.k = {name: self.kpi(name) for name in ("yield (kg/ha)", "%SE", "previous yield", "CES yield",
                                                    "planned", "analysed")}

        # --- Information Accompanying: the counts (current / previous) and the typed figures
        info = QtWidgets.QWidget()
        il = QtWidgets.QHBoxLayout(info)
        il.setContentsMargins(4, 8, 4, 4)
        il.setSpacing(16)
        self.grid = QtWidgets.QTableWidget(0, 3)
        self.grid.setHorizontalHeaderLabels(["", "Current year", "Previous year"])
        self.grid.verticalHeader().setVisible(False)
        self.grid.verticalHeader().setDefaultSectionSize(23)
        self.grid.setItemDelegate(_CountEdit(self.grid))
        T = QtWidgets.QAbstractItemView.EditTrigger
        self.grid.setEditTriggers(T.CurrentChanged | T.SelectedClicked | T.AnyKeyPressed | T.DoubleClicked)
        self.grid.itemChanged.connect(self._grid_edited)
        self.grid.setMinimumWidth(260)
        il.addWidget(self.grid, 1)
        right = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(right)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(6)
        self.fields: dict[str, QtWidgets.QLineEdit] = {}
        r = 0

        def field(key, text, width=120, rule=NUM, hint=""):
            nonlocal r
            g.addWidget(QtWidgets.QLabel(text), r, 0)
            b = _box(width, rule, hint, right=rule == NUM)
            b.textEdited.connect(self._edited)
            g.addWidget(b, r, 1, 1, 2)
            self.fields[key] = b
            r += 1

        g.addWidget(label("CES and previous year", "h3"), r, 0, 1, 3)
        r += 1
        field("CES YIELD", "CES yield (kg/ha)")
        field("CES %SE", "CES %SE")
        field("CES YEAR", "CES year", rule="", hint="e.g. 2024-25")
        field("PREVIOUS YIELD", "Previous year yield")
        field("PREVIOUS VARIANCE", "Previous year variance")
        g.addWidget(label("Details on yield rate (kg/ha) – saved in yield_history.csv", "h3"), r, 0, 1, 3)
        r += 1
        for c, t in enumerate(("Year", "ICS yield · %SE", "CES yield · %SE")):
            g.addWidget(label(t, "muted", wrap=False), r, c)
        r += 1
        self.year_labels = []
        for i in range(1, er.YEARS_BACK + 1):
            lab = QtWidgets.QLabel("")
            self.year_labels.append(lab)
            g.addWidget(lab, r, 0)
            for c, kind in ((1, "ICS"), (2, "CES")):
                pair = QtWidgets.QWidget()
                pl = QtWidgets.QHBoxLayout(pair)
                pl.setContentsMargins(0, 0, 0, 0)
                pl.setSpacing(4)
                for k, w, hint in ((f"{kind} {i}", 72, "yield"), (f"{kind} SE {i}", 52, "%SE")):
                    b = _box(w, NUM, hint)
                    b.textEdited.connect(self._edited)
                    self.fields[k] = b
                    pl.addWidget(b)
                g.addWidget(pair, r, c)
            r += 1
        g.addWidget(label("Submission", "h3"), r, 0, 1, 3)
        r += 1
        field("DUE DATE", "Due date", rule="", hint="dd.mm.yyyy")
        field("SUBMISSION DATE", "Date of submission", rule="", hint="dd.mm.yyyy")
        g.addWidget(label("Tinted = filled from the app; type to change it.", "muted"), r, 0, 1, 3)
        g.setRowStretch(r + 1, 1)
        scroll = QtWidgets.QScrollArea()                   # the typed figures scroll on a small screen
        scroll.setWidget(right)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(260)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        il.addWidget(scroll, 1)

        self.tt_view = Table(130)
        conf = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(conf)
        cl.setContentsMargins(4, 8, 4, 4)
        self.conf_title = label("", "h3")
        cl.addWidget(self.conf_title)
        self.conf_view = Table(110)
        hindi = QtGui.QFont("Nirmala UI")                   # Devanagari
        for w in (self.conf_title, self.conf_view, self.conf_view.horizontalHeader()):
            hindi.setPointSizeF(w.font().pointSizeF())
            hindi.setBold(w.font().bold())
            w.setFont(hindi)
        cl.addWidget(self.conf_view, 1)
        for w, name in ((info, "Information Accompanying"), (self.tt_view, "T-test"), (conf, "Confidential Sheet")):
            self.body.addTab(w, name)
        # the office's Central / State / Pooled workbooks: both samples of the crop, so the Sample choice is not used
        self.pooled = PooledPanel(self)
        self.body.addTab(self.pooled, "Combined && Pooled")
        self.body.currentChanged.connect(self._tab_changed)
        self._enable(False)

    def _tab_changed(self, _i: int) -> None:
        """Save / Export in the header are for the per-estimate sheets; the Combined & Pooled tab has its own."""
        on_pooled = self.body.currentWidget() is self.pooled
        for b in (self.b_save, self.b_export):
            b.setVisible(not on_pooled)

    # ------------------------------------------------------------------ refresh
    def _stamps(self) -> tuple:
        sc = self.scope
        files = [est.folder(sc.state, sc.year) / est.INPUTS_FILE, est.folder(sc.state, sc.year) / est.AREAS_FILE,
                 er.folder(sc.state, sc.year) / er.INPUTS_FILE, er.folder(sc.state, sc.year) / er.HISTORY_FILE,
                 *(er.folder(sc.state, er.previous_year(sc.year, i)) / er.HISTORY_FILE
                   for i in range(1, er.YEARS_BACK + 1))]
        return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files)

    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        self.pooled.refresh(sc.state, sc.year, self._season(), sc.crop)
        sel = self._selection()
        key = (sc.state, sc.year, sel, schedules.stamp(sc.state, sc.year), self._stamps())
        if key == self._key:
            return
        if self._dirty and self.rep is not None and sel != self.sel:
            if QtWidgets.QMessageBox.question(
                    self, "Not saved", "The figures typed for the estimate shown before are not saved. Save them now? "
                    "(No = discard them)") == QtWidgets.QMessageBox.StandardButton.Yes:
                er.save_typed(sc.state, sc.year, self.sel, self._typed(), er.history_values(self.rep),
                              self.rep.nm["crop"])
                key = key[:4] + (self._stamps(),)
        self._key, self._dirty, self.sel = key, False, sel
        self.rep = er.build(sc.state, sc.year, sel) if sel is not None else None
        if sel is not None and self.rep is None:
            self.status.setText("No saved estimate for this selection – work it out and save it in 5. Estimates "
                                "first.")
        self._fill()

    def _fill(self) -> None:
        rep = self.rep
        self._enable(rep is not None)
        self._filling = True
        self.grid.setRowCount(0)
        for b in self.fields.values():
            b.clear()
            b.setStyleSheet("")
        for k in self.k.values():
            k.set("–")
        for t in (self.tt_view, self.conf_view):
            t.set([], [])
        self.conf_title.setText("")
        if rep is None:
            self._filling = False
            return
        prev = er.previous_year(rep.year)
        for i, lab in enumerate(self.year_labels, 1):
            lab.setText(er.previous_year(rep.year, i))
        self.grid.setHorizontalHeaderLabels(["", f"Current ({rep.year})", f"Previous ({prev})"])
        bold = QtGui.QFont()
        bold.setBold(True)
        for title, items in GROUPS:
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            head = QtWidgets.QTableWidgetItem(title)
            head.setFont(bold)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.grid.setItem(r, 0, head)
            self.grid.setSpan(r, 0, 1, 3)
            for c in items:
                r = self.grid.rowCount()
                self.grid.insertRow(r)
                lab = QtWidgets.QTableWidgetItem(er.LABELS[c] if c not in er.CLASSES else
                                                 er.CLASS_HEADS[er.CLASSES.index(c)])
                lab.setData(Qt.ItemDataRole.UserRole, c)
                lab.setFlags(Qt.ItemFlag.ItemIsEnabled)
                cur = QtWidgets.QTableWidgetItem(_fmt(rep.now.counts.get(c)))
                cur.setFlags(Qt.ItemFlag.ItemIsEnabled)
                cur.setBackground(GREY)
                pv = QtWidgets.QTableWidgetItem(rep.value(f"PREV {c}"))
                pv.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
                for it in (cur, pv):
                    it.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                for col, it in enumerate((lab, cur, pv)):
                    self.grid.setItem(r, col, it)
        fit_columns(self.grid)
        self.grid.horizontalHeader().setStretchLastSection(True)
        for k, b in self.fields.items():
            b.setText(rep.value(k))
        self._filling = False
        self._paint()
        self._show_results()
        self.status.setText((f"Previous year ({prev}) filled from the app – check it" if rep.prev is not None else
                             f"Previous year ({prev}) is not in the app – type its figures") +
                            f"  ·  ID {rep.ident}")

    def _paint(self) -> None:
        """Tint the values that come from the app (unchanged); white once typed."""
        rep = self.rep
        if rep is None:
            return
        self._filling = True
        for r in range(self.grid.rowCount()):
            lab = self.grid.item(r, 0)
            c = lab.data(Qt.ItemDataRole.UserRole) if lab else None
            if not c:
                continue
            it = self.grid.item(r, 2)
            auto = rep.auto.get(f"PREV {c}", "")
            from_app = bool(auto) and it.text().strip() == auto
            it.setBackground(AUTO_BRUSH if from_app else WHITE)
            it.setToolTip(f"From the app ({er.previous_year(rep.year)} data); type to change" if from_app else "")
        for k, b in self.fields.items():
            auto = rep.auto.get(k, "")
            from_app = bool(auto) and b.text().strip() == auto
            b.setStyleSheet(f"QLineEdit {{ background: {AUTO}; }}" if from_app else "")
            b.setToolTip("From the app; type to change" if from_app else "")
        self._filling = False

    def _enable(self, on: bool) -> None:
        for w in (self.b_save, self.b_export, self.grid, *self.fields.values()):
            w.setEnabled(on)

    # ------------------------------------------------------------------ typed figures
    def _typed(self) -> dict[str, str]:
        """The values that differ from what the app fills (what the user typed)."""
        rep = self.rep
        vals = {k: b.text().strip() for k, b in self.fields.items()}
        for r in range(self.grid.rowCount()):
            lab = self.grid.item(r, 0)
            c = lab.data(Qt.ItemDataRole.UserRole) if lab else None
            if c:
                vals[f"PREV {c}"] = self.grid.item(r, 2).text().strip()
        return {k: v for k, v in vals.items() if v and v != rep.auto.get(k, "")}

    def _grid_edited(self, _item) -> None:
        if not self._filling:
            self._edited()

    def _edited(self, *_) -> None:
        if self._filling or self.rep is None:
            return
        self._dirty = True
        self.rep.typed = self._typed()
        self._paint()
        self._show_results()

    def _show_results(self) -> None:
        rep = self.rep
        res = rep.now.result
        self.k["yield (kg/ha)"].set(_fmt(res.yield_kg_ha))
        self.k["%SE"].set(_fmt(res.pct_se) if not isinstance(res.pct_se, str) else "n/a")
        self.k["previous yield"].set(rep.value("PREVIOUS YIELD") or "–")
        self.k["CES yield"].set(rep.value("CES YIELD") or "–")
        self.k["planned"].set(_fmt(rep.now.counts.get("PLANNED")))
        self.k["analysed"].set(_fmt(res.analysed))
        _show(self.tt_view, er.t_test_table(rep))
        row = er.confidential_row(rep)
        hi = er.hindi_names(rep)
        self.conf_title.setText(f"राज्य: {hi['state']}   ·   वर्ष: {rep.year}   ·   मौसम: {hi['season']}   ·   "
                                f"फसल: {hi['crop']}")
        keys = ["now", "prev", "ces", "diff_prev", "diff_ces", "planned", "analysed", "response"]
        rows = [[agency] + ([str(row[k]) for k in keys] if agency == row["agency"] else [""] * len(keys))
                for agency in ("केन्द्रीय", "राज्य", "सम्मिलित")]
        self.conf_view.set(CONF_HEADS, rows)
        fit_columns(self.conf_view)

    # ------------------------------------------------------------------ save / export
    def save(self) -> bool:
        sc = self.scope
        if self.rep is None:
            return False
        try:
            er.save_typed(sc.state, sc.year, self.sel, self._typed(), er.history_values(self.rep),
                          self.rep.nm["crop"])
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"The figures could not be saved:\n\n{e}")
            return False
        self._dirty = False
        self._key = self._key[:4] + (self._stamps(),)
        toast(self, "Saved.")
        return True

    def export(self) -> None:
        if self.rep is None or not self.save():
            return
        self.rep.typed = er.load_typed(self.scope.state, self.scope.year, self.sel)
        try:
            out = excel.export(self.rep)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the Excel file:\n\n{e}")
            return
        os.startfile(str(out.resolve().parent))                   # noqa: S606 (Windows)

