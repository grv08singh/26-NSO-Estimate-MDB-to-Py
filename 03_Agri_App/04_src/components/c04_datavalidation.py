"""4. Data Validation — KrishiSoft_V0.1's Yield Checking (= the old AS 2.0 YIELD CHECKING.accdb), plus a MINIMUM yield.

Per season + sample + crop (state + year = the open one):
  1. Limits: the MAXIMUM yield from the old table `yield rc7` (resources/max_yield.csv) or saved here, and the
     MINIMUM yield (new; only saved here – there is no old table for it). Both can be typed for this check only.
  2. Every experiment of that crop that has Block 9 (SRL 1), RC-7, Block 5 part 1 and Block 10 (the old form's
     INNER JOINs):
        editable (Block 5 / 9 / 10)   WEIGHT, NETWEIGHT, CROPCOND, AFF, L1, L2;  REJ (RC-7 itself)
        not editable (RC-7)           QTYG, QTYP, CROPCON, AFFECT  – they follow the edits
  3. Checks (red cells):
        above maximum     NETWEIGHT ≥ maximum yield                         -> WEIGHT, NETWEIGHT red
        below minimum     NETWEIGHT < minimum yield, crop not destroyed (4) -> WEIGHT, NETWEIGHT red   (new)
        Poor crop         CROPCOND 3 / 4 (below normal / destroyed) but AFF 0 (no cause)  -> CROPCOND, AFF red
        Good crop         CROPCOND 1 / 2 (good / normal) but AFF not 0 (affected)         -> CROPCOND, AFF red
        Rejected          REJ 1                                              -> REJ red
  4. Editing follows the old VBA (WEIGHT_AfterUpdate):
        crop 3000 or 2400       QTYG = WEIGHT, QTYP = NETWEIGHT (net weight typed)
        crop 2000 in state 21   NETWEIGHT = QTYP = WEIGHT x 10 / (L1 + L2) x 1000
        any other crop          QTYG = WEIGHT, NETWEIGHT = QTYP = WEIGHT x 1000
     NETWEIGHT -> QTYP, CROPCOND -> CROPCON, AFF -> AFFECT.  RUN YIELD CONVERSION does it for all rows.
  5. SAVE: each changed value becomes a line of 00_database/04_datavalidation/<STATE>/<YEAR>/corrections.csv
     (date, Exp-ID, table, SRL, field, old, new). src/utils/schedules.py applies them whenever schedules are read,
     so every module sees the corrected values and re-importing never undoes them.
Exports (CSV, a FLAGS column says why a row is red): Outliers (red rows) and Basic Data (all rows) in
02_artifacts/04_datavalidation/<STATE>/<YEAR>/Outliers|Basic Data/<CROP>/<Central|State>/.
"""
from __future__ import annotations

import csv
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils import folders as F

OLD_TABLE = Path(__file__).resolve().parents[1] / "resources" / "max_yield.csv"
DB = Path("00_database") / F.DATA_VALIDATION
ART = Path("02_artifacts") / F.DATA_VALIDATION
BACKUP = Path("05_backup") / F.DATA_VALIDATION
LIMITS_FILE = "yield_limits.csv"
CORR_FILE = "corrections.csv"
KEYS = ["SEASONCODE", "SAMPLE", "CROPCODE"]
TYPED_NET = {"3000", "2400"}
EDITABLE = ["WEIGHT", "NETWEIGHT", "CROPCOND", "AFF", "REJ", "L1", "L2"]   # REJ is RC-7 itself (no block)
RC7 = ["QTYG", "QTYP", "CROPCON", "AFFECT"]
BLOCK_OF = {"WEIGHT": "Sch20Block5p1", "NETWEIGHT": "Sch20Block5p1", "CROPCOND": "Sch20Block9P1",
            "AFF": "Sch20Block9P1", "L1": "Sch20Block10", "L2": "Sch20Block10"}
SRL_OF = {"Sch20Block9P1": "1"}             # the row of a block the form uses (Block 9 part 1: experimental field)
COLUMNS = ["EXPTID", "SEASONCODE", "SAMPLE", "STATE", "DISTRICT", "CROPCODE", "SELORDER", "EXPT",
           "WEIGHT", "NETWEIGHT", "CROPCOND", "AFF", "REJ", "QTYG", "QTYP", "CROPCON", "AFFECT", "L1", "L2"]
CHECK_COLUMNS = ["CHECK 1", "CHECK 2"]
OUTLIERS_DIR, BASIC_DATA_DIR = "Outliers", "Basic Data"

LABELS = {"L1": "Potato side 1 (m)", "L2": "Potato side 2 (m)", "CHECK 1": "Poor crop", "CHECK 2": "Good crop"}
CHECK_TEXT = {"CHECK 1": {"TRUE": "OK", "FALSE": "No cause"}, "CHECK 2": {"TRUE": "OK", "FALSE": "Affected"}}
TIPS = {
    "EXPTID": "Exp-ID", "SEASONCODE": "Season code", "SAMPLE": "Sample (1 Central, 2 State)",
    "STATE": "State code", "DISTRICT": "District code", "CROPCODE": "Crop code",
    "SELORDER": "Selection order", "EXPT": "Experiment number (1 or 2)",
    "WEIGHT": "Plot weight in kg (Schedule 2.0 Block 5) — editable",
    "NETWEIGHT": "Net weight in grams (Block 5) — follows the plot weight (× 1000); checked against the maximum "
                 "and minimum yield",
    "CROPCOND": "Crop condition (Block 9): 1 good, 2 normal, 3 below normal, 4 completely destroyed — editable",
    "AFF": "Affected by (Block 9): 0 not affected, 1 heavy rain, 2 flood, 3 drought, 4 pests, 9 others — editable",
    "REJ": "RC-7 REJ: 1 = rejected, 0 = not rejected — editable; red when 1",
    "QTYG": "RC-7 QTYG: plot weight in kg (follows Block 5)", "QTYP": "RC-7 QTYP: yield in grams (follows Block 5)",
    "CROPCON": "RC-7 CROPCON: crop condition (follows Block 9)", "AFFECT": "RC-7 AFFECT: affected by (follows Block 9)",
    "L1": "L1 (Block 10): one of the two parallel sides of the field in metres — potato only; used for crop 2000 in "
          "state 21",
    "L2": "L2 (Block 10): the other parallel side in metres — potato only",
    "CHECK 1": "A crop below normal or destroyed (condition 3 / 4) must say what affected it. "
               "'No cause' = condition 3 / 4 but affected 0.",
    "CHECK 2": "A good or normal crop (condition 1 / 2) should not be marked affected. "
               "'Affected' = condition 1 / 2 but affected not 0.",
}


def label(col: str) -> str:
    return LABELS.get(col, col)


def check_text(col: str, value: str) -> str:
    return CHECK_TEXT[col][value]


def fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:.0f}" if f.is_integer() else f"{f}"


def num(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ yield limits (maximum + minimum)

def _db(state: str, year: str) -> Path:
    return DB / state / year


def old_table(state_code: str) -> pd.DataFrame:
    t = pd.read_csv(OLD_TABLE, dtype=str)
    t = t[t["STATE"] == str(state_code).zfill(2)]
    return t.assign(MAX=pd.to_numeric(t["MAX_YIELD"], errors="coerce"))[KEYS + ["MAX"]]


def _saved(state: str, year: str) -> pd.DataFrame:
    f = _db(state, year) / LIMITS_FILE
    if not f.exists():
        return pd.DataFrame(columns=KEYS + ["MAX", "MIN", "SAVED_ON"])
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig").reindex(
        columns=KEYS + ["MAX", "MIN", "SAVED_ON"], fill_value="")


def get_limits(state: str, state_code: str, year: str, season: str, sample: str, crop: str) -> dict:
    """{'max', 'max_from', 'min', 'min_from'}: saved here first; the maximum else from the old table."""
    out = {"max": None, "max_from": "not set", "min": None, "min_from": "not set"}
    s = _saved(state, year)
    hit = s[(s.SEASONCODE == season) & (s.SAMPLE == sample) & (s.CROPCODE == crop)]
    if len(hit):
        r = hit.iloc[0]
        if r["MAX"] != "":
            out["max"], out["max_from"] = float(r["MAX"]), "saved"
        if r["MIN"] != "":
            out["min"], out["min_from"] = float(r["MIN"]), "saved"
    if out["max"] is None:
        old = old_table(state_code)
        o = old[(old.SEASONCODE == season) & (old.SAMPLE == sample) & (old.CROPCODE == crop)]
        if len(o) and pd.notna(o["MAX"].iloc[0]):
            out["max"], out["max_from"] = float(o["MAX"].iloc[0]), "old table"
    return out


def save_limits(state: str, year: str, season: str, sample: str, crop: str,
                maximum: float | None, minimum: float | None) -> None:
    """Keep the maximum / minimum yield of this crop + sample for this state + year (old file backed up first)."""
    folder = _db(state, year)
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / LIMITS_FILE
    saved = _saved(state, year)
    if f.exists():
        b = BACKUP / state / year / f"{datetime.now():%Y-%m-%d_%H%M%S}"
        b.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, b / LIMITS_FILE)
    saved = saved[~((saved.SEASONCODE == season) & (saved.SAMPLE == sample) & (saved.CROPCODE == crop))]
    row = {"SEASONCODE": season, "SAMPLE": sample, "CROPCODE": crop, "MAX": fmt(maximum), "MIN": fmt(minimum),
           "SAVED_ON": f"{datetime.now():%d-%m-%Y %H:%M}"}
    saved = pd.concat([saved, pd.DataFrame([row])], ignore_index=True).sort_values(KEYS)
    tmp = f.with_suffix(".tmp")
    saved.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(f)


def missing_max(state: str, state_code: str, year: str, ml: pd.DataFrame) -> list[str]:
    """Crops of the master list with no maximum yield (old table or saved)."""
    if ml.empty:
        return []
    t = old_table(state_code)
    s = _saved(state, year)
    s = s[s["MAX"] != ""].assign(MAX=lambda d: pd.to_numeric(d["MAX"], errors="coerce"))
    t = pd.concat([s[KEYS + ["MAX"]], t]).drop_duplicates(KEYS, keep="first")
    m = ml.drop_duplicates(KEYS).merge(t, on=KEYS, how="left")
    miss = m[m["MAX"].isna()].sort_values(["SEASONCODE", "CROPCODE", "SAMPLE"])
    out = []
    for (code, name, season), g in miss.groupby(["CROPCODE", "CROPNAME", "SEASONNAME"], sort=False):
        out.append(f"{code} {name} ({season.title()}, {' and '.join(str(x).title() for x in g['SAMPLENAME'])})")
    return out


# ------------------------------------------------------------------ the form

def experiments(ml: pd.DataFrame, rc7: pd.DataFrame, blocks: dict[str, pd.DataFrame],
                season: str, sample: str, crop: str) -> tuple[pd.DataFrame, int]:
    """(rows of the form for this selection, received schedules left out for lack of blocks). All text."""
    ml = ml[(ml.SEASONCODE == season) & (ml.SAMPLE == sample) & (ml.CROPCODE == crop)]
    if rc7.empty:
        return pd.DataFrame(columns=COLUMNS + ["DISTRICTNAME", "CROPNAME", "SOURCE"]), 0
    r = rc7[rc7["EXPTID"].isin(set(ml["EXPTID"]))].reindex(columns=["EXPTID", "SOURCE", "REJ"] + RC7)
    r = r.astype("string").fillna("")
    r["QTYG"] = r["QTYG"].map(fmt)
    r["QTYP"] = r["QTYP"].map(fmt)
    df = ml[["EXPTID", "SEASONCODE", "SAMPLE", "STATE", "DISTRICT", "DISTRICTNAME", "CROPCODE", "CROPNAME",
             "SELORDER", "EXPT"]].merge(r, on="EXPTID", how="inner")
    received = len(df)
    for table in ("Sch20Block9P1", "Sch20Block5p1", "Sch20Block10"):
        cols = [f for f, t in BLOCK_OF.items() if t == table]
        b = blocks.get(table, pd.DataFrame(columns=["EXPTID"] + cols))
        if table in SRL_OF and "SRL" in b.columns:
            b = b[b["SRL"].str.replace(r"\.0+$", "", regex=True) == SRL_OF[table]]
        b = b.drop_duplicates("EXPTID", keep="last").reindex(columns=["EXPTID"] + cols).fillna("")
        df = df.merge(b, on="EXPTID", how="inner")            # the old form's INNER JOINs
    df = df.sort_values(["DISTRICT", "SELORDER", "EXPT"]).reset_index(drop=True)
    return df, received - len(df)


def checks(row: dict) -> tuple[str, str]:
    """The old form's two TRUE/FALSE boxes."""
    aff, cond = num(row.get("AFF")), str(row.get("CROPCOND") or "").strip()
    c1 = "FALSE" if aff == 0 and cond in ("3", "4") else "TRUE"
    c2 = "FALSE" if aff is not None and aff > 0 and cond in ("1", "2") else "TRUE"
    return c1, c2


def above_max(row: dict, maximum: float | None) -> bool:
    net = num(row.get("NETWEIGHT"))
    return maximum is not None and net is not None and net >= maximum


def below_min(row: dict, minimum: float | None) -> bool:
    """Net weight under the minimum yield – not for a completely destroyed crop (condition 4)."""
    net = num(row.get("NETWEIGHT"))
    return (minimum is not None and net is not None and net < minimum
            and str(row.get("CROPCOND") or "").strip() != "4")


def rejected(row: dict) -> bool:
    return str(row.get("REJ") or "").strip() == "1"


def flags(row: dict, maximum: float | None, minimum: float | None) -> list[str]:
    """Why a row is red, in words."""
    c1, c2 = checks(row)
    out = []
    if above_max(row, maximum):
        out.append("above maximum")
    if below_min(row, minimum):
        out.append("below minimum")
    if c1 == "FALSE":
        out.append("poor crop, no cause")
    if c2 == "FALSE":
        out.append("good crop, affected")
    if rejected(row):
        out.append("rejected")
    return out


def is_red(row: dict, maximum: float | None, minimum: float | None) -> bool:
    return bool(flags(row, maximum, minimum))


def after_edit(row: dict, field: str, state_code: str) -> dict:
    """Values after one field was changed, as the old form's AfterUpdate code did."""
    r = dict(row)
    crop = r["CROPCODE"]
    state_code = str(state_code).zfill(2)
    if field in ("WEIGHT", "L1", "L2"):
        if field != "WEIGHT" and not (crop == "2000" and state_code == "21"):
            return r
        w = num(r["WEIGHT"])
        if crop in TYPED_NET:
            r["QTYG"] = r["WEIGHT"]
            r["QTYP"] = r["NETWEIGHT"]
        elif crop == "2000" and state_code == "21":
            l1, l2 = num(r["L1"]), num(r["L2"])
            net = w * 10 / (l1 + l2) * 1000 if w is not None and l1 is not None and l2 is not None and l1 + l2 else None
            r["NETWEIGHT"] = r["QTYP"] = "" if net is None else fmt(round(net))
        else:
            r["QTYG"] = r["WEIGHT"]
            r["NETWEIGHT"] = r["QTYP"] = "" if w is None else fmt(round(w * 1000, 3))
    elif field == "NETWEIGHT":
        r["QTYP"] = r["NETWEIGHT"]
    elif field == "CROPCOND":
        r["CROPCON"] = r["CROPCOND"]
    elif field == "AFF":
        r["AFFECT"] = r["AFF"]
    return r


def convert_all(rows: list[dict], state_code: str) -> list[dict]:
    """RUN YIELD CONVERSION: the WEIGHT rule applied to every row."""
    return [after_edit(r, "WEIGHT", state_code) for r in rows]


def same(a, b) -> bool:
    a, b = str(a or "").strip(), str(b or "").strip()
    na, nb = num(a), num(b)
    return na == nb if na is not None and nb is not None else a == b


def changes(old: dict, new: dict) -> list[tuple[str, str, str]]:
    return [(k, old.get(k, ""), new.get(k, "")) for k in EDITABLE + RC7 if not same(old.get(k, ""), new.get(k, ""))]


def save(state: str, year: str, edits: list[tuple[dict, dict]]) -> int:
    """Each changed value -> one line of corrections.csv (applied by src/utils/schedules.py). Returns values saved."""
    edits = [(o, n, changes(o, n)) for o, n in edits]
    edits = [e for e in edits if e[2]]
    if not edits:
        return 0
    folder = _db(state, year)
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / CORR_FILE
    first = not f.exists()
    stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    n = 0
    with open(f, "a", newline="", encoding="utf-8-sig" if first else "utf-8") as fh:
        w = csv.writer(fh)
        if first:
            w.writerow(["Date", "EXPTID", "Table", "SRL", "Field", "Old", "New"])
        for o, _, ch in edits:
            for k, a, b in ch:
                table = BLOCK_OF.get(k, "Sch20RC7")
                w.writerow([stamp, o["EXPTID"], table, SRL_OF.get(table, ""), k, a, b])
                n += 1
    return n


def export_csv(state: str, year: str, rows: list[dict], maximum: float | None, minimum: float | None,
               only_red: bool = True) -> Path:
    """The rows as CSV (only_red: rows with a red cell) with a FLAGS column, in Outliers / Basic Data."""
    first = rows[0] if rows else {}
    if only_red:
        rows = [r for r in rows if is_red(r, maximum, minimum)]
    crop = re.sub(r'[<>:"/\\|?*]', "", str(first.get("CROPNAME") or first.get("CROPCODE") or "crop")).strip()
    sample = {"1": "Central", "2": "State"}.get(str(first.get("SAMPLE", "")), "Sample")
    folder = ART / state / year / (OUTLIERS_DIR if only_red else BASIC_DATA_DIR) / crop / sample
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{datetime.now():%Y-%m-%d_%H%M%S}_{crop}_{sample}_{'outliers' if only_red else 'basic_data'}.csv"
    recs = []
    for r in rows:
        c1, c2 = checks(r)
        recs.append({**{label(c): r.get(c, "") for c in COLUMNS}, "DISTRICTNAME": r.get("DISTRICTNAME", ""),
                     label("CHECK 1"): check_text("CHECK 1", c1), label("CHECK 2"): check_text("CHECK 2", c2),
                     "MAXIMUM YIELD": fmt(maximum), "MINIMUM YIELD": fmt(minimum),
                     "FLAGS": "; ".join(flags(r, maximum, minimum))})
    pd.DataFrame(recs).to_csv(out, index=False, encoding="utf-8-sig")
    return out
