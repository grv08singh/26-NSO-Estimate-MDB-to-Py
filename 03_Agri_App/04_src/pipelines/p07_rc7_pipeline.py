"""Module 7 pipeline — RC7 without the app: the checks of every state + year (or one), shown with their
counts; --export writes both lists as CSV. It never applies a correction: that is done in the app, after you confirm.

    python run_step.py 7                       every state + year with a master list
    python run_step.py 7 BIHAR 2025-26         one state + year
    python run_step.py 7 BIHAR 2025-26 --export
"""
from collections import Counter
from pathlib import Path

import pandas as pd

from src.components import c07_rc7 as v
from src.logger import logging
from src.utils import folders as F
from src.utils import schedules
from src.utils.raw_inbox import state_names

STAGE_NAME = "7. RC7"
ML = Path("00_database") / F.MASTER_LIST


def check(state: str, year: str, export: bool = False) -> dict:
    f = ML / state / year / "master_list.csv"
    if not f.exists():
        logging.warning(f"{STAGE_NAME}: no master list for {state} {year}")
        return {}
    ml = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    rc = schedules.rc7(state, year)
    df = v.rows(ml, rc)
    if df.empty:
        return {}
    code = next((c for c, n in state_names(Path("00_database")).items() if n == state), str(df["STAT"].iloc[0]))
    props, fixed = v.propose(df, ml, rc, state, year)
    issues = v.problems(fixed, state, code, year)
    out = {"Schedules": len(df), "Corrections proposed": len(props), "Problems": len(issues)}
    logging.info(f"{STAGE_NAME} {state} {year}: {out}\n  proposed: {Counter(p['Field'] for p in props).most_common()}"
                 f"\n  problems: {Counter(p['Check'].split(' Allowed:')[0] for p in issues).most_common()}")
    if export:
        out["Exported to"] = str(v.export(state, year, props, issues, "all"))
    return out


def state_years() -> list[tuple[str, str]]:
    return sorted((f.parent.parent.name, f.parent.name) for f in ML.glob("*/*/master_list.csv"))


def run(state: str | None = None, year: str | None = None, export: bool = False) -> None:
    from src.logger.logging import use_folder
    for st, yr in ([(state.upper(), year)] if state and year else state_years()):
        use_folder(st, yr)
        res = check(st, yr, export)
        if res:
            print(f"\n{st} {yr}")
            for k, val in res.items():
                print(f"   {k:<22} {val}")
    use_folder()


if __name__ == "__main__":
    import sys
    run(*(sys.argv[1:3] if len(sys.argv) >= 3 else ()), export="--export" in sys.argv)
