# -*- coding: utf-8 -*-
"""Appearance after batch 4b of the UX audit (0.3): the Consistency grid, the
"Voice source" row, the Today bar with a taken port, small red text and the
dialog frame.

Guarded:
  * the Consistency grid enlarges the squares by width (at most CELL_MAX),
    the month labels sit above the columns and the days next to the rows,
  * the voice preparation status and "Try again" are inside the "Voice
    source" row (above its divider line) and the empty state takes no space,
  * with a taken port the heart-rate panel has only the button (one
    message, not two) and the bar text has a dark backing over the photo,
  * small red text is `danger_text` (>= 4.5:1), never `danger`,
  * every app dialog (DialogChrome) has a 1 px frame in `rule`.

Synthetic data; real Tk only with a hidden window.
"""
import os
import re
import sys
import types
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import theme  # noqa: E402
import ui_kit  # noqa: E402
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
# 7: the Consistency grid
# --------------------------------------------------------------------------

def test_stvorcek_rastie_kym_tyzdne_nezaplnia_sirku():
    G = ui_kit.DayGrid
    for sirka in (420, 500, 560):
        bunka, medzera = G.rozmer_bunky(sirka, 26)
        assert G.CELL < bunka < G.CELL_MAX
        assert G.GAP <= medzera <= G.GAP_MAX
        obsadene = 26 * (bunka + medzera) - medzera
        assert abs(obsadene - sirka) < 1.0, (sirka, obsadene)


def test_stvorcek_ma_strop_aj_dno():
    G = ui_kit.DayGrid
    assert G.rozmer_bunky(3000, 26) == (float(G.CELL_MAX), float(G.GAP_MAX))
    # a few weeks in a wide window: the squares are not giant
    assert G.rozmer_bunky(1000, 3)[0] == G.CELL_MAX
    # narrow window: the smallest square, the start of the history is cut off
    # (`_redraw`)
    assert G.rozmer_bunky(200, 26)[0] == G.CELL
    assert G.rozmer_bunky(0, 26) == (float(G.CELL), float(G.GAP))
    assert G.rozmer_bunky(500, 0) == (float(G.CELL), float(G.GAP))


def test_vyska_mriezky_ide_s_velkostou_stvorceka():
    G = ui_kit.DayGrid
    assert G.vyska_mriezky(G.CELL_MAX, G.GAP_MAX) > G.vyska_mriezky(G.CELL, G.GAP)
    assert G.vyska_mriezky(G.CELL, G.GAP) == \
        G.MONTH_H + 7 * (G.CELL + G.GAP) - G.GAP + G.LEGEND_H


class _Platno:
    """tk.Canvas dummy: items with text and coordinates, bbox ~7 px/char."""

    def __init__(self, sirka):
        self.sirka = sirka
        self.polozky = {}
        self._id = 0

    def winfo_width(self):
        return self.sirka

    def delete(self, tag):
        if tag == "all":
            self.polozky.clear()
        else:
            self.polozky.pop(tag, None)

    def _nova(self, druh, coords, **kw):
        self._id += 1
        self.polozky[self._id] = {"druh": druh, "coords": list(coords), **kw}
        return self._id

    def create_text(self, x, y, **kw):
        return self._nova("text", (x, y), **kw)

    def create_polygon(self, points, **kw):
        return self._nova("poly", points, **kw)

    def coords(self, polozka, *xy):
        self.polozky[polozka]["coords"] = list(xy)

    def bbox(self, polozka):
        p = self.polozky.get(polozka)
        if not p:
            return None
        x, y = p["coords"][:2]
        sirka = 7 * len(str(p.get("text", "")))
        if p.get("anchor") == "sw":
            return (x, y - 12, x + sirka, y)
        return (x, y - 6, x + sirka, y + 6)


def _mriezka(sirka, tyzdnov=26):
    g = object.__new__(ui_kit.DayGrid)
    g.pal = theme.tokens(theme.ZEN)
    g.canvas = _Platno(sirka)
    g.height = g.vyska_mriezky(g.CELL, g.GAP)
    g._get_widget_scaling = lambda: 1.0
    g.configure = lambda **kw: None
    dnes = date(2026, 11, 15)
    prvy = dnes - timedelta(days=tyzdnov * 7 - 1)
    dni = [{"date": prvy + timedelta(days=i), "seconds": (i % 3) * 1800.0}
           for i in range(tyzdnov * 7)]
    g._days, g._legend = dni, ("menej", "viac")
    g._months = tuple("jan feb mar apr máj jún júl aug sep okt nov dec".split())
    g._weekdays = tuple("po ut st št pi so ne".split())
    g._redraw()
    return g


def _bunky(g):
    """Day squares (without the legend - that has a fixed 10 px)."""
    return [x for x in g.canvas.polozky.values() if x["druh"] == "poly"
            and max(x["coords"][0::2]) - min(x["coords"][0::2]) >= g.CELL - 0.01]


def test_mriezka_zaplni_panel_a_popisky_sedia():
    g = _mriezka(700)
    p = list(g.canvas.polozky.values())
    bunky = _bunky(g)
    assert len(bunky) == 26 * 7
    xs = sorted({round(min(b["coords"][0::2]), 3) for b in bunky})
    pravy_okraj = max(max(b["coords"][0::2]) for b in bunky)
    assert 0.95 * 700 < pravy_okraj <= 700, "26 tyzdnov cez celu sirku"
    assert len(xs) == 26
    # months: each label starts exactly above some column
    mesiace = [x for x in p if x["druh"] == "text" and x.get("anchor") == "sw"
               and x["text"] in g._months]
    assert len(mesiace) >= 5
    for m in mesiace:
        assert any(abs(m["coords"][0] - x) < 0.6 for x in xs), m
    # days: the label's centre at the row's centre
    ys = sorted({round(min(b["coords"][1::2]), 3) for b in bunky})
    assert len(ys) == 7
    vyska = min(max(b["coords"][1::2]) - min(b["coords"][1::2]) for b in bunky)
    dni = [x for x in p if x["druh"] == "text" and x["text"] in g._weekdays]
    assert dni
    for d in dni:
        assert any(abs(d["coords"][1] - (y + vyska / 2.0)) < 0.6 for y in ys), d


def test_velke_stvorceky_maju_meno_kazdeho_dna():
    siroka = _mriezka(1200)
    dni = [x["text"] for x in siroka.canvas.polozky.values()
           if x["druh"] == "text" and x["text"] in siroka._weekdays]
    assert sorted(dni) == sorted(siroka._weekdays), "pri velkom kroku vsetkych 7 dni"
    uzka = _mriezka(360)
    dni = [x["text"] for x in uzka.canvas.polozky.values()
           if x["druh"] == "text" and x["text"] in uzka._weekdays]
    assert sorted(dni) == sorted(["po", "st", "pi"])


def test_cislo_dni_ostava_hore_pri_raste_mriezky():
    assert 'days_box.pack(side="right", padx=(18, 0), anchor="n")' in \
        zdroj_suboru("app_history.py")


# --------------------------------------------------------------------------
# 8: voice preparation status in the "Voice source" row
# --------------------------------------------------------------------------

def test_stav_hlasu_a_skusit_znova_su_v_riadku_zdroja_hlasu():
    zdroj = zdroj_suboru("app.py")
    assert re.search(r"self\.edge_status_label = ctk\.CTkLabel\(\s*row\.text_col,", zdroj)
    assert re.search(r"self\.edge_retry_btn = ui_kit\.button\(\s*row\.text_col,", zdroj)
    assert "voice_panel.body, pal, tr(\"common.retry\")" not in zdroj


class _Stitok:
    def __init__(self):
        self.zabaleny = False
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


def test_prazdny_stav_hlasu_nezabera_miesto():
    import app_audio
    stitok, tlacidlo = _Stitok(), _Stitok()
    a = types.SimpleNamespace(edge_status_label=stitok, edge_retry_btn=tlacidlo,
                              pal=theme.tokens(theme.ZEN))
    a._ukaz_skusit_hlas_znova = lambda ukaz: app_audio.AudioMixin._ukaz_skusit_hlas_znova(a, ukaz)
    app_audio.AudioMixin.set_edge_status(a, "")
    assert not stitok.zabaleny
    app_audio.AudioMixin.set_edge_status(a, "Pripravujem hlas…")
    assert stitok.zabaleny and stitok.cfg["text"] == "Pripravujem hlas…"
    # "Try again" goes only AFTER the status
    a._ukaz_skusit_hlas_znova(True)
    assert tlacidlo.zabaleny and tlacidlo.pack_kw.get("after") is stitok
    # a new status hides the button, an empty status also hides the label
    app_audio.AudioMixin.set_edge_status(a, "")
    assert not stitok.zabaleny and not tlacidlo.zabaleny


def test_settingrow_ma_verejny_stlpec_textu():
    root = _tk_root()
    try:
        riadok = ui_kit.SettingRow(root, theme.tokens(theme.ZEN), "Zdroj hlasu", "Veta.")
        assert riadok.sub_label.master is riadok.text_col
        assert riadok.title_label.master is riadok.text_col
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# 9: taken port on Today
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", TEMY)
def test_emptystate_schova_len_vetu(tema):
    root = _tk_root()
    try:
        stav = ui_kit.EmptyState(root, theme.tokens(tema), "Keď spáruješ hodinky…",
                                 action="Spárovať hodinky", command=lambda: None)
        stav.pack()
        assert stav.label.winfo_manager() == "pack"
        stav.ukaz_vetu(False)
        assert stav.label.winfo_manager() == ""
        assert stav.action.winfo_manager() == "pack", "tlacidlo ostava"
        stav.ukaz_vetu(False)                      # calling it twice breaks nothing
        stav.ukaz_vetu(True)
        assert stav.pack_slaves() == [stav.label, stav.action], "veta zase nad tlacidlom"
        holy = ui_kit.EmptyState(root, theme.tokens(tema), "Len veta.")
        holy.ukaz_vetu(False)
        holy.ukaz_vetu(True)
        assert holy.label.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_obsadeny_port_schova_vetu_panela_tepu():
    kod = zdroj_metody("_refresh_dnes_stats")
    assert 'ukaz_vetu(getattr(self, "_hr_state", None)' in kod
    assert 'not in ("busy", "busy_gave_up"))' in kod


def test_text_pasu_ma_podlozku_nad_fotkou():
    """The backing is an image with alpha BETWEEN the dojo and the text (tag
    "dtext", so it moves with the text) - not a box with an edge."""
    import app_today
    if app_today._ImageTk is None:
        pytest.skip("bez PIL ImageTk")
    import tkinter as tk
    root = _tk_root()
    try:
        c = tk.Canvas(root, width=400, height=300)
        dojo = c.create_rectangle(0, 0, 400, 300, fill="#806040")
        text = c.create_text(200, 200, text="Port 4455 je obsadený", tags=("dtext",))
        a = types.SimpleNamespace(_dnes_dojo_tk=object(), _dnes_tk_imgs={},
                                  PODLOZKA_ALFA=app_today.TodayMixin.PODLOZKA_ALFA,
                                  PODLOZKA_OKRAJ=app_today.TodayMixin.PODLOZKA_OKRAJ,
                                  PODLOZKA_ROZMAZ=app_today.TodayMixin.PODLOZKA_ROZMAZ)
        app_today.TodayMixin._podlozka_textu(a, c, 1.0, theme.tokens(theme.ZEN), {"dojo": dojo})
        podlozka = c.find_withtag("podlozka")
        assert len(podlozka) == 1 and "dtext" in c.gettags(podlozka[0])
        poradie = list(c.find_all())
        assert poradie.index(dojo) < poradie.index(podlozka[0]) < poradie.index(text)
        assert "podlozka" in a._dnes_tk_imgs, "referencia na obrazok sa drzi"
        # without a photo (only a colour background) nothing is drawn
        b = types.SimpleNamespace(_dnes_dojo_tk=None, _dnes_tk_imgs={})
        c2 = tk.Canvas(root, width=100, height=100)
        c2.create_text(50, 50, text="x", tags=("dtext",))
        app_today.TodayMixin._podlozka_textu(b, c2, 1.0, theme.tokens(theme.ZEN), {})
        assert not c2.find_withtag("podlozka")
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# 10: small red text
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", TEMY)
def test_danger_text_je_citatelny_na_vsetkych_plochach(tema):
    pal = theme.tokens(tema)
    for pozadie in ("bg", "surface", "surface_alt"):
        assert _kontrast(pal["danger_text"], pal[pozadie]) >= 4.5, pozadie


def test_ziadny_drobny_text_v_danger():
    vzor = re.compile(r'text_color=[^,\n]*\[["\']danger["\']\]')
    for meno in subory_appky() + ["ui_dialogs.py", "ui_kit.py", "ui_shell.py",
                                  "guide_panel.py", "guided_tour.py", "color_picker.py"]:
        najdene = vzor.search(zdroj_suboru(meno))
        assert najdene is None, (meno, najdene and najdene.group(0))


def test_stavy_tepu_a_parovania_v_danger_text():
    assert 'tr("settings.hr_status_busy_gave_up"), pal["danger_text"]' in \
        zdroj_metody("_hr_status_display")
    zdroj = zdroj_suboru("ui_dialogs.py")
    assert '"chyba": pal.get("danger_text", pal["danger"])' in zdroj
    assert 'self.error_label = ctk.CTkLabel(body, text="", text_color=pal["danger_text"]' in zdroj


@pytest.mark.parametrize("tema", TEMY)
def test_cislo_hranice_v_grafoch_je_danger_text(tema):
    import hud_paint
    pal = theme.tokens(tema)
    st = hud_paint.Style(pal)
    assert st.danger_text == hud_paint._hex(pal["danger_text"])
    assert st.danger == hud_paint._hex(pal["danger"]), "ciary a plochy ostavaju danger"
    assert "p.text(gx1, ty, popis, style.danger_text" in zdroj_suboru("hud_paint.py")
    assert 'popisok(y, self._threshold, pal["danger_text"])' in zdroj_suboru("ui_kit.py")


def test_stara_paleta_bez_danger_text_nepadne():
    import hud_paint
    st = hud_paint.Style({"danger": "#c1553d"})
    assert st.danger_text == st.danger


# --------------------------------------------------------------------------
# 11: dialog frame
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tema", TEMY)
def test_ram_dialogu_je_hrana_plochy(tema):
    pal = theme.tokens(tema)
    assert ui_kit.DIALOG_RAM_TOKEN == "rule"
    # the window frame is visible against the main window behind it and
    # against its own background
    assert _kontrast(pal[ui_kit.DIALOG_RAM_TOKEN], pal["bg"]) >= 1.5


@pytest.mark.parametrize("tema", TEMY)
def test_nastav_ram_okna(tema):
    import tkinter as tk
    root = _tk_root()
    try:
        top = tk.Toplevel(root)
        top.withdraw()
        pal = theme.tokens(tema)
        ui_kit.nastav_ram_okna(top, pal)
        assert int(top.cget("highlightthickness")) == 1
        assert top.cget("highlightbackground").lower() == pal["rule"].lower()
        assert top.cget("highlightcolor").lower() == pal["rule"].lower(), \
            "ram sa pri fokuse nemeni"
    finally:
        root.destroy()


def test_nastav_ram_okna_nevyhodi_vynimku():
    ui_kit.nastav_ram_okna(None, theme.tokens(theme.ZEN))
    ui_kit.nastav_ram_okna(object(), {})


def test_dialogchrome_da_ram_kazdemu_dialogu():
    import inspect
    kod = inspect.getsource(ui_kit.DialogChrome.__init__)
    assert "nastav_ram_okna(top, pal)" in kod
    # notice, question and choice (also the window at the first close X) go
    # through DialogChrome
    assert "chrome = DialogChrome(top, pal, title" in inspect.getsource(ui_kit._okno_appky)
    for meno in ("ui_dialogs.py", "color_picker.py", "guide_panel.py"):
        zdroj = zdroj_suboru(meno)
        assert zdroj.count("ctk.CTkToplevel(") <= zdroj.count("DialogChrome("), meno
