# Build RC7 rows
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from . import comparisons as cmp
from . import config
from . import converters as cv
from .loader import Row
from .report import Recorder
from .table import Table, to_int, to_number

log = logging.getLogger(__name__)

E9_PAIRS = [   # (PW column, S column): length, breadth
    (config.PW_FIELD_LENGTH, config.S_FIELD_LENGTH),
    (config.PW_FIELD_BREADTH, config.S_FIELD_BREADTH),
]

YES_NO_COMPARISONS = [   # (RC7 field, PW column, S column)
    ("E5", config.PW_IRRIGATION, config.S_IRRIGATED),
    ("E6", config.PW_FERTILIZER, config.S_FERTILIZER),
    ("E7", config.PW_MANURE, config.S_MANURE),
    ("E8", config.PW_PEST, config.S_PEST),
]


def _e1(row: Row, rec: Recorder, ident: Dict[str, object]) -> int:
    sn, sub = row.S(config.S_SN_MISTAKE), row.S(config.S_SUBSN_MISTAKE)
    for col, value in ((config.S_SN_MISTAKE, sn), (config.S_SUBSN_MISTAKE, sub)):
        ok = cmp.yes_no(value) is not None or (
            col == config.S_SUBSN_MISTAKE and str(value).strip().lower() in config.NA_TOKENS)
        if not cmp.is_missing(value) and not ok:
            rec.unmapped("E1", col, value, "not Yes/No/NA -> treated as missing")
    code = cmp.compare_e1(sn, sub)
    rec.comparison(ident, "E1", "", f"{sn} | {sub}", code)
    return code


def _e9(row: Row, rec: Recorder, ident: Dict[str, object]) -> int:
    pairs = [(row.PW(p), row.S(s)) for p, s in E9_PAIRS]
    code, pair_nos = cmp.compare_e9(pairs)
    label = ("missing in pair " if code == config.CMP_MISSING else "") + ", ".join(map(str, pair_nos))
    rec.comparison(ident, "E9", " | ".join(str(p) for p, _ in pairs),
                   " | ".join(str(s) for _, s in pairs), code, label)
    return code


def _e3(row: Row, rec: Recorder, ident: Dict[str, object]) -> Optional[int]:
    col = config.E3_PW_SEED_TYPE_COLUMN
    if col is None:
        return None
    pw, s = row.PW(col), row.S(config.S_SEED_TYPE)
    for source, value in ((col, pw), (config.S_SEED_TYPE, s)):
        if not cmp.is_missing(value) and cmp.seed_type(value) is None:
            rec.unmapped("E3", source, value, "unknown seed type -> treated as missing")
    code = cmp.compare_e3(pw, s, not_envisaged=config.E3_PW_NOT_ENVISAGED)
    rec.comparison(ident, "E3", pw, s, code)
    return code


def _yes_no_cmp(field: str, pw_col: str, s_col: str, row: Row, rec: Recorder,
                ident: Dict[str, object]) -> int:
    pw, s = row.PW(pw_col), row.S(s_col)
    if row.matched:
        cv.yes_no_logged(field, f"PW: {pw_col}", pw, rec)
    code = cmp.compare_yes_no(pw, s)
    rec.comparison(ident, field, pw, s, code)
    return code


def _e15(row: Row, rec: Recorder, ident: Dict[str, object]) -> int:
    pw, s = row.PW(config.PW_CROP_TYPE), row.S(config.S_NUM_CROPS)
    if not cmp.is_missing(pw) and cmp.pw_pure_mixture(pw) is None:
        rec.unmapped("E15", f"PW: {config.PW_CROP_TYPE}", pw, "not Pure/Mixture -> treated as missing")
    code = cmp.compare_e15(pw, s)
    rec.comparison(ident, "E15", f"{pw} -> {cmp.pw_pure_mixture(pw)}",
                   f"{s} -> {cmp.s_pure_mixture(s)}", code)
    return code


# RC7 values for one row
def build_row(row: Row, rec: Recorder) -> Dict[str, object]:
    ident = row.ident()
    S = row.S
    out: Dict[str, object] = {c: None for c in config.RC7_COLUMNS}

    out["RC"] = config.RC_VALUE
    out["ST"] = config.ST_VALUE
    out["YR"] = cv.yr(S(config.S_YEAR), rec, ident)
    out["SESON"] = cv.seson(S(config.S_SEASON), rec)
    out["CROP"] = cv.crop(S(config.S_CROP), rec)
    out["CONFAC"] = config.CONFAC_VALUE
    out["STAT"] = cv.to_int("STAT", config.S_STATE, S(config.S_STATE), rec, ident)
    out["DIST"] = cv.to_int("DIST", config.S_DISTRICT, S(config.S_DISTRICT), rec, ident)
    out["VILL"] = cv.to_int("VILL", config.S_VILLAGE, S(config.S_VILLAGE), rec, ident)
    out["RSV"] = cv.rsv(S(config.S_VILL_SUBST), S(config.S_VILL_SUBST_REASON), rec, ident)
    out["EXPNO"] = cv.to_int("EXPNO", config.S_EXPNO, S(config.S_EXPNO), rec, ident)
    out["STAGIN"] = cv.stagin(S(config.S_STAGE), rec)
    out["REXML"] = cv.rexml(S(config.S_EXP_MISSED), S(config.S_EXP_LOST), out["STAGIN"], rec, ident)
    level_col = config.CCE_DELEGATE_LEVEL_COLUMN
    out["CCE"] = cv.cce(S(config.S_PW_CONDUCTED), S(config.S_PW_TRAINED),
                        S(level_col) if level_col else None, rec, ident, level_col)
    out["CFC"] = cv.cfc(S(config.S_RECORDS), rec)
    out["RCSSN"] = cv.rcssn(S(config.S_SSN_SUBST), S(config.S_SSN_SUBST_REASON), rec, ident)
    out["E1"] = _e1(row, rec, ident)
    out["E2"] = cv.mistake_yes_no("E2", config.S_FIELD_MISTAKE, S(config.S_FIELD_MISTAKE), rec)
    out["E9"] = _e9(row, rec, ident)
    out["E11"] = cv.yes_no_code("E11", config.S_PLOT_LOCATION, S(config.S_PLOT_LOCATION), rec)
    out["E12"] = cv.yes_no_code("E12", config.S_PLOT_MEASURE, S(config.S_PLOT_MEASURE), rec)
    out["ADH"] = cv.adh(S(config.S_HARVEST_DATE), rec, ident)
    out["QTYG"] = cv.qtyg(S(config.S_HARVEST_WEIGHT), rec, ident)
    out["QTYP"] = cv.qtyp(S(config.S_NET_WEIGHT), rec, ident)
    out["E13"] = cv.yes_no_code("E13", config.S_WEIGHT_MISTAKE, S(config.S_WEIGHT_MISTAKE), rec)
    out["EQST"] = cv.equipment("EQST", config.S_EQ_SURVEY, S(config.S_EQ_SURVEY), rec)
    out["EQSB"] = cv.equipment("EQSB", config.S_EQ_BALANCE, S(config.S_EQ_BALANCE), rec)
    out["EQSW"] = cv.equipment("EQSW", config.S_EQ_WEIGHT, S(config.S_EQ_WEIGHT), rec)
    out["EQSP"] = cv.equipment("EQSP", config.S_EQ_PEGS, S(config.S_EQ_PEGS), rec)
    out["E14"] = cv.e14(S(config.S_DRIAGE), rec)
    out["STYPE"] = cv.stype(S(config.S_SEED_TYPE), rec)
    out["E3"] = _e3(row, rec, ident)
    out["SEEDR"] = cv.seedr(S(config.S_SEED_RATE), rec, ident)
    out["IRR"] = cv.yes_no_code("IRR", config.S_IRRIGATED, S(config.S_IRRIGATED), rec)
    out["NIRR"] = cv.nirr(S(config.S_NUM_IRRIGATIONS), rec, ident)
    out["FERTC"] = cv.yes_no_code("FERTC", config.S_FERTILIZER, S(config.S_FERTILIZER), rec)
    out["MANUR"] = cv.yes_no_code("MANUR", config.S_MANURE, S(config.S_MANURE), rec)
    out["PEST"] = cv.yes_no_code("PEST", config.S_PEST, S(config.S_PEST), rec)
    for field, pw_col, s_col in YES_NO_COMPARISONS:
        out[field] = _yes_no_cmp(field, pw_col, s_col, row, rec, ident)
    out["E15"] = _e15(row, rec, ident)
    out["CROPER"] = cv.croper(S(config.S_NUM_CROPS), rec, ident)
    out["CROPCON"] = cv.cropcon(S(config.S_CROP_CONDITION), rec, ident)
    out["AFFECT"] = cv.affect(S(config.S_AFFECT), rec)

    # cross-field checks
    if out["NIRR"] == 0 and out["IRR"] == config.YES_CODE:
        rec.issue("NIRR = 0 while IRR = 1", ident, "field irrigated but 0 irrigations")
    if out["QTYP"] == 0 and (out["QTYG"] or 0) > 0:
        rec.issue("QTYP = 0 while QTYG > 0", ident, f"QTYG = {out['QTYG']}")
    for c in config.ALWAYS_BLANK:
        out[c] = None
    return out


# Set value types
def _typed(records: List[Dict[str, object]]) -> Table:
    cols: Dict[str, List[object]] = {}
    for c in config.RC7_COLUMNS:
        vals = [r.get(c) for r in records]
        if c in config.FLOAT_COLUMNS:
            cols[c] = [to_number(v) for v in vals]
        elif c in config.MAYBE_FLOAT_COLUMNS:
            nums = [to_number(v) for v in vals]
            whole = all(f.is_integer() for f in nums if f is not None)
            cols[c] = [to_int(f) for f in nums] if whole else nums
        else:
            cols[c] = [to_int(v) for v in vals]
    return Table(config.RC7_COLUMNS, [list(r) for r in zip(*(cols[c] for c in config.RC7_COLUMNS))]
                 if records else [])


# Build the RC7 table
def build(rows: List[Row], rec: Recorder) -> Table:
    records = []
    for row in rows:
        if not row.matched:
            rec.issue("Unmatched join (no PW row)", row.ident(),
                      "all comparison fields set to 9")
        records.append(build_row(row, rec))
    return _typed(records)
