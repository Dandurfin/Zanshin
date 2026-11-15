# -*- coding: utf-8 -*-
"""The "Update voice" button (0.3, the author's decision 15. 11. 2026).

Microsoft refused the old edge-tts and the fix was a change in the library's
code. The player downloads a newer edge-tts themselves: Settings → Sound, the
"Voice source" row, or Ctrl+K. The core (network, verification, test word,
module swap) is `hlas_kniznica.aktualizuj` - it is tested by
test_022h_hlas_kniznica.py. This file guards the GUI:
  * the button is in the "Voice source" row, only with the natural voice,
    and is disabled while the update runs; Ctrl+K has the same item,
  * while watching, nothing goes to the network even on a click (the core
    is not called at all) and the status says it will run after watching;
    it never starts by itself,
  * the core runs in a helper thread and Tk is touched only via `ui_call`,
  * every result has its own status (colour by theme), one journal line and
    a link to the official releases only when it takes a new Zanshin to
    fix the voice,
  * after success the cues that lack a voice are prepared
    (`pregenerate(force=True)`),
  * texts in 11 languages with the app's dictionary and the same
    {placeholders}.

No network: the core is always a dummy, and to be safe its network steps fail.
"""
import ast
import os
import re
import sys
import threading
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app as app_mod  # noqa: E402
import app_audio  # noqa: E402
import audio_engine  # noqa: E402
import hlas_kniznica as hk  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import strom_appky, zdroj_metody  # noqa: E402
from i18n import tr  # noqa: E402
from settings_model import ENGINE_EDGE, ENGINE_SAPI  # noqa: E402

import test_021b_pregen_len_co_zaznie as pregen  # noqa: E402

D = app_mod.DandurfApp
S = i18n.STRINGS
JAZYKY = i18n.LANGUAGES
PAL = theme.tokens(theme.ZEN)


@pytest.fixture(autouse=True)
def _bez_siete(monkeypatch):
    """No test here may go online - not even by mistake via the core."""
    def _nie(*_a, **_k):
        raise AssertionError("test siahol na siet")
    monkeypatch.setattr(hk, "_otvor", _nie)
    monkeypatch.setattr(hk, "_syntetizuj", _nie)


# --------------------------------------------------------------------------
# Dummies
# --------------------------------------------------------------------------

class _Widget:
    """Label / button / frame: only what the app uses of them."""

    def __init__(self, zabaleny=False):
        self.zabaleny = zabaleny
        self.cfg = {}
        self.pack_kw = None

    def configure(self, **kw):
        self.cfg.update(kw)

    def winfo_manager(self):
        return "pack" if self.zabaleny else ""

    def pack(self, **kw):
        self.zabaleny, self.pack_kw = True, kw

    def pack_forget(self):
        self.zabaleny = False


_METODY = ("aktualizuj_hlas", "_aktualizacia_hlasu_hotova", "_obnov_aktualizaciu_hlasu",
           "_ukaz_vydania_zanshinu", "_chyba_hlas_pripomienkam", "set_edge_status",
           "_ukaz_skusit_hlas_znova", "_zrus_rozbehnutu_pripravu", "otvor_vydania_zanshinu",
           "_priprava_po_neuspechu")


def _atrapa(monkeypatch, engine=ENGINE_EDGE, pocuva=False, chyba_hlas=False,
            vysledok=None, vlakno=True):
    """An app with the real "Update voice" flow and a dummy core.

    `a.stavy` = (text, colour) of every status, `a.denn` = the journal,
    `a.ui` = what goes to the GUI thread, `a.vlakna` = started threads
    (without starting them), `a.jadro` = calls of
    `hlas_kniznica.aktualizuj`."""
    a = types.SimpleNamespace(
        engine=engine, listening=pocuva, pal=PAL, rate_value=0,
        edge_status_label=_Widget(), edge_retry_btn=_Widget(),
        edge_update_row=_Widget(zabaleny=engine == ENGINE_EDGE),
        edge_update_btn=_Widget(), edge_releases_btn=_Widget(),
        _aktualizacia_hlasu_bezi=False, _pregen_po_aktualizacii=False, _pregen_seq=0,
        stavy=[], denn=[], ui=[], vlakna=[], pripravy=[], bannery=[], jadro=[],
        vysledok=vysledok or hk.Vysledok(hk.STAV_AKTUALNY, aktivna="7.3.1",
                                         najnovsia="7.3.1"))
    a.edge_cache = types.SimpleNamespace(has=lambda t, v, r: not chyba_hlas)
    a.pregen_jobs = lambda: [("Grounded", "en-GB-SoniaNeural")]
    a.ui_call = a.ui.append
    a.log = a.denn.append
    a.pregenerate = lambda force=False: a.pripravy.append(force)
    a.refresh_edge_banner = lambda: a.bannery.append(1)
    for meno in _METODY:
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    skutocny = a.set_edge_status

    def _stav(text, color=None):
        a.stavy.append((text, color))
        skutocny(text, color)
    a.set_edge_status = _stav

    def _jadro(**kw):
        a.jadro.append(kw)
        return a.vysledok
    monkeypatch.setattr(hk, "aktualizuj", _jadro)
    if vlakno:
        monkeypatch.setattr(app_audio.threading, "Thread",
                            lambda *x, **k: a.vlakna.append(k) or types.SimpleNamespace(
                                start=lambda: None))
    return a


def _dobehni(a):
    """The thread body in place, then everything it sent to the GUI thread."""
    a.vlakna[-1]["target"]()
    for fn in list(a.ui):
        fn()
    a.ui.clear()


def _vysledok(a, stav, **kw):
    a.vysledok = hk.Vysledok(stav, **kw)
    a.aktualizuj_hlas()
    _dobehni(a)


# --------------------------------------------------------------------------
# The button in the "Voice source" row and the Ctrl+K item
# --------------------------------------------------------------------------

def test_tlacidlo_je_v_riadku_zdroja_hlasu():
    stranka = zdroj_metody("_build_zvuk_page")
    assert 'rad = ctk.CTkFrame(row.text_col, fg_color="transparent")' in stranka
    assert re.search(r'self\.edge_update_btn = ui_kit\.button\(\s*rad, pal, '
                     r'tr\("edge\.update\.btn"\), kind="quiet",\s*'
                     r'command=self\.aktualizuj_hlas, height=28\)', stranka)
    # the releases link is external -> a chip with an arrow (design rule)
    assert 'ui_kit.chip(rad, pal, "↗ " + tr("edge.update.releases_btn"),' in stranka
    assert "self.otvor_vydania_zanshinu)" in stranka
    # the button is below the status and "Try again" - the "Voice source" row
    # is built before the "Voice" row
    assert (stranka.index("self.edge_status_label = ctk.CTkLabel(")
            < stranka.index("self.edge_retry_btn = ui_kit.button(")
            < stranka.index("self.edge_update_btn = ui_kit.button(")
            < stranka.index('tr("settings.voice")'))
    assert "self._obnov_aktualizaciu_hlasu()" in stranka


def test_atributy_su_v_init_pred_stavbou_okna():
    init = zdroj_metody("__init__")
    for meno in ("self.edge_update_row = None", "self.edge_update_btn = None",
                 "self.edge_releases_btn = None", "self._aktualizacia_hlasu_bezi = False",
                 "self._pregen_po_aktualizacii = False"):
        assert meno in init, meno
        assert init.index(meno) < init.index("self._build_ui()"), meno


def _paleta(engine, pocuva=False):
    volania = []
    a = types.SimpleNamespace(
        listening=pocuva, world="play", profiles=[], slots=[], engine=engine,
        sidebar=types.SimpleNamespace(_select=lambda k: volania.append(("select", k))),
        replay_onboarding=lambda: None, open_guide_panel=lambda: None,
        pregenerate=lambda **k: None, toggle_listening=lambda: None,
        minimize_to_tray=lambda: None,
        aktualizuj_hlas=lambda: volania.append(("aktualizuj",)))
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    return D._command_palette_items(a), volania


def test_ctrl_k_ma_aktualizovat_hlas_pri_prirodzenom_hlase():
    polozky, volania = _paleta(ENGINE_EDGE)
    nazvy = [p[0] for p in polozky]
    assert tr("edge.update.btn") in nazvy
    polozka = next(p for p in polozky if p[0] == tr("edge.update.btn"))
    assert polozka[1] == tr("palette.cat.sound")
    # right after "Prepare the cue voice"
    assert nazvy.index(tr("edge.update.btn")) == nazvy.index(tr("common.prepare_voices")) + 1
    assert volania == [], "postavenie palety nic nespusti"
    polozka[2]()
    # goes to Settings → Sound (status is there), runs the same method as the button
    assert volania == [("select", "zvuk"), ("aktualizuj",)]


def test_ctrl_k_bez_aktualizacie_pri_hlase_z_windows():
    polozky, _ = _paleta(ENGINE_SAPI)
    assert tr("edge.update.btn") not in [p[0] for p in polozky]
    assert tr("common.prepare_voices") in [p[0] for p in polozky]


@pytest.mark.parametrize("engine, vidno", [(ENGINE_EDGE, True), (ENGINE_SAPI, False)])
def test_riadok_vidno_len_pri_prirodzenom_hlase(monkeypatch, engine, vidno):
    a = _atrapa(monkeypatch, engine=engine)
    a.edge_update_row.zabaleny = not vidno
    a._obnov_aktualizaciu_hlasu()
    assert a.edge_update_row.zabaleny is vidno
    assert a.edge_update_btn.cfg["state"] == "normal"


def test_prepnutie_motora_riadok_prepocita_cez_refresh_voice_box():
    """`refresh_voice_box` is called after every engine change (the switch,
    "Try again" with edge-tts missing, a new introduction) - the row goes
    along with it."""
    assert "self._obnov_aktualizaciu_hlasu()" in zdroj_metody("refresh_voice_box")
    assert "self.refresh_voice_box()" in zdroj_metody("on_engine_change")


# --------------------------------------------------------------------------
# Nothing goes to the network while watching; never by itself
# --------------------------------------------------------------------------

def test_pocas_sledovania_sa_jadro_nezavola(monkeypatch):
    a = _atrapa(monkeypatch, pocuva=True)
    a.aktualizuj_hlas()
    assert a.jadro == [] and a.vlakna == [] and a.ui == []
    assert a.stavy == [(tr("edge.update.after_watching"), PAL["text_dim"])]
    assert not a._aktualizacia_hlasu_bezi
    assert a.denn == [], "nic sa neodklada - dennik nesluby aktualizaciu po hre"


def test_pri_hlase_z_windows_sa_nic_nedeje(monkeypatch):
    a = _atrapa(monkeypatch, engine=ENGINE_SAPI)
    a.aktualizuj_hlas()
    assert a.jadro == [] and a.vlakna == [] and a.stavy == []


def test_druhy_klik_pocas_behu_nic_nespusti(monkeypatch):
    a = _atrapa(monkeypatch)
    a.aktualizuj_hlas()
    a.aktualizuj_hlas()
    assert len(a.vlakna) == 1


def _odkazy_na(meno):
    """Names of the app's methods in which the attribute `meno` appears."""
    najdene = set()
    for trieda in strom_appky().body:
        if not isinstance(trieda, ast.ClassDef):
            continue
        for f in trieda.body:
            if not isinstance(f, ast.FunctionDef):
                continue
            if any(isinstance(u, ast.Attribute) and u.attr == meno for u in ast.walk(f)):
                najdene.add(f.name)
    return najdene


def test_aktualizacia_sa_nikdy_nespusti_sama():
    # a click (the button) and Ctrl+K - nothing else (app start, engine switch,
    # start/stop watching, cue preparation...)
    assert _odkazy_na("aktualizuj_hlas") == {"_build_zvuk_page", "_command_palette_items"}
    # the core is called only by `aktualizuj_hlas`
    assert _odkazy_na("aktualizuj") == {"aktualizuj_hlas"}
    stranka = zdroj_metody("_build_zvuk_page")
    assert "self.aktualizuj_hlas()" not in stranka
    assert "command=self.aktualizuj_hlas" in stranka


def test_prepnutie_na_prirodzeny_hlas_jadro_nezavola(monkeypatch):
    volania = []
    a = pregen._atrapa(monkeypatch, pregen._tri())
    monkeypatch.setattr(hk, "aktualizuj", lambda **kw: volania.append(kw))
    a.engine = a.engine_pref = ENGINE_SAPI
    a.engine_var = types.SimpleNamespace(get=lambda: i18n.tr("engine.edge"))
    a.edge_voice_map = {"Sonia": pregen.HLAS}
    a.on_engine_change()
    for vlakno in a.vlakna:
        vlakno["target"]()
    assert volania == []


# --------------------------------------------------------------------------
# Helper thread and GUI thread
# --------------------------------------------------------------------------

def test_klik_spusti_jadro_v_pomocnom_vlakne(monkeypatch):
    a = _atrapa(monkeypatch)
    seq = a._pregen_seq
    a.aktualizuj_hlas()
    assert a.jadro == [], "jadro blokuje - na GUI vlakne sa nevola"
    assert len(a.vlakna) == 1 and a.vlakna[0]["daemon"] is True
    # button disabled, the status says what is going on, a preparation that
    # is already running waits
    assert a._aktualizacia_hlasu_bezi
    assert a.edge_update_btn.cfg["state"] == "disabled"
    assert a.stavy[-1] == (tr("edge.update.running"), PAL["warn"])
    assert a._pregen_seq == seq + 1
    a.vlakna[0]["target"]()
    assert len(a.jadro) == 1
    kw = a.jadro[0]
    assert kw["cache"] is a.edge_cache and callable(kw["abort"])
    assert len(a.ui) == 1, "vysledok ide na GUI vlakno cez ui_call"
    assert a.edge_update_btn.cfg["state"] == "disabled", "az GUI vlakno tlacidlo zapne"
    a.ui[0]()
    assert not a._aktualizacia_hlasu_bezi
    assert a.edge_update_btn.cfg["state"] == "normal"


def test_vlakno_na_tk_nesiaha(monkeypatch):
    """A real thread: all the app does from the thread is `ui_call`. The
    status, the journal, the button and the preparation all run only on
    the main thread."""
    a = _atrapa(monkeypatch, chyba_hlas=True, vlakno=False,
                vysledok=hk.Vysledok(hk.STAV_AKTUALIZOVANY, aktivna="7.3.1", nova="7.4.0",
                                     najnovsia="7.4.0"))
    hlavne = threading.get_ident()
    cudzie = []

    def _strazca(meno, fn):
        def obal(*x, **k):
            if threading.get_ident() != hlavne:
                cudzie.append(meno)
            return fn(*x, **k)
        return obal
    for meno in ("set_edge_status", "log", "pregenerate", "refresh_edge_banner",
                 "_obnov_aktualizaciu_hlasu", "_ukaz_vydania_zanshinu"):
        setattr(a, meno, _strazca(meno, getattr(a, meno)))
    for meno in ("edge_update_btn", "edge_status_label", "edge_releases_btn", "edge_update_row"):
        w = getattr(a, meno)
        w.configure = _strazca(meno, w.configure)
        w.pack = _strazca(meno, w.pack)
        w.pack_forget = _strazca(meno, w.pack_forget)
    zdielane = threading.Lock()
    ui = []

    def _ui_call(fn):
        with zdielane:
            ui.append(fn)
    a.ui_call = _ui_call
    a.aktualizuj_hlas()
    cakanie = threading.Event()
    for _ in range(500):                    # at most ~5 s
        with zdielane:
            if ui:
                break
        cakanie.wait(0.01)
    assert ui, "vysledok neprisiel"
    assert len(a.jadro) == 1
    assert cudzie == [], cudzie
    for fn in ui:
        fn()
    assert a.stavy[-1] == (tr("edge.update.updated", version="7.4.0"), PAL["success"])
    assert a.pripravy == [True]


def test_abort_sa_pyta_na_sledovanie_aj_na_motor(monkeypatch):
    a = _atrapa(monkeypatch)
    a.aktualizuj_hlas()
    a.vlakna[0]["target"]()
    zrus = a.jadro[0]["abort"]
    assert zrus() is False
    a.listening = True
    assert zrus() is True
    a.listening = False
    a.engine = ENGINE_SAPI
    assert zrus() is True, "hlas z Windows nic neposiela - ani zvysok aktualizacie"


def test_vynimka_jadra_tlacidlo_nezamkne(monkeypatch):
    a = _atrapa(monkeypatch)

    def _pada(**_kw):
        raise RuntimeError("C:\\Users\\hrac\\x")
    monkeypatch.setattr(hk, "aktualizuj", _pada)
    a.aktualizuj_hlas()
    _dobehni(a)
    assert not a._aktualizacia_hlasu_bezi
    assert a.edge_update_btn.cfg["state"] == "normal"
    assert a.stavy[-1][0] == tr("edge.update.error")
    assert a.denn == [tr("log.edge_update.error")]
    assert "hrac" not in a.denn[0]


# --------------------------------------------------------------------------
# Results: status, colour, journal, releases link
# --------------------------------------------------------------------------

USPECH = PAL["success"]
VAROVANIE = PAL["danger_text"]

VYSLEDKY = [
    # status, status key, journal key, colour, link, version in the text
    (hk.STAV_AKTUALNY, "edge.update.up_to_date", "log.edge_update.up_to_date",
     USPECH, False, "7.3.1"),
    (hk.STAV_AKTUALIZOVANY, "edge.update.updated", "log.edge_update.updated",
     USPECH, False, "7.4.0"),
    (hk.STAV_STALE_ODMIETNUTY, "edge.update.refused_still", "log.edge_update.refused_still",
     VAROVANIE, True, "7.4.0"),
    (hk.STAV_OFFLINE, "edge.update.offline", "log.edge_update.offline",
     VAROVANIE, False, None),
    (hk.STAV_NEKOMPATIBILNY, "edge.update.incompatible", "log.edge_update.incompatible",
     VAROVANIE, True, None),
    (hk.STAV_OVERENIE_ZLYHALO, "edge.update.verify_failed", "log.edge_update.verify_failed",
     VAROVANIE, False, None),
    (hk.STAV_CHYBA, "edge.update.error", "log.edge_update.error", VAROVANIE, False, None),
    (hk.STAV_ZANEPRAZDNENY, "edge.update.error", "log.edge_update.error",
     VAROVANIE, False, None),
]


@pytest.mark.parametrize("stav, kluc, riadok, farba, odkaz, verzia", VYSLEDKY)
def test_vysledok_ma_svoj_stav_farbu_riadok_a_odkaz(monkeypatch, stav, kluc, riadok,
                                                    farba, odkaz, verzia):
    a = _atrapa(monkeypatch)
    nova = "7.4.0" if stav == hk.STAV_AKTUALIZOVANY else None
    najnovsia = "7.3.1" if stav == hk.STAV_AKTUALNY else "7.4.0"
    _vysledok(a, stav, aktivna="7.3.1", nova=nova, najnovsia=najnovsia,
              dovod="sha256 nesedi C:\\Users\\hrac\\voice_lib")
    text, f = a.stavy[-1]
    assert text == tr(kluc, version=verzia or "?")
    if "{version}" in S[kluc]["sk"]:
        assert verzia in text
    if "{version}" in S[riadok]["sk"]:
        assert verzia in a.denn[0]
    assert f == farba
    assert a.edge_releases_btn.zabaleny is odkaz
    assert len(a.denn) == 1, "jeden riadok dennika za vysledok"
    assert a.denn[0] == tr(riadok, version=verzia or "?")
    # the technical reason goes only to app.log (core), not to the player
    for vidi in (text, a.denn[0]):
        assert "sha256" not in vidi and "hrac" not in vidi and "voice_lib" not in vidi
    assert not a._aktualizacia_hlasu_bezi and a.edge_update_btn.cfg["state"] == "normal"


def test_odkaz_na_vydania_len_pre_novy_zanshin():
    odkazy = {stav for stav, (_k, _r, _ok, odkaz)
              in app_audio._VYSLEDKY_AKTUALIZACIE.items() if odkaz}
    assert odkazy == {hk.STAV_STALE_ODMIETNUTY, hk.STAV_NEKOMPATIBILNY}
    # every core status except "cancelled" has a sentence (busy falls back to
    # the generic one)
    assert set(app_audio._VYSLEDKY_AKTUALIZACIE) | {hk.STAV_ZRUSENY, hk.STAV_ZANEPRAZDNENY} == {
        getattr(hk, m) for m in dir(hk) if m.startswith("STAV_")}


def test_dalsi_stav_odkaz_schova(monkeypatch):
    a = _atrapa(monkeypatch)
    _vysledok(a, hk.STAV_STALE_ODMIETNUTY, aktivna="7.3.1", najnovsia="7.4.0")
    assert a.edge_releases_btn.zabaleny
    assert a.edge_releases_btn.pack_kw == {"side": "left", "padx": (8, 0)}
    a.set_edge_status(tr("edge.generating"), PAL["warn"])
    assert not a.edge_releases_btn.zabaleny
    # the next click (status "updating") hides it too
    _vysledok(a, hk.STAV_NEKOMPATIBILNY, aktivna="7.3.1", najnovsia="8.0.0")
    assert a.edge_releases_btn.zabaleny
    a.aktualizuj_hlas()
    assert not a.edge_releases_btn.zabaleny


@pytest.mark.parametrize("engine, cakany", [(ENGINE_EDGE, "edge.update.after_watching"),
                                            (ENGINE_SAPI, None)])
def test_zrusena_aktualizacia(monkeypatch, engine, cakany):
    a = _atrapa(monkeypatch)
    a.aktualizuj_hlas()
    a.listening = engine == ENGINE_EDGE
    a.engine = engine
    a.vysledok = hk.Vysledok(hk.STAV_ZRUSENY, aktivna="7.3.1")
    _dobehni(a)
    text, farba = a.stavy[-1]
    if cakany:
        assert (text, farba) == (tr(cakany), PAL["text_dim"])
    else:
        assert text == ""
    assert a.denn == [tr("log.edge_update.cancelled")]
    assert a.pripravy == [] and a.bannery == []
    assert not a.edge_releases_btn.zabaleny


# --------------------------------------------------------------------------
# After success, whatever is missing gets prepared
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stav", [hk.STAV_AKTUALIZOVANY, hk.STAV_AKTUALNY])
def test_po_uspechu_sa_pripravia_chybajuce_hlasky(monkeypatch, stav):
    a = _atrapa(monkeypatch, chyba_hlas=True)
    _vysledok(a, stav, aktivna="7.3.1", nova="7.4.0", najnovsia="7.4.0")
    assert a.pripravy == [True], "pregenerate(force=True)"
    assert a.bannery == [1], "EDGE_AVAILABLE mohlo prave ozit"


def test_ked_nic_nechyba_ostane_veta_o_aktualizacii(monkeypatch):
    a = _atrapa(monkeypatch, chyba_hlas=False)
    _vysledok(a, hk.STAV_AKTUALIZOVANY, aktivna="7.3.1", nova="7.4.0", najnovsia="7.4.0")
    assert a.pripravy == []
    assert a.stavy[-1] == (tr("edge.update.updated", version="7.4.0"), PAL["success"])


def test_zmena_pocas_aktualizacie_sa_pripravi_po_uspechu(monkeypatch):
    a = _atrapa(monkeypatch, chyba_hlas=False)
    a.aktualizuj_hlas()
    a._pregen_po_aktualizacii = True        # `pregenerate` waited for the result
    a.vysledok = hk.Vysledok(hk.STAV_AKTUALIZOVANY, aktivna="7.3.1", nova="7.4.0")
    _dobehni(a)
    assert a.pripravy == [True] and not a._pregen_po_aktualizacii


@pytest.mark.parametrize("stav", [hk.STAV_STALE_ODMIETNUTY, hk.STAV_OFFLINE,
                                  hk.STAV_NEKOMPATIBILNY, hk.STAV_OVERENIE_ZLYHALO,
                                  hk.STAV_CHYBA])
def test_po_neuspechu_sa_nic_nepripravuje(monkeypatch, stav):
    a = _atrapa(monkeypatch, chyba_hlas=True)
    a.aktualizuj_hlas()
    a._pregen_po_aktualizacii = True
    a.vysledok = hk.Vysledok(stav, aktivna="7.3.1", najnovsia="7.4.0")
    _dobehni(a)
    assert a.pripravy == [] and a.bannery == []
    assert not a._pregen_po_aktualizacii


def test_priprava_pocas_aktualizacie_caka(monkeypatch):
    """`pregenerate` in the middle of an update does not go to the network
    and does not overwrite the "updating the voice" status - the result
    starts the preparation by itself."""
    a = pregen._atrapa(monkeypatch, pregen._tri())
    a._aktualizacia_hlasu_bezi = True
    a._pregen_po_aktualizacii = False
    a.pregenerate(force=True)
    assert a.vlakna == [] and a.posielane == []
    # the status stays "updating the voice" (no preparation sentence)
    assert a.stavy == [tr("edge.update.running")]
    assert a._pregen_po_aktualizacii is True
    a._aktualizacia_hlasu_bezi = False
    a.pregenerate()
    assert len(a.vlakna) == 1, "po aktualizacii priprava ide normalne"


def test_prepnutie_na_windows_a_spat_vrati_stav_aktualizacie(monkeypatch):
    """0.3 verifier: in the middle of an update the player switched to the
    Windows voice (the status was cleared) and back. `on_engine_change`
    then calls `pregenerate` - the status must say "updating the voice"
    again, otherwise the button is disabled without a single word until
    the result. Meanwhile nothing goes to the network."""
    a = pregen._atrapa(monkeypatch, pregen._tri())
    a.engine_var = types.SimpleNamespace(get=lambda: a._zvoleny)
    a.edge_voice_map = {"Sonia": "en-GB-SoniaNeural"}
    a._aktualizacia_hlasu_bezi = True
    a._pregen_po_aktualizacii = False
    a._zvoleny = app_audio.engine_labels()[ENGINE_SAPI]
    a.on_engine_change()
    assert a.stavy[-1] == ""
    a._zvoleny = app_audio.engine_labels()[ENGINE_EDGE]
    a.on_engine_change()
    assert a.stavy[-1] == tr("edge.update.running")
    assert a.vlakna == [] and a.posielane == []
    assert a._pregen_po_aktualizacii is True


@pytest.mark.parametrize("stav", [hk.STAV_ZRUSENY, hk.STAV_STALE_ODMIETNUTY,
                                  hk.STAV_OFFLINE, hk.STAV_CHYBA])
def test_priprava_cakajuca_na_aktualizaciu_sa_pri_sledovani_odlozi_na_po_hre(
        monkeypatch, stav):
    """0.3 verifier: at game start the auto-profile switches the profile
    (`schedule_pregenerate` -> `pregenerate` waits for the update) and
    right away watching starts, which cancels the update. Until now the
    waiting preparation was thrown away on cancellation (and on other
    failures) - the new profile's cues were not prepared even after the
    game. Now it goes to after the game (`_pregen_po_hre`), without the
    network and without a status change."""
    a = _atrapa(monkeypatch, chyba_hlas=True)
    a._pregen_po_hre = False
    a.aktualizuj_hlas()
    a._pregen_po_aktualizacii = True        # `pregenerate` waited for the result
    a.listening = True                      # the game has started
    a.vysledok = hk.Vysledok(stav, aktivna="7.3.1", najnovsia="7.4.0")
    _dobehni(a)
    assert a._pregen_po_hre is True
    assert a.pripravy == [], "pocas sledovania sa nic nespusta"
    assert not a._pregen_po_aktualizacii
    if stav == hk.STAV_ZRUSENY:
        assert a.stavy[-1] == (tr("edge.update.after_watching"), PAL["text_dim"])


def test_zrusena_bez_sledovania_spusti_cakajucu_pripravu(monkeypatch):
    """Cancelled by switching to the Windows voice and back (not watching):
    the "only after watching" sentence would lie, and the waiting
    preparation runs right away - nothing else is to be shown. Under the
    Windows voice `pregenerate` does nothing anyway."""
    a = _atrapa(monkeypatch)
    a._pregen_po_hre = False
    a.aktualizuj_hlas()
    a._pregen_po_aktualizacii = True
    a.vysledok = hk.Vysledok(hk.STAV_ZRUSENY, aktivna="7.3.1")
    _dobehni(a)
    assert a.stavy[-1] == ("", None)
    assert a.pripravy == [False] and a._pregen_po_hre is False


@pytest.mark.parametrize("stav", [hk.STAV_AKTUALIZOVANY, hk.STAV_OFFLINE,
                                  hk.STAV_STALE_ODMIETNUTY, hk.STAV_NEKOMPATIBILNY])
def test_vysledok_po_prepnuti_na_windows_ide_len_do_dennika(monkeypatch, stav):
    """0.3 verifier: the player switched to the Windows voice in the middle
    of an update, after the last `abort` check (e.g. during the test word
    or a slow PyPI without a network). `on_engine_change` cleared the
    status; a result that arrives afterwards must not show it under the
    Windows voice - it goes only to the journal."""
    a = _atrapa(monkeypatch)
    a.aktualizuj_hlas()
    a.engine = ENGINE_SAPI                  # `on_engine_change` to Windows
    a.set_edge_status("")
    a._obnov_aktualizaciu_hlasu()
    a.vysledok = hk.Vysledok(stav, aktivna="7.3.1", nova="7.4.0", najnovsia="7.4.0")
    _dobehni(a)
    assert a.stavy[-1] == ("", None), "po prepnuti uz ziadny stav"
    assert not a.edge_status_label.zabaleny
    assert not a.edge_releases_btn.zabaleny
    assert len(a.denn) == 1, "jeden riadok dennika ostava"
    assert not a._aktualizacia_hlasu_bezi


# --------------------------------------------------------------------------
# The releases link and the version in app.log
# --------------------------------------------------------------------------

def test_odkaz_otvori_oficialne_vydania(monkeypatch):
    otvorene = []
    monkeypatch.setattr(app_audio.webbrowser, "open", lambda u, *x, **k: otvorene.append(u))
    a = _atrapa(monkeypatch)
    a.otvor_vydania_zanshinu()
    assert otvorene == ["https://github.com/Dandurfin/Zanshin/releases/latest"]
    assert otvorene[0] == hk.RELEASES_URL


def test_odkaz_ked_prehliadac_zlyha_nic_nezhodi(monkeypatch):
    def _pada(*_a, **_k):
        raise OSError("ziadny prehliadac")
    monkeypatch.setattr(app_audio.webbrowser, "open", _pada)
    _atrapa(monkeypatch).otvor_vydania_zanshinu()


def test_verzia_v_app_logu_je_stiahnuta_po_aktualizacii(monkeypatch):
    from importlib import metadata
    monkeypatch.setattr(metadata, "version", lambda _m: "7.3.1")
    monkeypatch.setattr(audio_engine, "EDGE_VERZIA", "7.4.0")
    monkeypatch.setattr(audio_engine, "EDGE_STIAHNUTY", True)
    assert app_audio._verzia_edge_tts() == "7.4.0 (stiahnuta)"
    monkeypatch.setattr(audio_engine, "EDGE_STIAHNUTY", False)
    assert app_audio._verzia_edge_tts() == "7.3.1", "pribalena = metadata"


# --------------------------------------------------------------------------
# Row layout: status above the button, link next to it
# --------------------------------------------------------------------------

def test_stav_ide_nad_riadok_aktualizacie(monkeypatch):
    a = _atrapa(monkeypatch)
    a.set_edge_status("! nieco", PAL["danger_text"])
    assert a.edge_status_label.pack_kw.get("before") is a.edge_update_row
    a._ukaz_skusit_hlas_znova(True)
    assert a.edge_retry_btn.pack_kw.get("after") is a.edge_status_label


def test_skusit_znova_bez_stavu_ide_nad_riadok(monkeypatch):
    a = _atrapa(monkeypatch)
    a._ukaz_skusit_hlas_znova(True)
    assert a.edge_retry_btn.pack_kw.get("before") is a.edge_update_row


def _tk_root():
    if sys.platform != "win32":
        pytest.skip("len Windows")
    import tkinter as tk
    import customtkinter as ctk
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("bez displeja")
    root.withdraw()
    return root


def test_poradie_v_riadku_so_skutocnym_tk(monkeypatch):
    """Real widgets (hidden window): name, status, "Try again" and only then
    the "Update voice" row; the button really gets disabled."""
    import customtkinter as ctk
    root = _tk_root()
    try:
        stlpec = ctk.CTkFrame(root)
        stlpec.pack()
        nazov = ctk.CTkLabel(stlpec, text="Zdroj hlasu")
        nazov.pack(fill="x")
        a = _atrapa(monkeypatch)
        a.edge_status_label = ctk.CTkLabel(stlpec, text="")
        a.edge_retry_btn = ui_kit.button(stlpec, PAL, tr("common.retry"), height=28)
        rad = ctk.CTkFrame(stlpec, fg_color="transparent")
        a.edge_update_row = rad
        a.edge_update_btn = ui_kit.button(rad, PAL, tr("edge.update.btn"), kind="quiet",
                                          height=28)
        a.edge_update_btn.pack(side="left")
        a.edge_releases_btn = ui_kit.chip(rad, PAL, "\u2197 " + tr("edge.update.releases_btn"))
        a._obnov_aktualizaciu_hlasu()
        assert stlpec.pack_slaves() == [nazov, rad]
        a.set_edge_status(tr("edge.partial_refused", ok=1, total=3), PAL["danger_text"])
        a._ukaz_skusit_hlas_znova(True)
        assert stlpec.pack_slaves() == [nazov, a.edge_status_label, a.edge_retry_btn, rad]
        a._ukaz_vydania_zanshinu(True)
        assert rad.pack_slaves() == [a.edge_update_btn, a.edge_releases_btn]
        a._aktualizacia_hlasu_bezi = True
        a._obnov_aktualizaciu_hlasu()
        assert str(a.edge_update_btn.cget("state")) == "disabled"
        a._aktualizacia_hlasu_bezi = False
        a.set_edge_status(tr("edge.update.running"), PAL["warn"])
        assert rad.pack_slaves() == [a.edge_update_btn]
        a._obnov_aktualizaciu_hlasu()
        assert str(a.edge_update_btn.cget("state")) == "normal"
        a.engine = ENGINE_SAPI
        a._obnov_aktualizaciu_hlasu()
        assert rad not in stlpec.pack_slaves()
    finally:
        root.destroy()


@pytest.mark.parametrize("jazyk", JAZYKY)
def test_tlacidlo_a_odkaz_sa_zmestia_do_riadku(jazyk):
    """Button + link side by side fit the row's text width (WRAP of the
    Sound page = 560 px), in every language. Without Tk the width is
    estimated."""
    font = ui_kit.ui(12)
    tlacidlo = ui_kit._sirka_textu(i18n.tr_lang(jazyk, "edge.update.btn"), font) + 28
    odkaz = ui_kit._sirka_textu("\u2197 " + i18n.tr_lang(jazyk, "edge.update.releases_btn"),
                                font) + 28
    assert tlacidlo + 8 + max(odkaz, 140) <= 560, (jazyk, tlacidlo, odkaz)
    assert "WRAP = 560" in zdroj_metody("_build_zvuk_page")


# --------------------------------------------------------------------------
# Texts
# --------------------------------------------------------------------------

NOVE_KLUCE = (
    "edge.update.btn", "edge.update.releases_btn", "edge.update.running",
    "edge.update.after_watching", "edge.update.up_to_date", "edge.update.updated",
    "edge.update.refused_still", "edge.update.offline", "edge.update.incompatible",
    "edge.update.verify_failed", "edge.update.error",
    "log.edge_update.up_to_date", "log.edge_update.updated", "log.edge_update.refused_still",
    "log.edge_update.offline", "log.edge_update.incompatible", "log.edge_update.verify_failed",
    "log.edge_update.error", "log.edge_update.cancelled")

S_VERZIOU = {"edge.update.up_to_date", "edge.update.updated", "log.edge_update.up_to_date",
             "log.edge_update.updated", "log.edge_update.refused_still"}

OFICIALNY = {"sk": "oficiáln", "cs": "oficiáln", "en": "official", "ja": "公式", "zh": "官方",
             "ru": "официальн", "bg": "официалн", "es": "oficial", "pt": "oficial",
             "de": "offiziell", "fr": "officiel"}
SLEDOVANIE = {"sk": "sledovanie", "cs": "sledování", "en": "watching", "ja": "見守り",
              "zh": "关注", "ru": "наблюдение", "bg": "следенето", "es": "observación",
              "pt": "observar", "de": "Beobachtung", "fr": "observation"}
PRIPOMIENKA = {"sk": "pripomien", "cs": "připomín", "en": "cue", "ja": "合図", "zh": "提示",
               "ru": "подсказ", "bg": "подсказ", "es": "aviso", "pt": "aviso",
               "de": "Hinweis", "fr": "rappel"}


def _placeholdery(text):
    return sorted(re.findall(r"\{(\w+)\}", text))


@pytest.mark.parametrize("kluc", NOVE_KLUCE)
def test_nove_texty_v_11_jazykoch_s_rovnakymi_placeholdermi(kluc):
    assert set(S[kluc]) == set(JAZYKY)
    cakane = ["version"] if kluc in S_VERZIOU else []
    for jazyk in JAZYKY:
        text = S[kluc][jazyk]
        assert text.strip() and text == text.strip(), (kluc, jazyk)
        assert _placeholdery(text) == cakane, (kluc, jazyk)
        assert "\\u" not in text, (kluc, jazyk)
        assert not re.search(r"https?:|github\.com|www\.", text), (kluc, jazyk)
        assert "PyPI" not in text, "hrac nepotrebuje meno skladu kniznic"
        if jazyk not in ("sk", "en") and S[kluc]["sk"] != S[kluc]["en"]:
            assert text != S[kluc]["en"], ("neprelozene", kluc, jazyk)
        hotovy = i18n.tr_lang(jazyk, kluc, version="7.4.0")
        assert "{" not in hotovy, (kluc, jazyk)


def test_stavy_maju_znacku_a_dennik_nie():
    for jazyk in JAZYKY:
        assert S["edge.update.running"][jazyk].startswith("⟳ "), jazyk
        for kluc in ("edge.update.up_to_date", "edge.update.updated"):
            assert S[kluc][jazyk].startswith("✓ "), (kluc, jazyk)
        for kluc in ("edge.update.refused_still", "edge.update.offline",
                     "edge.update.incompatible", "edge.update.verify_failed",
                     "edge.update.error"):
            assert S[kluc][jazyk].startswith("! "), (kluc, jazyk)
        for kluc in NOVE_KLUCE:
            if kluc.startswith("log."):
                assert S[kluc][jazyk][0] not in "⟳✓!", (kluc, jazyk)


@pytest.mark.parametrize("kluc", ["edge.update.refused_still", "edge.update.incompatible",
                                  "log.edge_update.refused_still",
                                  "log.edge_update.incompatible"])
def test_novy_zanshin_z_oficialneho_githubu(kluc):
    for jazyk in JAZYKY:
        text = S[kluc][jazyk]
        assert "GitHub" in text and "Releases" in text, (kluc, jazyk)
        assert OFICIALNY[jazyk] in text, (kluc, jazyk)
        assert "Zanshin" in text, (kluc, jazyk)


def test_po_sledovani_hovori_slovnikom_sledovania():
    for jazyk in JAZYKY:
        assert SLEDOVANIE[jazyk] in S["edge.update.after_watching"][jazyk], jazyk
        # the same phrase as for voice preparation after the game
        assert SLEDOVANIE[jazyk] in S["edge.after_game"][jazyk], jazyk
    assert not re.search(r"po[čc]úv|poslouch", S["edge.update.after_watching"]["sk"])


def test_dennik_hovori_o_pripomienkach_a_hlase_z_windows():
    for jazyk in JAZYKY:
        assert PRIPOMIENKA[jazyk] in S["log.edge_update.updated"][jazyk], jazyk
        assert "Windows" in S["log.edge_update.refused_still"][jazyk], jazyk
        assert "Windows" in S["log.edge_update.cancelled"][jazyk], jazyk
        for kluc in ("log.edge_update.verify_failed", "log.edge_update.error"):
            assert "app.log" in S[kluc][jazyk], (kluc, jazyk)


@pytest.mark.parametrize("kluc", ["edge.partial_refused", "log.edge_failed_refused"])
def test_odmietnutie_radi_najprv_aktualizovat_hlas(kluc):
    """The refusal sentence first points to the button - by name, exactly as
    on the button - and only then to a new Zanshin from the official
    GitHub."""
    for jazyk in JAZYKY:
        text = S[kluc][jazyk]
        tlacidlo = i18n.tr_lang(jazyk, "edge.update.btn")
        assert tlacidlo in text, (kluc, jazyk)
        assert text.index(tlacidlo) < text.index("GitHub"), (kluc, jazyk)
        assert "Releases" in text and OFICIALNY[jazyk] in text, (kluc, jazyk)


def test_rodove_tvary_appky():
    """Feminine forms for the app itself (sk, cs, ru) - as in the journal."""
    assert "som ho nepoužila" in S["edge.update.verify_failed"]["sk"]
    assert "zahodila" in S["log.edge_update.verify_failed"]["sk"]
    assert "aktualizovala" in S["log.edge_update.updated"]["sk"]
    assert "aktualizovala" in S["log.edge_update.updated"]["cs"]
    assert "обновила" in S["log.edge_update.updated"]["ru"]
    assert "прервала" in S["log.edge_update.cancelled"]["ru"]
