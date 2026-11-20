"""
District Merging Engine.
"""
from typing import Dict, Optional
import pandas as pd

class DistrictMerger:
    """
    Handles merging of small districts with target districts when configured.
    """
    def __init__(self, merge_mapping: Optional[Dict[str, str]] = None):
        """
        Args:
            merge_mapping: Dictionary mapping source district code to target district code.
                           E.g., {'01': '02'} merges district '01' into district '02'.
        """
        self.merge_mapping = merge_mapping or {}

    def apply_merges(self, district_data: pd.DataFrame) -> pd.DataFrame:
        """
        Applies merging rules across district summary metrics.
        """
        if not self.merge_mapping or district_data.empty:
            return district_data

        df = district_data.copy()
        for src_dist, target_dist in self.merge_mapping.items():
            if src_dist not in df['DISTRICT'].values:
                continue
            
            src_row = df[df['DISTRICT'] == src_dist].iloc[0]
            
            if target_dist == '1':
                # Excluded from calculation
                mask = df['DISTRICT'] == src_dist
                numeric_cols = [
                    'total_villages', 'expt', 'sum_netweight', 'sum_netweight_sqr',
                    'SumOfcol11', 'SumOfnij2', 'area'
                ]
                for col in numeric_cols:
                    if col in df.columns:
                        df.loc[mask, col] = 0
            elif target_dist in df['DISTRICT'].values:
                # Merge into target district
                tgt_idx = df[df['DISTRICT'] == target_dist].index[0]
                cols_to_sum = [
                    'total_villages', 'expt', 'sum_netweight', 'sum_netweight_sqr',
                    'SumOfcol11', 'SumOfnij2', 'area'
                ]
                for col in cols_to_sum:
                    if col in df.columns:
                        df.loc[tgt_idx, col] += src_row[col]
                
                # Zero out source district
                src_idx = df[df['DISTRICT'] == src_dist].index[0]
                for col in cols_to_sum:
                    if col in df.columns:
                        df.loc[src_idx, col] = 0

        return df
