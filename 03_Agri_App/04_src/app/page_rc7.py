"""7. RC7 page (components/c07_rc7.py) – the crop cutting record of the open state + year.

All crops; a tick box for each season of the state + year's master list and Central / State ticks, on a line under
the title (the work page's Season / Crop lists are hidden here).
  Proposed corrections   one line per kind of fix (field, now → proposed, why) per crop + sample, ticked; Apply
                         ticked… asks first, then writes them to corrections.csv (every module uses them)
  Problems               what only you can decide; type the right value in "New value" and Save typed values
Mark final / Unmark final: the crops + samples of the ticked seasons / samples – final ones are locked (no
corrections, no typed values) until unmarked; the page warns when their data changed after marking.
Export: both lists as CSV.
"""
from __future__ import annotations

import os

from src.components import c07_rc7 as v
from src.utils import folders as F
from src.utils import schedules

from .look import fit_columns, button, flow_box, label, toast
from .qt import QtGui, QtWidgets, Qt
from .window import ART, C, StepTab, master_list

GROUP_HEADS = ["", "Field", "Now", "Proposed", "Why", "Season", "Crop", "Sample", "Schedules"]
PROBLEM_HEADS = ["Exp-ID", "District", "Season", "Crop", "Sample", "Field", "Entry noted", "Check", "New value"]
NEW = PROBLEM_HEADS.index("New value")
KEYS = {"Exp-ID": "EXPTID"}
IN_DV = {"QTYP", "QTYP / QTYG"}        # yields: fixed in 4. Data Validation (plot weight -> QTYG and QTYP together)
GREY = QtGui.QBrush(QtGui.QColor("#eef1f4"))
WHITE = QtGui.QBrush(QtGui.QColor("#ffffff"))


def _item(text, editable=False, right=False):
    it = QtWidgets.QTableWidgetItem("" if text is None else str(text))
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    if editable:
        flags |= Qt.ItemFlag.ItemIsEditable
    it.setFlags(flags)
    it.setBackground(WHITE if editable else GREY)
    if right:
        it.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
    return it


class RC7Tab(StepTab):
    number, title, tab = 7, "RC7", "RC7"
    uses_season_crop = False                  # its own season ticks; all crops

    @property
    def folder(self):                       # 02_artifacts/07_rc7/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.RC7 / sc.state / sc.year if sc.ok else ART / F.RC7

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self._key = None
        self.groups: list[dict] = []
        self.issues: list[dict] = []
        self.proposals: list[dict] = []
        self.n_rows = 0

        # --- Season ticks (rebuilt per state + year) and Sample ticks, on a line under the title
        picks, self.picks = flow_box(spacing=10)
        self.picks.addWidget(label("Season", "muted", wrap=False))
        self.season_cbs: list[QtWidgets.QCheckBox] = []
        self._seasons_for = None
        self.sample_lb = label("   Sample", "muted", wrap=False)
        self.picks.addWidget(self.sample_lb)
        self.central, self.state_s = QtWidgets.QCheckBox("Central"), QtWidgets.QCheckBox("State")
        for cb in (self.central, self.state_s):
            cb.setChecked(True)
            cb.toggled.connect(lambda on, cb=cb: self._sample_toggled(cb, on))
            self.picks.addWidget(cb)
        self.status.parentWidget().layout().insertWidget(1, picks)
        self.b_apply = button("Apply ticked…", primary=True, icon="SP_DialogApplyButton",
                              tip="Write the ticked corrections to corrections.csv (asks first)")
        self.b_apply.clicked.connect(self.apply_ticked)
        self.add_action(self.b_apply)
        self.b_final = button("Mark final", icon="SP_DialogYesButton",
                              tip="Mark the RC-7 of the crops + samples shown final (asks first); unmark it any time")
        self.b_final.clicked.connect(self.toggle_final)
        self.add_action(self.b_final)
        self.b_export = button("Export", icon="SP_DialogSaveButton", tip="Both lists as CSV in <dd.mm.yyyy>/")
        self.b_export.clicked.connect(self.export)
        self.add_action(self.b_export)
        self.k_rows = self.kpi("schedules checked")
        self.k_fix = self.kpi("corrections proposed")
        self.k_tick = self.kpi("ticked")
        self.k_prob = self.kpi("problems")
        self.df = None
        self.fstate: dict = {}

        # --- proposed corrections (grouped, ticked)
        fix = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(fix)
        fl.setContentsMargins(4, 8, 4, 4)
        bw, bl = flow_box(spacing=8)
        b_all, b_none = button("Tick all"), button("Untick all")
        b_all.clicked.connect(lambda: self._tick_all(True))
        b_none.clicked.connect(lambda: self._tick_all(False))
        bl.addWidget(b_all)
        bl.addWidget(b_none)
        bl.addWidget(label("Hover a line to see its schedules.", "muted", wrap=False))
        fl.addWidget(bw)
        self.fix_table = QtWidgets.QTableWidget(0, len(GROUP_HEADS))
        self.fix_table.setHorizontalHeaderLabels(GROUP_HEADS)
        self.fix_table.verticalHeader().setVisible(False)
        self.fix_table.verticalHeader().setDefaultSectionSize(24)
        self.fix_table.itemChanged.connect(lambda *_: self._count_ticked())
        fl.addWidget(self.fix_table, 1)

        # --- problems (typed values)
        prob = QtWidgets.QWidget()
        pl2 = QtWidgets.QVBoxLayout(prob)
        pl2.setContentsMargins(4, 8, 4, 4)
        fw, fl2 = flow_box(spacing=8)
        fl2.addWidget(label("Show", "muted", wrap=False))
        self.check_filter = QtWidgets.QComboBox()
        self.check_filter.setMinimumWidth(260)
        self.check_filter.currentIndexChanged.connect(self._filter_problems)
        fl2.addWidget(self.check_filter)
        self.b_save = button("Save typed values", icon="SP_DialogSaveButton",
                             tip="Write the values typed in 'New value' to corrections.csv (asks first)")
        self.b_save.clicked.connect(self.save_typed)
        fl2.addWidget(self.b_save)
        pl2.addWidget(fw)
        self.prob_table = QtWidgets.QTableWidget(0, len(PROBLEM_HEADS))
        self.prob_table.setHorizontalHeaderLabels(PROBLEM_HEADS)
        self.prob_table.verticalHeader().setVisible(False)
        self.prob_table.verticalHeader().setDefaultSectionSize(24)
        T = QtWidgets.QAbstractItemView.EditTrigger
        self.prob_table.setEditTriggers(T.CurrentChanged | T.SelectedClicked | T.AnyKeyPressed | T.DoubleClicked)
        pl2.addWidget(self.prob_table, 1)
        self.body.addTab(fix, "Proposed corrections")
        self.body.addTab(prob, "Problems")

    # ------------------------------------------------------------------ data
    def _seasons(self) -> list[str]:
        return [cb.property("code") for cb in self.season_cbs if cb.isChecked()]

    def _build_seasons(self, ml) -> None:
        """One tick box per season of the master list (with its planned schedules), all ticked."""
        for cb in self.season_cbs:
            i = self.picks.indexOf(cb)
            if i >= 0:
                self.picks.takeAt(i)
            cb.hide()
            cb.setParent(None)
            cb.deleteLater()
        self.season_cbs = []
        if ml.empty:
            return
        at = self.picks.indexOf(self.sample_lb)
        seasons = ml.groupby(["SEASONCODE", "SEASONNAME"]).size().reset_index(name="n")
        seasons = seasons.sort_values("SEASONCODE", key=lambda c: c.map(lambda x: int(x) if str(x).isdigit() else 99))
        for i, r in enumerate(seasons.itertuples()):
            cb = QtWidgets.QCheckBox(f"{str(r.SEASONNAME).title()} ({r.n:,})")
            cb.setProperty("code", r.SEASONCODE)
            cb.setToolTip(f"Season {r.SEASONCODE}: {r.n:,} planned experiments")
            cb.setChecked(True)
            cb.toggled.connect(lambda on, cb=cb: self._season_toggled(cb, on))
            self.picks.insertWidget(at + i, cb)
            self.season_cbs.append(cb)
        self.picks.invalidate()                              # re-flow the line for the new boxes
        self.picks.parentWidget().updateGeometry()

    def _season_toggled(self, cb, on: bool) -> None:
        if not on and not self._seasons():                   # one season at least
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
            return
        self.refresh()

    def _samples(self) -> list[str]:
        return [c for cb, c in ((self.central, "1"), (self.state_s, "2")) if cb.isChecked()]

    def _sample_toggled(self, cb, on: bool) -> None:
        if not on and not self._samples():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
            return
        self.refresh()

    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        from src.components import c05_estimates as est
        f = est.folder(sc.state, sc.year) / est.INPUTS_FILE
        ml = master_list(sc, all_seasons=True)
        if self._seasons_for != (sc.state, sc.year):
            self._seasons_for = (sc.state, sc.year)
            self._build_seasons(ml)
        key = (sc.state, sc.year, tuple(self._seasons()), tuple(self._samples()), schedules.stamp(sc.state, sc.year),
               f.stat().st_mtime_ns if f.exists() else 0)
        if key == self._key:
            return
        self._key = key
        rc = schedules.rc7(sc.state, sc.year)
        df = v.rows(ml, rc, tuple(self._seasons()), tuple(self._samples()))
        self.df, self.n_rows = df, len(df)
        self.fstate = v.final_state(sc.state, sc.year, df)
        if df.empty:
            self.proposals, self.groups, self.issues = [], [], []
            self.status.setText("No received schedule (RC-7) for the ticked seasons / samples yet." if not ml.empty else
                                "No master list for this state + year.")
        else:
            self.proposals, fixed = v.propose(df, ml, rc, sc.state, sc.year)
            self.groups = v.group_proposals(self.proposals)
            self.issues = v.problems(fixed, sc.state, sc.code, sc.year)
            self.status.setText(self._final_text())
        self._fill_groups()
        self._fill_problems()
        self.k_rows.set(f"{self.n_rows:,}")
        self.k_fix.set(f"{len(self.proposals):,}", C["orange"] if self.proposals else None)
        self.k_prob.set(f"{len(self.issues):,}", C["red"] if self.issues else None)
        for b in (self.b_export, self.b_save, self.b_final):
            b.setEnabled(self.n_rows > 0)
        self._show_final()

    # ------------------------------------------------------------------ final
    def _locked(self) -> set[str]:
        return {k for k, st in self.fstate.items() if st["final"]}

    def _final_text(self) -> str:
        fs = self.fstate
        n_final = sum(st["final"] for st in fs.values())
        changed = [f"{st['name']} {st['sample']}" for st in fs.values() if st["final"] and st["changed"]]
        text = ""
        if fs and n_final == len(fs):
            dates = sorted({st["marked_on"][:16] for st in fs.values()})
            text = f"Final since {dates[-1]}" + ("" if changed else " – locked; Unmark final to change it"
                                                  if len(fs) == 1 else " (all crops shown) – locked; Unmark final to "
                                                  "change them")
        elif n_final:
            text = f"{n_final} of {len(fs)} crop + sample(s) shown are final – their lines are locked"
        if changed:
            text += ("  ·  " if text else "") + ("Changed since it was marked final: " + ", ".join(changed[:6])
                                                 + (" …" if len(changed) > 6 else "") + " – check it and mark it final again")
        return text

    def _show_final(self) -> None:
        fs = self.fstate
        n_final = sum(st["final"] for st in fs.values())
        changed = any(st["final"] and st["changed"] for st in fs.values())
        all_final = bool(fs) and n_final == len(fs) and not changed
        self.b_final.setText("Unmark final" if all_final else "Mark final again" if changed else "Mark final")
        self.b_final.setIcon(self.style().standardIcon(
            getattr(QtWidgets.QStyle.StandardPixmap, "SP_DialogNoButton" if all_final else "SP_DialogYesButton")))

    def toggle_final(self) -> None:
        sc, fs = self.scope, self.fstate
        if not fs:
            return
        if all(st["final"] and not st["changed"] for st in fs.values()):            # unmark
            names = [f"{st['name']} {st['sample']}" for st in fs.values()]
            if QtWidgets.QMessageBox.question(
                    self, "Unmark final", f"Open the RC-7 of {len(names)} crop + sample(s) again?\n\n"
                    + "\n".join(names[:15]) + ("\n…" if len(names) > 15 else "")) \
                    != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            v.unmark_final(sc.state, sc.year, list(fs))
            toast(self, "Unmarked – the RC-7 can be corrected again.")
        else:                                                    # mark the ones not final yet
            keys = [k for k, st in fs.items() if not st["final"] or st["changed"]]
            names = [f"{fs[k]['name']} {fs[k]['sample']} ({fs[k]['schedules']} schedules)" for k in keys]
            open_fix = sum(len(g["items"]) for g in self.groups if g["KEY"] in keys)
            open_prob = sum(1 for p in self.issues if p["KEY"] in keys)
            box = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Icon.Question, "Mark final",
                f"Mark the RC-7 of {len(keys)} crop + sample(s) final?\n\n" + "\n".join(names[:15])
                + ("\n…" if len(names) > 15 else "")
                + (f"\n\nStill open: {open_fix:,} proposed correction(s) and {open_prob:,} problem(s)."
                   if open_fix or open_prob else "\n\nNo correction or problem is open.")
                + "\n\nFinal ones are locked until you unmark them; the final RC-7 file is written for 8. Annexures.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, self)
            box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
            if box.exec() != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            try:
                n = v.mark_final(sc.state, sc.year, self.df, keys)
            except OSError as e:
                QtWidgets.QMessageBox.critical(self, "Not saved", f"Could not mark it final:\n\n{e}")
                return
            toast(self, f"Marked final ({n:,} schedules).")
        self._key = None
        self.refresh()

    def _fill_groups(self) -> None:
        t = self.fix_table
        t.blockSignals(True)
        t.setRowCount(len(self.groups))
        locked = self._locked()
        for r, g in enumerate(self.groups):
            tick = QtWidgets.QTableWidgetItem()
            final = g["KEY"] in locked
            tick.setFlags(Qt.ItemFlag.ItemIsUserCheckable if final else
                          Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            tick.setCheckState(Qt.CheckState.Unchecked if final else Qt.CheckState.Checked)
            if final:
                tick.setToolTip("Final – unmark it to correct it")
            t.setItem(r, 0, tick)
            vals = [g["Field"], g["Now"] or "(blank)", g["Proposed"] or "(blank)", g["Why"], g["Season"], g["Crop"],
                    g["Sample"], len(g["items"])]
            for c, val in enumerate(vals, 1):
                it = _item(val, right=c == 8)
                ids = [p["EXPTID"] for p in g["items"]]
                it.setToolTip(", ".join(ids[:40]) + (f" … ({len(ids)})" if len(ids) > 40 else ""))
                t.setItem(r, c, it)
        t.blockSignals(False)
        fit_columns(t)
        t.horizontalHeader().setStretchLastSection(True)
        self._count_ticked()

    def _ticked(self) -> list[dict]:
        out = []
        for r, g in enumerate(self.groups):
            if self.fix_table.item(r, 0).checkState() == Qt.CheckState.Checked and g["KEY"] not in self._locked():
                out += g["items"]
        return out

    def _count_ticked(self) -> None:
        n = len(self._ticked())
        self.k_tick.set(f"{n:,}")
        self.b_apply.setText(f"Apply ticked ({n:,})…" if n else "Apply ticked…")
        self.b_apply.setEnabled(n > 0)

    def _tick_all(self, on: bool) -> None:
        self.fix_table.blockSignals(True)
        locked = self._locked()
        for r in range(self.fix_table.rowCount()):
            final = self.groups[r]["KEY"] in locked
            self.fix_table.item(r, 0).setCheckState(Qt.CheckState.Checked if on and not final else
                                                    Qt.CheckState.Unchecked)
        self.fix_table.blockSignals(False)
        self._count_ticked()

    def _fill_problems(self) -> None:
        kinds = sorted({p["Check"].split(" Allowed:")[0] for p in self.issues})
        self.check_filter.blockSignals(True)
        keep = self.check_filter.currentText()
        self.check_filter.clear()
        self.check_filter.addItem(f"All problems ({len(self.issues)})", "")
        for k in kinds:
            n = sum(p["Check"].startswith(k) for p in self.issues)
            self.check_filter.addItem(f"{k} ({n})", k)
        i = self.check_filter.findText(keep)
        self.check_filter.setCurrentIndex(max(0, i))
        self.check_filter.blockSignals(False)
        t = self.prob_table
        t.setRowCount(len(self.issues))
        for r, p in enumerate(self.issues):
            for c, name in enumerate(PROBLEM_HEADS):
                if name == "New value":
                    dv_field, final = p["Field"] in IN_DV, p["KEY"] in self._locked()
                    it = _item("final" if final else "→ 4. Data Validation" if dv_field else "",
                               editable=not dv_field and not final)
                    if final:
                        it.setToolTip("Final – unmark it to change it")
                    elif dv_field:
                        it.setToolTip("Change the plot weight in 4. Data Validation: QTYG and QTYP follow it")
                    t.setItem(r, c, it)
                else:
                    t.setItem(r, c, _item(p.get(KEYS.get(name, name), "")))
        fit_columns(t)
        t.setColumnWidth(PROBLEM_HEADS.index("Check"), min(t.columnWidth(PROBLEM_HEADS.index("Check")), 460))
        t.horizontalHeader().setStretchLastSection(True)
        self._filter_problems()

    def _filter_problems(self, *_) -> None:
        k = self.check_filter.currentData() or ""
        for r, p in enumerate(self.issues):
            self.prob_table.setRowHidden(r, bool(k) and not p["Check"].startswith(k))

    # ------------------------------------------------------------------ apply
    def _confirm(self, title: str, changes: list[dict]) -> bool:
        ids = {c["EXPTID"] for c in changes}
        lines = [f"{c['EXPTID']}  {c['Field']}:  {c['Now'] or 'blank'}  →  {c['Proposed'] or 'blank'}"
                 for c in changes]
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, title,
                                    f"Apply {len(changes):,} correction(s) in {len(ids):,} schedule(s)?\n\n"
                                    + "\n".join(lines[:12]) + ("\n…" if len(lines) > 12 else "") +
                                    "\n\nThe imported data stays as it is; the corrections go to corrections.csv and "
                                    "every module uses the corrected values.",
                                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                    self)
        box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        if len(lines) > 12:
            box.setDetailedText("\n".join(lines))
        return box.exec() == QtWidgets.QMessageBox.StandardButton.Yes

    def _write(self, changes: list[dict]) -> None:
        try:
            n = v.apply(self.scope.state, self.scope.year, changes)
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"The corrections could not be saved:\n\n{e}")
            return
        self._key = None
        self.win.refresh_modules()
        toast(self, f"{n:,} correction(s) saved.")

    def apply_ticked(self) -> None:
        changes = self._ticked()
        if changes and self._confirm("Apply corrections", changes):
            self._write(changes)

    def save_typed(self) -> None:
        changes = []
        for r, p in enumerate(self.issues):
            new = self.prob_table.item(r, NEW).text().strip()
            if not new or p["Field"] in IN_DV or p["KEY"] in self._locked():
                continue
            fields = [f.strip() for f in p["Field"].split("/")]
            if len(fields) != 1:
                continue                                         # QTYP / QTYG: type them in 4. Data Validation
            for e in p.get("EXPTIDS") or [p["EXPTID"]]:
                changes.append({"EXPTID": e, "Field": fields[0], "Now": p["Entry noted"], "Proposed": new})
        if not changes:
            QtWidgets.QMessageBox.information(self, "Save typed values", "Type the right value in the 'New value' "
                                              "column first.")
            return
        if self._confirm("Save typed values", changes):
            self._write(changes)

    def export(self) -> None:
        sc = self.scope
        try:
            out = v.export(sc.state, sc.year, self.proposals, self.issues, "_".join(cb.text().split(" (")[0] for cb in self.season_cbs if cb.isChecked()) or "all")
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the CSV files:\n\n{e}")
            return
        os.startfile(str(out.resolve()))                         # noqa: S606 (Windows)
