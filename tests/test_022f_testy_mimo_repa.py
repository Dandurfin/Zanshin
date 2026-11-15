# -*- coding: utf-8 -*-
"""Tests leave the repo-root data alone (0.3 batch 4b, tests/conftest.py).

When running from sources, the app's data are in the repo root
(`paths.data_dir`) and `logging_setup` wrote from tests into the same
logs/app.log as the live app. conftest.py redirects the paths to a temporary
folder before the first import of the app modules. The app itself does not
change: `paths.data_dir()` still returns the repo root when running from
sources.

The repo root is only read here (`os.stat`) - nothing in it is opened for
writing.
"""
import logging
import os
import tempfile

import app
import app_data
import app_prefs
import audio_engine
import logging_setup
import paths
import ui_dialogs

KOREN = os.path.normcase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _v_repe(cesta):
    cesta = os.path.normcase(os.path.abspath(cesta))
    return cesta == KOREN or cesta.startswith(KOREN + os.sep)


def test_appka_by_pisala_do_repa_testy_nie():
    # the app's behaviour has not changed
    assert os.path.normcase(paths.data_dir()) == KOREN
    # ...but the whole test run has its data in a temporary folder
    assert not _v_repe(paths.DATA_DIR)
    assert os.path.normcase(paths.DATA_DIR).startswith(
        os.path.normcase(os.path.abspath(tempfile.gettempdir())))


def test_moduly_appky_maju_presmerovane_cesty():
    for cesta in (paths.SETTINGS_PATH, paths.AUDIO_DIR, paths.TTS_CACHE_DIR,
                  app.DATA_DIR, app.AUDIO_DIR, app.TTS_CACHE_DIR,
                  app_data.DATA_DIR, app_prefs.SETTINGS_PATH,
                  audio_engine.TTS_CACHE_DIR, ui_dialogs.AUDIO_DIR,
                  logging_setup.LOG_DIR, logging_setup.APP_LOG_PATH,
                  logging_setup.CRASH_LOG_PATH):
        assert not _v_repe(cesta), cesta


def test_log_ide_do_docasneho_suboru_nie_do_repa():
    zanshin = logging.getLogger("zanshin")
    subory = [h.baseFilename for h in zanshin.handlers
              if isinstance(h, logging.FileHandler)]
    assert subory, "logger ma subor"
    assert not [s for s in subory if _v_repe(s)], subory
    zivy_log = os.path.join(KOREN, "logs", "app.log")
    pred = os.stat(zivy_log) if os.path.exists(zivy_log) else None
    logging_setup.get_logger("test_022f").info("riadok z testu (mimo repa)")
    for h in zanshin.handlers:
        h.flush()
    with open(logging_setup.APP_LOG_PATH, encoding="utf-8") as fh:
        assert "riadok z testu (mimo repa)" in fh.read()
    if pred is not None:
        po = os.stat(zivy_log)
        # the live app may write by itself; but this line is not there
        if (po.st_size, po.st_mtime_ns) != (pred.st_size, pred.st_mtime_ns):
            with open(zivy_log, "rb") as fh:
                fh.seek(pred.st_size)
                assert b"riadok z testu (mimo repa)" not in fh.read()
