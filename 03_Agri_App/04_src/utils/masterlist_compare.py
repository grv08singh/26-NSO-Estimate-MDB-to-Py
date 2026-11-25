"""Compare a checked master list with what is stored for its state + year (shown before importing).

Rule: a new file replaces only the SEASONS it contains; every other stored season stays as it is.
So the comparison is made season by season, only for the new file's seasons, by Exp-ID.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.utils.masterlist_checks import COLUMN_NAMES, KEY

SHOW = [KEY, "SEASONNAME", "SAMPLENAME", "DISTRICT", "DISTRICTNAME", "SELORDER", "EXPT", "CROPCODE", "CROPNAME"]


@dataclass
class Comparison:
    new_year: bool                                   # nothing stored for this state + year yet
    by_season: pd.DataFrame                          # Season | Stored | In file | Added | Removed | Changed | After import
    added: pd.DataFrame = field(default_factory=pd.DataFrame)
    removed: pd.DataFrame = field(default_factory=pd.DataFrame)
    changed: pd.DataFrame = field(default_factory=pd.DataFrame)    # Exp-ID, Column, Old value, New value
    kept_seasons: list = field(default_factory=list)                # stored seasons the file does not touch
    removed_with_data: pd.DataFrame = field(default_factory=pd.DataFrame)   # removed ones that already have RC-7
    unchanged: bool = False                          # the file's seasons are exactly as stored

    @property
    def counts(self) -> dict:
        return {"added": len(self.added), "removed": len(self.removed),
                "changed": self.changed["Exp-ID"].nunique() if not self.changed.empty else 0}


def compare(new: pd.DataFrame, stored: pd.DataFrame, received_uids: set | None = None) -> Comparison:
    """new / stored: master list rows with EXPTID (stored may be empty). received_uids: UIDs that have RC-7."""
    seasons_new = sorted(new["SEASONCODE"].unique())
    names = pd.concat([new[["SEASONCODE", "SEASONNAME"]], stored.reindex(columns=["SEASONCODE", "SEASONNAME"])]) \
        .drop_duplicates("SEASONCODE").set_index("SEASONCODE")["SEASONNAME"]
    if stored.empty:
        rows = [{"Season": f"{names[s]} ({s})", "Stored": 0, "In file": int((new.SEASONCODE == s).sum()),
                 "Added": int((new.SEASONCODE == s).sum()), "Removed": 0, "Changed": 0,
                 "After import": int((new.SEASONCODE == s).sum())} for s in seasons_new]
        return Comparison(True, _total(pd.DataFrame(rows)), added=new[SHOW].reset_index(drop=True))

    old = stored[stored["SEASONCODE"].isin(seasons_new)]
    kept = sorted(set(stored["SEASONCODE"]) - set(seasons_new))
    o, n = old.set_index(KEY), new.set_index(KEY)
    added = new[~new[KEY].isin(o.index)]
    removed = old[~old[KEY].isin(n.index)]
    both = sorted(set(o.index) & set(n.index))
    cols = [c for c in COLUMN_NAMES if c in o.columns and c in n.columns]
    oo, nn = o.loc[both, cols].fillna(""), n.loc[both, cols].fillna("")
    diff = oo != nn
    ri, ci = diff.values.nonzero()
    changed = pd.DataFrame([{"Exp-ID": diff.index[r], "Column": diff.columns[c], "Old value": oo.iat[r, c],
                             "New value": nn.iat[r, c]} for r, c in zip(ri, ci)],
                           columns=["Exp-ID", "Column", "Old value", "New value"])
    changed_ids = set(changed["Exp-ID"])
    rows = []
    for s in sorted(set(seasons_new) | set(kept)):
        touched = s in seasons_new
        st = int((stored.SEASONCODE == s).sum())
        fi = int((new.SEASONCODE == s).sum()) if touched else 0
        rows.append({"Season": f"{names.get(s, s)} ({s})" + ("" if touched else "  – not in file, kept"),
                     "Stored": st, "In file": fi if touched else "",
                     "Added": int((added.SEASONCODE == s).sum()) if touched else "",
                     "Removed": int((removed.SEASONCODE == s).sum()) if touched else "",
                     "Changed": int(new[(new.SEASONCODE == s) & new[KEY].isin(changed_ids)].shape[0]) if touched else "",
                     "After import": fi if touched else st})
    rwd = removed[removed["UID"].isin(received_uids or set())] if "UID" in removed.columns else removed.iloc[0:0]
    cmp = Comparison(False, _total(pd.DataFrame(rows)), added[SHOW].reset_index(drop=True),
                     removed.reindex(columns=SHOW).reset_index(drop=True), changed, kept,
                     rwd.reindex(columns=SHOW).reset_index(drop=True))
    cmp.unchanged = not len(added) and not len(removed) and changed.empty
    return cmp


def _total(t: pd.DataFrame) -> pd.DataFrame:
    tot = {"Season": "TOTAL"}
    for c in t.columns[1:]:
        tot[c] = int(pd.to_numeric(t[c], errors="coerce").fillna(0).sum())
    return pd.concat([t, pd.DataFrame([tot])], ignore_index=True)
