# RC7 file name and xlsx writer
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import openpyxl

from .table import Table


# Save RC7 as xlsx
def write_rc7_xlsx(df: Table, path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "RC7"
    ws.append(list(df.columns))
    for rec in df.rows:
        ws.append(rec)
    wb.save(path)


# RC7 file name
def run_name(df: Table, seasons: List[Optional[str]]) -> str:
    yrs = list(dict.fromkeys(v for v in df.col("YR") if v is not None))
    yr = str(yrs[0]) if len(yrs) == 1 else "MixedYR"
    names = sorted({s.strip() for s in seasons if s})
    season = names[0].replace(" ", "_") if len(names) == 1 else "MixedSeason"
    return f"{yr}_{season}_{datetime.now():%Y%m%d_%H%M}"
