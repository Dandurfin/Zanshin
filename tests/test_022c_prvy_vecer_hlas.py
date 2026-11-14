# -*- coding: utf-8 -*-
"""Prvy vecer hovori prirodzenym hlasom (0.2.2).

Audit: po uvode appka zacala sledovat o 250 ms. Lenze kym sleduje, na
Microsoft nechodi ani kvoli priprave hlasok (`pregenerate`), takze sa
priprava hned zastavila a prvy vecer - ten, podla ktoreho sa appka posudzuje -
hovoril vacsinou hlasom z Windows. Hraci de/fr/es/pt navyse dostali britsku
Soniu, hoci ich vstavane slova su v ich jazyku. Strazi sa:

  * prvy start zacne sledovat az ked su hlasky v cache, najviac po 15 s,
  * kym caka, stav na Dnes povie "Pripravujem hlas" (nie "Zastavene, klikni"),
  * hrac ani hra (auto-profil) nedostanu druhy start navyse,
  * VOICE_HINTS ma es/de/fr/pt - pribalene, zenske - a plati pravidlo z
    0.2.1d: hlas ide za slovami hlasok, nie za jazykom menu.

Bez Tk: `root.after` je atrapa, ktora ulohu spusti, az ked ju test pusti.
"""
import json
import os
import sys
import time
import types

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402
from settings_model import (DEFAULT_EDGE_VOICE, EDGE_FALLBACK_VOICES,  # noqa: E402
                            ENGINE_EDGE, ENGINE_SAPI, VOICE_HINTS,
                            default_slots, jazyky_hlasok, normalize_slot,
                            suggested_voice)

NOVE_NAVRHY = {"es": "es-ES-ElviraNeural", "de": "de-DE-KatjaNeural",
               "fr": "fr-FR-DeniseNeural", "pt": "pt-BR-FranciscaNeural"}


def _nic(*_a, **_k):
    return None


class _Root:
    """`root.after` bez Tk: uloha sa spusti, az ked ju test pusti."""

    def __init__(self):
        self.ulohy = {}
        self._n = 0

    def after(self, ms, fn):
        self._n += 1
        uid = "after#%d" % self._n
        self.ulohy[uid] = (ms, fn)
        return uid

    def after_cancel(self, uid):
        self.ulohy.pop(uid, None)

    def pusti(self):
        """Spusti vsetko, co prave caka (nie to, co pritom pribudne)."""
        cakajuce = list(self.ulohy.items())
        self.ulohy.clear()
        for _uid, (_ms, fn) in cakajuce:
            fn()


class _Cache:
    def __init__(self):
        self.hotove = set()

    def has(self, text, hlas, rate):
        return (text, hlas, rate) in self.hotove


@pytest.fixture
def edge(monkeypatch):
    import audio_engine
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)


def _appka(prace=(("Grounded", DEFAULT_EDGE_VOICE),
                  ("Breathe", DEFAULT_EDGE_VOICE))):
    """Ozajstne metody prveho startu a `start_listening` na DandurfApp bez
    Tk. Priprava hlasok je atrapa: `pregen_jobs` + cache."""
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root()
    a.engine = ENGINE_EDGE
    a.rate_value = 0
    a.edge_cache = _Cache()
    a.prace = list(prace)
    a.pregen_jobs = lambda: list(a.prace)
    a.listening = False
    a._prvy_start_caka = False
    a._prvy_start_job = None
    a._prvy_start_do = 0.0
    a.pasy = []
    a._refresh_kamae_state_text = lambda: a.pasy.append(a._prvy_start_caka)
    # to, co `start_listening` potrebuje (bez hodiniek, bez ovladaca)
    a.overlay_manager = types.SimpleNamespace(stop_all_tests=lambda: False)
    a.gamepad = types.SimpleNamespace(available=False, start=_nic)
    a.activity = types.SimpleNamespace(set_gamepad_watched=_nic)
    a.hr_monitoring_enabled = False
    a._resume_cue_trigger = _nic
    a.update_session_label = _nic
    a._apply_listening_visuals = _nic
    a.log = _nic
    a.update_tray_icon = _nic
    return a


def _priprav_vsetko(a):
    a.edge_cache.hotove.update((t, v, a.rate_value) for t, v in a.prace)


# --------------------------------------------------------------------------
# Kedy je hlas pripraveny
# --------------------------------------------------------------------------

def test_hlas_z_windows_alebo_bez_edge_necaka(monkeypatch):
    import audio_engine
    a = _appka()
    a.engine = ENGINE_SAPI
    assert a._hlas_pripraveny() is True
    a.engine = ENGINE_EDGE
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", False)
    assert a._hlas_pripraveny() is True


def test_hlas_pripraveny_az_ked_su_vsetky_hlasky_v_cache(edge):
    a = _appka()
    assert a._hlas_pripraveny() is False
    a.edge_cache.hotove.add(("Grounded", DEFAULT_EDGE_VOICE, 0))
    assert a._hlas_pripraveny() is False, "jedna hlaska este chyba"
    _priprav_vsetko(a)
    assert a._hlas_pripraveny() is True


def test_nic_na_pripravu_je_pripravene(edge):
    """Styl bez slov, Praca, vsetky hlasky vypnute: `pregen_jobs` je
    prazdne a niet na co cakat."""
    a = _appka(prace=())
    assert a._hlas_pripraveny() is True


# --------------------------------------------------------------------------
# Prvy start
# --------------------------------------------------------------------------

def test_hotovy_hlas_zacne_sledovat_hned_ako_doteraz(edge):
    a = _appka()
    _priprav_vsetko(a)
    a._zacni_sledovat_po_priprave_hlasu()
    assert a._prvy_start_caka is False and a.pasy == []
    [(ms, fn)] = a.root.ulohy.values()
    assert ms == 250
    a.root.pusti()
    assert a.listening is True


def test_kym_sa_pripravuje_nesleduje_a_pas_to_povie(edge):
    a = _appka()
    a._zacni_sledovat_po_priprave_hlasu()
    assert a.listening is False, "sledovanie by pripravu hned zastavilo"
    assert a._prvy_start_caka is True
    assert a.pasy == [True], "pas sa prepise hned"
    for _ in range(5):
        a.root.pusti()
    assert a.listening is False and a._prvy_start_caka is True
    assert len(a.root.ulohy) == 1, "caka sa dalej, jednou ulohou"


def test_po_priprave_zacne_sledovat_sama(edge):
    a = _appka()
    a._zacni_sledovat_po_priprave_hlasu()
    a.root.pusti()
    _priprav_vsetko(a)
    a.root.pusti()
    assert a.listening is True
    assert a._prvy_start_caka is False and a.pasy[-1] is False
    assert a.root.ulohy == {}


def test_nikdy_necaka_navzdy(edge):
    """Bez siete sa priprava nedokonci - po PRVY_START_MAX_S aj tak zacne."""
    import app as app_mod
    assert 0 < app_mod.DandurfApp.PRVY_START_MAX_S <= 15
    a = _appka()
    a._zacni_sledovat_po_priprave_hlasu()
    assert a._prvy_start_do - time.monotonic() <= a.PRVY_START_MAX_S + 0.5
    a.root.pusti()
    assert a.listening is False
    a._prvy_start_do = time.monotonic() - 0.01
    a.root.pusti()
    assert a.listening is True and a._prvy_start_caka is False
    assert a.root.ulohy == {}


def test_klik_hraca_pocas_cakania_nedostane_druhy_start(edge):
    """Hrac da ▶ a hned ■ - cakanie uz nesmie o chvilu zapnut sledovanie."""
    a = _appka()
    a._zacni_sledovat_po_priprave_hlasu()
    a.start_listening()                       # skutocny ▶
    assert a._prvy_start_caka is False
    assert a.root.ulohy == {}, "cakajuca uloha je zrusena"
    a.listening = False                       # ■
    _priprav_vsetko(a)
    a.root.pusti()
    assert a.listening is False


def test_hra_spustila_sledovanie_cakanie_skonci_bez_druheho_startu(edge):
    """Auto-profil zapne sledovanie pri starte hry - krok to len zisti."""
    a = _appka()
    a._zacni_sledovat_po_priprave_hlasu()
    starty = []
    a.start_listening = lambda: starty.append(True)
    a.listening = True
    a.root.pusti()
    assert starty == [] and a._prvy_start_caka is False
    assert a.root.ulohy == {}


def test_start_listening_rusi_cakanie_prveho_startu():
    telo = zdroj_metody("start_listening")
    assert "self._zrus_cakanie_prveho_startu()" in telo
    # az za `if self.listening: return` - beziace sledovanie nic nemeni
    assert (telo.index("if self.listening:\n            return")
            < telo.index("_zrus_cakanie_prveho_startu"))


def test_init_prveho_startu_caka_na_pripravu_spustenu_pred_nim():
    init = zdroj_metody("__init__")
    assert "self.root.after(250, self.start_listening)" not in init
    assert "self._zacni_sledovat_po_priprave_hlasu()" in init
    # priprava (`_load_edge_voices` -> `pregenerate`) sa spusta SKOR
    assert (init.index("self._load_edge_voices()")
            < init.index("self._zacni_sledovat_po_priprave_hlasu()"))


# --------------------------------------------------------------------------
# Stav na Dnes
# --------------------------------------------------------------------------

def test_stav_pocas_cakania_je_priprava_hlasu_nie_zastavene():
    import app as app_mod
    a = types.SimpleNamespace(listening=False, _prvy_start_caka=True,
                              _kamae_zastavene=lambda: ("stop", "klikni"))
    assert app_mod.DandurfApp._kamae_state_text(a) == (
        i18n.tr("kamae.voice_prep"), i18n.tr("kamae.voice_prep_sub"))
    a._prvy_start_caka = False
    assert app_mod.DandurfApp._kamae_state_text(a) == ("stop", "klikni")
    # stara atrapa bez atributu (ine testy) = ako doteraz
    b = types.SimpleNamespace(listening=False,
                              _kamae_zastavene=lambda: ("stop", ""))
    assert app_mod.DandurfApp._kamae_state_text(b) == ("stop", "")


def test_texty_cakania_vo_vsetkych_jazykoch_a_slovniku():
    for kluc in ("kamae.voice_prep", "kamae.voice_prep_sub"):
        zaznam = i18n.STRINGS[kluc]
        for jazyk in i18n.LANGUAGES:
            assert zaznam.get(jazyk, "").strip(), (kluc, jazyk)
    assert i18n.STRINGS["kamae.voice_prep"]["sk"] == "Pripravujem hlas"
    veta = i18n.STRINGS["kamae.voice_prep_sub"]["sk"]
    # hlavny vypinac = "sledovat", appka hovori v zenskom rode
    assert "sledovať" in veta and "sama" in veta
    assert "počúva" not in veta
    # bez vyzvy klikat: klik by pripravu zastavil
    assert "tlačidl" not in veta and "▶" not in veta


# --------------------------------------------------------------------------
# VOICE_HINTS pre es/de/fr/pt
# --------------------------------------------------------------------------

def _sloty(jazyk):
    povodny = i18n._lang["code"]
    i18n.set_lang(jazyk)
    try:
        return [normalize_slot(s) for s in default_slots()]
    finally:
        i18n.set_lang(povodny)


def test_nove_navrhy_su_pribalene_a_zenske():
    rod = {kod: r for kod, _, r in EDGE_FALLBACK_VOICES}
    for jazyk, hlas in NOVE_NAVRHY.items():
        assert VOICE_HINTS[jazyk] == hlas
        assert rod[hlas] == "f", hlas
        assert suggested_voice(jazyk) == hlas
        assert suggested_voice(jazyk, "en-US-GuyNeural") == "en-US-GuyNeural"


@pytest.mark.parametrize("jazyk", sorted(NOVE_NAVRHY))
def test_vstavane_slova_su_naozaj_v_tom_jazyku(jazyk):
    """Podmienka navrhu (0.2.1d): keby jazyk dostal anglicke slova, navrh by
    vratil presne tu chybu - cudzi hlas by cital "Grounded"."""
    assert jazyky_hlasok(_sloty(jazyk)) == {jazyk}
    assert jazyk not in jazyky_hlasok(_sloty("en"))


def test_anglicke_jazyky_navrh_nemaju():
    for jazyk in ("sk", "cs", "en"):
        assert jazyk not in VOICE_HINTS
        assert jazyky_hlasok(_sloty(jazyk)) == {"sk", "en", "cs"}


@pytest.fixture
def start(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def spusti(locale):
        monkeypatch.setattr(i18n, "_win_locale", lambda: locale)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield spusti
    i18n.set_lang(povodny)


@pytest.mark.parametrize("locale, jazyk", [
    ("de-DE", "de"), ("fr-FR", "fr"), ("es-ES", "es"), ("pt-BR", "pt"),
    ("de-AT", "de"), ("es-MX", "es")])
def test_prvy_start_dostane_hlas_svojich_slov(start, locale, jazyk):
    d = start(locale)
    assert d["edge_voice"] == NOVE_NAVRHY[jazyk]
    sloty = d["profiles"][0]["slots"]
    assert jazyky_hlasok(sloty) == {jazyk}, "hlas ide za slovami profilu"


def test_ulozeny_sonia_po_aktualizacii_ostava(start, tmp_path):
    """Existujuca instalacia s predvolenym hlasom sa pri starte nemeni -
    navrh pride az pri novom profile alebo prepnuti jazyka."""
    import app_prefs
    with open(app_prefs.SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump({"lang": "de", "theme": "zen",
                   "edge_voice": DEFAULT_EDGE_VOICE}, fh)
    assert start("de-DE")["edge_voice"] == DEFAULT_EDGE_VOICE


def _prepinac(monkeypatch, lang, hlas, sloty):
    import app as app_mod
    import ui_kit
    monkeypatch.setattr(ui_kit, "freeze_repaint", lambda *x: None)
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(lang=lang, edge_voice_id=hlas, engine=ENGINE_EDGE,
                              listening=False)
    a.slot_dicts = lambda: [dict(s) for s in sloty]
    a.root = types.SimpleNamespace(update_idletasks=lambda: None)
    for meno in ("save_settings", "pregenerate", "refresh_voice_box",
                 "_build_ui", "refresh_edge_banner", "_load_edge_voices",
                 "refresh_slot_summaries", "refresh_hr_status_label",
                 "_apply_listening_visuals", "_apply_overlay_labels",
                 "_apply_hud_labels", "log", "_refresh_guide_panel_theme"):
        setattr(a, meno, _nic)
    for meno in ("on_lang_switch", "_hlas_k_hlaskam"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    return a


@pytest.mark.parametrize("jazyk", sorted(NOVE_NAVRHY))
def test_prepnutie_s_anglickymi_slovami_necha_soniu(monkeypatch, jazyk):
    """Pravidlo z 0.2.1: hlas ide za slovami, nie za menu."""
    from app_spolocne import LANG_NATIVE_LABELS
    povodny = i18n._lang["code"]
    try:
        a = _prepinac(monkeypatch, "sk", DEFAULT_EDGE_VOICE, _sloty("sk"))
        a.on_lang_switch(LANG_NATIVE_LABELS[jazyk])
        assert a.lang == jazyk and a.edge_voice_id == DEFAULT_EDGE_VOICE
        b = _prepinac(monkeypatch, "en", DEFAULT_EDGE_VOICE, _sloty(jazyk))
        b.on_lang_switch(LANG_NATIVE_LABELS[jazyk])
        assert b.edge_voice_id == NOVE_NAVRHY[jazyk]
    finally:
        i18n.set_lang(povodny)
