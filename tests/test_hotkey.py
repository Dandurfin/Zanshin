# -*- coding: utf-8 -*-
"""Global "not now" key (spec §1.9).

The tests cover reading combinations and how `RegisterHotKey` differs from
the hook that phase 3 removed. The registration itself needs Windows and
so runs only where it is available — the rest is pure logic and passes
everywhere.
"""
import ast
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hotkey  # noqa: E402
from _zdroj_appky import strom_appky  # noqa: E402


# --------------------------------------------------------------------------
# Reading combinations
# --------------------------------------------------------------------------

def test_zakladna_kombinacia():
    mody, vk = hotkey.parse_combo("ctrl+alt+z")
    assert mody & hotkey.MOD_CONTROL
    assert mody & hotkey.MOD_ALT
    assert vk == 0x5A


def test_poradie_nerozhoduje():
    assert hotkey.parse_combo("alt+ctrl+z") == hotkey.parse_combo("ctrl+alt+z")


def test_velke_pismena_a_medzery():
    assert hotkey.parse_combo("  CTRL + Alt + Z ") == hotkey.parse_combo("ctrl+alt+z")


def test_norepeat_je_vzdy():
    """Without MOD_NOREPEAT, holding the key generates a flood of messages
    and "not now" would switch on and off ten times a second."""
    for combo in ("ctrl+alt+z", "shift+f9", "win+space"):
        mody, _vk = hotkey.parse_combo(combo)
        assert mody & hotkey.MOD_NOREPEAT, combo


def test_holy_klaves_sa_odmietne():
    """A bare key as a global hotkey would take a letter away from the
    player in every game and every chat — and they would have no idea
    why."""
    with pytest.raises(hotkey.BadCombo):
        hotkey.parse_combo("z")
    with pytest.raises(hotkey.BadCombo):
        hotkey.parse_combo("f9")


@pytest.mark.parametrize("zly", ["", "   ", "ctrl", "ctrl+a+b", "ctrl+nieco",
                                 "+", None])
def test_nezmysly_sa_odmietnu(zly):
    with pytest.raises(hotkey.BadCombo):
        hotkey.parse_combo(zly)
    assert hotkey.is_valid(zly) is False


def test_format_pre_rozhranie():
    assert hotkey.format_combo("ctrl+alt+z") == "Ctrl + Alt + Z"
    assert hotkey.format_combo("shift+f9") == "Shift + F9"
    assert hotkey.format_combo("nezmysel") == ""


# --------------------------------------------------------------------------
# How it differs from a hook
# --------------------------------------------------------------------------

def _zdroj(meno):
    cesta = os.path.join(os.path.dirname(__file__), "..", meno)
    return io.open(cesta, encoding="utf-8-sig").read()


def test_modul_nesiaha_na_hooky():
    """That is the whole reason for `RegisterHotKey` and not `pynput`.

    A hook sees EVERY key pressed and from the outside cannot be told apart
    from a keylogger. A hotkey tells Windows one combination and gets
    nothing else.
    """
    src = _zdroj("hotkey.py")
    strom = ast.parse(src)
    telo = "\n".join(ast.unparse(u) for u in strom.body
                     if not (isinstance(u, ast.Expr)
                             and isinstance(u.value, ast.Constant)))
    for zakazane in ("SetWindowsHookEx", "WH_KEYBOARD", "pynput",
                     "GetAsyncKeyState", "GetKeyboardState"):
        assert zakazane not in telo, f"hotkey.py siaha na {zakazane}"


def test_appka_neimportuje_pynput():
    """A guard against a comeback. The AST is read, not the raw text — the
    docstring explains why pynput is NOT there, and the test used to fail
    on that."""
    strom = strom_appky()
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.Import):
            for meno in uzol.names:
                assert "pynput" not in meno.name
        elif isinstance(uzol, ast.ImportFrom):
            assert "pynput" not in (uzol.module or "")


def test_import_nepadne_bez_win32():
    """The module must be importable even where there is no user32 —
    otherwise the import of the whole app would fail. The same discipline
    as `activity.py`."""
    assert isinstance(hotkey.AVAILABLE, bool)


# --------------------------------------------------------------------------
# Wiring into the app
# --------------------------------------------------------------------------

def _telo(meno_suboru, meno_funkcie):
    # "app.py" = the whole app: app.py and the DandurfApp mixins in app_*.py
    if meno_suboru == "app.py":
        strom = strom_appky()
    else:
        strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno_funkcie:
            telo = uzol.body
            if (telo and isinstance(telo[0], ast.Expr)
                    and isinstance(telo[0].value, ast.Constant)
                    and isinstance(telo[0].value.value, str)):
                telo = telo[1:]
            return "\n".join(ast.unparse(p) for p in telo)
    raise AssertionError(f"{meno_funkcie} sa v {meno_suboru} nenašla")


def test_stlacenie_ide_cez_ui_call():
    """The callback runs on `hotkey.py`'s own thread. `HeartStats`,
    `ActivityTracker` and `overlay_manager` are Tk-thread-only, so touching
    them directly from there would be a silent bug."""
    telo = _telo("app.py", "_on_snooze_hotkey")
    assert "ui_call" in telo, "stlačenie sa musí preniesť do Tk cez ui_call"


def test_skratka_je_prepinac():
    """A second press silently cancels. Making the player wait half an hour
    for something they switched on by mistake would be worse than the cues
    themselves."""
    telo = _telo("app.py", "_toggle_snooze_from_hotkey")
    assert "_cancel_snooze" in telo and "_start_snooze" in telo


def test_skratka_prezije_zastavenie_pocuvania():
    """The "not now" key must work even when the app is not listening right
    now, and even when it is minimised to the tray. It is switched off only
    on a real quit."""
    assert "stop_snooze_hotkey" not in _telo("app.py", "stop_listening")
    assert "stop_snooze_hotkey" not in _telo("app.py", "on_close")
    assert "stop_snooze_hotkey" in _telo("app.py", "_quit")


def test_zlyhana_registracia_nezhodi_appku():
    """Another app may hold the combination. That is not the app's fault - it
    keeps running and a line in the journal says what is left (stop
    listening)."""
    telo = _telo("app.py", "start_snooze_hotkey")
    assert "except Exception" in telo
    # journal line after the real registration result (0.3 batch 4b)
    assert "self._ohlas_vysledok_skratky(ok)" in telo
    assert "log.hotkey_failed" in _telo("app.py", "_ohlas_vysledok_skratky")


def test_tridsat_minut_podla_zadania():
    import app as app_mod
    assert app_mod.SNOOZE_HOTKEY_MINUTES == 30


def test_predvolena_kombinacia_je_platna():
    import app as app_mod
    assert hotkey.is_valid(app_mod.DEFAULT_SNOOZE_HOTKEY)


# --------------------------------------------------------------------------
# Real registration (Windows only)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not hotkey.AVAILABLE, reason="user32 nie je k dispozícii")
def test_registracia_a_ciste_zastavenie():
    """The thread must be stoppable. Without `PostThreadMessageW` it would
    hang on `GetMessageW` until the end of the process and the combination
    would stay taken."""
    import threading
    h = hotkey.GlobalHotkey("ctrl+alt+shift+f9", lambda: None)
    assert h.start() is True, h.error
    assert h.registered
    h.stop()
    assert not h.registered
    assert h._thread is None
    assert not [t for t in threading.enumerate() if t.name == "hotkey"]


@pytest.mark.skipif(not hotkey.AVAILABLE, reason="user32 nie je k dispozícii")
def test_neplatna_kombinacia_sa_vobec_nespusti():
    h = hotkey.GlobalHotkey("nezmysel", lambda: None)
    assert h.start() is False
    assert h._thread is None
    assert h.error


def test_hotkey_neloguje_cez_ui_call():
    """The hotkey is registered on its own thread already during `__init__`,
    i.e. BEFORE `root.mainloop()`. `ui_call` cannot schedule then and the
    message is silently lost — that is exactly what happened: „skratka
    zaregistrovaná" (shortcut registered) never reached the window and
    app.log only got a `ui_call` failure.
    """
    telo = _telo("app.py", "start_snooze_hotkey")
    assert "log=app_log" in telo, \
        "modul musí logovať do súboru, nie cez ui_call"
    assert "log=self.log_threadsafe" not in telo


def test_log_pri_starte_hovori_pravdu_o_skratke():
    """The start-up line no longer promises „Anti-Cheat Safe Mode“ or
    „žiadne blokovanie“ (no blocking): the app reserves the "not now"
    shortcut (`RegisterHotKey`), so the game does not get that combination.
    It can be changed (settings file), which is why the sentence names the
    default combination as the default."""
    import i18n
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app as app_mod
    predvolena = hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY, lang="en").replace(" ", "")
    assert predvolena == "Ctrl+Alt+Z"
    zaznam = i18n.STRINGS["log.safe_mode"]
    assert set(zaznam) == set(i18n.LANGUAGES)
    for jazyk, text in zaznam.items():
        # in German "Strg+Alt+Z" - key names by language (0.3 batch 4b)
        assert hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY,
                                   lang=jazyk).replace(" ", "") in text, jazyk
        for stare in ("Anti-Cheat", "anti-cheat", "Safe Mode", "アンチチート", "反作弊",
                      "читов", "anti-trampas", "anti-triche"):
            assert stare not in text, (jazyk, stare)
    assert "blokovan" not in zaznam["sk"] and "blocking" not in zaznam["en"]
    assert "„teraz nie“" in zaznam["sk"] and "“not now”" in zaznam["en"]
    # 0.3: the app speaks in the 1st person ("rezervujem", "I reserve")
    assert "rezervuje" in zaznam["sk"] and "reserve" in zaznam["en"]
