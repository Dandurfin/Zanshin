# -*- coding: utf-8 -*-
"""Nothing may break SILENTLY. Unhandled exceptions must end up in
crash.log — from our own threads as well as from Tk callbacks.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    return open(os.path.join(ROOT, name), encoding="utf-8").read()


def test_vlaknove_vynimky_koncia_v_crash_logu():
    """B13: since Python 3.8 exceptions from threads go to
    `threading.excepthook`, NOT to `sys.excepthook`. The app has ~20 threads;
    without this their crash would not leave a single byte in crash.log (and in
    the packaged build stderr goes nowhere)."""
    src = _read("main.py")
    assert "threading.excepthook" in src, (
        "main.py musí nastaviť threading.excepthook, inak pády vlákien miznú")
    assert "log_crash" in src


def test_tk_aj_hlavne_vlakno_maju_svoj_hook():
    src = _read("main.py")
    assert "report_callback_exception" in src   # Tk callbacks
    assert "sys.excepthook" in src              # main thread / before root


def test_zvukove_vlakno_prezije_zlyhanie_startu():
    """B14: `SpeechWorker.run` applied the saved voice/rate OUTSIDE the try —
    one COM error (an uninstalled/broken SAPI voice) killed the sound thread
    BEFORE the loop and from then on nothing was heard (TTS, SFX, cues),
    without a word. The start must be in a try and fall back to pyttsx3."""
    import ast
    src = _read("audio_engine.py")
    strom = ast.parse(src)
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.ClassDef) and uzol.name == "SpeechWorker":
            run = next(u for u in uzol.body
                       if isinstance(u, ast.FunctionDef) and u.name == "run")
            # the first executable statement in run() must be a Try that wraps
            # the start
            prvy = run.body[0]
            assert isinstance(prvy, ast.Try), (
                "SpeechWorker.run musí začínať try okolo _init_sapi/_apply_*")
            telo = ast.get_source_segment(src, prvy)
            assert "_init_sapi" in telo, "try musí obaľovať init SAPI"
            return
    raise AssertionError("SpeechWorker.run sa nenašla")
