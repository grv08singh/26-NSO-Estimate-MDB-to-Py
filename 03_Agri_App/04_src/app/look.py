# Look and feel copied from KrishiStat (dgces_app/ui.py): colours, style sheet, small widgets, tables,
# toast, wheat drawing and the front page. Only the imports and the front page's step names were changed.
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from typing import Callable, List, Optional, Tuple

from .qt import QtCore, QtGui, QtWidgets, Qt, Signal, run_exec

# Colours
C = {
    "bg": "#F1F6EE", "card": "#FFFFFF", "line": "#D5E2D0", "line2": "#E6EEE2", "text": "#1E2A1F",
    "muted": "#56685A", "dark": "#1F4D2B", "dark2": "#2E6B3C", "accent": "#2F7D3A", "accent2": "#1F5A28",
    "accent_bg": "#E2F0DD", "green": "#1D6B3A", "green_bg": "#DDF0E1", "orange": "#8A4A0B",
    "orange_bg": "#FCEBD3", "red": "#8A1C1C", "red_bg": "#FBE4E4", "hover": "#F2F8EF",
    "gold": "#D9A521", "head": "#EDF5E9",
}
ORANGE = QtGui.QColor("#FCE3C8")
YELLOW = QtGui.QColor("#FFF1C9")
ARROW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "arrow_down.svg").replace(os.sep, "/")

STYLE = f"""
* {{ font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 10pt; color: {C['text']}; }}
QMainWindow, QDialog, #page {{ background: {C['bg']}; }}
QToolBar {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #173D22, stop:0.6 {C['dark']}, stop:1 #3B7F46);
    border: none; padding: 6px 10px; spacing: 4px; }}
QToolBar QToolButton {{ color: white; font-weight: 600; padding: 7px 14px; border-radius: 6px; }}
QToolBar QToolButton:hover {{ background: rgba(255, 255, 255, 0.16); }}
QToolBar QLabel {{ color: white; background: transparent; }}
QStatusBar {{ background: {C['card']}; color: {C['muted']}; border-top: 1px solid {C['line']}; }}
QStatusBar QLabel {{ color: {C['muted']}; }}

#card, #stateCard, #stateCardOn, #kpi {{ background: {C['card']}; border: 1px solid {C['line']}; border-radius: 10px; }}
#stateCard:hover, #stateCardOn:hover {{ border: 1px solid {C['accent']}; background: {C['hover']}; }}
#stateCardOn {{ border: 2px solid {C['accent']}; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F1F8EC); }}
#banner {{ border-radius: 14px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1F4D2B, stop:0.55 #2F7D3A, stop:1 #8DBF5A); }}
#banner QLabel {{ background: transparent; color: white; }}
#bannerSub {{ color: #E4F2DC; }}
#flow {{ background: rgba(255, 255, 255, 0.18); color: white; border-radius: 12px; padding: 5px 12px; font-weight: 600; }}
#kpi QLabel {{ background: transparent; }}
#kpiValue {{ font-size: 18pt; font-weight: 700; }}
#kpiValueS {{ font-size: 13pt; font-weight: 700; }}
QToolButton#more {{ padding: 7px 12px; border: 1px solid #B5C7AF; border-radius: 6px; background: white; }}
QToolButton#more:hover {{ border-color: {C['accent']}; background: {C['hover']}; }}
QToolButton#more::menu-indicator {{ image: none; width: 0; }}
#kpiCaption {{ color: {C['muted']}; font-size: 9pt; }}

QLabel#h1 {{ font-size: 20pt; font-weight: 700; }}
QLabel#h2 {{ font-size: 13pt; font-weight: 700; }}
QLabel#h3 {{ font-size: 11pt; font-weight: 600; }}
QLabel#muted {{ color: {C['muted']}; }}
QLabel#step {{ background: {C['accent']}; color: white; border-radius: 12px; font-weight: 700;
               min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; qproperty-alignment: AlignCenter; }}
QLabel#chip_neutral {{ background: {C['bg']}; color: {C['muted']}; border-radius: 10px; padding: 3px 10px; }}
QLabel#chip_blue {{ background: {C['accent_bg']}; color: {C['accent2']}; border-radius: 10px; padding: 3px 10px; font-weight: 600; }}
QLabel#chip_green {{ background: {C['green_bg']}; color: {C['green']}; border-radius: 10px; padding: 3px 10px; font-weight: 600; }}
QLabel#chip_orange {{ background: {C['orange_bg']}; color: {C['orange']}; border-radius: 10px; padding: 3px 10px; font-weight: 600; }}
QLabel#chip_red {{ background: {C['red_bg']}; color: {C['red']}; border-radius: 10px; padding: 3px 10px; font-weight: 600; }}
QLabel#warn {{ background: {C['orange_bg']}; border: 1px solid #E8B884; color: {C['orange']}; padding: 10px 12px; border-radius: 8px; }}
QLabel#ok {{ background: {C['green_bg']}; color: {C['green']}; padding: 8px 12px; border-radius: 8px; font-weight: 600; }}
QLabel#bad {{ background: {C['red_bg']}; color: {C['red']}; padding: 10px 12px; border-radius: 8px; }}
QLabel#info {{ background: {C['accent_bg']}; color: {C['accent2']}; padding: 10px 12px; border-radius: 8px; }}
QLabel#toast {{ background: {C['dark']}; border-left: 4px solid {C['gold']}; color: white; padding: 12px 18px; border-radius: 8px; font-weight: 600; }}

QPushButton {{ padding: 7px 14px; border: 1px solid #B5C7AF; border-radius: 6px; background: white; min-height: 18px; }}
QPushButton:hover {{ border-color: {C['accent']}; background: {C['hover']}; }}
QPushButton:pressed {{ background: {C['accent_bg']}; }}
QPushButton:checked {{ background: {C['accent_bg']}; border: 1px solid {C['accent']}; color: {C['accent2']}; }}
QPushButton:disabled {{ color: #9AAA9C; border-color: {C['line']}; background: #F5F8F3; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3A8C45, stop:1 {C['accent']});
    color: white; border: 1px solid {C['accent2']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {C['accent2']}; }}
QPushButton#primary:disabled {{ background: #A9BBA4; border-color: #A9BBA4; color: white; }}
QPushButton#final {{ border: 1px solid #E8B884; color: {C['orange']}; font-weight: 600; }}
QPushButton#final:checked {{ background: {C['green_bg']}; border: 1px solid #7DB491; color: {C['green']}; }}
QPushButton#light {{ background: white; color: {C['accent2']}; border: none; border-radius: 8px;
    padding: 10px 20px; font-weight: 700; }}
QPushButton#light:hover {{ background: #F3FAEF; }}
QPushButton#link {{ border: none; background: transparent; color: {C['accent']}; font-weight: 600; padding: 4px 6px; }}
QPushButton#link:hover {{ text-decoration: underline; }}

QLineEdit, QComboBox {{ padding: 6px 10px; border: 1px solid #B5C7AF; border-radius: 6px; background: white; min-height: 18px; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {C['accent']}; }}
QComboBox:disabled {{ background: #F1F5EF; color: {C['muted']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{ARROW}"); width: 12px; height: 8px; }}
QCheckBox, QRadioButton {{ spacing: 8px; padding: 4px; }}

QTreeWidget {{ background: white; border: none; outline: 0; show-decoration-selected: 0; }}
QTreeWidget::branch:selected {{ background: transparent; }}
QTreeWidget::item {{ padding: 6px 4px; border-radius: 4px; }}
QTreeWidget::item:hover {{ background: {C['hover']}; }}
QTreeWidget::item:selected {{ background: {C['accent_bg']}; color: {C['accent2']}; }}
QTableView, QTableWidget {{ background: white; border: 1px solid {C['line']}; border-radius: 8px;
    gridline-color: {C['line2']}; selection-background-color: {C['accent_bg']}; selection-color: {C['text']};
    alternate-background-color: #F8FBF6; }}
QHeaderView::section {{ background: {C['head']}; padding: 6px 8px; border: none; border-right: 1px solid {C['line2']};
    border-bottom: 1px solid {C['line']}; font-weight: 600; color: {C['text']}; }}
QHeaderView::section:hover {{ background: {C['accent_bg']}; }}
QTableCornerButton::section {{ background: {C['head']}; border: none; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; margin-right: 4px; border: none;
    border-bottom: 3px solid transparent; color: {C['muted']}; }}
QTabBar::tab:hover {{ color: {C['accent2']}; }}
QTabBar::tab:selected {{ color: {C['accent2']}; border-bottom: 3px solid {C['accent']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #BCD0B5; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #BCD0B5; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle {{ background: {C['bg']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{ background: {C['dark']}; color: white; border: none; padding: 6px; }}

#front QLabel {{ color: white; background: transparent; }}
#frontName {{ font-size: 46pt; font-weight: 800; }}
#frontSub {{ font-size: 15pt; color: #E2F3E4; }}
#frontFoot {{ font-size: 9.5pt; color: #EAF5EB; }}
#logoBox {{ background: white; border-radius: 14px; }}
#wheatRing {{ background: rgba(255, 255, 255, 0.12); border: 2px solid #EBC254; border-radius: 42px; }}
#frontSep {{ background: rgba(255, 255, 255, 0.4); }}
QPushButton#startBtn {{ background: #E9B83C; color: #1F2A12; border: none; border-radius: 14px;
    font-size: 16pt; font-weight: 700; padding: 12px 48px; }}
QPushButton#startBtn:hover {{ background: #F2C55A; }}
QPushButton#startBtn:pressed {{ background: #D9A521; }}
QListWidget#moduleNav {{ background: transparent; border: none; outline: 0; }}
QListWidget#moduleNav::item {{ padding: 10px 10px; margin: 2px 0; border-radius: 8px; font-size: 10.5pt; }}
QListWidget#moduleNav::item:hover {{ background: {C['hover']}; }}
QListWidget#moduleNav::item:selected {{ background: {C['accent_bg']}; color: {C['accent2']}; font-weight: 700;
    border-left: 4px solid {C['accent']}; }}
QComboBox#barYear {{ background: rgba(255, 255, 255, 0.95); color: #1F4D2B; border: 1px solid #EBC254;
    border-radius: 6px; font-weight: 700; padding: 4px 10px; min-width: 90px; }}
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def busy(fn: Callable[[], object]):
    QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return fn()
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def error_box(parent, title: str, exc: BaseException) -> None:
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(str(exc))
    box.setDetailedText(traceback.format_exc())
    run_exec(box)


# Open a folder
def open_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)                       # noqa: S606 (Windows only)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def label(text: str = "", name: str = "", wrap: bool = True) -> QtWidgets.QLabel:
    lb = QtWidgets.QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


# Apply a style class
def restyle(w: QtWidgets.QWidget, name: str) -> None:
    w.setObjectName(name)
    w.style().unpolish(w)
    w.style().polish(w)


def chip(text: str, kind: str = "neutral") -> QtWidgets.QLabel:
    lb = QtWidgets.QLabel(text)
    lb.setObjectName(f"chip_{kind}")
    return lb


def button(text: str, primary: bool = False, icon: Optional[str] = None, tip: str = "") -> QtWidgets.QPushButton:
    b = QtWidgets.QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if icon:
        b.setIcon(std_icon(icon))
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def std_icon(name: str) -> QtGui.QIcon:
    sp = getattr(QtWidgets.QStyle.StandardPixmap, name)
    return QtWidgets.QApplication.style().standardIcon(sp)


# Draw a wheat ear
def wheat_pixmap(size: int = 64, grain: Optional[str] = None, stem: str = "#F3E3A6",
                 leaf: str = "#8DBF5A") -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    k = size / 64.0
    P, R = QtCore.QPointF, QtCore.QRectF
    p.setPen(QtGui.QPen(QtGui.QColor(stem), 2.6 * k))
    p.drawLine(P(32 * k, 62 * k), P(32 * k, 12 * k))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(leaf))
    for side in (-1, 1):  # leaves
        path = QtGui.QPainterPath(P(32 * k, 58 * k))
        path.quadTo(P((32 + side * 20) * k, 52 * k), P((32 + side * 22) * k, 38 * k))
        path.quadTo(P((32 + side * 8) * k, 46 * k), P(32 * k, 58 * k))
        p.drawPath(path)
    p.setBrush(QtGui.QColor(grain or C["gold"]))
    for i in range(5):  # grains
        y = (20 + i * 7.5) * k
        for side in (-1, 1):
            p.save()
            p.translate(32 * k + side * 5 * k, y)
            p.rotate(side * 32)
            p.drawEllipse(R(-3.6 * k, -7 * k, 7.2 * k, 14 * k))
            p.restore()
    p.drawEllipse(R(28.4 * k, 2 * k, 7.2 * k, 14 * k))
    p.end()
    return pm


def card(margin: int = 16, spacing: int = 10) -> Tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    f = QtWidgets.QFrame()
    f.setObjectName("card")
    lay = QtWidgets.QVBoxLayout(f)
    lay.setContentsMargins(margin, margin, margin, margin)
    lay.setSpacing(spacing)
    return f, lay


class FlowLayout(QtWidgets.QLayout):
    """Puts widgets in a row and wraps them onto the next line when the width runs out (any screen size).
    right=True keeps each line right-aligned (for buttons on the right)."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, spacing: int = 6, right: bool = False) -> None:
        super().__init__(parent)
        self._items: List[QtWidgets.QLayoutItem] = []
        self._sp, self._right = spacing, right
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def insertWidget(self, index: int, w: QtWidgets.QWidget) -> None:
        self.addChildWidget(w)
        self._items.insert(max(0, min(index, len(self._items))), QtWidgets.QWidgetItem(w))
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QtCore.QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._place(rect, move=True)

    def _shown(self) -> list:
        return [it for it in self._items if not it.isEmpty()]

    def sizeHint(self) -> QtCore.QSize:
        items = self._shown()
        m = self.contentsMargins()
        if not items:
            return QtCore.QSize(0, 0)
        w = sum(it.sizeHint().width() for it in items) + self._sp * (len(items) - 1)
        h = max(it.sizeHint().height() for it in items)
        return QtCore.QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

    def minimumSize(self) -> QtCore.QSize:
        s = QtCore.QSize(0, 0)
        for it in self._shown():
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, rect, move: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        lines, line, used = [], [], 0
        for it in self._shown():
            w = it.sizeHint().width()
            if line and used + self._sp + w > r.width():
                lines.append(line)
                line, used = [], 0
            used += (self._sp if line else 0) + w
            line.append(it)
        if line:
            lines.append(line)
        y = r.y()
        for ln in lines:
            h = max(it.sizeHint().height() for it in ln)
            width = sum(min(it.sizeHint().width(), r.width()) for it in ln) + self._sp * (len(ln) - 1)
            x = r.x() + (max(0, r.width() - width) if self._right else 0)
            for it in ln:
                w = min(it.sizeHint().width(), r.width())
                if move:
                    it.setGeometry(QtCore.QRect(x, y + (h - it.sizeHint().height()) // 2, w, it.sizeHint().height()))
                x += w + self._sp
            y += h + self._sp
        return max(0, y - self._sp - r.y()) + m.top() + m.bottom()


def fit_columns(view: QtWidgets.QTableView, rows: int = 150) -> None:
    """Columns as wide as their text, measured on the first `rows` rows only (Qt measures every cell otherwise:
    seconds on a table of a few thousand rows)."""
    view.horizontalHeader().setResizeContentsPrecision(rows)
    view.resizeColumnsToContents()


def flow_box(right: bool = False, spacing: int = 6) -> Tuple[QtWidgets.QWidget, "FlowLayout"]:
    """A widget whose children wrap onto more lines when narrow."""
    w = QtWidgets.QWidget()
    lay = FlowLayout(w, spacing, right)
    return w, lay


def fit_to_screen(w: QtWidgets.QWidget, width: int, height: int, share: float = 0.92) -> None:
    """Resize to width x height, but never larger than the screen the widget is on."""
    scr = (w.screen() if hasattr(w, "screen") and w.screen() else QtGui.QGuiApplication.primaryScreen())
    g = scr.availableGeometry()
    w.resize(min(width, int(g.width() * share)), min(height, int(g.height() * share)))


def clear_layout(lay: QtWidgets.QLayout) -> None:
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            clear_layout(it.layout())


# Summary card
class Kpi(QtWidgets.QFrame):

    COMPACT_SIZE = (128, 60)          # every compact count box the same size, so a row of them lines up

    def __init__(self, caption: str, compact: bool = False) -> None:
        super().__init__()
        self.setObjectName("kpi")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(*((10, 4, 8, 4) if compact else (16, 10, 16, 10)))
        lay.setSpacing(0)
        self.value = label("–", "kpiValueS" if compact else "kpiValue", wrap=False)
        self.caption = label(caption, "kpiCaption", wrap=compact)
        lay.addWidget(self.value)
        lay.addWidget(self.caption)
        if compact:
            self.setFixedSize(*self.COMPACT_SIZE)
            lay.addStretch(1)

    def set(self, value: str, color: Optional[str] = None) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class AutoLabel(QtWidgets.QLabel):
    """A label that takes no room while it is empty (status lines that only say something now and then)."""

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setVisible(bool(text))


# ---------------------------------------------------------------------------
# Table model + sortable proxy for raw sheets and RC7
# ---------------------------------------------------------------------------
class TableModel(QtCore.QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.headers: List[str] = []
        self.rows: List[List[str]] = []
        self.bg: Optional[Callable[[int, int], Optional[QtGui.QColor]]] = None

    def set(self, headers: List[str], rows: List[List[str]],
            bg: Optional[Callable[[int, int], Optional[QtGui.QColor]]] = None) -> None:
        self.beginResetModel()
        self.headers, self.rows, self.bg = headers, rows, bg
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self.rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.BackgroundRole and self.bg:
            return self.bg(index.row(), index.column())
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section] if section < len(self.headers) else None
        return str(section + 1)


# Sort numbers as numbers
class SortProxy(QtCore.QSortFilterProxyModel):

    def lessThan(self, left, right):
        rows = self.sourceModel().rows
        a, b = rows[left.row()][left.column()], rows[right.row()][right.column()]
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return str(a) < str(b)


class Table(QtWidgets.QTableView):
    def __init__(self, col_width: int = 110) -> None:
        super().__init__()
        self.src = TableModel()
        self.proxy = SortProxy()
        self.proxy.setSourceModel(self.src)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setDefaultSectionSize(col_width)
        self.horizontalHeader().setHighlightSections(False)
        self.verticalHeader().setDefaultSectionSize(26)
        self.setShowGrid(True)

    def set(self, headers, rows, bg=None) -> None:
        self.src.set(headers, rows, bg)

    def source_row(self) -> Optional[int]:
        idx = self.currentIndex()
        if not idx.isValid():
            return None
        return self.proxy.mapToSource(idx).row()

    def select_source_row(self, r: int) -> None:
        idx = self.proxy.mapFromSource(self.src.index(r, 0))
        if idx.isValid():
            self.selectRow(idx.row())
            self.scrollTo(idx, QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter)


# ---------------------------------------------------------------------------
# Toast message
# ---------------------------------------------------------------------------
class Toast(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWordWrap(True)
        self.hide()
        self.effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QtCore.QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.finished.connect(self._done)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade)

    def show_msg(self, text: str, ms: int = 4500) -> None:
        self.setText(text)
        self.setMaximumWidth(520)
        self.adjustSize()
        p = self.parentWidget()
        self.move(p.width() - self.width() - 24, p.height() - self.height() - 44)
        self.anim.stop()
        self.effect.setOpacity(1.0)
        self.show()
        self.raise_()
        self.timer.start(ms)

    def _fade(self) -> None:
        self.anim.setDuration(500)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _done(self) -> None:
        if self.effect.opacity() == 0.0:
            self.hide()


def toast(widget: QtWidgets.QWidget, text: str) -> None:
    win = widget.window()
    t = getattr(win, "toast", None)
    if t is not None:
        t.show_msg(text)



# ---------------------------------------------------------------------------
# Front page
# ---------------------------------------------------------------------------
APP_NAME = "KrishiStat"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


# App version from version.txt
def app_version() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    places = [os.path.join(getattr(sys, "_MEIPASS", here), "version.txt"),
              os.path.join(here, "..", "version.txt"),
              os.path.join(here, "..", "windows", "version.txt")]
    for p in places:
        try:
            with open(p, encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except OSError:
            continue
    return ""


# Step line on the front page
class StepLine(QtWidgets.QWidget):
    STEPS = ("Master List", "Schedules", "RC-7 Match", "Correction", "Control Reg.", "Estimate", "Annexure", "Charts")

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(960, 86)

    def paintEvent(self, _e) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        n, w, r = len(self.STEPS), self.width(), 22
        xs = [w * (2 * i + 1) / (2 * n) for i in range(n)]
        g = QtGui.QLinearGradient(xs[0], 0, xs[-1], 0)
        g.setColorAt(0, QtGui.QColor("#EBC254"))
        g.setColorAt(1, QtGui.QColor(235, 194, 84, 90))
        p.setPen(QtGui.QPen(QtGui.QBrush(g), 2))
        p.drawLine(QtCore.QPointF(xs[0], r + 1), QtCore.QPointF(xs[-1], r + 1))
        num = QtGui.QFont(self.font())
        num.setPointSizeF(12)
        num.setBold(True)
        txt = QtGui.QFont(self.font())
        txt.setPointSizeF(10)
        txt.setWeight(QtGui.QFont.Weight.DemiBold if hasattr(QtGui.QFont, "Weight") else 63)
        for i, (x, name) in enumerate(zip(xs, self.STEPS)):
            p.setPen(QtGui.QPen(QtGui.QColor("#EBC254"), 2))
            p.setBrush(QtGui.QColor("#22562D"))
            p.drawEllipse(QtCore.QPointF(x, r + 1), r, r)
            p.setFont(num)
            p.setPen(QtGui.QColor("#FAD978"))
            p.drawText(QtCore.QRectF(x - r, 1, 2 * r, 2 * r), int(Qt.AlignmentFlag.AlignCenter), str(i + 1))
            p.setFont(txt)
            p.setPen(QtGui.QColor("#FFFFFF"))
            p.drawText(QtCore.QRectF(x - 60, 2 * r + 10, 120, 26), int(Qt.AlignmentFlag.AlignCenter), name)
        p.end()


class FrontPage(QtWidgets.QWidget):
    """Welcome screen: logos, name and Start - nothing else (the year is chosen in the top bar)."""
    start = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("front")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(60, 40, 60, 40)  # space for the border
        lay.setSpacing(0)
        lay.addStretch(3)

        logos = QtWidgets.QHBoxLayout()
        logos.setSpacing(18)
        logos.addStretch(1)
        box = QtWidgets.QFrame()
        box.setObjectName("logoBox")
        bl = QtWidgets.QHBoxLayout(box)
        bl.setContentsMargins(6, 6, 6, 6)
        img = QtWidgets.QLabel()
        pm = QtGui.QPixmap(os.path.join(ASSETS, "nso_logo.png"))
        if not pm.isNull():
            img.setPixmap(pm.scaledToHeight(84, Qt.TransformationMode.SmoothTransformation))
            bl.addWidget(img)
            logos.addWidget(box)
            sep = QtWidgets.QFrame()
            sep.setObjectName("frontSep")
            sep.setFixedSize(1, 64)
            logos.addWidget(sep)
        ring = QtWidgets.QLabel()
        ring.setObjectName("wheatRing")
        ring.setFixedSize(84, 84)
        ring.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring.setPixmap(wheat_pixmap(52, grain="#F3C94B"))
        logos.addWidget(ring)
        logos.addStretch(1)
        lay.addLayout(logos)
        lay.addSpacing(26)

        name = QtWidgets.QLabel(APP_NAME)
        name.setObjectName("frontName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(name)
        sub = QtWidgets.QLabel("Crop Cutting Experiment · Data Processing")
        sub.setObjectName("frontSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(40)
        brow = QtWidgets.QHBoxLayout()
        brow.addStretch(1)
        self.b_start = QtWidgets.QPushButton("Start  →")
        self.b_start.setObjectName("startBtn")
        self.b_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_start.setShortcut(QtGui.QKeySequence(Qt.Key.Key_Return))
        self.b_start.clicked.connect(self.start.emit)
        brow.addWidget(self.b_start)
        brow.addStretch(1)
        lay.addLayout(brow)
        lay.addStretch(4)

        foot = QtWidgets.QHBoxLayout()
        ver = app_version()
        left = QtWidgets.QLabel(f"Version {ver}" if ver else "")
        right = QtWidgets.QLabel("Schedule AS 2.0 · Record Type 7")
        for w in (left, right):
            w.setObjectName("frontFoot")
        foot.addWidget(left)
        foot.addStretch(1)
        foot.addWidget(right)
        lay.addLayout(foot)

    def paintEvent(self, _e) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        g = QtGui.QLinearGradient(0, 0, w * 0.45, h)
        g.setColorAt(0.0, QtGui.QColor("#2E7139"))
        g.setColorAt(0.55, QtGui.QColor("#3F8C4A"))
        g.setColorAt(1.0, QtGui.QColor("#56A862"))
        p.fillRect(self.rect(), g)
        glow = QtGui.QRadialGradient(w / 2, -h * 0.1, max(w, h) * 0.55)
        glow.setColorAt(0, QtGui.QColor(120, 196, 133, 170))
        glow.setColorAt(1, QtGui.QColor(120, 196, 133, 0))
        p.fillRect(self.rect(), glow)
        base = h - 260 * min(1.0, h / 800)
        k = (h - base) / 260

        def wave(y0, pts, color):
            path = QtGui.QPainterPath(QtCore.QPointF(0, base + y0 * k))
            for (c1x, c1y, c2x, c2y, ex, ey) in pts:
                path.cubicTo(c1x * w, base + c1y * k, c2x * w, base + c2y * k, ex * w, base + ey * k)
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()
            p.fillPath(path, color)

        wave(150, [(0.19, 110, 0.36, 190, 0.55, 140), (0.74, 90, 0.86, 110, 1.0, 155)], QtGui.QColor(255, 255, 255, 20))
        wave(210, [(0.20, 180, 0.41, 245, 0.59, 205), (0.77, 165, 0.88, 185, 1.0, 215)], QtGui.QColor(224, 174, 42, 52))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 46), 1))
        p.drawLine(QtCore.QPointF(60, h - 68), QtCore.QPointF(w - 60, h - 68))
        self._glow_border(p, w, h)
        p.end()

    # Draw the page border
    @staticmethod
    def _glow_border(p: QtGui.QPainter, w: float, h: float) -> None:
        steps = 40
        for i in range(steps):  # green edge shade
            a = int(200 * (1 - i / steps) ** 1.8)
            g = QtGui.QLinearGradient(0, 0, w, h)
            for pos, col in ((0.0, "#163D20"), (0.5, "#1F4D2B"), (1.0, "#163D20")):
                c = QtGui.QColor(col)
                c.setAlpha(a)
                g.setColorAt(pos, c)
            p.setPen(QtGui.QPen(QtGui.QBrush(g), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QtCore.QRectF(i + 0.5, i + 0.5, w - 2 * i - 1, h - 2 * i - 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for inset, width, alpha, radius in ((14, 2.0, 235, 16), (22, 1.2, 190, 12)):
            rect = QtCore.QRectF(inset, inset, w - 2 * inset, h - 2 * inset)
            c = QtGui.QColor("#F3C94B")  # gold line
            c.setAlpha(alpha)
            p.setPen(QtGui.QPen(c, width))
            p.drawRoundedRect(rect, radius, radius)

