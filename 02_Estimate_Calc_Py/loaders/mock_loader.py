"""
Mock / Synthetic Data Generator for Testing & Demos.
"""
import numpy as np
import pandas as pd
from .base_loader import BaseDataLoader

class MockDataLoader(BaseDataLoader):
    """
    Generates synthetic CCE experiment data and district crop areas for testing.
    """
    def __init__(
        self,
        num_districts: int = 4,
        villages_per_district: int = 5,
        experiments_per_village: int = 2,
        seed: int = 42
    ):
        self.num_districts = num_districts
        self.villages_per_district = villages_per_district
        self.experiments_per_village = experiments_per_village
        self.seed = seed

    def load_experiments(self) -> pd.DataFrame:
        np.random.seed(self.seed)
        records = []
        districts = [
            (f"{i+1:02d}", f"DISTRICT_{i+1}") for i in range(self.num_districts)
        ]
        
        for dist_code, dist_name in districts:
            for v in range(1, self.villages_per_district + 1):
                sel_order = f"{v:02d}"
                for e in range(1, self.experiments_per_village + 1):
                    # Realistic green weight between 5,000g and 22,000g
                    weight = int(np.random.normal(12000, 2500))
                    weight = max(2000, weight)
                    records.append({
                        'STATE': '33',
                        'SEASONCODE': '4',
                        'SAMPLE': '2',
                        'CROPCODE': '1611',
                        'DISTRICT': dist_code,
                        'DISTRICTNAME': dist_name,
                        'SELORDER': sel_order,
                        'EXPT': str(e),
                        'INSPSTATE': '1',
                        'REJ': '0',
                        'NETWEIGHT': weight,
                        'YEAR': '2024-25',
                        'CROPNAME': 'PADDY',
                        'STATENAME': 'TAMIL NADU',
                        'SEASONNAME': 'RABI',
                        'SAMPLENAME': 'STATE'
                    })
        return pd.DataFrame(records)

    def load_areas(self) -> pd.DataFrame:
        np.random.seed(self.seed)
        areas = []
        for i in range(self.num_districts):
            dist_code = f"{i+1:02d}"
            # Random district area in hectares (e.g. 10 to 500 ha)
            area_ha = float(np.random.randint(15, 80))
            areas.append({
                'DISTRICT': dist_code,
                'AREA': area_ha,
                'STATE': '33',
                'CROPCODE': '1611',
                'SEASONCODE': '4',
                'SAMPLE': '2'
            })
        return pd.DataFrame(areas)
