"""
Unit and Integration Tests for NSO Estimation Pipeline.
"""
import unittest
import os
import sys
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.conversion_factors import ConversionFactors
from loaders.mock_loader import MockDataLoader
from loaders.access_loader import AccessDataLoader
from loaders.tabular_loader import TabularDataLoader
from engine.village_calculator import VillageCalculator
from engine.district_calculator import DistrictCalculator
from engine.state_estimator import StateEstimator
from pipeline import NSOEstimatePipeline

class TestNSOEstimatePipeline(unittest.TestCase):

    def test_conversion_factors(self):
        factors = ConversionFactors(driage_ratio=0.75, recovery_ratio=1.0, conversion_factor=0.4)
        self.assertAlmostEqual(factors.ccf, 0.30, places=4)
        with self.assertRaises(ValueError):
            ConversionFactors(driage_ratio=-0.1).validate()

    def test_village_calculator_known_values(self):
        # 1 district, 1 village, 2 experiments with weights 10000 and 12000
        df = pd.DataFrame([
            {'DISTRICT': '01', 'DISTRICTNAME': 'TEST_DIST', 'SELORDER': '01', 'NETWEIGHT': 10000, 'INSPSTATE': '1', 'REJ': '0'},
            {'DISTRICT': '01', 'DISTRICTNAME': 'TEST_DIST', 'SELORDER': '01', 'NETWEIGHT': 12000, 'INSPSTATE': '1', 'REJ': '0'},
        ])
        v_df = VillageCalculator.calculate_village_metrics(df)
        self.assertEqual(len(v_df), 1)
        row = v_df.iloc[0]
        self.assertEqual(row['nij'], 2)
        self.assertEqual(row['nij2'], 4)
        self.assertEqual(row['sum_netweight'], 22000)
        # col11 = 22000^2 / 2 = 484,000,000 / 2 = 242,000,000
        self.assertEqual(row['col11'], 242000000.0)

    def test_mock_pipeline_execution(self):
        factors = ConversionFactors(driage_ratio=0.75, recovery_ratio=1.0, conversion_factor=0.4)
        pipeline = NSOEstimatePipeline(loader=MockDataLoader(seed=123), conversion_factors=factors)
        result = pipeline.run(state_code='33', season_code='4', crop_code='1611', sample_type='2')

        self.assertIsNotNone(result)
        self.assertGreater(result.state_dry_yield, 0)
        self.assertGreaterEqual(result.dry_yield_variance, 0)
        self.assertGreaterEqual(result.standard_error, 0)
        self.assertGreater(result.percentage_se, 0)
        self.assertGreater(result.total_experiments, 0)

        df_dist = pipeline.to_district_dataframe()
        self.assertEqual(len(df_dist), 4)
        self.assertIn('dryyield', df_dist.columns)
        self.assertIn('avy*area', df_dist.columns)

    def test_access_database_matching(self):
        db_path = r"d:\05 GIT\26-NSO-Estimate-MDB-to-Py\01_Estimate_Workflow_in_mdb\ASSOFTWARE\ESTIMATE.accdb"
        if not os.path.exists(db_path):
            self.skipTest(f"Access database not found at {db_path}")

        # In final table of ESTIMATE.accdb:
        # DHARMAPURI: netweight=64920, expt=4, ccf=0.30008, dryyield=4870
        factors = ConversionFactors(driage_ratio=0.7502, recovery_ratio=1.0, conversion_factor=0.4)
        pipeline = NSOEstimatePipeline(db_path=db_path, conversion_factors=factors)
        
        # Test loading
        df_raw = pipeline.loader.load_experiments()
        self.assertFalse(df_raw.empty)
        self.assertIn('NETWEIGHT', df_raw.columns)

if __name__ == '__main__':
    unittest.main()
