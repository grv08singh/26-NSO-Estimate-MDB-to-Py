"""
Abstract Base Data Loader.
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import Tuple, Dict

class BaseDataLoader(ABC):
    """
    Abstract interface for loading CCE experiment records and district areas.
    """

    @abstractmethod
    def load_experiments(self) -> pd.DataFrame:
        """
        Loads raw experiment records into a standardized DataFrame.
        Columns required:
            - STATE (str)
            - SEASONCODE (str)
            - SAMPLE (str)
            - CROPCODE (str)
            - DISTRICT (str)
            - DISTRICTNAME (str)
            - SELORDER (str)
            - EXPT (str or int)
            - INSPSTATE (str)
            - REJ (str)
            - NETWEIGHT (float)
        """
        pass

    @abstractmethod
    def load_areas(self) -> pd.DataFrame:
        """
        Loads district area information.
        Columns required:
            - DISTRICT (str)
            - AREA (float in hectares)
        """
        pass
