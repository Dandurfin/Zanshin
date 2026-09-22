# -*- coding: utf-8 -*-
"""Nič sa nesmie pokaziť POTICHU. Neošetrené výnimky musia skončiť v
crash.log — aj z vlastných vlákien, aj z Tk callbackov.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    return open(os.path.join(ROOT, name), encoding="utf-8").read()


def test_vlaknove_vynimky_koncia_v_crash_logu():
    """B13: od Pythonu 3.8 idú výnimky z vlákien do `threading.excepthook`,
    NIE do `sys.excepthook`. Appka má ~20 vlákien; bez tohto by ich pád
    nezanechal v crash.log ani bajt (a v zabalenom builde ide stderr nikam)."""
    src = _read("main.py")
    assert "threading.excepthook" in src, (
        "main.py musí nastaviť threading.excepthook, inak pády vlákien miznú")
    assert "log_crash" in src


def test_tk_aj_hlavne_vlakno_maju_svoj_hook():
    src = _read("main.py")
    assert "report_callback_exception" in src   # Tk callbacky
    assert "sys.excepthook" in src              # hlavné vlákno / pred root-om


def test_zvukove_vlakno_prezije_zlyhanie_startu():
    """B14: `SpeechWorker.run` aplikoval uložený hlas/rýchlosť MIMO try —
    jedna COM chyba (odinštalovaný/poškodený SAPI hlas) zabila zvukové
    vlákno PRED slučkou a od tej chvíle nebolo počuť nič (TTS, SFX, hlášky),
    bez slova. Štart musí byť v try a padnúť späť na pyttsx3."""
    import ast
    src = _read("audio_engine.py")
    strom = ast.parse(src)
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.ClassDef) and uzol.name == "SpeechWorker":
            run = next(u for u in uzol.body
                       if isinstance(u, ast.FunctionDef) and u.name == "run")
            # prvý výkonný príkaz v run() musí byť Try, ktorý obalí štart
            prvy = run.body[0]
            assert isinstance(prvy, ast.Try), (
                "SpeechWorker.run musí začínať try okolo _init_sapi/_apply_*")
            telo = ast.get_source_segment(src, prvy)
            assert "_init_sapi" in telo, "try musí obaľovať init SAPI"
            return
    raise AssertionError("SpeechWorker.run sa nenašla")
