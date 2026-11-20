import os
from pathlib import Path
from dataclasses import dataclass
import pandas as pd
from src.utils.common import load_csv, load_excel, load_mdb
from src.logger import logging


@dataclass
class DataIngestionParams:
    input_path: Path
    mdb_table: str


class DataIngestion:
    def __init__(self, params: DataIngestionParams):
        self.params = params

    def _discover_files(self) -> list[Path]:
        files = []
        for file in os.listdir(self.params.input_path):
            file_path = Path(self.params.input_path) / file
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in (".csv", ".mdb", ".accdb", ".xlsx", ".xls"):
                    files.append(file_path)
        logging.info(f"Discovered {len(files)} data files in {self.params.input_path}")
        return files

    def _load_file(self, file_path: Path) -> pd.DataFrame | None:
        ext = file_path.suffix.lower()
        source = ext.lstrip(".")

        if ext == ".csv":
            df = load_csv(file_path)
        elif ext in (".mdb", ".accdb"):
            df = load_mdb(file_path, self.params.mdb_table)
        elif ext in (".xlsx", ".xls"):
            df = load_excel(file_path)
        else:
            return None

        df["source"] = source
        logging.info(f"Loaded {len(df)} rows from {file_path.name} (source={source})")
        return df

    def ingest_data(self) -> pd.DataFrame:
        logging.info("Entered ingest_data method of DataIngestion class")
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

        except Exception as e:
            logging.info(f"Error occurred while ingesting data from {self.params.input_path}")
            raise e

        logging.info(f"Exited ingest_data method of DataIngestion class (total rows: {len(df)})")
        return df