# RC7 settings, column names and code tables
from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
RAW_DATA_DIR = "raw_data"
OUTPUT_DIR = "final_rc"

# ---------------------------------------------------------------------------
# Fixed values
# ---------------------------------------------------------------------------
RC_VALUE = 7          # record type
ST_VALUE = 1          # 1 = Central sample
CONFAC_VALUE = 0

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
# E3: PW seed-type column (None = blank)
E3_PW_SEED_TYPE_COLUMN: Optional[str] = None
# E3 = 8 when True
E3_PW_NOT_ENVISAGED = False

# CCE: delegate level column (None = blank)
CCE_DELEGATE_LEVEL_COLUMN: Optional[str] = None

# ---------------------------------------------------------------------------
# Input sheets
# ---------------------------------------------------------------------------
SHEET_S = "FinalNSOFieldData"          # Supervisor
SHEET_PW = "FinalNSO_PW_FieldData"     # Primary Worker

# Missing values
MISSING_TOKENS = {"", "none", "nan", "-"}

YES_TOKENS = {"yes"}
NO_TOKENS = {"no"}
# Not applicable values (code 8)
NA_TOKENS = {"na", "n/a", "not applicable"}

# ---------------------------------------------------------------------------
# Supervisor (S) columns
# ---------------------------------------------------------------------------
S_YEAR = "Year"
S_SEASON = "Season"
S_STATE = "State LGD Code"
S_DISTRICT = "District LGD Code"
S_VILLAGE = "Village LGD Code"
S_CROP = "Crop"
S_EXPNO = "Experiment No."
S_STAGE = "Stage of Supervision"
S_EXP_MISSED = "Reason for Experiment Missed"
S_EXP_LOST = "Reason for Experiment Lost"
S_VILL_SUBST = "Was the selected village substituted?"
S_VILL_SUBST_REASON = "Reason for village substitution"
S_ASSIGNED_PW = "Assigned PW Name"
S_PW_CONDUCTED = "Did the assigned pw conducted CCE?"
S_PW_NAME_CONDUCTED = "Name of PW conducted CCE"
S_PW_TRAINED = "Is PW trained?"
S_SSN_SUBST = "Was Survey/Sub-Survey No. substituted?"
S_SSN_SUBST_REASON = "Reason for Substitution"
S_RECORDS = "Records consulted for selection of Survey/Sub-Survey No."
S_SN_MISTAKE = "Any mistake with Survey No.?"            # col AK (E1)
S_SUBSN_MISTAKE = "Any mistake with Sub-Survey No.?"     # col AM (E1)
S_FIELD_MISTAKE = "Any mistake with Field Selection?"
S_PLOT_LOCATION = "Any mistake with Plot Location?"
S_PLOT_MEASURE = "Any mistake with Plot Measurement?"
S_HARVEST_DATE = "Date of harvest (actually harvested)"
S_HARVEST_WEIGHT = "Harvest Produce Weight (in Kg)"
S_NET_WEIGHT = "Net Weight (in Kg)"
S_WEIGHT_MISTAKE = "Any mistake with Weight Measurements?"
S_EQ_SURVEY = "Surveying Equipment Details"
S_EQ_PEGS = "Pegs Details"
S_EQ_BALANCE = "Balance Details"
S_EQ_WEIGHT = "Weight Details"
S_SEED_TYPE = "Type of Seed"
S_SEED_RATE = "Rate of Application (in Kg/Ha)"
S_IRRIGATED = "Was the field irrigated?"
S_NUM_IRRIGATIONS = "No. of Irrigations Applied"
S_FERTILIZER = "Was fertilizer applied?"
S_MANURE = "Was Manure Applied?"
S_PEST = "Was Pest Control Measures Adopted ?"   # note the space before "?"
S_CROP_CONDITION = "Crop Condition (in Exp. plot)"
S_AFFECT = "Crop affected reason"
S_NUM_CROPS = "Total no. of crop(s) sown in the field"
S_DRIAGE = "Rate Driage Exp. Planning & Storage Arrangements"
S_FIELD_LENGTH = "Length of field (in Steps)"      # col AZ
S_FIELD_BREADTH = "Breadth of field (in Steps)"    # col BC

# ---------------------------------------------------------------------------
# Primary Worker (PW) columns
# ---------------------------------------------------------------------------
PW_VILLAGE = "Village LGD Code"
PW_CROP = "Crop"  # second Crop column is read as Crop.1
PW_EXPNO = "Experiment No."
PW_IRRIGATION = "Irrigation Status"
PW_MANURE = "Was Manure Applied?"
PW_CROP_TYPE = "Crop Type (Pure or Mixture)"
PW_FERTILIZER = "Was Fertilizer Used?"
PW_PEST = "Was Pesticide/Insecticide Applied?"
PW_FIELD_LENGTH = "Length of field from South-West corner (in Steps)"    # col AV
PW_FIELD_BREADTH = "Breadth of field from South-West corner (in Steps)"  # col AW

# Join keys (S column, PW column)
JOIN_KEYS = [(S_VILLAGE, PW_VILLAGE), (S_CROP, PW_CROP), (S_EXPNO, PW_EXPNO)]

REQUIRED_S_COLUMNS: List[str] = [
    S_YEAR, S_SEASON, S_STATE, S_DISTRICT, S_VILLAGE, S_CROP, S_EXPNO, S_STAGE,
    S_EXP_MISSED, S_EXP_LOST, S_VILL_SUBST, S_VILL_SUBST_REASON, S_ASSIGNED_PW,
    S_PW_CONDUCTED, S_PW_NAME_CONDUCTED, S_PW_TRAINED, S_SSN_SUBST,
    S_SSN_SUBST_REASON, S_RECORDS, S_SN_MISTAKE, S_SUBSN_MISTAKE, S_FIELD_MISTAKE,
    S_PLOT_LOCATION, S_PLOT_MEASURE, S_HARVEST_DATE, S_HARVEST_WEIGHT, S_NET_WEIGHT,
    S_WEIGHT_MISTAKE, S_EQ_SURVEY, S_EQ_PEGS, S_EQ_BALANCE, S_EQ_WEIGHT, S_SEED_TYPE,
    S_SEED_RATE, S_IRRIGATED, S_NUM_IRRIGATIONS, S_FERTILIZER, S_MANURE, S_PEST,
    S_CROP_CONDITION, S_AFFECT, S_NUM_CROPS, S_DRIAGE, S_FIELD_LENGTH, S_FIELD_BREADTH,
]

REQUIRED_PW_COLUMNS: List[str] = [
    PW_VILLAGE, PW_CROP, PW_EXPNO,
    PW_IRRIGATION, PW_MANURE, PW_CROP_TYPE, PW_FERTILIZER, PW_PEST,
    PW_FIELD_LENGTH, PW_FIELD_BREADTH,
]

# ---------------------------------------------------------------------------
# RC7 columns
# ---------------------------------------------------------------------------
RC7_COLUMNS: List[str] = [
    "RC", "ST", "YR", "SESON", "CROP", "NEXP", "NEXNR", "CONFAC", "STAT", "DIST",
    "VILL", "RSV", "EXPNO", "STAGIN", "REXML", "CCE", "CFC", "RCSSN", "E1", "E2",
    "E9", "E10", "E11", "E12", "ADH", "QTYG", "QTYP", "E13", "EQST", "EQSB",
    "EQSW", "EQSP", "E14", "STYPE", "E3", "SVARC", "SEEDR", "E4", "IRR", "E5",
    "IRRP", "NIRR", "FERTC", "E6", "QTN", "CODN", "QTP", "CODP", "QTK", "CODK",
    "MANUR", "E7", "PEST", "E8", "E15", "REJ", "CROPER", "CROPCON", "AFFECT",
]
assert len(RC7_COLUMNS) == 59

# Always blank columns
ALWAYS_BLANK: Dict[str, str] = {
    "NEXP": "may be automated later",
    "NEXNR": "may be automated later",
    "E10": "deleted in mapping",
    "SVARC": "deleted; needs Khasra data",
    "E4": "PW seed quantity unit unclear",
    "IRRP": "not in data",
    "QTN": "N/P/K data not yet available",
    "CODN": "N/P/K data not yet available",
    "QTP": "N/P/K data not yet available",
    "CODP": "N/P/K data not yet available",
    "QTK": "N/P/K data not yet available",
    "CODK": "N/P/K data not yet available",
    "REJ": "not in data",
}

# Columns with decimals
FLOAT_COLUMNS = {"QTYG"}
MAYBE_FLOAT_COLUMNS = {"SEEDR"}

# Fields in the summary
SUMMARY_FIELDS: List[str] = [
    "SESON", "CROP", "RSV", "STAGIN", "REXML", "CCE", "CFC", "RCSSN", "E1", "E2",
    "E11", "E12", "E13", "EQST", "EQSB", "EQSW", "EQSP", "E14", "STYPE", "E3",
    "IRR", "E5", "FERTC", "E6", "MANUR", "E7", "PEST", "E8", "E15", "CROPER",
    "CROPCON", "AFFECT", "NIRR",
]

# ---------------------------------------------------------------------------
# Comparison codes
# ---------------------------------------------------------------------------
CMP_MISMATCH = 1
CMP_SAME = 2
CMP_NOT_ENVISAGED = 8
CMP_MISSING = 9

YES_CODE = 1
NO_CODE = 0

OTHERS_CODE = 9

# ---------------------------------------------------------------------------
# Code tables
# ---------------------------------------------------------------------------
# A. SESON
SEASON_CODES: Dict[str, int] = {
    "kharif": 1, "early kharif": 2, "late kharif": 3,
    "rabi": 4, "summer": 5, "whole year": 6,
}

# B. CROP
CROP_CODES: Dict[str, int] = {
    "wheat": 8,
    "pigeon pea": 43,
}

# C. RSV
RSV_REASON_CODES: Dict[str, int] = {
    "crop not sown": 1,
    "entire crop harvested in the village": 2,
    "records not available": 3,
}
RSV_NOT_SUBSTITUTED = 0

# D. STAGIN
STAGE_CODES: Dict[str, int] = {
    "harvest": 1,
    "post-harvest": 2,
    "lost": 3,
}
STAGE_LOST = 3

# E. REXML
REXML_MISSED_ALIASES: Dict[int, List[str]] = {
    1: ["Date of harvest not intimated"],
    2: ["Change in date of harvest intimated late"],
    3: ["Supervisor could not reach the village in time"],
    4: ["Overlapping harvest dates"],
    9: ["Other"],
}
REXML_LOST_ALIASES: Dict[int, List[str]] = {
    1: ["Cultivator harvested before the date fixed"],
    2: ["Primary worker did not conduct the experiment"],
    3: ["Delay in selection of survey no. / replacement of village"],
    4: ["Selection found wrong and correctly selected field already harvested"],
    9: ["Other"],
}


def _alias_table(aliases: Dict[int, List[str]]) -> Dict[str, int]:
    return {text.strip().lower(): code for code, texts in aliases.items() for text in texts}


REXML_MISSED_CODES = _alias_table(REXML_MISSED_ALIASES)
REXML_LOST_CODES = _alias_table(REXML_LOST_ALIASES)

# F. CCE
CCE_TRAINING: Dict[str, str] = {"trained": "trained", "untrained": "untrained"}
CCE_TRAINING_NOT_KNOWN = "not known"
CCE_ASSIGNED = "assigned"
CCE_SENIOR = "senior"
CCE_JUNIOR = "junior"
CCE_MATRIX: Dict[tuple, int] = {
    (CCE_SENIOR, "trained"): 1, (CCE_SENIOR, "untrained"): 2, (CCE_SENIOR, CCE_TRAINING_NOT_KNOWN): 3,
    (CCE_JUNIOR, "trained"): 4, (CCE_JUNIOR, "untrained"): 5, (CCE_JUNIOR, CCE_TRAINING_NOT_KNOWN): 6,
    (CCE_ASSIGNED, "trained"): 7, (CCE_ASSIGNED, "untrained"): 8, (CCE_ASSIGNED, CCE_TRAINING_NOT_KNOWN): 9,
}
# Delegate level values
CCE_DELEGATE_LEVELS: Dict[str, str] = {
    "equivalent/senior": CCE_SENIOR, "equivalent": CCE_SENIOR, "senior": CCE_SENIOR,
    "junior": CCE_JUNIOR,
}

# G. CFC
CFC_CODES: Dict[str, int] = {
    "khasra": 1, "map": 2, "both": 3, "nothing consulted": 4,
}

# H. RCSSN
RCSSN_REASON_CODES: Dict[str, int] = {
    "crop harvested prior to selection": 1,
    "crop harvested before the date fixed": 2,
    "field partially harvested": 3,
}
RCSSN_NOT_SUBSTITUTED = 0

# M. Equipment (EQST, EQSB, EQSW, EQSP)
EQUIPMENT_CODES: Dict[str, int] = {
    "supplied and used": 0,
    "supplied but locally procured items used (standard)": 1,
    "supplied but locally procured items used (non-standard)": 2,
    "supplied but not used though required": 3,
    "supplied but not required to be used": 4,
    "not supplied but locally procured items used (standard)": 5,
    "not supplied but locally procured items used (non-standard)": 6,
    "not supplied and also not used though required": 7,
    "not supplied and not required": 8,
    "information not available": 9,
}

# N. E14 (driage)
DRIAGE_CODES: Dict[str, int] = {
    "satisfactory": 0,
    "defective": 1,
    "not planned": 8,
}

# O. STYPE
SEED_TYPE_CODES: Dict[str, int] = {"high yielding": 1, "local": 2}

# P. CROPER
CROPER_PURE = 100

# R. CROPCON
CROP_CONDITION_CODES: Dict[str, int] = {
    "good": 1, "above normal": 1,
    "normal": 2, "below normal": 3,
    "completely destroyed": 4,
}

# S. AFFECT
AFFECT_CODES: Dict[str, int] = {
    "not affected": 0, "heavy rain": 1, "flood": 2, "drought": 3, "pests": 4,
}

# E15 (pure / mixture)
PURE = "Pure"
MIXTURE = "Mixture"
PW_PURE_TEXT = "pure crop"
PW_MIXTURE_PREFIX = "mixture"

# Report actions
ACTION_BLANK = "UNMAPPED VALUE -> blank"
ACTION_CROP = "UNMAPPED CROP -> blank"
ACTION_OTHERS = "mapped to Others (9)"
ACTION_NOT_YES_NO = "not yes/no -> treated as missing"
