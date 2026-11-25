# Qt import (PySide6 or PyQt5)
try:
    from PySide6 import QtCore, QtGui, QtWidgets   # noqa: F401
    Signal = QtCore.Signal
    API = "PySide6"
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets     # noqa: F401
    Signal = QtCore.pyqtSignal
    API = "PyQt5"

Qt = QtCore.Qt


# Run a dialog or the app
def run_exec(obj):
    fn = getattr(obj, "exec_", None) or getattr(obj, "exec")
    return fn()
