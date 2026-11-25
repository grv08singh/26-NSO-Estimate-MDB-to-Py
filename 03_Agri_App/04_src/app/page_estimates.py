"""5. Estimates page — the old ESTIMATE.accdb (components/c05_estimates.py) for the open state + year.

Crop (and season) come from the work page's dropdowns. Central / State / Combined: one of them. Combined shows two
choices below the counts, each "Crop code [typed] ☐ Central ☐ State" (choice 1 starts as the chosen crop); the
estimate pools both, e.g. 1611 State + 1612 State = 1600, or 1611 Central + 1611 State.
The tabs follow the office printout:
  Area Sheet       area and merge-into code per district (click a cell and type; Enter goes down), CF / driage /
                   recovery, prepared by -> Calculate & save (kept in 00_database/05_estimates/<STATE>/<YEAR>/)
  Intermediate Table, Variance (columns 1–14), (%) S.E., Compiled Data, Estimate BD (every planned plot)
  Export           one Excel workbook with those six sheets in <Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/
"""
from __future__ import annotations

import os

import pandas as pd

from src.components import c05_estimates as est
from src.components import c05_estimates_report as report
from src.utils import folders as F
from src.utils import schedules
from src.utils.config_loader import load_config

from .look import fit_columns, AutoLabel, Table, button, flow_box, label, toast
from .qt import QtCore, QtGui, QtWidgets, Qt
from .window import ART, C, DataView, StepTab, master_list

SHEET = ["District code", "District name", "Area", "Expt", "Merge dist code", "Merge district name"]
AREA, EXPT, MERGE, MNAME = 2, 3, 4, 5
MIN_EXPTS = est.MIN_EXPTS       # a district with fewer expts is shown in red (area sheet, here and in the workbook)
NUM = r"\d*(\.\d*)?"
GREY = QtGui.QBrush(QtGui.QColor("#eef1f4"))
WHITE = QtGui.QBrush(QtGui.QColor("#ffffff"))
RED = QtGui.QBrush(QtGui.QColor("#ffc7ce"))
TOTAL = QtGui.QColor("#EEF1F4")


def _validator(rule: str):
    return QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(rule))


def _box(width: int, rule: str = NUM, hint: str = "", right: bool = True) -> QtWidgets.QLineEdit:
    b = QtWidgets.QLineEdit()
    b.setFixedWidth(width)
    if rule:
        b.setValidator(_validator(rule))
    b.setPlaceholderText(hint)
    if right:
        b.setAlignment(Qt.AlignmentFlag.AlignRight)
    return b


def _fmt(v, nd: int | None = None) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, str):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if nd is not None:
        return f"{f:,.{nd}f}"
    return f"{f:,.0f}" if f.is_integer() else f"{f:,.6f}".rstrip("0").rstrip(".")


def _show(table: Table, df: pd.DataFrame, nd: dict | None = None) -> None:
    """A small read-only table; the TOTAL row grey."""
    nd = nd or {}
    rows = [[_fmt(v, nd.get(c)) for c, v in zip(df.columns, rec)] for rec in df.itertuples(index=False)]
    total = {i for i, r in enumerate(rows) if r and r[0] in (est.TOTAL_LABEL, est.WEIGHTED_LABEL)}
    table.set([str(c) for c in df.columns], rows, (lambda r, c: TOTAL if r in total else None))
    fit_columns(table)


class _SheetEdit(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        e = QtWidgets.QLineEdit(parent)
        e.setValidator(_validator(NUM if index.column() == AREA else r"\d{0,2}"))
        return e


class AreaSheet(QtWidgets.QTableWidget):
    """The area sheet: a click (or arrow key) on an Area / Merge cell starts typing there; Enter goes down a row."""

    def __init__(self) -> None:
        super().__init__(0, len(SHEET))
        T = QtWidgets.QAbstractItemView.EditTrigger
        self.setEditTriggers(T.CurrentChanged | T.SelectedClicked | T.AnyKeyPressed | T.EditKeyPressed
                             | T.DoubleClicked)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setItemDelegate(_SheetEdit(self))

    def closeEditor(self, editor, hint) -> None:
        H = QtWidgets.QAbstractItemDelegate.EndEditHint
        super().closeEditor(editor, H.NoHint if hint == H.SubmitModelCache else hint)
        if hint == H.SubmitModelCache:                       # Enter: the same column, next row
            r, c = self.currentRow() + 1, self.currentColumn()
            if r < self.rowCount():
                self.setCurrentCell(r, c)


class ChoiceRow(QtWidgets.QWidget):
    """One choice of a combined estimate: Crop code [typed] ☐ Central ☐ State, the crop's name shown."""

    def __init__(self, tab: "EstimatesTab") -> None:
        super().__init__()
        self.tab = tab
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(label("Crop code", "muted", wrap=False))
        self.code = _box(70, r"\d{0,4}", "crop", right=False)
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setToolTip("Crop code (4 digits) of the chosen season")
        self.central, self.state_s = QtWidgets.QCheckBox("Central"), QtWidgets.QCheckBox("State")
        self.name = label("", "muted", wrap=False)
        lay.addWidget(self.code)
        for cb in (self.central, self.state_s):
            lay.addWidget(cb)
            cb.toggled.connect(self._changed)
        lay.addWidget(self.name)
        lay.addStretch(1)
        self.code.textEdited.connect(self._changed)

    def crop(self) -> str | None:
        c = self.code.text().strip()
        return c if len(c) == 4 else None

    def samples(self) -> list[str]:
        return [code for cb, code in ((self.central, "1"), (self.state_s, "2")) if cb.isChecked()]

    def set(self, crop: str, samples: list[str]) -> None:
        self.code.setText(crop)
        for cb, code in ((self.central, "1"), (self.state_s, "2")):
            cb.blockSignals(True)
            cb.setChecked(code in samples)
            cb.blockSignals(False)
        self.show_name()

    def show_name(self) -> None:
        c = self.crop()
        self.name.setText(self.tab.crop_name(c, self.samples() or ["1", "2"]) if c else "")

    def _changed(self, *_):
        self.show_name()
        if self.crop() or not self.code.text():
            self.tab.refresh()


class SamplePicker:
    """Central / State / Combined (one at a time) in the header; Combined shows two choices below the counts, each
    "Crop code [typed] ☐ Central ☐ State". Used by 5. Estimates and 6. Estimate Report (the page needs .scope, .status,
    .actions and a refresh())."""

    def _build_sample_picker(self) -> None:
        pick = QtWidgets.QWidget()
        pl = QtWidgets.QHBoxLayout(pick)
        pl.setContentsMargins(0, 0, 8, 0)
        pl.addWidget(label("Sample", "muted", wrap=False))
        self.central = QtWidgets.QCheckBox("Central")
        self.state_s = QtWidgets.QCheckBox("State")
        self.combined = QtWidgets.QCheckBox("Combined")
        self.central.setChecked(True)
        self.central.setToolTip("Central sample (1)")
        self.state_s.setToolTip("State sample (2)")
        self.combined.setToolTip("Pool samples and / or other crops of the same season (e.g. 1611 + 1612 -> 1600)")
        self.sample_group = QtWidgets.QButtonGroup(self)          # one of the three at a time
        self.sample_group.setExclusive(True)
        for cb in (self.central, self.state_s, self.combined):
            self.sample_group.addButton(cb)
            pl.addWidget(cb)
        self.sample_group.buttonToggled.connect(self._sample_changed)
        self.actions.insertWidget(0, pick)

        # --- combined: two choices below the counts, each crop code + Central / State
        self.parts_box = QtWidgets.QWidget()
        pbl = QtWidgets.QVBoxLayout(self.parts_box)
        pbl.setContentsMargins(0, 0, 0, 0)
        pbl.setSpacing(4)
        self.choices = [ChoiceRow(self), ChoiceRow(self)]
        for row in self.choices:
            pbl.addWidget(row)
        self.parts_box.setVisible(False)
        self.status.parentWidget().layout().insertWidget(self.status.parentWidget().layout().count() - 1,
                                                         self.parts_box)

    # ------------------------------------------------------------------ selection
    def crop_name(self, crop: str, samples: list[str]) -> str:
        """Name of a crop code in the chosen season, with its planned count (the ticked samples)."""
        season = self._season()
        ml = master_list(self.scope, all_seasons=True)
        r = ml[(ml["SEASONCODE"] == season) & (ml["CROPCODE"] == crop) & ml["SAMPLE"].isin(samples)]
        if r.empty:
            return "not in this season / sample"
        return f"{r['CROPNAME'].iloc[0]} · {len(r)} planned"

    def _season(self) -> str | None:
        sc = self.scope
        if not sc.crop:
            return None
        if sc.season:
            return sc.season
        ml = master_list(sc, all_seasons=True)
        seasons = sorted(set(ml.loc[ml["CROPCODE"] == sc.crop, "SEASONCODE"]))
        return seasons[0] if len(seasons) == 1 else None

    def _selection(self) -> est.Selection | None:
        sc = self.scope
        if not sc.crop:
            self.status.setText("Choose a crop in the Crop list above; its estimate is worked out here.")
            return None
        season = self._season()
        if season is None:
            self.status.setText("This crop is in more than one season: choose the season too.")
            return None
        if self.combined.isChecked():
            parts = []
            for row in self.choices:
                if row.crop():
                    parts += [(season, smp, row.crop()) for smp in row.samples()
                              if (season, smp, row.crop()) not in parts]
            if len(parts) < 2:                        # nothing to pool yet: wait for the second choice
                self.status.setText("")
                return None
        else:
            parts = [(season, "1" if self.central.isChecked() else "2", sc.crop)]
        if len(parts) > est.MAX_PARTS:
            self.status.setText(f"At most {est.MAX_PARTS} parts can be pooled (crops × samples) – untick a sample or "
                                "clear a crop code.")
            return None
        self.status.setText("")
        return est.Selection(tuple(parts))

    def _sample_changed(self, button, on: bool) -> None:
        if not on:
            return
        combined = button is self.combined
        self.parts_box.setVisible(combined)
        if combined and not self.choices[0].crop() and self.scope.crop:     # choice 1 = the chosen crop
            self.choices[0].set(self.scope.crop, ["1"])
        self.refresh()


class EstimatesTab(SamplePicker, StepTab):
    number, title, tab = 5, "Estimates", "Estimates"

    @property
    def folder(self):                       # 02_artifacts/05_estimates/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.ESTIMATES / sc.state / sc.year if sc.ok else ART / F.ESTIMATES

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self.sel: est.Selection | None = None
        self.exps = self.base = pd.DataFrame()
        self.result: est.Result | None = None
        self.counts: dict = {}
        self.nm: dict = {}
        self._key = None
        self._status_base = ""
        self._info: dict = {}          # typed figures of the information sheet (a later module) – kept as saved
        self._filling = False
        self._dirty = False

        self._build_sample_picker()
        self.b_export = button("Export", icon="SP_DialogSaveButton",
                               tip="One Excel workbook, a sheet per table, in "
                                   "<sample>/<VARIETY>/<date>/")
        self.b_export.clicked.connect(self.export)
        self.add_action(self.b_export)

        self.k = {name: self.kpi(name) for name in ("yield (kg/ha)", "%SE", "SE (kg/ha)", "variance", "area",
                                                    "planned", "analysed")}
        self.k["analysed"].setToolTip("Harvested plots used in the estimate (STAGIN 1)")

        # --- area sheet
        sheet_tab = QtWidgets.QWidget()
        sl = QtWidgets.QVBoxLayout(sheet_tab)
        sl.setContentsMargins(4, 8, 4, 4)
        self.sheet = AreaSheet()
        self.sheet.setHorizontalHeaderLabels(SHEET)
        self.sheet.horizontalHeaderItem(AREA).setToolTip("Crop area of the district (as the office's area sheet)")
        self.sheet.horizontalHeaderItem(MERGE).setToolTip("Code of a district whose plots and area this row takes in "
                                                          "(mark that district 1); 1 = leave this district out")
        self.sheet.verticalHeader().setVisible(False)
        self.sheet.verticalHeader().setDefaultSectionSize(24)
        self.sheet.horizontalHeader().setStretchLastSection(True)
        self.sheet.itemChanged.connect(self._sheet_edited)
        self.sheet.setMinimumHeight(180)
        sl.addWidget(self.sheet, 1)
        fw, fl = flow_box(spacing=10)
        self.cf, self.driage, self.recovery = _box(90), _box(90), _box(90)
        self.prepared = _box(200, "", "name", right=False)
        for name, b in (("Conversion factor", self.cf), ("Driage ratio", self.driage),
                        ("Recovery ratio", self.recovery), ("Prepared by", self.prepared)):
            cell = QtWidgets.QWidget()
            cl = QtWidgets.QHBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.addWidget(QtWidgets.QLabel(name))
            cl.addWidget(b)
            b.textEdited.connect(self._edited)
            fl.addWidget(cell)
        sl.addWidget(fw)
        self.sheet_note = AutoLabel("")
        self.sheet_note.setObjectName("muted")
        self.sheet_note.setWordWrap(True)
        self.sheet_note.setVisible(False)
        sl.addWidget(self.sheet_note)
        bw, bl = flow_box(spacing=8)
        self.b_copy = button("Copy from the other sample",
                             tip="Fill the areas, merges and factors saved for the same crop's other sample")
        self.b_copy.clicked.connect(self.copy_other)
        self.b_calc = button("Calculate && save", primary=True, icon="SP_DialogApplyButton",
                             tip="Work out the estimate and keep this area sheet for this selection")
        self.b_calc.clicked.connect(lambda: self.calculate(save=True))
        bl.addWidget(self.b_copy)
        bl.addWidget(self.b_calc)
        sl.addWidget(bw)

        # --- the sheets of the office printout: Intermediate table, Variance, (%) S.E., Compiled data, Estimate BD
        inter_tab = QtWidgets.QWidget()
        it = QtWidgets.QVBoxLayout(inter_tab)
        it.setContentsMargins(4, 8, 4, 4)
        self.final_note = AutoLabel("")
        self.final_note.setObjectName("muted")
        self.final_note.setWordWrap(True)
        self.final_note.setVisible(False)
        it.addWidget(self.final_note)
        self.inter_view = Table(100)
        it.addWidget(self.inter_view, 1)
        self.var_view = Table(100)
        self.steps_view = Table(160)
        self.compiled_view = Table(160)
        self.bd_view = DataView("District")

        for w, name in ((sheet_tab, "Area Sheet"), (inter_tab, "Intermediate Table"), (self.var_view, "Variance"),
                        (self.steps_view, "(%) S.E."), (self.compiled_view, "Compiled Data"),
                        (self.bd_view, "Estimate BD")):
            self.body.addTab(w, name)
        self._enable(False)

    # ------------------------------------------------------------------ refresh / build
    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        sel = self._selection()
        d = est.folder(sc.state, sc.year)
        stamps = tuple((d / f).stat().st_mtime_ns if (d / f).exists() else 0 for f in (est.INPUTS_FILE,
                                                                                      est.AREAS_FILE))
        key = (sc.state, sc.year, sel, schedules.stamp(sc.state, sc.year), stamps)
        if key == self._key:
            return
        if self._dirty and self.sel is not None and sel != self.sel and self.result is not None:
            if QtWidgets.QMessageBox.question(
                    self, "Area sheet not saved", "The area sheet shown before has changes that are not saved. "
                    "Save them now? (No = discard them)") == QtWidgets.QMessageBox.StandardButton.Yes:
                est.save_inputs(sc.state, sc.year, self.sel, self._inputs(), self.base, self.nm.get("crop", ""))
                stamps = tuple((d / f).stat().st_mtime_ns if (d / f).exists() else 0 for f in (est.INPUTS_FILE,
                                                                                              est.AREAS_FILE))
                key = key[:4] + (stamps,)
        self._key = key
        self._dirty = False
        self.sel, self.result = sel, None
        if sel is None:
            self.exps = self.base = pd.DataFrame()
            self._fill_sheet(est.Inputs())
            self._clear_results()
            self._enable(False)
            return
        ml = master_list(sc, all_seasons=True)
        self.exps = est.experiments(ml, schedules.rc7(sc.state, sc.year), sel)
        self.base = est.district_base(est.harvested(self.exps))
        self.counts = est.information(self.exps)
        self.nm = est.names(ml, sel)
        inputs = est.load_inputs(sc.state, sc.year, sel)
        self._filling = True
        for box, val in ((self.cf, inputs.cf), (self.driage, inputs.driage), (self.recovery, inputs.recovery)):
            box.setText("" if val is None else f"{val:g}")
        self.prepared.setText(inputs.prepared_by)
        self._info = dict(inputs.info)
        self._filling = False
        self._fill_sheet(inputs)
        self.bd_view.set_frame(est.bd_table(self.exps), "District name",      # rejected plots highlighted
                               bg=lambda rec, col: RED.color() if str(rec.get("Rejected")) == "1" else None)
        c = self.counts
        self._status_base = ((f"{self.nm['parts']} → {self.nm['crop']} Combined · " if sel.combined else "")
                             + f"missed {c['MISSED']} · lost {c['LOST']} · not received {c['NR']} · "
                             f"{len(self.base)} districts")
        self.status.setText(self._status_base + (f" · saved {inputs.saved_on}" if inputs.saved_on
                                                 else " · area sheet not saved yet"))
        self._enable(True)
        self._clear_results()
        k = self.k
        k["planned"].set(f"{c['PLANNED']:,}")
        k["analysed"].set(f"{c['ANALYSED']:,}")
        if inputs.areas and inputs.cf and inputs.driage and inputs.recovery:
            self.calculate(save=False)
            self.body.setCurrentIndex(1)
        else:
            self.body.setCurrentIndex(0)

    def _enable(self, on: bool) -> None:
        for w in (self.cf, self.driage, self.recovery, self.prepared, self.b_calc):
            w.setEnabled(on)
        self.b_export.setEnabled(self.result is not None)
        self.b_copy.setEnabled(on and self.sel is not None and not self.sel.combined)

    def _clear_results(self) -> None:
        for name, kp in self.k.items():
            if name not in ("planned", "analysed") or self.sel is None:
                kp.set("–")
        for t in (self.steps_view, self.inter_view, self.var_view, self.compiled_view):
            t.set([], [])
        if self.sel is None:
            self.bd_view.set_frame(pd.DataFrame())
        self.final_note.setText("")
        self.b_export.setEnabled(False)

    # ------------------------------------------------------------------ area sheet
    def _fill_sheet(self, inputs: est.Inputs) -> None:
        self._filling = True
        self.sheet.setRowCount(len(self.base))
        for r, row in enumerate(self.base.itertuples(index=False)):
            area = inputs.areas.get(row.DISTRICT)
            vals = [row.DISTRICT, row.DISTRICTNAME, "" if area is None else f"{float(area):g}", str(row.EXPT),
                    inputs.merges.get(row.DISTRICT, ""), ""]
            for c, text in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(text)
                flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                if c in (AREA, MERGE):
                    flags |= Qt.ItemFlag.ItemIsEditable
                item.setFlags(flags)
                item.setBackground(WHITE if c in (AREA, MERGE) else GREY)
                if c in (AREA, EXPT):
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                self.sheet.setItem(r, c, item)
        fit_columns(self.sheet)
        self._filling = False
        self._paint_sheet()

    def _paint_sheet(self) -> None:
        self._filling = True
        names = dict(zip(self.base["DISTRICT"], self.base["DISTRICTNAME"])) if len(self.base) else {}
        missing, few = 0, []
        for r in range(self.sheet.rowCount()):
            short = int(self.sheet.item(r, EXPT).text() or 0) < MIN_EXPTS       # fewer than 4 expts: red
            m = self.sheet.item(r, MERGE).text().strip()
            m2 = m if m in ("", "1") else m.zfill(2)
            out = m == "1"                                                      # left out: the whole row red
            self.sheet.item(r, MNAME).setText("left out" if out else names.get(m2, "not on this sheet" if m else ""))
            for c in range(self.sheet.columnCount()):
                plain = WHITE if c in (AREA, MERGE) else GREY
                self.sheet.item(r, c).setBackground(RED if out or (short and c in (1, EXPT)) else plain)
            if short and not out:
                few.append(self.sheet.item(r, 1).text())
            a = self.sheet.item(r, AREA)
            if not out and not a.text().strip():
                a.setBackground(RED)
                missing += 1
        self._filling = False
        notes = ([f"{missing} district(s) still need an area (red)."] if missing else []) + (
            [f"Fewer than {MIN_EXPTS} expts – merge into another district (merge dist code) and mark it 1: "
             f"{', '.join(few)}."] if few else [])
        self.sheet_note.setText("  ".join(notes))

    def _sheet_edited(self, _item) -> None:
        if self._filling:
            return
        self._paint_sheet()
        self._edited()

    def _edited(self, *_):
        if not self._filling:
            self._dirty = True

    def _inputs(self) -> est.Inputs:
        areas, merges = {}, {}
        for r in range(self.sheet.rowCount()):
            d = self.sheet.item(r, 0).text()
            a = est._num(self.sheet.item(r, AREA).text())
            if a is not None:
                areas[d] = a
            m = self.sheet.item(r, MERGE).text().strip()
            if m:
                merges[d] = m if m == "1" else m.zfill(2)
        return est.Inputs(cf=est._num(self.cf.text()), driage=est._num(self.driage.text()),
                          recovery=est._num(self.recovery.text()), prepared_by=self.prepared.text().strip(),
                          areas=areas, merges=merges,
                          info=dict(self._info))

    def copy_other(self) -> None:
        """Areas, merges, factors and typed figures saved for the same crop's other sample."""
        if self.sel is None or self.sel.combined:
            return
        s, sm, c = self.sel.parts[0]
        other = est.Selection(((s, {"1": "2", "2": "1"}[sm], c),))
        inp = est.load_inputs(self.scope.state, self.scope.year, other)
        if not inp.areas and inp.cf is None:
            QtWidgets.QMessageBox.information(self, "Copy", f"Nothing is saved yet for {self.nm.get('cropname', c)}, "
                                              f"{est.SAMPLE_NAME[other.parts[0][1]].title()} sample.")
            return
        cur = self._inputs()
        inp.prepared_by = cur.prepared_by or inp.prepared_by
        self._filling = True
        for box, val in ((self.cf, inp.cf), (self.driage, inp.driage), (self.recovery, inp.recovery)):
            box.setText("" if val is None else f"{val:g}")
        self.prepared.setText(inp.prepared_by)
        self._filling = False
        self._fill_sheet(inp)
        self._dirty = True
        toast(self, "Copied from the other sample – check them, then Calculate & save.")

    # ------------------------------------------------------------------ calculate
    def calculate(self, save: bool = True) -> None:
        sc = self.scope
        if self.sel is None:
            return
        inputs = self._inputs()
        if not inputs.cf or not inputs.driage or not inputs.recovery:
            QtWidgets.QMessageBox.information(self, "Estimates", "Please enter the conversion factor, driage ratio "
                                              "and recovery ratio.")
            return
        res = est.calculate(self.base, inputs)
        self.result = res
        if save:
            try:
                est.save_inputs(sc.state, sc.year, self.sel, inputs, self.base, self.nm.get("crop", ""))
            except OSError as e:
                QtWidgets.QMessageBox.critical(self, "Not saved", f"The area sheet could not be saved:\n\n{e}")
                return
            self._dirty = False
            d = est.folder(sc.state, sc.year)
            self._key = self._key[:4] + (tuple((d / f).stat().st_mtime_ns if (d / f).exists() else 0
                                              for f in (est.INPUTS_FILE, est.AREAS_FILE)),)
            self.status.setText(self._status_base + f" · saved {inputs.saved_on}")
            toast(self, "Estimate worked out; area sheet saved.")
        k = self.k
        k["yield (kg/ha)"].set(_fmt(res.yield_kg_ha))
        k["%SE"].set(_fmt(res.pct_se, 1) if not isinstance(res.pct_se, str) else "n/a",
                     C["red"] if not isinstance(res.pct_se, str) and res.pct_se > 10 else None)
        k["SE (kg/ha)"].set(_fmt(res.se, 2) if not isinstance(res.se, str) else "n/a")
        k["variance"].set(_fmt(res.variance) if not isinstance(res.variance, str) else "n/a")
        k["area"].set(_fmt(res.total_area))
        k["analysed"].set(f"{res.analysed:,}")
        steps = est.se_table(res)
        steps["Value"] = [v if isinstance(v, str) else _fmt(round(v, 2)) for v in steps["Value"]]
        _show(self.steps_view, steps)
        _show(self.inter_view, est.intermediate_table(res), {"CCF": 4})
        _show(self.var_view, est.variance_table(res), {"8. (ni² − Σnij²) ÷ (ni × (mi − 1))": 2})
        _show(self.compiled_view, est.compiled_table(res, self.counts["PLANNED"]))
        self.final_note.setText("  ".join(res.warnings))
        self._enable(True)
        self.b_export.setEnabled(True)
        if save:
            self.body.setCurrentIndex(1)

    # ------------------------------------------------------------------ export
    def export(self) -> None:
        sc = self.scope
        if self.result is None or self.sel is None:
            return
        inputs = self._inputs()
        try:
            if self._dirty:
                est.save_inputs(sc.state, sc.year, self.sel, inputs, self.base, self.nm.get("crop", ""))
                self._dirty = False
                self.status.setText(self._status_base + f" · saved {inputs.saved_on}")
            self.result = est.calculate(self.base, inputs)
            out = report.export(sc.state, sc.year, self.sel, self.nm, inputs, self.base, self.result, self.exps)
            # Also append to consolidated summary CSV
            ml = master_list(sc, all_seasons=True)
            state_code = ml["STATE"].iloc[0] if len(ml) and "STATE" in ml.columns else sc.state
            report.append_summary_csv(sc.state, sc.year, self.sel, self.nm, self.result, state_code)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the Excel file:\n\n{e}")
            return
        os.startfile(str(out.resolve()))                         # noqa: S606 (Windows)
