"""Module 2 pipeline — the Control Register without the app: a SUMMARY shown on screen and in the log, nothing written.

Same figures as the app's 2. Control Register page (components/c02_controlregister_summary.py), from the stored
master list and the imported schedules of a state + year, with the Data Validation corrections applied (a schedule
changed from REJ 1 to 0 counts as not rejected at once). In the app the page works it out by itself whenever it is
opened, schedules are imported or corrections are saved.

    python run_step.py 2                     every state + year with a master list
    python run_step.py 2 BIHAR 2025-26       one state + year
"""
from pathlib import Path

import pandas as pd

from src.components import c02_controlregister_summary as cr
from src.logger import logging
from src.utils import folders as F
from src.utils import schedules
from src.utils.config_loader import load_config
from src.utils.raw_inbox import state_names

STAGE_NAME = "2. Control Register"


class ControlRegisterPipeline:
    def __init__(self, state: str, year: str, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.state, self.year = state.upper(), year
        self.db = Path(self.config.get("database_root", "00_database"))

    def main(self) -> dict:
        """Totals of the state + year (planned, received, not received, harvested, missed, lost, rejected,
        Harvest %), also logged with the by-crop table."""
        ml_file = self.db / F.MASTER_LIST / self.state / self.year / "master_list.csv"
        if not ml_file.exists():
            logging.warning(f"{STAGE_NAME}: no master list for {self.state} {self.year}")
            return {}
        ml = pd.read_csv(ml_file, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        df, not_in_ml = cr.build(ml, schedules.rc7(self.state, self.year))
        totals = cr.totals(df)
        dg = len(schedules.dgces_ids(self.state, self.year))
        text = "  ".join(f"{k}: {v:.2f}" if k == "Harvest %" else f"{k}: {v:,}" for k, v in totals.items())
        logging.info(f"{STAGE_NAME} {self.state} {self.year} – {text}  |  received, not in master list: "
                     f"{len(not_in_ml):,}  |  DGCES (not linked): {dg:,}")
        crop = cr.by_crop(df)
        if not crop.empty:
            logging.info("By crop:\n" + crop.to_string(index=False))
        return {**totals, "Received, not in master list": len(not_in_ml), "DGCES (not linked)": dg}


def state_years(config_path: str = "config.yaml") -> list[tuple[str, str]]:
    """(STATE, YEAR) of every stored master list."""
    db = Path(load_config(config_path).get("database_root", "00_database"))
    return sorted((f.parent.parent.name, f.parent.name) for f in (db / F.MASTER_LIST).glob("*/*/master_list.csv"))


def run(state: str | None = None, year: str | None = None) -> None:
    from src.logger.logging import use_folder
    todo = [(state.upper(), year)] if state and year else state_years()
    if state and year and state.upper() not in {s for s in state_names(Path("00_database")).values()}:
        logging.warning(f"Unknown state {state}")
    for st, yr in todo:
        use_folder(st, yr)                               # 03_logs/<STATE>/<YEAR>/
        res = ControlRegisterPipeline(st, yr).main()
        if res:
            print(f"\n{st} {yr}")
            for k, v in res.items():
                print(f"   {k:<32} {v:.2f}" if k == "Harvest %" else f"   {k:<32} {v:,}")
    use_folder()


if __name__ == "__main__":
    import sys
    run(*(sys.argv[1:3] if len(sys.argv) >= 3 else ()))
