"""8. Annexures — Export: the office's workbooks and a CSV per table.

  1Annexures(Eng / Hi / Bi).xlsx   Annex-XIX … XXIV in the office's final standard, the languages asked
                                   (c08_annexures_final.py)
  1Tables S-1.xlsx, S-2 …          RC7-Y1 … Y13 of each season; 1Tables 8,9,10-Y.xlsx (c08_annexures_tables.py)
  csv/                             Annex XIX … XXIV and every Y-table as CSV (c08_annexures.py)
Saved in 02_artifacts/08_annexures/<STATE>/<YEAR>/<SEASONS>/<dd.mm.yyyy>/.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.components import c08_annexures as A


def export(rep: A.Report, state_hi: str = "", state_code: str = "", languages=("Bi",)) -> list[Path]:
    """Every workbook of the report (+ CSV files). Returns the workbooks made. The old annexure books have room for
    two seasons: with more seasons only the Y-tables are made. (state_hi: kept for callers; the Hindi names
    come from the master list.)"""
    from src.components import c08_annexures_final as annex
    from src.components import c08_annexures_tables as tables
    made = datetime.now()
    folder = A.report_folder(rep.state, rep.year, rep, made)
    csv_dir = folder / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    def save_csv(name: str, df: pd.DataFrame):
        safe = re.sub(r"[^A-Za-z0-9_.+-]+", "_", name)
        df.drop(columns=["_kind"], errors="ignore").to_csv(csv_dir / f"{safe}.csv", index=False, encoding="utf-8-sig")

    for name in ("XIX", "XX", "XXI", "XXII", "XXIII", "XXIV"):    # XVI – XVIII, XXV: typed by the office
        save_csv(f"Annex_{name}", A.annexure(rep, name))
    for t in A.Y_TABLES:
        for s, sn in rep.seasons:
            for smp, smp_name in A.SAMPLES.items():
                save_csv(f"{t}_{sn}_{smp_name}", A.y_table(rep, t, s, smp))
    out = tables.export(rep, folder, state_code, made)
    if languages and len(rep.seasons) <= 2:
        out = annex.export(rep, folder, list(languages), state_code) + out
    return out
