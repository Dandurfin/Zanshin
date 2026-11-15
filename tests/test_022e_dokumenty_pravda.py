# -*- coding: utf-8 -*-
"""Truth check of the documents after batch 4 (0.3) - the skeptic's fixes.

  * The shortcut row in Settings reports a taken shortcut right FROM THE START
    (not only after choosing) and after the default shortcut is swapped at
    start it shows the new one - CHANGELOG, HOW-IT-WORKS and SAFETY all
    promise it ("the row says so").
  * HOW-IT-WORKS / CHANGELOG: the session save rule is a minute AND at least
    10 samples (`hr_stats.je_ulozitelna`), not "a minute of heart rate".
  * The questionnaire on quitting: touched answers are saved only by the
    SECOND "Quit" (`_quit` knows only a questionnaire opened while closing) -
    and the documents say so.
  * PRIVACY: "Delete history" also deletes the prepared voice and older logs.
  * HOW-IT-WORKS: from adapters the name, description, type and state are
    used - not the MAC.

Everything on stubs and synthetic data.
"""
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import app as app_mod  # noqa: E402
import data_io  # noqa: E402
import hotkey  # noqa: E402
import hr_stats  # noqa: E402
from i18n import tr  # noqa: E402
from app_spolocne import DEFAULT_SNOOZE_HOTKEY, SNOOZE_HOTKEY_MINUTES  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return " ".join(fh.read().split())


# --------------------------------------------------------------------------
# The shortcut row after start
# --------------------------------------------------------------------------

class _Popis:
    def __init__(self):
        self.text = None

    def configure(self, text=None, **_kw):
        self.text = text


class _Premenna:
    def __init__(self, hodnota):
        self.hodnota = hodnota

    def get(self):
        return self.hodnota

    def set(self, hodnota):
        self.hodnota = hodnota


class _Skratka:
    def __init__(self, combo, callback, log=None):
        self.combo, self.registered = combo, False

    def start(self):
        self.registered = self.combo != "ctrl+alt+z"       # Z: "another program holds it"
        return self.registered

    def stop(self):
        self.registered = False


def _appka_s_riadkom(kolizia):
    """State after `_build_ui`: the row built for the default shortcut, still
    before `_vyber_skratku_pri_starte` and registration."""
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.snooze_hotkey = DEFAULT_SNOOZE_HOTKEY
    a.snooze_hotkey_chosen = False
    a._hotkey = None
    a._hotkey_zlyhala = False
    a.denn = []
    a.log = a.denn.append
    a.save_settings = lambda: None
    volby = a._snooze_hotkey_volby(kolizia=kolizia)
    a._snooze_hotkey_podla_popisu = dict(volby)
    a.snooze_hotkey_row = types.SimpleNamespace(sub_label=_Popis())
    a.snooze_hotkey_var = _Premenna(volby[0][0])
    a.snooze_hotkey_row.sub_label.text = a._snooze_hotkey_sub()
    return a


def test_obsadena_skratka_pri_starte_riadok_povie_hned(monkeypatch):
    monkeypatch.setattr(hotkey, "GlobalHotkey", _Skratka)
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)
    a = _appka_s_riadkom(kolizia=lambda c: "")
    sluboval = a.snooze_hotkey_row.sub_label.text
    assert sluboval == tr("settings.snooze_hotkey_sub", combo="Ctrl + Alt + Z",
                          minutes=SNOOZE_HOTKEY_MINUTES)
    assert a._vyber_skratku_pri_starte(kolizia=lambda c: "") is None
    assert a.start_snooze_hotkey() is False
    a._refresh_snooze_hotkey_row()
    assert a.snooze_hotkey_row.sub_label.text == tr(
        "settings.snooze_hotkey_taken", combo="Ctrl + Alt + Z")


def test_vymena_skratky_pri_starte_prepise_aj_ponuku(monkeypatch):
    monkeypatch.setattr(hotkey, "GlobalHotkey", _Skratka)
    monkeypatch.setattr(app_mod, "TRAY_AVAILABLE", True)

    def polske(combo):
        return "ż" if combo == "ctrl+alt+z" else ""
    a = _appka_s_riadkom(kolizia=polske)
    assert a.snooze_hotkey_var.get() == tr("settings.snooze_hotkey_types",
                                           combo="Ctrl + Alt + Z", char="ż")
    assert a._vyber_skratku_pri_starte(kolizia=polske) == "ctrl+alt+f9"
    assert a.start_snooze_hotkey() is True
    a._refresh_snooze_hotkey_row()
    assert a.snooze_hotkey_var.get() == "Ctrl + Alt + F9"
    assert a.snooze_hotkey_row.sub_label.text == tr(
        "settings.snooze_hotkey_sub", combo="Ctrl + Alt + F9",
        minutes=SNOOZE_HOTKEY_MINUTES)


def test_refresh_bez_riadku_nic_nerobi():
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a._refresh_snooze_hotkey_row()          # no row, no error


def test_start_obnovi_riadok_az_po_registracii():
    init = zdroj_metody("__init__")
    assert init.index("self._build_ui()") < init.index("self.start_snooze_hotkey()")
    assert init.index("self.start_snooze_hotkey()") < init.index(
        "self._refresh_snooze_hotkey_row()")
    # and what the documents promise holds
    assert "If another program holds yours, the row says so." in _read("CHANGELOG.md")
    assert "od 0.3 to povie aj riadok v nastaveniach" in _read("SAFETY.md")


# --------------------------------------------------------------------------
# When a session is saved
# --------------------------------------------------------------------------

def test_pravidlo_ulozenia_relacie_v_dokumentoch_sedi_s_kodom():
    ok = {"duration_s": 60.0, "samples": 10}
    assert hr_stats.je_ulozitelna(ok)
    assert not hr_stats.je_ulozitelna(dict(ok, samples=9))
    assert not hr_stats.je_ulozitelna(dict(ok, duration_s=59.0))
    # 2 minutes with 30 samples (less than a minute of heart rate) ARE SAVED
    assert hr_stats.je_ulozitelna({"duration_s": 120.0, "samples": 30})
    a = _read("docs/HOW-IT-WORKS.md")
    assert "A session of at least a minute with at least 10 heart-rate readings is saved" in a
    assert "Sessions with at least a minute of heart rate are saved" not in a
    c = _read("CHANGELOG.md")
    assert "session without even a minute of heart rate still isn't saved" not in c
    assert "(fewer than 10 readings) still isn't saved, but the log now says so" in c
    # journal: only a session from a minute with fewer than 10 samples
    kod = zdroj_metody("_kratka_relacia_bez_tepu")
    assert "trvanie >= 60 and vzorky < 10" in kod


# --------------------------------------------------------------------------
# The questionnaire on quitting
# --------------------------------------------------------------------------

def test_dotknute_odpovede_uklada_len_druhe_ukoncenie():
    quit_kod = zdroj_metody("_quit")
    assert "_dotaznik_pri_zatvarani" in quit_kod
    # `_quit` remembers the questionnaire ONLY when it was opened while closing
    otazka = zdroj_metody("_ask_session_context")
    assert otazka.index('getattr(self, "_zatvara_sa", False)') < otazka.index(
        "self._dotaznik_pri_zatvarani = dialog")
    a = _read("docs/HOW-IT-WORKS.md")
    assert ("If you quit Zanshin while it's watching, it saves the session and "
            "opens its questions first. If you quit again while they're open") in a
    c = _read("CHANGELOG.md")
    assert "a second Quit while they're open saves the answers you've touched" in c


# --------------------------------------------------------------------------
# PRIVACY: what "Delete history" deletes
# --------------------------------------------------------------------------

def test_privacy_menuje_vsetko_co_zmazanie_historie_zmaze():
    p = _read("PRIVACY.md")
    assert ("deletes the session, insight and measurement files above with their "
            "backups, the prepared voice clips, the crash log and older logs "
            "(not your settings or recordings)") in p
    assert ("data.delete.tts", os.path.join("audio", "tts_cache")) in data_io.MAZATELNE_PRIECINKY
    assert "crash.log" in data_io._LOG_SUBORY and "app.log.1" in data_io._LOG_SUBORY
    mena = {meno for _k, meno in data_io.MAZATELNE}
    assert not {m for m in mena if "settings" in m}


# --------------------------------------------------------------------------
# HOW-IT-WORKS: what the app uses from adapters
# --------------------------------------------------------------------------

def test_adaptery_len_meno_popis_typ_a_stav():
    a = _read("docs/HOW-IT-WORKS.md")
    assert ("uses only the adapters' names, descriptions and types and whether "
            "they're connected") in a
    assert "názvy, popisy, typy a stav (pripojený či nie) adaptérov" in _read("SAFETY.md")
    kod = zdroj_suboru("netinfo.py")
    assert "a.OperStatus == 1" in kod
    assert "a.PhysicalAddress" not in kod, "MAC adresa sa nepouziva"
    assert ('out.append((ip, a.FriendlyName or "", a.Description or "",\n'
            "                                    int(a.IfType)))") in kod
