import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
from src.utils.common import load_csv, load_excel, load_mdb
from src.logger import logging


# Required columns for detailed experiment data (RC7 format)
REQUIRED_COLUMNS = [
    "EXPTID", "SRL", "RC", "ST", "YR", "SESON", "CROP", "NEXP", "NEXNR", "CONFAC",
    "STAT", "DIST", "VILL", "RSV", "EXPNO", "STAGIN", "REXML", "CCE", "CFC", "RCSSN",
    "E1", "E2", "E9", "E10", "E11", "E12", "ADH", "QTYG", "QTYP", "E13",
    "EQST", "EQSB", "EQSW", "EQSP", "E14", "STYPE", "E3", "SVARC", "SEEDR", "E4",
    "IRR", "E5", "IRRP", "NIRR", "FERTC", "E6", "QTN", "CODN", "QTP", "CODP",
    "QTK", "CODK", "MANUR", "E7", "PEST", "E8", "E15", "REJ", "CROPER", "CROPCON", "AFFECT"
]


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has all required columns, adding missing ones as NaN."""
    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_cols:
        # Add all missing columns at once to avoid fragmentation
        missing_df = pd.DataFrame(np.nan, index=df.index, columns=list(missing_cols))
        df = pd.concat([df, missing_df], axis=1)
        logging.warning(f"Added missing columns with NaN: {missing_cols}")
    # Return only required columns in the correct order
    return df[REQUIRED_COLUMNS]


@dataclass
class SchIngestionParams:
    input_path: Path
    mdb_table: str


class SchIngestion:
    def __init__(self, params: SchIngestionParams):
        self.params = params

    def _discover_files(self) -> list[Path]:
        files = []
        for file in os.listdir(self.params.input_path):
            file_path = Path(self.params.input_path) / file
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in (".csv", ".mdb", ".accdb", ".xlsx", ".xls"):
                    files.append(file_path)
        logging.info(f"Discovered {len(files)} schedule files in {self.params.input_path}")
        return files

    def _load_file(self, file_path: Path) -> pd.DataFrame | None:
        ext = file_path.suffix.lower()

        if ext == ".csv":
            df = load_csv(file_path)
        elif ext in (".mdb", ".accdb"):
            df = load_mdb(file_path, self.params.mdb_table)
        elif ext in (".xlsx", ".xls"):
            df = load_excel(file_path)
        else:
            return None

        # Remove rows where all fields are empty/null in the raw data
        initial_rows = len(df)
        df = df.dropna(how="all")
        final_rows = len(df)
        empty_rows_removed = initial_rows - final_rows
        if empty_rows_removed > 0:
            logging.info(f"Removed {empty_rows_removed} empty rows from {file_path.name} ({initial_rows} -> {final_rows})")

        # Standardize columns to match REQUIRED_COLUMNS schema
        df = _standardize_columns(df)

        # Remove rows where all RC7 columns are NaN (no RC7 data)
        # This removes rows from files that don't have RC7 format data (e.g., Excel with different schema)
        rc7_cols = [col for col in REQUIRED_COLUMNS if col in df.columns]
        if rc7_cols:
            initial_rows = len(df)
            df = df.dropna(subset=rc7_cols, how="all")
            final_rows = len(df)
            rc7_empty_removed = initial_rows - final_rows
            if rc7_empty_removed > 0:
                logging.info(f"Removed {rc7_empty_removed} rows with no RC7 data from {file_path.name} ({initial_rows} -> {final_rows})")

        # Return empty dataframe if all rows were removed
        if df.empty:
            logging.info(f"No RC7 data rows remaining in {file_path.name}")
            return df

        # Add CROPCODE extracted from EXPTID (digits 8-11, 1-indexed = positions 7-10 0-indexed)
        if "EXPTID" in df.columns:
            # Convert EXPTID to string, handling both float (e.g., 1.330101e+11) and string formats
            def exptid_to_str(x):
                if pd.isna(x):
                    return ""
                if isinstance(x, float):
                    return f"{x:.0f}"
                return str(x)

            df["EXPTID_str"] = df["EXPTID"].apply(exptid_to_str)
            df["CROPCODE"] = df["EXPTID_str"].str[7:11]
            df = df.drop(columns=["EXPTID_str"])

            # Convert EXPTID to integer (handle NaN)
            def exptid_to_int(x):
                if pd.isna(x):
                    return pd.NA
                if isinstance(x, float):
                    return int(x)
                if isinstance(x, int):
                    return x
                try:
                    return int(float(x))
                except (ValueError, TypeError):
                    return pd.NA

            df["EXPTID"] = df["EXPTID"].apply(exptid_to_int)
            # Convert to nullable integer type
            df["EXPTID"] = df["EXPTID"].astype("Int64")

        # Add UID column: YR_STAT_SESON_ST_CROPCODE_DIST_VILL_EXPNO
        uid_cols = ["YR", "STAT", "SESON", "ST", "CROPCODE", "DIST", "VILL", "EXPNO"]
        if all(col in df.columns for col in uid_cols):
            def clean_val(v):
                """Convert value to string without leading zeros.
                If value is numeric (int/float) or numeric string, convert to int first to strip leading zeros.
                """
                if pd.isna(v):
                    return ""
                if isinstance(v, float):
                    # Convert float to int to remove .0, then to string
                    return f"{v:.0f}"
                if isinstance(v, int):
                    return str(v)
                # For strings, try to convert to number to strip leading zeros
                s = str(v).strip()
                if s == "":
                    return ""
                # Try to convert to float/int to remove leading zeros
                try:
                    # Check if it's a numeric string (including leading zeros)
                    if s.replace('.', '', 1).isdigit():
                        num = float(s)
                        # If it's a whole number, convert to int to remove .0
                        if num == int(num):
                            return str(int(num))
                        return str(num)
                except ValueError:
                    pass
                # If not numeric, return as-is (but remove trailing .0 if present)
                return s.replace(".0", "")

            df["UID"] = (
                df["YR"].apply(clean_val) + "_" +
                df["STAT"].apply(clean_val) + "_" +
                df["SESON"].apply(clean_val) + "_" +
                df["ST"].apply(clean_val) + "_" +
                df["CROPCODE"].apply(clean_val) + "_" +
                df["DIST"].apply(clean_val) + "_" +
                df["VILL"].apply(clean_val) + "_" +
                df["EXPNO"].apply(clean_val)
            )
            # Move UID to first column
            cols = ["UID"] + [col for col in df.columns if col != "UID"]
            df = df[cols]

        logging.info(f"Loaded {len(df)} rows from {file_path.name}")
        return df

    def ingest_data(self) -> pd.DataFrame:
        logging.info("Entered ingest_data method of SchIngestion class")
        df = None

        try:
            # Capture ingestion timestamp
            ingestion_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                # Add created_at timestamp column
                df["created_at"] = ingestion_timestamp

                # Remove duplicates based on UID, keeping the latest row based on created_at
                if "UID" in df.columns:
                    initial_rows = len(df)
                    # Sort by created_at descending so latest rows come first
                    df = df.sort_values(by="created_at", ascending=False)
                    # Drop duplicates based on UID, keeping the first (latest) occurrence
                    df = df.drop_duplicates(subset=["UID"], keep="first")
                    final_rows = len(df)
                    duplicates_removed = initial_rows - final_rows
                    if duplicates_removed > 0:
                        logging.info(f"Removed {duplicates_removed} duplicate UID rows ({initial_rows} -> {final_rows})")

        except Exception as e:
            logging.info(f"Error occurred while ingesting schedule data from {self.params.input_path}")
            raise e

        # Ensure EXPTID is written as integer (no .0) in CSV output
        if "EXPTID" in df.columns:
            def exptid_to_int_str(x):
                if pd.isna(x):
                    return ""
                if isinstance(x, float):
                    return f"{int(x)}"
                if isinstance(x, int):
                    return str(x)
                try:
                    return str(int(float(x)))
                except (ValueError, TypeError):
                    return ""

            df["EXPTID"] = df["EXPTID"].apply(exptid_to_int_str)

        logging.info(f"Exited ingest_data method of SchIngestion class (total rows: {len(df)})")
        return df