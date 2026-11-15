# -*- coding: utf-8 -*-
"""Theme recolouring without rebuilding the window (`theme_recolor.py`).

Background: switching the theme called `_build_ui()`, which destroyed and
rebuilt the whole window from scratch - measured 1374 widgets, 101 878 Tk
calls and 2.97 s of blocking, during which the window was assembled piece
by piece in front of the player (29 different intermediate states). Now
the colours are just rewritten: 673 ms, 5 intermediate states.

The tests here are purely logical (no Tk), so they run everywhere. That
recolouring gives EXACTLY the same result as a rebuild is verified by the
live harness - it compares colours widget by widget and must come out
with 0 differences.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import theme as theme_mod  # noqa: E402
import theme_recolor  # noqa: E402
from _zdroj_appky import subory_appky, zdroj_metody  # noqa: E402

ZEN = theme_mod.tokens(theme_mod.ZEN)
MODERN = theme_mod.tokens(theme_mod.MODERN)


def _read(name):
    with open(os.path.join(os.path.dirname(__file__), "..", name),
              encoding="utf-8") as fh:
        return fh.read()


def test_mapa_pokryva_kazdy_farebny_token():
    """Every colour from the old theme must know what to change into."""
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    for token, hodnota in ZEN.items():
        if not isinstance(hodnota, str) or not hodnota.startswith("#"):
            continue
        assert hodnota.lower() in mapa, f"token {token} ({hodnota}) nie je v mape"


def test_mapa_funguje_v_oboch_smeroch():
    for a, b in ((ZEN, MODERN), (MODERN, ZEN)):
        mapa = theme_recolor.build_color_map(a, b)
        assert mapa, "mapa nesmie byt prazdna"
        for stara, nova in mapa.items():
            assert nova.startswith("#"), f"{stara} -> {nova!r} nie je farba"


def test_nejednoznacnost_riesi_preferencia():
    """In Sumi both `accent` and `keycap_text` have the value #d9b868, but in
    Modern they differ. The map must pick `accent` (the dominant token);
    the keycaps set their own colour through `ui_kit.Keycap.set_pal`."""
    assert ZEN["accent"].lower() == ZEN["keycap_text"].lower(), (
        "predpoklad testu padol - tieto tokeny uz nemaju rovnaku hodnotu")
    assert MODERN["accent"].lower() != MODERN["keycap_text"].lower()
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    assert mapa[ZEN["accent"].lower()].lower() == MODERN["accent"].lower()


def test_tokeny_rovnake_v_oboch_temach_sa_nemenia():
    """`warn`, `washi` and `font_family` are the same in both themes."""
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    for token in ("warn", "washi"):
        hodnota = ZEN[token].lower()
        assert mapa[hodnota].lower() == hodnota


def test_transparent_a_nefarby_ostavaju():
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    assert theme_recolor._preloz("transparent", mapa) is None
    assert theme_recolor._preloz("", mapa) is None
    assert theme_recolor._preloz(None, mapa) is None
    assert theme_recolor._preloz("#123456", mapa) is None   # outside the theme


def test_dvojica_farieb_sa_preklada_po_prvkoch():
    """CustomTkinter can have a colour as (light, dark)."""
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    par = (ZEN["surface"], "transparent")
    out = theme_recolor._preloz(par, mapa)
    assert out is not None
    assert out[0].lower() == MODERN["surface"].lower()
    assert out[1] == "transparent"


def test_bg_color_je_medzi_sledovanymi_volbami():
    """`bg_color` is a derived colour that CTk stores from the parent. When
    it was missing, the old shade showed through in the rounded corners of
    the segmented button - only the 'recolouring == rebuild' test caught
    it."""
    assert "bg_color" in theme_recolor.COLOR_OPTIONS


def test_hladanie_zvyskov_ignoruje_nemenne_tokeny():
    """Without `new_pal`, `warn`/`washi` would be reported as forgotten."""
    trieda = theme_recolor.find_theme_colored
    assert "new_pal" in trieda.__code__.co_varnames


def test_prepnutie_temy_nestavia_okno_znova():
    """Regression: `on_theme_switch` must not go back to `_build_ui()` as the
    main path - that was the 2.97 s of flicker."""
    blok = zdroj_metody("on_theme_switch")
    assert "self._recolor_ui(" in blok, "prepnutie temy musi prefarbovat"
    # _build_ui may stay ONLY as a rescue in the except branch
    if "self._build_ui()" in blok:
        assert "except Exception:" in blok, (
            "_build_ui() v on_theme_switch je pripustne len ako fallback")


def test_prvky_s_vlastnou_paletou_maju_set_pal():
    """Whatever keeps its own copy of the palette must be able to accept a
    new one - otherwise the old colours would come back on the first
    hover/click."""
    shell = _read("ui_shell.py")
    # `QuickDock` was here until 2.1. The quick dock (🔊 / 😴 / ⌘) left the
    # side column — `_StateDot` is what, in its place, keeps its own copy
    # of the palette and must be able to accept a new one.
    for trieda in ("class Sidebar", "class _StateDot", "class _NavRow",
                   "class _EnsoButton", "class TitleBar"):
        i = shell.index(trieda)
        koniec = shell.find("\nclass ", i + 1)
        telo = shell[i:koniec if koniec > 0 else len(shell)]
        assert "def set_pal" in telo, f"{trieda} nema set_pal()"
    assert "def set_pal" in _read("ui_kit.py")[_read("ui_kit.py").index("class Keycap"):]


def test_kazdy_widget_s_vlastnou_paletou_je_aj_v_recolor_ui():
    """Having `set_pal` is not enough - someone has to call it.

    `KamaeBar` had everything except this: it kept `self.pal`, drew from
    it, and was not in the list searched in `_recolor_ui`. After switching
    from Sumi to Aizome the canvas background changed (`recolor_tree`
    rewrites that as a widget OPTION), but the plate, the breathing line
    and the text stayed in the old theme. No test, no harness and no
    check_before_run caught it - and it was the header of the Today page,
    i.e. the first thing you see after switching.

    The test asks the other way round from the one above it: not "does
    the class have set_pal", but "does the class draw from its own
    palette, and if so, does anyone call it?".
    """
    import ast

    zdroj = _read("ui_kit.py")
    strom = ast.parse(zdroj)
    # the list of classes the app recolours by name
    blok = zdroj_metody("_recolor_ui")

    chyba = []
    for uzol in strom.body:
        if not isinstance(uzol, ast.ClassDef):
            continue
        telo = ast.unparse(uzol)
        # "draws from its own palette" = somewhere in the class there is
        # `self.pal[` or `self.pal.get(`. Just storing `self.pal = pal` is
        # not enough - Panel does that too, and it only passes the colours
        # on to CTk widgets, which `recolor_tree` then rewrites by itself.
        if "self.pal[" not in telo and "self.pal.get(" not in telo:
            continue
        meno = uzol.name
        # Descendants of PalCanvas are covered: they inherit `set_pal` and
        # `_recolor_ui` finds them via the base class. This is checked
        # FIRST - otherwise the test would fail on DayGrid, which has no
        # `set_pal` of its own and does not need one.
        dedi_z_palcanvas = any(
            isinstance(b, ast.Name) and b.id == "PalCanvas" for b in uzol.bases)
        if dedi_z_palcanvas or meno == "PalCanvas":
            continue
        if "def set_pal" not in telo:
            chyba.append(f"{meno} kresli z vlastnej palety a nema set_pal()")
            continue
        if f"ui_kit.{meno}" not in blok:
            chyba.append(f"{meno} ma set_pal(), ale _recolor_ui ho nevola")
    assert not chyba, "\n".join(chyba)


def test_popupy_maju_poistku_proti_scaling_trackeru():
    """A plain `tk.Toplevel` with CTk widgets inside fails on AttributeError.

    CustomTkinter registers such a window (putting a single CTk widget in
    it is enough) and `ScalingTracker` then periodically calls
    `block_update_dimensions_event()`, which exists only on `CTk`/
    `CTkToplevel`. The crash is in an `after` callback, so it does not
    bring the app down — it just quietly lands in crash.log on every DPI
    change.
    """
    import ui_kit
    assert hasattr(ui_kit, "priprav_popup")

    import tkinter as tk
    trieda = type("FalosnyTop", (), {})
    okno = trieda()
    ui_kit.priprav_popup(okno)
    okno.block_update_dimensions_event()      # must not crash
    okno.unblock_update_dimensions_event()

    # Every window that CTk widgets get poured into has to go through it.
    # guided_tour.py: the tour bubble holds CTk widgets and without this
    # safeguard it crashed on a DPI change (several monitors with different
    # resolutions).
    # app = app.py and the DandurfApp mixins in app_*.py
    for subor in (*subory_appky(), "ui_shell.py", "ui_dialogs.py", "guided_tour.py"):
        zdroj = _read(subor)
        for riadok in zdroj.split("\n"):
            if "tk.Toplevel(" in riadok and "ctk." not in riadok:
                assert "priprav_popup" in riadok, f"{subor}: {riadok.strip()}"
