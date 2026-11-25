"""7. RC7 — the old RC7 <year>.accdb validation (DataValidation20) and the auto-corrections of the
06_RC_Cleaning script, for the crop cutting record (RC-7) of the open state + year.

  proposed corrections   safe fixes the app can work out (the user ticks / unticks them and confirms; applied ones
                         go to 00_database/04_datavalidation/<STATE>/<YEAR>/corrections.csv, like Data Validation, so
                         every module uses them and re-importing never undoes them)
  problems               what only the user can decide (wrong codes, yield 0 or above the maximum, seed ratio, dates …);
                         a typed value is saved the same way

Rules (in this order; each one sees the earlier ones' result):
  REJ not 0/1 -> 0 · CCE 0 -> 7 · RSV not 0,1,2,3,9 -> 0 · missed / lost with a wrong reason (REXML) -> 9 ·
  harvested / missed: CFC not 1–4 -> 4, RCSSN not 0,1,2,3,9 -> 0, blank EQST / EQSB / EQSW / EQSP -> 9 ·
  missed: QTYG, QTYP blank · destroyed crop (CROPCON 4): QTYG, QTYP 0 · rejected / missed / lost: E13 blank ·
  rejected / lost: E14 blank, crops 14 / 33 / 44: E14 8 · good / normal crop: AFFECT 0 · NIRR blank and IRR 0: NIRR 0 ·
  NIRR > 0: IRR 1 · QTN / QTP / QTK > 0: CODN 1 / CODP 2 / CODK 3 · COD 9: quantity 0, COD 8: quantity blank ·
  any N / P / K > 0: FERTC 1 · lost: every field from CCE on blank · NEXP = planned, NEXNR = planned − received
  (master list + schedules) · CONFAC = ⌊CCF × 10,000⌋ from the area sheet saved in 5. Estimates · YR = the first year.
Problems: codes outside rc7_code_rules.csv (harvested plots: blank too) · harvested with QTYP 0 (not destroyed) ·
  FERTC 1 without N, P, K · IRR 1 without irrigations · QTYP above the maximum yield (4. Data Validation's limits) ·
  QTYP < QTYG × 1000 (not crops 3000 / 2400) · order of selection > 25 · CONFAC missing · seed ratio above
  seed_ratio.csv · harvest date (ADH, ddmm) not a date.
"""
from __future__ import annotations

import csv
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.components import c04_datavalidation as dv
from src.components import c05_estimates as est
from src.utils import folders as F

RES = Path(__file__).resolve().parents[1] / "resources"
ART = Path("02_artifacts") / F.RC7
TABLE = "Sch20RC7"
LOST_BLANK = ["CCE", "CFC", "RCSSN", "E1", "E2", "E9", "E10", "E11", "E12", "ADH", "QTYG", "QTYP", "E13", "EQST",
              "EQSB", "EQSW", "EQSP", "E14", "STYPE", "E3", "SVARC", "SEEDR", "E4", "IRR", "E5", "IRRP", "NIRR",
              "FERTC", "E6", "QTN", "CODN", "QTP", "CODP", "QTK", "CODK", "MANUR", "E7", "PEST", "E8", "E15",
              "CROPER", "CROPCON", "AFFECT"]
PROPOSAL_COLUMNS = ["EXPTID", "District", "Season", "Crop", "Sample", "Field", "Now", "Proposed", "Why"]
PROBLEM_COLUMNS = ["EXPTID", "District", "Season", "Crop", "Sample", "Field", "Entry noted", "Check"]


def code(v) -> str:
    """'1.0' -> '1', None / nan -> ''."""
    s = "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def num(v) -> float | None:
    try:
        f = float(str(v).strip())
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def code_rules() -> pd.DataFrame:
    return pd.read_csv(RES / "rc7_code_rules.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")


def seed_ratios() -> dict[str, float]:
    t = pd.read_csv(RES / "seed_ratio.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return {r.CROP2.zfill(2): float(r.MAX_SEED_RATIO) for r in t.itertuples() if r.MAX_SEED_RATIO}


def key_of(r) -> str:
    """'season-sample-crop' of a row: what is marked final."""
    return f"{r.get('SEASONCODE', '')}-{r.get('SAMPLE', '')}-{r.get('CROPCODE', '')}"


# ------------------------------------------------------------------ the RC-7 rows of the scope

def rows(ml: pd.DataFrame, rc7: pd.DataFrame, seasons=(), samples=("1", "2")) -> pd.DataFrame:
    """RC-7 of the planned experiments of the ticked seasons (none = all) and samples, all crops, with the master
    list's names."""
    if ml.empty or rc7.empty:
        return pd.DataFrame()
    m = ml[ml["SAMPLE"].isin(samples)]
    if seasons:
        m = m[m["SEASONCODE"].isin(seasons)]
    keep = ["EXPTID", "SEASONCODE", "SEASONNAME", "SAMPLE", "CROPCODE", "CROPNAME", "DISTRICTNAME", "SELORDER", "EXPT"]
    rc = rc7.drop_duplicates("EXPTID", keep="last")
    rc = rc.drop(columns=[c for c in keep if c != "EXPTID" and c in rc.columns])    # the master list's win
    df = rc.merge(m[keep], on="EXPTID", how="inner")
    return df.sort_values(["SEASONCODE", "SAMPLE", "CROPCODE", "EXPTID"]).reset_index(drop=True)


# ------------------------------------------------------------------ proposed corrections

def _ccf(state: str, year: str) -> dict[tuple, float]:
    """(season, sample, 2-digit crop) -> CCF = CF × driage × recovery of the area sheets saved in 5. Estimates (only
    when all varieties of the crop agree)."""
    inp = est._read(est.folder(state, year) / est.INPUTS_FILE, est.INPUT_COLUMNS)
    seen: dict[tuple, set] = {}
    for r in inp.itertuples():
        parts = [p.split("-") for p in r.KEY.split("+")]
        cf, dr, rr = num(r.CF), num(r.DRIAGE), num(r.RECOVERY)
        if len(parts) != 1 or None in (cf, dr, rr):
            continue
        s, smp, c = parts[0]
        seen.setdefault((s, smp, c[:2]), set()).add(round(cf * dr * rr, 6))
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def _planned(ml: pd.DataFrame) -> dict[tuple, int]:
    m = ml.assign(C2=ml["CROPCODE"].str[:2])
    return m.groupby(["SEASONCODE", "SAMPLE", "C2"]).size().to_dict()


def propose(df: pd.DataFrame, ml_all: pd.DataFrame, rc7_all: pd.DataFrame, state: str, year: str
            ) -> tuple[list[dict], pd.DataFrame]:
    """(proposed corrections, the rows as they would be with all of them applied)."""
    out, fixed = [], []
    planned = _planned(ml_all)
    rc_in_ml = rc7_all[["EXPTID"]].drop_duplicates().merge(ml_all[["EXPTID", "SEASONCODE", "SAMPLE", "CROPCODE"]],
                                                           on="EXPTID", how="inner")
    received = rc_in_ml.assign(C2=rc_in_ml["CROPCODE"].str[:2]).groupby(["SEASONCODE", "SAMPLE", "C2"]).size().to_dict()
    ccf = _ccf(state, year)
    yr = year[:4]
    for rec in df.to_dict("records"):
        r = dict(rec)
        changes: dict[str, list] = {}

        def put(field, value, why):
            if field not in r:
                return
            if not dv.same(r.get(field, ""), value):
                first = changes.get(field, [r.get(field, ""), None, []])
                first[1] = value
                first[2].append(why)
                changes[field] = first
                r[field] = value

        st, cond = code(r.get("STAGIN")), code(r.get("CROPCON"))
        if code(r.get("REJ")) not in ("", "0", "1"):
            put("REJ", "0", "REJ can only be 0 or 1")
        rej = code(r.get("REJ")) == "1"
        if code(r.get("CCE")) == "0":
            put("CCE", "7", "CCE 0 is not a code (old tool: 7)")
        if code(r.get("RSV")) not in ("0", "1", "2", "3", "9"):
            put("RSV", "0", "RSV must be 0, 1, 2, 3 or 9")
        if st in ("2", "3") and code(r.get("REXML")) not in ("1", "2", "3", "4", "9"):
            put("REXML", "9", "missed / lost: reason must be 1, 2, 3, 4 or 9")
        if st in ("1", "2"):
            if code(r.get("CFC")) not in ("1", "2", "3", "4"):
                put("CFC", "4", "CFC must be 1–4")
            if code(r.get("RCSSN")) not in ("0", "1", "2", "3", "9"):
                put("RCSSN", "0", "RCSSN must be 0, 1, 2, 3 or 9")
            for f in ("EQST", "EQSB", "EQSW", "EQSP"):
                if code(r.get(f)) == "":
                    put(f, "9", "blank equipment code")
        if st == "2":
            put("QTYG", "", "missed experiment: no yield")
            put("QTYP", "", "missed experiment: no yield")
        elif st == "1" and cond == "4":
            put("QTYG", "0", "crop completely destroyed: yield 0")
            put("QTYP", "0", "crop completely destroyed: yield 0")
        if rej or st in ("2", "3"):
            put("E13", "", "rejected / missed / lost: E13 blank")
        if rej or st == "3":
            put("E14", "", "rejected / lost: E14 blank")
        elif code(r.get("CROP")).zfill(2) in ("14", "33", "44"):
            put("E14", "8", "crops 14 / 33 / 44: E14 8")
        if st in ("1", "2") and cond in ("1", "2") and code(r.get("AFFECT")) not in ("", "0"):
            put("AFFECT", "0", "good / normal crop: not affected")
        nirr = num(r.get("NIRR"))
        if code(r.get("NIRR")) == "" and code(r.get("IRR")) == "0":
            put("NIRR", "0", "not irrigated: no irrigations")
        if nirr and nirr > 0 and code(r.get("IRR")) != "1":
            put("IRR", "1", "irrigations given: irrigated")
        for q, c, v in (("QTN", "CODN", "1"), ("QTP", "CODP", "2"), ("QTK", "CODK", "3")):
            if (num(r.get(q)) or 0) > 0 and code(r.get(c)) != v:
                put(c, v, f"{q} given: {c} {v}")
            if code(r.get(c)) == "9" and code(r.get(q)) not in ("0", ""):
                put(q, "0", f"{c} 9: {q} 0")
            if code(r.get(c)) == "8" and code(r.get(q)) != "":
                put(q, "", f"{c} 8: {q} blank")
        if any((num(r.get(q)) or 0) > 0 for q in ("QTN", "QTP", "QTK")) and code(r.get("FERTC")) != "1":
            put("FERTC", "1", "N / P / K given: fertiliser applied")
        if st == "3":
            for f in LOST_BLANK:
                if code(r.get(f)) != "":
                    put(f, "", "lost experiment: no data")
        key = (r.get("SEASONCODE"), r.get("SAMPLE"), str(r.get("CROPCODE", ""))[:2])
        if key in planned:
            put("NEXP", str(planned[key]), "planned experiments (master list)")
            put("NEXNR", str(planned[key] - received.get(key, 0)), "planned − received")
        if key in ccf:
            c_ = ccf[key]
            put("CONFAC", str(math.floor(c_ * 10000) if c_ < 1 else c_), "CCF of the area sheet saved in 5. Estimates")
        if code(r.get("YR")) != yr:
            put("YR", yr, f"YR = {yr} for {year}")
        for f, (now, new, why) in changes.items():
            if not dv.same(now, new):
                out.append({"EXPTID": r["EXPTID"], "District": r.get("DISTRICTNAME", ""), "Crop": r.get("CROPNAME", ""),
                            "Sample": {"1": "Central", "2": "State"}.get(r.get("SAMPLE"), ""), "KEY": key_of(r),
                            "Season": str(r.get("SEASONNAME", "")).title(), "Field": f,
                            "Now": code(now), "Proposed": code(new), "Why": "; ".join(dict.fromkeys(why))})
        fixed.append(r)
    return out, pd.DataFrame(fixed, columns=df.columns) if fixed else df


# ------------------------------------------------------------------ problems

def _valid_ddmm(v, yr: str) -> bool:
    s = code(v).zfill(4)
    try:
        date(int(yr), int(s[2:]), int(s[:2]))
        return True
    except ValueError:
        try:                                      # rabi harvests run into the next calendar year
            date(int(yr) + 1, int(s[2:]), int(s[:2]))
            return True
        except ValueError:
            return False


def problems(df: pd.DataFrame, state: str, state_code: str, year: str) -> list[dict]:
    """What the user must decide, on the rows as they would be after the proposed corrections."""
    rules = code_rules()
    seeds = seed_ratios()
    limits: dict[tuple, float | None] = {}
    out = []
    no_confac: dict[tuple, list] = {}                # (crop, sample) -> Exp-IDs without a conversion factor
    for r in df.to_dict("records"):
        st = code(r.get("STAGIN"))
        base = {"EXPTID": r["EXPTID"], "District": r.get("DISTRICTNAME", ""), "Crop": r.get("CROPNAME", ""),
                "Sample": {"1": "Central", "2": "State"}.get(r.get("SAMPLE"), ""), "KEY": key_of(r),
                "Season": str(r.get("SEASONNAME", "")).title()}

        def add(field, entry, check):
            out.append({**base, "Field": field, "Entry noted": code(entry), "Check": check})

        if st != "3":
            for rule in rules.itertuples():
                if rule.FIELD not in r:
                    continue
                v = code(r.get(rule.FIELD))
                if v == "" and st != "1":
                    continue
                if v not in rule.ALLOWED.split(","):
                    add(rule.FIELD, v, f"{rule.MESSAGE} Allowed: {rule.ALLOWED.replace(',', ', ')}"
                        + (" (blank)" if v == "" else ""))
        if st == "1":
            qtyp, qtyg = num(r.get("QTYP")), num(r.get("QTYG"))
            if not qtyp and code(r.get("CROPCON")) != "4":
                add("QTYP", r.get("QTYP"), "Yield (QTYP) is 0 for a harvested experiment")
            if code(r.get("FERTC")) == "1" and not any((num(r.get(q)) or 0) > 0 for q in ("QTN", "QTP", "QTK")) \
                    and "9" not in (code(r.get("CODN")), code(r.get("CODP")), code(r.get("CODK"))):
                add("FERTC", r.get("FERTC"), "Fertiliser applied (FERTC 1) but N, P, K not given")
            if code(r.get("IRR")) == "1" and not num(r.get("NIRR")):
                add("NIRR", r.get("NIRR"), "Irrigated (IRR 1) but the number of irrigations is not given")
            key = (r.get("SEASONCODE"), r.get("SAMPLE"), r.get("CROPCODE"))
            if key not in limits:
                limits[key] = dv.get_limits(state, state_code, year, *key)["max"]
            if qtyp is not None and limits[key] is not None and qtyp > limits[key]:
                add("QTYP", r.get("QTYP"), f"Yield is more than {limits[key]:g}")
            if qtyp is not None and qtyg is not None and str(r.get("CROPCODE")) not in dv.TYPED_NET \
                    and qtyp < round(qtyg * 1000):
                add("QTYP / QTYG", f"{code(r.get('QTYP'))}, {code(r.get('QTYG'))}",
                    "Quantity produced (QTYP) is less than the net weight (QTYG × 1000)")
            sr, lim = num(r.get("SEEDR")), seeds.get(code(r.get("CROP")).zfill(2))
            if sr is not None and lim is not None and sr > lim:
                add("SEEDR", r.get("SEEDR"), f"Seed ratio is more than {lim:g}")
            if code(r.get("ADH")) and not _valid_ddmm(r.get("ADH"), year[:4]):
                add("ADH", r.get("ADH"), "Harvest date (ddmm) is not a date")
        if (num(r.get("VILL")) or 0) > 25:
            add("VILL", r.get("VILL"), "Order of selection is more than 25")
        if st != "3" and not num(r.get("CONFAC")):
            no_confac.setdefault((base["Crop"], base["Sample"], base["KEY"], base["Season"]), []).append(r["EXPTID"])
    for (crop, sample, key, season), ids in no_confac.items():    # one line per crop + sample
        out.append({"EXPTID": f"{len(ids)} schedules", "District": "", "Crop": crop, "Sample": sample, "KEY": key,
                    "Season": season,
                    "Field": "CONFAC", "Entry noted": "",
                    "Check": "Conversion factor is not filled – save this crop's area sheet in 5. Estimates (the CCF "
                             "comes from it) or type it here", "EXPTIDS": ids})
    return out


def group_proposals(proposals: list[dict]) -> list[dict]:
    """One line per (field, now, proposed, why, crop, sample) with its schedules – what the user ticks."""
    groups: dict[tuple, dict] = {}
    for p in proposals:
        k = (p["Field"], p["Now"], p["Proposed"], p["Why"], p["Crop"], p["Sample"], p["KEY"])
        g = groups.setdefault(k, {"Field": p["Field"], "Now": p["Now"], "Proposed": p["Proposed"], "Why": p["Why"],
                                  "Season": p["Season"], "Crop": p["Crop"], "Sample": p["Sample"], "KEY": p["KEY"],
                                  "items": []})
        g["items"].append(p)
    return sorted(groups.values(), key=lambda g: (g["KEY"].split("-")[0], g["Crop"], g["Sample"], g["Field"]))


# ------------------------------------------------------------------ final (per crop + sample)
#   final.csv       KEY, SEASONCODE, SAMPLE, CROPCODE, CROPNAME, SCHEDULES, FINGERPRINT, MARKED_ON
#   final_rows.csv  the RC-7 rows of every final crop + sample, as they were when marked (copied to
#                   02_artifacts/07_rc7/<STATE>/<YEAR>/final/RC7_final.csv for 8. Annexures)

DB = Path("00_database") / F.RC7
FINAL_FILE, FINAL_ROWS = "final.csv", "final_rows.csv"
FINAL_COLUMNS = ["KEY", "SEASONCODE", "SAMPLE", "CROPCODE", "CROPNAME", "SCHEDULES", "FINGERPRINT", "MARKED_ON"]
RC7_FIELDS = ["RC", "ST", "YR", "SESON", "CROP", "NEXP", "NEXNR", "CONFAC", "STAT", "DIST", "VILL", "RSV", "EXPNO",
              "STAGIN", "REXML", "CCE", "CFC", "RCSSN", "E1", "E2", "E9", "E10", "E11", "E12", "ADH", "QTYG", "QTYP",
              "E13", "EQST", "EQSB", "EQSW", "EQSP", "E14", "STYPE", "E3", "SVARC", "SEEDR", "E4", "IRR", "E5", "IRRP",
              "NIRR", "FERTC", "E6", "QTN", "CODN", "QTP", "CODP", "QTK", "CODK", "MANUR", "E7", "PEST", "E8", "E15",
              "REJ", "CROPER", "CROPCON", "AFFECT"]


def _final_dir(state: str, year: str) -> Path:
    return DB / state / year


def finals(state: str, year: str) -> pd.DataFrame:
    f = _final_dir(state, year) / FINAL_FILE
    if not f.exists():
        return pd.DataFrame(columns=FINAL_COLUMNS)
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig").reindex(columns=FINAL_COLUMNS,
                                                                                         fill_value="")


def fingerprint(rows: pd.DataFrame) -> str:
    """Changes when any RC-7 value of these schedules changes (re-import, Data Validation, a correction here)."""
    import hashlib
    cols = ["EXPTID"] + [c for c in RC7_FIELDS if c in rows.columns]
    t = rows[cols].copy()
    for c in cols:
        t[c] = t[c].map(code)
    return hashlib.sha1(t.sort_values("EXPTID").to_csv(index=False).encode("utf-8")).hexdigest()


def final_state(state: str, year: str, df: pd.DataFrame) -> dict[str, dict]:
    """KEY -> {'final': bool, 'marked_on', 'changed': bool, 'name', 'schedules'} for the crops + samples in df."""
    fin = finals(state, year).set_index("KEY")
    out = {}
    for key, g in df.groupby(df.apply(key_of, axis=1)) if len(df) else []:
        rec = {"final": key in fin.index, "marked_on": "", "changed": False, "name": g["CROPNAME"].iloc[0],
               "sample": {"1": "Central", "2": "State"}.get(g["SAMPLE"].iloc[0], ""), "schedules": len(g)}
        if rec["final"]:
            rec["marked_on"] = fin.at[key, "MARKED_ON"]
            rec["changed"] = fin.at[key, "FINGERPRINT"] != fingerprint(g)
        out[key] = rec
    return out


def _write_finals(state: str, year: str, fin: pd.DataFrame, rows: pd.DataFrame) -> None:
    d = _final_dir(state, year)
    d.mkdir(parents=True, exist_ok=True)
    for df, name in ((fin, FINAL_FILE), (rows, FINAL_ROWS)):
        tmp = (d / name).with_suffix(".tmp")
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
        tmp.replace(d / name)
    art = ART / state / year / "final"                     # the final RC-7 file (for 8. Annexures)
    art.mkdir(parents=True, exist_ok=True)
    order = [c for c in ("ST", "SESON", "CROP", "DIST", "VILL", "EXPNO") if c in rows.columns]
    rows.reindex(columns=["EXPTID"] + RC7_FIELDS).sort_values(order or ["EXPTID"]).to_csv(
        art / "RC7_final.csv", index=False, encoding="utf-8-sig")


def _final_rows(state: str, year: str) -> pd.DataFrame:
    f = _final_dir(state, year) / FINAL_ROWS
    if not f.exists():
        return pd.DataFrame(columns=["KEY", "EXPTID"] + RC7_FIELDS)
    return pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def mark_final(state: str, year: str, df: pd.DataFrame, keys: list[str]) -> int:
    """Mark these crops + samples (KEYs) of df final: their rows as they are now are kept. Returns schedules."""
    fin, rows = finals(state, year), _final_rows(state, year)
    df = df.assign(KEY=df.apply(key_of, axis=1)) if len(df) else df
    n, new_fin, new_rows = 0, [], []
    stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    for key in keys:
        g = df[df["KEY"] == key]
        if g.empty:
            continue
        s, smp, c = key.split("-")
        new_fin.append({"KEY": key, "SEASONCODE": s, "SAMPLE": smp, "CROPCODE": c, "CROPNAME": g["CROPNAME"].iloc[0],
                        "SCHEDULES": len(g), "FINGERPRINT": fingerprint(g), "MARKED_ON": stamp})
        new_rows.append(g.reindex(columns=["KEY", "EXPTID"] + RC7_FIELDS))
        n += len(g)
    done = {r["KEY"] for r in new_fin}
    fin = pd.concat([fin[~fin["KEY"].isin(done)], pd.DataFrame(new_fin, columns=FINAL_COLUMNS)], ignore_index=True)
    rows = pd.concat([rows[~rows["KEY"].isin(done)], *new_rows], ignore_index=True)
    _write_finals(state, year, fin, rows)
    return n


def unmark_final(state: str, year: str, keys: list[str]) -> int:
    """Open these crops + samples again. Returns how many were final."""
    fin, rows = finals(state, year), _final_rows(state, year)
    n = int(fin["KEY"].isin(keys).sum())
    _write_finals(state, year, fin[~fin["KEY"].isin(keys)], rows[~rows["KEY"].isin(keys)])
    return n


# ------------------------------------------------------------------ apply (corrections.csv) and export

def apply(state: str, year: str, changes: list[dict]) -> int:
    """Each change {EXPTID, Field, Now, Proposed} -> one line of corrections.csv (applied by utils/schedules.py)."""
    changes = [c for c in changes if not dv.same(c["Now"], c["Proposed"])]
    if not changes:
        return 0
    folder = dv._db(state, year)
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / dv.CORR_FILE
    first = not f.exists()
    stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    with open(f, "a", newline="", encoding="utf-8-sig" if first else "utf-8") as fh:
        w = csv.writer(fh)
        if first:
            w.writerow(["Date", "EXPTID", "Table", "SRL", "Field", "Old", "New"])
        for c in changes:
            w.writerow([stamp, c["EXPTID"], TABLE, "", c["Field"], c["Now"], c["Proposed"]])
    return len(changes)


def export(state: str, year: str, proposals: list[dict], issues: list[dict], scope: str) -> Path:
    """Both lists as CSV in 02_artifacts/07_rc7/<STATE>/<YEAR>/<dd.mm.yyyy>/."""
    made = datetime.now()
    out = ART / state / year / f"{made:%d.%m.%Y}"
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{made:%Y-%m-%d_%H%M%S}_{est._safe(scope)}"
    pd.DataFrame(proposals, columns=PROPOSAL_COLUMNS).to_csv(out / f"{tag}_proposed_corrections.csv", index=False,
                                                             encoding="utf-8-sig")
    pd.DataFrame(issues, columns=PROBLEM_COLUMNS).to_csv(out / f"{tag}_problems.csv", index=False,
                                                         encoding="utf-8-sig")
    return out
