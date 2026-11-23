from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from src.utils.common import load_csv
from src.logger import logging


@dataclass
class RC7PreprocessingParams:
    ml_ingested_path: Path
    sch_ingested_path: Path
    output_path: Path


class RC7Preprocessing:
    def __init__(self, params: RC7PreprocessingParams):
        self.params = params

    def _load_data(self, path: Path, name: str) -> pd.DataFrame:
        """Load CSV data from path."""
        logging.info(f"Loading {name} from {path}")
        df = load_csv(path)
        logging.info(f"Loaded {name} with shape {df.shape}")
        return df

    def _validate_uid_column(self, df: pd.DataFrame, name: str) -> None:
        """Validate that UID column exists in dataframe."""
        if "UID" not in df.columns:
            raise ValueError(f"UID column not found in {name}. Columns: {list(df.columns)}")
        logging.info(f"UID column validated in {name} ({df['UID'].nunique()} unique values)")

    def preprocess(self) -> pd.DataFrame:
        """
        Perform left join of ML ingested data (left) with schedule ingested (right) on UID,
        but only keep columns from a2 (RC7 data) plus UID in the final output.
        """
        logging.info("Starting RC7 preprocessing - left join on UID, keeping only a2 columns")

        # Load both datasets
        df_left = self._load_data(self.params.ml_ingested_path, "ML ingested data (a1)")
        df_right = self._load_data(self.params.sch_ingested_path, "Schedule ingested (a2)")

        # Validate UID columns exist
        self._validate_uid_column(df_left, "ML ingested data (a1)")
        self._validate_uid_column(df_right, "Schedule ingested (a2)")

        # Store original a2 columns (before merge)
        a2_columns = df_right.columns.tolist()

        # Perform left join: left=a1 (ML), right=a2 (RC7)
        logging.info(f"Performing left join on UID. Left shape: {df_left.shape}, Right shape: {df_right.shape}")

        df_merged = pd.merge(
            df_left,
            df_right,
            on="UID",
            how="left",
            suffixes=("_ML", "_RC7")
        )

        logging.info(f"Left join completed. Result shape: {df_merged.shape}")

        # Log join statistics
        rc7_cols = df_merged.filter(like="_RC7").columns
        right_matched = df_merged[rc7_cols[0]].notna().sum() if len(rc7_cols) > 0 else 0
        logging.info(f"Total UIDs from left (ML): {len(df_left)}")
        logging.info(f"UIDs with matching RC7 data: {right_matched}")
        logging.info(f"UIDs without RC7 match: {len(df_left) - right_matched}")

        # Keep only UID and a2 columns
        # After merge with suffixes, a2 columns may have _RC7 suffix (if conflict) or original name (if no conflict)
        cols_to_keep = ["UID"]
        for col in a2_columns:
            if col == "UID":
                continue
            # Check for _RC7 suffix first (conflict case), then original name (no conflict)
            rc7_col = f"{col}_RC7"
            if rc7_col in df_merged.columns:
                cols_to_keep.append(rc7_col)
            elif col in df_merged.columns:
                cols_to_keep.append(col)

        df_final = df_merged[cols_to_keep].copy()

        # Rename columns to remove _RC7 suffix for cleaner output
        rename_map = {}
        for col in a2_columns:
            if col == "UID":
                continue
            rc7_col = f"{col}_RC7"
            if rc7_col in df_final.columns:
                rename_map[rc7_col] = col
        df_final = df_final.rename(columns=rename_map)

        # Ensure EXPTID is integer type (nullable Int64 to handle NaN)
        if "EXPTID" in df_final.columns:
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

            df_final["EXPTID"] = df_final["EXPTID"].apply(exptid_to_int)
            df_final["EXPTID"] = df_final["EXPTID"].astype("Int64")

        logging.info(f"Final output shape (only a2 columns + UID): {df_final.shape}")
        logging.info(f"Columns kept: {list(df_final.columns)}")

        # Save the merged dataframe
        logging.info(f"Saving RC7 preprocessed data to {self.params.output_path}")
        self.params.output_path.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(self.params.output_path, index=False)
        logging.info(f"RC7 preprocessed data saved successfully ({df_final.shape})")

        return df_final