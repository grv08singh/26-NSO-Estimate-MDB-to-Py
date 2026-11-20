"""
Experiment and Raw Observation Models.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExperimentRecord:
    """
    Represents a single Crop Cutting Experiment (CCE) observation.
    
    Attributes:
        state_code (str): Two-digit state code.
        season_code (str): Season code (e.g. 1=Autumn, 2=Winter, 3=Summer, 4=Rabi).
        crop_code (str): 4-digit crop code.
        sample_type (str): Sample code ('1' = Central, '2' = State).
        district_code (str): Two-digit district code.
        district_name (str): Name of the district.
        sel_order (str): Selection order of the village / FSU (e.g. '01', '02', ...).
        expt_no (str): Experiment number within village ('1', '2', etc.).
        insp_state (str): Inspection status ('1' = inspected/harvested, '2'=missed, '3'=lost).
        rejected (str): Rejection flag ('1' = rejected, other/empty = valid).
        net_weight (float): Net green weight of harvested crop in grams.
        year (str): Survey reference year (e.g. '2024-25').
    """
    state_code: str
    season_code: str
    crop_code: str
    sample_type: str
    district_code: str
    district_name: str
    sel_order: str
    expt_no: str
    insp_state: str = '1'
    rejected: str = '0'
    net_weight: float = 0.0
    year: str = ''

    @property
    def is_valid_harvest(self) -> bool:
        """Only experiments with insp_state == '1' and rejected != '1' enter calculations."""
        return str(self.insp_state).strip() == '1' and str(self.rejected).strip() != '1'
