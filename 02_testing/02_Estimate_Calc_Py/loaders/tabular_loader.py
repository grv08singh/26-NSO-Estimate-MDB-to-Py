"""
Tabular (CSV, Excel, pandas DataFrame) Data Loader.
"""
from typing import Optional, Union
import pandas as pd
from .base_loader import BaseDataLoader

class TabularDataLoader(BaseDataLoader):
    """
    Loads experiment records and district areas from CSV, Excel, or in-memory DataFrames.
    """
    def __init__(
        self,
        experiments_source: Union[str, pd.DataFrame],
        areas_source: Optional[Union[str, pd.DataFrame]] = None
    ):
        self.experiments_source = experiments_source
        self.areas_source = areas_source

    def _read_source(self, source: Union[str, pd.DataFrame]) -> pd.DataFrame:
        if isinstance(source, pd.DataFrame):
            df = source.copy()
        elif str(source).endswith(('.xlsx', '.xls')):
            df = pd.read_excel(source)
        else:
            df = pd.read_csv(source)
        
        df.columns = [str(c).upper().strip() for c in df.columns]
        return df

    def load_experiments(self) -> pd.DataFrame:
        return self._read_source(self.experiments_source)

    def load_areas(self) -> pd.DataFrame:
        if self.areas_source is not None:
            return self._read_source(self.areas_source)
        return pd.DataFrame(columns=['DISTRICT', 'AREA'])
