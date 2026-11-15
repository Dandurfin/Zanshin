"""Shared setup for the whole test run (0.3 batch 4b).

WHY: when running from source the data folder is the repo root
(`paths.data_dir`), so `logging_setup` wrote from the tests into the same
logs/app.log as the player's live app - every test run added hundreds of
lines there ("svet prepnuty na work" (world switched to work), made-up
errors...). And a test that forgot to redirect saving the settings or the
history would write right next to the player's real data.

Pytest loads this file BEFORE every test module, so the paths are
redirected here to a temporary folder before any app module copies them
(`from paths import DATA_DIR`) and before `logging_setup` first creates the
log file. The app does not change: `paths.data_dir()` returns the same as
before, the tests only overwrite the values in the modules. `SOUNDS_DIR`
stays - when running from source those are the bundled sounds in assets/
(in git), not player data.

Tests that redirect the paths themselves (monkeypatch to `tmp_path`) work
the same as before - their redirect simply overrides this one.
"""
import atexit
import logging
import os
import shutil
import sys
import tempfile

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

# One temporary folder for the whole run (logs too). Not under the repo root.
TESTOVACIE_DATA = tempfile.mkdtemp(prefix="zanshin-testy-")

import paths  # noqa: E402

paths.DATA_DIR = TESTOVACIE_DATA
paths.SETTINGS_PATH = os.path.join(TESTOVACIE_DATA, "dandurf_settings.json")
paths.AUDIO_DIR = os.path.join(TESTOVACIE_DATA, "audio")
paths.TTS_CACHE_DIR = os.path.join(paths.AUDIO_DIR, "tts_cache")

import logging_setup  # noqa: E402

logging_setup.LOG_DIR = os.path.join(TESTOVACIE_DATA, "logs")
logging_setup.APP_LOG_PATH = os.path.join(logging_setup.LOG_DIR, "app.log")
logging_setup.CRASH_LOG_PATH = os.path.join(logging_setup.LOG_DIR, "crash.log")

if logging_setup._configured:
    # Someone has already set up the logger (should not happen - conftest goes
    # first). Its file may be in the repo, so the handler is closed and set up
    # again here.
    _zanshin = logging.getLogger("zanshin")
    for _h in list(_zanshin.handlers):
        _zanshin.removeHandler(_h)
        _h.close()
    logging_setup._configured = False


def _uprac():
    """After the run, closes the log file (Windows would not let it be deleted
    otherwise) and deletes the temporary folder. A cleanup error must not
    spoil the test result."""
    for _h in list(logging.getLogger("zanshin").handlers):
        try:
            _h.close()
        except Exception:
            pass
    shutil.rmtree(TESTOVACIE_DATA, ignore_errors=True)


atexit.register(_uprac)
