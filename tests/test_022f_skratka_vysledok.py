# -*- coding: utf-8 -*-
"""The "not now" shortcut row by the REAL registration result (0.3 batch 4b).

`GlobalHotkey.start()` waits for the result at most 2 s. When Windows was
slow at start, it returned False - and the row in Settings and the journal
claimed that another program held the shortcut, although it worked a moment
later. Now the shortcut thread reports the result itself (`on_result`), the
app carries it into Tk (`ui_call` = `root.after(0)`) and only then writes
the line and refreshes Settings.

No real registration: the Windows API is a dummy that answers only when the
test tells it to.
"""
import threading
import types

import pytest
from ctypes import wintypes

import app as app_mod
import hotkey
from i18n import tr


# --------------------------------------------------------------------------
# GlobalHotkey with a slow fake registration
# --------------------------------------------------------------------------

class _PomalyUser32:
    """RegisterHotKey answers only when the test releases `pust`; GetMessageW
    waits until `stop()` sends WM_QUIT (the dummy's PostThreadMessageW)."""

    def __init__(self, uspech=True):
        self.pust = threading.Event()
        self.koniec = threading.Event()
        self.uspech = uspech
        self.zaregistrovane = []
        self.odregistrovane = []

    def RegisterHotKey(self, _hwnd, ident, mody, vk):
        self.pust.wait(5.0)
        if self.uspech:
            self.zaregistrovane.append((ident, mody, vk))
            return 1
        return 0

    def UnregisterHotKey(self, _hwnd, ident):
        self.odregistrovane.append(ident)
        return 1

    def GetMessageW(self, _msg, _hwnd, _a, _b):
        self.koniec.wait(5.0)
        return 0


def _atrapa_win32(monkeypatch, user32):
    ctypes_atrapa = types.SimpleNamespace(
        byref=lambda x: x,
        get_last_error=lambda: 1409,
        windll=types.SimpleNamespace(
            kernel32=types.SimpleNamespace(GetCurrentThreadId=lambda: 7),
            user32=types.SimpleNamespace(
                PostThreadMessageW=lambda *_a: user32.koniec.set() or 1)))
    monkeypatch.setattr(hotkey, "_win32", lambda: (ctypes_atrapa, user32))
    monkeypatch.setattr(hotkey, "AVAILABLE", True)
    monkeypatch.setattr(hotkey.GlobalHotkey, "CAKAJ_NA_REGISTRACIU_S", 0.05)
    assert wintypes.MSG  # _slucka takes it from the real ctypes


@pytest.mark.parametrize("uspech", [True, False])
def test_pomala_registracia_povie_vysledok_neskor(monkeypatch, uspech):
    user32 = _PomalyUser32(uspech)
    _atrapa_win32(monkeypatch, user32)
    vysledky, prislo = [], threading.Event()
    h = hotkey.GlobalHotkey("ctrl+alt+z", lambda: None,
                            on_result=lambda ok: (vysledky.append(ok), prislo.set()))
    try:
        assert h.start() is False, "este nie je hotovo"
        assert h.caka is True, "False zo start() teraz NEZNAMENA obsadene"
        assert vysledky == []
        user32.pust.set()
        assert prislo.wait(5.0)
        assert vysledky == [uspech]
        assert h.caka is False
        assert h.registered is uspech
        if not uspech:
            assert "1409" in (h.error or "")
    finally:
        user32.pust.set()
        h.stop()
    assert h._thread is None


def test_rychla_registracia_vrati_vysledok_hned(monkeypatch):
    user32 = _PomalyUser32(True)
    user32.pust.set()
    _atrapa_win32(monkeypatch, user32)
    monkeypatch.setattr(hotkey.GlobalHotkey, "CAKAJ_NA_REGISTRACIU_S", 5.0)
    vysledky, prislo = [], threading.Event()
    h = hotkey.GlobalHotkey("ctrl+alt+z", lambda: None,
                            on_result=lambda ok: (vysledky.append(ok), prislo.set()))
    try:
        assert h.start() is True
        assert h.caka is False
        # `on_result` comes here too (once) - the app drops it, already said
        assert prislo.wait(5.0) and vysledky == [True]
    finally:
        h.stop()


def test_vynimka_v_on_result_nezabije_vlakno(monkeypatch):
    user32 = _PomalyUser32(True)
    user32.pust.set()
    _atrapa_win32(monkeypatch, user32)
    monkeypatch.setattr(hotkey.GlobalHotkey, "CAKAJ_NA_REGISTRACIU_S", 5.0)
    zaznam, zalogovane = [], threading.Event()

    def log(sprava):
        zaznam.append(sprava)
        if "on_result" in sprava:
            zalogovane.set()

    def zle(_ok):
        raise RuntimeError("callback")

    h = hotkey.GlobalHotkey("ctrl+alt+z", lambda: None, log=log, on_result=zle)
    try:
        assert h.start() is True
        assert zalogovane.wait(5.0)
        assert "hotkey: on_result vyhodil vynimku" in zaznam
        assert h._thread.is_alive(), "slucka ide dalej"
    finally:
        h.stop()


# --------------------------------------------------------------------------
# The app: row and journal only after the real result
# --------------------------------------------------------------------------

class _CakajucaSkratka:
    """GlobalHotkey dummy: `start()` timed out (`caka`); the test answers."""
    instancie = []

    def __init__(self, combo, on_press, log=None, on_result=None):
        self.combo, self.on_result = combo, on_result
        self.registered, self.caka = False, False
        type(self).instancie.append(self)

    def start(self):
        self.caka = True
        return False

    def dokonci(self, ok):
        self.registered, self.caka = ok, False
        self.on_result(ok)

    def stop(self):
        self.registered = False


class _Stitok:
    def __init__(self):
        self.text = None

    def configure(self, text=None, **_k):
        self.text = text


def _appka(monkeypatch, combo="ctrl+alt+z"):
    _CakajucaSkratka.instancie = []
    monkeypatch.setattr(hotkey, "GlobalHotkey", _CakajucaSkratka)
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.snooze_hotkey = combo
    a._hotkey = None
    a.denn = []
    a.log = a.denn.append
    a.fronta = []
    a.ui_call = a.fronta.append          # like root.after(0): only in the Tk thread
    a.snooze_hotkey_row = types.SimpleNamespace(sub_label=_Stitok())
    a.snooze_hotkey_var = None
    a.pas = []
    a._refresh_kamae_state_text = lambda: a.pas.append("pas")
    return a


def _dorucit(a):
    fronta, a.fronta[:] = list(a.fronta), []
    for fn in fronta:
        fn()


def test_pomaly_start_netvrdi_obsadene(monkeypatch):
    a = _appka(monkeypatch)
    assert a.start_snooze_hotkey() is False
    assert a._hotkey_caka is True and a._hotkey_zlyhala is False
    assert a.denn == [], "ziadne 'drzi ju iny program', kym vysledok nie je"
    pekne = hotkey.format_combo("ctrl+alt+z")
    assert a._snooze_hotkey_sub() != tr("settings.snooze_hotkey_taken", combo=pekne)


def test_neskory_uspech_zapise_zapnute_a_obnovi_riadok(monkeypatch):
    a = _appka(monkeypatch)
    a.start_snooze_hotkey()
    skratka = _CakajucaSkratka.instancie[-1]
    skratka.dokonci(True)                 # from the shortcut thread
    assert a.denn == [], "z vlakna nic priamo - az cez ui_call"
    _dorucit(a)
    pekne = hotkey.format_combo("ctrl+alt+z")
    assert a.denn == [tr("log.hotkey_on", combo=pekne)]
    assert a._hotkey_caka is False and a._hotkey_zlyhala is False
    assert a.snooze_hotkey_row.sub_label.text == a._snooze_hotkey_sub()
    assert a.pas == ["pas"]
    assert a._skratka_teraz_nie() == pekne


def test_neskore_zlyhanie_povie_obsadene_raz(monkeypatch):
    a = _appka(monkeypatch)
    a.start_snooze_hotkey()
    _CakajucaSkratka.instancie[-1].dokonci(False)
    _dorucit(a)
    pekne = hotkey.format_combo("ctrl+alt+z")
    assert a.denn == [tr("log.hotkey_failed_tray", combo=pekne)]
    assert a._hotkey_zlyhala is True
    assert a.snooze_hotkey_row.sub_label.text == tr("settings.snooze_hotkey_taken", combo=pekne)
    # a second (delayed) result of the same registration is no longer written
    a._po_registracii_skratky(a._hotkey_gen, False)
    assert len(a.denn) == 1


def test_vysledok_starej_skratky_sa_zahodi(monkeypatch):
    a = _appka(monkeypatch)
    a.start_snooze_hotkey()
    stara = _CakajucaSkratka.instancie[-1]
    a.snooze_hotkey = "ctrl+alt+f9"       # the player picked another one meanwhile
    a.start_snooze_hotkey(po_zmene=True)
    stara.dokonci(False)
    _dorucit(a)
    assert a.denn == [] and a._hotkey_zlyhala is False and a._hotkey_caka is True
    _CakajucaSkratka.instancie[-1].dokonci(True)
    _dorucit(a)
    assert a.denn == [tr("log.hotkey_on", combo=hotkey.format_combo("ctrl+alt+f9"))]


class _HotovaHned(_CakajucaSkratka):
    """`start()` still returned False, but the thread finished successfully
    before the app asked about `caka` - the result is already final in
    `registered`."""

    def start(self):
        self.registered, self.caka = True, False
        self.on_result(True)
        return False


def test_vysledok_medzi_start_a_caka_sa_nestrati(monkeypatch):
    a = _appka(monkeypatch)
    monkeypatch.setattr(hotkey, "GlobalHotkey", _HotovaHned)
    assert a.start_snooze_hotkey() is True
    _dorucit(a)                           # the thread's on_result is dropped - already said
    assert a.denn == [tr("log.hotkey_on", combo=hotkey.format_combo("ctrl+alt+z"))]
    assert a._hotkey_zlyhala is False
