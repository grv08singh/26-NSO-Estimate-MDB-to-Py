"""6. Estimate Report — the "Combined & Pooled" tab (components/c06_estimatereport_pooled.py): the office's two
workbooks (01 Central.xlsx, 02 State.xlsx) in the app.

The crop chosen in the work page's lists gives the crop group (e.g. 0611 MAIZE_UI + 0612 MAIZE_IR). Left: the
figures – yield, variance and area of both strata for Central and State, planned / analysed, previous year, CES,
the Hindi names – filled from the app where it has them (tinted), typed otherwise. Right: the results, worked out as
you type – Combined (Central), Combined (State), Pooled, each with its T-tests, and the Confidential Sheets.
Save keeps the typed figures; Export writes the office's workbook (six sheets, live formulas).
"""
from __future__ import annotations

import os

import pandas as pd

from src.components import c06_estimatereport as er
from src.components import c06_estimatereport_pooled as pr

from .look import Table, button, fit_columns, label, toast
from .page_estimates import NUM, _box, _fmt
from .qt import QtGui, QtWidgets, Qt

AUTO = "#EEF5EA"                              # filled from the app
SIGNIFICANT = QtGui.QColor("#ffc7ce")
RESULT = QtGui.QColor("#EEF1F4")
SIGNED = r"-?\d*(\.\d*)?"


def _show(table: Table, df: pd.DataFrame, bg=None) -> None:
    rows = [[_fmt(v) if not isinstance(v, str) else v for v in rec] for rec in df.itertuples(index=False)]
    table.set([str(c) for c in df.columns], rows, bg)
    fit_columns(table)
    _fit_height(table)


def _fit_height(table: Table) -> None:
    """Just tall enough for its rows (and a horizontal scroll bar when the columns are wider than the tab)."""
    h = table.horizontalHeader().sizeHint().height() + table.verticalHeader().length() + 2 * table.frameWidth()
    table.setFixedHeight(h + table.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent) + 2)


def _small(table: Table, rows: int) -> Table:
    """A small results table: no sorting, no row numbers, no scrolling inside the tab."""
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setFixedHeight(table.horizontalHeader().sizeHint().height() + 26 * rows + 24)
    return table


def _hindi(*widgets) -> None:
    for w in widgets:
        f = QtGui.QFont("Nirmala UI")                          # Devanagari
        f.setPointSizeF(w.font().pointSizeF())
        f.setBold(w.font().bold())
        w.setFont(f)


class PooledPanel(QtWidgets.QWidget):
    """The tab. The page calls refresh(state, year, season, crop)."""

    def __init__(self, page) -> None:
        super().__init__()
        self.page = page
        self.rep: pr.PooledReport | None = None
        self._key = None
        self._filling = False
        self._dirty = False
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 4)
        lay.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self.title = label("", "h3")
        _hindi(self.title)
        top.addWidget(self.title, 1)
        self.b_save = button("Save figures", icon="SP_DialogApplyButton",
                             tip="Keep the typed figures of this crop (Central, State, previous year, CES, names)")
        self.b_save.clicked.connect(self.save)
        self.b_export = button("Export workbook", primary=True, icon="SP_DialogSaveButton",
                               tip="The office's workbook: comb('c), conf('C), comb('S), conf('S), pool(p), conf('P) "
                                   "with live formulas, in Pooled/<CROP>/<date>/")
        self.b_export.clicked.connect(self.export)
        top.addWidget(self.b_save)
        top.addWidget(self.b_export)
        lay.addLayout(top)
        self.status = label("", "muted")
        lay.addWidget(self.status)

        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        lay.addWidget(split, 1)

        # ---------------- left: the figures
        form = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(form)
        g.setContentsMargins(0, 0, 8, 0)
        g.setVerticalSpacing(5)
        g.setHorizontalSpacing(8)
        self.fields: dict[str, QtWidgets.QLineEdit] = {}
        self.stratum_heads: list[QtWidgets.QLabel] = []
        self.r = 0

        def head(text):
            g.addWidget(label(text, "h3"), self.r, 0, 1, 3)
            self.r += 1

        def pair(text, key, rule=NUM, hint=""):
            g.addWidget(QtWidgets.QLabel(text), self.r, 0)
            for col, (s, _) in enumerate(pr.SAMPLES, 1):
                b = self._field(f"{key} {s}", 110, rule, hint)
                g.addWidget(b, self.r, col)
            self.r += 1

        def one(text, key, rule=NUM, hint="", width=226):
            g.addWidget(QtWidgets.QLabel(text), self.r, 0)
            b = self._field(key, width, rule, hint, right=rule != "")
            g.addWidget(b, self.r, 1, 1, 2)
            self.r += 1
            return b

        g.addWidget(label("", "muted"), self.r, 0)
        for col, (_, name) in enumerate(pr.SAMPLES, 1):
            g.addWidget(label(name, "h3", wrap=False), self.r, col)
        self.r += 1
        for i in (1, 2):
            lab = label(f"Stratum {i}", "h3")
            self.stratum_heads.append(lab)
            g.addWidget(lab, self.r, 0, 1, 3)
            self.r += 1
            pair(f"Yield rate (Y{i}), kg/ha", f"Y{i}")
            pair(f"Variance (V{i})", f"V{i}")
            pair(f"Area (A{i}), ha", f"A{i}")
        head("Experiments")
        pair("Planned", "PLANNED", r"\d*")
        pair("Analysed", "ANALYSED", r"\d*")
        self.prev_head = label("Previous year", "h3")
        g.addWidget(self.prev_head, self.r, 0, 1, 3)
        self.r += 1
        pair("Yield (kg/ha)", "PREV YIELD")
        pair("Variance", "PREV VARIANCE")
        one("Pooled yield (kg/ha)", "PREV POOLED YIELD")
        one("Pooled variance", "PREV POOLED VARIANCE")
        head("CES (General Crop Estimation Survey)")
        one("CES yield (kg/ha)", "CES YIELD")
        one("CES %SE", "CES %SE")
        one("CES reference year", "CES YEAR", "", "e.g. 2023-24")
        head("On the sheets")
        _hindi(one("State (Hindi)", "STATE HI", ""), one("Season (Hindi)", "SEASON HI", ""),
               one("Crop (Hindi)", "CROP HI", ""))
        one("Stratum 1 heading", "LABEL 1", "", "e.g. UNIRRIGATED")
        one("Stratum 2 heading", "LABEL 2", "", "e.g. IRRIGATED")
        _hindi(one("Prepared by", "PREPARED BY", ""))
        one("Letter date (दिनांक)", "LETTER DATE", "", "dd.mm.yyyy")
        g.addWidget(label("Tinted = filled from the app (5. Estimates, master list, last year); type to change it. "
                          "One stratum only (e.g. paddy): stratum 2 is 0.", "muted"), self.r, 0, 1, 3)
        g.setRowStretch(self.r + 1, 1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(form)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(320)
        split.addWidget(scroll)
        self._form = form

        # ---------------- right: the results
        self.results = QtWidgets.QTabWidget()
        self.results.setDocumentMode(True)
        self.comb: dict[str, tuple[Table, Table, Table, QtWidgets.QLabel]] = {}
        for s, name in pr.SAMPLES:
            w, parts = self._result_page(f"Combined estimate – {name} sample (Intermediate Table 4)", 3, 2)
            self.comb[s] = parts
            self.results.addTab(w, f"Combined – {name}")
        w, self.pool_parts = self._result_page("Pooled estimate – Central + State", 2, 3)
        self.results.addTab(w, "Pooled")
        conf = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(conf)
        cl.setContentsMargins(4, 8, 4, 4)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(label("Sheet", "muted", wrap=False))
        self.conf_pick = QtWidgets.QComboBox()
        self.conf_pick.addItems(["conf('C) – Central", "conf('S) – State", "conf('P) – Central, State, Pooled"])
        self.conf_pick.setCurrentIndex(2)
        self.conf_pick.currentIndexChanged.connect(lambda _: self._show_conf())
        row.addWidget(self.conf_pick)
        row.addStretch(1)
        cl.addLayout(row)
        self.conf_head = label("", "h3")
        self.conf_view = _small(Table(105), 3)
        self.conf_ref = label("", "muted")
        _hindi(self.conf_head, self.conf_view, self.conf_view.horizontalHeader(), self.conf_ref)
        cl.addWidget(self.conf_head)
        cl.addWidget(label("फसल सांख्यिकी सुधार योजना के अंतर्गत फसल कटाई प्रयोग के प्रतिदर्श जांच पर आधारित अनुमानित "
                           "उपज दर (कि.ग्राम/हैकटेयर) – कोष्ठक में मानक त्रुटि (%); * = अन्तर गण्य", "muted"))
        cl.addWidget(self.conf_view)
        cl.addWidget(self.conf_ref)
        cl.addStretch(1)
        self.results.addTab(conf, "Confidential Sheet")
        split.addWidget(self.results)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([form.sizeHint().width() + 24, 900])      # the whole form (both samples) visible
        self._enable(False)

    # ------------------------------------------------------------------ building blocks
    def _field(self, key, width, rule, hint, right=True) -> QtWidgets.QLineEdit:
        b = _box(width, rule, hint, right=right)
        b.textEdited.connect(self._edited)
        self.fields[key] = b
        return b

    def _result_page(self, title: str, input_rows: int, tests: int):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 4)
        v.setSpacing(6)
        v.addWidget(label(title, "h3"))
        inputs = _small(Table(120), input_rows)
        steps = _small(Table(120), 4)
        tt = _small(Table(95), tests)
        note = label("", "muted")
        v.addWidget(inputs)
        v.addWidget(steps)
        v.addWidget(label("T-test  (t = |Y1 − Y2| ÷ √(V1 + V2); significant when t > 1.96; CES variance = "
                          "(CES yield × CES %SE ÷ 100)²)", "muted"))
        v.addWidget(tt)
        v.addWidget(note)
        v.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(w)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        return scroll, (inputs, steps, tt, note)

    def _enable(self, on: bool) -> None:
        for w in (self.b_save, self.b_export, *self.fields.values()):
            w.setEnabled(on)

    # ------------------------------------------------------------------ refresh
    def refresh(self, state: str, year: str, season: str | None, crop: str) -> None:
        key = (state, year, season, crop, pr.stamp(state, year) if state and year else ())
        if key == self._key:
            return
        new_group = self._key is None or key[:4] != self._key[:4]
        if self._dirty and self.rep is not None and new_group:
            if QtWidgets.QMessageBox.question(
                    self, "Not saved", f"The figures typed for {self.rep.names['crop']} (Combined & Pooled) are not "
                    "saved. Save them now? (No = discard them)") == QtWidgets.QMessageBox.StandardButton.Yes:
                self.save(quiet=True)
                key = key[:4] + ((pr.stamp(state, year)),)
        self._key, self._dirty = key, False
        self.rep = None
        if not crop:
            msg = "Choose a crop in the Crop list above: its Central and State estimates are combined and pooled here."
        elif not season:
            msg = "This crop is in more than one season: choose the season too."
        else:
            self.rep = pr.build(state, year, season, crop)
            msg = "" if self.rep is not None else "This crop is not in the master list of the chosen season."
        self._fill(msg)

    def _fill(self, msg: str = "") -> None:
        rep = self.rep
        self._enable(rep is not None)
        self._filling = True
        for b in self.fields.values():
            b.clear()
            b.setStyleSheet("")
        self._filling = False
        if rep is None:
            self.title.setText("")
            self.status.setText(msg)
            for parts in (*self.comb.values(), self.pool_parts):
                for t in parts[:3]:
                    t.set([], [])
                parts[3].setText("")
            self.conf_view.set([], [])
            self.conf_head.setText("")
            self.conf_ref.setText("")
            return
        nm, g = rep.names, rep.group
        parts = " + ".join(f"{c} {n}" for c, n in zip(g.codes, nm["crops"]))
        self.title.setText(f"{nm['crop']} · {str(nm['season']).title()} · {rep.year}   ({parts})")
        for i, lab in enumerate(self.stratum_heads):
            code = g.codes[i] if i < len(g.codes) else ""
            lab.setText(f"Stratum {i + 1}: {nm['labels'][i]} ({code})" if code else
                        f"Stratum {i + 1}: none (one crop code) – left at 0")
        self.prev_head.setText(f"Previous year ({er.previous_year(rep.year)})")
        self._filling = True
        for k, b in self.fields.items():
            b.setText(rep.value(k))
        self._filling = False
        bits = []
        if rep.warning:
            bits.append(rep.warning)
        missing = [name for s, name in pr.SAMPLES for i in range(1, len(g.codes) + 1)
                   if not rep.auto.get(f"Y{i} {s}")]
        if missing:
            bits.append("No saved estimate in 5. Estimates for some strata (" + ", ".join(sorted(set(missing))) +
                        ") – work them out there, or type the figures.")
        bits.append(f"Previous year from the app: {rep.prev_auto_from}." if rep.prev_auto_from else
                    f"Previous year ({er.previous_year(rep.year)}) is not worked out in the app – type its figures.")
        self.status.setText("  ".join(bits))
        self._paint()
        self._show_results()

    def _paint(self) -> None:
        rep = self.rep
        for k, b in self.fields.items():
            auto = rep.auto.get(k, "")
            from_app = bool(auto) and b.text().strip() == auto
            b.setStyleSheet(f"QLineEdit {{ background: {AUTO}; }}" if from_app else "")
            b.setToolTip("From the app; type to change" if from_app else "")

    # ------------------------------------------------------------------ typing
    def _typed(self) -> dict[str, str]:
        rep = self.rep
        vals = {k: b.text().strip() for k, b in self.fields.items()}
        return {k: v for k, v in vals.items() if v and v != rep.auto.get(k, "")}

    def _edited(self, *_) -> None:
        if self._filling or self.rep is None:
            return
        self._dirty = True
        self.rep.typed = self._typed()
        self._paint()
        self._show_results()

    # ------------------------------------------------------------------ results
    def _show_results(self) -> None:
        rep = self.rep
        sig = lambda df: (lambda r, c: SIGNIFICANT if df.iloc[r]["Result"] == "Significant" else None)  # noqa: E731
        for s, name in pr.SAMPLES:
            inputs, steps, tt, note = self.comb[s]
            c = rep.combined(s)
            _show(inputs, pr.combined_table(rep, s), lambda r, col: RESULT if r == 2 else None)
            _show(steps, pr.steps_table(c.yc, c.vc, c.se, c.pct_se, "combined"))
            df = pr.tests_table(rep.tests(s))
            _show(tt, df, sig(df))
            note.setText(f"Not worked out: {c.problem}." if c.problem else "")
        inputs, steps, tt, note = self.pool_parts
        c, s, p = rep.combined("1"), rep.combined("2"), rep.pooled
        _show(inputs, pd.DataFrame([{"": "Central (1)", "Yield rate (kg/ha)": pr._f(c.yc), "Variance": pr._f(c.vc)},
                                    {"": "State (2)", "Yield rate (kg/ha)": pr._f(s.yc), "Variance": pr._f(s.vc)}]))
        _show(steps, pr.steps_table(p.yp, p.vp, p.se, p.pct_se, "pooled"))
        df = pr.tests_table(rep.pooled_tests())
        _show(tt, df, sig(df))
        note.setText(f"Not worked out: {p.problem}." if p.problem else "")
        self._show_conf()

    def _show_conf(self) -> None:
        rep = self.rep
        if rep is None:
            return
        which = [["Central"], ["State"], ["Central", "State", "Pooled"]][self.conf_pick.currentIndex()]
        self.conf_head.setText(f"राज्य: {rep.value('STATE HI')}   ·   वर्ष: {rep.year}   ·   मौसम: "
                               f"{rep.value('SEASON HI')}   ·   फसल: {rep.value('CROP HI')}   ·   पिछला वर्ष: "
                               f"{er.previous_year(rep.year)}   ·   जी.सी.ई.एस. वर्ष: {rep.value('CES YEAR') or '–'}")
        _show(self.conf_view, pr.conf_table(rep, which))
        self.conf_ref.setText(f"{rep.letter_ref}        दिनांक : {rep.value('LETTER DATE')}")

    # ------------------------------------------------------------------ save / export
    def save(self, quiet: bool = False) -> bool:
        rep = self.rep
        if rep is None:
            return False
        try:
            pr.save_typed(rep.state, rep.year, rep.group, rep.names["crop"], self._typed())
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"The figures could not be saved:\n\n{e}")
            return False
        self._dirty = False
        self._key = self._key[:4] + (pr.stamp(rep.state, rep.year),)
        if not quiet:
            toast(self, "Saved.")
        return True

    def export(self) -> None:
        rep = self.rep
        if rep is None or not self.save(quiet=True):
            return
        c, s = rep.combined("1"), rep.combined("2")
        if c.yc is None and s.yc is None:
            QtWidgets.QMessageBox.information(self, "Nothing to export",
                                              "Neither the Central nor the State estimate can be worked out yet: "
                                              "yield, variance and area of each stratum are needed.")
            return
        try:
            out = pr.export(rep)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the Excel file:\n\n{e}")
            return
        toast(self, f"Exported {out.name}")
        os.startfile(str(out.resolve().parent))                   # noqa: S606 (Windows)
