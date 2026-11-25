"""Make the code folder 04_src importable as `src` (a Python name cannot start with a digit).

Every module imports `src.…` (e.g. `from src.logger import logging`); this maps `src` to the 04_src folder.
Used by app.py and run_step.py; run from the 03_Agri_App folder (they change to it themselves).
"""
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CODE = "04_src"


def setup() -> str:
    os.chdir(ROOT)                                   # every path in config.yaml is relative to 03_Agri_App
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    if "src" not in sys.modules:
        sys.modules["src"] = importlib.import_module(CODE)
    return ROOT
