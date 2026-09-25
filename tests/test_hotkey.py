# -*- coding: utf-8 -*-
"""Globálny kláves „teraz nie" (zadanie §1.9).

Testuje sa čítanie kombinácií a to, čím sa `RegisterHotKey` líši od hooku,
ktorý fáza 3 zrušila. Samotná registrácia potrebuje Windows a beží preto
len tam, kde je — zvyšok je čistá logika a prejde všade.
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
# Čítanie kombinácií
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
    """Bez MOD_NOREPEAT vygeneruje držanie klávesu záplavu správ a „teraz
    nie" by sa zaplo a vyplo desaťkrát za sekundu."""
    for combo in ("ctrl+alt+z", "shift+f9", "win+space"):
        mody, _vk = hotkey.parse_combo(combo)
        assert mody & hotkey.MOD_NOREPEAT, combo


def test_holy_klaves_sa_odmietne():
    """Holý kláves ako globálny hotkey by hráčovi zobral písmeno v každej hre
    aj v každom chate — a on by netušil prečo."""
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
# Čím sa to líši od hooku
# --------------------------------------------------------------------------

def _zdroj(meno):
    cesta = os.path.join(os.path.dirname(__file__), "..", meno)
    return io.open(cesta, encoding="utf-8-sig").read()


def test_modul_nesiaha_na_hooky():
    """To je celý dôvod, prečo `RegisterHotKey` a nie `pynput`.

    Hook vidí KAŽDÝ stlačený kláves a navonok sa nedá odlíšiť od keyloggera.
    Hotkey povie Windowsu jednu kombináciu a nič iné nedostane.
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
    """Poistka proti návratu. Číta sa AST, nie surový text — docstring
    vysvetľuje, prečo tam pynput NIE JE, a test na tom kedysi padal."""
    strom = strom_appky()
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.Import):
            for meno in uzol.names:
                assert "pynput" not in meno.name
        elif isinstance(uzol, ast.ImportFrom):
            assert "pynput" not in (uzol.module or "")


def test_import_nepadne_bez_win32():
    """Modul sa musí dať importovať aj tam, kde žiadny user32 nie je — inak
    by padol import celej appky. Rovnaká disciplína ako `activity.py`."""
    assert isinstance(hotkey.AVAILABLE, bool)


# --------------------------------------------------------------------------
# Zapojenie do appky
# --------------------------------------------------------------------------

def _telo(meno_suboru, meno_funkcie):
    # "app.py" = cela appka: app.py aj mixiny DandurfApp v app_*.py
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
    """Callback beží na vlastnom vlákne `hotkey.py`. `HeartStats`,
    `ActivityTracker` aj `overlay_manager` sú výhradne Tk-vláknové, takže
    siahnuť na ne odtiaľ priamo by bola tichá chyba."""
    telo = _telo("app.py", "_on_snooze_hotkey")
    assert "ui_call" in telo, "stlačenie sa musí preniesť do Tk cez ui_call"


def test_skratka_je_prepinac():
    """Druhé stlačenie ticho zruší. Nechať hráča čakať pol hodiny na niečo,
    čo si omylom zapol, by bolo horšie než samotné hlášky."""
    telo = _telo("app.py", "_toggle_snooze_from_hotkey")
    assert "_cancel_snooze" in telo and "_start_snooze" in telo


def test_skratka_prezije_zastavenie_pocuvania():
    """„Teraz nie" má fungovať, aj keď appka práve nepočúva, aj keď je
    minimalizovaná v lište. Vypína sa až pri skutočnom ukončení."""
    assert "stop_snooze_hotkey" not in _telo("app.py", "stop_listening")
    assert "stop_snooze_hotkey" not in _telo("app.py", "on_close")
    assert "stop_snooze_hotkey" in _telo("app.py", "_quit")


def test_zlyhana_registracia_nezhodi_appku():
    """Kombináciu môže držať iná appka. Nie je to chyba appky - beží ďalej
    a riadok v denníku povie, čo zostáva (zastaviť počúvanie)."""
    telo = _telo("app.py", "start_snooze_hotkey")
    assert "log.hotkey_failed" in telo
    assert "except Exception" in telo


def test_tridsat_minut_podla_zadania():
    import app as app_mod
    assert app_mod.SNOOZE_HOTKEY_MINUTES == 30


def test_predvolena_kombinacia_je_platna():
    import app as app_mod
    assert hotkey.is_valid(app_mod.DEFAULT_SNOOZE_HOTKEY)


# --------------------------------------------------------------------------
# Skutočná registrácia (len Windows)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not hotkey.AVAILABLE, reason="user32 nie je k dispozícii")
def test_registracia_a_ciste_zastavenie():
    """Vlákno sa musí dať zastaviť. Bez `PostThreadMessageW` by viselo na
    `GetMessageW` až do konca procesu a kombinácia by ostala zabratá."""
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
    """Hotkey sa registruje na vlastnom vlákne už počas `__init__`, teda
    PRED `root.mainloop()`. `ui_call` vtedy plánovať nevie a správa sa ticho
    stratí — presne to sa aj dialo: „skratka zaregistrovaná" sa do okna
    nikdy nedostala a v app.log pribudlo len zlyhanie `ui_call`.
    """
    telo = _telo("app.py", "start_snooze_hotkey")
    assert "log=app_log" in telo, \
        "modul musí logovať do súboru, nie cez ui_call"
    assert "log=self.log_threadsafe" not in telo


def test_log_pri_starte_hovori_pravdu_o_skratke():
    """Riadok pri štarte už nesľubuje „Anti-Cheat Safe Mode“ ani „žiadne
    blokovanie“: skratku „teraz nie“ si appka rezervuje (`RegisterHotKey`),
    takže tú kombináciu hra nedostane. Dá sa zmeniť (súbor nastavení), preto
    veta menuje predvolenú kombináciu ako predvolenú."""
    import i18n
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import app as app_mod
    predvolena = hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY).replace(" ", "")
    assert predvolena == "Ctrl+Alt+Z"
    zaznam = i18n.STRINGS["log.safe_mode"]
    assert set(zaznam) == set(i18n.LANGUAGES)
    for jazyk, text in zaznam.items():
        assert predvolena in text, jazyk
        for stare in ("Anti-Cheat", "anti-cheat", "Safe Mode", "アンチチート", "反作弊",
                      "читов", "anti-trampas", "anti-triche"):
            assert stare not in text, (jazyk, stare)
    assert "blokovan" not in zaznam["sk"] and "blocking" not in zaznam["en"]
    assert "„teraz nie“" in zaznam["sk"] and "“not now”" in zaznam["en"]
    assert "rezervuje" in zaznam["sk"] and "reserves" in zaznam["en"]
