from pathlib import Path
from src.components.c1_ML_ingestion import MLIngestion, MLIngestionParams
from src.utils.config_loader import load_config
from src.utils.common import create_directories
from src.logger import logging
import pandas as pd


STAGE_NAME = "ML Ingestion"


class MLIngestionPipeline:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.ml_ingestion_config = self.config.get("ML_ingestion", {})

    def _get_input_path(self) -> Path:
        ml_path = self.ml_ingestion_config.get("ML_path", "")
        if ml_path:
            return Path(ml_path)
        return Path("01_raw_data/00_MasterList")

    def _get_output_path(self) -> Path:
        ingested_ml_path = self.ml_ingestion_config.get("ingested_ML_path", "artifacts/a00_ingested_ML/ingested_ML.csv")
        return Path(ingested_ml_path)

    def _save_csv_overwrite(self, path: Path, data: pd.DataFrame):
        """Save DataFrame to CSV, overwriting any existing file."""
        logging.info("Entered Method save_csv_overwrite")
        try:
            create_directories([path.parent])
            data.to_csv(path, index=False)
            logging.info(f"CSV file saved at {path} ({len(data)} rows)")
        except Exception as e:
            logging.info(f"Error occurred while saving CSV: {path}")
            raise e
        logging.info("Exited Method save_csv_overwrite")

    def main(self) -> pd.DataFrame:
        logging.info(f"Starting {STAGE_NAME} pipeline")

        input_path = self._get_input_path()
        output_path = self._get_output_path()

        logging.info(f"Input path: {input_path}")
        logging.info(f"Output path: {output_path}")

        create_directories([output_path.parent])

        params = MLIngestionParams(input_path=input_path, output_path=output_path)
        ingestion = MLIngestion(params)
        df = ingestion.ingest_ML()

        if df.empty:
            logging.warning("Ingested DataFrame is empty")
        else:
            self._save_csv_overwrite(output_path, df)
            logging.info(f"Saved ingested ML data to {output_path} (shape: {df.shape})")

        logging.info(f"Completed {STAGE_NAME} pipeline")
        return df


if __name__ == "__main__":
    pipeline = MLIngestionPipeline()
    pipeline.main()