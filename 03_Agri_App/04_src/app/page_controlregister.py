"""2. Control Register page (copy of KrishiSoft_V0.1's Control Register module, two parts):

  counts + By crop + By RO / SRO   planned vs received, harvested / missed / lost / rejected (old AS 2.0 report)
  NR (Not Received)                the planned experiments without a schedule; office-format NR Excel files

Season / Crop come from the work page; Sample from the box in the header. Everything is worked out when the page
is shown (no Run): from the stored master list and the imported schedules of the open state + year.
"""
from __future__ import annotations

import os

import pandas as pd

from src.components import c02_controlregister_summary as cr
from src.utils import folders as F
from src.utils import schedules

from .look import button, flow_box, label, toast
from .qt import QtGui, QtWidgets
from .window import ART, C, DB, ROOT, YELLOW, DataView, StepTab, master_list

GREY = QtGui.QColor("#EEF1F4")


def _pct(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "Harvest %" in df.columns:
        df = df.assign(**{"Harvest %": df["Harvest %"].map(lambda v: f"{v:.2f}")})
    return df


def _total_rows(rec, col):
    return GREY if rec.get("Crop") == "TOTAL" or rec.get("SRO") in ("TOTAL", "RO TOTAL") else None


class ControlRegisterTab(StepTab):
    number, title, tab = 2, "Control Register", "Control Register"

    @property
    def folder(self):                       # 02_artifacts/02_controlregister/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.CONTROL_REGISTER / sc.state / sc.year if sc.ok else ART / F.CONTROL_REGISTER

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()                     # worked out when shown
        self._key = None
        self.full = pd.DataFrame()            # every planned experiment of the state + year, with status
        self.not_in_ml = pd.DataFrame()       # imported RC-7 not in the master list
        self.dg = pd.DataFrame()             # DGCES experiments of the state + year

        b_exp = button("Export (CSV)", icon="SP_DialogSaveButton",
                       tip="Summary, By crop and By RO / SRO as CSV files in 02_controlregister/<STATE>/<YEAR>/")
        b_exp.clicked.connect(self.export)
        self.add_action(b_exp)
        pick = QtWidgets.QWidget()                     # Sample, next to the buttons in the top row
        pl = QtWidgets.QHBoxLayout(pick)
        pl.setContentsMargins(0, 0, 8, 0)
        pl.addWidget(label("Sample", "muted", wrap=False))
        self.sample = QtWidgets.QComboBox()
        self.sample.addItem("All", "")
        self.sample.addItem("Central (1)", "1")
        self.sample.addItem("State (2)", "2")
        self.sample.currentIndexChanged.connect(lambda *_: self.show_register())
        pl.addWidget(self.sample)
        self.actions.insertWidget(0, pick)

        self.k = {name: self.kpi(name.lower()) for name in cr.COLUMNS}
        self.k_extra = self.kpi("not in master list")
        self.k_dg = self.kpi("DGCES (not linked)")

        self.crop_view = DataView("", 90)
        self.ro_view = DataView("", 120)
        self.nr = NRView(self)
        self.extra_view = DataView("", 90)
        self.body.addTab(self.crop_view, "By crop")
        self.body.addTab(self.ro_view, "By RO / SRO")
        self.body.addTab(self.nr, "NR (Not Received)")
        self.body.addTab(self.extra_view, "Received, not in master list")

    # ---- data
    def _load(self) -> None:
        sc = self.scope
        ml_file = DB / F.MASTER_LIST / sc.state / sc.year / "master_list.csv"
        key = (sc.state, sc.year, schedules.stamp(sc.state, sc.year), ml_file.stat().st_mtime_ns if ml_file.exists() else 0)
        if key == self._key:
            return
        self._key = key
        ml = master_list(sc, all_seasons=True)
        self.full, self.not_in_ml = cr.build(ml, schedules.rc7(sc.state, sc.year))
        self.dg = schedules.dgces_ids(sc.state, sc.year)

    def part(self) -> pd.DataFrame:
        """Planned experiments of the chosen season / crop (work page)."""
        df, sc = self.full, self.scope
        if df.empty:
            return df
        if sc.season:
            df = df[df["SEASONCODE"] == sc.season]
        if sc.crop:
            df = df[df["CROPCODE"] == sc.crop]
        return df

    def refresh(self) -> None:
        if not self.scope.ok:
            return
        self._load()
        self.show_register()
        self.nr.fill()

    def show_register(self) -> None:
        sc = self.scope
        df = cr.filter_sample(self.part(), self.sample.currentData())
        t = cr.totals(df)
        for name, v in t.items():
            self.k[name].set(f"{v:.2f}" if name == "Harvest %" else f"{v:,}",
                             C["orange"] if name == "Not received" and v else
                             C["green"] if name in ("Received", "Harvested") and v else None)
        self.k_extra.set(f"{len(self.not_in_ml):,}", C["orange"] if len(self.not_in_ml) else None)
        dg = self.dg
        if not dg.empty and sc.season:
            dg = dg[dg["SEASON"].str.upper() == sc.season_name.upper()]
        if not dg.empty and self.sample.currentData():
            dg = dg[dg["SAMPLE"] == self.sample.currentData()]
        self.k_dg.set(f"{len(dg):,}")
        self.crop_view.set_frame(_pct(cr.by_crop(df)), bg=_total_rows)
        self.ro_view.set_frame(_pct(cr.by_ro_sro(df)), bg=_total_rows)
        self.extra_view.set_frame(self.not_in_ml)
        self.status.setText("No master list for this state + year." if self.full.empty else "")

    # ---- actions
    def export(self) -> None:
        sc = self.scope
        df = cr.filter_sample(self.part(), self.sample.currentData())
        if df.empty:
            return
        what = ", ".join(x for x in (sc.season_name, sc.crop_name, self.sample.currentText()
                                     if self.sample.currentData() else "") if x) or "All experiments"
        try:
            out = cr.export_csv(self.folder / "control_register", df, self.not_in_ml,
                                {"State + Year": f"{sc.state} {sc.year}", "Showing": what})
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the CSV files:\n\n{e}")
            return
        toast(self, f"Control Register saved: {out.relative_to(ROOT) if out.is_absolute() else out}")
        os.startfile(str(out))                                  # noqa: S606 (Windows)


class NRView(QtWidgets.QWidget):
    """NR tab: Season / Sample / Crop lists that only offer what still has NR (with counts), the NR list, export."""
    LISTS = [("Season", "SEASONCODE"), ("Sample", "SAMPLE"), ("Crop", "CROPCODE")]

    def __init__(self, tab: ControlRegisterTab) -> None:
        super().__init__()
        self.tab = tab
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        row_w, row = flow_box(spacing=8)
        self.combos: dict[str, QtWidgets.QComboBox] = {}
        for name, col in self.LISTS:
            combo = QtWidgets.QComboBox()
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(22)
            combo.currentIndexChanged.connect(lambda *_: self.fill())
            pair = QtWidgets.QWidget()
            pl = QtWidgets.QHBoxLayout(pair)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.addWidget(QtWidgets.QLabel(name))
            pl.addWidget(combo)
            row.addWidget(pair)
            self.combos[col] = combo
        b_all = button("Show all")
        b_all.clicked.connect(self.clear)
        row.addWidget(b_all)
        self.b_export = button("Export NR (Excel)", primary=True, icon="SP_DialogSaveButton",
                               tip="Office-format NR files: one per season + crop + sample, in NR/<date>/Central|State/")
        self.b_export.clicked.connect(self.export)
        row.addWidget(self.b_export)
        b_open = button("Open NR folder", icon="SP_DirOpenIcon")
        b_open.clicked.connect(lambda: self._open_folder())
        row.addWidget(b_open)
        lay.addWidget(row_w)
        self.status = label("", "muted")
        lay.addWidget(self.status)
        self.view = DataView("", 100)
        lay.addWidget(self.view, 1)

    def _open_folder(self) -> None:
        f = self.tab.folder / "NR"
        f.mkdir(parents=True, exist_ok=True)
        os.startfile(str(f))                                    # noqa: S606 (Windows)

    def _chosen(self) -> dict:
        return {col: c.currentData() for col, c in self.combos.items() if c.currentIndex() > 0 and c.currentData()}

    def _filtered(self, skip: str | None = None) -> pd.DataFrame:
        df = self.tab.part()
        for col, code in self._chosen().items():
            if col != skip and not df.empty:
                df = df[df[col] == code]
        return df

    def clear(self) -> None:
        for c in self.combos.values():
            c.blockSignals(True)
            c.setCurrentIndex(0)
            c.blockSignals(False)
        self.fill()

    def fill(self) -> None:
        """Each list: 'All' + the values that still have NR given the other choices, with NR counts."""
        for col, combo in self.combos.items():
            keep = combo.currentData() if combo.currentIndex() > 0 else None
            part = self._filtered(skip=col)
            left = part[~part["RECEIVED"]] if not part.empty else part
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"All  —  {len(left):,} NR", None)
            if not left.empty:
                first = left.drop_duplicates(col).set_index(col)
                if col == "SEASONCODE":
                    names = first["SEASONNAME"].str.title()
                elif col == "SAMPLE":
                    names = first["SAMPLENAME"].str.title()
                else:
                    names = first["CROPNAME"] + "  ·  " + first["SEASONNAME"].str.title() + "  (" + first.index + ")"
                counts = left[col].value_counts()
                order = left.drop_duplicates(col).assign(
                    _s=lambda d: pd.to_numeric(d["SEASONCODE"], errors="coerce")).sort_values(["_s", col])[col]
                for code in order:
                    combo.addItem(f"{names[code]}  —  {counts[code]:,} NR", code)
            i = combo.findData(keep) if keep is not None else 0
            combo.setCurrentIndex(max(0, i))
            combo.blockSignals(False)
        part = self._filtered()
        rows = cr.nr_list(part)
        self.view.set_frame(rows, bg=lambda rec, col: YELLOW if col == "Exp-ID" else None)
        self.b_export.setEnabled(not rows.empty)
        self.b_export.setText(f"Export NR (Excel, {len(rows):,})" if not rows.empty else "Export NR (Excel)")
        planned = len(part)
        self.status.setText("" if part.empty and self.tab.full.empty else
                            f"<b>No NR</b>: all {planned:,} planned schedules received." if rows.empty else
                            f"<b>NR schedules: {len(rows):,}</b> of {planned:,} planned.")

    def export(self) -> None:
        sc = self.tab.scope
        if self.tab.full.empty:
            return
        try:
            day, files = cr.export_nr_excel(self.tab.folder / "NR", sc.year, self.tab.full, self._filtered(),
                                            one_crop="CROPCODE" in self._chosen() or bool(sc.crop))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export failed", f"Could not write the NR files:\n\n{e}\n\n"
                                          "If one of them is open in Excel, close it and try again.")
            return
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("NR exported")
        box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        box.setText(f"{len(files)} NR file(s) saved in NR\\{day.name} (Central and State folders).")
        box.setDetailedText("\n".join(f"{f.parent.name}\\{f.name}" for f in files))
        open_btn = box.addButton("Open folder", QtWidgets.QMessageBox.ButtonRole.ActionRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            os.startfile(str(day))                              # noqa: S606 (Windows)

