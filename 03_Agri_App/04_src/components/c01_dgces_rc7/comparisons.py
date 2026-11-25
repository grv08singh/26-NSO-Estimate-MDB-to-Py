# Comparison codes (E1, E3, E5-E9, E15)
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from . import config


# Is the value missing
def is_missing(value: Optional[str]) -> bool:
    return value is None or str(value).strip().lower() in config.MISSING_TOKENS


# Yes / No or None
def yes_no(value: Optional[str]) -> Optional[str]:
    if is_missing(value):
        return None
    v = str(value).strip().lower()
    if v in config.YES_TOKENS:
        return "yes"
    if v in config.NO_TOKENS:
        return "no"
    return None


# Compare two values (1 / 2 / 9)
def standard_rule(pw: Optional[object], s: Optional[object]) -> int:
    if pw is None or s is None:
        return config.CMP_MISSING
    return config.CMP_SAME if pw == s else config.CMP_MISMATCH


# E1: survey number mistake
def compare_e1(sn_mistake: Optional[str], subsn_mistake: Optional[str]) -> int:
    sn = yes_no(sn_mistake)
    sub = yes_no(subsn_mistake)
    sub_na = not is_missing(subsn_mistake) and str(subsn_mistake).strip().lower() in config.NA_TOKENS
    if sn is None or (sub is None and not sub_na):
        return config.CMP_MISSING
    if sn == "yes" or sub == "yes":
        return config.CMP_MISMATCH
    if sub_na:
        return config.CMP_NOT_ENVISAGED
    return config.CMP_SAME


# Measurement as a number
def _measure(value: Optional[str]) -> Optional[object]:
    if is_missing(value):
        return None
    v = str(value).strip()
    try:
        return float(v)
    except ValueError:
        return v


# E9: length and breadth
def compare_e9(pairs: Sequence[Tuple[Optional[str], Optional[str]]]) -> Tuple[int, List[int]]:
    cleaned = [(_measure(p), _measure(s)) for p, s in pairs]
    missing = [i + 1 for i, (p, s) in enumerate(cleaned) if p is None or s is None]
    if missing:
        return config.CMP_MISSING, missing
    differ = [i + 1 for i, (p, s) in enumerate(cleaned) if p != s]
    return (config.CMP_MISMATCH if differ else config.CMP_SAME), differ


# E5-E8: yes / no compare
def compare_yes_no(pw_value: Optional[str], s_value: Optional[str]) -> int:
    return standard_rule(yes_no(pw_value), yes_no(s_value))


# Seed type code
def seed_type(value: Optional[str]) -> Optional[int]:
    if is_missing(value):
        return None
    return config.SEED_TYPE_CODES.get(str(value).strip().lower())


# E3: seed type
def compare_e3(pw_value: Optional[str], s_value: Optional[str],
               not_envisaged: bool = config.E3_PW_NOT_ENVISAGED) -> int:
    if not_envisaged:
        return config.CMP_NOT_ENVISAGED
    return standard_rule(seed_type(pw_value), seed_type(s_value))


# PW pure or mixture
def pw_pure_mixture(value: Optional[str]) -> Optional[str]:
    if is_missing(value):
        return None
    v = str(value).strip().lower()
    if v == config.PW_PURE_TEXT:
        return config.PURE
    if v.startswith(config.PW_MIXTURE_PREFIX):
        return config.MIXTURE
    return None


# S pure or mixture
def s_pure_mixture(num_crops: Optional[str]) -> Optional[str]:
    if is_missing(num_crops):
        return None
    try:
        n = float(str(num_crops).strip())
    except ValueError:
        return None
    if n == 1:
        return config.PURE
    if n > 1:
        return config.MIXTURE
    return None


# E15: pure or mixture
def compare_e15(pw_value: Optional[str], s_num_crops: Optional[str]) -> int:
    return standard_rule(pw_pure_mixture(pw_value), s_pure_mixture(s_num_crops))
