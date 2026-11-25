"""Master list checks (taken from KrishiSoft's master list module), in LENIENT mode.

The official layout has 26 columns, YEAR … STATUS. Exp-ID (12 digits) = SAMPLE + STATE + DISTRICT + SELORDER
+ CROPCODE + EXPT, the same as EXPTID in AS 2.0's EXPTMASTER table.

Lenient means small things are fixed and only listed, not rejected:
  - column names in any letter case / with spaces, in any order; extra columns ignored
  - an EXPTID column is allowed (it must equal the Exp-ID built from its parts)
  - several sheets in one file are read together; rows repeated exactly are kept once
  - spaces at the start / end, double spaces, tabs, non-breaking spaces and line breaks in text are cleaned
Real errors still reject the file (blank codes, wrong number of digits, one code with two names, the same
Exp-ID with different data, more than one state or year in a file, …) and an error report (CSV files) is written.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import openpyxl
import pandas as pd

KEY = "EXPTID"

# Official column order. width = exact number of digits for codes (0 = free text).
COLUMNS: list[tuple[str, int, bool]] = [   # (name, digits, required)
    ("YEAR", 0, True), ("SEASONCODE", 1, True), ("SEASONNAME", 0, True), ("HSEASONNAME", 0, True),
    ("SAMPLE", 1, True), ("SAMPLENAME", 0, True), ("HSAMPLENAME", 0, True),
    ("STATE", 2, True), ("STATENAME", 0, True), ("SHORTSTATE", 0, True), ("HSTATENAME", 0, True),
    ("ROCODE", 3, True), ("RONAME", 0, True), ("HRONAME", 0, True),
    ("SROCODE", 4, True), ("SRONAME", 0, True), ("HSRONAME", 0, True),
    ("DISTRICT", 2, True), ("DISTRICTNAME", 0, True), ("HDISTRICTNAME", 0, True),
    ("SELORDER", 2, True), ("EXPT", 1, True),
    ("CROPCODE", 4, True), ("CROPNAME", 0, True), ("HCROPNAME", 0, True),
    ("STATUS", 0, False),
]
COLUMN_NAMES = [c[0] for c in COLUMNS]
ID_PARTS = ["SAMPLE", "STATE", "DISTRICT", "SELORDER", "CROPCODE", "EXPT"]
SAMPLE_NAMES = {"1": "CENTRAL", "2": "STATE"}
CODE_NAME_PAIRS = [
    ("SEASONCODE", "SEASONNAME"), ("SEASONCODE", "HSEASONNAME"),
    ("SAMPLE", "SAMPLENAME"), ("SAMPLE", "HSAMPLENAME"),
    ("STATE", "STATENAME"), ("STATE", "HSTATENAME"), ("STATE", "SHORTSTATE"),
    ("ROCODE", "RONAME"), ("ROCODE", "HRONAME"),
    ("SROCODE", "SRONAME"), ("SROCODE", "HSRONAME"),
    ("DISTRICT", "DISTRICTNAME"), ("DISTRICT", "HDISTRICTNAME"),
    ("CROPCODE", "CROPNAME"), ("CROPCODE", "HCROPNAME"),
]
YEAR_RE = re.compile(r"^(\d{4})-(\d{2})$")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
HINDI_COLUMNS = ["HSEASONNAME", "HSAMPLENAME", "HSTATENAME", "HRONAME", "HSRONAME", "HDISTRICTNAME", "HCROPNAME"]
ENGLISH_COLUMNS = ["SEASONNAME", "SAMPLENAME", "STATENAME", "SHORTSTATE", "RONAME", "SRONAME",
                   "DISTRICTNAME", "CROPNAME"]
SEASON_CODES = {"1", "2", "3", "4", "5", "6"}
EXPT_CODES = {"1", "2"}
MAX_SELORDER = 25          # same limit as the AS 2.0 RC-7 validation ("Order of Selection")


@dataclass
class Issue:
    row: int | None      # Excel row number (None = whole file)
    column: str
    value: str
    problem: str
    sheet: str = ""


@dataclass
class CheckResult:
    source: Path
    sheets: list[str] = field(default_factory=list)
    data: pd.DataFrame = field(default_factory=pd.DataFrame)   # 26 columns + SHEET + EXCEL_ROW
    issues: list[Issue] = field(default_factory=list)          # real errors -> file rejected
    fixes: list[Issue] = field(default_factory=list)           # small things fixed (lenient)
    year: str = ""
    state: str = ""        # STATENAME in capitals, e.g. BIHAR
    state_code: str = ""   # e.g. 10

    @property
    def ok(self) -> bool:
        return not self.issues


# ---------------------------------------------------------------- reading (lenient)

def _as_seen(cell) -> str:
    """Cell value as Excel shows it: number 1 with format '00' -> '01'."""
    v = cell.value
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not v.is_integer():
            return repr(v)
        n = int(v)
        fmt = (cell.number_format or "").strip()
        if fmt and set(fmt) == {"0"}:
            return str(n).zfill(len(fmt))
        return str(n)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _clean(v: str) -> tuple[str, str]:
    """(cleaned text, what was fixed or '')."""
    if not v:
        return v, ""
    fixed = []
    out = v
    if any(ch in out for ch in "\n\r\t\xa0​"):
        out = re.sub(r"[\n\r\t\xa0​]+", " ", out)
        fixed.append("line break / tab / hidden space")
    if out != out.strip():
        out = out.strip()
        fixed.append("space at start or end")
    if "  " in out:
        out = re.sub(r" {2,}", " ", out)
        fixed.append("double space")
    return out, ", ".join(fixed)


def read_excel(path: Path) -> CheckResult:
    """Every sheet that has the master list columns, cleaned; what was cleaned goes to res.fixes."""
    res = CheckResult(Path(path))
    wb = openpyxl.load_workbook(path, read_only=False, data_only=True)   # full mode: number formats
    frames = []
    try:
        for ws in wb.worksheets:
            rows = list(ws.iter_rows())
            if not rows:
                continue
            header = [_clean(_as_seen(c))[0].upper() for c in rows[0]]
            pos = {h: i for i, h in enumerate(header) if h}
            if not set(COLUMN_NAMES) - {"STATUS"} <= set(pos):
                missing = [c for c in COLUMN_NAMES if c not in pos]
                res.fixes.append(Issue(None, ", ".join(missing[:6]), "", f"Sheet '{ws.title}' skipped: not a master "
                                       f"list sheet ({len(missing)} column(s) missing)", ws.title))
                continue
            res.sheets.append(ws.title)
            extra = [h for h in pos if h not in COLUMN_NAMES and h != KEY]
            if extra:
                res.fixes.append(Issue(1, ", ".join(extra[:6]), "", "Extra column(s) ignored", ws.title))
            want = COLUMN_NAMES + ([KEY] if KEY in pos else [])
            recs, excel_rows = [], []
            for r in rows[1:]:
                values = {}
                for name in want:
                    i = pos.get(name)
                    cell = r[i] if i is not None and i < len(r) else None
                    text = _as_seen(cell) if cell is not None else ""
                    text, fix = _clean(text)
                    if fix:
                        res.fixes.append(Issue(r[0].row, name, text, f"Cleaned: {fix}", ws.title))
                    values[name] = text
                if not any(values[c] for c in COLUMN_NAMES):
                    continue                                  # fully empty row
                recs.append(values)
                excel_rows.append(r[0].row)
            df = pd.DataFrame(recs, columns=want)
            df.insert(0, "EXCEL_ROW", excel_rows)
            df.insert(0, "SHEET", ws.title)
            frames.append(df)
    finally:
        wb.close()
    if not frames:
        res.issues.append(Issue(None, "", "", "No sheet with the master list columns (YEAR … HCROPNAME)"))
        return res
    df = pd.concat(frames, ignore_index=True).fillna("")
    # several sheets (e.g. ML_C, ML_S, ML_C+S): the same row twice is kept once
    before = len(df)
    df = df.drop_duplicates(subset=COLUMN_NAMES, keep="first").reset_index(drop=True)
    if len(df) < before:
        res.fixes.append(Issue(None, "", "", f"{before - len(df)} row(s) repeated exactly (other sheet / same sheet) "
                                             "kept once"))
    # an EXPTID column must agree with its parts
    if KEY in df.columns:
        built = df[ID_PARTS].agg("".join, axis=1)
        bad = (df[KEY] != "") & (df[KEY] != built)
        for _, r in df[bad].iterrows():
            res.issues.append(Issue(int(r.EXCEL_ROW), KEY, r[KEY], f"EXPTID does not match its parts "
                                    f"({built[_]})", r.SHEET))
        df = df.drop(columns=KEY)
    res.data = df
    return res


# ---------------------------------------------------------------- checks (KrishiSoft rules)

def _guess_state_year(res: CheckResult) -> None:
    df = res.data

    def usual(col: str) -> str:
        if col not in df.columns:
            return ""
        s = df[col].astype(str).str.strip()
        s = s[s != ""]
        return s.mode().iloc[0] if not s.empty else ""

    year = usual("YEAR")
    res.year = year if YEAR_RE.fullmatch(year) else ""
    res.state_code = usual("STATE")
    if res.state_code and "STATENAME" in df.columns:
        names = df.loc[df["STATE"] == res.state_code, "STATENAME"].str.strip().str.upper()
        names = names[names != ""]
        res.state = names.mode().iloc[0] if not names.empty else ""
    res.state = re.sub(r'[<>:"/\\|?*]', "", res.state)


def check(res: CheckResult) -> CheckResult:
    """Every KrishiSoft rule on the cleaned data; problems go to res.issues (nothing is changed)."""
    _guess_state_year(res)
    df = res.data
    if df.empty:
        res.issues.append(Issue(None, "", "", "No data rows"))
        return res
    rows = df["EXCEL_ROW"]
    sheets = df["SHEET"]

    def flag(mask: pd.Series, col: str, problem: str) -> None:
        for r, sh, v in zip(rows[mask], sheets[mask], df.loc[mask, col]):
            res.issues.append(Issue(int(r), col, v, problem, sh))

    for name, width, required in COLUMNS:          # required cells and code widths
        s = df[name]
        blank = s == ""
        if required:
            flag(blank, name, "Blank")
        if width:
            flag(~blank & ~s.str.fullmatch(rf"\d{{{width}}}"), name, f"Must be exactly {width} digit(s)")

    years = df.loc[df["YEAR"] != "", "YEAR"]       # one year, YYYY-YY
    fmt_bad = ~years.str.fullmatch(YEAR_RE.pattern)
    flag(fmt_bad.reindex(df.index, fill_value=False), "YEAR", "Must look like 2025-26")
    good_years = years[~fmt_bad]
    for y in good_years.unique():
        m = YEAR_RE.match(y)
        if (int(m.group(1)) + 1) % 100 != int(m.group(2)):
            flag(df["YEAR"] == y, "YEAR", "Second year must follow the first (e.g. 2025-26)")
    if good_years.nunique() > 1:
        main = good_years.mode().iloc[0]
        flag((df["YEAR"] != "") & (df["YEAR"] != main) & ~fmt_bad.reindex(df.index, fill_value=False),
             "YEAR", f"Different year from the rest of the file ({main}); one master list per year")
    elif good_years.nunique() == 1:
        res.year = good_years.iloc[0]

    states = df.loc[df["STATE"] != "", "STATE"]    # one state per file
    if states.nunique() > 1:
        main = states.mode().iloc[0]
        flag((df["STATE"] != "") & (df["STATE"] != main), "STATE",
             f"Different state from the rest of the file ({main}); one master list per state")

    flag(df["SAMPLE"].ne("") & ~df["SAMPLE"].isin(SAMPLE_NAMES), "SAMPLE", "Must be 1 (Central) or 2 (State)")
    expected = df["SAMPLE"].map(SAMPLE_NAMES)
    flag(expected.notna() & (df["SAMPLENAME"].str.upper() != expected), "SAMPLENAME", "Does not match SAMPLE code")

    for code, name in CODE_NAME_PAIRS:             # each code has one name (letter case ignored)
        sub = df[(df[code] != "") & (df[name] != "")]
        upper = sub[name].str.upper()
        names = upper.groupby(sub[code]).nunique()
        for c in names[names > 1].index:
            counts = upper[sub[code] == c].value_counts()
            usual = counts.index[0]
            odd = (df[code] == c) & (df[name] != "") & (df[name].str.upper() != usual)
            flag(odd, name, f"{code} {c} is '{usual}' in {counts.iloc[0]} other row(s)")

    both = (df["SROCODE"].str.len() == 4) & (df["ROCODE"].str.len() == 3)
    flag(both & (df["SROCODE"].str[:3] != df["ROCODE"]), "SROCODE", "SRO code does not start with its RO code")

    exptid = df[ID_PARTS].agg("".join, axis=1)     # Exp-ID unique (exact repeats were already merged)
    complete = df[ID_PARTS].ne("").all(axis=1)
    dup = complete & exptid.duplicated(keep=False)
    for r, sh, e in zip(rows[dup], sheets[dup], exptid[dup]):
        res.issues.append(Issue(int(r), KEY, e, "Same Exp-ID with different data in another row", sh))

    def one_value_per_group(group: pd.Series, value: pd.Series, col: str, message: str) -> None:
        ok = (group != "") & (value != "")
        counts = value[ok].groupby(group[ok]).value_counts()
        for g in counts.index.get_level_values(0).unique():
            per = counts[g]
            if len(per) > 1:
                usual = per.index[0]
                flag(ok & (group == g) & (value != usual), col, message.format(g=g, usual=usual, n=per.iloc[0]))

    flag(df["SEASONCODE"].str.fullmatch(r"\d") & ~df["SEASONCODE"].isin(SEASON_CODES), "SEASONCODE", "Must be 1 to 6")
    flag(df["EXPT"].str.fullmatch(r"\d") & ~df["EXPT"].isin(EXPT_CODES), "EXPT", "Must be 1 or 2")
    sel = pd.to_numeric(df["SELORDER"].where(df["SELORDER"].str.fullmatch(r"\d{2}")), errors="coerce")
    flag(sel.notna() & ((sel < 1) | (sel > MAX_SELORDER)), "SELORDER", f"Must be 01 to {MAX_SELORDER:02d}")
    flag(df["SHORTSTATE"].ne("") & ~df["SHORTSTATE"].str.fullmatch(r"[A-Z]{2}"), "SHORTSTATE",
         "Must be 2 capital letters (e.g. BR)")
    flag(df["STATUS"] != "", "STATUS", "Must be blank")

    both = (df["ROCODE"].str.len() == 3) & (df["STATE"].str.len() == 2)
    flag(both & (df["ROCODE"].str[:2] != df["STATE"]), "ROCODE", "RO code does not start with the STATE code")
    one_value_per_group(df["DISTRICT"], df["SROCODE"], "SROCODE", "District {g} is under SRO {usual} in {n} other row(s)")
    one_value_per_group(df["CROPCODE"], df["SEASONCODE"], "SEASONCODE", "Crop {g} is in season {usual} in {n} other row(s)")

    for code, name in CODE_NAME_PAIRS:             # a name is not used for two codes
        if code in ("STATE", "SAMPLE"):
            continue
        key = df[name].str.upper()
        if code == "CROPCODE":
            key = df["SEASONCODE"] + "|" + key
        one_value_per_group(key, df[code], name, f"Name '{{g}}' is also used for {code} {{usual}} ({{n}} row(s))")
    for issue in res.issues:
        if issue.problem.startswith("Name '") and "|" in issue.problem:
            issue.problem = re.sub(r"Name '\d\|", "Name '", issue.problem)

    village = df["SAMPLE"] + "|" + df["DISTRICT"] + "|" + df["SELORDER"] + "|" + df["CROPCODE"]
    valid = df[ID_PARTS].ne("").all(axis=1) & df["EXPT"].isin(EXPT_CODES)
    have = df.loc[valid, "EXPT"].groupby(village[valid]).agg(lambda s: set(s))
    for v, expts in have.items():
        missing = EXPT_CODES - expts
        if missing:
            flag(valid & (village == v), "EXPT", f"Experiment {', '.join(sorted(missing))} missing for this village and crop")

    for col in HINDI_COLUMNS:
        flag(df[col].ne("") & ~df[col].str.contains(DEVANAGARI), col, "Must be written in Hindi")
    for col in ENGLISH_COLUMNS:
        flag(df[col].str.contains(DEVANAGARI), col, "Must be in English (has Hindi letters)")
    return res


def check_file(path: Path) -> CheckResult:
    res = read_excel(path)
    if res.data.empty and res.issues:
        return res
    return check(res)


def with_exptid(df: pd.DataFrame) -> pd.DataFrame:
    out = df.drop(columns=[c for c in ("SHEET", "EXCEL_ROW") if c in df.columns]).copy()
    out[KEY] = out[ID_PARTS].agg("".join, axis=1)
    return out


# ---------------------------------------------------------------- reports

def _issue_frame(items: list[Issue]) -> pd.DataFrame:
    return pd.DataFrame([{"Sheet": i.sheet, "Excel row": i.row if i.row else "(file)", "Column": i.column,
                          "Value": i.value, "Problem": i.problem} for i in items],
                        columns=["Sheet", "Excel row", "Column", "Value", "Problem"])


RULES = [
    ("All columns", "The 26 columns YEAR … STATUS (any letter case or order; extra columns and an EXPTID column are "
                    "allowed - an EXPTID column must equal SAMPLE+STATE+DISTRICT+SELORDER+CROPCODE+EXPT)"),
    ("All cells", "Spaces at the start / end, double spaces, tabs, hidden characters and line breaks are CLEANED "
                  "automatically (listed in 'Cleaned', not errors)"),
    ("All cells", "Not blank (except STATUS)"),
    ("YEAR", "Like 2025-26 (second year follows the first); the same year in every row"),
    ("SEASONCODE", "1 digit, 1 to 6; a crop is in one season only"),
    ("SAMPLE", "1 (Central) or 2 (State); SAMPLENAME CENTRAL for 1, STATE for 2 (letter case ignored)"),
    ("STATE", "2 digits; one state per file"),
    ("ROCODE / SROCODE", "3 / 4 digits; RO code starts with the STATE code, SRO code with its RO code; "
                         "a district is under one SRO"),
    ("DISTRICT, SELORDER, EXPT, CROPCODE", "2, 2 (01 to 25), 1 (1 or 2), 4 digits; every village has experiments 1 and 2"),
    ("Code and name", "Each code has one name (English, Hindi, short state name) and a name is not used for two codes"),
    ("Hindi / English", "H… columns in Hindi (Devanagari); the others without Hindi letters; SHORTSTATE 2 capitals"),
    ("Exp-ID", "SAMPLE+STATE+DISTRICT+SELORDER+CROPCODE+EXPT is unique (rows repeated exactly are kept once)"),
    ("STATUS", "Blank"),
]


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    """CSV with a BOM, so Excel opens Hindi text correctly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_error_report(res: CheckResult, folder: Path) -> Path:
    """Error report as CSV files in folder/<date-time>_<file>_ERRORS/ (like KrishiSoft's sheets):
    Read_me, Rules, Problem_count, Errors, Marked_data (the rows with problems, a PROBLEMS column and the bad
    columns listed in BAD_COLUMNS), Cleaned. Returns the folder."""
    out = folder / f"{datetime.now():%Y-%m-%d_%H%M%S}_{res.source.stem}_ERRORS"
    out.mkdir(parents=True, exist_ok=True)
    errors = _issue_frame(res.issues)
    write_csv(pd.DataFrame({"Master list check FAILED": [
        f"File: {res.source.name}", f"Sheet(s): {', '.join(res.sheets) or '-'}",
        f"State / year: {res.state or '?'} {res.year or '?'}", f"Checked: {datetime.now():%d-%m-%Y %H:%M}",
        f"Problems found: {len(res.issues)} (the file was NOT imported; the stored list is unchanged)",
        f"Cleaned automatically: {len(res.fixes)} item(s) - see Cleaned.csv",
        "Errors.csv lists every problem; Marked_data.csv has the rows with problems (PROBLEMS, BAD_COLUMNS).",
        "Rules.csv lists every check. Correct the file and import it again."]}), out / "Read_me.csv")
    write_csv(pd.DataFrame(RULES, columns=["Column", "Rule"]), out / "Rules.csv")
    write_csv(errors.groupby(["Column", "Problem"]).size().reset_index(name="Count")
              .sort_values("Count", ascending=False), out / "Problem_count.csv")
    write_csv(errors, out / "Errors.csv")
    data = res.data
    rows_with = {(i.sheet, i.row) for i in res.issues if i.row}
    if not data.empty and rows_with:
        marked = data[[(sh, r) in rows_with for sh, r in zip(data["SHEET"], data["EXCEL_ROW"])]].copy()
        probs, bad = {}, {}
        for i in res.issues:
            if i.row:
                probs.setdefault((i.sheet, i.row), []).append(i.problem)
                bad.setdefault((i.sheet, i.row), []).extend(ID_PARTS if i.column == KEY else i.column.split(", "))
        keys = list(zip(marked["SHEET"], marked["EXCEL_ROW"]))
        marked.insert(2, "PROBLEMS", ["; ".join(dict.fromkeys(probs.get(k, []))) for k in keys])
        marked.insert(3, "BAD_COLUMNS", [", ".join(dict.fromkeys(bad.get(k, []))) for k in keys])
        write_csv(marked.rename(columns={"SHEET": "Sheet", "EXCEL_ROW": "Excel row"}), out / "Marked_data.csv")
    if res.fixes:
        write_csv(_issue_frame(res.fixes), out / "Cleaned.csv")
    return out


def summary_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(crop-wise, district-wise) counts Central / State / Total per state + year."""
    sample = df["SAMPLE"].map(SAMPLE_NAMES).rename("S")
    crop = (df.groupby(["STATENAME", "YEAR", "SEASONCODE", "SEASONNAME", "CROPCODE", "CROPNAME", sample]).size()
            .unstack("S", fill_value=0).reindex(columns=list(SAMPLE_NAMES.values()), fill_value=0))
    crop["TOTAL"] = crop.sum(axis=1)
    dist = (df.groupby(["STATENAME", "YEAR", "DISTRICT", "DISTRICTNAME", sample]).size()
            .unstack("S", fill_value=0).reindex(columns=list(SAMPLE_NAMES.values()), fill_value=0))
    dist["TOTAL"] = dist.sum(axis=1)
    return crop.reset_index(), dist.reset_index()
