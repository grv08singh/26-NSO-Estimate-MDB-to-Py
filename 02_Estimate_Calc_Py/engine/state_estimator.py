"""
State-Level Yield, Variance, and %SE Estimator (replicates %se and INTERMEDIATE TABLE reports).
"""
import math
from typing import List, Dict, Any, Tuple
from models.district_result import DistrictEstimate, StateEstimate

class StateEstimator:
    """
    Computes State-level weighted yield rate (kg/ha), ANOVA variance components,
    Standard Error (kg/ha), and Percentage Standard Error (%SE).
    """

    @staticmethod
    def estimate_state(
        district_estimates: List[DistrictEstimate],
        state_code: str = '',
        state_name: str = '',
        crop_code: str = '',
        crop_name: str = '',
        season_name: str = '',
        sample_name: str = '',
        year: str = ''
    ) -> StateEstimate:
        """
        Aggregates district estimates into a comprehensive state-level statistical estimate.
        """
        dist_dict = {d.district_code: d for d in district_estimates}
        
        # Area and Production totals
        total_area = sum(d.area for d in district_estimates)
        total_avy_area = sum(d.avy_times_area for d in district_estimates)
        total_expt = sum(d.num_experiments for d in district_estimates)
        total_villages = sum(d.num_villages for d in district_estimates)

        # State dry yield: Round(Sum(dryyield * area) / Sum(area), 0)
        if total_area > 0:
            state_dry_yield = round(total_avy_area / total_area, 0)
        else:
            state_dry_yield = 0.0

        # Totals for variance calculations
        sum_mi_minus_1 = sum(d.mi_minus_1 for d in district_estimates)
        sum_ni_minus_mi = sum(d.ni_minus_mi for d in district_estimates)
        sum_col11 = sum(d.col11 for d in district_estimates)
        sum_col12 = sum(d.col12 for d in district_estimates)
        sum_ai2_ni = sum(d.ai2_ni for d in district_estimates)
        sum_i = sum(d.i_ratio for d in district_estimates)
        sum_check = sum(d.check_flag for d in district_estimates)
        sum_netweight2 = sum(d.sum_netweight_sqr for d in district_estimates)

        # Average CCF for non-zero districts
        valid_ccfs = [d.ccf for d in district_estimates if d.ccf > 0]
        avg_ccf = sum(valid_ccfs) / len(valid_ccfs) if valid_ccfs else 0.0

        # Check if sampling across all villages is equal (sum_i == sum_check)
        equal_sampling = (round(sum_i, 2) == round(sum_check, 2))

        # Text46 (Sum of text779):
        # IIf([expt]=0, 0, IIf([AccessTotalsi]=[AccessTotalscheck], 0, Round(([ai2/ni]*[nij2])/([expt]*[i]), 0)))
        text46 = 0.0
        if not equal_sampling:
            for d in district_estimates:
                if d.num_experiments > 0 and d.i_ratio > 0:
                    term = round((d.ai2_ni * d.nij2) / (d.num_experiments * d.i_ratio), 0)
                    text46 += term

        # Text48: IIf([AccessTotalsi]=[AccessTotalscheck], 0, [AccessTotalsnetweight2])
        text48 = 0.0 if equal_sampling else sum_netweight2

        # Text0 (Between-Village Mean Square): Round(([text50] - [text52]) / [text42], 0)
        # (Sum(col11) - Sum(col12)) / Sum(mi - 1)
        if sum_mi_minus_1 > 0:
            text0 = round((sum_col11 - sum_col12) / sum_mi_minus_1, 0)
        else:
            text0 = 0.0

        # Text1 (Within-Village Mean Square):
        # IIf([text48]=0, "Not Applicable", Round(([text48] - [text50]) / [text44], 0))
        if text48 == 0 or sum_ni_minus_mi == 0:
            text1 = "Not Applicable"
            text2 = "Not Applicable"
            # Text3: Round([text0] * [text54] / ([text58] * [text58]), 0)
            if total_area > 0:
                text3 = round((text0 * sum_ai2_ni) / (total_area ** 2), 0)
            else:
                text3 = 0.0
        else:
            text1 = round((text48 - sum_col11) / sum_ni_minus_mi, 0)
            text2 = text0 - text1
            # Text3: Round(([text1] * [text54] + [text2] * [text46]) / ([text58] * [text58]), 0)
            if total_area > 0:
                text3 = round((text1 * sum_ai2_ni + text2 * text46) / (total_area ** 2), 0)
            else:
                text3 = 0.0

        # Text4 (Dry Yield Variance): Round([text3] * ([text62] * [text62]), 0)
        # Green variance * (avg_ccf ^ 2)
        text4 = round(text3 * (avg_ccf ** 2), 0)
        # Avoid negative variance due to severe sampling anomalies
        text4 = max(0.0, text4)

        # Text5 (Standard Error in kg/ha): Round(Sqr([text4]), 2)
        text5 = round(math.sqrt(text4), 2)

        # Text6 (Percentage Standard Error %SE): Round([text5] * 100 / [text60], 1)
        if state_dry_yield > 0:
            text6 = round((text5 * 100.0) / state_dry_yield, 1)
        else:
            text6 = 0.0

        return StateEstimate(
            state_code=state_code,
            state_name=state_name,
            crop_code=crop_code,
            crop_name=crop_name,
            season_name=season_name,
            sample_name=sample_name,
            year=year,
            total_area=total_area,
            total_production_proxy=total_avy_area,
            state_dry_yield=state_dry_yield,
            total_experiments=total_expt,
            total_villages=total_villages,
            avg_ccf=avg_ccf,
            between_village_ms=text0,
            within_village_ms=text1,
            ms_difference=text2,
            green_yield_variance=text3,
            dry_yield_variance=text4,
            standard_error=text5,
            percentage_se=text6,
            district_estimates=dist_dict
        )
