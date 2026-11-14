# -*- coding: utf-8 -*-
"""Dotaznik po hre (0.2.2, davka 4 auditu UX).

  * "Za tebou je ... hrania." je nadpis tela v ui(16, 'bold'), nie drobna
    veta v listke okna; od hodiny citatelna dlzka ("2 h 03 min", nie "2:03"),
  * ked appka v relacii zbadala hru na celu obrazovku (exkluzivny
    fullscreen - obrazky nad nou Windows nevykresli), suhrn nesie
    `fullscreen` a hlavicka dotaznika povie jednu kratku vetu.

Synteticke data, bez okna.
"""
import ast
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _dialog_init():
    strom = ast.parse(zdroj_suboru("ui_dialogs.py"))
    trieda = next(u for u in strom.body
                  if isinstance(u, ast.ClassDef) and u.name == "SessionEndDialog")
    init = next(f for f in trieda.body
                if isinstance(f, ast.FunctionDef) and f.name == "__init__")
    return ast.unparse(init)


# --------------------------------------------------------------------------
# Nadpis
# --------------------------------------------------------------------------

def test_cas_hrania_je_nadpis_tela():
    init = _dialog_init()
    assert "self.heading_label = ctk.CTkLabel(body, text=titulok, " \
           "font=ui_kit.ui(16, 'bold')" in init
    # nadpis je prvy v tele, pred vetou o hlaskach aj pred krivkou
    assert init.index("self.heading_label") < init.index("podnadpis =")
    # v listke len meno appky - ta ista veta dvakrat pod sebou by tam bola navyse
    assert "ui_kit.DialogChrome(self.top, pal, APP_NAME, on_close=self.close)" in init


def test_cas_od_hodiny_citatelne(sk):
    import ui_dialogs
    cas = ui_dialogs.SessionEndDialog._cas
    assert cas(26) == "26 min"
    assert cas(123) == "2 h 03 min"
    assert i18n.tr("session.end.title", time=cas(123)) == "Za tebou je 2 h 03 min hrania."


def test_prazdny_dovod_ticha_nenecha_medzeru():
    init = _dialog_init()
    blok = init[init.index("preco = self._preco_ticho(summary)"):]
    blok = blok[:blok.index("krivka = ")]
    assert "if preco:" in blok


# --------------------------------------------------------------------------
# Exkluzivny fullscreen
# --------------------------------------------------------------------------

def test_kedy_dotaznik_povie_vetu_o_fullscreene():
    import ui_dialogs
    ukaz = ui_dialogs.SessionEndDialog.ukaz_fullscreen_vetu
    assert ukaz({"fullscreen": True}, 2, "play") is True
    assert ukaz({"fullscreen": True}, 0, "play") is False, "bez hlasky nebol obrazok"
    assert ukaz({"fullscreen": True}, 2, "work") is False, "v Praci nie je hlas"
    assert ukaz({}, 2, "play") is False
    assert ukaz(None, 2, "play") is False
    assert ukaz({"fullscreen": True}, "zle", "play") is False


def test_veta_ide_pod_nadpis():
    init = _dialog_init()
    veta = init.index("tr('session.end.fullscreen_note')")
    assert init.index("self.heading_label") < veta < init.index("podnadpis =")
    assert "if self.ukaz_fullscreen_vetu(summary, cues, self._svet):" in init


def _appka(fullscreen, monkeypatch, relacia=True):
    import app_data
    volania = []

    def je_fullscreen(_root=None):
        volania.append(True)
        return fullscreen

    monkeypatch.setattr(app_data.display, "is_fullscreen_foreground", je_fullscreen)
    dennik = []
    a = types.SimpleNamespace(root=None, _hr_session_open=relacia, log=dennik.append)
    return a, volania, dennik


def test_relacia_si_zapamata_fullscreen(monkeypatch):
    import app as app_mod
    a, volania, dennik = _appka(True, monkeypatch)
    app_mod.DandurfApp._warn_exclusive_fullscreen_once(a)
    assert a._session_fullscreen is True and a._fullscreen_warned is True
    assert len(dennik) == 1
    # obe uz vedia - dalsie sekundy sa okno nekontroluje
    app_mod.DandurfApp._warn_exclusive_fullscreen_once(a)
    assert len(volania) == 1
    # nova relacia (`_open_hr_session` nuluje priznak): zisti sa znova,
    # ale do dennika uz nie - ten je raz za beh appky
    a._session_fullscreen = False
    app_mod.DandurfApp._warn_exclusive_fullscreen_once(a)
    assert a._session_fullscreen is True and len(dennik) == 1


def test_bez_fullscreenu_ani_bez_relacie_nic(monkeypatch):
    import app as app_mod
    a, _v, dennik = _appka(False, monkeypatch)
    app_mod.DandurfApp._warn_exclusive_fullscreen_once(a)
    assert not getattr(a, "_session_fullscreen", False) and dennik == []
    a, _v, dennik = _appka(True, monkeypatch, relacia=False)
    app_mod.DandurfApp._warn_exclusive_fullscreen_once(a)
    assert not getattr(a, "_session_fullscreen", False)
    assert len(dennik) == 1


def test_otvorenie_relacie_nuluje_priznak():
    telo = zdroj_metody("_open_hr_session")
    assert "self._session_fullscreen = False" in telo


def _suhrn(**stav):
    import app as app_mod
    a = types.SimpleNamespace(hr_stats=types.SimpleNamespace(summary=lambda **k: {}),
                              **stav)
    return app_mod.DandurfApp._suhrn_relacie(a)


def test_suhrn_nesie_fullscreen_len_ked_bol():
    assert _suhrn(_session_fullscreen=True)["fullscreen"] is True
    assert "fullscreen" not in _suhrn(_session_fullscreen=False)
    assert "fullscreen" not in _suhrn()


def test_import_historie_priznak_prenesie():
    """Nove pole prejde kontrolou neznameho pola (`data_io._je_obycajne`)."""
    zaklad = {"started": 1_700_000_000.0, "duration_s": 1800.0}
    assert data_io.clean_session(dict(zaklad, fullscreen=True))["fullscreen"] is True


def test_veta_vo_vsetkych_jazykoch():
    zaznam = i18n.STRINGS["session.end.fullscreen_note"]
    assert set(zaznam) == set(i18n.LANGUAGES)
    for jazyk, text in zaznam.items():
        assert "Borderless" in text, jazyk          # tak sa to vola v hrach
        assert len(text) < 200, jazyk               # jedna kratka veta
        if jazyk not in ("sk", "en"):
            assert text != zaznam["en"], jazyk
    sk = zaznam["sk"]
    assert "obrázky" in sk and "Hlas" in sk
    for slovo in ("odpočúva", "počúva", "hlášk", "spúšťa", "slot", "vizuál"):
        assert slovo not in sk.lower(), slovo
    assert "pictures" in zaznam["en"]
