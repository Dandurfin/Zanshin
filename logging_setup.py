"""Centralised logging to a file - solves points 1 and 3 of the code review:

  1. No top-level crash handler - main.py now writes every unhandled
     exception (also from mainloop) to crash.log in %APPDATA%, so alpha
     testers have something to send back when the app crashes/freezes.
  2. Too broad `except Exception: pass` - silently swallowed errors
     (saving settings, loading voices, tray icon...) now also go to the
     rotating app.log, not only to the UI log, which is lost after an app
     restart.

Usage in other modules:
    from logging_setup import get_logger
    log = get_logger(__name__)
    ...
    except Exception:
        log.exception("what failed")   # also writes the traceback

Log files:
  %APPDATA%\\Zanshin\\logs\\app.log     - rotating (5x 1 MB), normal operation
  %APPDATA%\\Zanshin\\logs\\crash.log   - unhandled exceptions (append, never deleted)
"""

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime

from paths import DATA_DIR

LOG_DIR = os.path.join(DATA_DIR, "logs")
APP_LOG_PATH = os.path.join(LOG_DIR, "app.log")
CRASH_LOG_PATH = os.path.join(LOG_DIR, "crash.log")

_configured = False


def _ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return True
    except Exception:
        return False


def _configure_root_logger():
    global _configured
    if _configured:
        return
    _configured = True
    root_logger = logging.getLogger("zanshin")
    root_logger.setLevel(logging.INFO)
    if not _ensure_log_dir():
        # If even creating the folder fails (e.g. no permissions), we at least
        # keep the logger working to stderr - the app itself must never crash
        # because of logging.
        handler = logging.StreamHandler(sys.stderr)
    else:
        try:
            handler = logging.handlers.RotatingFileHandler(
                APP_LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        except Exception:
            handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    root_logger.addHandler(handler)


def get_logger(name):
    """Returns the logger `zanshin.<name>`, writing to app.log. Safe to call
    from any module (the setup runs only once, statically)."""
    _configure_root_logger()
    return logging.getLogger(f"zanshin.{name}")


def log_crash(exc_type, exc_value, exc_tb):
    """Writes an unhandled exception to crash.log (append, never deleted -
    unlike the rotating app.log). Call from sys.excepthook or from a
    try/except around root.mainloop()."""
    _ensure_log_dir()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    entry = f"\n==== {stamp} ====\n{text}"
    try:
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        # If even the crash log cannot be written, we at least print it to the
        # console - we must never hide the original with another exception.
        print(entry, file=sys.stderr)
    try:
        get_logger("crash").critical("Neosetrena vynimka - detaily v crash.log:\n%s", text)
    except Exception:
        pass
