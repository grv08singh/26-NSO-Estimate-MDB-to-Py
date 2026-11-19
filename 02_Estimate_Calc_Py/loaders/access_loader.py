"""
Microsoft Access (.accdb / .mdb) Data Loader using pyodbc.
"""
from typing import Optional
import pandas as pd
from .base_loader import BaseDataLoader

class AccessDataLoader(BaseDataLoader):
    """
    Loads experiment records and district areas directly from an Access database.
    """
    def __init__(self, db_path: str, table_name: str = 'total estimate'):
        self.db_path = db_path
        self.table_name = table_name

    def _get_connection(self):
        try:
            import pyodbc
        except ImportError:
            raise ImportError("pyodbc is required to load from Microsoft Access databases.")
        
        conn_str = rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={self.db_path};"
        return pyodbc.connect(conn_str)

    def load_experiments(self) -> pd.DataFrame:
        conn = self._get_connection()
        try:
            query = f"SELECT * FROM [{self.table_name}]"
            df = pd.read_sql(query, conn)
            # Ensure standard column naming and string formatting
            col_map = {
                'STATE': 'STATE',
                'SEASONCODE': 'SEASONCODE',
                'SAMPLE': 'SAMPLE',
                'CROPCODE': 'CROPCODE',
                'DISTRICT': 'DISTRICT',
                'DISTRICTNAME': 'DISTRICTNAME',
                'SELORDER': 'SELORDER',
                'EXPT': 'EXPT',
                'INSPSTATE': 'INSPSTATE',
                'REJ': 'REJ',
                'NETWEIGHT': 'NETWEIGHT'
            }
            # Normalize column names to uppercase
            df.columns = [str(c).upper().strip() for c in df.columns]
            return df
        finally:
            conn.close()

    def load_areas(self, area_table: str = 'areabasictablequery') -> pd.DataFrame:
        conn = self._get_connection()
        try:
            query = f"SELECT * FROM [{area_table}]"
            df = pd.read_sql(query, conn)
            df.columns = [str(c).upper().strip() for c in df.columns]
            return df
        except Exception:
            # Fallback to empty DataFrame if area table does not exist
            return pd.DataFrame(columns=['DISTRICT', 'AREA'])
        finally:
            conn.close()
