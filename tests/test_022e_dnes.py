# -*- coding: utf-8 -*-
"""The Today page after batch 4 of the UX audit (0.3).

Guarded:
  * the main switch is ONE button with text ("▶ Start watching" /
    "■ Stop watching") - the same words as the tray icon menu,
    primary when the app is stopped, secondary when it is watching,
    keyboard-operable (Enter, Space) and it toggles exactly the same as
    before,
  * the Ctrl+K palette says the same about the switch as the tray,
  * a busy heart-rate port has its own state with advice on Today (not
    "Waiting for heart rate"),
  * before the first session with heart rate, cards and zones with only
    dashes are hidden,
  * while the app is learning the heart-rate limit, Today shows a quiet
    "n of 3" sentence.

Only synthetic data. Tk is used only where a real widget is involved, and
only on Windows with a display.
"""
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody  # noqa: E402

JAZYKY = ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg")


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _today():
    import app_today
    return app_today.TodayMixin


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


# --------------------------------------------------------------------------
# Main switch: texts
# --------------------------------------------------------------------------

def test_tlacidlo_hovori_tie_iste_slova_ako_lista():
    """One switch, one name: the button in the bar = the item in the tray
    menu, only with the ▶ / ■ sign. In all 11 languages."""
    for jazyk in JAZYKY:
        start = i18n.tr_lang(jazyk, "dock.start")
        stop = i18n.tr_lang(jazyk, "dock.stop")
        assert start == "▶ " + i18n.tr_lang(jazyk, "tray.start"), jazyk
        assert stop == "■ " + i18n.tr_lang(jazyk, "tray.stop"), jazyk
        assert i18n.STRINGS["kamae.bar_hint"][jazyk].strip(), jazyk
    assert i18n.tr_lang("sk", "dock.start") == "▶ Spustiť sledovanie"
    assert i18n.tr_lang("sk", "dock.stop") == "■ Zastaviť sledovanie"
    assert i18n.tr_lang("en", "dock.start") == "▶ Start watching"
    assert i18n.tr_lang("en", "dock.stop") == "■ Stop watching"


def test_texty_pasu_su_na_jednom_mieste(sk):
    D = _app()
    assert D._texty_pasu() == (i18n.tr("dock.start"), i18n.tr("dock.stop"),
                               i18n.tr("kamae.bar_hint"))
    src = zdroj_appky()
    # The hint for the small icon ("Click ▶ on the left") and the bar heading
    # are gone - the keys are no longer in the dictionary or in the code.
    assert not re.search(r'tr\("kamae\.bar_(title|sub)"', src)
    assert "kamae.bar_title" not in i18n.STRINGS
    assert "kamae.bar_sub" not in i18n.STRINGS
    assert "self.kamae.set_texts(*self._texty_pasu())" in zdroj_metody("_build_dnes_page")


def test_prepis_pasu_nastavi_tlacidlo_a_bodku(sk):
    D = _app()
    volania = []

    class _Pas:
        def set_texts(self, *texty):
            volania.append(("pas", texty))

    a = types.SimpleNamespace(
        kamae=_Pas(), _texty_pasu=D._texty_pasu,
        _refresh_state_dot=lambda: volania.append(("bodka",)),
        _refresh_dnes_state_text=lambda: volania.append(("dnes",)))
    D._refresh_kamae_state_text(a)
    assert volania == [("pas", D._texty_pasu()), ("bodka",), ("dnes",)]


def test_vypinac_ide_jednou_cestou_s_listou():
    """The button, the tray, the palette and the game all toggle via
    start/stop_listening, and those always go through
    `_apply_listening_visuals` (button) and `update_tray_icon` (tray
    menu) - so they cannot drift apart."""
    vizual = zdroj_metody("_apply_listening_visuals")
    assert "self.kamae.set_live(self.listening)" in vizual
    for metoda in ("start_listening", "stop_listening"):
        telo = zdroj_metody(metoda)
        assert "self._apply_listening_visuals()" in telo, metoda
        assert "self.update_tray_icon()" in telo, metoda
    assert "on_toggle=self.toggle_listening" in zdroj_metody("_build_dnes_page")
    lista = zdroj_metody("setup_tray")
    assert 'tr("tray.stop") if getattr(self, "listening", False)' in lista


def _atrapa_palety(pocuva):
    D = _app()
    a = types.SimpleNamespace(
        listening=pocuva, world="play", profiles=[], slots=[],
        sidebar=types.SimpleNamespace(_select=lambda k: None),
        replay_onboarding=lambda: None, open_guide_panel=lambda: None,
        pregenerate=lambda **k: None, toggle_listening=lambda: None,
        minimize_to_tray=lambda: None)
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    return D._command_palette_items(a), a


def test_paleta_hovori_co_sa_stane_ako_lista(sk):
    for pocuva, kluc in ((False, "tray.start"), (True, "tray.stop")):
        polozky, a = _atrapa_palety(pocuva)
        nazvy = [p[0] for p in polozky]
        assert i18n.tr(kluc) in nazvy, pocuva
        prepinac = next(p for p in polozky if p[0] == i18n.tr(kluc))
        assert prepinac[2] is a.toggle_listening


# --------------------------------------------------------------------------
# Main switch: widget (Tk)
# --------------------------------------------------------------------------

def test_kamaebar_tlacidlo_primary_secondary_a_klavesnica(sk):
    import ui_kit
    root = _tk_root()
    bar = None
    try:
        prepnute = []
        pal = theme.tokens(theme.ZEN)
        start, stop, veta = _app()._texty_pasu()
        bar = ui_kit.KamaeBar(root, pal, on_toggle=lambda: prepnute.append(1),
                              start_label=start, stop_label=stop, hint=veta)
        bar.pack(fill="x")
        root.update_idletasks()
        assert bar.button_label() == start
        # keyboard-operable: Tab reaches the canvas, Enter and Space
        # toggle the same as a click
        assert str(bar.canvas.cget("takefocus")) == "1"
        for klaves in ("<Return>", "<KP_Enter>", "<space>"):
            assert bar.canvas.bind(klaves), klaves
        assert bar._key() == "break" and prepnute == [1]
        # drawing: stopped = primary (accent fill), watching = secondary
        bar._last_mierka = 1.0
        bar._build_items(520, 64, 1.0)
        bar._update_items(520, 64, 1.0, 0.0)
        assert bar._btn_stav[0] == "primary"
        assert bar.canvas.itemcget(bar._it["btn_text"], "text") == start
        assert bar.canvas.itemcget(bar._it["btn_text"], "fill") == pal["bg"]
        bar.set_live(True)
        assert bar.button_label() == stop
        bar._update_items(520, 64, 1.0, 0.3)
        assert bar._btn_stav[0] == "secondary"
        assert bar.canvas.itemcget(bar._it["btn_text"], "text") == stop
        assert bar.canvas.itemcget(bar._it["btn_text"], "fill") == pal["text"]
        # click: only into the button, not anywhere in the bar
        x0, y0, x1, y1 = bar._btn_rect
        bar._clicked(types.SimpleNamespace(x=(x0 + x1) / 2, y=(y0 + y1) / 2))
        assert prepnute == [1, 1]
        bar._clicked(types.SimpleNamespace(x=x1 + 200, y=(y0 + y1) / 2))
        assert prepnute == [1, 1]
        # the button width comes from the longer text - no jump on toggle
        sirka_sleduje = x1 - x0
        bar.set_live(False)
        bar._build_items(520, 64, 1.0)
        assert bar._btn_rect[2] - bar._btn_rect[0] == sirka_sleduje
    finally:
        if bar is not None:
            bar.stop()
        root.destroy()


# --------------------------------------------------------------------------
# Busy port
# --------------------------------------------------------------------------

def _atrapa_stavu(**kw):
    D = _app()
    a = types.SimpleNamespace(listening=True, hr_monitoring_enabled=True,
                              hr_port=4455, world="play", _hr_state="connecting",
                              _hr_last_bpm=None, _hr_lost=False, _cue_armed=False,
                              _kamae_zastavene=lambda: ("stop", ""))
    a.__dict__.update(kw)
    a._kamae_port_obsadeny = types.MethodType(D._kamae_port_obsadeny, a)
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    return D, a


@pytest.mark.parametrize("stav, prijem", [("busy", True), ("busy_gave_up", False)])
@pytest.mark.parametrize("pocuva", [True, False])
def test_obsadeny_port_ma_vlastny_stav_s_radou(sk, stav, prijem, pocuva):
    """During the retries ("busy") and after giving up ("busy_gave_up",
    receiving switched off only in memory) - and also when the app is not
    watching: heart rate from the phone will not arrive, whether it starts
    or not."""
    D, a = _atrapa_stavu(_hr_state=stav, hr_monitoring_enabled=prijem,
                         listening=pocuva, hr_port=4456)
    titul, veta = D._kamae_state_text(a)
    assert titul == i18n.tr("kamae.port_busy", port=4456) == "Port 4456 je obsadený"
    assert veta == i18n.tr("kamae.port_busy_sub", page=i18n.tr("nav.vhre_short"),
                           card=i18n.tr("settings.hr_section_title"))
    assert "OBS" in veta and "„V hre → Hodinky a tep“" in veta


def test_obsadeny_port_vo_svete_praca_menuje_obrazovku(sk):
    D, a = _atrapa_stavu(_hr_state="busy", world="work")
    _titul, veta = D._kamae_state_text(a)
    assert "„Obrazovka → Hodinky a tep“" in veta


def test_bez_obsadeneho_portu_plati_doterajsie_stavy(sk):
    D, a = _atrapa_stavu(_hr_state="no_client")
    assert D._kamae_state_text(a)[0] == i18n.tr("kamae.no_client")
    D, a = _atrapa_stavu(_hr_state="disconnected", hr_monitoring_enabled=False)
    assert D._kamae_state_text(a)[0] == i18n.tr("kamae.no_watch")
    D, a = _atrapa_stavu(_hr_state="disconnected", listening=False)
    assert D._kamae_state_text(a) == ("stop", "")


def test_veta_o_porte_vo_vsetkych_jazykoch():
    for jazyk in JAZYKY:
        titul = i18n.STRINGS["kamae.port_busy"][jazyk]
        veta = i18n.STRINGS["kamae.port_busy_sub"][jazyk]
        assert "{port}" in titul, jazyk
        # in Japanese and Chinese without spaces around the arrow: Tk breaks
        # the line at a space and the arrow would be left alone on a line
        sipka = "{page}→{card}" if jazyk in ("ja", "zh") else "{page} → {card}"
        assert sipka in veta and "OBS" in veta, jazyk
        assert "WebSocket" in veta, jazyk


# --------------------------------------------------------------------------
# Empty state before the first session with heart rate
# --------------------------------------------------------------------------

class _W:
    """A recording widget dummy with pack."""

    def __init__(self, zabaleny=True):
        self.m = "pack" if zabaleny else ""
        self.kw = {}
        self.cfg = {}

    def winfo_manager(self):
        return self.m

    def pack(self, **kw):
        self.m = "pack"
        self.kw = kw

    def pack_forget(self):
        self.m = ""

    def pack_configure(self, **kw):
        self.cfg.update(kw)


def _atrapa_dnes(session_count=0, historia=()):
    return types.SimpleNamespace(
        hr_stats=types.SimpleNamespace(session_count=session_count),
        _history_cached=lambda: list(historia),
        dnes_bpm_box=_W(), dnes_stats_head=_W(), dashboard_grid=_W(),
        dnes_zone_panel=_W(), dnes_zone_obsah=_W(), dnes_zone_empty=_W(False),
        dnes_live=_W(False), dnes_empty=_W(True))


def test_pred_prvou_relaciou_s_tepom_su_karty_a_pasma_schovane():
    T = _today()
    a = _atrapa_dnes()
    T._sync_dnes_prazdny_stav(a)
    for meno in ("dnes_bpm_box", "dnes_stats_head", "dashboard_grid", "dnes_zone_obsah"):
        assert getattr(a, meno).m == "", meno
    assert a.dnes_zone_empty.m == "pack"
    assert a.dnes_zone_panel.cfg == {"expand": False}
    # the empty state in the "Heart rate and load" panel (sentence + Pair your
    # watch) stays
    assert a.dnes_empty.m == "pack"


def test_prva_vzorka_tepu_vrati_plny_pohlad():
    T = _today()
    a = _atrapa_dnes()
    T._sync_dnes_prazdny_stav(a)
    a.hr_stats.session_count = 1
    T._sync_dnes_prazdny_stav(a)
    for meno in ("dnes_bpm_box", "dnes_stats_head", "dashboard_grid", "dnes_zone_obsah"):
        assert getattr(a, meno).m == "pack", meno
    assert a.dnes_zone_empty.m == ""
    assert a.dnes_zone_panel.cfg == {"expand": True}
    # order: the heart-rate number before the empty state / live block, the
    # header and the card grid before the zone panel
    assert a.dnes_bpm_box.kw.get("before") is a.dnes_empty
    assert a.dnes_stats_head.kw.get("before") is a.dnes_zone_panel
    assert a.dashboard_grid.kw.get("before") is a.dnes_zone_panel


def test_ulozena_relacia_v_historii_staci_na_plny_pohlad():
    T = _today()
    a = _atrapa_dnes(historia=[{"started": 1.0, "samples": 600}])
    assert T._dnes_ma_tep(a) is True
    T._sync_dnes_prazdny_stav(a)
    assert a.dnes_bpm_box.m == "pack" and a.dnes_zone_empty.m == ""


def test_prazdny_stav_sa_prestavuje_len_pri_zmene():
    T = _today()
    a = _atrapa_dnes()
    T._sync_dnes_prazdny_stav(a)
    a.dnes_zone_empty.m = ""            # if it were rebuilt on every sample,
    T._sync_dnes_prazdny_stav(a)        # it would bring it back
    assert a.dnes_zone_empty.m == ""


def test_atrapa_bez_cache_dostane_plny_pohlad():
    """Tests call `_refresh_dnes_stats` on dummies - those without history
    must not stay in the empty state."""
    T = _today()
    assert T._dnes_ma_tep(types.SimpleNamespace()) is True


def test_rozpinanie_panela_pasiem_nenasobi_okraje_a_drzi_poradie():
    import customtkinter as ctk
    T = _today()
    root = _tk_root()
    try:
        rodic = ctk.CTkFrame(root)
        rodic.pack(fill="both", expand=True)
        prvy = ctk.CTkFrame(rodic, height=20)
        prvy.pack(fill="x")
        panel = ctk.CTkFrame(rodic, height=40)
        panel.pack(fill="both", expand=True, pady=(12, 0))
        posledny = ctk.CTkFrame(rodic, height=20)
        posledny.pack(fill="x")
        okraj = panel.pack_info()["pady"]
        for rozpinaj in (False, True, False):
            T._rozpinaj(panel, rozpinaj)
            assert bool(int(panel.pack_info()["expand"])) is rozpinaj
            assert panel.pack_info()["pady"] == okraj
            assert rodic.pack_slaves() == [prvy, panel, posledny]
            # CTk remembers the new call (also for DPI changes) with an unscaled
            # margin
            assert panel._last_geometry_manager_call["kwargs"]["pady"] == (12, 0)
    finally:
        root.destroy()


def test_dnes_volaju_prazdny_stav_a_nova_stranka_ho_nastavi_znova():
    assert "TodayMixin._sync_dnes_prazdny_stav(self)" in zdroj_metody("_refresh_dnes_stats")
    stavba = zdroj_metody("_build_dnes_page")
    assert "self._dnes_ma_tep_stav = None" in stavba
    assert "self._dnes_learning_key = None" in stavba
    for meno in ("self.dnes_bpm_box", "self.dnes_stats_head", "self.dnes_zone_obsah",
                 "self.dnes_zone_empty = ui_kit.EmptyState("):
        assert meno in stavba, meno
    assert i18n.tr_lang("sk", "dnes.zones_empty") == "Pásma sa ukážu po prvej relácii s tepom."


# --------------------------------------------------------------------------
# Learning phase
# --------------------------------------------------------------------------

def _relacia(start, dlzka=1800.0, **kw):
    r = {"started": start, "duration_s": dlzka, "samples": int(dlzka),
         "curve": [70 + (i % 5) for i in range(200)]}
    r.update(kw)
    return r


def test_relacie_na_ucenie_ratanie_ako_veta_pri_senzore():
    T = _today()
    a = types.SimpleNamespace(ALGORITMUS_SVET="play")
    historia = [
        _relacia(1), _relacia(2),
        _relacia(3, dlzka=120.0),               # short - not learned from
        _relacia(4, world="work"),              # Work - not learned from
        _relacia(5, imported=True),             # someone else's body
        _relacia(6, setup=True),                # setting up the app
    ]
    assert T._relacie_na_ucenie(a, historia) == 2
    # the same rule as `_kriticky_popis` (the sentence below the sensor)
    rucne = len([r for r in hr_stats.ciste_relacie(hr_stats.sessions_in_world(historia, "play"))
                 if hr_stats.je_dost_dlha(r)])
    assert rucne == 2
    assert T._relacie_na_ucenie(a, [_relacia(i) for i in range(30)]) == \
        hr_stats.KRITICKY_MIN_RELACII


def _atrapa_ucenia(historia, svet="play", session_count=1):
    kresby = []
    a = types.SimpleNamespace(
        world=svet, ALGORITMUS_SVET="play",
        hr_stats=types.SimpleNamespace(session_count=session_count),
        _history_cached=lambda: historia,
        _refresh_dnes_backdrop=lambda _e=None, force=False: kresby.append(force),
        kresby=kresby)
    return a


def test_veta_o_uceni_n_z_troch(sk):
    T = _today()
    historia = [_relacia(1)]
    a = _atrapa_ucenia(historia)
    T._refresh_dnes_learning(a)
    assert a._dnes_learning_text == i18n.tr("dnes.learning", n=1, celkom=3)
    assert a._dnes_learning_text.startswith("Ešte ťa spoznávam — 1 z 3")
    assert a.kresby == [False]
    # the same history (cache) -> nothing is recomputed or redrawn
    T._refresh_dnes_learning(a)
    assert a.kresby == [False]


def test_veta_o_uceni_po_tretej_relacii_zmizne(sk):
    T = _today()
    a = _atrapa_ucenia([_relacia(1)])
    T._refresh_dnes_learning(a)
    assert a._dnes_learning_text
    a._history_cached = lambda h=[_relacia(i) for i in range(3)]: h
    T._refresh_dnes_learning(a)
    assert a._dnes_learning_text == ""


def test_veta_o_uceni_nie_je_v_praci_ani_pred_prvym_tepom(sk):
    T = _today()
    a = _atrapa_ucenia([_relacia(1)], svet="work")
    T._refresh_dnes_learning(a)
    assert getattr(a, "_dnes_learning_text", "") == ""
    b = _atrapa_ucenia([], session_count=0)
    T._refresh_dnes_learning(b)
    assert getattr(b, "_dnes_learning_text", "") == ""
    # the first heart rate has arrived, nothing is saved yet -> "0 of 3"
    c = _atrapa_ucenia([], session_count=5)
    T._refresh_dnes_learning(c)
    assert c._dnes_learning_text == i18n.tr("dnes.learning", n=0, celkom=3)


def test_veta_o_uceni_vo_vsetkych_jazykoch():
    for jazyk in JAZYKY:
        text = i18n.STRINGS["dnes.learning"][jazyk]
        assert "{n}" in text and "{celkom}" in text, jazyk
        assert "5" in text, jazyk
    assert "_dnes_learning_text" in zdroj_metody("_paint_dnes_canvas")
    assert "TodayMixin._refresh_dnes_learning(self)" in zdroj_metody("_refresh_dnes_stats")
