"""Module 6 pipeline — the Estimate Report without the app: for every estimate saved in 5. Estimates, the
Information Accompanying / T-test / Confidential Sheet figures are worked out (previous year from the app, typed
figures from 6. Estimate Report) and shown; with --export each is also written as the Excel workbook.

    python run_step.py 6                       every state + year with saved estimates
    python run_step.py 6 BIHAR 2025-26         one state + year
    python run_step.py 6 BIHAR 2025-26 --export
"""
import pandas as pd

from src.components import c05_estimates as est
from src.components import c06_estimatereport as er
from src.components import c06_estimatereport_excel as excel
from src.components import c06_estimatereport_pooled as pr
from src.logger import logging

STAGE_NAME = "6. Estimate Report"


class EstimateReportPipeline:
    def __init__(self, state: str, year: str):
        self.state, self.year = state.upper(), year

    def main(self, export: bool = False) -> list[dict]:
        saved = est._read(est.folder(self.state, self.year) / est.INPUTS_FILE, est.INPUT_COLUMNS)
        if saved.empty:
            logging.warning(f"{STAGE_NAME}: no saved estimate for {self.state} {self.year}")
            return []
        out = []
        for key in saved["KEY"]:
            sel = est.Selection(tuple(tuple(p.split("-")) for p in key.split("+")))
            rep = er.build(self.state, self.year, sel)
            if rep is None:
                continue
            conf = er.confidential_row(rep)
            row = {"Season": rep.nm["season"], "Crop": rep.nm["crop"], "Sample": sel.sample_label,
                   "Yield (SE%)": conf["now"], "Previous (SE%)": conf["prev"], "CES (SE%)": conf["ces"],
                   "% diff. previous": conf["diff_prev"], "% diff. CES": conf["diff_ces"],
                   "Planned": conf["planned"], "Analysed": conf["analysed"],
                   "Previous year in the app": "yes" if rep.prev is not None else "no"}
            if export:
                row["Exported to"] = str(excel.export(rep))
            out.append(row)
        logging.info(f"{STAGE_NAME} {self.state} {self.year}:\n" + pd.DataFrame(out).to_string(index=False))
        return out

    def pooled(self, export: bool = False) -> list[dict]:
        """Combined & Pooled (the office's Central / State workbooks) of every crop group with a saved estimate."""
        saved = est._read(est.folder(self.state, self.year) / est.INPUTS_FILE, est.INPUT_COLUMNS)
        groups = sorted({(k.split("-")[0], k.split("-")[2]) for k in saved["KEY"] if "+" not in k})
        out, seen = [], set()
        for season, crop in groups:
            rep = pr.build(self.state, self.year, season, crop)
            if rep is None or rep.group.key in seen:
                continue
            seen.add(rep.group.key)
            c, s, p = rep.combined("1"), rep.combined("2"), rep.pooled
            row = {"Season": rep.names["season"], "Crop": rep.names["crop"], "Codes": "+".join(rep.group.codes),
                   "Central (SE%)": pr._pair(c.yc, c.pct_se), "State (SE%)": pr._pair(s.yc, s.pct_se),
                   "Pooled (SE%)": pr._pair(p.yp, p.pct_se),
                   "Central vs State": pr.t_test("", c.yc, c.vc, s.yc, s.vc).result}
            if export and (c.yc is not None or s.yc is not None):
                row["Exported to"] = str(pr.export(rep))
            out.append(row)
        if out:
            logging.info(f"{STAGE_NAME} Combined & Pooled {self.state} {self.year}:\n"
                         + pd.DataFrame(out).to_string(index=False))
        return out


def state_years() -> list[tuple[str, str]]:
    """(STATE, YEAR) with estimates saved in 5. Estimates."""
    return sorted((f.parent.parent.name, f.parent.name) for f in est.DB.glob(f"*/*/{est.INPUTS_FILE}"))


def run(state: str | None = None, year: str | None = None, export: bool = False) -> None:
    from src.logger.logging import use_folder
    for st, yr in ([(state.upper(), year)] if state and year else state_years()):
        use_folder(st, yr)                               # 03_logs/<STATE>/<YEAR>/
        pipe = EstimateReportPipeline(st, yr)
        res = pipe.main(export)
        if res:
            print(f"\n{st} {yr}")
            print(pd.DataFrame(res).to_string(index=False))
        pooled = pipe.pooled(export)
        if pooled:
            print(f"\n{st} {yr} – Combined & Pooled")
            print(pd.DataFrame(pooled).to_string(index=False))
    use_folder()


if __name__ == "__main__":
    import sys
    run(*(sys.argv[1:3] if len(sys.argv) >= 3 else ()), export="--export" in sys.argv)
