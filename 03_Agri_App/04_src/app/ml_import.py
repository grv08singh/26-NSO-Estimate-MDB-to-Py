"""Import Master List (States page): check → review → confirm → store.

1. Every picked file is checked on its own (KrishiSoft rules, lenient: spaces, hidden characters, column names,
   extra columns, several sheets, exact repeats are cleaned and listed).
2. A file with real problems is rejected: its error report (CSV files: Read me, Rules, Problem count, Errors,
   Marked data with a PROBLEMS column, Cleaned) goes to 02_artifacts/00_masterlist/<STATE>/<YEAR>/errors/<file>_ERRORS/; it is NOT copied into raw data.
3. A file that passes is compared with what is stored for its state + year, season by season (a file replaces only
   the seasons it contains). The review shows it all; nothing is stored until 'Import' is pressed.
4. Import: the passed files are copied into 01_raw_data/00_masterlist/<STATE>/<YEAR>/ and the master list step stores them
   (the old list goes to 05_backup first).
"""
from __future__ import annotations

from src.utils import folders as F
import os
from pathlib import Path

import pandas as pd

from .look import fit_columns, button, fit_to_screen, label
from .qt import QtWidgets, Qt


def check_files(paths: list, art: Path, db: Path) -> list[dict]:
    """Runs in the background: check and compare every picked file (nothing is stored)."""
    import logging
    from src.utils import masterlist_checks, masterlist_compare

    log = logging.getLogger()
    received = art / F.IMPORT_SCHEDULES / "ingested_sch.csv"
    uids = set(pd.read_csv(received, dtype=str, usecols=["UID"])["UID"]) if received.exists() else set()
    out = []
    for p in map(Path, paths):
        res = masterlist_checks.check_file(p)
        state, year = res.state.upper(), res.year
        r = {"path": str(p), "file": p.name, "state": state, "year": year, "rows": len(res.data),
             "sheets": ", ".join(res.sheets), "fixes": masterlist_checks._issue_frame(res.fixes), "ok": res.ok}
        if not res.ok:
            folder = art / F.MASTER_LIST / (state or "UNKNOWN-STATE") / (year or "UNKNOWN-YEAR") / "errors"
            r["report"] = str(masterlist_checks.write_error_report(res, folder))
            errs = masterlist_checks._issue_frame(res.issues)
            r["problems"] = (errs.groupby(["Column", "Problem"]).size().reset_index(name="Count")
                             .sort_values("Count", ascending=False))
            log.warning(f"{p.name}: REJECTED - {len(res.issues)} problem(s); report {r['report']}")
        else:
            new = masterlist_checks.with_exptid(res.data)
            f = db / F.MASTER_LIST / state / year / "master_list.csv"
            stored = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig") if f.exists() \
                else pd.DataFrame()
            r["cmp"] = masterlist_compare.compare(new, stored, uids)
            r["experiments"] = len(new)
            r["crop"], r["sample"] = _file_summaries(new)
            log.info(f"{p.name}: passed - {state} {year}, {len(new)} experiments, {len(res.fixes)} item(s) cleaned")
        out.append(r)
    return out


def _file_summaries(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(crop-wise, sample-wise) counts of the experiments in a file: Central / State / Total, with a TOTAL row."""
    from src.utils.masterlist_checks import SAMPLE_NAMES
    df = df.assign(Season=df["SEASONNAME"].str.upper() + " (" + df["SEASONCODE"] + ")",
                   S=df["SAMPLE"].map(SAMPLE_NAMES).fillna("OTHER"))
    cols = [c for c in list(SAMPLE_NAMES.values()) + ["OTHER"] if c != "OTHER" or (df["S"] == "OTHER").any()]
    names = {"CENTRAL": "Central", "STATE": "State", "OTHER": "Other sample"}

    def count(keys: list) -> pd.DataFrame:
        t = df.groupby(keys + ["S"]).size().unstack("S", fill_value=0).reindex(columns=cols, fill_value=0)
        t["Total"] = t.sum(axis=1)
        t = t.reset_index().sort_values(keys[:1], key=lambda s: s.str.extract(r"\((\d+)\)")[0].astype(int),
                                        kind="stable")
        total = {k: "" for k in keys} | {c: int(t[c].sum()) for c in cols + ["Total"]}
        total[keys[0]] = "TOTAL"
        return pd.concat([t, pd.DataFrame([total])], ignore_index=True).rename(columns=names)

    crop = count(["Season", "CROPCODE", "CROPNAME"]).rename(columns={"CROPCODE": "Crop code", "CROPNAME": "Crop"})
    return crop, count(["Season"])


def _table(df: pd.DataFrame) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(len(df), len(df.columns))
    t.setHorizontalHeaderLabels([str(c) for c in df.columns])
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    for i, row in enumerate(df.astype(str).values.tolist()):
        for j, v in enumerate(row):
            t.setItem(i, j, QtWidgets.QTableWidgetItem("" if v in ("nan", "None") else v))
    fit_columns(t)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class ImportReview(QtWidgets.QDialog):
    """What each picked file would do; 'Import' stores the files that passed and differ from what is stored."""

    def __init__(self, results: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import master list – review")
        fit_to_screen(self, 1000, 640)
        self.results = results
        self.to_import = [r["path"] for r in results if r["ok"] and not r["cmp"].unchanged]
        lay = QtWidgets.QVBoxLayout(self)
        n_ok = sum(r["ok"] for r in results)
        lay.addWidget(label(f"{len(results)} file(s) checked: {n_ok} passed, {len(results) - n_ok} rejected. "
                            "Nothing is stored until you press Import.", "h3"))
        tabs = QtWidgets.QTabWidget()
        for r in results:
            tabs.addTab(self._file_page(r), ("✓ " if r["ok"] else "✗ ") + r["file"])
        lay.addWidget(tabs, 1)
        bar = QtWidgets.QHBoxLayout()
        bar.addStretch(1)
        cancel = button("Cancel" if self.to_import else "Close")
        cancel.clicked.connect(self.reject)
        bar.addWidget(cancel)
        if self.to_import:
            ok = button(f"Import {len(self.to_import)} file(s)", primary=True, icon="SP_DialogApplyButton")
            ok.clicked.connect(self.accept)
            bar.addWidget(ok)
        lay.addLayout(bar)

    def _file_page(self, r: dict) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        where = f"{r['state'] or 'state ?'} · {r['year'] or 'year ?'}"
        sub = QtWidgets.QTabWidget()
        if not r["ok"]:
            msg = label(f"<b>REJECTED</b> – {where} – real problems found, the stored list is not changed. "
                        f"The error report (CSV files; Marked_data has a PROBLEMS column) is in:<br><tt>{r['report']}</tt>", "bad")
            lay.addWidget(msg)
            b = button("Open error report folder", icon="SP_DirOpenIcon")
            b.clicked.connect(lambda: os.startfile(r["report"]))          # noqa: S606 (Windows)
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            sub.addTab(_table(r["problems"]), "Problems")
        else:
            c = r["cmp"]
            if c.new_year:
                text = f"<b>NEW</b> – {where}: {r['experiments']:,} experiments will be stored."
            elif c.unchanged:
                text = f"<b>SAME AS STORED</b> – {where}: nothing to import."
            else:
                k = c.counts
                text = (f"<b>UPDATE</b> – {where}: replaces only the season(s) in the file – {k['added']} added, "
                        f"{k['removed']} removed, {k['changed']} changed."
                        + (" Seasons not in the file stay as stored." if c.kept_seasons else ""))
            lay.addWidget(label(text, "ok" if c.new_year or c.unchanged else "info"))
            if not c.removed_with_data.empty:
                lay.addWidget(label(f"⚠ {len(c.removed_with_data)} experiment(s) that would be removed already have "
                                    "schedules (RC-7) – see 'Removed with schedules'.", "warn"))
            sub.addTab(_table(c.by_season), "By season")
            sub.addTab(_table(r["crop"]), "Crop-wise (in file)")
            sub.addTab(_table(r["sample"]), "Sample-wise (in file)")
            if not c.new_year:
                for name, df in (("Added", c.added), ("Removed", c.removed), ("Changed", c.changed),
                                 ("Removed with schedules", c.removed_with_data)):
                    if not df.empty:
                        sub.addTab(_table(df), f"{name} ({len(df)})")
        if not r["fixes"].empty:
            sub.addTab(_table(r["fixes"]), f"Cleaned automatically ({len(r['fixes'])})")
        lay.addWidget(label(f"Sheet(s) read: {r['sheets'] or '-'} · rows: {r['rows']:,}", "muted"))
        lay.addWidget(sub, 1)
        return w
