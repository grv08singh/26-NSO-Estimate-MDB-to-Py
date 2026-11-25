# Data issues and counts
from __future__ import annotations

import logging
import math
from collections import Counter, OrderedDict
from typing import Dict, Iterable, List, Optional, Sequence

import openpyxl

from . import config
from .table import Table

log = logging.getLogger(__name__)

BLANK_LABEL = "(blank)"


# Collects issues
class Recorder:

    def __init__(self) -> None:
        self._unmapped: "OrderedDict[tuple, int]" = OrderedDict()
        self.comparisons: List[Dict[str, object]] = []
        self.issues: List[Dict[str, object]] = []

    # Unmatched text
    def unmapped(self, field: str, source: str, raw: object, action: str) -> None:
        key = (field, source, raw, action)
        self._unmapped[key] = self._unmapped.get(key, 0) + 1

    # Data issue
    def issue(self, kind: str, ident: Optional[Dict[str, object]], detail: str) -> None:
        row: Dict[str, object] = {"Issue": kind}
        row.update(ident or {})
        row["Detail"] = detail
        self.issues.append(row)

    # Comparison result
    def comparison(self, ident: Dict[str, object], field: str, pw: object, s: object,
                   code: Optional[int], differing: str = "") -> None:
        row: Dict[str, object] = dict(ident)
        row.update({"Field": field, "PW value(s)": pw, "S value(s)": s,
                    "Result": code, "Differing pair(s)": differing})
        self.comparisons.append(row)

    def unmapped_rows(self) -> List[Dict[str, object]]:
        return [{"Field": f, "Source column": s, "Raw value": r, "Count": n, "Action": a}
                for (f, s, r, a), n in self._unmapped.items()]


def _blank(v: object) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


# Value counts
def value_counts(values: Iterable[object]) -> "OrderedDict[str, int]":
    labels = [BLANK_LABEL if _blank(v) else str(v) for v in values]
    return OrderedDict(Counter(labels).most_common())


def _write_sheet(wb: openpyxl.Workbook, title: str, header: Sequence[str],
                 rows: Iterable[Sequence[object]]) -> None:
    ws = wb.create_sheet(title)
    ws.append(list(header))
    for r in rows:
        ws.append([None if _blank(v) else v for v in r])


# Write report workbook
def write_report(path: str, rc7: Table, rec: Recorder, meta: Dict[str, object]) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    summary: List[List[object]] = [[k, v] for k, v in meta.items()]
    summary.append([])
    summary.append(["Field", "Value", "Count"])
    for f in config.SUMMARY_FIELDS:
        for val, n in value_counts(rc7.col(f)).items():
            summary.append([f, val, n])
    for f in config.ALWAYS_BLANK:
        summary.append([f, BLANK_LABEL + " - " + config.ALWAYS_BLANK[f], sum(1 for v in rc7.col(f) if _blank(v))])
    _write_sheet(wb, "Summary", ["Item", "Value", ""], summary)

    cmp_cols = ["District", "Village", "Crop", "EXPNO", "Field", "PW value(s)", "S value(s)",
                "Result", "Differing pair(s)"]
    _write_sheet(wb, "Comparisons", cmp_cols, ([r.get(c) for c in cmp_cols] for r in rec.comparisons))

    um_cols = ["Field", "Source column", "Raw value", "Count", "Action"]
    _write_sheet(wb, "Unmapped_Values", um_cols, ([r[c] for c in um_cols] for r in rec.unmapped_rows()))

    is_cols = ["Issue", "District", "Village", "Crop", "EXPNO", "Detail"]
    _write_sheet(wb, "Data_Issues", is_cols, ([r.get(c) for c in is_cols] for r in rec.issues))

    wb.save(path)
    log.info("Report written: %s", path)
