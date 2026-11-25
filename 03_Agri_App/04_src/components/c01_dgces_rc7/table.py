# Simple table for RC7 output
from __future__ import annotations

import csv
import math
import os
from typing import Dict, List, Optional, Sequence


class Table:
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
        self.columns: List[str] = list(columns)
        self.rows: List[List[object]] = [list(r) for r in rows]

    def __len__(self) -> int:
        return len(self.rows)

    # Column values
    def col(self, name: str) -> List[object]:
        i = self.columns.index(name)
        return [r[i] for r in self.rows]

    # One row as dict
    def row(self, n: int) -> Dict[str, object]:
        return dict(zip(self.columns, self.rows[n]))

    # Filter rows
    def where(self, keep) -> "Table":
        return Table(self.columns, [r for r in self.rows if keep(dict(zip(self.columns, r)))])

    def write_csv(self, path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=os.linesep)
            w.writerow(self.columns)
            for r in self.rows:
                w.writerow(["" if v is None else repr(v) if isinstance(v, float) else v for v in r])

    # Read csv
    @classmethod
    def read_csv(cls, path: str) -> "Table":
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        return cls(rows[0] if rows else [], rows[1:])


# Text to float
def to_number(v: object) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None if v is None else float(v)
    try:
        f = float(str(v).strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# Text to int
def to_int(v: object) -> Optional[int]:
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    f = to_number(v)
    if f is None:
        return None
    if not f.is_integer():
        raise ValueError(f"cannot store {v!r} as an integer")
    return int(f)
