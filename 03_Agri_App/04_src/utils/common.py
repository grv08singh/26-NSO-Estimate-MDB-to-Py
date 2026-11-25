import os
import yaml
from src.logger import logging
try:
    from ensure import ensure_annotations
except ImportError:          # 'ensure' only checks argument types; run without it if it is not installed
    def ensure_annotations(fn):
        return fn
from pathlib import Path
from typing import Any
import json
import joblib
import pandas as pd
import pyodbc
import numpy as np


class ConfigBox(dict):
    """Simple dict subclass allowing attribute access to keys."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            if isinstance(v, dict):
                self[k] = ConfigBox(v)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'ConfigBox' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value


class BoxValueError(ValueError):
    """Placeholder for BoxValueError."""
    pass


@ensure_annotations
def read_yaml(path: Path) -> ConfigBox:
    logging.info("Entered Method read_yaml")
    try:
        with open(path, 'r') as yaml_file:
            content = yaml.safe_load(yaml_file)
            logging.info(f"YAML file loaded successfully: {path}")
            logging.info("Exited Method read_yaml")
            return ConfigBox(content)
    except BoxValueError as e:
        logging.info(f"YAML file is empty: {path}")
        raise ValueError("YAML file is empty")
    except Exception as e:
        logging.info(f"Error occurred while loading YAML: {path}")
        raise e

@ensure_annotations
def create_directories(path_list: list, verbose=True):
    logging.info("Entered Method create_directories")
    for path in path_list:
        os.makedirs(path, exist_ok=True)
        if verbose:
            logging.info(f"Directory created: {path}")
    logging.info("Exited Method create_directories")

@ensure_annotations
def save_json(path: Path, data: dict):
    logging.info("Entered Method save_json")
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"JSON file saved at {path}")
    logging.info("Exited Method save_json")

@ensure_annotations
def load_json(path: Path) -> dict:
    logging.info("Entered Method load_json")
    with open(path, 'r') as f:
        content = json.load(f)
    logging.info(f"JSON loaded: {path}")
    logging.info("Exited Method load_json")
    return ConfigBox(content)

@ensure_annotations
def save_csv(path: Path, data: pd.DataFrame):
    logging.info("Entered Method save_csv")
    try:
        if path.exists():
            existing_df = pd.read_csv(path)
            combined_df = pd.concat([existing_df, data], ignore_index=True)
            combined_df.to_csv(path, index=False)
            logging.info(f"Appended {len(data)} rows to existing CSV at {path} (total: {len(combined_df)} rows)")
        else:
            data.to_csv(path, index=False, encoding='utf-8')
            logging.info(f"CSV file saved at {path} ({len(data)} rows)")
    except Exception as e:
        logging.info(f"Error occurred while saving CSV: {path}")
        raise e
    logging.info("Exited Method save_csv")

@ensure_annotations
def load_csv(path: Path) -> pd.DataFrame:
    """Load CSV file without column standardization."""
    logging.info("Entered Method load_csv")
    try:
        content = pd.read_csv(path)
        logging.info(f"CSV file loaded successfully: {path} ({len(content)} rows)")
    except Exception as e:
        logging.info(f"Error occurred while loading CSV: {path}")
        raise e
    logging.info("Exited Method load_csv")
    return content

@ensure_annotations
def load_mdb(path: Path, table: str) -> pd.DataFrame:
    """Load MDB table without column standardization."""
    logging.info("Entered Method load_mdb")
    try:
        conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            f"DBQ={path};"
        )
        conn = pyodbc.connect(conn_str)
        query = f"SELECT * FROM [{table}]"
        content = pd.read_sql(query, conn)
        conn.close()
        logging.info(f"MDB table '{table}' loaded from {path} ({len(content)} rows)")
    except Exception as e:
        logging.info(f"Error occurred while loading MDB: {path}")
        raise e
    logging.info("Exited Method load_mdb")
    return content

@ensure_annotations
def load_excel(path: Path) -> pd.DataFrame:
    """Load all sheets from Excel file without column filtering."""
    logging.info("Entered Method load_excel")
    try:
        all_sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        valid_dfs = []
        for name, sheet_df in all_sheets.items():
            if not sheet_df.empty:
                valid_dfs.append(sheet_df)
                logging.info(f"Loaded sheet '{name}' from {path} ({len(sheet_df)} rows)")
            else:
                logging.info(f"Skipped empty sheet '{name}' from {path}")
        if valid_dfs:
            content = pd.concat(valid_dfs, ignore_index=True)
        else:
            logging.warning(f"No valid sheets found in {path}")
            content = pd.DataFrame()
    except Exception as e:
        logging.info(f"Error occurred while loading Excel: {path}")
        raise e
    logging.info("Exited Method load_excel")
    return content