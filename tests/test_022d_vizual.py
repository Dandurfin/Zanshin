# -*- coding: utf-8 -*-
"""UX/UI and graphics per the 0.3 audit (section 2, "Unified design rules").

Guarded:
  * token contrast in BOTH themes (WCAG): content text >= 4.5:1, a
    secondary button's border >= 3:1, a divider line >= 1.5:1, a switch
    that is on differs from one that is off by at least 3:1,
  * one switch for the app (`ui_kit.switch`) - no bare `ctk.CTkSwitch(`
    outside ui_kit, on = `accent`,
  * four kinds of button (`ui_kit.button`) and their colours, natural width,
  * a 1 px divider line really is visible (`ui_kit.linka` has `bg_color`),
  * the side panel highlights the real page even when navigating from code,
    ⚙ by "Heart rate in game" leads to General, to the heart-rate panel
    section,
  * dialogs are centred and fit a low screen (1366x768 at 150 %),
  * a number carries the colour of the state, not of the metric (the
    heart-rate maximum is not `danger`),
  * the smallest font is 10, Japanese and Chinese have their own font,
  * a stopped app has no red dot, an unfilled slider does not look like 0.

All without a real window - Tk classes are replaced by recording dummies.
"""
import ast
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
import ui_shell  # noqa: E402
from _zdroj_appky import subory_appky, zdroj_metody, zdroj_suboru  # noqa: E402

TEMY = (theme.ZEN, theme.MODERN)


def _lum(farba):
    h = farba.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _kontrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


class _Zapis:
    """A Tk class dummy: remembers the arguments, draws nothing."""

    def __init__(self, *args, **kw):
        self.args, self.kw = args, kw


# --------------------------------------------------------------------------
# Token contrast
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", TEMY)
def test_obsahovy_text_je_citatelny(tema):
    pal = theme.tokens(tema)
    for token in ("text", "text_dim", "text_faint"):
        for pozadie in ("bg", "surface"):
            assert _kontrast(pal[token], pal[pozadie]) >= 4.5, (tema, token, pozadie)
    # even on a highlighted row (hover, selected session) at least 4.3:1
    assert _kontrast(pal["text_faint"], pal["surface_alt"]) >= 4.3


@pytest.mark.parametrize("tema", TEMY)
def test_hierarchia_textu_ostala(tema):
    """The lighter `text_faint` must not overtake `text_dim` - the order
    text > text_dim > text_faint still holds."""
    pal = theme.tokens(tema)
    assert _lum(pal["text"]) > _lum(pal["text_dim"]) > _lum(pal["text_faint"])


@pytest.mark.parametrize("tema", TEMY)
def test_ovladace_a_linky_maju_kontrast(tema):
    pal = theme.tokens(tema)
    assert _kontrast(pal["control_border"], pal["surface"]) >= 3.0
    assert _kontrast(pal["rule"], pal["surface"]) >= 1.5
    assert _kontrast(pal["danger_text"], pal["surface"]) >= 4.5
    # a switch that is on (accent) against one that is off (switch_off): before
    # 0.3 the on state had `accent2` and a contrast of 1.07:1
    assert _kontrast(pal["accent"], pal["switch_off"]) >= 3.0
    # dark text on the primary button
    assert _kontrast(pal["bg"], pal["accent"]) >= 4.5


def test_aizome_zastaveny_pas_nie_je_tepla_plocha():
    pal = theme.tokens(theme.MODERN)
    r, g, b = (int(pal["plate_idle_border"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    assert b > r, "ram zastaveneho pasu ma byt indigovy, nie hnedy"


def test_nove_tokeny_su_v_oboch_temach_a_v_mape_prefarbenia():
    import theme_recolor
    for token in ("rule", "control_border", "danger_text"):
        for tema in TEMY:
            assert token in theme.tokens(tema), (token, tema)
    mapa = theme_recolor.build_color_map(theme.tokens(theme.ZEN), theme.tokens(theme.MODERN))
    for token in ("rule", "control_border", "danger_text", "text_faint"):
        stara = theme.tokens(theme.ZEN)[token].lower()
        assert mapa[stara].lower() == theme.tokens(theme.MODERN)[token].lower(), token


# --------------------------------------------------------------------------
# One switch, four buttons, a visible line
# --------------------------------------------------------------------------

def test_ziadny_holy_ctkswitch_mimo_ui_kit():
    subory = subory_appky() + ["ui_dialogs.py", "ui_shell.py", "guide_panel.py",
                               "color_picker.py", "guided_tour.py"]
    for meno in subory:
        assert "ctk.CTkSwitch(" not in zdroj_suboru(meno), meno


def test_prepinac_zapnuty_je_v_akcente(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkSwitch", _Zapis)
    pal = theme.tokens(theme.ZEN)
    sw = ui_kit.switch(None, pal)
    assert sw.kw["progress_color"] == pal["accent"]
    assert sw.kw["fg_color"] == pal["switch_off"]
    assert sw.kw["button_color"] == pal["text"]
    assert sw.kw["switch_width"] == 36, "bez textu kompaktny"
    s_textom = ui_kit.switch(None, pal, text="Ukazat IP", font=ui_kit.ui(11))
    assert "switch_width" not in s_textom.kw
    assert s_textom.kw["progress_color"] == pal["accent"]


def test_vypnuty_prepinac_netvrdi_ze_funguje():
    pal = theme.tokens(theme.ZEN)
    volania = []
    sw = types.SimpleNamespace(configure=lambda **kw: volania.append(kw))
    ui_kit.nastav_prepinac_aktivny(sw, pal, False)
    assert volania[-1]["state"] == "disabled"
    assert volania[-1]["progress_color"] != pal["accent"]
    ui_kit.nastav_prepinac_aktivny(sw, pal, True)
    assert volania[-1]["progress_color"] == pal["accent"]


def test_styri_druhy_tlacidla(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkButton", _Zapis)
    pal = theme.tokens(theme.MODERN)
    primary = ui_kit.button(None, pal, "Ulozit", kind="primary", width=100)
    assert primary.kw["fg_color"] == pal["accent"] and primary.kw["text_color"] == pal["bg"]
    sec = ui_kit.button(None, pal, "Importovat", width=100)
    assert sec.kw["border_color"] == pal["control_border"] and sec.kw["border_width"] == 1
    danger = ui_kit.button(None, pal, "Zmazat", kind="danger", width=100)
    assert danger.kw["text_color"] == pal["danger_text"]
    assert danger.kw["border_color"] == pal["danger_text"]
    quiet = ui_kit.button(None, pal, "Vratit", kind="quiet", width=100)
    assert quiet.kw["border_width"] == 0
    for b in (primary, sec, danger, quiet):
        assert b.kw["corner_radius"] == ui_kit.RADIUS_CONTROL


def test_tlacidlo_ma_prirodzenu_sirku(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkButton", _Zapis)
    monkeypatch.setattr(ui_kit, "_sirka_textu", lambda text, font: 10 * len(text))
    pal = theme.tokens(theme.ZEN)
    kratke = ui_kit.button(None, pal, "Test")
    dlhe = ui_kit.button(None, pal, "Ako sparovat hodinky...")
    assert kratke.kw["width"] == 40 + 2 * ui_kit._BUTTON_PAD_X
    assert dlhe.kw["width"] > kratke.kw["width"]


def test_linka_je_vidno(monkeypatch):
    """A CTkFrame 1 px high drew a rectangle of zero height on a canvas in
    the parent's colour - the line was not visible at all. `bg_color`
    fixes that."""
    monkeypatch.setattr(ui_kit.ctk, "CTkFrame", _Zapis)
    pal = theme.tokens(theme.ZEN)
    linka = ui_kit.linka(None, pal)
    assert linka.kw["fg_color"] == linka.kw["bg_color"] == pal["rule"]
    assert linka.kw["height"] == 1


def test_deliace_linky_appky_idu_cez_linka():
    """No 1 px CTkFrame without `bg_color` (it would be invisible)."""
    vzor = re.compile(r'ctk\.CTkFrame\([^)]*height=1[,)]')
    for meno in subory_appky() + ["ui_dialogs.py", "ui_kit.py"]:
        for m in vzor.finditer(zdroj_suboru(meno)):
            kus = m.group(0)
            assert "bg_color" in kus or "width=" in kus or 'fg_color="transparent"' in kus, \
                (meno, kus)


def test_rozbalovacka_ma_pevnu_sirku_a_neoreze_text(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkOptionMenu", _Zapis)
    monkeypatch.setattr(ui_kit, "_sirka_textu", lambda text, font: 7 * len(text))
    pal = theme.tokens(theme.ZEN)
    kratka = ui_kit.option_menu(None, pal, values=["Hra", "Praca"])
    assert kratka.kw["width"] == ui_kit.CONTROL_W
    assert kratka.kw["dynamic_resizing"] is False
    dlha = ui_kit.option_menu(None, pal, values=["x" * 60])
    assert dlha.kw["width"] >= 7 * 60 + ui_kit._MENU_CHROME_W, "dlhy text sa neodreze"


def test_text_bez_emoji_ikony():
    assert ui_kit.bez_ikony("🥾 Ťažisko (drep/slide)") == "Ťažisko (drep/slide)"
    assert ui_kit.bez_ikony("🖱️ Uvoľnenie (myš)") == "Uvoľnenie (myš)"
    assert ui_kit.bez_ikony("Ťažisko (drep/slide)") == "Ťažisko (drep/slide)"
    assert ui_kit.bez_ikony("🫁 呼吸") == "呼吸"
    assert ui_kit.bez_ikony("+ Nový") == "+ Nový", "ASCII znamienko nie je ikona"
    assert ui_kit.bez_ikony("📋 Kopírovať kód profilu") == "Kopírovať kód profilu"
    assert ui_kit.bez_ikony("🗑") == "🗑", "samotny symbol ostane"


def test_vizualy_v_hre_kreslia_obrazok_z_hry_nie_emoji():
    stranka = zdroj_metody("_build_vhre_page")
    assert "icon_slot=vizualy[index]" in stranka
    assert "raw.partition(" not in stranka
    karta = zdroj_suboru("ui_dialogs.py")
    i = karta.index("class SlotCard")
    slot = karta[i:karta.index("\nclass ", i + 1)]
    # in-game slot 2 is the hand ("release"), not the eye from the Guide card
    assert '("grounding", "jaw", "release", "breath")' in slot
    assert "ui_kit.SlotIcon(col0, pal, vizualy[self.index]" in slot


# --------------------------------------------------------------------------
# Navigation
# --------------------------------------------------------------------------

class _Riadok:
    def __init__(self):
        self.aktivny = None

    def set_active(self, active):
        self.aktivny = active


def test_bocny_panel_zvyrazni_kartu_nastaveni():
    rows = {k: _Riadok() for k in ("dnes", "historia", "vhre", "nastavenia")}
    panel = types.SimpleNamespace(GROUPS=ui_shell.Sidebar.GROUPS, rows=rows)
    ui_shell.Sidebar.mark_active(panel, "vseobecne")
    assert rows["nastavenia"].aktivny is True
    assert rows["dnes"].aktivny is False


def test_navigacia_z_kodu_oznaci_panel():
    D = _app()
    oznacene, ukazane = [], []
    a = types.SimpleNamespace(
        TAB_ALIAS=D.TAB_ALIAS, SETTINGS_TABS=D.SETTINGS_TABS,
        pages=types.SimpleNamespace(show=ukazane.append),
        settings_pages=types.SimpleNamespace(show=ukazane.append),
        settings_nav=types.SimpleNamespace(set_active=lambda k: None),
        sidebar=types.SimpleNamespace(mark_active=oznacene.append))
    D._navigate(a, "vseobecne")
    assert ukazane == ["nastavenia", "vseobecne"]
    assert oznacene == ["vseobecne"], "ⓘ O appke musi rozsvietit Nastavenia"
    D._navigate(a, "historia")
    assert oznacene[-1] == "historia"


def test_ozubene_koliesko_pri_tepe_v_hre_vedie_na_hud():
    dnes = zdroj_metody("_build_dnes_page")
    assert "command=self.show_hud_settings" in dnes
    assert 'command=lambda: self._navigate("vhre")' not in dnes
    D = _app()
    kroky = []
    sekcia = types.SimpleNamespace(expanded=False,
                                   toggle=lambda: kroky.append("rozbal"))
    a = types.SimpleNamespace(
        hud_section=sekcia, _navigate=lambda k: kroky.append(("nav", k)),
        root=types.SimpleNamespace(after=lambda ms, fn: kroky.append(("po", ms))),
        _posun_vseobecne_na=lambda p: None)
    D.show_hud_settings(a)
    assert kroky[0] == ("nav", "vseobecne") and "rozbal" in kroky
    assert ("po", 80) in kroky
    assert "self.hud_section = hud_panel" in zdroj_metody("_build_ingame_sections_into")


def test_karty_nastaveni_su_text_s_linkou_nie_chipy():
    src = zdroj_suboru("ui_kit.py")
    i = src.index("class SubNav")
    subnav = src[i:src.index("\nclass ", i + 1)]
    assert "border_width=0" in subnav and "border_width=1" not in subnav
    assert 'pal["accent"] if active else "transparent"' in subnav


# --------------------------------------------------------------------------
# Dialogs: centred and on screen
# --------------------------------------------------------------------------

class _Tracker:
    deactivate_automatic_dpi_awareness = False

    def __init__(self, mierka):
        self.window_scaling = mierka
        self.widget_scaling = mierka


class _Top:
    def __init__(self):
        self.geo, self.min = None, None

    def geometry(self, text):
        self.geo = text

    def minsize(self, w, h):
        self.min = (w, h)


# 1366x768 at 150 %, a 72 px taskbar; the app already scaled down to 0.7
NIZKA_150 = display.Monitor(0, 0, 1366, 768, primary=True,
                            work=(0, 0, 1366, 696), dpi=144)


def test_parovaci_dialog_sa_zmesti_na_nizku_obrazovku(monkeypatch):
    monkeypatch.setattr(ui_kit, "_ctk_tracker", lambda: _Tracker(0.7))
    monkeypatch.setattr(ui_kit.display_mod, "monitor_at_cursor", lambda *_a: NIZKA_150)
    top = _Top()
    w, h = ui_kit.umiestni_dialog(top, object(), 560, 640, min_width=520, min_height=560)
    mierka = 1.5 * 0.7
    assert round(h * mierka) <= NIZKA_150.work_height - display.WINDOW_FIT_MARGIN_PX
    assert w == 560
    # minsize never bigger than what fits - else Tk would stretch the window
    assert top.min[1] <= h
    rozmer, x, y = top.geo.split("+")
    assert rozmer == f"{w}x{h}"
    assert int(y) >= NIZKA_150.work_y
    assert int(y) + round(h * mierka) <= NIZKA_150.work_y + NIZKA_150.work_height
    assert getattr(top, "_zanshin_umiestnene", False)


def test_na_velkej_obrazovke_sa_rozmer_nemeni(monkeypatch):
    velka = display.Monitor(0, 0, 1920, 1080, primary=True, work=(0, 0, 1920, 1032), dpi=96)
    monkeypatch.setattr(ui_kit, "_ctk_tracker", lambda: _Tracker(1.0))
    monkeypatch.setattr(ui_kit.display_mod, "monitor_at_cursor", lambda *_a: velka)
    top = _Top()
    assert ui_kit.umiestni_dialog(top, object(), 520, 760) == (520, 760)
    assert top.geo == "520x760+%d+%d" % ((1920 - 520) // 2, (1032 - 760) // 2)


def test_pevne_dialogy_pouzivaju_spolocneho_pomocnika():
    dialogy = zdroj_suboru("ui_dialogs.py")
    for stary in ('self.top.geometry("520x760")', 'self.top.geometry("660x680")',
                  'self.top.geometry(ui_kit.vycentrovana_geometria(app.root, 560, 640))'):
        assert stary not in dialogy, stary
    assert "ui_kit.umiestni_dialog(self.top, app.root, 520, 760" in dialogy
    assert "ui_kit.umiestni_dialog(self.top, self.app.root, 660, 680)" in dialogy
    sprievodca = zdroj_suboru("guide_panel.py")
    assert 'self.top.geometry("720x680")' not in sprievodca
    assert "ui_kit.umiestni_dialog(self.top, app.root, 720, 680" in sprievodca


def test_dialog_bez_rozmeru_sa_vycentruje():
    chrome = ast.unparse(next(
        n for n in ast.walk(ast.parse(zdroj_suboru("ui_kit.py")))
        if isinstance(n, ast.ClassDef) and n.name == "DialogChrome"))
    assert "vycentruj_podla_obsahu(top)" in chrome
    assert "_zanshin_umiestnene" in chrome


def test_zmazanie_historie_sa_potvrdzuje_v_okne_appky():
    telo = zdroj_metody("delete_history")
    assert "messagebox.askyesno(" not in telo
    # 0.3 batch 4: the question has three choices (Delete / Export first /
    # Cancel) and lives in `_spytaj_zmazanie` - `ui_kit.choose`, without it
    # `ui_kit.confirm`.
    assert "self._spytaj_zmazanie(" in telo
    otazka = zdroj_metody("_spytaj_zmazanie")
    assert '("delete", tr("data.delete.btn"), "danger")' in otazka
    assert "ui_kit.confirm(" in otazka and "danger=True" in otazka
    assert 'ok_label=tr("data.delete.btn")' in otazka


# --------------------------------------------------------------------------
# Colour, font, state
# --------------------------------------------------------------------------

def test_cislo_nesie_farbu_stavu_nie_metriky():
    D = _app()
    povolene = {"text", "zone_calm", "zone_high", "blue"}
    detail = dict((k, c) for k, _l, c in D.HISTORY_DETAIL_CELLS)
    assert detail["max"] == "text", "maximum tepu nie je poplach"
    assert set(detail.values()) <= povolene
    assert {c for _k, _t, c in D.HISTORY_METRICS} <= povolene
    katalog = {k: c for k, _t, c in D._dashboard_stat_catalog(types.SimpleNamespace())}
    assert katalog["max"] == "text" and katalog["peak"] == "text"
    assert set(katalog.values()) <= povolene
    assert "blue" not in {c for k, c in katalog.items() if k != "hrr"}


def test_najmensie_pismo_je_10():
    vzor = re.compile(r"\b(?:ui|mono|display)\((?:[0-9])\b(?![0-9])")
    for meno in subory_appky() + ["ui_kit.py", "ui_dialogs.py", "ui_shell.py",
                                  "guide_panel.py"]:
        najdene = vzor.findall(zdroj_suboru(meno))
        assert not najdene, (meno, najdene)


def test_japoncina_ma_vlastne_pismo(monkeypatch):
    import i18n
    monkeypatch.setattr(ui_kit, "_resolved", {})
    monkeypatch.setattr(ui_kit.tkfont, "families",
                        lambda *a, **k: ("Segoe UI Variable Text", "Yu Gothic UI",
                                         "Bahnschrift", "Consolas"))
    monkeypatch.setitem(i18n._lang, "code", "ja")
    assert ui_kit.ui(12)[0] == "Yu Gothic UI"
    assert ui_kit.display(12)[0] == "Yu Gothic UI"
    assert ui_kit.mono(12)[0] == "Consolas", "cisla ostavaju v monospace"
    assert ui_kit.ui(10)[1] == 11, "kanji pod 11 sa zlievaju"
    monkeypatch.setitem(i18n._lang, "code", "sk")
    assert ui_kit.ui(12)[0] == "Segoe UI Variable Text"
    assert ui_kit.ui(10)[1] == 10


def test_zastavena_appka_nema_cervenu_bodku():
    src = zdroj_suboru("ui_shell.py")
    i = src.index("class _StateDot")
    bodka = src[i:src.index("\nclass ", i + 1)]
    kresba = bodka[bodka.index("def _redraw"):]
    assert 'pal["danger"]' not in kresba
    assert "text_faint" in kresba


def test_nevyplneny_posuvnik_dotaznika_nevyzera_ako_nula():
    src = zdroj_suboru("ui_dialogs.py")
    i = src.index("class SessionEndDialog")
    dialog = src[i:src.index("\nclass ", i + 1)]
    vytvorenie = dialog[dialog.index("sl = ui_kit.block_slider_wheel("):dialog.index("sl.set(0)")]
    assert 'progress_color=pal["switch_off"]' in vytvorenie
    assert 'button_color=pal["switch_off"]' in vytvorenie
    dotyk = dialog[dialog.index("def _on_load"):]
    dotyk = dotyk[:dotyk.index("\n    def ")]
    assert 'progress_color=pal["accent"]' in dotyk


def test_karty_bez_tepu_ukazuju_pomlcku_nie_nulu():
    import hr_stats
    D = _app()
    a = types.SimpleNamespace(hr_stats=hr_stats.HeartStats(critical_bpm=110),
                              _hr_session_open=False, world="play",
                              _history_cached=lambda: [])
    for stat in ("baseline", "hrr", "over", "avg", "max", "peak"):
        assert D._dashboard_stat_value(a, stat)[0] == "—", stat
    # zero cues is a real value, not "we don't know"
    assert D._dashboard_stat_value(a, "breath")[0] == "0"


def test_jas_fotky_na_dnes_ide_za_sledovanim():
    D = _app()
    kroky = []
    a = types.SimpleNamespace(listening=True, _dnes_hero_on=True,
                              _start_dnes_hero=lambda: kroky.append("jasne"),
                              _stop_dnes_hero=lambda: kroky.append("tlmene"))
    D._sync_dnes_hero(a)
    assert kroky == ["tlmene"]
    a.listening, a._dnes_hero_on = False, False
    D._sync_dnes_hero(a)
    assert kroky == ["tlmene", "jasne"]
    a._dnes_hero_on = True
    D._sync_dnes_hero(a)
    assert kroky == ["tlmene", "jasne"], "bez zmeny sa neprekresluje"
    assert "self._sync_dnes_hero()" in zdroj_metody("_apply_listening_visuals")


def test_okraj_stranky_je_jeden():
    """Pages, the tab row and the breathing bar all start at `PAGE_GUTTER`,
    and the scrolling area does not indent the content by its radius."""
    assert ui_kit.PAGE_GUTTER == 24
    for meno in subory_appky():
        src = zdroj_suboru(meno)
        assert "padx=24, pady=(20, 20)" not in src, meno
    src = zdroj_suboru("ui_kit.py")
    stranka = src[src.index("def stranka_scroll"):]
    assert "corner_radius=0" in stranka[:stranka.index("\ndef ")]
    assert "padx=(0, ui_kit.SCROLLBAR_W)" in zdroj_metody("_build_dnes_page")
