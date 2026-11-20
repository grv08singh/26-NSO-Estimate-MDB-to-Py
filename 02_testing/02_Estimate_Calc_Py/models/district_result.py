"""
District and State Estimation Result Models.
"""
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class DistrictEstimate:
    """
    Holds calculated metrics for a single district.
    """
    district_code: str
    district_name: str
    num_villages: int            # m_i
    num_experiments: int         # n_i
    sum_netweight: float         # Sum y_ijk (g)
    sum_netweight_sqr: float     # Sum y_ijk^2
    area: float                  # A_i (hectares)
    ccf: float                   # Composite conversion factor
    col11: float                 # Sum_j (Sum_k y_ijk)^2 / n_ij
    nij2: float                  # Sum_j n_ij^2
    mi_minus_1: int              # m_i - 1
    ni_minus_mi: int             # n_i - m_i
    i_ratio: float               # (n_i^2 - Sum n_ij^2) / (n_i * (m_i - 1))
    ai2_ni: float                # Round(A_i^2 / n_i, 0)
    col9: float                  # Round((A_i^2 * Sum n_ij^2) / (n_i * i_ratio), 0)
    green_yield: float           # Round(sum_netweight / num_experiments, 0) (g/plot)
    dry_yield: float             # Round(green_yield * ccf, 0) (kg/ha)
    avy_times_area: float        # dry_yield * area (proxy for production)
    col12: float                 # Round(sum_netweight^2 / num_experiments, 0)
    check_flag: int              # 2 if num_experiments > 0 else 0
    merged_with: str = ''        # target district if merged

    def to_dict(self) -> Dict[str, Any]:
        return {
            'district_code': self.district_code,
            'district_name': self.district_name,
            'village': self.num_villages,
            'expt': self.num_experiments,
            'netweight': self.sum_netweight,
            'netweight2': self.sum_netweight_sqr,
            'area': self.area,
            'ccf': self.ccf,
            'col11': self.col11,
            'nij2': self.nij2,
            'mi-1': self.mi_minus_1,
            'ni-mi': self.ni_minus_mi,
            'i': self.i_ratio,
            'ai2/ni': self.ai2_ni,
            'col9': self.col9,
            'agreenyield': self.green_yield,
            'dryyield': self.dry_yield,
            'avy*area': self.avy_times_area,
            'col12': self.col12,
            'check': self.check_flag,
            'merged_with': self.merged_with
        }

@dataclass
class StateEstimate:
    """
    Holds aggregated state-level estimation results including yield, variance, and %SE.
    """
    state_code: str
    state_name: str
    crop_code: str
    crop_name: str
    season_name: str
    sample_name: str
    year: str
    total_area: float                    # Sum A_i (hectares)
    total_production_proxy: float        # Sum (dry_yield * A_i)
    state_dry_yield: float               # Round(total_production_proxy / total_area, 0) (kg/ha)
    total_experiments: int               # Sum n_i
    total_villages: int                  # Sum m_i
    avg_ccf: float                       # Average CCF
    between_village_ms: float            # Text0 (Between-village mean square)
    within_village_ms: Any               # Text1 (Within-village mean square or "Not Applicable")
    ms_difference: Any                   # Text2 (Text0 - Text1 or "Not Applicable")
    green_yield_variance: float          # Text3
    dry_yield_variance: float            # Text4 (Variance in (kg/ha)^2)
    standard_error: float                # Text5 (SE in kg/ha = Sqrt(Variance))
    percentage_se: float                 # Text6 (%SE = (SE * 100) / state_dry_yield)
    district_estimates: Dict[str, DistrictEstimate] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'state_code': self.state_code,
            'state_name': self.state_name,
            'crop_code': self.crop_code,
            'crop_name': self.crop_name,
            'season_name': self.season_name,
            'sample_name': self.sample_name,
            'year': self.year,
            'total_area_ha': self.total_area,
            'total_experiments': self.total_experiments,
            'total_villages': self.total_villages,
            'state_dry_yield_kg_per_ha': self.state_dry_yield,
            'dry_yield_variance': self.dry_yield_variance,
            'standard_error_kg_per_ha': self.standard_error,
            'percentage_se': self.percentage_se,
            'between_village_ms': self.between_village_ms,
            'within_village_ms': self.within_village_ms,
            'green_yield_variance': self.green_yield_variance,
            'avg_ccf': self.avg_ccf,
            'districts': [d.to_dict() for d in self.district_estimates.values()]
        }
