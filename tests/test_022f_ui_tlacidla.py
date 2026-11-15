# -*- coding: utf-8 -*-
"""Buttons and dropdowns after batch 4b of the UX audit (0.3).

Guarded:
  * no emoji on the "Pair a watch now" button in the introduction and in
    the cue sound dropdown ("Automatic", "Custom file: ...") - in all 11
    languages; a custom file is still shown and selected correctly,
  * the chip is only for external links (↗) - "Show IP" is a secondary
    button with a fixed width for both texts,
  * the voice choice in the cue window is `ui_kit.option_menu`, the window
    buttons (the after-game questionnaire, introduction, tour) come from
    `ui_kit.button`,
  * the voice dropdown in Settings widens with new values (long Windows
    voice names do not get clipped),
  * a DISABLED button has one look for all kinds (text `text_faint`, border
    `control_border`) and gets its original look back once enabled - even
    if the theme was switched in the meantime.

Synthetic data; real Tk only with a hidden window.
"""
import ast
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import subory_appky, zdroj_suboru  # noqa: E402

TEMY = (theme.ZEN, theme.MODERN)
JAZYKY = ("sk", "en", "ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg")


def _je_emoji(znak):
    o = ord(znak)
    return (0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF or 0x1F900 <= o <= 0x1F9FF
            or o == 0xFE0F)


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


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


def _metoda(subor, trieda, meno):
    for uzol in ast.parse(zdroj_suboru(subor)).body:
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == meno:
                    return ast.unparse(f)
    raise AssertionError(f"{trieda}.{meno} nie je v {subor}")


# --------------------------------------------------------------------------
# 1 + 2: no emoji
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kluc", ["ob.step3.pair_now", "ob.step3.pair_queued",
                                  "sfx.auto", "sfx.custom_prefix"])
@pytest.mark.parametrize("jazyk", JAZYKY)
def test_texty_tlacidiel_bez_emoji(kluc, jazyk):
    text = i18n.tr_lang(jazyk, kluc)
    assert text and not any(_je_emoji(z) for z in text), (jazyk, text)
    assert text == text.strip(), "po odstraneni emoji ostala medzera na zaciatku"


def test_tlacidlo_parovania_v_uvode_nepridava_emoji():
    kod = _metoda("ui_dialogs.py", "OnboardingWizard", "_pair_button_look")
    assert "🕑" not in kod
    assert "text=tr('ob.step3.pair_now')" in kod


@pytest.mark.parametrize("jazyk", JAZYKY)
def test_vlastny_subor_v_rozbalovacke_zvuku(jazyk):
    """The shown text of a custom file carries the file name and cannot be
    confused with any option from the list - so picking from the dropdown
    never switches it to another sound."""
    import settings_model
    povodny = i18n._lang["code"]
    i18n.set_lang(jazyk)
    try:
        text = settings_model.sfx_choice_display("__custom__", os.path.join("x", "moj_zvuk.wav"))
        assert "moj_zvuk.wav" in text
        assert not any(_je_emoji(z) for z in text)
        volby = settings_model.sfx_dropdown_options()
        assert volby[0] == (i18n.tr("sfx.auto"), "")
        assert text not in [d for d, _v in volby]
        assert settings_model.sfx_choice_display("", None) == i18n.tr("sfx.auto")
    finally:
        i18n.set_lang(povodny)


def test_vyber_zvuku_najde_hodnotu_podla_textu_bez_emoji(sk):
    """`SlotCard.on_sfx_choice` looks up the value by the shown text - without
    the emoji, "Automaticky" (Automatic) must still mean the empty key (by
    theme)."""
    import settings_model
    import ui_dialogs
    ulozene = []
    karta = types.SimpleNamespace(
        sfx_options=settings_model.sfx_dropdown_options(), sfx_key="zen:x",
        app=types.SimpleNamespace(save_settings=lambda: ulozene.append(1)),
        refresh_summary=lambda: None)
    ui_dialogs.SlotCard.on_sfx_choice(karta, i18n.tr("sfx.auto"))
    assert karta.sfx_key == "" and ulozene
    display, hodnota = settings_model.sfx_dropdown_options()[1]
    ui_dialogs.SlotCard.on_sfx_choice(karta, display)
    assert karta.sfx_key == hodnota


# --------------------------------------------------------------------------
# 3: chip only for external links
# --------------------------------------------------------------------------

def test_chip_len_pre_externe_odkazy():
    subory = subory_appky() + ["ui_dialogs.py", "ui_shell.py", "guide_panel.py",
                               "guided_tour.py", "color_picker.py"]
    for meno in subory:
        for m in re.finditer(r"ui_kit\.chip\(([^\n]*)", zdroj_suboru(meno)):
            assert "\\u2197" in m.group(1) or "↗" in m.group(1), (meno, m.group(0))


def test_ukazat_ip_je_vedlajsie_tlacidlo_so_stalou_sirkou():
    kod = _metoda("ui_dialogs.py", "WatchPairingDialog", "__init__")
    assert "ui_kit.chip(" not in kod
    assert "self.ip_toggle = ui_kit.button(" in kod
    assert "fit_texts=(tr('hr.ip_hide'),)" in kod


def test_fit_texts_berie_sirku_z_najdlhsieho(monkeypatch):
    monkeypatch.setattr(ui_kit, "_sirka_textu", lambda text, font: 10 * len(text))
    zapis = []
    monkeypatch.setattr(ui_kit.ctk, "CTkButton",
                        lambda *a, **kw: zapis.append(kw) or types.SimpleNamespace())
    pal = theme.tokens(theme.ZEN)
    ui_kit.button(None, pal, "Ukázať IP", fit_texts=("Skryť IP adresu",))
    assert zapis[-1]["width"] == 10 * len("Skryť IP adresu") + 2 * ui_kit._BUTTON_PAD_X


# --------------------------------------------------------------------------
# 4: controls from ui_kit, not bare CTk
# --------------------------------------------------------------------------

def test_ziadna_hola_rozbalovacka_mimo_ui_kit():
    subory = subory_appky() + ["ui_dialogs.py", "ui_shell.py", "guide_panel.py",
                               "guided_tour.py", "color_picker.py"]
    for meno in subory:
        assert "ctk.CTkOptionMenu(" not in zdroj_suboru(meno), meno


def test_vyber_hlasu_pripomienky_je_option_menu():
    kod = _metoda("ui_dialogs.py", "SlotSettingsDialog", "__init__")
    assert "self.voice_box = ui_kit.option_menu(" in kod
    assert "ctk.CTkButton(" not in kod, "tlacidla okna su z ui_kit.button"


@pytest.mark.parametrize("trieda, metoda", [
    ("SessionEndDialog", "__init__"),
    ("OnboardingWizard", "_build_footer"),
    ("OnboardingWizard", "_show_quit_question"),
    ("NewProfileDialog", "__init__"),
    ("ImportProfileDialog", "__init__"),
    ("RecordDialog", "__init__"),
])
def test_tlacidla_okien_su_z_ui_kit(trieda, metoda):
    kod = _metoda("ui_dialogs.py", trieda, metoda)
    # only the questionnaire's choice chips may stay bare CTkButton
    # (they toggle)
    for m in re.finditer(r"ctk\.CTkButton\(", kod):
        okolie = kod[m.start():m.start() + 400]
        assert "_pick_one" in okolie or "_toggle_body" in okolie or "_prepni" in okolie \
            or "_set_activity" in okolie, (trieda, okolie[:120])


def test_ukazka_v_uvode_a_prehliadka_su_z_ui_kit():
    zdroj = zdroj_suboru("ui_dialogs.py")
    assert "self.preview_btn = ui_kit.button(" in zdroj
    prehliadka = zdroj_suboru("guided_tour.py")
    assert "ui_kit.button(btns, pal, tr(\"tour.skip\"), kind=\"quiet\"" in prehliadka
    assert "kind=\"primary\"" in prehliadka


# --------------------------------------------------------------------------
# 5: the voice dropdown grows with its values
# --------------------------------------------------------------------------

class _Menu:
    def __init__(self, **kw):
        self.kw = dict(kw)

    def configure(self, **kw):
        self.kw.update(kw)


def test_nove_hodnoty_rozsiria_rozbalovacku(monkeypatch):
    monkeypatch.setattr(ui_kit, "_sirka_textu", lambda text, font: 7 * len(text))
    monkeypatch.setattr(ui_kit.ctk, "CTkOptionMenu", lambda master, **kw: _Menu(**kw))
    pal = theme.tokens(theme.ZEN)
    menu = ui_kit.option_menu(None, pal, values=["Načítavam…"])
    zaciatok = menu.kw["width"]
    assert zaciatok == ui_kit.CONTROL_W, "kratky text - minimalna sirka"
    dlhe = "Microsoft Hedda Desktop - German (Germany) Extended"
    ui_kit.nastav_hodnoty_menu(menu, ["Zira", dlhe])
    assert menu.kw["values"] == ["Zira", dlhe]
    assert menu.kw["width"] == 7 * len(dlhe) + ui_kit._MENU_CHROME_W
    # back to short values: never narrower than the original minimum
    ui_kit.nastav_hodnoty_menu(menu, ["A"])
    assert menu.kw["width"] == ui_kit.CONTROL_W


def test_dynamicka_rozbalovacka_si_sirku_riesi_sama(monkeypatch):
    monkeypatch.setattr(ui_kit.ctk, "CTkOptionMenu", lambda master, **kw: _Menu(**kw))
    menu = ui_kit.option_menu(None, theme.tokens(theme.ZEN), width=104,
                              dynamic_resizing=True, values=["a"])
    ui_kit.nastav_hodnoty_menu(menu, ["dlha hodnota " * 5])
    assert menu.kw["width"] == 104


def test_nastav_hodnoty_menu_nevyhodi_vynimku():
    class _Zly:
        def configure(self, **kw):
            raise RuntimeError("zniceny widget")
    ui_kit.nastav_hodnoty_menu(_Zly(), ["a"])
    ui_kit.nastav_hodnoty_menu(None, ["a"])


def test_refresh_voice_box_pouziva_nastav_hodnoty_menu():
    from _zdroj_appky import zdroj_metody
    kod = zdroj_metody("refresh_voice_box")
    assert "ui_kit.nastav_hodnoty_menu(self.voice_box" in kod
    assert "self.voice_box.configure(values=" not in kod


# --------------------------------------------------------------------------
# 6: one look for a disabled button
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", TEMY)
@pytest.mark.parametrize("druh", ui_kit.BUTTON_KINDS)
def test_vzhlad_vypnuteho_je_jeden_pre_vsetky_druhy(tema, druh):
    pal = theme.tokens(tema)
    st = ui_kit.vzhlad_vypnuteho(druh, pal)
    assert st["text_color"] == st["text_color_disabled"] == pal["text_faint"]
    assert pal["danger_text"] not in st.values() and pal["accent"] not in st.values()
    if druh in ("secondary", "danger"):
        assert st["border_color"] == pal["control_border"]
    if druh == "primary":
        assert st["fg_color"] == pal["surface_alt"], "vypnute hlavne tlacidlo nesvieti zlatom"


@pytest.mark.parametrize("tema", TEMY)
@pytest.mark.parametrize("druh", ui_kit.BUTTON_KINDS)
def test_vypnute_tlacidlo_naozaj(tema, druh):
    root = _tk_root()
    try:
        pal = theme.tokens(tema)
        btn = ui_kit.button(root, pal, "Zmazať históriu", kind=druh)
        zapnute = {k: btn.cget(k) for k in ("text_color", "border_color", "fg_color")}
        btn.configure(state="disabled")
        assert btn.cget("state") == "disabled"
        assert btn.cget("text_color") == pal["text_faint"]
        assert btn.cget("text_color_disabled") == pal["text_faint"]
        if druh in ("secondary", "danger"):
            assert btn.cget("border_color") == pal["control_border"]
        # disabling a second time breaks nothing
        btn.configure(state="disabled")
        btn.configure(state="normal")
        assert btn.cget("state") == "normal"
        assert {k: btn.cget(k) for k in zapnute} == zapnute
    finally:
        root.destroy()


def test_vypnute_uz_pri_stavbe():
    root = _tk_root()
    try:
        pal = theme.tokens(theme.ZEN)
        btn = ui_kit.button(root, pal, "Prehrať", state="disabled")
        assert btn.cget("state") == "disabled"
        assert btn.cget("text_color") == pal["text_faint"]
        btn.configure(state="normal")
        assert btn.cget("text_color") == pal["text"]
        assert btn.cget("border_color") == pal["control_border"]
    finally:
        root.destroy()


def test_zapnutie_po_zmene_temy_vrati_farby_novej_temy():
    """Switching the world recolours the window by value (`theme_recolor`).
    When that happens while "Delete" is disabled, once enabled it must have
    the red of the NEW theme."""
    import theme_recolor
    root = _tk_root()
    try:
        sumi, aizome = theme.tokens(theme.ZEN), theme.tokens(theme.MODERN)
        btn = ui_kit.button(root, sumi, "Zmazať", kind="danger")
        btn.configure(state="disabled")
        mapa = theme_recolor.build_color_map(sumi, aizome)
        # recolouring like `theme_recolor` - colours by value, without state
        btn.configure(**{k: mapa.get(str(btn.cget(k)).lower(), btn.cget(k))
                         for k in ("text_color", "border_color")})
        assert btn.cget("text_color").lower() == aizome["text_faint"].lower()
        btn.configure(state="normal")
        assert btn.cget("text_color").lower() == aizome["danger_text"].lower()
        assert btn.cget("border_color").lower() == aizome["danger_text"].lower()
    finally:
        root.destroy()


def test_farby_poslane_s_vypnutim_maju_prednost():
    root = _tk_root()
    try:
        pal = theme.tokens(theme.ZEN)
        btn = ui_kit.button(root, pal, "Test")
        btn.configure(state="disabled", text_color=pal["warn"])
        assert btn.cget("text_color") == pal["warn"]
    finally:
        root.destroy()


def test_tlacidla_ktore_sa_vypinaju_su_z_ui_kit():
    """"Delete history" (while watching) and "Delete this session" (while
    recording) - both `ui_kit.button(kind="danger")`, so disabling gets a
    uniform look without any extra code."""
    assert 'self.data_delete_btn = ui_kit.button(rad, pal, tr("data.delete.btn"), kind="danger"' \
        in zdroj_suboru("app_data.py")
    assert 'tr("history.delete_session.btn"), kind="danger"' in zdroj_suboru("app_history.py")
