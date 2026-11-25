"""Logging for the app and the pipelines — state-wise and year-wise like all data:

  03_logs/<STATE>/<YEAR>/<date>.log   everything done for that state + year (imports, modules), one file per day
  03_logs/app/<date>.log              what belongs to no single state + year (start-up, master list imports)

use_folder(state, year) switches the log file; use_folder() goes back to 03_logs/app/.
"""
import sys
import logging
import re
from pathlib import Path
from datetime import datetime

# Anchor log directory to project root (2 levels up from src/logger)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "03_logs"
FORMAT = "[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s"


def _file_for(state: str | None = None, year: str | None = None) -> Path:
    safe = lambda s: re.sub(r'[<>:"/\\|?*]', "", str(s)).strip()        # noqa: E731
    folder = LOG_DIR / safe(state.upper()) / safe(year) if state and year else LOG_DIR / "app"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{datetime.now():%Y-%m-%d}.log"


LOG_FILE_PATH = _file_for()
_file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")

logging.basicConfig(level=logging.INFO, format=FORMAT, handlers=[_file_handler, logging.StreamHandler(sys.stdout)])


def use_folder(state: str | None = None, year: str | None = None) -> Path:
    """Write the log to 03_logs/<STATE>/<YEAR>/<date>.log from now on (no state: 03_logs/app/<date>.log)."""
    global _file_handler, LOG_FILE_PATH
    path = _file_for(state, year)
    if Path(_file_handler.baseFilename) == path.resolve():
        return path
    root = logging.getLogger()
    new = logging.FileHandler(path, encoding="utf-8")
    new.setFormatter(logging.Formatter(FORMAT))
    root.removeHandler(_file_handler)
    _file_handler.close()
    root.addHandler(new)
    _file_handler, LOG_FILE_PATH = new, path
    return path


# Shared logger instance
logger = logging.getLogger("AgriApp")

# Re-export standard methods and levels so `from src.logger import logging` works seamlessly
info = logging.info
error = logging.error
warning = logging.warning
debug = logging.debug
critical = logging.critical
exception = logging.exception
log = logging.log
basicConfig = logging.basicConfig
getLogger = logging.getLogger

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
