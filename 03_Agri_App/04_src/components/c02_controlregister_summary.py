"""2. Control Register: planned experiments of the master list vs the imported schedules (RC-7), and NR.

Copied from KrishiSoft_V0.1 (core/control_register.py + core/nr.py), which follows the old AS 2.0 Access tool
(control register.accdb, reports DETAILS / CONTROL REGISTER / TOTAL RO). Status comes from RC-7:
STAGIN 1 = harvested, 2 = missed, 3 = lost; REJ 1 = rejected.

    Planned       experiments in the master list
    Received      planned experiments that have an imported RC-7
    Not received  planned experiments without an RC-7 (NR)
    Harvested     STAGIN 1 minus rejected (same formula as the old report)
    Missed / Lost STAGIN 2 / 3
    Rejected      REJ 1
    Harvest %     harvested × 100 / planned

DGCES experiments have no Exp-ID yet (order of selection pending), so they cannot be matched to the
master list: they are only counted ("DGCES received, not linked yet").

Exports: the Control Register as CSV files; NR in the office's NR Excel format (user decision 2026-11-24).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

COUNTS = ["Planned", "Received", "Not received", "Harvested", "Missed", "Lost", "Rejected"]
COLUMNS = COUNTS + ["Harvest %"]


def _code(s: pd.Series) -> pd.Series:
    """'1' / '1.0' / ' 1' -> '1'."""
    return s.fillna("").astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)


def build(ml: pd.DataFrame, rc7: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(one row per planned experiment with its status, imported RC-7 rows not in the master list)."""
    if ml.empty:
        return pd.DataFrame(), pd.DataFrame()
    planned = set(ml["EXPTID"])
    if rc7.empty:
        rc7 = pd.DataFrame(columns=["EXPTID", "STAGIN", "REJ", "SOURCE"])
    rc7 = rc7.drop_duplicates("EXPTID", keep="last")
    extra = rc7[~rc7["EXPTID"].isin(planned)]
    r = rc7.reindex(columns=["EXPTID", "STAGIN", "REJ", "SOURCE"]).astype(str)
    df = ml.merge(r, on="EXPTID", how="left")
    df["RECEIVED"] = df["SOURCE"].notna() & (df["SOURCE"] != "nan")
    st, rej = _code(df["STAGIN"]), _code(df["REJ"])
    df["H1"] = df["RECEIVED"] & (st == "1")
    df["MISSED"] = df["RECEIVED"] & (st == "2")
    df["LOST"] = df["RECEIVED"] & (st == "3")
    df["REJECTED"] = df["RECEIVED"] & (rej == "1")
    return df, extra


def _counts(g: pd.DataFrame) -> dict:
    planned = len(g)
    received = int(g["RECEIVED"].sum())
    harvested = int(g["H1"].sum()) - int(g["REJECTED"].sum())
    return {"Planned": planned, "Received": received, "Not received": planned - received, "Harvested": harvested,
            "Missed": int(g["MISSED"].sum()), "Lost": int(g["LOST"].sum()), "Rejected": int(g["REJECTED"].sum()),
            "Harvest %": round(harvested * 100 / planned, 2) if planned else 0.0}


def totals(df: pd.DataFrame) -> dict:
    return _counts(df) if not df.empty else {c: 0 for c in COLUMNS}


def filter_sample(df: pd.DataFrame, sample: str | None) -> pd.DataFrame:
    return df[df["SAMPLE"] == sample] if sample and not df.empty else df


def by_crop(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    rows = []
    for (scode, season, crop, cname, sample), g in df.groupby(
            ["SEASONCODE", "SEASONNAME", "CROPCODE", "CROPNAME", "SAMPLENAME"], sort=False):
        rows.append({"_s": scode, "Season": season, "Crop code": crop, "Crop": cname, "Sample": sample, **_counts(g)})
    out = pd.DataFrame(rows)
    out = out.assign(_n=pd.to_numeric(out["_s"], errors="coerce")).sort_values(["_n", "Crop code", "Sample"])
    out = out.drop(columns=["_s", "_n"])
    total = {"Season": "", "Crop code": "", "Crop": "TOTAL", "Sample": "", **_counts(df)}
    return pd.concat([out, pd.DataFrame([total])], ignore_index=True)


def by_ro_sro(df: pd.DataFrame) -> pd.DataFrame:
    """RO and SRO rows with an RO total after each RO and a grand total (like the old TOTAL RO report)."""
    if df.empty:
        return pd.DataFrame()
    rows = []
    for (ro, roname), g_ro in df.groupby(["ROCODE", "RONAME"], sort=True):
        for (sro, sroname), g in g_ro.groupby(["SROCODE", "SRONAME"], sort=True):
            rows.append({"RO": f"{roname} ({ro})", "SRO": f"{sroname} ({sro})", **_counts(g)})
        rows.append({"RO": f"{roname} ({ro})", "SRO": "RO TOTAL", **_counts(g_ro)})
    rows.append({"RO": "", "SRO": "TOTAL", **_counts(df)})
    return pd.DataFrame(rows)


def export_csv(folder: Path, df: pd.DataFrame, extra: pd.DataFrame, head: dict) -> Path:
    """<folder>/<date-time>/Summary.csv, By_crop.csv, By_RO_SRO.csv (+ Not_in_master_list.csv)."""
    out = folder / f"{datetime.now():%Y-%m-%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    summary = {**head, "Made on": f"{datetime.now():%d-%m-%Y %H:%M}", **totals(df),
               "Received but not in master list": len(extra)}
    pd.DataFrame(list(summary.items()), columns=["Item", "Value"]).to_csv(out / "Summary.csv", index=False,
                                                                          encoding="utf-8-sig")
    by_crop(df).to_csv(out / "By_crop.csv", index=False, encoding="utf-8-sig")
    by_ro_sro(df).to_csv(out / "By_RO_SRO.csv", index=False, encoding="utf-8-sig")
    if not extra.empty:
        extra.to_csv(out / "Not_in_master_list.csv", index=False, encoding="utf-8-sig")
    return out


# ------------------------------------------------------------ NR (Not Received)

NR_COLUMNS = {"EXPTID": "Exp-ID", "SEASONNAME": "Season", "SAMPLENAME": "Sample", "DISTRICTNAME": "District",
              "RONAME": "RO", "SRONAME": "SRO", "CROPCODE": "Crop code", "CROPNAME": "Crop",
              "SELORDER": "Sel. order", "EXPT": "Expt"}
NR_ORDER = ["SEASONCODE", "CROPCODE", "SAMPLE", "SROCODE", "DISTRICT", "SELORDER", "EXPT"]


def nr_list(df: pd.DataFrame) -> pd.DataFrame:
    """Not-received rows, sorted season -> crop -> sample -> SRO -> district -> sel. order -> expt."""
    if df.empty:
        return pd.DataFrame(columns=list(NR_COLUMNS.values()))
    out = df[~df["RECEIVED"]].sort_values(NR_ORDER)
    return out[list(NR_COLUMNS)].rename(columns=NR_COLUMNS).reset_index(drop=True)


# Office format (e.g. NR\03.09.2026\Central\NR_REDGRAM_CENTRAL_2025-26.xlsx): one file per season + crop + sample,
# crop varieties together (WHEAT_HYI + WHEAT_LI -> WHEAT), season in front only when the crop grows in more than one
# season (AGHANI_PADDY), Central with RONAME and State without, rows by RO then Exp-ID, codes as text, Calibri 11,
# bold header, thin borders.
VARIETY = re.compile(r"_(HYUI|HYI|LUI|HY|LI|UI|I|L)$")
SHORT = {"RAPE_MUSTARD": "R&M"}
EXPORT_CENTRAL = ["SEASONNAME", "SAMPLENAME", "STATENAME", "RONAME", "CROPNAME", "DISTRICT", "DISTRICTNAME",
                  "SELORDER", "EXPTNO"]
EXPORT_STATE = [c for c in EXPORT_CENTRAL if c != "RONAME"]


def crop_group(cropname: str) -> str:
    """PADDY_HYI -> PADDY, WHEAT_LI -> WHEAT, SUGARCANE_UI -> SUGARCANE, RAPE_MUSTARD -> R&M."""
    base = VARIETY.sub("", str(cropname).strip().upper())
    return SHORT.get(base, base)


def export_nr_excel(nr_root: Path, year: str, planned_all: pd.DataFrame, part: pd.DataFrame,
                    one_crop: bool = False) -> tuple[Path, list[Path]]:
    """Write the NR files of the chosen experiments into nr_root/<dd.mm.yyyy>/<Central|State>/.

    planned_all: every planned experiment (to know which crops grow in more than one season).
    one_crop: a single crop was chosen, so files are named by that crop, not its group.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Border, Font, Side
    from openpyxl.utils import get_column_letter

    seasons_of = planned_all.assign(_g=planned_all["CROPNAME"].map(crop_group)).groupby("_g")["SEASONNAME"].nunique()
    day = nr_root / f"{date.today():%d.%m.%Y}"
    nr = part[~part["RECEIVED"]].assign(EXPTNO=lambda d: d["EXPT"], _g=lambda d: d["CROPNAME"].map(crop_group))
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    written = []
    for (season, group, sample), g in nr.groupby(["SEASONNAME", "_g", "SAMPLENAME"], sort=False):
        label = g["CROPNAME"].iloc[0] if one_crop else group
        if seasons_of.get(group, 1) > 1:
            label = f"{season}_{label}"
        sample = str(sample).upper()
        central = sample == "CENTRAL"
        cols = EXPORT_CENTRAL if central else EXPORT_STATE
        g = g.sort_values(["RONAME", "EXPTID"] if central else ["EXPTID"])
        folder = day / sample.title()
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"NR_{label}_{sample}_{year}.xlsx"
        wb = Workbook()
        sh = wb.active
        sh.title = re.sub(r"[\[\]:*?/\\]", "", label)[:31]
        sh.append(cols)
        for rec in g[cols].astype(str).itertuples(index=False):
            sh.append(list(rec))
        for row in sh.iter_rows():
            for c in row:
                c.border = box
                c.font = Font(name="Calibri", size=11, bold=c.row == 1)
                c.number_format = "@"                      # codes stay text: 08, 03
        for i, col in enumerate(cols, 1):
            width = max(len(col), *(len(str(v)) for v in g[col])) + 3
            sh.column_dimensions[get_column_letter(i)].width = width
        wb.save(out)
        written.append(out)
    return day, written
