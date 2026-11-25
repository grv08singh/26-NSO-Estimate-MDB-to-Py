"""3. View Schedule: fill the Schedule 2.0 Word form (as20.docx) for an Exp-ID; view it in Word or save it as PDF.

Copied from KrishiSoft_V0.1 (core/schedule_print.py). The template comes from the AS 2.0 software. Every value
cell holds one placeholder:

  #NAME           a column of the master list (#STATENAME, #DISTRICT, #YEAR, #PRTID …) or, by the
                  same name, of Block 1 / 2 / 10 / 12 (#TEHSIL, #CULTNAME, #REMARKS, #SUPVNAME …)
  #A1 … #A10      sample / season / crop header (master list)
  #<L><c>.<r>     block L, its c-th data column, row (SRL) r — e.g. #R2.1 = Block 3, DIMLENGTH, SRL 1
  #M<c>.<code>    Block 5p3 (several harvests): row = item code 10 … 95 / 99, 12 count/weight columns
  #MD.<code>      Block 5p3 harvest date of that item code

The letter -> block/column layout and the number formats were checked in KrishiSoft against 59 schedules printed
by the old software (2020-21 … 2025-26): every filled placeholder matches. Empty values are left blank.
The data (master list row + block rows of one Exp-ID) is passed in; reading it is src/utils/schedules.py.
"""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from lxml import etree

TEMPLATE = Path(__file__).resolve().parents[1] / "resources" / "as20.docx"
BLANK = ""
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
TOKEN = re.compile(r"#[A-Za-z][A-Za-z0-9_.]*")

# Coded blocks: letter -> (block table, data columns in placeholder order)
CODED = {
    "R": ("Sch20Block3", ["UNITLENGTH", "DIMLENGTH", "UNITBREADTH", "DIMBREADTH", "COORDLENGTH", "COORDBREADTH"]),
    "P": ("Sch20Block3p1", ["TREES", "R1", "R2", "R3", "R4", "R5"]),
    "S": ("Sch20Block4", ["MSTK", "MSTKTYP", "RECT"]),
    "T": ("Sch20Block5p1", ["DTORIGINAL", "DTACTUAL", "DTTHRESHING", "DTWEIGH", "SHAPE", "PRODDESC",
                            "WEIGHT", "NETWEIGHT", "MISTAKE", "RECTI", "TOTPICK"]),
    "U": ("Sch20Block5p2", ["IFMISSED", "DTPICK", "WEIGHT", "FRUITS", "FRUITWEIGHT", "STALKWEIGHT"]),
    "V": ("Sch20Block6", ["EQUIP", "EQUIPSTATUS", "BALANCE", "BALANCESTATUS", "WEIGHT", "PEGS"]),
    "W": ("Sch20Block7", ["DESPLANNED", "ARRANGEMENTS", "DTHARVEST", "PRODDESC", "WEIGHT", "PRODAVL", "WEIGHTSUPER"]),
    "X": ("Sch20Block8P1", ["SEEDTYPE", "NAMESTRAIN", "RATEOFAPP", "IFAPPLIED", "IRRIGATIONS", "IRRISOURCE",
                            "SPECIFYIRRISOURCE"]),
    "Q": ("Sch20Block8P2", ["FERTAPPLIED", "FERTNAME1", "FERTNAME2", "FERTNAME3", "FERTQT1", "FERTQT2", "FERTQT3",
                            "FERTRATEN", "FERTRATEP", "FERTRATEK", "MANRAPPLIED", "MANRCODE", "SPECIFYMANRCODE",
                            "PESTAPPLIED", "PESTMEASURE"]),
    "Y": ("Sch20Block9P1", ["CROPDENSITY", "CROPMATURITY", "CROPCOND", "AFF"]),
    "Z": ("Sch20Block9P2", ["AREA", "FIELDMERGE", "CROPNAME", "PROVINF1", "PCNTFORM1", "PROVINSUPER", "PCNTSUPER"]),
    "L": ("Sch20Block10", ["L1", "L2"]),
}
M_BLOCK = ("Sch20Block5p3", ["NUM1", "WT1", "NUM2", "WT2", "NUM3", "WT3", "NUM4", "WT4", "NUM5", "WT5",
                             "TNUM", "TWT"])
HEADER = {"A1": "HSAMPLENAME", "A2": "SAMPLENAME", "A3": "SAMPLE", "A4": "EXPT", "A5": "HSEASONNAME",
          "A6": "SEASONNAME", "A7": "SEASONCODE", "A8": "HCROPNAME", "A9": "CROPNAME", "A10": "CROPCODE"}
MASTER_NAMED = {"YEAR", "STATE", "STATENAME", "HSTATENAME", "DISTRICT", "DISTRICTNAME", "HDISTRICTNAME", "SELORDER"}
NAMED_BLOCKS = ["Sch20Block1", "Sch20Block2", "Sch20Block10", "Sch20Block12"]

# Number formats used by the old software (everything else is printed exactly as stored)
FORMATS = {
    ("Sch20Block2", "SURVAREA"): "{:.2f}", ("Sch20Block2", "CROPAREA"): "{:.2f}",
    ("Sch20Block5p1", "WEIGHT"): "{:.3f}",
    ("Sch20Block8P1", "RATEOFAPP"): "int",
    **{("Sch20Block8P2", c): "int" for c in ("FERTQT1", "FERTQT2", "FERTQT3", "FERTRATEN", "FERTRATEP", "FERTRATEK")},
    ("Sch20Block9P2", "PCNTFORM1"): "int", ("Sch20Block9P2", "PCNTSUPER"): "int",
}


def prtid(m: dict) -> str:
    """Printed schedule id, e.g. C3BR31PADDY_ HY_IR0112020-21 (checked on 59 old schedules)."""
    return (("C" if m.get("SAMPLE") == "1" else "S") + m.get("SEASONCODE", "") + m.get("SHORTSTATE", "")
            + m.get("DISTRICT", "") + m.get("CROPNAME", "") + m.get("SELORDER", "") + m.get("EXPT", "")
            + m.get("YEAR", ""))


def _fmt(table: str | None, col: str, value) -> str:
    value = "" if value is None else str(value)
    if value.strip() == "":
        return BLANK
    f = FORMATS.get((table, col))
    if f:
        try:
            num = float(value)
        except ValueError:
            return value.rstrip()
        if f == "int":                 # 25.0 -> 25, but 167.5 stays 167.5 (as the old software)
            return str(int(num)) if num.is_integer() else value.strip()
        return f.format(num)
    return value.rstrip()


def _rows(df: pd.DataFrame | None, key: str = "SRL") -> dict[str, dict]:
    if df is None or df.empty:
        return {}
    out = {}
    for rec in df.to_dict("records"):
        k = str(rec.get(key, "") or "")
        if k.endswith(".0"):
            k = k[:-2]
        out[k] = rec
    return out


def _first(df: pd.DataFrame | None) -> dict:
    return df.iloc[0].to_dict() if df is not None and not df.empty else {}


def build_values(master: dict, blocks: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Value for every placeholder in the template (without the '#')."""
    master = {k: ("" if v is None else str(v)) for k, v in master.items()}
    master.setdefault("PRTID", prtid(master))
    single = {t: _first(blocks.get(t)) for t in NAMED_BLOCKS}
    by_srl = {t: _rows(blocks.get(t)) for t, _ in CODED.values()}
    m_rows = _rows(blocks.get(M_BLOCK[0]))
    values: dict[str, str] = {}
    for token in template_tokens():
        name = token[1:]
        if name in HEADER:
            values[name] = master.get(HEADER[name], "") or BLANK
        elif name == "PRTID" or name in MASTER_NAMED:
            values[name] = master.get(name) or BLANK
        elif m := re.fullmatch(r"([A-Z])(\d+)(?:\.(\d+))?", name):
            letter, col_no, row = m.group(1), int(m.group(2)), m.group(3) or ""
            if letter == "M":
                col = M_BLOCK[1][col_no - 1]
                values[name] = _fmt(M_BLOCK[0], col, m_rows.get(row, {}).get(col))
            elif letter in CODED:
                table, cols = CODED[letter]
                rec = by_srl[table].get(row, {}) if row else _first(blocks.get(table))
                values[name] = _fmt(table, cols[col_no - 1], rec.get(cols[col_no - 1]))
            else:
                values[name] = BLANK
        elif m := re.fullmatch(r"MD\.(\d+)", name):
            values[name] = _fmt(M_BLOCK[0], "DTHARVEST", m_rows.get(m.group(1), {}).get("DTHARVEST"))
        else:   # named column of Block 1 / 2 / 10 / 12
            table = next((t for t in NAMED_BLOCKS if name in single[t]), None)
            values[name] = _fmt(table, name, single[table].get(name)) if table else BLANK
    return values


_TOKENS: list[str] | None = None


def _placeholder_paragraphs(root):
    """(token, text elements) for every paragraph whose whole text is one placeholder (Word may split it)."""
    for p in root.iter(W + "p"):
        ts = list(p.iter(W + "t"))
        text = "".join(t.text or "" for t in ts).strip()
        if ts and TOKEN.fullmatch(text):
            yield text, ts


def template_tokens() -> list[str]:
    global _TOKENS
    if _TOKENS is None:
        root = etree.fromstring(zipfile.ZipFile(TEMPLATE).read("word/document.xml"))
        _TOKENS = sorted({tok for tok, _ in _placeholder_paragraphs(root)})
    return _TOKENS


def fill_document(values: dict[str, str], out_path: Path) -> Path:
    """Write a copy of the template with every placeholder replaced."""
    with zipfile.ZipFile(TEMPLATE) as zin:
        parts = {i.filename: zin.read(i.filename) for i in zin.infolist()}
        infos = zin.infolist()
    root = etree.fromstring(parts["word/document.xml"])
    for token, ts in list(_placeholder_paragraphs(root)):
        if token[1:] not in values:
            continue
        for extra in ts[1:]:          # a split placeholder: keep the first piece, empty the rest
            extra.text = ""
        t = ts[0]
        lines = values[token[1:]].replace("\r\n", "\n").replace("\r", "\n").split("\n")
        t.text = lines[0]
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        anchor = t
        for line in lines[1:]:        # line breaks inside a value (e.g. remarks)
            br = etree.Element(W + "br")
            anchor.addnext(br)
            nt = etree.Element(W + "t")
            nt.text = line
            nt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            br.addnext(nt)
            anchor = nt
    parts["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            zout.writestr(info, parts[info.filename])
    tmp.replace(out_path)
    return out_path


def values_for(ml_row: dict, blocks: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Placeholder values for one Exp-ID (its master list row + its block rows)."""
    return build_values(ml_row, {t: df.reset_index(drop=True) for t, df in blocks.items()})


def schedule_list(ml: pd.DataFrame, rc7: pd.DataFrame, blocks1: pd.DataFrame) -> pd.DataFrame:
    """One row per imported Exp-ID: what is needed to find it (VILLAGE from Block 1, BLOCKS stored or not)."""
    cols = ["EXPTID", "VILLAGE", "SOURCES", "BLOCKS"]
    if rc7.empty:
        return pd.DataFrame(columns=cols)
    ids = rc7.groupby("EXPTID")["SOURCE"].agg(lambda s: " + ".join(sorted(set(s)))).rename("SOURCES")
    if blocks1.empty:
        blocks1 = pd.DataFrame(columns=["EXPTID", "SURVVILL"])
    village = blocks1.drop_duplicates("EXPTID", keep="last").set_index("EXPTID").get(
        "SURVVILL", pd.Series(dtype=str))
    stored = set(blocks1["EXPTID"])
    return pd.DataFrame([{"EXPTID": e, "VILLAGE": village.get(e, ""), "SOURCES": src,
                          "BLOCKS": "Yes" if e in stored else "RC-7 only"} for e, src in ids.items()], columns=cols)


def crop_sample_folder(row: dict) -> Path:
    """<CROP>/<Central|State> sub-folder for one master-list row."""
    crop = re.sub(r'[<>:"/\\|?*]', "", str(row.get("CROPNAME") or row.get("CROPCODE") or "crop")).strip()
    return Path(crop) / {"1": "Central", "2": "State"}.get(str(row.get("SAMPLE", "")), "Sample")


def output_name(exptid: str, values: dict[str, str]) -> str:
    """Same style as the old software: P_EXPTID_<id>_<PRTID>_<date>.docx"""
    safe = re.sub(r'[<>:"/\\|?*]', "", values.get("PRTID", ""))
    return f"P_EXPTID_{exptid}_{safe}_{datetime.now():%d%b%Y}.docx"


def make_docx(ml_row: dict, blocks: dict[str, pd.DataFrame], out_dir: Path) -> Path:
    """The filled Word form of one Exp-ID (to view / edit in Word)."""
    values = values_for(ml_row, blocks)
    return fill_document(values, out_dir / crop_sample_folder(ml_row) / output_name(ml_row["EXPTID"], values))


def make_pdfs(ml: pd.DataFrame, grouped: dict[str, dict[str, pd.DataFrame]], exptids: list[str], out_dir: Path,
              progress=None, should_stop=None) -> list[tuple[str, Path | None, str]]:
    """Schedule 2.0 PDFs: fill the Word template, convert with Microsoft Word (one Word for the batch).

    grouped = {block table: {exptid: rows}}. Each PDF goes into out_dir/<CROP>/<Central|State>/.
    Returns (exptid, pdf or None, error) per Exp-ID. should_stop(): True ends the batch after the current one.
    """
    import tempfile

    import pythoncom
    import win32com.client

    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ml.drop_duplicates("EXPTID").set_index("EXPTID")
    results = []
    pythoncom.CoInitialize()          # needed in a background thread
    word = None
    try:
        try:
            word = win32com.client.DispatchEx("Word.Application")
        except Exception as e:
            raise RuntimeError("Microsoft Word is needed to make the PDF and could not be started "
                               f"on this PC ({e}).") from e
        word.Visible = False
        word.DisplayAlerts = 0
        with tempfile.TemporaryDirectory() as tmp:
            for i, exptid in enumerate(exptids, 1):
                if should_stop and should_stop():
                    break
                if progress:
                    progress(i, len(exptids), exptid)
                try:
                    if exptid not in rows.index:
                        raise ValueError("not in the master list")
                    row = {"EXPTID": exptid, **rows.loc[exptid].to_dict()}
                    blocks = {t: g[exptid] for t, g in grouped.items() if exptid in g}
                    values = values_for(row, blocks)
                    docx = fill_document(values, Path(tmp) / f"{exptid}.docx")
                    folder = out_dir / crop_sample_folder(row)
                    folder.mkdir(parents=True, exist_ok=True)
                    pdf = folder / Path(output_name(exptid, values)).with_suffix(".pdf")
                    doc = word.Documents.Open(str(docx), ReadOnly=True, AddToRecentFiles=False)
                    try:
                        doc.SaveAs2(str(pdf), FileFormat=17)        # 17 = PDF
                    finally:
                        doc.Close(False)
                    results.append((exptid, pdf, ""))
                except Exception as e:
                    results.append((exptid, None, str(e).splitlines()[0][:200]))
    finally:
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()
    return results
