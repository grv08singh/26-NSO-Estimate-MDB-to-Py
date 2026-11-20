"""
NSO Crop Yield & Standard Error Estimation Pipeline.
Main Orchestrator Class: NSOEstimatePipeline.
"""
from typing import Optional, Dict, Any, Union
import json
import pandas as pd

from models.conversion_factors import ConversionFactors
from models.district_result import DistrictEstimate, StateEstimate
from loaders.base_loader import BaseDataLoader
from loaders.access_loader import AccessDataLoader
from loaders.tabular_loader import TabularDataLoader
from loaders.mock_loader import MockDataLoader
from engine.preprocessor import ExperimentPreprocessor
from engine.village_calculator import VillageCalculator
from engine.district_calculator import DistrictCalculator
from engine.merger import DistrictMerger
from engine.state_estimator import StateEstimator

class NSOEstimatePipeline:
    """
    End-to-end modular pipeline to calculate crop yield rate (kg/ha)
    and percentage Standard Error (%SE) replicating NSO's ESTIMATE.accdb.
    """

    def __init__(
        self,
        loader: Optional[BaseDataLoader] = None,
        conversion_factors: Optional[ConversionFactors] = None,
        db_path: Optional[str] = None,
        table_name: str = 'total estimate',
        experiments_file: Optional[str] = None,
        areas_file: Optional[str] = None
    ):
        """
        Initializes the pipeline with either a custom BaseDataLoader or paths to data files.
        """
        if loader is not None:
            self.loader = loader
        elif db_path is not None:
            self.loader = AccessDataLoader(db_path=db_path, table_name=table_name)
        elif experiments_file is not None:
            self.loader = TabularDataLoader(experiments_source=experiments_file, areas_source=areas_file)
        else:
            self.loader = MockDataLoader()

        self.factors = conversion_factors or ConversionFactors()
        self.state_result: Optional[StateEstimate] = None

    def run(
        self,
        state_code: Optional[str] = None,
        season_code: Optional[str] = None,
        crop_code: Optional[str] = None,
        sample_type: Optional[str] = None,
        conversion_type: int = 1,
        merge_mapping: Optional[Dict[str, str]] = None,
        state_name: str = '',
        crop_name: str = '',
        season_name: str = '',
        sample_name: str = '',
        year: str = ''
    ) -> StateEstimate:
        """
        Executes the complete estimation workflow:
            1. Loads raw experiments and district areas.
            2. Filters to harvested & valid experiments (INSPSTATE='1', REJ!='1').
            3. Applies selection criteria (state, season, crop, sample, conversion type).
            4. Calculates village-level components (col11, nij^2).
            5. Aggregates to district level with area data and CCF.
            6. Applies district merges if specified.
            7. Computes district Green Yield, Dry Yield, and ANOVA terms.
            8. Computes State Yield, ANOVA variance components, SE, and %SE.
        """
        self.factors.validate()

        # Step 1: Load data
        df_raw = self.loader.load_experiments()
        df_areas = self.loader.load_areas()

        # Extract metadata if available in records
        if not df_raw.empty:
            if not state_name and 'STATENAME' in df_raw.columns:
                state_name = str(df_raw['STATENAME'].dropna().iloc[0])
            if not crop_name and 'CROPNAME' in df_raw.columns:
                crop_name = str(df_raw['CROPNAME'].dropna().iloc[0])
            if not season_name and 'SEASONNAME' in df_raw.columns:
                season_name = str(df_raw['SEASONNAME'].dropna().iloc[0])
            if not sample_name and 'SAMPLENAME' in df_raw.columns:
                sample_name = str(df_raw['SAMPLENAME'].dropna().iloc[0])
            if not year and 'YEAR' in df_raw.columns:
                year = str(df_raw['YEAR'].dropna().iloc[0])

        # Step 2 & 3: Preprocessing and Filtering
        df_harvested = ExperimentPreprocessor.filter_harvested(df_raw)
        df_filtered = ExperimentPreprocessor.filter_by_criteria(
            df_harvested,
            state_code=state_code,
            season_code=season_code,
            crop_code=crop_code,
            sample_type=sample_type,
            conversion_type=conversion_type
        )

        # Step 4: Village-level calculations
        village_metrics = VillageCalculator.calculate_village_metrics(df_filtered)
        dist_agg = VillageCalculator.aggregate_to_district(village_metrics)

        # Step 5: District-level calculations
        district_estimates = DistrictCalculator.calculate_districts(
            df_harvested=df_filtered,
            df_areas=df_areas,
            factors=self.factors,
            village_dist_agg=dist_agg
        )

        # Step 6: District Merging if specified
        if merge_mapping:
            merger = DistrictMerger(merge_mapping)
            # Re-run after applying merges to district tables if needed
            # For modularity, mark merged flags
            for d in district_estimates:
                if d.district_code in merge_mapping:
                    d.merged_with = merge_mapping[d.district_code]

        # Step 7: State-level Estimation
        self.state_result = StateEstimator.estimate_state(
            district_estimates=district_estimates,
            state_code=state_code or '',
            state_name=state_name,
            crop_code=crop_code or '',
            crop_name=crop_name,
            season_name=season_name,
            sample_name=sample_name,
            year=year
        )

        return self.state_result

    def to_district_dataframe(self) -> pd.DataFrame:
        """Returns district estimates as a pandas DataFrame."""
        if not self.state_result:
            raise RuntimeError("Pipeline has not been run yet. Call pipeline.run() first.")
        
        rows = [d.to_dict() for d in self.state_result.district_estimates.values()]
        return pd.DataFrame(rows)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the full estimation result as a dictionary."""
        if not self.state_result:
            raise RuntimeError("Pipeline has not been run yet. Call pipeline.run() first.")
        return self.state_result.to_dict()

    def export_csv(self, file_path: str) -> None:
        """Exports district estimates to a CSV file."""
        df = self.to_district_dataframe()
        df.to_csv(file_path, index=False)

    def export_json(self, file_path: str) -> None:
        """Exports state estimation summary to a JSON file."""
        data = self.to_dict()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def print_summary(self) -> None:
        """Prints a human-readable summary matching NSO's official report layout."""
        if not self.state_result:
            raise RuntimeError("Pipeline has not been run yet. Call pipeline.run() first.")
        
        res = self.state_result
        print("=" * 80)
        print("  GOVERNMENT OF INDIA - NATIONAL STATISTICAL OFFICE (NSO)")
        print("  IMPROVEMENT OF CROP STATISTICS (ICS) SCHEME")
        print("  ESTIMATE OF CROP YIELD & STANDARD ERROR")
        print("=" * 80)
        print(f"  State:   {res.state_name} ({res.state_code})")
        print(f"  Crop:    {res.crop_name} ({res.crop_code})")
        print(f"  Season:  {res.season_name}")
        print(f"  Sample:  {res.sample_name}")
        print(f"  Year:    {res.year}")
        print("-" * 80)
        print(f"  Total Area Sown (ha):       {res.total_area:,.2f}")
        print(f"  Total Villages Sampled:     {res.total_villages}")
        print(f"  Total Experiments Analysed: {res.total_experiments}")
        print(f"  Average CCF Factor:         {res.avg_ccf:.5f}")
        print("-" * 80)
        print(f"  ★ STATE ESTIMATED DRY YIELD: {res.state_dry_yield:,.0f} Kg / hectare")
        print(f"  ★ DRY YIELD VARIANCE:        {res.dry_yield_variance:,.0f}")
        print(f"  ★ STANDARD ERROR (SE):       {res.standard_error:,.2f} Kg / hectare")
        print(f"  ★ PERCENTAGE STANDARD ERROR: {res.percentage_se:.1f} %")
        print("=" * 80)
        print("\nANOVA & Sampling Design Variance Components:")
        print(f"  Between-Village MS (Text0):  {res.between_village_ms:,.0f}")
        print(f"  Within-Village MS (Text1):   {res.within_village_ms}")
        print(f"  MS Difference (Text2):       {res.ms_difference}")
        print(f"  Green Yield Variance (Text3):{res.green_yield_variance:,.0f}")
        print("=" * 80)
