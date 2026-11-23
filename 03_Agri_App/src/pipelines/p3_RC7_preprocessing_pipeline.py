from pathlib import Path
from src.components.c3_RC7_preprocessing import RC7Preprocessing, RC7PreprocessingParams
from src.utils.config_loader import load_config
from src.utils.common import create_directories
from src.logger import logging
import pandas as pd


STAGE_NAME = "RC7 Preprocessing"


class RC7PreprocessingPipeline:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.ml_ingestion_config = self.config.get("ML_ingestion", {})
        self.sch_ingestion_config = self.config.get("sch_ingestion", {})
        self.rc7_preprocessing_config = self.config.get("RC7_preprocessing", {})

    def _get_ml_ingested_path(self) -> Path:
        ml_path = self.ml_ingestion_config.get("ingested_ML_path", "artifacts/a1_ingested_ML/ingested_ML.csv")
        return Path(ml_path)

    def _get_sch_ingested_path(self) -> Path:
        sch_path = self.sch_ingestion_config.get("ingested_sch_path", "artifacts/a2_ingested_sch/ingested_sch.csv")
        return Path(sch_path)

    def _get_output_path(self) -> Path:
        output_path = self.rc7_preprocessing_config.get("RC7_preprocessed_path", "artifacts/a3_RC7_preprocessed/preprocessed_RC7.csv")
        return Path(output_path)

    def main(self) -> pd.DataFrame:
        logging.info(f"Starting {STAGE_NAME} pipeline")

        ml_ingested_path = self._get_ml_ingested_path()
        sch_ingested_path = self._get_sch_ingested_path()
        output_path = self._get_output_path()

        logging.info(f"ML ingested path: {ml_ingested_path}")
        logging.info(f"Schedule ingested path: {sch_ingested_path}")
        logging.info(f"Output path: {output_path}")

        # Check if required input files exist
        if not ml_ingested_path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {ml_ingested_path}\n"
                f"Please run pipeline p1 (ML Ingestion) first:\n"
                f"  python -m src.pipelines.p1_ML_ingestion_pipeline"
            )
        if not sch_ingested_path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {sch_ingested_path}\n"
                f"Please run pipeline p2 (Schedule Ingestion) first:\n"
                f"  python -m src.pipelines.p2_sch_ingestion_pipeline"
            )

        create_directories([output_path.parent])

        params = RC7PreprocessingParams(
            ml_ingested_path=ml_ingested_path,
            sch_ingested_path=sch_ingested_path,
            output_path=output_path
        )

        preprocessing = RC7Preprocessing(params)
        df = preprocessing.preprocess()

        if df.empty:
            logging.warning("Preprocessed DataFrame is empty")
        else:
            logging.info(f"Completed {STAGE_NAME} pipeline (shape: {df.shape})")

        return df


if __name__ == "__main__":
    pipeline = RC7PreprocessingPipeline()
    pipeline.main()