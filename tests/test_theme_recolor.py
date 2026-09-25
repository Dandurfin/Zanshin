# -*- coding: utf-8 -*-
"""Prefarbenie temy bez prestavby okna (`theme_recolor.py`).

Pozadie: prepnutie temy volalo `_build_ui()`, ktore znicilo a odznova
postavilo cele okno - odmerane 1374 widgetov, 101 878 volani Tk a 2,97 s
blokovania, pocas ktorych sa okno pred hracom skladalo po castiach
(29 roznych medzistavov). Teraz sa farby len prepisu: 673 ms, 5 medzistavov.

Testy tu su ciste logicke (bez Tk), aby bezali vsade. Ze prefarbenie dava
PRESNE ten isty vysledok ako prestavba, overuje zivy harness - porovnava
farby widget po widgete a musi vyjst 0 rozdielov.
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
    """Kazda farba zo starej temy musi vediet, na co sa ma zmenit."""
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
    """V Sumi maju `accent` aj `keycap_text` hodnotu #d9b868, ale v Modern
    sa rozchadzaju. Mapa musi vybrat `accent` (dominantny token); klavesy
    si svoju farbu nastavuju samy cez `ui_kit.Keycap.set_pal`."""
    assert ZEN["accent"].lower() == ZEN["keycap_text"].lower(), (
        "predpoklad testu padol - tieto tokeny uz nemaju rovnaku hodnotu")
    assert MODERN["accent"].lower() != MODERN["keycap_text"].lower()
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    assert mapa[ZEN["accent"].lower()].lower() == MODERN["accent"].lower()


def test_tokeny_rovnake_v_oboch_temach_sa_nemenia():
    """`warn`, `washi` a `font_family` su v oboch temach rovnake."""
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    for token in ("warn", "washi"):
        hodnota = ZEN[token].lower()
        assert mapa[hodnota].lower() == hodnota


def test_transparent_a_nefarby_ostavaju():
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    assert theme_recolor._preloz("transparent", mapa) is None
    assert theme_recolor._preloz("", mapa) is None
    assert theme_recolor._preloz(None, mapa) is None
    assert theme_recolor._preloz("#123456", mapa) is None   # mimo temy


def test_dvojica_farieb_sa_preklada_po_prvkoch():
    """CustomTkinter vie mat farbu ako (svetla, tmava)."""
    mapa = theme_recolor.build_color_map(ZEN, MODERN)
    par = (ZEN["surface"], "transparent")
    out = theme_recolor._preloz(par, mapa)
    assert out is not None
    assert out[0].lower() == MODERN["surface"].lower()
    assert out[1] == "transparent"


def test_bg_color_je_medzi_sledovanymi_volbami():
    """`bg_color` je odvodena farba, ktoru si CTk ulozi z rodica. Ked
    chybala, presvital stary odtien v zaoblenych rohoch segmentoveho
    prepinaca - chytil to az test 'prefarbenie == prestavba'."""
    assert "bg_color" in theme_recolor.COLOR_OPTIONS


def test_hladanie_zvyskov_ignoruje_nemenne_tokeny():
    """Bez `new_pal` by sa `warn`/`washi` hlasili ako zabudnute."""
    trieda = theme_recolor.find_theme_colored
    assert "new_pal" in trieda.__code__.co_varnames


def test_prepnutie_temy_nestavia_okno_znova():
    """Regresia: `on_theme_switch` sa nesmie vratit k `_build_ui()` ako
    hlavnej ceste - to bolo tych 2,97 s blikania."""
    blok = zdroj_metody("on_theme_switch")
    assert "self._recolor_ui(" in blok, "prepnutie temy musi prefarbovat"
    # _build_ui smie zostat LEN ako zachrana v except vetve
    if "self._build_ui()" in blok:
        assert "except Exception:" in blok, (
            "_build_ui() v on_theme_switch je pripustne len ako fallback")


def test_prvky_s_vlastnou_paletou_maju_set_pal():
    """Co si drzi vlastnu kopiu palety, musi vediet prijat novu - inak by
    sa stare farby vratili pri prvom hover/kliku."""
    shell = _read("ui_shell.py")
    # `QuickDock` tu bol do 2.1. Rýchly dok (🔊 / 😴 / ⌘) z bočného rádu
    # odišiel — `_StateDot` je na jeho mieste to, čo si drží vlastnú kópiu
    # palety a musí vedieť prijať novú.
    for trieda in ("class Sidebar", "class _StateDot", "class _NavRow",
                   "class _EnsoButton", "class TitleBar"):
        i = shell.index(trieda)
        koniec = shell.find("\nclass ", i + 1)
        telo = shell[i:koniec if koniec > 0 else len(shell)]
        assert "def set_pal" in telo, f"{trieda} nema set_pal()"
    assert "def set_pal" in _read("ui_kit.py")[_read("ui_kit.py").index("class Keycap"):]


def test_kazdy_widget_s_vlastnou_paletou_je_aj_v_recolor_ui():
    """Mat `set_pal` nestaci - niekto ho musi zavolat.

    `KamaeBar` mal vsetko okrem tohto: drzal si `self.pal`, kreslil z nej a
    v prehladavanom zozname v `_recolor_ui` nebol. Po prepnuti zo Sumi na
    Aizome sa pozadie platna zmenilo (to prepisuje `recolor_tree` ako
    OPTION widgetu), ale plat, dychova linka aj text ostali v starej teme.
    Nechytil to ziadny test, ziadny harness ani check_before_run - a bola to
    hlavicka stranky Dnes, teda prva vec, ktoru po prepnuti vidno.

    Test sa pyta obratene nez ten nad nim: nie "ma trieda set_pal", ale
    "kresli trieda z vlastnej palety, a ak ano, vola ju niekto?".
    """
    import ast

    zdroj = _read("ui_kit.py")
    strom = ast.parse(zdroj)
    # zoznam tried, ktore appka prefarbuje menovite
    blok = zdroj_metody("_recolor_ui")

    chyba = []
    for uzol in strom.body:
        if not isinstance(uzol, ast.ClassDef):
            continue
        telo = ast.unparse(uzol)
        # "kresli z vlastnej palety" = niekde v triede je `self.pal[` alebo
        # `self.pal.get(`. Samotne ulozenie `self.pal = pal` nestaci - to
        # robi aj Panel, ktory farby len posunie dalej do CTk widgetov a
        # tie uz `recolor_tree` prepise sam.
        if "self.pal[" not in telo and "self.pal.get(" not in telo:
            continue
        meno = uzol.name
        # Potomkovia PalCanvas su vybaveni: `set_pal` dedia a `_recolor_ui`
        # ich najde cez zakladnu triedu. Kontroluje sa to PRVE - inak by
        # test padol na DayGrid, ktory vlastny `set_pal` nema a nepotrebuje.
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
    """Obyčajný `tk.Toplevel` s CTk widgetmi vnútri padá na AttributeError.

    CustomTkinter si také okno zaregistruje (stačí doň vložiť jediný CTk
    widget) a `ScalingTracker` potom periodicky volá
    `block_update_dimensions_event()`, ktorá existuje len na `CTk`/
    `CTkToplevel`. Pád je v `after` callbacku, takže appku nezhodí — len
    potichu pristane v crash.log pri každej zmene DPI.
    """
    import ui_kit
    assert hasattr(ui_kit, "priprav_popup")

    import tkinter as tk
    trieda = type("FalosnyTop", (), {})
    okno = trieda()
    ui_kit.priprav_popup(okno)
    okno.block_update_dimensions_event()      # nesmie padnúť
    okno.unblock_update_dimensions_event()

    # Každé okno, do ktorého sa sypú CTk widgety, cez ňu musí prejsť.
    # guided_tour.py: bublina prehliadky drží CTk widgety a bez tejto
    # poistky padala na zmene DPI (viac monitorov s rôznym rozlíšením).
    # appka = app.py aj mixiny DandurfApp v app_*.py
    for subor in (*subory_appky(), "ui_shell.py", "ui_dialogs.py", "guided_tour.py"):
        zdroj = _read(subor)
        for riadok in zdroj.split("\n"):
            if "tk.Toplevel(" in riadok and "ctk." not in riadok:
                assert "priprav_popup" in riadok, f"{subor}: {riadok.strip()}"
