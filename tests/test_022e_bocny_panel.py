# -*- coding: utf-8 -*-
"""The side panel and the status dot after batch 4 of the UX audit (0.3).

Guarded:
  * Settings and the magnifier (Ctrl+K) are in ONE group below "In-game" -
    nothing sits at the bottom of the panel any more, which could not be
    reached on a low screen,
  * the watch and the magnifier have a short visible label, and all labels
    fit the panel's width in all 11 languages,
  * the real page is highlighted (the Settings tab too),
  * the status dot has a fourth state "watching, but the heart rate dropped
    out" (a triangle in `danger_text`) that sets it apart from the amber
    "not now" ring,
  * in the Work world "V hre" (In-game) is called "Obrazovka" (Screen).
"""
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

JAZYKY = ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg")
POPISKY = ("nav.dnes", "nav.historia", "nav.vhre_short", "nav.vhre_work_short",
           "nav.nastavenia", "nav.search", "nav.watch")


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


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
# Texts
# --------------------------------------------------------------------------

def test_nove_popisky_su_vo_vsetkych_jazykoch():
    assert i18n.tr_lang("sk", "nav.watch") == "Hodinky"
    assert i18n.tr_lang("sk", "nav.search") == "Hľadať"
    assert i18n.tr_lang("sk", "nav.vhre_work_short") == "Obrazovka"
    assert i18n.tr_lang("en", "nav.vhre_work_short") == "Screen"
    for kluc in ("nav.watch", "nav.search", "nav.vhre_work_short", "nav.vhre_work"):
        for jazyk in JAZYKY:
            assert i18n.STRINGS[kluc][jazyk].strip(), (kluc, jazyk)
        # it is not copied English
        assert i18n.STRINGS[kluc]["de"] != i18n.STRINGS[kluc]["en"], kluc


def test_tip_bodky_opisuje_vsetky_styri_stavy():
    """Solid dot, triangle, dot in a ring, empty ring - every language must
    name the triangle (heart-rate dropout) and ▶ (how to start the app)."""
    trojuholnik = {"sk": "Trojuholník", "en": "Triangle", "ja": "三角", "zh": "三角形",
                   "ru": "Треугольник", "es": "Triángulo", "de": "Dreieck",
                   "fr": "Triangle", "pt": "Triângulo", "cs": "Trojúhelník",
                   "bg": "Триъгълник"}
    for jazyk in JAZYKY:
        tip = i18n.STRINGS["sidebar.state_tip"][jazyk]
        assert trojuholnik[jazyk] in tip, jazyk
        assert "▶" in tip, jazyk
    en = i18n.STRINGS["sidebar.state_tip"]["en"]
    for cast in ("Solid green dot", "Triangle", "Amber dot in a ring", "Hollow ring"):
        assert cast in en, cast


# --------------------------------------------------------------------------
# Label width
# --------------------------------------------------------------------------

def test_popisky_sa_zmestia_do_panela_vo_vsetkych_jazykoch():
    import tkinter.font as tkfont
    import ui_kit
    import ui_shell
    root = _tk_root()
    povodny = i18n._lang["code"]
    try:
        miesto = ui_shell.Sidebar.WIDTH - 2 * 8       # the row has padx=8 on both sides
        for jazyk in JAZYKY:
            i18n.set_lang(jazyk)
            rodina, velkost = ui_kit.ui(10)[:2]
            pismo = tkfont.Font(root=root, family=rodina, size=-velkost)
            for kluc in POPISKY:
                text = i18n.tr(kluc)
                assert pismo.measure(text) <= miesto, (jazyk, kluc, text,
                                                       pismo.measure(text))
    finally:
        i18n.set_lang(povodny)
        root.destroy()


# --------------------------------------------------------------------------
# Order and highlighting (Tk)
# --------------------------------------------------------------------------

def _postav_panel(root, labels=None):
    import ui_shell
    navigovane = []
    panel = ui_shell.Sidebar(
        root, on_navigate=navigovane.append, pal=theme.tokens(theme.ZEN),
        on_palette=lambda: navigovane.append("PALETA"),
        on_pair_watch=lambda: navigovane.append("PAROVANIE"),
        labels=labels or {"dnes": "Dnes", "historia": "História", "vhre": "V hre",
                          "nastavenia": "Nastavenia", "search": "Hľadať",
                          "watch": "Hodinky", "cmdk": "Hľadať a prepínať",
                          "state_tip": "tip"})
    panel.pack(side="left", fill="y")
    root.update_idletasks()
    return panel, navigovane


def test_nastavenia_a_lupa_su_v_jednej_skupine_pod_v_hre():
    root = _tk_root()
    try:
        panel, navigovane = _postav_panel(root)
        assert list(panel.rows) == ["dnes", "historia", "vhre", "nastavenia"]
        poradie = panel.pack_slaves()
        indexy = [poradie.index(w) for w in (
            panel.rows["dnes"], panel.rows["historia"], panel.rows["vhre"],
            panel.rows["nastavenia"], panel.cmdk_btn, panel.pair_btn)]
        assert indexy == sorted(indexy), "Dnes, Historia, V hre, Nastavenia, Hladat, Hodinky"
        # Nothing is stuck to the bottom of the panel (it could not be reached
        # there on a low screen).
        for widget in poradie:
            assert widget.pack_info().get("side") != "bottom", widget
        # the labels below the magnifier and the watch
        assert panel.cmdk_btn.label.cget("text") == "Hľadať"
        assert panel.pair_btn.caption.cget("text") == "Hodinky"
        # the magnifier opens the palette, does not navigate
        panel.cmdk_btn._clicked()
        assert navigovane[-1] == "PALETA"
        assert "hladat" not in panel.rows
    finally:
        root.destroy()


def test_zvyraznena_je_skutocna_stranka():
    root = _tk_root()
    try:
        panel, _ = _postav_panel(root)
        for kluc, aktivny in (("historia", "historia"), ("vseobecne", "nastavenia"),
                              ("zvuk", "nastavenia"), ("vhre", "vhre")):
            panel.mark_active(kluc)
            zasvietene = [k for k, rad in panel.rows.items() if rad.active]
            assert zasvietene == [aktivny], kluc
            assert not panel.cmdk_btn.active
    finally:
        root.destroy()


def test_popisok_v_hre_sa_da_prepisat_bez_prestavby():
    root = _tk_root()
    try:
        panel, _ = _postav_panel(root)
        panel.set_label("vhre", "Obrazovka")
        assert panel.rows["vhre"].label.cget("text") == "Obrazovka"
        assert panel.rows["vhre"].text == "Obrazovka"      # the bubble too
        panel.set_label("neexistuje", "x")                  # does not crash
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# Status dot: the fourth state
# --------------------------------------------------------------------------

def _typy(bodka):
    """[(item kind, colour)] - the colour is the fill, and when there is
    none (hollow ring, ring), the outline."""
    c = bodka.canvas
    vysledok = []
    for polozka in c.find_all():
        farba = c.itemcget(polozka, "fill") or c.itemcget(polozka, "outline")
        vysledok.append((c.type(polozka), farba))
    return vysledok


@pytest.mark.parametrize("tema", [theme.ZEN, theme.MODERN])
def test_bodka_vypadok_je_trojuholnik_v_danger_text(tema):
    import ui_shell
    root = _tk_root()
    try:
        pal = theme.tokens(tema)
        bodka = ui_shell._StateDot(root, pal, tip="ZAKLAD")
        bodka.pack()
        # stopped: hollow ring
        assert _typy(bodka) == [("oval", pal["text_faint"])]
        bodka.set_live(True)
        assert _typy(bodka) == [("oval", pal["success"])]
        bodka.set_lost(True)
        assert _typy(bodka) == [("polygon", pal["danger_text"])]
        # a dropout takes precedence even over "not now" (the player turned
        # that on themselves)
        bodka.set_snoozed(True, tip="do 21:45")
        assert _typy(bodka) == [("polygon", pal["danger_text"])]
        assert bodka._aktualny_tip() == "ZAKLAD"
        bodka.set_lost(False)
        typy = _typy(bodka)
        assert [t for t, _f in typy] == ["oval", "oval"], "prstenec + bodka"
        assert bodka._aktualny_tip() == "do 21:45"
        # a stopped app shows no dropout (not watching, nothing to drop out)
        bodka.set_snoozed(False)
        bodka.set_lost(True)
        bodka.set_live(False)
        assert _typy(bodka) == [("oval", pal["text_faint"])]
        # the triangle is readable in both themes (>= 3:1 on the panel
        # background)
        assert _kontrast(pal["danger_text"], pal["bg"]) >= 3.0
        # and differs from the amber "not now"
        assert pal["danger_text"].lower() != pal["warn"].lower()
    finally:
        root.destroy()


def _lum(farba):
    h = farba.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _kontrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class _Bodka:
    def __init__(self):
        self.lost = []

    def set_lost(self, lost):
        self.lost.append(lost)


@pytest.mark.parametrize("pocuva, prijem, vypadol, cakam", [
    (True, True, True, True),
    (False, True, True, False),      # stopped app
    (True, False, True, False),      # receiving switched off - that is not a dropout
    (True, True, False, False),
])
def test_appka_posiela_bodke_vypadok(pocuva, prijem, vypadol, cakam):
    import app_today
    bodka = _Bodka()
    a = types.SimpleNamespace(sidebar=types.SimpleNamespace(state_dot=bodka),
                              listening=pocuva, hr_monitoring_enabled=prijem,
                              _hr_lost=vypadol)
    app_today.TodayMixin._refresh_state_dot(a)
    assert bodka.lost == [cakam]


def test_bodka_sa_obnovi_pri_kazdej_zmene_stavu_tepu():
    """`_refresh_kamae_state_text` is called by every change of the
    heart-rate state and of watching - and it redraws the dot too."""
    assert "_refresh_state_dot" in zdroj_metody("_refresh_kamae_state_text")
    for metoda in ("_apply_hr_status", "_apply_hr_bpm", "stop_heart_rate_monitor",
                   "_apply_listening_visuals"):
        assert "self._refresh_kamae_state_text()" in zdroj_metody(metoda), metoda


def test_vypadok_pozna_appka_uz_davno():
    """The dot measures nothing new - it reads `_hr_lost` from
    `_zaznamenaj_vypadok`."""
    telo = zdroj_metody("_zaznamenaj_vypadok")
    assert "self._hr_lost = True" in telo
    assert "self._hr_lost = False" in zdroj_metody("_tep_je_spat")
    assert "_hr_lost" in zdroj_metody("_hodinky_vypadli")


# --------------------------------------------------------------------------
# The Work world: "Obrazovka" (Screen)
# --------------------------------------------------------------------------

def test_v_hre_sa_vo_svete_praca_vola_obrazovka(sk):
    D = _app()
    hra = types.SimpleNamespace(world="play")
    praca = types.SimpleNamespace(world="work")
    assert D._nazov_vhre(hra) == "V hre"
    assert D._nazov_vhre(praca) == "Obrazovka"
    assert D._nazov_vhre(hra, dlhy=True) == i18n.tr("nav.vhre")
    assert D._nazov_vhre(praca, dlhy=True) == "Hodinky a obrazovka"


def test_prepnutie_sveta_prepise_popisok_a_stav(sk):
    D = _app()
    volania = []
    a = types.SimpleNamespace(
        world="work",
        sidebar=types.SimpleNamespace(set_label=lambda k, t: volania.append((k, t))),
        _refresh_kamae_state_text=lambda: volania.append("stav"))
    a._nazov_vhre = types.MethodType(D._nazov_vhre, a)
    D._sync_world_nazvy(a)
    assert volania == [("vhre", "Obrazovka"), "stav"]
    assert "_sync_world_nazvy" in zdroj_metody("set_world")
    assert '"vhre": self._nazov_vhre()' in zdroj_metody("_build_ui")
    assert "self._nazov_vhre(dlhy=True)" in zdroj_metody("_command_palette_items")


def test_sidebar_zdroj_nema_spodny_blok():
    shell = zdroj_suboru("ui_shell.py")
    sidebar = shell[shell.index("class Sidebar"):shell.index("def kresli_nav_ikonu")]
    assert 'side="bottom"' not in sidebar
    assert "for key, icon, default_label in self.PAGES:" in sidebar
