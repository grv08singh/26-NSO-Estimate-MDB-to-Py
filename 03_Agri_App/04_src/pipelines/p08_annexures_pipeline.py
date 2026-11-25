"""Module 8 pipeline — Annexures without the app: the Kharif and the Rabi report of every state + year (or one), or
the report / seasons given; headline numbers; --export writes the workbooks and the CSV files.

    python run_step.py 8                                   every state + year with a master list
    python run_step.py 8 BIHAR 2025-26                     one state + year: the Kharif and the Rabi report
    python run_step.py 8 BIHAR 2025-26 --seasons kharif --export [--languages Eng,Hi,Bi]   (default Bi;
                                                           --seasons kharif / rabi, or season codes 2,3)
"""
from pathlib import Path

import pandas as pd

from src.components import c08_annexures as A
from src.components import c08_annexures_excel as X
from src.logger import logging
from src.utils import folders as F

STAGE_NAME = "8. Annexures"
ML = Path("00_database") / F.MASTER_LIST


def report(state: str, year: str, seasons: list[str], export: bool = False, languages: tuple = ()) -> dict:
    f = ML / state / year / "master_list.csv"
    if not f.exists():
        logging.warning(f"{STAGE_NAME}: no master list for {state} {year}")
        return {}
    ml = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    rep = A.build(state, year, ml, seasons)
    if not len(rep.cy.rows):
        return {}
    h = A.headline(rep)
    out = {"Seasons": " + ".join(n for _, n in rep.seasons), "Schedules (RC-7)": len(rep.cy.rows),
           "Previous year": f"{rep.py.year} from {rep.py.source}" if rep.py is not None else "not loaded",
           "This year": h.get("cy"), "Previous": h.get("py")}
    logging.info(f"{STAGE_NAME} {state} {year}: {out}")
    if export:
        hi = str(ml["HSTATENAME"].iloc[0]).strip() if "HSTATENAME" in ml else ""
        code = str(ml["STATE"].iloc[0]) if "STATE" in ml else ""
        made = X.export(rep, hi, code, languages or ("Bi",))
        out["Exported to"] = str(made[0].parent) + "  (" + ", ".join(f.name for f in made) + ")"
    return out


def state_years() -> list[tuple[str, str]]:
    return sorted((f.parent.parent.name, f.parent.name) for f in ML.glob("*/*/master_list.csv"))


def run(state: str | None = None, year: str | None = None, export: bool = False, seasons: str | None = None,
        languages: str | None = None) -> None:
    from src.logger.logging import use_folder
    langs = tuple(x.strip() for x in languages.split(",")) if languages else ()
    for st, yr in ([(state.upper(), year)] if state and year else state_years()):
        use_folder(st, yr)
        f = ML / st / yr / "master_list.csv"
        ml = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig") if f.exists() else pd.DataFrame()
        reports = A.report_seasons(ml)
        if seasons:                                    # season codes given, or a report name
            key = seasons.strip().title()
            todo = {key: [x[0] for x in reports[key]]} if key in reports else \
                {"Report": [x.strip() for x in seasons.split(",")]}
        else:                                          # both reports, each on its own
            todo = {k: [x[0] for x in v] for k, v in reports.items()}
        for name, codes in todo.items():
            res = report(st, yr, codes, export, langs)
            if res:
                print(f"\n{st} {yr} – {name} report")
                for k, val in res.items():
                    print(f"   {k:<18} {val}")
    use_folder()


if __name__ == "__main__":
    run()
