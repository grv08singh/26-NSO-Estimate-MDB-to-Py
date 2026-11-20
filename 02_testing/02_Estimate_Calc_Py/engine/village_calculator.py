"""
Village-Level Statistical Calculator (replicates Query4 & COL11NIJ2).
"""
import pandas as pd

class VillageCalculator:
    """
    Computes within-village aggregates and intermediate sums:
        - n_ij (count of experiments per village)
        - n_ij^2
        - col11_ij = (Sum_k y_ijk)^2 / n_ij
        - Sum_k y_ijk^2
    """

    @staticmethod
    def calculate_village_metrics(df_harvested: pd.DataFrame) -> pd.DataFrame:
        """
        Groups harvested records by District and Village (SELORDER) to compute
        village-level statistics.
        """
        if df_harvested.empty:
            return pd.DataFrame(columns=[
                'DISTRICT', 'DISTRICTNAME', 'SELORDER', 'nij', 'nij2',
                'sum_netweight', 'sum_netweight_sqr', 'col11'
            ])

        # Precompute individual weight squared
        df = df_harvested.copy()
        df['netweight_sqr'] = df['NETWEIGHT'] ** 2

        # Group by district and village
        grouped = df.groupby(['DISTRICT', 'DISTRICTNAME', 'SELORDER'], as_index=False).agg(
            nij=('NETWEIGHT', 'count'),
            sum_netweight=('NETWEIGHT', 'sum'),
            sum_netweight_sqr=('netweight_sqr', 'sum')
        )

        # Compute village components
        grouped['nij2'] = grouped['nij'] ** 2
        grouped['col11'] = (grouped['sum_netweight'] ** 2) / grouped['nij']

        return grouped

    @staticmethod
    def aggregate_to_district(village_df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates village metrics up to the district level (replicates COL11NIJ2):
            - SumOfcol11 = Sum_j col11_ij
            - SumOfnij2 = Sum_j n_ij^2
            - total_villages = m_i (count of distinct villages)
        """
        if village_df.empty:
            return pd.DataFrame(columns=[
                'DISTRICT', 'DISTRICTNAME', 'total_villages', 'SumOfcol11', 'SumOfnij2'
            ])

        dist_agg = village_df.groupby(['DISTRICT', 'DISTRICTNAME'], as_index=False).agg(
            total_villages=('SELORDER', 'nunique'),
            SumOfcol11=('col11', 'sum'),
            SumOfnij2=('nij2', 'sum')
        )
        return dist_agg
