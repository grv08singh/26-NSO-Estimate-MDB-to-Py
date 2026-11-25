"""States page (KrishiStat's 'Home: states', adapted): one card per state, for ONE agricultural year (chosen on the
welcome screen or in the top bar). A state has data for that year when its master list for the year is stored.
Importing a master list is done here, because it is once-a-year work.
"""
from __future__ import annotations

from src.utils import folders as F
import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import states
from .look import Kpi, button, chip, flow_box, label, restyle, wheat_pixmap
from .qt import QtWidgets, Qt, Signal


def stored_years(database: Path) -> Dict[str, dict]:
    """{state code: {"name": STATE, "years": [(year, experiments), …] newest first}} from the stored master lists."""
    out: Dict[str, dict] = {}
    for f in (database / F.MASTER_LIST).glob("*/*/info.json"):
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        code = str(info.get("state_code", "")).zfill(2)
        st = out.setdefault(code, {"name": info.get("state", f.parent.parent.name), "years": []})
        st["years"].append((info.get("year", f.parent.name), int(info.get("experiments", 0))))
    for st in out.values():
        st["years"].sort(reverse=True)
    return out


def all_years(database: Path) -> List[str]:
    """Every year with a stored master list in any state, newest first."""
    return sorted({y for st in stored_years(database).values() for y, _ in st["years"]}, reverse=True)


def current_agri_year(today: Optional[date] = None) -> str:
    """The agricultural year (July – June) of today: 24-11-2026 -> 2026-27, 10-03-2027 -> 2026-27."""
    d = today or date.today()
    first = d.year if d.month >= 7 else d.year - 1
    return f"{first}-{(first + 1) % 100:02d}"


def default_year(database: Path) -> str:
    """The current agricultural year when it has a master list, else the newest year that has one ('' if none)."""
    years = all_years(database)
    cur = current_agri_year()
    return cur if cur in years else (years[0] if years else "")


class StateCard(QtWidgets.QFrame):
    """One state for the chosen year: its code, name and experiments. Open = that state + year."""
    clicked = Signal(str, str, str)         # state name, state code, year

    def __init__(self, name: str, code: str) -> None:
        super().__init__()
        self.name, self.code_ = name, code
        self.has_data = False
        self.year = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(112)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        top = QtWidgets.QHBoxLayout()
        self.code = chip(f"Code {code}", "neutral")
        self.badge = chip("", "neutral")
        top.addWidget(self.code)
        top.addStretch(1)
        top.addWidget(self.badge)
        lay.addLayout(top)
        self.title = label(name, "h3", wrap=False)
        lay.addWidget(self.title)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.detail = label("", "muted")
        self.b_open = button("Open →", primary=True)
        self.b_open.clicked.connect(self._open)
        row.addWidget(self.detail, 1)
        row.addWidget(self.b_open)
        lay.addLayout(row)
        lay.addStretch(1)
        for w in (self.code, self.badge, self.title, self.detail):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_status(self, year: str, years: List[Tuple[str, int]]) -> None:
        """years = all stored (year, experiments) of this state; the card shows `year` only."""
        self.year = year
        n = dict(years).get(year)
        self.has_data = n is not None
        self.b_open.setVisible(self.has_data)
        others = [y for y, _ in years if y != year]
        if self.has_data:
            restyle(self, "stateCardOn")
            self.badge.setText("Master list")
            restyle(self.badge, "chip_green")
            self.detail.setText(f"{n:,} experiments")
            self.setToolTip(f"{self.name} {year}: Open")
        else:
            restyle(self, "stateCard")
            self.badge.setText("No data")
            restyle(self.badge, "chip_neutral")
            self.detail.setText(f"No master list for {year}" if year else "No master list yet")
            if others:
                self.detail.setText(self.detail.text() + f" · has {', '.join(others)}")
            self.setToolTip(f"{self.name}: import its {year} master list first" if year else
                            f"{self.name}: import its master list first")

    def _open(self) -> None:
        if self.has_data:
            self.clicked.emit(self.name, self.code_, self.year)

    def mouseReleaseEvent(self, e) -> None:            # a click on the card opens it
        if e.button() == Qt.MouseButton.LeftButton:
            self._open()


class StatesPage(QtWidgets.QWidget):
    state_chosen = Signal(str, str, str)       # state name, code, year
    import_clicked = Signal()

    def __init__(self, database: Path) -> None:
        super().__init__()
        self.setObjectName("page")
        self.database = database
        self.year = default_year(database)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(14)

        banner = QtWidgets.QFrame()
        banner.setObjectName("banner")
        bl = QtWidgets.QHBoxLayout(banner)
        bl.setContentsMargins(26, 20, 26, 20)
        bl.setSpacing(18)
        ic = QtWidgets.QLabel()
        ic.setPixmap(wheat_pixmap(84))
        bl.addWidget(ic)
        tl = QtWidgets.QVBoxLayout()
        tl.setSpacing(6)
        self.head = label("", "h1", wrap=True)
        tl.addWidget(self.head)
        sub = label("Choose a state. A state has data for the year once its master list is imported (once a year). "
                    "Change the year in the top bar.", "bannerSub")
        tl.addWidget(sub)
        bl.addLayout(tl, 1)
        b_imp = button("Import Master List…", icon="SP_DialogOpenButton",
                       tip="Pick the year's master list file(s); the state and year are read from the file")
        b_imp.setObjectName("light")
        b_imp.clicked.connect(self.import_clicked.emit)
        bl.addWidget(b_imp, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(banner)
        lay.addWidget(label("States", "h2"))

        bar_w, bar = flow_box(spacing=10)                  # wraps onto two lines on a narrow screen
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search state name or code …")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.only_data = QtWidgets.QCheckBox("Only states with data")
        bar.addWidget(self.search)
        bar.addWidget(self.only_data)
        self.kpi_states = Kpi("states with data", compact=True)
        self.kpi_exp = Kpi("experiments", compact=True)
        bar.addWidget(self.kpi_states)
        bar.addWidget(self.kpi_exp)
        lay.addWidget(bar_w)

        box = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(box)
        self.grid.setSpacing(12)
        self.grid.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        lay.addWidget(scroll, 1)

        self.cards: List[StateCard] = []
        self.search.textChanged.connect(self.relayout)
        self.only_data.toggled.connect(self.relayout)
        self.refresh()

    def set_year(self, year: str) -> None:
        self.year = year
        self.refresh()

    def refresh(self) -> None:
        data = stored_years(self.database)
        known = {str(c).zfill(2): n for n, c in states.STATES}
        for code, st in data.items():                      # a stored state that is not in the list
            known.setdefault(code, st["name"].title())
        if {c.code_ for c in self.cards} != set(known):
            for c in self.cards:
                c.setParent(None)
            self.cards = []
            for code, name in sorted(known.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999):
                card = StateCard(name, code)
                card.clicked.connect(self.state_chosen.emit)
                self.cards.append(card)
        n_exp = 0
        for c in self.cards:
            years = data.get(c.code_, {}).get("years", [])
            c.set_status(self.year, years)
            n_exp += dict(years).get(self.year, 0)
        self.head.setText(f"Crop Cutting Experiments · {self.year}" if self.year else "Crop Cutting Experiments")
        self.kpi_states.set(f"{sum(c.has_data for c in self.cards)} / {len(self.cards)}")
        self.kpi_exp.set(f"{n_exp:,}")
        self.relayout(force=True)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.relayout()

    def relayout(self, *_args, force: bool = False) -> None:
        cols = max(1, (self.width() - 64) // 250)
        q = self.search.text().strip().lower()
        show = [c for c in self.cards
                if (not q or q in c.name.lower() or q == c.code_ or q == c.code_.lstrip("0"))
                and (not self.only_data.isChecked() or c.has_data)]
        key = (cols, tuple(id(c) for c in show))
        if not force and key == getattr(self, "_key", None):
            return
        self._key = key
        for c in self.cards:
            self.grid.removeWidget(c)
            c.setVisible(c in show)
        for i, c in enumerate(show):
            self.grid.addWidget(c, i // cols, i % cols)
        for col in range(cols):
            self.grid.setColumnStretch(col, 1)
        self.grid.setRowStretch(len(show) // cols + 1, 1)
