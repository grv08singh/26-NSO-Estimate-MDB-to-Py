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

                # Add YR column: extract second year from YEAR (e.g., '2025-26' -> '2026')
                df = self._add_yr_column(df)

                # Add UID column: YEAR_STATE_SEASONCODE_SAMPLE_CROPCODE_DISTRICT_SELORDER_EXPT
                df = self._add_uid_column(df)

        except Exception as e:
            logging.info(f"Error occurred while ingesting data from {self.params.input_path}")
            raise e

        logging.info(f"Completed ML data ingestion (total rows: {len(df)})")
        return df

    def _clean_uid_val(self, v) -> str:
        """Convert value to string without leading zeros.
        If value is numeric (int/float) or numeric string, convert to int first to strip leading zeros.
        """
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:.0f}"
        if isinstance(v, int):
            return str(v)
        # For strings, try to convert to number to strip leading zeros
        s = str(v).strip()
        if s == "":
            return ""
        # Try to convert to float/int to remove leading zeros
        try:
            if s.replace('.', '', 1).isdigit():
                num = float(s)
                if num == int(num):
                    return str(int(num))
                return str(num)
        except ValueError:
            pass
        return s.replace(".0", "")

    def _add_uid_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add UID column with format: YR_STATE_SEASONCODE_SAMPLE_CROPCODE_DISTRICT_SELORDER_EXPT"""
        # Ensure required columns exist
        required_cols = ["YR", "STATE", "SEASONCODE", "SAMPLE", "CROPCODE", "DISTRICT", "SELORDER", "EXPT"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logging.warning(f"Missing columns for UID generation: {missing_cols}")
            return df

        # Convert to string and create UID (using _clean_uid_val to strip leading zeros)
        df["UID"] = (
            df["YR"].apply(self._clean_uid_val) + "_" +
            df["STATE"].apply(self._clean_uid_val) + "_" +
            df["SEASONCODE"].apply(self._clean_uid_val) + "_" +
            df["SAMPLE"].apply(self._clean_uid_val) + "_" +
            df["CROPCODE"].apply(self._clean_uid_val) + "_" +
            df["DISTRICT"].apply(self._clean_uid_val) + "_" +
            df["SELORDER"].apply(self._clean_uid_val) + "_" +
            df["EXPT"].apply(self._clean_uid_val)
        )

        # Move UID to the first column
        cols = ["UID"] + [col for col in df.columns if col != "UID"]
        df = df[cols]

        logging.info(f"Added UID column with {df['UID'].nunique()} unique values")
        return df

    def _add_yr_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add YR column extracting the second year from YEAR (e.g., '2025-26' -> '2026')"""
        if "YEAR" not in df.columns:
            logging.warning("YEAR column not found, cannot add YR column")
            return df

        def extract_yr(year_val):
            if pd.isna(year_val):
                return None
            year_str = str(year_val).strip()
            # Handle format like '2025-26' or '2025-2026'
            if "-" in year_str:
                parts = year_str.split("-")
                second_part = parts[1].strip()
                # If it's 2 digits, assume 20xx format
                if len(second_part) == 2:
                    return f"20{second_part}"
                return second_part
            # If no dash, return as is
            return year_str

        df["YR"] = df["YEAR"].apply(extract_yr)
        logging.info(f"Added YR column with {df['YR'].nunique()} unique values")
        return df