"""
Experiment Data Preprocessor.
"""
from typing import Optional
import pandas as pd

class ExperimentPreprocessor:
    """
    Cleans, filters, and standardizes experiment records for estimation.
    """

    @staticmethod
    def filter_harvested(df: pd.DataFrame) -> pd.DataFrame:
        """
        Keeps only successfully inspected and non-rejected experiments:
        INSPSTATE == '1' and REJ != '1'.
        """
        df = df.copy()
        mask_insp = df['INSPSTATE'].astype(str).str.strip() == '1'
        mask_rej = df['REJ'].astype(str).str.strip() != '1'
        return df[mask_insp & mask_rej].copy()

    @staticmethod
    def filter_by_criteria(
        df: pd.DataFrame,
        state_code: Optional[str] = None,
        season_code: Optional[str] = None,
        crop_code: Optional[str] = None,
        sample_type: Optional[str] = None,
        conversion_type: int = 1
    ) -> pd.DataFrame:
        """
        Filters data by user criteria and handles conversion types:
            - conversion_type 1: Standard sample (Central='1', State='2')
            - conversion_type 2: Combined sample (both Central and State, recoding crop_code to parent 'XX00')
        """
        df = df.copy()

        if state_code:
            df = df[df['STATE'].astype(str).str.strip() == str(state_code).strip()]

        if season_code:
            df = df[df['SEASONCODE'].astype(str).str.strip() == str(season_code).strip()]

        if conversion_type == 2:
            # Combined sample: includes both Central ('1') and State ('2')
            df = df[df['SAMPLE'].astype(str).str.strip().isin(['1', '2'])]
            if crop_code:
                # In combined mode, crop code is matched on parent group (e.g. '1611' -> '1600')
                parent_prefix = str(crop_code).strip()[:2]
                df = df[df['CROPCODE'].astype(str).str.strip().str.startswith(parent_prefix)]
        else:
            if sample_type:
                df = df[df['SAMPLE'].astype(str).str.strip() == str(sample_type).strip()]
            if crop_code:
                df = df[df['CROPCODE'].astype(str).str.strip() == str(crop_code).strip()]

        # Ensure NETWEIGHT is float
        df['NETWEIGHT'] = pd.to_numeric(df['NETWEIGHT'], errors='coerce').fillna(0.0)
        return df
