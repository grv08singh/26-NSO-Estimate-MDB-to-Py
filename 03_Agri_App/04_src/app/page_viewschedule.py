"""3. View Schedule page (copy of KrishiSoft_V0.1's Print Schedules): build an Exp-ID from its parts, find it, view
the filled Schedule 2.0 form in Word or save it as PDF; several in a print list; or all imported (of the chosen
season / crop).

Exp-ID = SAMPLE (1) + STATE (2) + DISTRICT (2) + SELORDER (2) + CROPCODE (4) + EXPT (1). The state comes from the
open state; the user types the other five parts (a typed code jumps to the next box). No editing anywhere.
Files: 02_artifacts/03_viewschedule/<STATE>/<YEAR>/<CROP>/<Central|State>/ (PDF), …/word/… (forms opened in Word).
DGCES schedules have no Exp-ID yet, so they cannot be found here.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pandas as pd

from src.components import c03_viewschedule as vs
from src.utils import folders as F
from src.utils import schedules

from .look import fit_columns, button, card, flow_box, label, std_icon
from .qt import QtCore, QtGui, QtWidgets, Qt, Signal
from .window import ART, DB, StepTab, master_list

# (label, master list column, digits, hint shown before anything is typed)
PARTS = [("Sample", "SAMPLE", 1, "1 or 2"), ("District", "DISTRICT", 2, "2 digits"),
         ("Sel. order", "SELORDER", 2, "01–25"), ("Crop code", "CROPCODE", 4, "4 digits"),
         ("Expt", "EXPT", 1, "1 or 2")]
ASK_ABOVE = 50          # ask before printing more than this many schedules


class PrintWorker(QtCore.QThread):
    progress = Signal(int, int, str)
    done = Signal(object)
    crashed = Signal(str)

    def __init__(self, ml: pd.DataFrame, state: str, year: str, exptids: list, out_dir) -> None:
        super().__init__()
        self.ml, self.state, self.year, self.exptids, self.out_dir = ml, state, year, exptids, out_dir
        self.stop_requested = False

    def run(self) -> None:
        try:
            grouped = schedules.blocks_by_exptid(self.state, self.year)
            self.done.emit(vs.make_pdfs(self.ml, grouped, self.exptids, self.out_dir,
                                        lambda i, n, e: self.progress.emit(i, n, e), lambda: self.stop_requested))
        except Exception as e:
            self.crashed.emit(str(e))


class PdfPreview(QtWidgets.QDialog):
    """The Schedule 2.0 PDF shown inside the app (all pages, zoom). save_to: where 'Save PDF' copies it
    (None = it is already saved there)."""

    def __init__(self, parent, pdf: Path, title: str, save_to: Path | None = None, saved_in: Path | None = None):
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView
        from .look import fit_to_screen

        super().__init__(parent)
        self.pdf, self.save_to = pdf, save_to
        self.setWindowTitle(title)
        fit_to_screen(self, 1000, 1000)
        lay = QtWidgets.QVBoxLayout(self)
        self.doc = QPdfDocument(self)
        self.doc.load(str(pdf))
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        bar_w, bar = flow_box(spacing=8)
        bar.addWidget(label(f"{self.doc.pageCount()} page(s)", "muted", wrap=False))
        for text, fn in (("−", lambda: self._zoom(0.8)), ("+", lambda: self._zoom(1.25)),
                         ("Fit width", lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth))):
            b = button(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.note = label(f"Saved in {saved_in}" if saved_in else "", "muted", wrap=False)
        bar.addWidget(self.note)
        lay.addWidget(bar_w)
        lay.addWidget(self.view, 1)
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        if save_to is not None:
            self.b_save = button("Save PDF", primary=True, icon="SP_DialogSaveButton",
                                 tip=f"Copy this PDF to {save_to.parent}")
            self.b_save.clicked.connect(self.save)
            btns.addWidget(self.b_save)
        b_close = button("Close")
        b_close.clicked.connect(self.accept)
        btns.addWidget(b_close)
        lay.addLayout(btns)

    def _zoom(self, f: float) -> None:
        from PySide6.QtPdfWidgets import QPdfView
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.2, min(5.0, self.view.zoomFactor() * f)))

    def save(self) -> None:
        self.save_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.pdf, self.save_to)
        self.note.setText(f"Saved in {self.save_to.parent}")
        self.b_save.setEnabled(False)
        self.b_save.setText("Saved")


BLOCK_TITLES = {          # as headed in the Schedule 2.0 form (as20.docx)
    "Sch20Block1": "Block 1 – Identification and other particulars of sample village",
    "Sch20Block2": "Block 2 – Particulars of survey / sub-survey number",
    "Sch20Block3": "Block 3 – Measurement of field and selection of random coordinates",
    "Sch20Block3p1": "Block 3 (part 1) – Trees / rows in the plot",
    "Sch20Block4": "Block 4 – Location and marking of plots",
    "Sch20Block5p1": "Block 5 (part 1) – Conduct of experiment and weight of the harvest produce",
    "Sch20Block5p2": "Block 5 (part 2) – Pickings",
    "Sch20Block5p3": "Block 5 (part 3) – Several harvests",
    "Sch20Block6": "Block 6 – Details regarding equipment",
    "Sch20Block7": "Block 7 – Post-harvest operations",
    "Sch20Block8P1": "Block 8 (part 1) – Data on inputs: seed and irrigation",
    "Sch20Block8P2": "Block 8 (part 2) – Data on inputs: fertilizers, manure, pesticides",
    "Sch20Block9P1": "Block 9 (part 1) – Crop condition",
    "Sch20Block9P2": "Block 9 (part 2) – Area under the crop",
    "Sch20Block10": "Block 10 / 11 – Measurement of the field (potato: L1, L2) and remarks",
    "Sch20Block12": "Block 12 – Particulars of field work and movement of schedules",
    "Sch20RC7": "RC-7 – Record type 7",
}
HIDE = {"EXPTID", "YR", "SOURCE", "SOURCE_FILE", "FILE_TIME", "DGCES_KEY", "UID", "created_at", "CROPCODE"}


class BlockView(QtWidgets.QDialog):
    """One schedule, block by block (read-only, Data Validation corrections included); Print as PDF at the end."""

    def __init__(self, tab: "ViewScheduleTab", exptid: str, ml_row: dict, blocks: dict, rc7_row: dict | None):
        from src.utils.schedule20 import BLOCK_TABLES, SRLDESC
        from .look import fit_to_screen

        super().__init__(tab)
        self.tab, self.exptid, self.printed = tab, exptid, False
        self.setWindowTitle(f"Schedule 2.0 – {exptid}")
        fit_to_screen(self, 1150, 780)
        lay = QtWidgets.QVBoxLayout(self)
        m = ml_row
        lay.addWidget(label(f"{exptid}", "h2", wrap=False))
        lay.addWidget(label(f"{str(m.get('SEASONNAME', '')).title()} · {str(m.get('SAMPLENAME', '')).title()} · "
                            f"{str(m.get('DISTRICTNAME', '')).title()} ({m.get('DISTRICT', '')}) · "
                            f"{m.get('CROPNAME', '')} ({m.get('CROPCODE', '')}) · Sel. order {m.get('SELORDER', '')} · "
                            f"Expt {m.get('EXPT', '')} · PRTID {vs.prtid(m)}", "muted"))
        split = QtWidgets.QSplitter()
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("moduleNav")
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        self.block_title = label("", "h3")
        rl.addWidget(self.block_title)
        rl.addWidget(self.table, 1)
        split.addWidget(self.list)
        split.addWidget(right)
        split.setSizes([300, 850])
        lay.addWidget(split, 1)
        self.data: list[tuple[str, pd.DataFrame]] = []
        for t in BLOCK_TABLES + ["Sch20RC7"]:
            df = pd.DataFrame([rc7_row]) if t == "Sch20RC7" and rc7_row else blocks.get(t, pd.DataFrame())
            if t == "Sch20RC7" and not rc7_row:
                df = pd.DataFrame()
            if not df.empty and "SRL" in df.columns and t in SRLDESC:
                df = df.copy()
                df.insert(df.columns.get_loc("SRL") + 1, "ITEM",
                          [SRLDESC[t].get(int(float(x)), "") if str(x).replace(".0", "").isdigit() else ""
                           for x in df["SRL"]])
            self.data.append((t, df))
            item = QtWidgets.QListWidgetItem(BLOCK_TITLES.get(t, t).split(" – ")[0]
                                             + ("" if not df.empty else "  (not filled)"))
            item.setToolTip(BLOCK_TITLES.get(t, t))
            if df.empty:
                item.setForeground(QtGui.QColor("#9AAA9C"))
            self.list.addItem(item)
        self.list.currentRowChanged.connect(self._show)
        self.list.setCurrentRow(0)
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(label("Read-only · values as stored (Data Validation corrections included)", "muted"))
        bar.addStretch(1)
        b_pdf = button("Print as PDF", primary=True, icon="SP_DialogSaveButton",
                       tip="Fill the Schedule 2.0 form and save it as PDF (Microsoft Word)")
        b_pdf.clicked.connect(self._print)
        b_close = button("Close")
        b_close.clicked.connect(self.reject)
        bar.addWidget(b_pdf)
        bar.addWidget(b_close)
        lay.addLayout(bar)

    def _show(self, i: int) -> None:
        t, df = self.data[i]
        self.block_title.setText(BLOCK_TITLES.get(t, t))
        cols = [c for c in df.columns if c not in HIDE] if not df.empty else []
        if df.empty:
            self.table.setRowCount(0)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["Nothing filled in this block"])
        elif len(df) == 1:                                     # one row: field -> value
            rec = df.iloc[0]
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["Field", "Value"])
            self.table.setRowCount(len(cols))
            for r, c in enumerate(cols):
                self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(c))
                v = rec.get(c, "")
                self.table.setItem(r, 1, QtWidgets.QTableWidgetItem("" if str(v) in ("nan", "None") else str(v)))
        else:                                                  # several rows (SRL): a table
            self.table.setColumnCount(len(cols))
            self.table.setHorizontalHeaderLabels(cols)
            self.table.setRowCount(len(df))
            for r, rec in enumerate(df[cols].astype(str).values.tolist()):
                for c, v in enumerate(rec):
                    self.table.setItem(r, c, QtWidgets.QTableWidgetItem("" if v in ("nan", "None") else v))
        fit_columns(self.table)
        self.table.horizontalHeader().setStretchLastSection(True)

    def _print(self) -> None:
        self.printed = True
        self.accept()
        self.tab.start_print([self.exptid], "one")


class ViewScheduleTab(StepTab):
    number, title, tab = 3, "View Schedule", "View Schedule"

    @property
    def folder(self):                       # 02_artifacts/03_viewschedule/<STATE>/<YEAR>/
        sc = self.scope
        return ART / F.VIEW_SCHEDULE / sc.state / sc.year if sc.ok else ART / F.VIEW_SCHEDULE

    def __init__(self, win) -> None:
        super().__init__(win)
        self.b_run.hide()
        self.ml = pd.DataFrame()
        self.imported = pd.DataFrame(columns=["EXPTID"])
        self.found: str | None = None
        self.print_list: list[str] = []
        self.worker: PrintWorker | None = None
        self._key = None
        self.b_all = button("Print all", icon="SP_FileDialogListView",
                            tip="Every imported schedule of the chosen season / crop as PDF")
        self.b_all.clicked.connect(lambda: self.start_print(self._all_ids(), "all"))
        self.add_action(self.b_all)
        self.k_imp = self.kpi("imported (printable)")
        self.k_list = self.kpi("in print list")

        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(4, 10, 4, 4)
        lay.setSpacing(8)

        # --- Exp-ID parts
        lay.addWidget(label("Find a schedule – type the parts of the Exp-ID and press Search (or Enter)", "h3"))
        # every cell has the same shape (label on top, box below) so labels, boxes and buttons line up;
        # what a typed code means is shown in one line under the row, not under each box
        parts_w, parts = flow_box(spacing=10)
        self.boxes: dict[str, QtWidgets.QLineEdit] = {}
        self.hints: dict[str, str] = {}

        def cell(title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            c = QtWidgets.QWidget()
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            cl.addWidget(QtWidgets.QLabel(title))
            cl.addWidget(widget)
            return c

        for lab, col, digits, hint in PARTS[:1] + [("State", "STATE", 2, "")] + PARTS[1:]:
            box = QtWidgets.QLineEdit()
            box.setFixedWidth(64 + 12 * digits)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == "STATE":                          # fixed: the open state
                box.setReadOnly(True)
                box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                box.setStyleSheet("background: #F1F5EF; color: #1F4D2B; font-weight: 700;")
                self.state_box = box
            else:
                box.setMaxLength(digits)
                box.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(rf"\d{{0,{digits}}}")))
                box.setPlaceholderText(hint)
                box.textEdited.connect(lambda _t, col=col: self._part_typed(col))
                box.returnPressed.connect(self.search)
                self.boxes[col], self.hints[col] = box, ""
            parts.addWidget(cell(lab, box))
        btns = QtWidgets.QWidget()
        bl = QtWidgets.QHBoxLayout(btns)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        self.b_search = button("Search", primary=True, icon="SP_FileDialogContentsView")
        self.b_search.clicked.connect(self.search)
        b_clear = button("Clear")
        b_clear.clicked.connect(self.clear_parts)
        bl.addWidget(self.b_search)
        bl.addWidget(b_clear)
        parts.addWidget(cell(" ", btns))
        lay.addWidget(parts_w)
        self.exptid_lb = label("", "muted")
        lay.addWidget(self.exptid_lb)

        # --- details of the schedule found
        self.details, dl = card(12, 6)
        self.details_text = QtWidgets.QLabel()
        self.details_text.setWordWrap(True)
        self.details_text.setTextFormat(Qt.TextFormat.RichText)
        dl.addWidget(self.details_text)
        dbar_w, dbar = flow_box(right=True)
        self.b_view = button("View", icon="SP_FileDialogContentsView",
                             tip="See the schedule block by block; Print as PDF from there")
        self.b_view.clicked.connect(self.view_blocks)
        self.b_add = button("Add to print list", icon="SP_FileDialogNewFolder")
        self.b_add.clicked.connect(self.add_to_list)
        self.b_one = button("Print this as PDF", primary=True, icon="SP_DialogSaveButton")
        self.b_one.clicked.connect(lambda: self.start_print([self.found], "one"))
        for b in (self.b_view, self.b_add, self.b_one):
            dbar.addWidget(b)
        dl.addWidget(dbar_w)
        self.details.setVisible(False)
        lay.addWidget(self.details)

        # --- print list
        lbar_w, lbar = flow_box(spacing=8)
        lbar.addWidget(label("Print list", "h3", wrap=False))
        self.b_clear_list = button("Clear list")
        self.b_clear_list.clicked.connect(self.clear_list)
        self.b_print_list = button("Print list as PDF", primary=True, icon="SP_DialogSaveButton")
        self.b_print_list.clicked.connect(lambda: self.start_print(list(self.print_list), "list"))
        lbar.addWidget(self.b_clear_list)
        lbar.addWidget(self.b_print_list)
        lay.addWidget(lbar_w)
        self.list_text = label("", "muted")
        lay.addWidget(self.list_text)

        # --- progress
        prog = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.b_stop = button("Stop")
        self.b_stop.clicked.connect(self.stop_print)
        prog.addWidget(self.progress, 1)
        prog.addWidget(self.b_stop)
        lay.addLayout(prog)
        self.progress_text = label("", "muted")
        lay.addWidget(self.progress_text)
        for w in (self.progress, self.b_stop, self.progress_text):
            w.setVisible(False)
        lay.addStretch(1)
        self.body.addTab(page, "Find, view and print")
        self.more.addAction(std_icon("SP_DirOpenIcon"), "Open PDF folder", self._open_pdf_folder)

    # ---- data
    def refresh(self) -> None:
        sc = self.scope
        if not sc.ok or self.worker:
            return
        ml_file = DB / F.MASTER_LIST / sc.state / sc.year / "master_list.csv"
        key = (sc.state, sc.year, schedules.stamp(sc.state, sc.year), ml_file.stat().st_mtime_ns if ml_file.exists() else 0)
        if key != self._key:
            self._key = key
            self.ml = master_list(sc, all_seasons=True)
            b1 = schedules.blocks(sc.state, sc.year).get("Sch20Block1", pd.DataFrame())
            self.imported = vs.schedule_list(self.ml, schedules.rc7(sc.state, sc.year), b1)
            self.print_list = [e for e in self.print_list if e in set(self.imported["EXPTID"])]
            self.clear_parts()
        self.state_box.setText(sc.code or "–")
        self.state_box.setToolTip(sc.state.title())
        self._update()

    def _all_ids(self) -> list[str]:
        """Imported schedules of the chosen season / crop."""
        scope_ids = set(master_list(self.scope)["EXPTID"]) if not self.ml.empty else set()
        return [e for e in self.imported["EXPTID"] if e in scope_ids]

    # ---- Exp-ID parts
    def _names(self, col: str, code: str) -> str:
        if self.ml.empty or not code:
            return ""
        rows = self.ml[self.ml[col] == code]
        if rows.empty:
            return "not in master list"
        if col == "SAMPLE":
            return rows["SAMPLENAME"].iloc[0].title()
        if col == "DISTRICT":
            return rows["DISTRICTNAME"].iloc[0].title()
        if col == "CROPCODE":
            return f"{rows['CROPNAME'].iloc[0]} · {rows['SEASONNAME'].iloc[0].title()}"
        return ""

    def _part_typed(self, col: str) -> None:
        box = self.boxes[col]
        full = len(box.text()) == box.maxLength()
        self.hints[col] = self._names(col, box.text()) if full else ""
        if full:                                       # jump to the next box, like filling a form
            cols = list(self.boxes)
            i = cols.index(col)
            if i + 1 < len(cols):
                self.boxes[cols[i + 1]].setFocus()
                self.boxes[cols[i + 1]].selectAll()
        self.details.setVisible(False)
        self.found = None
        self._show_exptid()
        self._update()

    def _built_id(self) -> tuple[str, list[str]]:
        """(Exp-ID from the boxes, names of empty parts). Short codes get leading zeros (1 -> 01)."""
        parts, missing = {}, []
        for lab, col, digits, _ in PARTS:
            text = self.boxes[col].text().strip()
            if not text:
                missing.append(lab)
            parts[col] = text.zfill(digits)
        return (parts["SAMPLE"] + self.scope.code.zfill(2) + parts["DISTRICT"] + parts["SELORDER"]
                + parts["CROPCODE"] + parts["EXPT"]), missing

    def _show_exptid(self) -> None:
        """Exp-ID line under the boxes, with what each typed code means (Central · Bihar · E.Champaran · …)."""
        exptid, missing = self._built_id()
        typed = any(b.text() for b in self.boxes.values())
        names = [self.hints.get("SAMPLE", ""), self.scope.state.title() if typed else "", self.hints.get("DISTRICT", ""),
                 f"Sel. order {self.boxes['SELORDER'].text()}" if self.boxes["SELORDER"].text() else "",
                 self.hints.get("CROPCODE", ""),
                 f"Expt {self.boxes['EXPT'].text()}" if self.boxes["EXPT"].text() else ""]
        meaning = "  ·  ".join(n for n in names if n)
        self.exptid_lb.setText(f"Exp-ID: <b>{exptid if not missing else '…'}</b>"
                               + (f"   (still to fill: {', '.join(missing)})" if missing else "")
                               + (f"<br>{meaning}" if meaning else ""))

    def clear_parts(self) -> None:
        for col, box in self.boxes.items():
            box.clear()
            self.hints[col] = ""
        self.found = None
        self.details.setVisible(False)
        self._show_exptid()

    def search(self) -> None:
        sc = self.scope
        exptid, missing = self._built_id()
        if missing:
            self._show_exptid()
            return
        for _lab, col, digits, _ in PARTS:                      # show the padded codes back in the boxes
            self.boxes[col].setText(self.boxes[col].text().zfill(digits))
            self.hints[col] = self._names(col, self.boxes[col].text())
        self._show_exptid()
        self.found = None
        m = self.ml[self.ml["EXPTID"] == exptid] if not self.ml.empty else pd.DataFrame()
        imp = self.imported[self.imported["EXPTID"] == exptid]
        if m.empty:
            html = (f"<b style='color:#b3261e'>{exptid} is not in the {sc.state} {sc.year} master list.</b><br>"
                    "Check the codes (the names under the boxes show what each code is).")
        else:
            r = m.iloc[0]
            info = [("Season", r["SEASONNAME"].title()), ("Sample", str(r["SAMPLENAME"]).title()),
                    ("District", f"{r['DISTRICTNAME'].title()} ({r['DISTRICT']})"),
                    ("Crop", f"{r['CROPNAME']} ({r['CROPCODE']})"), ("Sel. order", r["SELORDER"]),
                    ("Expt", r["EXPT"]), ("RO / SRO", f"{r['RONAME'].title()} / {r['SRONAME'].title()}"),
                    ("PRTID", vs.prtid(r.to_dict()))]
            if imp.empty:
                head = (f"<b style='color:#8a6d00'>{exptid} is in the master list but has not been imported "
                        "yet – nothing to show.</b>")
            else:
                i = imp.iloc[0]
                self.found = exptid
                info += [("Village", i["VILLAGE"] or "—"), ("Imported from", i["SOURCES"]),
                         ("Schedule 2.0 blocks", "stored" if i["BLOCKS"] == "Yes"
                          else "not stored (RC-7 only): block parts stay blank")]
                head = f"<b style='color:#1b5e20'>{exptid} found.</b>"
            half = (len(info) + 1) // 2                          # two columns keep the box short
            cell = lambda k, v: (f"<td style='padding-right:14px;color:#56685A'>{k}</td>"   # noqa: E731
                                 f"<td style='padding-right:36px'>{v}</td>")
            rows = "".join("<tr>" + cell(*info[i]) + (cell(*info[i + half]) if i + half < len(info) else "")
                           + "</tr>" for i in range(half))
            html = f"{head}<table style='margin-top:6px'>{rows}</table>"
        self.details_text.setText(html)
        self.details.setVisible(True)
        self._update()

    # ---- view / print list
    def view_blocks(self) -> None:
        """The schedule block by block in a window; Print as PDF from there."""
        if not self.found:
            return
        sc = self.scope
        row = self.ml[self.ml["EXPTID"] == self.found].iloc[0].to_dict()
        rc = schedules.rc7(sc.state, sc.year)
        hit = rc[rc["EXPTID"] == self.found] if not rc.empty else rc
        BlockView(self, self.found, row, schedules.blocks(sc.state, sc.year, self.found),
                  hit.iloc[0].to_dict() if len(hit) else None).exec()

    def add_to_list(self) -> None:
        if self.found and self.found not in self.print_list:
            self.print_list.append(self.found)
        self.clear_parts()
        self._update()

    def clear_list(self) -> None:
        self.print_list = []
        self._update()

    def _update(self) -> None:
        busy = self.worker is not None
        for box in self.boxes.values():
            box.setEnabled(not busy)
        self.b_search.setEnabled(not busy)
        in_list = bool(self.found) and self.found in self.print_list
        self.b_one.setEnabled(self.found is not None and not busy)
        self.b_view.setEnabled(self.found is not None and not busy)
        self.b_add.setEnabled(self.found is not None and not in_list and not busy)
        self.b_add.setText("Already in print list" if in_list else "Add to print list")
        n = len(self.print_list)
        self.list_text.setText(", ".join(self.print_list) if n else
                               "Empty. Search a schedule and press “Add to print list” to print several together.")
        self.b_print_list.setText(f"Print list as PDF ({n})")
        self.b_print_list.setEnabled(n > 0 and not busy)
        self.b_clear_list.setEnabled(n > 0 and not busy)
        total = len(self._all_ids()) if not self.imported.empty else 0
        self.b_all.setText(f"Print all ({total:,})")
        self.b_all.setEnabled(total > 0 and not busy)
        self.k_imp.set(f"{total:,}")
        self.k_list.set(str(n))
        self.status.setText("" if total else
                            f"No imported schedule for {self.scope.state} {self.scope.year} (this season / crop) yet.")

    def _open_pdf_folder(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.folder))                          # noqa: S606 (Windows)

    # ---- print
    def start_print(self, exptids: list, what: str) -> None:
        sc = self.scope
        if not exptids or self.worker:
            return
        n = len(exptids)
        if n > ASK_ABOVE:
            which = "ALL imported schedules" if what == "all" else "the print list"
            if QtWidgets.QMessageBox.question(
                    self, "Print many schedules", f"Print {which}: {n:,} PDFs?\n\nThis can take a while (Word makes "
                    "each PDF). You can press Stop at any time; PDFs already made are kept.") \
                    != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self._what, self._started = what, time.monotonic()
        self.progress.setRange(0, n)
        self.progress.setValue(0)
        for w in (self.progress, self.b_stop, self.progress_text):
            w.setVisible(True)
        self.b_stop.setEnabled(True)
        self.progress_text.setText("Making the form with Microsoft Word …")
        self._tmp = tempfile.mkdtemp(prefix="krishistat_view_") if what == "view" else None
        self.worker = PrintWorker(self.ml, sc.state, sc.year, exptids, Path(self._tmp) if self._tmp else self.folder)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.crashed.connect(lambda msg: QtWidgets.QMessageBox.critical(self, "Printing stopped", msg))
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        self._update()

    def _on_progress(self, i: int, n: int, exptid: str) -> None:
        self.progress.setValue(i - 1)
        text = f"Making the form of {exptid}" if self._what == "view" else f"Printing {i:,} of {n:,}: {exptid}"
        if i > 2:
            left = (time.monotonic() - self._started) / (i - 1) * (n - i + 1)
            text += f"   ·   about {left / 60:.0f} min left" if left >= 90 else f"   ·   about {left:.0f} s left"
        self.progress_text.setText(text)

    def stop_print(self) -> None:
        if self.worker:
            self.worker.stop_requested = True
            self.b_stop.setEnabled(False)
            self.progress_text.setText(self.progress_text.text().split("   ·")[0] + "   ·   stopping after this one …")

    def _on_done(self, results) -> None:
        ok = [r for r in results if r[1]]
        bad = [r for r in results if not r[1]]
        if self._what in ("view", "one") and len(results) == 1:       # one schedule: show it here
            if not ok:
                QtWidgets.QMessageBox.warning(self, "View schedule", f"Could not make the form:\n\n{bad[0][2]}")
            else:
                e, pdf, _ = ok[0]
                row = self.ml[self.ml["EXPTID"] == e].iloc[0].to_dict()
                if self._what == "view":
                    target = self.folder / vs.crop_sample_folder(row) / pdf.name
                    dlg = PdfPreview(self, pdf, f"Schedule 2.0 – {e}", save_to=target)
                else:
                    dlg = PdfPreview(self, pdf, f"Schedule 2.0 – {e} (saved)", saved_in=pdf.parent)
                dlg.exec()
            if self._tmp:
                shutil.rmtree(self._tmp, ignore_errors=True)
            return
        stopped = self.worker is not None and self.worker.stop_requested and len(results) < len(self.worker.exptids)
        if self._what == "list" and not bad and not stopped:
            self.print_list = []                       # printed: start a fresh list
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Printing stopped" if stopped else "Printing finished")
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning if bad or stopped else QtWidgets.QMessageBox.Icon.Information)
        folders = sorted({p.parent for _, p, _ in ok})
        text = f"{len(ok):,} PDF(s) saved" + (f" in {folders[0]}." if len(folders) == 1 else
                                             f" in {len(folders)} crop / sample folders." if folders else ".")
        if stopped:
            text = f"Stopped by you after {len(results):,} of {len(self.worker.exptids):,}.\n" + text
        if bad:
            text += f"\n{len(bad):,} could not be printed (see details)."
            box.setDetailedText("\n".join(f"{e}: {err}" for e, _, err in bad))
        box.setText(text)
        open_btn = None
        if ok:
            open_btn = box.addButton("Open PDF" if len(ok) == 1 else "Open folder",
                                     QtWidgets.QMessageBox.ButtonRole.ActionRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Close)
        box.exec()
        if open_btn is not None and box.clickedButton() is open_btn:
            os.startfile(str(ok[0][1] if len(ok) == 1 else (folders[0] if len(folders) == 1 else self.folder)))

    def _on_finished(self) -> None:
        self.worker = None
        for w in (self.progress, self.b_stop, self.progress_text):
            w.setVisible(False)
        self._update()
