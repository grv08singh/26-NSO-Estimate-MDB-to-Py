"""Start the app:  python app.py   (or double-click run_app.bat)."""
import sys

import bootstrap

bootstrap.setup()

from src.app.window import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
