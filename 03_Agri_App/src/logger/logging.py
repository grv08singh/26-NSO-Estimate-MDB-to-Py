import sys
import logging
from pathlib import Path
from datetime import datetime

# Generate timestamped filename
LOG_FILE = f"{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.log"

# Anchor log directory to project root (2 levels up from src/logger)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_PATH = LOG_DIR / LOG_FILE

# Configure both file and console handlers
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

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
