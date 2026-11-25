# RC7 field rules
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional, Union

from . import config
from .comparisons import is_missing, yes_no
from .report import Recorder

Ident = Optional[Dict[str, object]]
Number = Union[int, float]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
# Find a code
def lookup(table: Dict[str, object], value: Optional[str]) -> Optional[object]:
    if is_missing(value):
        return None
    return table.get(str(value).strip().lower())


# Code or blank
def code_or_blank(field: str, source: str, value: Optional[str], table: Dict[str, int],
                  rec: Recorder, action: str = config.ACTION_BLANK) -> Optional[int]:
    if is_missing(value):
        return None
    code = lookup(table, value)
    if code is None:
        rec.unmapped(field, source, value, action)
    return code


# Code or 9
def code_or_others(field: str, source: str, value: Optional[str], table: Dict[str, int],
                   rec: Recorder) -> Optional[int]:
    if is_missing(value):
        return None
    code = lookup(table, value)
    if code is None:
        rec.unmapped(field, source, value, config.ACTION_OTHERS)
        return config.OTHERS_CODE
    return code


# Yes / No or None
def yes_no_logged(field: str, source: str, value: Optional[str], rec: Recorder) -> Optional[str]:
    yn = yes_no(value)
    if yn is None and not is_missing(value):
        rec.unmapped(field, source, value, config.ACTION_NOT_YES_NO)
    return yn


# Text to number
def to_number(field: str, source: str, value: Optional[str], rec: Recorder,
              ident: Ident) -> Optional[float]:
    if is_missing(value):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        rec.issue(f"{field}: not a number", ident, f"{source} = {value!r}")
        return None


# Text to whole number
def to_int(field: str, source: str, value: Optional[str], rec: Recorder,
           ident: Ident) -> Optional[int]:
    n = to_number(field, source, value, rec, ident)
    if n is None:
        return None
    if not n.is_integer():
        rec.issue(f"{field}: not a whole number", ident, f"{source} = {value!r}")
        return None
    return int(n)


# int if whole
def whole_or_float(n: Optional[float]) -> Optional[Number]:
    if n is None:
        return None
    return int(n) if n.is_integer() else n


# ---------------------------------------------------------------------------
# Field rules
# ---------------------------------------------------------------------------
# YR: year
def yr(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    if is_missing(value):
        return None
    head = str(value).strip()[:4]
    if not head.isdigit():
        rec.issue("YR: bad year", ident, f"{config.S_YEAR} = {value!r}")
        return None
    return int(head)


# SESON: season
def seson(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("SESON", config.S_SEASON, value, config.SEASON_CODES, rec)


# CROP: crop code
def crop(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("CROP", config.S_CROP, value, config.CROP_CODES, rec, config.ACTION_CROP)


# RSV: village substitution
def rsv(substituted: Optional[str], reason: Optional[str], rec: Recorder,
        ident: Ident = None) -> Optional[int]:
    yn = yes_no_logged("RSV", config.S_VILL_SUBST, substituted, rec)
    if yn is None:
        return None
    if yn == "no":
        return config.RSV_NOT_SUBSTITUTED
    if is_missing(reason):
        rec.issue("RSV: Yes with reason missing", ident, f"{config.S_VILL_SUBST_REASON} is empty")
        return None
    return code_or_others("RSV", config.S_VILL_SUBST_REASON, reason, config.RSV_REASON_CODES, rec)


# STAGIN code
def stagin(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("STAGIN", config.S_STAGE, value, config.STAGE_CODES, rec)


# REXML: missed / lost reason
def rexml(missed: Optional[str], lost: Optional[str], stage_code: Optional[int],
          rec: Recorder, ident: Ident = None) -> Optional[int]:
    has_missed, has_lost = not is_missing(missed), not is_missing(lost)
    if not has_missed and not has_lost:
        return None
    use_lost = has_lost and not has_missed
    if has_missed and has_lost:
        use_lost = stage_code == config.STAGE_LOST
        rec.issue("REXML: both missed and lost reasons given", ident,
                  f"missed={missed!r}, lost={lost!r}; used {'lost' if use_lost else 'missed'} "
                  f"(STAGIN={stage_code})")
    if use_lost:
        return code_or_others("REXML", config.S_EXP_LOST, lost, config.REXML_LOST_CODES, rec)
    return code_or_others("REXML", config.S_EXP_MISSED, missed, config.REXML_MISSED_CODES, rec)


def _training(value: Optional[str], rec: Recorder) -> str:
    if is_missing(value):
        return config.CCE_TRAINING_NOT_KNOWN
    t = config.CCE_TRAINING.get(str(value).strip().lower())
    if t is None:
        rec.unmapped("CCE", config.S_PW_TRAINED, value, "treated as training not known")
        return config.CCE_TRAINING_NOT_KNOWN
    return t


# CCE code
def cce(conducted: Optional[str], trained: Optional[str], delegate_level: Optional[str],
        rec: Recorder, ident: Ident = None,
        level_column: Optional[str] = None) -> Optional[int]:
    yn = yes_no_logged("CCE", config.S_PW_CONDUCTED, conducted, rec)
    if yn is None:
        return None
    if yn == "yes":
        return config.CCE_MATRIX[(config.CCE_ASSIGNED, _training(trained, rec))]
    if level_column is None:
        rec.issue("CCE: delegated, delegate level not configured", ident,
                  "CCE_DELEGATE_LEVEL_COLUMN is None")
        return None
    level = lookup(config.CCE_DELEGATE_LEVELS, delegate_level)
    if level is None:
        rec.unmapped("CCE", level_column, delegate_level, config.ACTION_BLANK)
        return None
    return config.CCE_MATRIX[(level, _training(trained, rec))]


# CFC code
def cfc(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("CFC", config.S_RECORDS, value, config.CFC_CODES, rec)


# RCSSN: survey number substitution
def rcssn(substituted: Optional[str], reason: Optional[str], rec: Recorder,
          ident: Ident = None) -> Optional[int]:
    yn = yes_no_logged("RCSSN", config.S_SSN_SUBST, substituted, rec)
    if yn is None:
        return None
    if yn == "no":
        return config.RCSSN_NOT_SUBSTITUTED
    if is_missing(reason):
        rec.issue("RCSSN: AE = Yes with AF missing", ident, f"{config.S_SSN_SUBST_REASON} is empty")
        return None
    return code_or_others("RCSSN", config.S_SSN_SUBST_REASON, reason, config.RCSSN_REASON_CODES, rec)


# Yes 1, No 2, NA 8, missing 9
def mistake_yes_no(field: str, source: str, value: Optional[str], rec: Recorder) -> int:
    if not is_missing(value) and str(value).strip().lower() in config.NA_TOKENS:
        return config.CMP_NOT_ENVISAGED
    yn = yes_no_logged(field, source, value, rec)
    if yn is None:
        return config.CMP_MISSING
    return config.CMP_MISMATCH if yn == "yes" else config.CMP_SAME


# Yes 1, No 0
def yes_no_code(field: str, source: str, value: Optional[str], rec: Recorder) -> Optional[int]:
    yn = yes_no_logged(field, source, value, rec)
    if yn is None:
        return None
    return config.YES_CODE if yn == "yes" else config.NO_CODE


_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y")


# ADH: harvest day and month
def adh(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    if is_missing(value):
        rec.issue("ADH: date missing", ident, f"{config.S_HARVEST_DATE} is empty")
        return None
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return int(f"{d.day:02d}{d.month:02d}")
    rec.issue("ADH: unparseable date", ident, f"{config.S_HARVEST_DATE} = {value!r}")
    return None


# QTYG: weight in kg
def qtyg(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[float]:
    return to_number("QTYG", config.S_HARVEST_WEIGHT, value, rec, ident)


# QTYP: weight in grams
def qtyp(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    if is_missing(value):
        return None
    try:
        grams = Decimal(str(value).strip()) * 1000
    except InvalidOperation:
        rec.issue("QTYP: not a number", ident, f"{config.S_NET_WEIGHT} = {value!r}")
        return None
    return int(grams.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# Equipment codes
def equipment(field: str, source: str, value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank(field, source, value, config.EQUIPMENT_CODES, rec)


# E14: driage
def e14(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("E14", config.S_DRIAGE, value, config.DRIAGE_CODES, rec)


# STYPE: seed type
def stype(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_blank("STYPE", config.S_SEED_TYPE, value, config.SEED_TYPE_CODES, rec)


# SEEDR: seed rate
def seedr(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[Number]:
    return whole_or_float(to_number("SEEDR", config.S_SEED_RATE, value, rec, ident))


# NIRR: irrigations
def nirr(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    return to_int("NIRR", config.S_NUM_IRRIGATIONS, value, rec, ident)


# CROPER: crop percentage
def croper(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    n = to_number("CROPER", config.S_NUM_CROPS, value, rec, ident)
    if n is None:
        return None
    if n == 1:
        return config.CROPER_PURE
    rec.issue("CROPER: more than one crop, percentage not available", ident,
              f"{config.S_NUM_CROPS} = {value!r}")
    return None


# CROPCON: crop condition
def cropcon(value: Optional[str], rec: Recorder, ident: Ident = None) -> Optional[int]:
    if is_missing(value):
        return None
    return code_or_blank("CROPCON", config.S_CROP_CONDITION, value, config.CROP_CONDITION_CODES, rec)


# AFFECT code
def affect(value: Optional[str], rec: Recorder) -> Optional[int]:
    return code_or_others("AFFECT", config.S_AFFECT, value, config.AFFECT_CODES, rec)
