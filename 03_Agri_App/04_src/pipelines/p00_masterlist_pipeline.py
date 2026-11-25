from src.utils import folders as F
from pathlib import Path
from src.components.c00_masterlist import MasterList, MasterListParams
from src.utils.config_loader import load_config
from src.utils.common import create_directories
from src.logger import logging
import pandas as pd


STAGE_NAME = "00. Master List"


class MasterListPipeline:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.masterlist_config = self.config.get("masterlist", {})
        self.ingestion = None

    def _get_input_path(self) -> Path:
        return Path(self.masterlist_config.get("raw_ML_path") or "01_raw_data/00_masterlist")

    def _get_output_path(self) -> Path:
        """The module's output folder; every state + year gets its own <STATE>/<YEAR>/ inside it."""
        return Path(self.masterlist_config.get("ingested_ML_path", "02_artifacts/00_masterlist"))

    def _save_csv_overwrite(self, path: Path, data: pd.DataFrame):
        """Save DataFrame to CSV, overwriting any existing file."""
        create_directories([path.parent])
        data.to_csv(path, index=False, encoding="utf-8-sig")
        logging.info(f"CSV file saved at {path} ({len(data)} rows)")

    def main(self) -> pd.DataFrame:
        logging.info(f"Starting {STAGE_NAME} pipeline")
        input_path = self._get_input_path()
        output_path = self._get_output_path()
        logging.info(f"Input path: {input_path}")
        logging.info(f"Output folder: {output_path}/<STATE>/<YEAR>/")
        create_directories([output_path])

        params = MasterListParams(
            input_path=input_path, output_path=output_path / "ingested_ML.csv",      # only its folder is used
            database_path=Path(self.config.get("database_root", "00_database")) / F.MASTER_LIST,
            backup_path=Path(self.config.get("backup_root", "05_backup")) / F.MASTER_LIST)
        self.ingestion = MasterList(params)
        df = self.ingestion.ingest_ML()

        if df.empty:
            logging.warning("Ingested DataFrame is empty")
        logging.info(f"Completed {STAGE_NAME} pipeline")
        return df


if __name__ == "__main__":
    pipeline = MasterListPipeline()
    pipeline.main()
