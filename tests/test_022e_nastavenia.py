# -*- coding: utf-8 -*-
"""Settings and visual leftovers (0.3, batch 4 of the UX audit).

  * Sound: "How I speak up" is the first row of the Loudness panel, not
    its own card for one sentence (one panel less, the same behaviour),
  * Panel: heading -> line -> body 8 px apart; a line only BETWEEN rows,
    not under the last one (there it lay right above the panel frame),
  * no line above the Guide card, the profile bar on the same edge as the
    cards below it, one slider style across the whole app,
  * the cue card shows the fixed category name above the phrase,
  * Aizome: calm (`zone_calm`) is no longer blue - blue belongs to
    recovery,
  * the Guide window without emoji in the title.

No window - the Tk classes are dummies.
"""
import ast
import colorsys
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import uzol_metody, zdroj_suboru  # noqa: E402


def _metoda(subor, trieda, meno):
    strom = ast.parse(zdroj_suboru(subor))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == meno:
                    return f
    raise AssertionError(f"{trieda}.{meno} v {subor} chyba")


def _volania(uzol, meno):
    return [u for u in ast.walk(uzol) if isinstance(u, ast.Call)
            and ast.unparse(u.func) == meno]


# --------------------------------------------------------------------------
# Sound: "How I speak up" in the Loudness panel
# --------------------------------------------------------------------------

def test_styl_hlasky_je_prvy_riadok_panela_hlasitost():
    stranka = uzol_metody("_build_zvuk_page")
    panely = _volania(stranka, "ui_kit.Panel")
    assert len(panely) == 2, "Hlas + Hlasitost, ziadna karta pre jednu vetu"
    assert [ast.unparse(p.args[2]) if len(p.args) > 2 else ast.unparse(p.keywords[0].value)
            for p in panely] == ["tr('settings.audio_voice_title')",
                                 "tr('settings.audio_volume_title')"]
    riadky = [ast.unparse(r) for r in _volania(stranka, "ui_kit.SettingRow")]
    hlasitost = [r for r in riadky if r.startswith("ui_kit.SettingRow(loud_panel.body")]
    assert "tr('settings.cue_style')" in hlasitost[0], "prvy riadok panela"
    assert "tr('settings.volume')" in hlasitost[1]
    assert not any("styl_panel" in r for r in riadky)


def test_styl_hlasky_sa_sprava_rovnako():
    text = ast.unparse(uzol_metody("_build_zvuk_page"))
    assert "self.cue_style_var = tk.StringVar(" in text
    assert "values=self._cue_style_labels()" in text
    assert "command=self._on_cue_style_label" in text


# --------------------------------------------------------------------------
# Panel and divider lines
# --------------------------------------------------------------------------

def test_panel_rozostupy_8_px():
    init = ast.unparse(_metoda("ui_kit.py", "Panel", "__init__"))
    assert "rule.pack(fill='x', pady=(8, 0))" in init
    assert "pady=(8 if title is not None else 14, 14)" in init


class _Linka:
    def __init__(self):
        self.vidno = True

    def pack(self, **kw):
        self.vidno = True

    def pack_forget(self):
        self.vidno = False


def _riadok():
    r = ui_kit.SettingRow.__new__(ui_kit.SettingRow)
    r.deliaca_linka = _Linka()
    r._linka_vidno = True
    return r


class _Rodic:
    def __init__(self, deti):
        self.deti = deti

    def pack_slaves(self):
        return list(self.deti)


def test_linka_len_medzi_riadkami():
    a, b, c = _riadok(), _riadok(), _riadok()
    veta = object()                       # e.g. the voice preparation status
    rodic = _Rodic([a, b, veta, c])
    ui_kit.SettingRow.obnov_linky(rodic)
    assert a.deliaca_linka.vidno and b.deliaca_linka.vidno
    assert not c.deliaca_linka.vidno, "pod poslednym riadkom panela linka nie je"
    # another row was added: c is no longer the last - the line comes back
    d = _riadok()
    rodic.deti.append(d)
    ui_kit.SettingRow.obnov_linky(rodic)
    assert c.deliaca_linka.vidno and not d.deliaca_linka.vidno
    # a repeated call changes nothing
    ui_kit.SettingRow.obnov_linky(rodic)
    assert c.deliaca_linka.vidno and not d.deliaca_linka.vidno


def test_riadok_za_ktorym_nieco_je_linku_ma():
    a = _riadok()
    rodic = _Rodic([a, object()])         # a button under the row
    ui_kit.SettingRow.obnov_linky(rodic)
    assert a.deliaca_linka.vidno


def test_obnova_liniek_nikdy_nevyhodi():
    class _Zly:
        def pack_slaves(self):
            raise RuntimeError("okno zaniklo")

    ui_kit.SettingRow.obnov_linky(_Zly())


def test_linky_sa_prepocitaju_pri_zmene_rodica():
    """`after_idle` alone was not enough: a dropdown in the next row calls
    `update_idletasks` and the check finished before the next row existed -
    the lines disappeared even between rows (screenshot of the Sound page)."""
    init = ast.unparse(_metoda("ui_kit.py", "SettingRow", "__init__"))
    assert "tk.Misc.bind(master, '<Configure>'" in init
    assert "SettingRow.obnov_linky(m)" in init


def test_ziadna_linka_nad_kartou_sprievodcu():
    text = ast.unparse(uzol_metody("_build_spustace_page"))
    pred = text[:text.index("self._build_guide_into(wrap, pal)")]
    posledny = pred.rstrip().splitlines()[-1]
    assert "ui_kit.linka" not in posledny
    assert "ctk.CTkFrame(wrap, fg_color='transparent', height=16)" in posledny


# --------------------------------------------------------------------------
# Left edge, sliders
# --------------------------------------------------------------------------

def test_lista_profilu_na_hrane_kariet_pripomienok():
    stranka = ast.unparse(uzol_metody("_build_spustace_page"))
    assert "inner.pack(fill='x', padx=16, pady=11)" in stranka
    assert "auto_row.pack(fill='x', padx=16, pady=(0, 11))" in stranka
    karta = ast.unparse(_metoda("ui_dialogs.py", "SlotCard", "__init__"))
    assert "grid.pack(fill='x', padx=16, pady=12)" in karta


def test_jeden_styl_posuvnika(monkeypatch):
    zaznam = {}

    class _Slider:
        def __init__(self, master, **kw):
            zaznam.update(kw)

        def bind(self, *a, **k):
            pass

    monkeypatch.setattr(ui_kit.ctk, "CTkSlider", _Slider)
    pal = theme.tokens(theme.MODERN)
    ui_kit.slider(None, pal, from_=0, to=100)
    assert zaznam["progress_color"] == zaznam["button_color"] == pal["accent"]
    assert zaznam["fg_color"] == pal["switch_off"]
    assert zaznam["button_hover_color"] == pal["accent_hover"]


def test_okno_obrazkov_ma_posuvniky_jednym_stylom():
    strom = ast.parse(zdroj_suboru("ui_dialogs.py"))
    okno = next(u for u in strom.body
                if isinstance(u, ast.ClassDef) and u.name == "OverlaySettingsDialog")
    assert not _volania(okno, "ctk.CTkSlider")
    posuvniky = _volania(okno, "ui_kit.slider")
    # size, X, Y, breath and the limit of the ring at high heart rate
    assert len(posuvniky) == 5
    for p in posuvniky:
        farby = {k.arg for k in p.keywords} & {"progress_color", "button_color",
                                               "fg_color", "button_hover_color"}
        assert not farby, "X/Y mali vlastnu tmavu vypln accent2"
    # "Close" is the app's secondary button, not an accent2 fill in CTk font
    zavriet = [ast.unparse(c) for c in _volania(okno, "ui_kit.button")]
    assert any("tr('common.close')" in c for c in zavriet)


def test_nastavenia_appky_pouzivaju_jeden_posuvnik():
    for meno in ("_build_zvuk_page", "_build_ingame_sections_into"):
        text = ast.unparse(uzol_metody(meno))
        assert "ctk.CTkSlider(" not in text, meno
        assert "ui_kit.slider(" in text, meno


# --------------------------------------------------------------------------
# Cue card: fixed category name
# --------------------------------------------------------------------------

def test_karta_ukazuje_nazov_kategorie_pred_frazou():
    karta = ast.unparse(_metoda("ui_dialogs.py", "SlotCard", "__init__"))
    nazov = karta.index("tr(f'overlay.slot.{self.index}')")
    assert nazov < karta.index("self.entry = ctk.CTkEntry(")
    blok = karta[karta.index("self.category_label = None"):nazov]
    assert "if je_kategoria(self.index):" in blok
    assert "text_dim" in karta[nazov:karta.index("self.entry = ctk.CTkEntry(")]


def test_nazvy_kategorii_vo_vsetkych_jazykoch_bez_emoji():
    for i in range(4):
        zaznam = i18n.STRINGS[f"overlay.slot.{i}"]
        assert set(zaznam) == set(i18n.LANGUAGES)
        for jazyk, text in zaznam.items():
            assert text.strip() and ui_kit.bez_ikony(text) == text, (i, jazyk)
    assert [i18n.STRINGS[f"overlay.slot.{i}"]["sk"] for i in range(4)] == [
        "Ťažisko", "Čeľusť", "Ruka a pohľad", "Dych"]


# --------------------------------------------------------------------------
# Aizome: calm is not blue
# --------------------------------------------------------------------------

def _odtien(farba):
    r, g, b = (int(farba.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360.0


def _jas(farba):
    kanaly = [int(farba.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    kanaly = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in kanaly]
    return 0.2126 * kanaly[0] + 0.7152 * kanaly[1] + 0.0722 * kanaly[2]


def _kontrast(a, b):
    la, lb = _jas(a), _jas(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("tema", [theme.ZEN, theme.MODERN])
def test_pokoj_nie_je_modry_ako_zotavenie(tema):
    pal = theme.tokens(tema)
    pokoj = pal["zone_calm"]
    assert pokoj.lower() != pal["blue"].lower()
    assert abs(_odtien(pokoj) - _odtien(pal["blue"])) >= 30, \
        "karta Pokojovy tep vedla karty Zotavenie - dve modre"
    assert 60 <= _odtien(pokoj) < 180, "zelenkavy rad ako matcha v Sumi"
    assert pokoj.lower() != pal["success"].lower(), "stav nie je pasmo"
    assert _kontrast(pokoj, pal["surface"]) >= 4.5


def test_karty_pokoja_a_zotavenia_maju_rozne_tokeny():
    D = __import__("app").DandurfApp
    detail = {k: c for k, _l, c in D.HISTORY_DETAIL_CELLS}
    assert detail["calm"] == "zone_calm" and detail["hrr"] == "blue"
    katalog = {k: c for k, _t, c in D._dashboard_stat_catalog(types.SimpleNamespace())}
    assert katalog["baseline"] == "zone_calm" and katalog["hrr"] == "blue"


# --------------------------------------------------------------------------
# Guide without emoji
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kluc", ["guide.panel_title", "guide.window_title"])
def test_nadpis_sprievodcu_bez_emoji(kluc):
    for jazyk, text in i18n.STRINGS[kluc].items():
        assert "📖" not in text, jazyk
        assert all(ord(z) < 0x1F000 for z in text), jazyk
        assert text == text.strip(), jazyk
