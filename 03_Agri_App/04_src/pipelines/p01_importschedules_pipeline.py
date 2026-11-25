"""Module 1 pipeline — ONE state + year at a time, everything state-wise and year-wise:

  raw        01_raw_data/01_importschedules/<STATE>/<YEAR>/MDB/ and DGCES/
  outputs    02_artifacts/01_importschedules/<STATE>/<YEAR>/  ingested_sch.csv (RC-7), mdb/, dgces/, clubbed/,
             report/ (Files.csv, Tables.csv, Last_import.csv, DGCES issues …), import_history.csv
  database   00_database/01_importschedules/<STATE>/<YEAR>/  file_cache/, dgces_samples.json

The app runs it for the open state + year. Without the app (run_step.py 1) it runs for every <STATE>/<YEAR> folder
of the raw data. DGCES files keep the sample (Central / State) they were imported with.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.components.c01_importschedules import ImportSchedules, ImportSchedulesParams
from src.logger import logging
from src.utils import folders as F
from src.utils.config_loader import load_config
from src.utils.raw_inbox import state_names

STAGE_NAME = "1. Import Schedules"
SAMPLES = {"1": "1", "central": "1", "c": "1", "2": "2", "state": "2", "s": "2"}


class ImportSchedulesPipeline:
    def __init__(self, state: str, state_code: str, year: str, config_path: str = "config.yaml",
                 dgces_sample: str | None = None):
        self.config = load_config(config_path)
        self.ingestion_config = self.config.get("importschedules", {})
        self.state, self.state_code, self.year = state.upper(), str(state_code).zfill(2), year
        given = dgces_sample or self.ingestion_config.get("dgces_sample")
        self.dgces_sample = SAMPLES.get(str(given).strip().lower()) if given else None
        self.ingestion = None

    # ---- folders of this state + year
    def _raw(self) -> Path:
        return Path(self.ingestion_config.get("raw_data_path") or "01_raw_data/01_importschedules") \
            / self.state / self.year

    def _out(self) -> Path:
        return Path(self.ingestion_config.get("artifacts_path") or "02_artifacts/01_importschedules") \
            / self.state / self.year

    def _db(self) -> Path:
        return Path(self.config.get("database_root", "00_database")) / F.IMPORT_SCHEDULES / self.state / self.year

    def main(self, just_imported: list | None = None) -> pd.DataFrame:
        """just_imported = the files copied in by this import (paths in the raw folder); None = every file
        (a run without the app). They make report/Last_import.csv and are added to import_history.csv."""
        logging.info(f"Starting {STAGE_NAME} pipeline for {self.state} {self.year}")
        input_path, out_dir, db = self._raw(), self._out(), self._db()
        input_path.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        report = out_dir / "report"
        dgces_dir = out_dir / "dgces"

        # each DGCES file keeps the sample it was imported with; the sample given now is for newly picked ones
        memory_file = db / "dgces_samples.json"
        samples = self._remembered_samples(memory_file, dgces_dir / "DGCES_ID.csv")
        picked = self._labels(input_path, just_imported) if just_imported is not None else set()
        if self.dgces_sample:
            samples.update({lb: self.dgces_sample for lb in picked if lb.lower().endswith(".xlsx")})

        params = ImportSchedulesParams(input_path=input_path,
                                       mdb_table=self.ingestion_config.get("mdb_table", "Sch20RC7"),
                                       dgces_sample=self.dgces_sample, dgces_samples=samples,
                                       dgces_codes=self.config.get("DGCES_codes") or {},
                                       cache_dir=db / "file_cache", state=self.state,
                                       state_code=self.state_code, year=self.year,
                                       names=state_names(Path(self.config.get("database_root", "00_database"))))
        self.ingestion = ImportSchedules(params)
        df = self.ingestion.ingest_data()
        self._save_samples(memory_file, input_path)

        # rebuilt from the raw files of this state + year each run (unchanged files come from the cache)
        df.to_csv(out_dir / "ingested_sch.csv", index=False, encoding="utf-8-sig")
        logging.info(f"Saved RC-7 of {self.state} {self.year}: {len(df)} rows")
        self.ingestion.write_tables(out_dir / "mdb", dgces_dir, out_dir / "clubbed", df)
        self.ingestion.write_report(report, df)
        self._log_import(report, out_dir / "import_history.csv", input_path, just_imported)
        logging.info(f"Completed {STAGE_NAME} pipeline for {self.state} {self.year}")
        return df

    @staticmethod
    def _labels(input_path: Path, paths: list) -> set:
        """Paths in the raw folder -> their labels (MDB/<file> or DGCES/<file>, as in SOURCE_FILE)."""
        base = input_path.resolve()
        labels = set()
        for p in paths:
            try:
                labels.add(Path(p).resolve().relative_to(base).as_posix())
            except ValueError:
                pass
        return labels

    @staticmethod
    def _remembered_samples(memory_file: Path, dgces_id: Path) -> dict:
        """{DGCES file label: sample} saved by earlier imports (first time: read from the last DGCES_ID.csv)."""
        try:
            return dict(json.loads(memory_file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        if dgces_id.exists():
            ids = pd.read_csv(dgces_id, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            if {"SOURCE_FILE", "SAMPLE"} <= set(ids.columns):
                return {f: g["SAMPLE"].mode().iloc[0] for f, g in ids.groupby("SOURCE_FILE") if (g["SAMPLE"] != "").any()}
        return {}

    def _save_samples(self, memory_file: Path, input_path: Path) -> None:
        """Remember the sample of every DGCES file converted in this run (files no longer there are forgotten)."""
        ing = self.ingestion
        keep = {f.file: ing.sample_for(input_path / f.file) for f in ing.files
                if f.kind == "DGCES" and not f.error and not f.note.startswith("skipped")
                and ing.sample_for(input_path / f.file)}
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        memory_file.write_text(json.dumps(keep, indent=1, sort_keys=True), encoding="utf-8")

    def _log_import(self, report: Path, history: Path, input_path: Path, just_imported: list | None) -> None:
        """report/Last_import.csv = the files of this import; the same rows are added to import_history.csv."""
        files = self.ingestion.files_report
        if files.empty:
            return
        if just_imported is not None:
            files = files[files["File"].isin(self._labels(input_path, just_imported))]
        last = files.copy()
        last.insert(0, "Import run", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        last.to_csv(report / "Last_import.csv", index=False, encoding="utf-8-sig")
        new = not history.exists()
        last.to_csv(history, mode="a", header=new, index=False, encoding="utf-8-sig" if new else "utf-8")
        logging.info(f"Import log: {len(last)} file(s) -> {report / 'Last_import.csv'}; history {history}")


def state_years(config_path: str = "config.yaml") -> list[tuple[str, str, str]]:
    """(STATE, code, YEAR) of every <STATE>/<YEAR> folder of the raw schedules."""
    cfg = load_config(config_path)
    raw = Path(cfg.get("importschedules", {}).get("raw_data_path") or "01_raw_data/01_importschedules")
    code_of = {n: c for c, n in state_names(Path(cfg.get("database_root", "00_database"))).items()}
    out = []
    for d in sorted(p for p in raw.glob("*/*") if p.is_dir()):
        state, year = d.parent.name, d.name
        if state in code_of:
            out.append((state, code_of[state], year))
        else:
            logging.warning(f"{d}: unknown state '{state}' – skipped")
    return out


def run_all(dgces_sample: str | None = None) -> None:
    from src.logger.logging import use_folder
    for state, code, year in state_years():
        use_folder(state, year)                          # 03_logs/<STATE>/<YEAR>/
        ImportSchedulesPipeline(state, code, year, dgces_sample=dgces_sample).main()
    use_folder()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=STAGE_NAME)
    ap.add_argument("--sample", help="sample of DGCES files not imported before: central / state")
    args = ap.parse_args()
    run_all(args.sample)
