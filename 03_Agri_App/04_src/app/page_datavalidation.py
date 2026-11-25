"""4. Data Validation page — KrishiSoft_V0.1's Yield Checking page (old YIELD CHECKING.accdb), with a minimum yield.

Crop (and season) come from the work page's dropdowns, the sample from the header. Then:
  limits      Maximum yield (old table or saved) and Minimum yield (saved); typed values are used for this check,
              Save limits keeps them for this crop + sample in this state + year
  the table   Block 5 / 9 / 10 values editable, RC-7 values follow; red cells as in the old form (+ below minimum);
              RUN YIELD CONVERSION; SAVE (confirmed) writes corrections that every module then uses
  find        a full Exp-ID opens its crop and shows only that row; part of one narrows the list
"""
from __future__ import annotations

import os

from src.components import c04_datavalidation as dv
from src.utils import folders as F
from src.utils import schedules

from .look import fit_columns, AutoLabel, button, flow_box, label, toast
from .qt import QtCore, QtGui, QtWidgets, Qt
from .window import ART, C, DB, StepTab, master_list

HEAD = dv.COLUMNS + dv.CHECK_COLUMNS
COL = {name: i for i, name in enumerate(HEAD)}
RULES = {"WEIGHT": r"\d*(\.\d*)?", "NETWEIGHT": r"\d*(\.\d*)?", "CROPCOND": r"[1-4]?", "AFF": r"\d?",
         "REJ": r"[01]?", "L1": r"\d*(\.\d*)?", "L2": r"\d*(\.\d*)?"}
RED = QtGui.QBrush(QtGui.QColor("#ffc7ce"))
CHANGED = QtGui.QBrush(QtGui.QColor("#fff4c2"))
GREY = QtGui.QBrush(QtGui.QColor("#eef1f4"))
WHITE = QtGui.QBrush(QtGui.QColor("#ffffff"))


class _Validated(QtWidgets.QStyledItemDelegate):
    """Editors that only accept what the old form's fields accept (numbers; condition 1–4; REJ 0/1)."""

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)
        rule = RULES.get(HEAD[index.column()])
        if rule:
            editor.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(rule)))
        return editor


class DataValidationTab(StepTab):
    number, title, tab = 4, "Data Validation", "Data Validation"

    @property
    def folder(self):                       # 02_artifacts/04_datavalidation/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.DATA_VALIDATION / sc.state / sc.year if sc.ok else ART / F.DATA_VALIDATION

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self.sel: tuple | None = None          # (season, sample, crop) shown
        self.orig: list[dict] = []             # as stored (corrections applied)
        self.rows: list[dict] = []             # with changes not saved yet
        self._key = None
        self._filling = False
        self._left_out = 0

        pick = QtWidgets.QWidget()
        pl = QtWidgets.QHBoxLayout(pick)
        pl.setContentsMargins(0, 0, 8, 0)
        pl.addWidget(label("Sample", "muted", wrap=False))
        self.sample = QtWidgets.QComboBox()
        self.sample.addItem("Central (1)", "1")
        self.sample.addItem("State (2)", "2")
        self.sample.currentIndexChanged.connect(lambda *_: self.refresh())
        pl.addWidget(self.sample)
        self.actions.insertWidget(0, pick)
        self.b_out = button("Export Outliers", icon="SP_DialogSaveButton",
                            tip="Rows with a red cell, as CSV (FLAGS says why) in Outliers/<CROP>/<Sample>/")
        self.b_out.clicked.connect(lambda: self.export(True))
        self.add_action(self.b_out)
        self.b_all = button("Export Basic Data", icon="SP_DialogSaveButton",
                            tip="All rows of the list, as CSV, in Basic Data/<CROP>/<Sample>/")
        self.b_all.clicked.connect(lambda: self.export(False))
        self.add_action(self.b_all)

        self.k_n = self.kpi("experiments")
        self.k_max = self.kpi("above maximum")
        self.k_min = self.kpi("below minimum")
        self.k_cond = self.kpi("condition vs affected")
        self.k_rej = self.kpi("rejected (REJ 1)")
        self.k_chg = self.kpi("changes not saved")

        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(4, 8, 4, 4)
        lay.setSpacing(8)

        # --- limits
        lim_w, lim = flow_box(spacing=10)
        self.max_box, self.min_box = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        self._paint_wait = QtCore.QTimer(self)          # re-colour the rows when typing pauses, not on every key
        self._paint_wait.setSingleShot(True)
        self._paint_wait.setInterval(250)
        self._paint_wait.timeout.connect(self._paint_all)
        for name, box in (("Maximum yield", self.max_box), ("Minimum yield", self.min_box)):
            box.setFixedWidth(120)
            box.setAlignment(Qt.AlignmentFlag.AlignRight)
            box.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r"\d*(\.\d*)?")))
            box.setPlaceholderText("not set")
            box.textEdited.connect(lambda _t: self._paint_wait.start())
            cell = QtWidgets.QWidget()
            cl = QtWidgets.QHBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.addWidget(label(name, "h3", wrap=False))
            cl.addWidget(box)
            lim.addWidget(cell)
        self.b_save_lim = button("Save limits", tip="Keep this maximum and minimum yield for this crop and sample "
                                 "in this state + year")
        self.b_save_lim.clicked.connect(self.save_limits)
        lim.addWidget(self.b_save_lim)
        self.lim_note = label("", "muted", wrap=False)
        lim.addWidget(self.lim_note)
        lay.addWidget(lim_w)

        # --- find one experiment
        find_w, find = flow_box(spacing=8)
        find.addWidget(QtWidgets.QLabel("Find an experiment"))
        self.find_box = QtWidgets.QLineEdit()
        self.find_box.setPlaceholderText("Exp-ID (12 digits, or part of it)")
        self.find_box.setFixedWidth(240)
        self.find_box.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r"\d{0,12}")))
        self.find_box.returnPressed.connect(self.search)
        find.addWidget(self.find_box)
        b_find = button("Search", icon="SP_FileDialogContentsView")
        b_find.clicked.connect(self.search)
        find.addWidget(b_find)
        self.b_show_all = button("Show all rows")
        self.b_show_all.clicked.connect(self.show_all_rows)
        self.b_show_all.setEnabled(False)
        find.addWidget(self.b_show_all)
        lay.addWidget(find_w)

        self.note = AutoLabel("")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        lay.addWidget(self.note)

        # --- the experiments
        self.table = QtWidgets.QTableWidget(0, len(HEAD))
        self.table.setHorizontalHeaderLabels([dv.label(h) for h in HEAD])
        for i, h in enumerate(HEAD):
            self.table.horizontalHeaderItem(i).setToolTip(dv.TIPS.get(h, h))
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setItemDelegate(_Validated(self.table))
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
                                   | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
                                   | QtWidgets.QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.table.itemChanged.connect(self._cell_edited)
        self.table.setMinimumHeight(200)
        lay.addWidget(self.table, 1)
        lay.addWidget(label("White = editable (Block 5 / 9 / 10, REJ); grey = RC-7, follows your edits. Red = a check "
                            "failed; yellow = changed, not saved. Hover a heading to see what it is.", "muted"))

        bar_w, bar = flow_box(spacing=8)
        self.b_convert = button("RUN YIELD CONVERSION", tip="Plot weight -> net weight / RC-7 for every row "
                                "(the old rule)")
        self.b_convert.clicked.connect(self.run_conversion)
        self.b_undo = button("Undo changes")
        self.b_undo.clicked.connect(self.undo)
        self.b_save = button("SAVE", primary=True, icon="SP_DialogApplyButton")
        self.b_save.clicked.connect(self.save)
        for b in (self.b_convert, self.b_undo, self.b_save):
            bar.addWidget(b)
        lay.addWidget(bar_w)
        self.body.addTab(page, "Yield check")
        self._set_enabled(False)

    # ---- selection
    def _selection(self) -> tuple | None:
        """(season, sample, crop) from the work page + Sample box, or None (with the reason in the status line)."""
        sc = self.scope
        if not sc.crop:
            self.status.setText("Choose a crop in the Crop list above (and the sample); its experiments are listed "
                                "here with the yield checks.")
            return None
        season = sc.season
        if not season:
            ml = master_list(sc, all_seasons=True)
            seasons = sorted(set(ml.loc[ml["CROPCODE"] == sc.crop, "SEASONCODE"]))
            if len(seasons) != 1:
                self.status.setText("This crop is in more than one season: choose the season too.")
                return None
            season = seasons[0]
        self.status.setText("")
        return season, self.sample.currentData(), sc.crop

    def _pending(self) -> list:
        return [(o, x) for o, x in zip(self.orig, self.rows) if dv.changes(o, x)]

    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok:
            return
        sel = self._selection()
        lim_file = DB / F.DATA_VALIDATION / sc.state / sc.year / dv.LIMITS_FILE
        key = (sc.state, sc.year, sel, schedules.stamp(sc.state, sc.year), lim_file.stat().st_mtime_ns if lim_file.exists() else 0)
        if key == self._key:
            return
        if self._pending() and sel != self.sel:
            ans = QtWidgets.QMessageBox.question(
                self, "Changes not saved", f"{len(self._pending())} schedule(s) of the list shown before have changes "
                "that are not saved. Save them now? (No = discard them)",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            if ans == QtWidgets.QMessageBox.StandardButton.Yes:
                dv.save(sc.state, sc.year, self._pending())
        self._key = key
        self.sel = sel
        if sel is None:
            self.orig, self.rows = [], []
            self.note.setText("")
            self._fill_table()
            self._set_enabled(False)
            return
        ml = master_list(sc, all_seasons=True)
        rows, self._left_out = dv.experiments(ml, schedules.rc7(sc.state, sc.year), schedules.blocks(sc.state, sc.year),
                                              *sel)
        lim = dv.get_limits(sc.state, sc.code, sc.year, *sel)
        self.max_box.setText(dv.fmt(lim["max"]))
        self.min_box.setText(dv.fmt(lim["min"]))
        self.lim_note.setText(f"maximum: {lim['max_from']} · minimum: {lim['min_from']}   (typed values are used "
                              "for this check; Save limits keeps them)")
        self.orig = rows.reindex(columns=dv.COLUMNS + ["DISTRICTNAME", "SOURCE", "CROPNAME"]).fillna("").to_dict(
            "records")
        self.rows = [dict(r) for r in self.orig]
        self.note.setText(f"{self._left_out} received schedule(s) of this crop are not listed: no Block 5 / 9 / 10 "
                          "(missed or lost) – as in the old form." if self._left_out else "")
        self._set_enabled(True)
        self._fill_table()

    def _set_enabled(self, on: bool) -> None:
        for w in (self.max_box, self.min_box, self.b_save_lim, self.b_convert, self.b_undo, self.b_out, self.b_all):
            w.setEnabled(on)
        if not on:
            self.max_box.clear()
            self.min_box.clear()
            self.lim_note.setText("")
            for k in (self.k_n, self.k_max, self.k_min, self.k_cond, self.k_rej, self.k_chg):
                k.set("–")
            self.b_save.setEnabled(False)

    # ---- limits
    def _limits(self) -> tuple:
        return dv.num(self.max_box.text()), dv.num(self.min_box.text())

    def save_limits(self) -> None:
        sc = self.scope
        if self.sel is None:
            return
        mx, mn = self._limits()
        if mx is not None and mn is not None and mn >= mx:
            QtWidgets.QMessageBox.warning(self, "Yield limits", "The minimum yield must be below the maximum yield.")
            return
        season, sample, crop = self.sel
        if QtWidgets.QMessageBox.question(
                self, "Save limits", f"Keep maximum {dv.fmt(mx) or 'not set'} and minimum {dv.fmt(mn) or 'not set'} "
                f"for crop {crop} ({sc.crop_name}), season {season}, sample {sample} in {sc.state} {sc.year}?") \
                != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        dv.save_limits(sc.state, sc.year, season, sample, crop, mx, mn)
        self._key = None
        self.refresh()
        toast(self, "Yield limits saved.")

    # ---- table
    def _fill_table(self) -> None:
        self._filling = True
        self.table.setRowCount(len(self.rows))
        for r in range(len(self.rows)):
            for c, name in enumerate(HEAD):
                item = QtWidgets.QTableWidgetItem()
                flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                if name in dv.EDITABLE:
                    flags |= Qt.ItemFlag.ItemIsEditable
                item.setFlags(flags)
                if name in ("WEIGHT", "NETWEIGHT", "QTYG", "QTYP", "L1", "L2"):
                    item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                self.table.setItem(r, c, item)
            self.table.setRowHidden(r, False)
        self._filling = False
        self.b_show_all.setEnabled(False)
        self._paint_all()
        fit_columns(self.table)

    def _paint_row(self, r: int) -> None:
        row, orig = self.rows[r], self.orig[r]
        mx, mn = self._limits()
        c1, c2 = dv.checks(row)
        red_weight = dv.above_max(row, mx) or dv.below_min(row, mn)
        red_cond = "FALSE" in (c1, c2)
        bold = QtGui.QFont()
        bold.setBold(True)
        values = {**row, "CHECK 1": dv.check_text("CHECK 1", c1), "CHECK 2": dv.check_text("CHECK 2", c2)}
        for c, name in enumerate(HEAD):
            item = self.table.item(r, c)
            item.setText(str(values.get(name, "") or ""))
            changed = name in dv.EDITABLE + dv.RC7 and not dv.same(orig.get(name, ""), row.get(name, ""))
            red = ((red_weight and name in ("WEIGHT", "NETWEIGHT")) or (red_cond and name in ("CROPCOND", "AFF"))
                   or (name == "REJ" and dv.rejected(row)))
            item.setBackground(RED if red else CHANGED if changed else WHITE if name in dv.EDITABLE else GREY)
            item.setFont(bold if changed else QtGui.QFont())
            if name in dv.CHECK_COLUMNS:
                item.setForeground(QtGui.QBrush(QtGui.QColor("#1b5e20" if values[name] == "OK" else "#b3261e")))
            if red:
                item.setToolTip(", ".join(dv.flags(row, mx, mn)))

    def _paint_all(self) -> None:
        self._filling = True
        for r in range(len(self.rows)):
            self._paint_row(r)
        self._filling = False
        self._update_counts()

    def _cell_edited(self, item) -> None:
        if self._filling:
            return
        r, name = item.row(), HEAD[item.column()]
        if name not in dv.EDITABLE:
            return
        row = dict(self.rows[r])
        row[name] = item.text().strip()
        self.rows[r] = dv.after_edit(row, name, self.scope.code)
        self._filling = True
        self._paint_row(r)
        self._filling = False
        self._update_counts()

    def _update_counts(self) -> None:
        if self.sel is None:
            return
        mx, mn = self._limits()
        n = len(self.rows)
        above = sum(dv.above_max(r, mx) for r in self.rows)
        below = sum(dv.below_min(r, mn) for r in self.rows)
        cond = sum("FALSE" in dv.checks(r) for r in self.rows)
        rej = sum(dv.rejected(r) for r in self.rows)
        values = sum(len(dv.changes(o, x)) for o, x in self._pending())
        self.k_n.set(f"{n:,}")
        self.k_max.set(str(above), C["red"] if above else None)
        self.k_min.set(str(below), C["red"] if below else None)
        self.k_cond.set(str(cond), C["red"] if cond else None)
        self.k_rej.set(str(rej), C["orange"] if rej else None)
        self.k_chg.set(str(values), C["orange"] if values else None)
        self.b_save.setText(f"SAVE ({values} change{'s' if values != 1 else ''})" if values else "SAVE")
        self.b_save.setEnabled(bool(values))
        self.b_undo.setEnabled(bool(values))
        red = sum(dv.is_red(r, mx, mn) for r in self.rows)
        self.b_out.setText(f"Export Outliers ({red})")
        self.b_out.setEnabled(red > 0)
        self.b_all.setText(f"Export Basic Data ({n})")
        self.b_all.setEnabled(n > 0)
        self.b_convert.setEnabled(n > 0)
        if n == 0:
            self.status.setText(f"No experiment of {self.scope.crop_name}, sample {self.sel[1]} has Schedule 2.0 "
                                "blocks yet.")

    def run_conversion(self) -> None:
        self.rows = dv.convert_all(self.rows, self.scope.code)
        self._paint_all()

    def undo(self) -> None:
        self.rows = [dict(r) for r in self.orig]
        self._paint_all()

    def save(self) -> None:
        sc = self.scope
        edits = self._pending()
        if not edits:
            return
        mx, mn = self._limits()
        lines = []
        for o, x in edits:
            lines.append(f"{o['EXPTID']}:")
            lines += [f"     {k}:  {a or 'blank'}  →  {b or 'blank'}" for k, a, b in dv.changes(o, x)]
        still = [x["EXPTID"] for _, x in edits if dv.is_red(x, mx, mn)]
        text = (f"Save {sum(len(dv.changes(o, x)) for o, x in edits)} change(s) in {len(edits)} schedule(s)?\n\n"
                + "\n".join(lines[:18]) + ("\n     …" if len(lines) > 18 else ""))
        if still:
            text += f"\n\nNote: {len(still)} of them still fail a check."
        text += ("\n\nThe imported data stays as it is; the changes are kept in corrections.csv and every module "
                 "uses the corrected values.")
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Confirm SAVE", text,
                                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                    self)
        box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        if len(lines) > 18:
            box.setDetailedText("\n".join(lines))
        if box.exec() != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            n = dv.save(sc.state, sc.year, edits)
        except OSError as e:
            QtWidgets.QMessageBox.critical(self, "Not saved", f"The changes could not be saved:\n\n{e}")
            return
        self.orig = [dict(r) for r in self.rows]
        self._paint_all()
        self._key = None
        self.win.refresh_modules()
        toast(self, f"{n} value(s) saved.")

    def export(self, only_red: bool) -> None:
        sc = self.scope
        if not self.rows:
            return
        mx, mn = self._limits()
        try:
            out = dv.export_csv(sc.state, sc.year, self.rows, mx, mn, only_red)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the CSV file:\n\n{e}")
            return
        os.startfile(str(out))                                  # noqa: S606 (Windows)

    # ---- find
    def search(self) -> None:
        """Full Exp-ID: switch to its crop / season / sample and show only that row. Part of one: narrow the list."""
        sc, wp = self.scope, self.win.work
        text = self.find_box.text().strip()
        if not text:
            return
        if len(text) == 12:
            ml = master_list(sc, all_seasons=True)
            hit = ml[ml["EXPTID"] == text]
            if hit.empty:
                QtWidgets.QMessageBox.information(self, "Find", f"{text} is not in the {sc.state} {sc.year} "
                                                  "master list.")
                return
            r = hit.iloc[0]
            if (r["SEASONCODE"], r["SAMPLE"], r["CROPCODE"]) != self.sel:
                self.sample.blockSignals(True)
                self.sample.setCurrentIndex(max(0, self.sample.findData(r["SAMPLE"])))
                self.sample.blockSignals(False)
                for i in range(wp.season_box.count()):
                    if (wp.season_box.itemData(i) or ("",))[0] == r["SEASONCODE"]:
                        wp.season_box.setCurrentIndex(i)
                for i in range(wp.crop_box.count()):
                    if (wp.crop_box.itemData(i) or ("",))[0] == r["CROPCODE"]:
                        wp.crop_box.setCurrentIndex(i)
                self.refresh()
            idx = [i for i, row in enumerate(self.rows) if row["EXPTID"] == text]
            if not idx:
                QtWidgets.QMessageBox.information(self, "Find", self._why_not_listed(text, r))
                return
        else:
            if self.sel is None:
                QtWidgets.QMessageBox.information(self, "Find", "Type the full 12-digit Exp-ID, or choose a crop "
                                                  "first and type part of an Exp-ID to narrow its list.")
                return
            idx = [i for i, row in enumerate(self.rows) if text in row["EXPTID"]]
            if not idx:
                QtWidgets.QMessageBox.information(self, "Find", f"No Exp-ID in this list contains {text}.")
                return
        keep = set(idx)
        for i in range(len(self.rows)):
            self.table.setRowHidden(i, i not in keep)
        self.table.selectRow(idx[0])
        self.table.scrollToItem(self.table.item(idx[0], 0))
        self.b_show_all.setEnabled(len(keep) < len(self.rows))

    def _why_not_listed(self, exptid: str, ml_row) -> str:
        rc7 = schedules.rc7(self.scope.state, self.scope.year)
        name = f"{ml_row['CROPNAME']}, {ml_row['DISTRICTNAME']}"
        if rc7.empty or exptid not in set(rc7["EXPTID"]):
            return f"{exptid} ({name}) has not been received yet (NR), so there is nothing to check."
        st = str(rc7.loc[rc7["EXPTID"] == exptid, "STAGIN"].iloc[0]).replace(".0", "")
        why = {"2": "it was missed (STAGIN 2)", "3": "it was lost (STAGIN 3)"}.get(st, "its Schedule 2.0 blocks "
                                                                                     "are not stored (RC-7 only)")
        return f"{exptid} ({name}) is received but not listed: {why}, so it has no Block 5 weight."

    def show_all_rows(self) -> None:
        for i in range(len(self.rows)):
            self.table.setRowHidden(i, False)
        self.b_show_all.setEnabled(False)
        self.find_box.clear()

