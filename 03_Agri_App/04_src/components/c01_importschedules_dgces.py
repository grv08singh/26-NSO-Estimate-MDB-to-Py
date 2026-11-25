"""DGCES workbook -> Schedule A.S. 2.0 block tables (same tables and columns as the AS 2.0 .mdb).

Input: the DGCES Excel with the Supervisor sheet (FinalNSOFieldData) and the Primary Worker sheet
(FinalNSO_PW_FieldData), joined on Village LGD code + Crop + Experiment no. (c01_dgces_rc7.loader).
The field-by-field rules follow the review file DGCES_to_Schedule2.0_block_mapping.xlsx.

Identity: DGCES has no order of selection (O/S), so the Exp-ID cannot be built yet — EXPTID stays blank.
Every row carries DGCES_KEY (year|season|state LGD|district LGD|village LGD|crop|expt) and the DGCES_ID
table keeps the LGD codes and names, so the Exp-ID can be filled in later without converting again.
Codes still to be decided (irrigation source, manure, substitution reason) come from config.yaml (DGCES_codes).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from src.components.c01_dgces_rc7 import config as rc
from src.components.c01_dgces_rc7.comparisons import is_missing, yes_no
from src.components.c01_dgces_rc7.loader import Row
from src.components.c01_dgces_rc7.report import Recorder
from src.utils.schedule20 import BLOCKS, SRLDESC

# ---------------------------------------------------------------- DGCES column names (besides c01_dgces_rc7.config)
S_STATE_NAME, S_DISTRICT_NAME = "State", "District"
S_SUBDIST_LGD, S_SUBDIST = "Sub-District LGD Code", "Sub-District"
S_VILLAGE_NAME = "Village"
S_SUP_NAME, S_SUP_DATE = "Supervisor Name", "Date of Supervision"
S_ORIG_VILL = "Originally selected village"
S_TRAIN_DATE = "Date of Last Training Attended"
S_HIGHEST = "Highest Serial/Survey No. in the village"
S_FINAL_SN = "Final Selected Survey/Sub-Survey No."
S_SN_MISTAKE_TEXT = "Mistake noticed with Survey/Sub-Survey No. substitution"
S_SN_RECT = "Was the mistake rectified for Survey No."
S_SUBSN_RECT = "Was the mistake rectified for Sub-Survey No."
S_FIELD_RECT = "Was the mistake rectified for Field Selection?"
S_SURV_AREA = "Area of selected Survey/Sub-Survey No.(in Ha)"
S_CROP_AREA = "Area under exp. crop/crop mixture in selected Survey/Sub-Survey No.(in Ha)"
S_AREA_LESS = "Was exp. crop area less than selected Survey/Sub-Survey No"
S_AREA_LESS_REASON = "Reason for area of exp. crop less than Survey/Sub-Survey No."
S_CULT = "Cultivator Name"
S_SHAPE, S_SIZE = "Plot Shape", "Plot Size"
S_LEN_UNIT, S_LEN_ROWS = "Length Measured (in Steps/Rows)", "Length of field (in Rows)"
S_BRE_UNIT, S_BRE_ROWS = "Breadth Measured (in Steps/Rows)", "Breadth of field (in Rows)"
S_LOC_RECT = "Was the mistake rectified for Plot Location?"
S_MEAS_TEXT = "Mistake noticed with Plot Measurement"
S_MEAS_RECT = "Was the mistake rectified for Plot Measurement?"
S_HARV_ORIG, S_THRESH, S_WEIGH = "Date of harvest (originally fixed)", "Date of threshing", "Date of first weighment"
S_PROD_DESC = "Harvest Produce Description"
S_WEIGHT_RECT = "Was the mistake rectified for Weight Measurement"
S_EQ_TYPE, S_BAL_TYPE = "Type of Surveying Equipment", "Type of Balance Used"
S_HY_NAME, S_HY_STRAIN = "High Yielding/G.M Hybrid Seed Name", "High Yielding/G.M Hybrid Strain No."
S_IRR_SRC = "Irrigation Source"
S_MANURE_TYPE, S_MANURE_OTHER = "Type of Manure", "Other Type of Manure"
S_PEST_MEAS = "Measures Adopted"
S_DENS_F, S_DENS_P = "Crop Density (in Exp. field)", "Crop Density (in Exp. plot)"
S_MAT_F, S_MAT_P = "Crop Maturity (in Exp. field)", "Crop Maturity (in Exp. plot)"
S_COND_F = "Crop Condition (in Exp. field)"

PW_CROP_FULL = "Crop.1"
PW_REGION, PW_REGION_NAME = "Regional Code", "Regional Name"
PW_SUBREGION, PW_SUBREGION_NAME = "Sub Regional Code", "Sub Regional Name"
PW_AREA = "Area (in Ha) of the Experimental Crop Sown in the Selected Survey No./Sub-Division No."
PW_FINAL_SUBDIV = "Final Sub Division Number"
PW_HARVEST_DATE = "Harvesting Date"
PW_VARIETY = "Seed Variety Name"
PW_SEED_QTY = "Seed Quantity Used (in Kg) of Exp. Crop Sown in Selected Survey No./Sub-Division No."
PW_PLOT_SEL = "Plot Selection Type (Broadcasting/One-Sided Row/Two-Sided Row)"
PW_RAND_L, PW_RAND_B = "Selected Random Number (for Length)", "Selected Random Number (for Breadth)"
PW_ROWS_L, PW_ROWS_B = "No. of Rows (along Length)", "No. of Rows (along Breadth)"
PW_MANURE_TYPE = "Type of Manure"

# ---------------------------------------------------------------- code tables (Schedule 2.0 form)
YES1_NO0 = {"yes": "1", "no": "0"}
YES1_NO2 = {"yes": "1", "no": "2"}
TRAINED = {"trained": "1", "untrained": "2"}
UNITS = {"metres": "1", "meters": "1", "metre": "1", "steps": "2", "rows": "3"}
EQUIP = {"chain/string": "1", "chain": "1", "string": "1", "tape": "2", "i.s.i.": "3", "isi": "3"}
BALANCE = {"weighing balance": "1", "spring balance": "2", "digital balance": "3"}
DRIAGE = {"satisfactory": ("1", "0"), "defective": ("1", "1"), "not planned": ("0", "4")}   # (DESPLANNED, ARRANGEMENTS)
DENSITY = {"uniform": "1", "irregular": "2", "scanty": "3"}
MATURITY = {"unripe": "1", "ripe": "2", "over ripe": "3", "overripe": "3"}
CONDITION = {"good": "1", "above normal": "1", "normal": "2", "below normal": "3", "completely destroyed": "4",
             "damaged": "4"}
PEST_MEASURE = {"preventive": "1", "curative": "2", "both": "3"}
AREA_LESS = {"non-agricultural use": "1", "non agricultural use": "1", "not in agriculture use": "1",
             "other agricultural use": "2"}

# codes still TO DECIDE: defaults here, config.yaml (DGCES_codes) can change them
DEFAULT_CODES = {
    "irrigation_source": {"canal": "1", "tank": "2", "state tube well": "3", "private tube well": "4", "well": "5",
                          "boring personal (diesel)": "4", "boring personal (electricity)": "4", "borewell": "4"},
    "manure": {"farmyard manure": "1", "farm yard manure": "1", "green manure": "2"},
    "substitution_reason": {"crop harvested prior to selection": "1", "crop harvested before the date fixed": "2",
                            "field partially harvested": "3"},
}
OTHER = "9"


def _t(v) -> str:
    return "" if is_missing(v) else str(v).strip()


def _code(table: dict, v, rec: Recorder, field: str, source: str, other: str | None = None) -> str:
    """Form code for a text answer; unknown text -> `other` (with a note) or blank."""
    if is_missing(v):
        return ""
    c = table.get(str(v).strip().lower())
    if c is None:
        rec.unmapped(field, source, v, f"-> {other} (other)" if other else "-> blank")
        return other or ""
    return c


def _date(v) -> str:
    """dd/mm/yyyy or yyyy-mm-dd -> dd-mm-yyyy (the .mdb text format)."""
    t = _t(v)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(t, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return t


def _month_year(v) -> str:
    d = _date(v)
    return d[3:5] + "/" + d[6:] if re.fullmatch(r"\d{2}-\d{2}-\d{4}", d) else d     # mm/yyyy as on the form


def _num(v) -> float | None:
    try:
        return float(_t(v))
    except ValueError:
        return None


def _numtext(v) -> str:
    n = _num(v)
    if n is None:
        return ""
    return str(int(n)) if n.is_integer() else str(n)


def _grams(v) -> str:
    t = _t(v)
    try:
        return str(int((Decimal(t) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))) if t else ""
    except InvalidOperation:
        return ""


def dgces_key(row: Row) -> str:
    S = row.S
    return "|".join(_t(S(c)) for c in (rc.S_YEAR, rc.S_SEASON, rc.S_STATE, rc.S_DISTRICT, rc.S_VILLAGE, rc.S_CROP,
                                         rc.S_EXPNO))


class Converter:
    def __init__(self, codes: dict | None = None):
        self.codes = {k: dict(v) for k, v in DEFAULT_CODES.items()}
        for k, v in (codes or {}).items():                # config.yaml overrides / additions
            self.codes.setdefault(k, {}).update({str(a).strip().lower(): str(b) for a, b in (v or {}).items()})

    # ------------------------------------------------------------ one experiment
    def convert(self, row: Row, rec: Recorder) -> dict[str, list[dict]]:
        S, P = row.S, row.PW
        ident = row.ident()
        out: dict[str, list[dict]] = {t: [] for t in BLOCKS}

        def add(table: str, **vals):
            rec_ = {c: "" for c in BLOCKS[table]}
            rec_.update({k: ("" if v is None else v) for k, v in vals.items()})
            if "SRL" in vals and table in SRLDESC and "SRLDESC" in rec_:
                rec_["SRLDESC"] = SRLDESC[table].get(int(vals["SRL"]), "")
            out[table].append(rec_)

        # Block 1 ---------------------------------------------------------
        subst = yes_no(S(rc.S_VILL_SUBST))
        reason = ""
        if subst == "no":
            reason = "0"
        elif subst == "yes":
            reason = _code({k: str(v) for k, v in rc.RSV_REASON_CODES.items()},
                           S(rc.S_VILL_SUBST_REASON), rec, "Block1 REASON", rc.S_VILL_SUBST_REASON, OTHER)
        stage = _code({k: str(v) for k, v in rc.STAGE_CODES.items()}, S(rc.S_STAGE), rec, "Block1 INSPSTATE", rc.S_STAGE)
        lost_code, lost_text = "", ""
        missed, lost = S(rc.S_EXP_MISSED), S(rc.S_EXP_LOST)
        if not is_missing(lost) and (is_missing(missed) or stage == "3"):
            lost_code = _code({k: str(v) for k, v in rc.REXML_LOST_CODES.items()}, lost, rec, "Block1 REASONLOST",
                              rc.S_EXP_LOST, OTHER)
            lost_text = _t(lost) if lost_code == OTHER else ""
        elif not is_missing(missed):
            lost_code = _code({k: str(v) for k, v in rc.REXML_MISSED_CODES.items()}, missed, rec, "Block1 REASONLOST",
                              rc.S_EXP_MISSED, OTHER)
            lost_text = _t(missed) if lost_code == OTHER else ""
        add("Sch20Block1",
            TEHSIL=_t(S(S_SUBDIST)), SURVVILL=_t(S(S_VILLAGE_NAME)),
            ORGVILL=_t(S(S_ORIG_VILL)) if subst == "yes" else "",
            REASON=reason, SPECIFYREASON=_t(S(rc.S_VILL_SUBST_REASON)) if reason == OTHER else "",
            SURVEYNO=_t(S(S_HIGHEST)), DTINSPECT=_date(S(S_SUP_DATE)), INSPSTATE=stage,
            REASONLOST=lost_code, SPECIFYREASONLOST=lost_text,
            ENTRUSTNAME=_t(S(rc.S_ASSIGNED_PW)),
            TRAINEDENTRUST=_code(TRAINED, S(rc.S_PW_TRAINED), rec, "Block1 TRAINEDENTRUST", rc.S_PW_TRAINED) or "3",
            ENTRUSTTRG=_month_year(S(S_TRAIN_DATE)),
            DONEBYENTRUST=_code(YES1_NO2, S(rc.S_PW_CONDUCTED), rec, "Block1 DONEBYENTRUST", rc.S_PW_CONDUCTED),
            CONDUCTNAME=_t(S(rc.S_PW_NAME_CONDUCTED)))

        # Block 2 ---------------------------------------------------------
        ssn = yes_no(S(rc.S_SSN_SUBST))
        subs, subs_text = "", ""
        if ssn == "no":
            subs = "0"
        elif ssn == "yes" and not is_missing(S(rc.S_SSN_SUBST_REASON)):
            subs = _code(self.codes["substitution_reason"], S(rc.S_SSN_SUBST_REASON), rec, "Block2 SUBSREASON",
                         rc.S_SSN_SUBST_REASON, OTHER)
            subs_text = _t(S(rc.S_SSN_SUBST_REASON)) if subs == OTHER else ""
        elif ssn == "yes":
            rec.issue("Survey no. substituted but no reason", ident, "Block 2 SUBSREASON left blank")

        def mistake(col_yes, col_rect, field):
            yn = yes_no(S(col_yes))
            if yn == "no":
                return "0", "", ""
            if yn == "yes":   # the form wants the TYPE of mistake; DGCES gives only Yes
                rec.issue(f"{field}: mistake noticed, type not given", ident, "coded 9 (other)")
                return OTHER, "Type of mistake not given in DGCES data", _code(YES1_NO0, S(col_rect), rec,
                                                                             f"Block2 rectified ({field})", col_rect)
            return "", "", ""

        ms, ms_t, ms_r = mistake(rc.S_SN_MISTAKE, S_SN_RECT, "survey no.")
        if ms == OTHER and not is_missing(S(S_SN_MISTAKE_TEXT)):
            ms_t = _t(S(S_SN_MISTAKE_TEXT))
        mb, mb_t, mb_r = mistake(rc.S_SUBSN_MISTAKE, S_SUBSN_RECT, "sub-survey no.")
        mf, mf_t, mf_r = mistake(rc.S_FIELD_MISTAKE, S_FIELD_RECT, "field")
        less = yes_no(S(S_AREA_LESS))
        final_sub = _num(P(PW_FINAL_SUBDIV))
        add("Sch20Block2",
            RECORD=_code({k: str(v) for k, v in rc.CFC_CODES.items()}, S(rc.S_RECORDS), rec, "Block2 RECORD", rc.S_RECORDS),
            SELAREATYPE="" if final_sub is None else ("1" if final_sub == 0 else "2"),
            SURVNO=_t(S(S_FINAL_SN)), SURVAREA=_numtext(S(S_SURV_AREA)),
            SUBSREASON=subs, SPECIFYSUBSREASON=subs_text,
            CROPAREA=_numtext(S(S_CROP_AREA)),
            REASONBIGSURVAREA=_code(AREA_LESS, S(S_AREA_LESS_REASON), rec, "Block2 REASONBIGSURVAREA",
                                    S_AREA_LESS_REASON) if less == "yes" else "",
            CULTNAME=_t(S(S_CULT)),
            MISTSURV=ms, SPECIFYMISTSURV=ms_t, MISTSUBSURV=mb, SPECIFYMISTSUBSURV=mb_t, MISTFIELD=mf,
            SPECIFYMISTFIELD=mf_t, RECTSURV=ms_r, RECTSUBSURV=mb_r, RECTFIELD=mf_r)

        # Block 3: SRL 1 = P.W.'s entry, SRL 2 = Supervisor's findings ---------------------------------
        rows_sown = "row" in _t(P(PW_PLOT_SEL)).lower() and "not in rows" not in _t(P(PW_PLOT_SEL)).lower()
        pw_unit = "3" if rows_sown else ("2" if row.matched else "")
        pw_len = _numtext(P(rc.PW_FIELD_LENGTH)) or (_numtext(P(PW_ROWS_L)) if rows_sown else "")
        pw_bre = _numtext(P(rc.PW_FIELD_BREADTH)) or (_numtext(P(PW_ROWS_B)) if rows_sown else "")
        add("Sch20Block3", SRL=1, UNITLENGTH=pw_unit, DIMLENGTH=pw_len, UNITBREADTH=pw_unit, DIMBREADTH=pw_bre,
            COORDLENGTH=_numtext(P(PW_RAND_L)).zfill(2) if _numtext(P(PW_RAND_L)) else "",
            COORDBREADTH=_numtext(P(PW_RAND_B)).zfill(2) if _numtext(P(PW_RAND_B)) else "")
        lu = _code(UNITS, S(S_LEN_UNIT), rec, "Block3 UNITLENGTH", S_LEN_UNIT)
        bu = _code(UNITS, S(S_BRE_UNIT), rec, "Block3 UNITBREADTH", S_BRE_UNIT)
        add("Sch20Block3", SRL=2, UNITLENGTH=lu,
            DIMLENGTH=_numtext(S(S_LEN_ROWS)) if lu == "3" else _numtext(S(rc.S_FIELD_LENGTH)),
            UNITBREADTH=bu, DIMBREADTH=_numtext(S(S_BRE_ROWS)) if bu == "3" else _numtext(S(rc.S_FIELD_BREADTH)))

        # Block 4: SRL 1 plot location, SRL 2 plot measurement -----------------------------------------
        loc = _code(YES1_NO0, S(rc.S_PLOT_LOCATION), rec, "Block4 MSTK", rc.S_PLOT_LOCATION)
        if loc == "1":
            rec.issue("Plot location: mistake noticed, type not given", ident, "Block 4 MSTKTYP left blank")
        add("Sch20Block4", SRL=1, MSTK=loc,
            RECT=_code(YES1_NO0, S(S_LOC_RECT), rec, "Block4 RECT", S_LOC_RECT) if loc == "1" else "")
        mea = _code(YES1_NO0, S(rc.S_PLOT_MEASURE), rec, "Block4 MSTK", rc.S_PLOT_MEASURE)
        add("Sch20Block4", SRL=2, MSTK=mea, MSTKTYP="3" if mea == "1" else "",
            RECT=_code(YES1_NO0, S(S_MEAS_RECT), rec, "Block4 RECT", S_MEAS_RECT) if mea == "1" else "")

        # Block 5.1 -------------------------------------------------------
        size = _t(S(S_SIZE)).lower().replace(" ", "")
        shape = ""
        if m := re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", size):
            shape = f"{m.group(1)}mX{m.group(2)}m," + _t(S(S_SHAPE))
        elif size or _t(S(S_SHAPE)):
            shape = ",".join(x for x in (_t(S(S_SIZE)), _t(S(S_SHAPE))) if x)
        weight, net = _num(S(rc.S_HARVEST_WEIGHT)), _num(S(rc.S_NET_WEIGHT))
        if net == 0 and (weight or 0) > 0:
            rec.issue("Net weight 0 while produce weight > 0", ident, f"produce {weight} kg")
        wm = _code(YES1_NO0, S(rc.S_WEIGHT_MISTAKE), rec, "Block5p1 MISTAKE", rc.S_WEIGHT_MISTAKE)
        add("Sch20Block5p1", DTORIGINAL=_date(S(S_HARV_ORIG)), DTACTUAL=_date(S(rc.S_HARVEST_DATE)),
            DTTHRESHING=_date(S(S_THRESH)), DTWEIGH=_date(S(S_WEIGH)), SHAPE=shape,
            PRODDESC=_t(S(S_PROD_DESC)).upper(), WEIGHT=_numtext(S(rc.S_HARVEST_WEIGHT)),
            NETWEIGHT=_grams(S(rc.S_NET_WEIGHT)), MISTAKE=wm,
            RECTI=_code(YES1_NO0, S(S_WEIGHT_RECT), rec, "Block5p1 RECTI", S_WEIGHT_RECT) if wm == "1" else "")

        # Block 6 ---------------------------------------------------------
        eq = {k: str(v) for k, v in rc.EQUIPMENT_CODES.items()}
        add("Sch20Block6",
            EQUIP=_code(EQUIP, S(S_EQ_TYPE), rec, "Block6 EQUIP", S_EQ_TYPE),
            EQUIPSTATUS=_code(eq, S(rc.S_EQ_SURVEY), rec, "Block6 EQUIPSTATUS", rc.S_EQ_SURVEY),
            BALANCE=_code(BALANCE, S(S_BAL_TYPE), rec, "Block6 BALANCE", S_BAL_TYPE),
            BALANCESTATUS=_code(eq, S(rc.S_EQ_BALANCE), rec, "Block6 BALANCESTATUS", rc.S_EQ_BALANCE),
            WEIGHT=_code(eq, S(rc.S_EQ_WEIGHT), rec, "Block6 WEIGHT", rc.S_EQ_WEIGHT),
            PEGS=_code(eq, S(rc.S_EQ_PEGS), rec, "Block6 PEGS", rc.S_EQ_PEGS))

        # Block 7 (harvest stage: item 1 only) -------------------------------------------------------
        dr = _t(S(rc.S_DRIAGE)).lower()
        planned, arrange = DRIAGE.get(dr, ("", ""))
        if dr and dr not in DRIAGE:
            rec.unmapped("Block7", rc.S_DRIAGE, S(rc.S_DRIAGE), "-> blank")
        add("Sch20Block7", DESPLANNED=planned, ARRANGEMENTS=arrange)

        # Block 8.1: SRL 1 P, 2 S, 3 Kh --------------------------------------------------------------
        seed_codes = {k: str(v) for k, v in rc.SEED_TYPE_CODES.items()}
        qty, area = _num(P(PW_SEED_QTY)), _num(P(PW_AREA))
        rate_p = ""
        if qty and area:
            r = qty / area
            rate_p = str(int(r)) if r.is_integer() else f"{r:.2f}"
        irr_p = _code(YES1_NO0, P(rc.PW_IRRIGATION), rec, "Block8P1 IFAPPLIED (P)", rc.PW_IRRIGATION)
        add("Sch20Block8P1", SRL=1, NAMESTRAIN=_t(P(PW_VARIETY)), RATEOFAPP=rate_p, IFAPPLIED=irr_p)
        src_text = _t(S(S_IRR_SRC))
        irr_s = _code(YES1_NO0, S(rc.S_IRRIGATED), rec, "Block8P1 IFAPPLIED (S)", rc.S_IRRIGATED)
        src = _code(self.codes["irrigation_source"], src_text, rec, "Block8P1 IRRISOURCE", S_IRR_SRC, OTHER) \
            if irr_s == "1" else ""
        add("Sch20Block8P1", SRL=2,
            SEEDTYPE=_code(seed_codes, S(rc.S_SEED_TYPE), rec, "Block8P1 SEEDTYPE", rc.S_SEED_TYPE),
            NAMESTRAIN=" ".join(x for x in (_t(S(S_HY_NAME)), _t(S(S_HY_STRAIN))) if x),
            RATEOFAPP=_numtext(S(rc.S_SEED_RATE)), IFAPPLIED=irr_s,
            IRRIGATIONS=_numtext(S(rc.S_NUM_IRRIGATIONS)) if irr_s == "1" else "",
            IRRISOURCE=src, SPECIFYIRRISOURCE=src_text if src == OTHER else "")
        add("Sch20Block8P1", SRL=3, SEEDTYPE="3", IFAPPLIED="3")          # Khasra: not available

        # Block 8.2: SRL 1 P, 2 S --------------------------------------------------------------------
        def manure(applied, kind_col, other_col, sheet_get, who):
            a = _code(YES1_NO0, sheet_get(applied), rec, f"Block8P2 MANRAPPLIED ({who})", applied)
            if a != "1":
                return a, "", ""
            kind = _t(sheet_get(kind_col))
            if not kind:
                return a, "", ""
            code = _code(self.codes["manure"], kind, rec, f"Block8P2 MANRCODE ({who})", kind_col, OTHER)
            other = _t(sheet_get(other_col)) if other_col else ""
            return a, code, (other or kind) if code == OTHER else ""

        pa, pc, ps = manure(rc.PW_MANURE, PW_MANURE_TYPE, None, P, "P")
        add("Sch20Block8P2", SRL=1,
            FERTAPPLIED=_code(YES1_NO0, P(rc.PW_FERTILIZER), rec, "Block8P2 FERTAPPLIED (P)", rc.PW_FERTILIZER),
            MANRAPPLIED=pa, MANRCODE=pc, SPECIFYMANRCODE=ps,
            PESTAPPLIED=_code(YES1_NO0, P(rc.PW_PEST), rec, "Block8P2 PESTAPPLIED (P)", rc.PW_PEST))
        sa, sc, ss = manure(rc.S_MANURE, S_MANURE_TYPE, S_MANURE_OTHER, S, "S")
        pest_s = _code(YES1_NO0, S(rc.S_PEST), rec, "Block8P2 PESTAPPLIED (S)", rc.S_PEST)
        add("Sch20Block8P2", SRL=2,
            FERTAPPLIED=_code(YES1_NO0, S(rc.S_FERTILIZER), rec, "Block8P2 FERTAPPLIED (S)", rc.S_FERTILIZER),
            MANRAPPLIED=sa, MANRCODE=sc, SPECIFYMANRCODE=ss, PESTAPPLIED=pest_s,
            PESTMEASURE=_code(PEST_MEASURE, S(S_PEST_MEAS), rec, "Block8P2 PESTMEASURE", S_PEST_MEAS)
            if pest_s == "1" else "")

        # Block 9.1: SRL 1 field, 2 plot -------------------------------------------------------------
        aff_codes = {k: str(v) for k, v in rc.AFFECT_CODES.items()}
        aff = _code(aff_codes, S(rc.S_AFFECT), rec, "Block9P1 AFF", rc.S_AFFECT, OTHER)
        for srl, dens, mat, cond in ((1, S_DENS_F, S_MAT_F, S_COND_F), (2, S_DENS_P, S_MAT_P, rc.S_CROP_CONDITION)):
            add("Sch20Block9P1", SRL=srl,
                CROPDENSITY=_code(DENSITY, S(dens), rec, "Block9P1 CROPDENSITY", dens),
                CROPMATURITY=_code(MATURITY, S(mat), rec, "Block9P1 CROPMATURITY", mat),
                CROPCOND=_code(CONDITION, S(cond), rec, "Block9P1 CROPCOND", cond),
                AFF=aff)                       # DGCES has one 'affected' answer: used for field and plot

        # Block 9.2: rows 1-6 ------------------------------------------------------------------------
        crops_s = _num(S(rc.S_NUM_CROPS))
        pure_p = _t(P(rc.PW_CROP_TYPE)).lower()
        add("Sch20Block9P2", SRL=1, AREA=_numtext(S(S_CROP_AREA)), CROPNAME=_t(P(PW_CROP_FULL)) or _t(S(rc.S_CROP)),
            PROVINF1="1" if pure_p else "", PCNTFORM1="100" if pure_p == rc.PW_PURE_TEXT else "",
            PROVINSUPER="1" if crops_s is not None else "", PCNTSUPER="100" if crops_s == 1 else "")
        for srl in range(2, 7):
            add("Sch20Block9P2", SRL=srl)
        if crops_s is not None and crops_s > 1:
            rec.issue("Mixture: other crops and percentages not in DGCES", ident, f"{crops_s:g} crops sown")

        # Block 10 (+ remarks) and Block 12 ---------------------------------------------------------
        remarks = "; ".join(x for x in (_t(S(S_SN_MISTAKE_TEXT)), _t(S(S_MEAS_TEXT))) if x)
        add("Sch20Block10", REMARKS=remarks)
        add("Sch20Block12", DTFLDWORK=_date(P(PW_HARVEST_DATE)), DTSAMPLECHK=_date(S(S_SUP_DATE)),
            SUPVNAME=_t(S(S_SUP_NAME)))
        return out


def identity(row: Row, sample: str, source_file: str) -> dict:
    """The DGCES_ID row: what DGCES says about who / where this experiment is (EXPTID waits for the O/S)."""
    S, P = row.S, row.PW
    return {"DGCES_KEY": dgces_key(row), "EXPTID": "", "YEAR": _t(S(rc.S_YEAR)), "SEASON": _t(S(rc.S_SEASON)),
            "SAMPLE": sample, "STATE_LGD": _t(S(rc.S_STATE)), "STATENAME": _t(S(S_STATE_NAME)),
            "DISTRICT_LGD": _t(S(rc.S_DISTRICT)), "DISTRICTNAME": _t(S(S_DISTRICT_NAME)),
            "SUBDISTRICT_LGD": _t(S(S_SUBDIST_LGD)), "SUBDISTRICT": _t(S(S_SUBDIST)),
            "VILLAGE_LGD": _t(S(rc.S_VILLAGE)), "VILLAGENAME": _t(S(S_VILLAGE_NAME)),
            "CROP": _t(S(rc.S_CROP)), "CROP_FULL": _t(P(PW_CROP_FULL)), "SEED_TYPE": _t(S(rc.S_SEED_TYPE)),
            "EXPT": _t(S(rc.S_EXPNO)), "RO_CODE": _t(P(PW_REGION)), "RO_NAME": _t(P(PW_REGION_NAME)),
            "SRO_CODE": _t(P(PW_SUBREGION)), "SRO_NAME": _t(P(PW_SUBREGION_NAME)),
            "PW_ROW_FOUND": "Yes" if row.matched else "No", "SOURCE_FILE": source_file}
