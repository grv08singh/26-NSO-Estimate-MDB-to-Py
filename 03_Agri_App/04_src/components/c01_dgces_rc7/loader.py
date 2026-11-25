# Read the Excel file and join S and PW rows
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import openpyxl

from . import config

log = logging.getLogger(__name__)


# Missing columns error
class MissingColumnsError(Exception):
    pass


# Cell to clean text
def cell_to_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        text = str(value)
    elif isinstance(value, float):
        text = str(int(value)) if value.is_integer() else repr(value)
    elif isinstance(value, datetime):
        text = value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, date):
        text = value.strftime("%Y-%m-%d") + " 00:00:00"
    else:
        text = str(value)
    text = text.strip()
    if text.lower() in config.MISSING_TOKENS:
        return None
    return text


# Rename repeated headers
def dedupe_headers(headers: List[Optional[str]]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for i, h in enumerate(headers):
        name = (str(h).strip() if h is not None else "") or f"Unnamed: {i}"
        if name in seen:
            seen[name] += 1
            out.append(f"{name}.{seen[name]}")
        else:
            seen[name] = 0
            out.append(name)
    return out


# Read one sheet
def read_sheet(path: str, sheet: str) -> Tuple[List[str], List[Dict[str, Optional[str]]]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if sheet not in wb.sheetnames:
        raise MissingColumnsError(f"Sheet '{sheet}' not found in {path}. Sheets: {wb.sheetnames}")
    rows_iter = wb[sheet].iter_rows(values_only=True)
    try:
        headers = dedupe_headers(list(next(rows_iter)))
    except StopIteration:
        return [], []
    rows: List[Dict[str, Optional[str]]] = []
    for raw in rows_iter:
        values = [cell_to_str(v) for v in raw]
        if all(v is None for v in values):
            continue  # skip empty lines
        values += [None] * (len(headers) - len(values))
        rows.append(dict(zip(headers, values)))
    wb.close()
    return headers, rows


# Check required columns
def validate_columns(headers: List[str], required: List[str], sheet: str) -> None:
    missing = [c for c in required if c not in headers]
    if missing:
        raise MissingColumnsError(
            f"Sheet '{sheet}' is missing {len(missing)} required column(s):\n  - " + "\n  - ".join(missing))


# One joined row
@dataclass
class Row:
    s: Dict[str, Optional[str]]
    pw: Optional[Dict[str, Optional[str]]]
    index: int = 0
    extra: Dict[str, object] = field(default_factory=dict)

    # Supervisor value
    def S(self, col: str) -> Optional[str]:
        return self.s.get(col)

    # PW value
    def PW(self, col: str) -> Optional[str]:
        return self.pw.get(col) if self.pw is not None else None

    @property
    def matched(self) -> bool:
        return self.pw is not None

    # Row identity
    def ident(self) -> Dict[str, Optional[str]]:
        return {
            "District": self.S(config.S_DISTRICT),
            "Village": self.S(config.S_VILLAGE),
            "Crop": self.S(config.S_CROP),
            "EXPNO": self.S(config.S_EXPNO),
        }


def _key(row: Dict[str, Optional[str]], cols: List[str]) -> Tuple[str, ...]:
    return tuple((row.get(c) or "").strip().lower() for c in cols)


@dataclass
class LoadResult:
    rows: List[Row]
    s_count: int
    pw_count: int
    unmatched: List[Row]
    duplicate_pw_keys: List[Tuple[str, ...]]


# Join Supervisor and PW rows
def join(s_rows: List[Dict[str, Optional[str]]], pw_rows: List[Dict[str, Optional[str]]]) -> LoadResult:
    s_keys = [s for s, _ in config.JOIN_KEYS]
    pw_keys = [p for _, p in config.JOIN_KEYS]
    pw_index: Dict[Tuple[str, ...], Dict[str, Optional[str]]] = {}
    dups: List[Tuple[str, ...]] = []
    for r in pw_rows:
        k = _key(r, pw_keys)
        if k in pw_index:
            dups.append(k)
            continue
        pw_index[k] = r
    rows: List[Row] = []
    unmatched: List[Row] = []
    for i, s in enumerate(s_rows):
        row = Row(s=s, pw=pw_index.get(_key(s, s_keys)), index=i)
        rows.append(row)
        if not row.matched:
            unmatched.append(row)
    if dups:
        log.warning("%d duplicate PW join key(s); first PW row used", len(dups))
    return LoadResult(rows, len(s_rows), len(pw_rows), unmatched, dups)


# Find the input file
def find_input(raw_dir: str, explicit: Optional[str]) -> str:
    if explicit:
        if not os.path.isfile(explicit):
            raise FileNotFoundError(f"Input file not found: {explicit}")
        return explicit
    files = sorted(f for f in os.listdir(raw_dir)
                   if f.lower().endswith(".xlsx") and not f.startswith("~$"))
    if not files:
        raise FileNotFoundError(f"No .xlsx file found in {raw_dir}/")
    if len(files) > 1:
        raise ValueError(f"Several .xlsx files in {raw_dir}/ ({', '.join(files)}); use --input <file>")
    return os.path.join(raw_dir, files[0])


# Load and join both sheets
def load(path: str) -> LoadResult:
    s_headers, s_rows = read_sheet(path, config.SHEET_S)
    pw_headers, pw_rows = read_sheet(path, config.SHEET_PW)
    s_required = list(config.REQUIRED_S_COLUMNS)
    if config.CCE_DELEGATE_LEVEL_COLUMN:
        s_required.append(config.CCE_DELEGATE_LEVEL_COLUMN)
    pw_required = list(config.REQUIRED_PW_COLUMNS)
    if config.E3_PW_SEED_TYPE_COLUMN:
        pw_required.append(config.E3_PW_SEED_TYPE_COLUMN)
    errors = []
    for headers, req, sheet in ((s_headers, s_required, config.SHEET_S),
                                (pw_headers, pw_required, config.SHEET_PW)):
        try:
            validate_columns(headers, req, sheet)
        except MissingColumnsError as e:
            errors.append(str(e))
    if errors:
        raise MissingColumnsError("\n".join(errors))
    log.info("Read %d S rows and %d PW rows from %s", len(s_rows), len(pw_rows), path)
    return join(s_rows, pw_rows)
