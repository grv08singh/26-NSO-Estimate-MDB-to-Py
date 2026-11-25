"""Run one module without the app (the code is in 04_src, so `python -m src.pipelines…` no longer works):

    python run_step.py 0                       00. Master List (store the master lists in 01_raw_data/00_masterlist)
    python run_step.py 1                       1. Import Schedules for every <STATE>/<YEAR> of the raw schedules
                                               (--sample central / state for DGCES files not imported before)
    python run_step.py 2 [STATE YEAR]          2. Control Register summary (every state + year, or one), shown only
    python run_step.py 5 [STATE YEAR] [--export]  5. Estimates: every saved area sheet worked out again (--export:
                                               also written as the Excel workbook)
    python run_step.py 6 [STATE YEAR] [--export]  6. Estimate Report of every saved estimate (--export: the workbooks)
    python run_step.py 7 [STATE YEAR] [--export]  7. RC7: the checks, counted (--export: both lists as CSV)
    python run_step.py 8 [STATE YEAR] [--seasons kharif|rabi|2,3] [--export] [--languages Eng,Hi,Bi]
                                               8. Annexures: the Kharif and Rabi reports (or the one given),
                                               headline numbers (--export: the workbooks + CSV files)
"""
import argparse
import sys

import bootstrap

bootstrap.setup()


def main() -> int:
    ap = argparse.ArgumentParser(description="Run one module of the Agri App")
    ap.add_argument("module", choices=["0", "1", "2", "5", "6", "7", "8"])
    ap.add_argument("--sample", help="module 1: sample of the DGCES files (central / state)")
    ap.add_argument("--export", action="store_true", help="modules 5 / 6 / 7 / 8: also write the files")
    ap.add_argument("--seasons", help="module 8: the report – kharif / rabi – or season codes, e.g. 2,3")
    ap.add_argument("--languages", help="module 8: annexures Eng, Hi, Bi (comma separated; default Bi)")
    ap.add_argument("state", nargs="?", help="modules 2 / 5 / 6 / 7: one state (e.g. BIHAR)")
    ap.add_argument("year", nargs="?", help="modules 2 / 5 / 6 / 7: its year (e.g. 2025-26)")
    args = ap.parse_args()
    if args.module == "0":
        from src.pipelines.p00_masterlist_pipeline import MasterListPipeline
        MasterListPipeline().main()
    elif args.module == "1":
        from src.pipelines.p01_importschedules_pipeline import run_all
        run_all(args.sample)
    elif args.module == "2":
        from src.pipelines.p02_controlregister_pipeline import run
        run(args.state, args.year)
    elif args.module == "5":
        from src.pipelines.p05_estimates_pipeline import run
        run(args.state, args.year, args.export)
    elif args.module == "6":
        from src.pipelines.p06_estimatereport_pipeline import run
        run(args.state, args.year, args.export)
    elif args.module == "7":
        from src.pipelines.p07_rc7_pipeline import run
        run(args.state, args.year, args.export)
    else:
        from src.pipelines.p08_annexures_pipeline import run
        run(args.state, args.year, args.export, args.seasons, args.languages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
