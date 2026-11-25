"""Module 5 pipeline — the Estimates without the app: every estimate whose area sheet is saved (in the app) is worked
out again from the stored master list and the imported schedules (Data Validation corrections applied), shown on
screen and in the log; with --export each one is also written as the Excel workbook, as the app's Export button.
Also writes a consolidated summary CSV (config: estimates_report.summary_csv_path) with:
Year, State code, Season code, Sample code, Crop code, Yield (kg/ha), %SE, Variance, Area (ha).

    python run_step.py 5                       every state + year with saved area sheets
    python run_step.py 5 BIHAR 2025-26         one state + year
    python run_step.py 5 BIHAR 2025-26 --export
"""
from pathlib import Path

import pandas as pd

from src.components import c05_estimates as est
from src.components import c05_estimates_report as report
from src.logger import logging
from src.utils import folders as F
from src.utils import schedules
from src.utils.config_loader import load_config

STAGE_NAME = "5. Estimates"


class EstimatesPipeline:
    def __init__(self, state: str, year: str, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.state, self.year = state.upper(), year
        self.db = Path(self.config.get("database_root", "00_database"))

    def main(self, export: bool = False) -> list[dict]:
        ml_file = self.db / F.MASTER_LIST / self.state / self.year / "master_list.csv"
        saved = est._read(est.folder(self.state, self.year) / est.INPUTS_FILE, est.INPUT_COLUMNS)
        if not ml_file.exists() or saved.empty:
            logging.warning(f"{STAGE_NAME}: no master list or no saved area sheet for {self.state} {self.year}")
            return []
        ml = pd.read_csv(ml_file, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        # Get state code from master list (STATE column)
        state_code = ml["STATE"].iloc[0] if len(ml) and "STATE" in ml.columns else self.state
        rc7 = schedules.rc7(self.state, self.year)
        out = []
        for key in saved["KEY"]:
            sel = est.Selection(tuple(tuple(p.split("-")) for p in key.split("+")))
            exps = est.experiments(ml, rc7, sel)
            base = est.district_base(est.harvested(exps))
            inputs = est.load_inputs(self.state, self.year, sel)
            res = est.calculate(base, inputs)
            nm = est.names(ml, sel)
            row = {"Season": nm["season"], "Crop": nm["crop"], "Sample": sel.sample_label, "Yield (kg/ha)": res.yield_kg_ha,
                   "Variance": res.variance, "SE": res.se, "%SE": res.pct_se, "Area": res.total_area,
                   "Planned": len(exps), "Analysed": res.analysed}
            if export:
                row["Exported to"] = str(report.export(self.state, self.year, sel, nm, inputs, base, res, exps))
                # Also append to consolidated summary CSV
                report.append_summary_csv(self.state, self.year, sel, nm, res, state_code)
            for w in res.warnings:
                logging.warning(f"{STAGE_NAME} {nm['crop']} {sel.sample_label}: {w}")
            out.append(row)
        logging.info(f"{STAGE_NAME} {self.state} {self.year}:\n" + pd.DataFrame(out).to_string(index=False))
        return out


def state_years() -> list[tuple[str, str]]:
    """(STATE, YEAR) with saved area sheets."""
    return sorted((f.parent.parent.name, f.parent.name) for f in est.DB.glob(f"*/*/{est.INPUTS_FILE}"))


def run(state: str | None = None, year: str | None = None, export: bool = False) -> None:
    from src.logger.logging import use_folder
    for st, yr in ([(state.upper(), year)] if state and year else state_years()):
        use_folder(st, yr)                               # 03_logs/<STATE>/<YEAR>/
        res = EstimatesPipeline(st, yr).main(export)
        if res:
            print(f"\n{st} {yr}")
            print(pd.DataFrame(res).to_string(index=False))
    use_folder()


if __name__ == "__main__":
    import sys
    run(*(sys.argv[1:3] if len(sys.argv) >= 3 else ()), export="--export" in sys.argv)
