"""Schedule A.S. 2.0 table layout, exactly as in the AS 2.0 .mdb files (NSSAS20xx.mdb / ESCH field .mdb).

Every source (mdb, DGCES) is stored in these tables with these columns, keyed by EXPTID.
Rows with several lines per experiment use SRL (and SRLDESC as in the ItemMaster tables).
"""

RC7_TABLE = "Sch20RC7"
RC7_COLUMNS = [
    "EXPTID", "SRL", "RC", "ST", "YR", "SESON", "CROP", "NEXP", "NEXNR", "CONFAC", "STAT", "DIST", "VILL", "RSV",
    "EXPNO", "STAGIN", "REXML", "CCE", "CFC", "RCSSN", "E1", "E2", "E9", "E10", "E11", "E12", "ADH", "QTYG", "QTYP",
    "E13", "EQST", "EQSB", "EQSW", "EQSP", "E14", "STYPE", "E3", "SVARC", "SEEDR", "E4", "IRR", "E5", "IRRP", "NIRR",
    "FERTC", "E6", "QTN", "CODN", "QTP", "CODP", "QTK", "CODK", "MANUR", "E7", "PEST", "E8", "E15", "REJ", "CROPER",
    "CROPCON", "AFFECT",
]

# Sch20RC7 field types in the .mdb: text codes keep a fixed width (DIST "01", ADH "0405"); 0 = no padding
RC7_TEXT_WIDTH = {"EXPTID": 12, "RC": 1, "ST": 1, "SESON": 1, "CROP": 2, "STAT": 2, "DIST": 2, "VILL": 2, "RSV": 1,
                  "EXPNO": 1, "STAGIN": 1, "REXML": 1, "CCE": 1, "CFC": 1, "RCSSN": 1, "E1": 1, "E2": 1, "E9": 1,
                  "E10": 1, "E11": 1, "E12": 1, "ADH": 4, "E13": 1, "EQST": 1, "EQSB": 1, "EQSW": 1, "EQSP": 1,
                  "E14": 1, "STYPE": 1, "E3": 1, "SVARC": 1, "E4": 1, "IRR": 1, "E5": 1, "IRRP": 1, "FERTC": 1,
                  "E6": 1, "CODN": 1, "CODP": 1, "CODK": 1, "MANUR": 1, "E7": 1, "PEST": 1, "E8": 1, "E15": 1,
                  "REJ": 1, "CROPCON": 1, "AFFECT": 1}
RC7_INT = {"SRL", "YR", "NEXP", "NEXNR", "QTYP", "NIRR"}       # the rest (CONFAC, QTYG, SEEDR, QTN … CROPER) are numbers


def rc7_text(col: str, v) -> str:
    """One RC-7 value written as the .mdb holds it (codes zero-padded, whole numbers without .0)."""
    if v is None or (isinstance(v, float) and v != v) or str(v).strip() in ("", "nan", "None", "<NA>"):
        return ""
    s = str(v).strip()
    try:
        f = float(s)
        if f.is_integer():
            s = str(int(f))
    except ValueError:
        return s
    w = RC7_TEXT_WIDTH.get(col, 0)
    return s.zfill(w) if w and s.isdigit() else s


BLOCKS = {
    "Sch20Block1": ["EXPTID", "TEHSIL", "SURVVILL", "ORGVILL", "REASON", "SPECIFYREASON", "SURVEYNO", "DTINSPECT",
                    "INSPSTATE", "PEGVISIBLE", "REASONLOST", "SPECIFYREASONLOST", "ENTRUSTNAME", "ENTRUSTDESIG",
                    "TRAINEDENTRUST", "ENTRUSTTRG", "DONEBYENTRUST", "CONDUCTNAME", "CONDUCTDESIG", "CONDUCTRANK",
                    "TRAINEDCONDUCT", "CONDUCTTRG"],
    "Sch20Block2": ["EXPTID", "RECORD", "SELAREATYPE", "SURVNO", "SURVAREA", "SUBSREASON", "SPECIFYSUBSREASON",
                    "CROPFIELDS", "CROPAREA", "REASONBIGSURVAREA", "CULTNAME", "INFORMANT", "MISTSURV",
                    "SPECIFYMISTSURV", "MISTSUBSURV", "SPECIFYMISTSUBSURV", "MISTFIELD", "SPECIFYMISTFIELD",
                    "RECTSURV", "RECTSUBSURV", "RECTFIELD"],
    "Sch20Block3": ["EXPTID", "SRL", "SRLDESC", "UNITLENGTH", "DIMLENGTH", "UNITBREADTH", "DIMBREADTH", "COORDLENGTH",
                    "COORDBREADTH"],
    "Sch20Block3p1": ["EXPTID", "SRL", "SRLDESC", "TREES", "R1", "R2", "R3", "R4", "R5"],
    "Sch20Block4": ["EXPTID", "SRL", "SRLDESC", "MSTK", "MSTKTYP", "RECT"],
    "Sch20Block5p1": ["EXPTID", "DTORIGINAL", "DTACTUAL", "DTTHRESHING", "DTWEIGH", "SHAPE", "PRODDESC", "WEIGHT",
                      "NETWEIGHT", "MISTAKE", "RECTI", "TOTPICK"],
    "Sch20Block5p2": ["EXPTID", "SRL", "SRLDESC", "IFMISSED", "DTPICK", "WEIGHT", "FRUITS", "FRUITWEIGHT", "STALKWEIGHT"],
    "Sch20Block5p3": ["EXPTID", "SRL", "SRL2", "DTHARVEST", "SRLDESC", "NUM1", "WT1", "NUM2", "WT2", "NUM3", "WT3",
                      "NUM4", "WT4", "NUM5", "WT5", "TNUM", "TWT"],
    "Sch20Block6": ["EXPTID", "EQUIP", "EQUIPSTATUS", "BALANCE", "BALANCESTATUS", "WEIGHT", "PEGS"],
    "Sch20Block7": ["EXPTID", "DESPLANNED", "ARRANGEMENTS", "DTHARVEST", "PRODDESC", "WEIGHT", "PRODAVL", "WEIGHTSUPER"],
    "Sch20Block8P1": ["EXPTID", "SRL", "SRLDESC", "SEEDTYPE", "NAMESTRAIN", "RATEOFAPP", "IFAPPLIED", "IRRIGATIONS",
                      "IRRISOURCE", "SPECIFYIRRISOURCE"],
    "Sch20Block8P2": ["EXPTID", "SRL", "SRLDESC", "FERTAPPLIED", "FERTNAME1", "FERTNAME2", "FERTNAME3", "FERTQT1",
                      "FERTQT2", "FERTQT3", "FERTRATEN", "FERTRATEP", "FERTRATEK", "MANRAPPLIED", "MANRCODE",
                      "SPECIFYMANRCODE", "PESTAPPLIED", "PESTMEASURE"],
    "Sch20Block9P1": ["EXPTID", "SRL", "SRLDESC", "CROPDENSITY", "CROPMATURITY", "CROPCOND", "AFF"],
    "Sch20Block9P2": ["EXPTID", "SRL", "AREA", "FIELDMERGE", "CROPNAME", "PROVINF1", "PCNTFORM1", "PROVINSUPER",
                      "PCNTSUPER"],
    "Sch20Block10": ["EXPTID", "CF", "L1", "L2", "REMARKS"],
    "Sch20Block12": ["EXPTID", "DTFLDWORK", "DTSAMPLECHK", "DTSUBMISSION", "SUPVNAME", "SUPVDESIG", "SUPVSIG", "DTINSP",
                     "DTRECEIPT", "DTSCRUTINY", "DTDESP", "INSPNAME", "INSPDESIG", "INSPHQR", "INSPSIG", "INSPREMARK"],
}
BLOCK_TABLES = list(BLOCKS)

# SRLDESC texts of the AS 2.0 ItemMaster tables
SRLDESC = {
    "Sch20Block3": {1: "P.W.'s entry", 2: "Supervisor's findings"},
    "Sch20Block4": {1: "Plot location", 2: "Plot measurement"},
    "Sch20Block8P1": {1: "P", 2: "S", 3: "Kh"},
    "Sch20Block8P2": {1: "P", 2: "S"},
    "Sch20Block9P1": {1: "Experimental field", 2: "Experimental plot"},
}

# columns added to every stored row (where it came from)
META = ["SOURCE", "SOURCE_FILE", "FILE_TIME"]
