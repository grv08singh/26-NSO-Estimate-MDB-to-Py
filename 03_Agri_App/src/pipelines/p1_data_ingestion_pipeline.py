from pathlib import Path
from src.components.c1_data_ingestion import DataIngestion, DataIngestionParams
from src.utils.config_loader import load_config
from src.utils.common import save_csv, create_directories
from src.logger import logging
import pandas as pd


STAGE_NAME = "Data Ingestion"


class DataIngestionPipeline:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.ingestion_config = self.config.get("data_ingestion", {})

    def _get_input_path(self) -> Path:
        raw_data_path = self.ingestion_config.get("raw_data_path", "")
        if raw_data_path:
            return Path(raw_data_path)
        return Path("ingest_data")

    def _get_output_path(self) -> Path:
        ingested_data_path = self.ingestion_config.get("ingested_data_path", "artifacts/01_data_ingestion/RC7_imported.csv")
        return Path(ingested_data_path)

    def _get_mdb_table(self) -> str:
        return self.ingestion_config.get("mdb_table", "Sch20RC7")

    def main(self) -> pd.DataFrame:
        logging.info(f"Starting {STAGE_NAME} pipeline")

        input_path = self._get_input_path()
        output_path = self._get_output_path()
        mdb_table = self._get_mdb_table()

        logging.info(f"Input path: {input_path}")
        logging.info(f"Output path: {output_path}")
        logging.info(f"MDB table: {mdb_table}")

        create_directories([output_path.parent])

        params = DataIngestionParams(input_path=input_path, mdb_table=mdb_table)
        ingestion = DataIngestion(params)
        df = ingestion.ingest_data()

        if df.empty:
            logging.warning("Ingested DataFrame is empty")
        else:
            save_csv(output_path, df)
            logging.info(f"Saved ingested data to {output_path} (shape: {df.shape})")

        logging.info(f"Completed {STAGE_NAME} pipeline")
        return df


if __name__ == "__main__":
    pipeline = DataIngestionPipeline()
    pipeline.main()