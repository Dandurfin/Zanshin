# -*- coding: utf-8 -*-
"""0.2.1: „teraz nie“ aj bez skratky - položka v ponuke ikony v lište.

Review 0.2: keď Ctrl+Alt+Z drží iná appka, `RegisterHotKey` zlyhá a hlášky
sa potom dali stíšiť jedine zastavením počúvania - to zastaví aj meranie.
Tlačidlo v doku odišlo s dokom, v okne ani v lište nič iné nebolo.

Teraz:
  * v ponuke listy je položka „Teraz nie (30 min)“ - robí presne to, čo
    skratka (prepínač cez `_toggle_snooze_from_hotkey`, cez `ui_call`),
    a fajka hovorí, či práve platí,
  * zlyhanie registrácie sa ohlási RAZ riadkom v denníku, ktorý ukáže na
    tú položku (bez listy ostáva stará veta o zastavení).
"""
import os
import random
import sys
import time as _time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import trigger  # noqa: E402


def _nic(*_a, **_k):
    return None


class _Root:
    def __init__(self):
        self.ulohy = {}
        self._n = 0

    def after(self, ms, fn):
        self._n += 1
        uid = f"after#{self._n}"
        self.ulohy[uid] = (ms, fn)
        return uid

    def after_cancel(self, uid):
        self.ulohy.pop(uid, None)


class _Bodka:
    def __init__(self):
        self.stav = []

    def set_snoozed(self, active, tip=None):
        self.stav.append((active, tip))


# --------------------------------------------------------------------------
# Atrapa pystray
# --------------------------------------------------------------------------

class _Polozka:
    def __init__(self, text, action, checked=None, default=False, **_kw):
        self.text, self.action, self.checked = text, action, checked
        self.default = default


class _Menu:
    def __init__(self, *polozky):
        self.polozky = polozky


class _Ikona:
    def __init__(self, name, image, title, menu):
        self.menu = menu
        self.aktualizacie = 0

    def run(self):
        pass

    def update_menu(self):
        self.aktualizacie += 1


class _Vlakno:
    def __init__(self, target=None, daemon=None, **_kw):
        self.target = target

    def start(self):
        pass


def _appka(monkeypatch):
    import app as app_mod
    monkeypatch.setattr(app_mod, "pystray", types.SimpleNamespace(
        Menu=_Menu, MenuItem=_Polozka, Icon=_Ikona), raising=False)
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root()
    a.denn = []
    a.log = a.denn.append
    a.fronta = []
    a.ui_call = a.fronta.append
    a.make_tray_image = lambda: None
    a.listening = True
    a._hr_session_open = True
    a._cue_armed = False
    a._snooze_job = None
    a._snooze_po_hlaske = None
    a.hr_stats = hr_stats.HeartStats(critical_bpm=110)
    a.cue_trigger = trigger.CueTrigger(rng=random.Random(1), clock=_time.time)
    a.cue_trigger.open_session(silent_share=0.0)
    a._on_cue_event = _nic
    a._refresh_dnes_state_text = _nic
    a._refresh_kamae_state_text = _nic
    a.bodka = _Bodka()
    a.sidebar = types.SimpleNamespace(state_dot=a.bodka)
    app_mod.DandurfApp.setup_tray(a)
    return app_mod, a


def _polozka_teraz_nie(app_mod, a):
    text = i18n.tr("tray.snooze", minutes=app_mod.SNOOZE_HOTKEY_MINUTES)
    najdene = [p for p in a.tray_icon.menu.polozky if p.text(p) == text]
    assert len(najdene) == 1, "v liste chyba polozka „teraz nie“"
    return najdene[0]


def test_lista_ma_teraz_nie_a_robi_to_iste_co_skratka(monkeypatch):
    app_mod, a = _appka(monkeypatch)
    p = _polozka_teraz_nie(app_mod, a)
    assert p.checked is not None and p.checked(p) is False
    p.action(a.tray_icon, p)
    # klik prisiel na vlakne listy - do Tk ide cez `ui_call`, nic priamo
    assert a.fronta == [a._toggle_snooze_from_hotkey]
    assert a._snooze_job is None
    a.fronta.pop()()
    assert a._snooze_job is not None
    assert a.root.ulohy[a._snooze_job][0] == app_mod.SNOOZE_HOTKEY_MINUTES * 60 * 1000
    assert a.cue_trigger._suspended_by == trigger.A_SNOOZE
    assert a.listening is True and a._hr_session_open is True
    assert p.checked(p) is True, "fajka ukaze, ze teraz nie plati"
    # druhy klik zrusi - prepinac ako skratka
    p.action(a.tray_icon, p)
    a.fronta.pop()()
    assert a._snooze_job is None and p.checked(p) is False
    assert a.denn[-1] == i18n.tr("log.snooze_cancelled")


def test_polozka_funguje_so_skutocnym_pystray(monkeypatch):
    """Atrapa vyssie prijme hocico. Skutocny `pystray.MenuItem` si akciu aj
    `checked` obali podla poctu argumentov - tu sa overi, ze klik aj fajka
    prejdu tak, ako ich zavola pystray (bez ikony a bez vlakna listy)."""
    pystray = pytest.importorskip("pystray")
    import app as app_mod
    monkeypatch.setattr(app_mod, "pystray", types.SimpleNamespace(
        Menu=pystray.Menu, MenuItem=pystray.MenuItem, Icon=_Ikona), raising=False)
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.fronta = []
    a.ui_call = a.fronta.append
    a.make_tray_image = lambda: None
    a._snooze_job = None
    app_mod.DandurfApp.setup_tray(a)
    text = i18n.tr("tray.snooze", minutes=app_mod.SNOOZE_HOTKEY_MINUTES)
    najdene = [p for p in a.tray_icon.menu.items if p.text == text]
    assert len(najdene) == 1
    p = najdene[0]
    assert p.checked is False
    p(a.tray_icon)                      # takto klik vola pystray
    assert a.fronta == [a._toggle_snooze_from_hotkey]
    a._snooze_job = "after#1"
    assert p.checked is True


def test_fajka_sa_obnovi_aj_po_skratke(monkeypatch):
    """Pystray si menu postaví znova len na `update_menu`; skratka ani
    `ui_call` po kliku ho inak neobnovia."""
    app_mod, a = _appka(monkeypatch)
    pred = a.tray_icon.aktualizacie
    a._toggle_snooze_from_hotkey()
    assert a.tray_icon.aktualizacie > pred
    pred = a.tray_icon.aktualizacie
    a._toggle_snooze_from_hotkey()
    assert a.tray_icon.aktualizacie > pred


def test_pokazene_menu_listy_nezhodi_stisenie(monkeypatch):
    app_mod, a = _appka(monkeypatch)

    def zlyha():
        raise OSError("menu")
    a.tray_icon.update_menu = zlyha
    a._toggle_snooze_from_hotkey()
    assert a._snooze_job is not None
    assert a.bodka.stav[-1][0] is True, "bodka stavu sa aj tak prepne"


def test_bez_listy_indikator_nespadne(monkeypatch):
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a._refresh_dnes_state_text = _nic
    a._snooze_job = None
    app_mod.DandurfApp._refresh_snooze_indicator(a)      # ziadne tray_icon


# --------------------------------------------------------------------------
# Zlyhaná registrácia skratky
# --------------------------------------------------------------------------

class _Skratka:
    vysledok = False

    def __init__(self, combo, callback, log=None):
        self.combo = combo

    def start(self):
        return type(self).vysledok

    def stop(self):
        pass


def _registruj(monkeypatch, podari_sa, lista):
    import app as app_mod
    monkeypatch.setattr(app_mod.hotkey, "GlobalHotkey",
                        type("S", (_Skratka,), {"vysledok": podari_sa}))
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", lista)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.denn = []
    a.log = a.denn.append
    a._hotkey = None
    a.snooze_hotkey = app_mod.DEFAULT_SNOOZE_HOTKEY
    ok = app_mod.DandurfApp.start_snooze_hotkey(a)
    return app_mod, ok, a.denn


def test_zlyhana_skratka_posle_hraca_do_listy_raz(monkeypatch):
    import hotkey
    app_mod, ok, denn = _registruj(monkeypatch, False, True)
    combo = hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY)
    assert ok is False
    assert denn == [i18n.tr("log.hotkey_failed_tray", combo=combo)]


def test_bez_listy_ostava_stara_veta(monkeypatch):
    import hotkey
    app_mod, ok, denn = _registruj(monkeypatch, False, False)
    combo = hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY)
    assert denn == [i18n.tr("log.hotkey_failed", combo=combo)]


def test_uspesna_skratka_hlasi_len_pripravenost(monkeypatch):
    import hotkey
    app_mod, ok, denn = _registruj(monkeypatch, True, True)
    combo = hotkey.format_combo(app_mod.DEFAULT_SNOOZE_HOTKEY)
    assert ok is True and denn == [i18n.tr("log.hotkey_on", combo=combo)]


def test_skratka_sa_registruje_len_raz_pri_starte():
    """„Raz“ z hlásenia stojí na tom, že `start_snooze_hotkey` volá len
    `__init__` - keby ju volalo aj niečo opakované, riadok by sa množil."""
    with open(os.path.join(os.path.dirname(__file__), "..", "app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    assert src.count("self.start_snooze_hotkey()") == 1


def test_nove_vety_hovoria_pravdu():
    """Veta o zlyhaní už nesmie tvrdiť, že „teraz nie“ nepôjde vôbec, ani
    sľubovať meranie (počas stíšenia v zastavenej appke sa nemeria) - len
    to, čo platí vždy: počúvanie to nezastaví. Kľúče dopĺňa jazyková časť
    0.2.1; kým tam nie sú, stráži ich tests/test_i18n_keys.py."""
    s = i18n.STRINGS
    if "log.hotkey_failed_tray" not in s or "tray.snooze" not in s:
        pytest.skip("kluce 0.2.1 este nie su v i18n")
    for kluc in ("log.hotkey_failed_tray", "tray.snooze"):
        assert set(s[kluc]) == set(i18n.LANGUAGES), kluc
    veta = s["log.hotkey_failed_tray"]
    assert "{combo}" in veta["sk"] and "{combo}" in veta["en"]
    assert "lište" in veta["sk"] and "tray" in veta["en"]
    assert "Počúvanie to nezastaví" in veta["sk"]
    assert "doesn’t stop listening" in veta["en"]
    for jazyk in ("sk", "en"):
        assert "merať" not in veta[jazyk] and "measuring" not in veta[jazyk]
    assert s["tray.snooze"]["sk"].startswith("Teraz nie")
    assert s["tray.snooze"]["en"].startswith("Not now")
    for jazyk in i18n.LANGUAGES:
        assert "{minutes}" in s["tray.snooze"][jazyk], jazyk
