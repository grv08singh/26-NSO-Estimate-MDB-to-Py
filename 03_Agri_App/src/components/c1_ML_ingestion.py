import os
from pathlib import Path
from dataclasses import dataclass
import pandas as pd
from src.utils.common import load_excel
from src.logger import logging


@dataclass
class MLIngestionParams:
    input_path: Path
    output_path: Path


class MLIngestion:
    def __init__(self, params: MLIngestionParams):
        self.params = params

    def _discover_files(self) -> list[Path]:
        files = []
        for file in os.listdir(self.params.input_path):
            file_path = Path(self.params.input_path) / file
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in (".xlsx", ".xls"):
                    files.append(file_path)
        logging.info(f"Discovered {len(files)} Excel files in {self.params.input_path}")
        return files

    def _load_file(self, file_path: Path) -> pd.DataFrame | None:
        ext = file_path.suffix.lower()

        if ext in (".xlsx", ".xls"):
            df = load_excel(file_path)
        else:
            return None

        if df is not None and not df.empty:
            df["source"] = ext.lstrip(".")
            df["source_file"] = file_path.name
            logging.info(f"Loaded {len(df)} rows from {file_path.name}")
            return df
        return None

    def ingest_ML(self) -> pd.DataFrame:
        logging.info("Starting ML data ingestion")
        df = None

        try:
            for file_path in self._discover_files():
                temp_df = self._load_file(file_path)
                if temp_df is None:
                    continue

                if df is None:
                    df = temp_df
                else:
                    df = pd.concat([df, temp_df], ignore_index=True)

            if df is None:
                logging.warning("No valid data files found; returning empty DataFrame")
                df = pd.DataFrame()
            else:
                # Remove duplicate rows
                initial_rows = len(df)
                df = df.drop_duplicates()
                final_rows = len(df)
                duplicates_removed = initial_rows - final_rows
                if duplicates_removed > 0:
                    logging.info(f"Removed {duplicates_removed} duplicate rows ({initial_rows} -> {final_rows})")

        except Exception as e:
            logging.info(f"Error occurred while ingesting data from {self.params.input_path}")
            raise e

        logging.info(f"Completed ML data ingestion (total rows: {len(df)})")
        return df