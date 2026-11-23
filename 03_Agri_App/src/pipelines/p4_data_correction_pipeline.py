from pathlib import Path
from src.components.c4_data_correction import run_data_correction_ui
from src.utils.config_loader import load_config
from src.utils.common import create_directories
from src.logger import logging


STAGE_NAME = "Data Correction"


class DataCorrectionPipeline:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.rc7_preprocessing_config = self.config.get("RC7_preprocessing", {})

    def _get_input_path(self) -> Path:
        input_path = self.rc7_preprocessing_config.get("RC7_preprocessed_path", "artifacts/a3_RC7_preprocessed/preprocessed_RC7.csv")
        return Path(input_path)

    def _get_output_path(self) -> Path:
        output_path = self.rc7_preprocessing_config.get("RC7_corrected_path", "artifacts/a4_corrected_data/corrected_RC7.csv")
        return Path(output_path)

    def main(self) -> None:
        logging.info(f"Starting {STAGE_NAME} pipeline")

        input_path = self._get_input_path()
        output_path = self._get_output_path()

        logging.info(f"Input path: {input_path}")
        logging.info(f"Output path: {output_path}")

        # Check if required input file exists
        if not input_path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {input_path}\n"
                f"Please run pipeline p3 (RC7 Preprocessing) first:\n"
                f"  python -m src.pipelines.p3_RC7_preprocessing_pipeline"
            )

        create_directories([output_path.parent])

        logging.info(f"Launching Data Correction UI...")
        logging.info(f"Input: {input_path}")
        logging.info(f"Output: {output_path}")

        # Run the UI (this blocks until UI is closed)
        run_data_correction_ui(input_path, output_path)

        logging.info(f"Completed {STAGE_NAME} pipeline")


if __name__ == "__main__":
    pipeline = DataCorrectionPipeline()
    pipeline.main()