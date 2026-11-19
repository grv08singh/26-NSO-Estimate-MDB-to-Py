"""
District-Level Yield & Intermediate ANOVA Calculator (replicates finalquery).
"""
from typing import Dict, List, Optional
import pandas as pd
from models.conversion_factors import ConversionFactors
from models.district_result import DistrictEstimate

class DistrictCalculator:
    """
    Computes district-level Green Yield, Dry Yield (kg/ha), and intermediate ANOVA variance terms.
    """

    @staticmethod
    def calculate_districts(
        df_harvested: pd.DataFrame,
        df_areas: pd.DataFrame,
        factors: ConversionFactors,
        village_dist_agg: pd.DataFrame
    ) -> List[DistrictEstimate]:
        """
        Combines harvested experiments, village aggregates, and district crop areas
        to produce DistrictEstimate objects.
        """
        # Overall district totals from raw experiments
        if not df_harvested.empty:
            df_h = df_harvested.copy()
            df_h['netweight_sqr'] = df_h['NETWEIGHT'] ** 2
            dist_raw = df_h.groupby(['DISTRICT', 'DISTRICTNAME'], as_index=False).agg(
                expt=('NETWEIGHT', 'count'),
                sum_netweight=('NETWEIGHT', 'sum'),
                sum_netweight_sqr=('netweight_sqr', 'sum')
            )
        else:
            dist_raw = pd.DataFrame(columns=['DISTRICT', 'DISTRICTNAME', 'expt', 'sum_netweight', 'sum_netweight_sqr'])

        # Ensure area table has standard columns
        area_dict = {}
        if not df_areas.empty:
            for _, row in df_areas.iterrows():
                d_code = str(row['DISTRICT']).strip().zfill(2)
                area_val = float(row.get('AREA', 0.0) or 0.0)
                area_dict[d_code] = area_val

        # Merge raw totals with village aggregates
        if not dist_raw.empty and not village_dist_agg.empty:
            merged = pd.merge(dist_raw, village_dist_agg, on=['DISTRICT', 'DISTRICTNAME'], how='outer').fillna(0)
        elif not dist_raw.empty:
            merged = dist_raw.copy()
            merged['total_villages'] = 0
            merged['SumOfcol11'] = 0.0
            merged['SumOfnij2'] = 0.0
        else:
            merged = pd.DataFrame()

        results: List[DistrictEstimate] = []
        ccf = factors.ccf

        # Also ensure districts from area table with 0 experiments are included if present
        all_districts = set(merged['DISTRICT'].unique() if not merged.empty else [])
        all_districts.update(area_dict.keys())

        for dist_code in sorted(all_districts):
            d_code_str = str(dist_code).strip().zfill(2)
            row = merged[merged['DISTRICT'] == dist_code] if not merged.empty else pd.DataFrame()
            
            if not row.empty:
                r = row.iloc[0]
                dist_name = str(r['DISTRICTNAME'])
                n_i = int(r.get('expt', 0))
                m_i = int(r.get('total_villages', 0))
                netweight = float(r.get('sum_netweight', 0.0))
                netweight2 = float(r.get('sum_netweight_sqr', 0.0))
                col11 = float(r.get('SumOfcol11', 0.0))
                nij2 = float(r.get('SumOfnij2', 0.0))
            else:
                dist_name = f"DISTRICT_{d_code_str}"
                n_i = 0
                m_i = 0
                netweight = 0.0
                netweight2 = 0.0
                col11 = 0.0
                nij2 = 0.0

            area = float(area_dict.get(d_code_str, 0.0))

            # Mathematical formulas exactly matching MS Access finalquery:
            mi_minus_1 = max(0, m_i - 1) if m_i > 0 else 0
            ni_minus_mi = max(0, n_i - m_i)

            # i_ratio: Round((expt^2 - nij2) / (expt * (m_i - 1)), 2)
            if n_i > 0 and mi_minus_1 > 0:
                i_ratio = round((n_i**2 - nij2) / (n_i * mi_minus_1), 2)
            else:
                i_ratio = 0.0

            # ai2_ni: Round(area^2 / expt, 0)
            if n_i > 0:
                ai2_ni = round((area**2) / n_i, 0)
            else:
                ai2_ni = 0.0

            # col9: Round((area^2 * nij2) / (expt * i_ratio), 0)
            if n_i > 0 and i_ratio > 0:
                col9 = round(((area**2) * nij2) / (n_i * i_ratio), 0)
            else:
                col9 = 0.0

            # agreenyield: Round(netweight / expt, 0) (grams per plot)
            if n_i > 0:
                green_yield = round(netweight / n_i, 0)
            else:
                green_yield = 0.0

            # dryyield: Round(agreenyield * ccf, 0) (kg per hectare)
            if n_i > 0:
                dry_yield = round(green_yield * ccf, 0)
            else:
                dry_yield = 0.0

            # avy*area: dryyield * area
            if n_i > 0:
                avy_times_area = dry_yield * area
            else:
                avy_times_area = 0.0

            # col12: Round(netweight^2 / expt, 0)
            if n_i > 0:
                col12 = round((netweight**2) / n_i, 0)
            else:
                col12 = 0.0

            check_flag = 2 if n_i > 0 else 0

            est = DistrictEstimate(
                district_code=d_code_str,
                district_name=dist_name,
                num_villages=m_i,
                num_experiments=n_i,
                sum_netweight=netweight,
                sum_netweight_sqr=netweight2,
                area=area,
                ccf=ccf,
                col11=col11,
                nij2=nij2,
                mi_minus_1=mi_minus_1,
                ni_minus_mi=ni_minus_mi,
                i_ratio=i_ratio,
                ai2_ni=ai2_ni,
                col9=col9,
                green_yield=green_yield,
                dry_yield=dry_yield,
                avy_times_area=avy_times_area,
                col12=col12,
                check_flag=check_flag
            )
            results.append(est)

        return results
