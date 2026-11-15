# -*- coding: utf-8 -*-
"""The main window fits on the screen of ordinary laptops (0.3).

The window has a fixed 1180x760 LOGICAL px (`DandurfApp.WINDOW_W/H`) and
CTk multiplies them by the display scale. On a 1920x1080 gaming laptop at
150 % that was ~1140 px against ~1008 px of work area, on 1366x768 at
100 % 760 against ~720 px. The window cannot be stretched or maximised,
so Settings at the bottom of the side menu ended up under the taskbar.

Guarded:
  * pure maths (`display.window_fit_factor`, `center_in_work_area`) for
    1080p@150 %, 1366x768@100 %, 1440p@100 %, 4K@150 %, 1080p@100 % and
    multiple monitors with the taskbar on the side; scaling down never
    below 0.7,
  * an assumption about CTk: window size = logical * window DPI *
    window_scaling and `set_window_scaling` OVERWRITES the value
    (verified on the installed CTk),
  * `ui_kit` with a substitute tracker that computes like CTk: where the
    window does not fit, the whole app shrinks (elements and window by
    the same factor), where it fits, nothing changes; the target
    monitor's DPI is set before the UI is built; the window is centred in
    the work area, and when it does not fit even at 0.7, it is stuck to
    the top,
  * app.py calls it before the first-start guide and `_build_ui`, and the
    window size stays fixed (minsize == maxsize),
  * the first-start guide uses the same centre calculation,
  * KNOWN_ISSUES says the same as the code (monitor under the cursor, at
    most 70 %).

All without a real window and monitor - the tests do not change CTk's
global scale.
"""
import ast
import os
import sys
import tkinter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

W, H = 1180, 760
OKRAJ = display.WINDOW_FIT_MARGIN_PX


def _mon(x, y, w, h, work, dpi, primary=True):
    return display.Monitor(x, y, w, h, primary=primary, work=work, dpi=dpi)


# Setups from the audit. Work area = monitor without the taskbar (48 px
# at 100 %, 72 px at 150 %), exactly as GetMonitorInfo returns it.
LAPTOP_1080_150 = _mon(0, 0, 1920, 1080, (0, 0, 1920, 1008), 144)
LAPTOP_1366_100 = _mon(0, 0, 1366, 768, (0, 0, 1366, 720), 96)
DESKTOP_1080_100 = _mon(0, 0, 1920, 1080, (0, 0, 1920, 1032), 96)
DESKTOP_1440_100 = _mon(0, 0, 2560, 1440, (0, 0, 2560, 1392), 96)
UHD_150 = _mon(0, 0, 3840, 2160, (0, 0, 3840, 2088), 144)
# Second monitor right of the main one, taskbar on the LEFT side (62 px).
BOK_VPRAVO = _mon(1920, 0, 1366, 768, (1982, 0, 1304, 768), 96, primary=False)
# Second monitor on the left (negative x), taskbar on the RIGHT side, 125 %.
BOK_VLAVO_125 = _mon(-1920, 0, 1920, 1080, (-1920, 0, 1844, 1080), 120,
                     primary=False)
# So small that even 0.7 does not help (1080p at 200 %).
PRIMALY_200 = _mon(0, 0, 1920, 1080, (0, 0, 1920, 984), 192)

ZOSTAVY = {
    "1080p@150": LAPTOP_1080_150,
    "1366x768@100": LAPTOP_1366_100,
    "1080p@100": DESKTOP_1080_100,
    "1440p@100": DESKTOP_1440_100,
    "4K@150": UHD_150,
    "bok_vpravo": BOK_VPRAVO,
    "bok_vlavo@125": BOK_VLAVO_125,
}


def _fyz(logicky, mierka):
    # CTk: geometry() rounds (round), minsize/maxsize truncates (int).
    # For the test whether the window fits, round is the worse case.
    return round(logicky * mierka)


# --------------------------------------------------------------------------
# Pure maths (display.py)
# --------------------------------------------------------------------------

def test_dpi_scale_ako_ctk():
    assert display.dpi_scale(LAPTOP_1080_150) == 1.5
    assert display.dpi_scale(DESKTOP_1080_100) == 1.0
    assert display.dpi_scale(BOK_VLAVO_125) == 1.25
    # a broken value does not crash
    assert display.dpi_scale(_mon(0, 0, 10, 10, None, 0)) == 1.0


def test_laptop_1080p_pri_150_sa_zmensi_a_zmesti():
    mon = LAPTOP_1080_150
    s = display.dpi_scale(mon)
    assert _fyz(H, s) + OKRAJ > mon.work_height, "predpoklad auditu: bez zmeny sa nezmesti"
    f = display.window_fit_factor(W, H, s, mon.work_width, mon.work_height)
    assert f == pytest.approx(0.87)
    assert _fyz(H, s * f) + OKRAJ <= mon.work_height
    assert _fyz(W, s * f) + OKRAJ <= mon.work_width


def test_1366x768_pri_100_sa_zmensi_a_zmesti():
    mon = LAPTOP_1366_100
    s = display.dpi_scale(mon)
    assert H + OKRAJ > mon.work_height
    f = display.window_fit_factor(W, H, s, mon.work_width, mon.work_height)
    assert f == pytest.approx(0.926)
    assert _fyz(H, s * f) + OKRAJ <= mon.work_height


@pytest.mark.parametrize("meno", ["1080p@100", "1440p@100", "4K@150"])
def test_kde_sa_zmesti_nemeni_sa_nic(meno):
    mon = ZOSTAVY[meno]
    f = display.window_fit_factor(W, H, display.dpi_scale(mon),
                                  mon.work_width, mon.work_height)
    assert f == 1.0


@pytest.mark.parametrize("meno", sorted(ZOSTAVY))
def test_okno_je_cele_v_pracovnej_ploche(meno):
    mon = ZOSTAVY[meno]
    s = display.dpi_scale(mon)
    f = display.window_fit_factor(W, H, s, mon.work_width, mon.work_height)
    assert display.WINDOW_MIN_FIT <= f <= 1.0
    pw, ph = _fyz(W, s * f), _fyz(H, s * f)
    x, y = display.center_in_work_area(mon, pw, ph)
    assert mon.work_x <= x and x + pw <= mon.work_x + mon.work_width
    assert mon.work_y <= y and y + ph <= mon.work_y + mon.work_height
    # centred: left/right and top/bottom margins differ by at most 1 px
    vlavo, vpravo = x - mon.work_x, mon.work_x + mon.work_width - (x + pw)
    hore, dole = y - mon.work_y, mon.work_y + mon.work_height - (y + ph)
    assert abs(vlavo - vpravo) <= 1 and abs(hore - dole) <= 1


def test_lista_uloh_na_boku_posunie_stred():
    """The centre is in the work area, not in the whole monitor - the window
    is not centred under the taskbar on the side."""
    mon = BOK_VPRAVO
    f = display.window_fit_factor(W, H, 1.0, mon.work_width, mon.work_height)
    assert f < 1.0                    # 768 px of height, no taskbar at the bottom - just short
    pw = _fyz(W, f)
    x, _y = display.center_in_work_area(mon, pw, _fyz(H, f))
    assert x == 1982 + (1304 - pw) // 2
    assert x > mon.x + 62             # not under the taskbar
    # negative coordinates of the virtual desktop (monitor left of the main)
    mon = BOK_VLAVO_125
    pw = _fyz(W, 1.25)
    x, _y = display.center_in_work_area(mon, pw, _fyz(H, 1.25))
    assert x == -1920 + (1844 - pw) // 2
    assert x + pw <= -1920 + 1844     # the taskbar on the right stays free


def test_nikdy_pod_minimum_a_vtedy_hore():
    mon = PRIMALY_200
    s = display.dpi_scale(mon)
    f = display.window_fit_factor(W, H, s, mon.work_width, mon.work_height)
    assert f == display.WINDOW_MIN_FIT == 0.7
    ph = _fyz(H, s * f)
    assert ph > mon.work_height        # does not fit even at 0.7...
    x, y = display.center_in_work_area(mon, _fyz(W, s * f), ph)
    assert y == mon.work_y             # ...so the title bar stays at the top
    assert x >= mon.work_x


def test_faktor_je_zaokruhleny_nadol():
    # 992 / 1140 = 0.87017... - rounded up, CTk would make the window a
    # pixel too big
    f = display.window_fit_factor(W, H, 1.5, 1920, 1008)
    assert f == 0.87
    assert f * 1000 == int(f * 1000)
    # a zero or broken scale does not crash and does not shrink for no reason
    assert display.window_fit_factor(W, H, 0, 4000, 3000) == 1.0
    assert display.window_fit_factor(W, H, None, 4000, 3000) == 1.0
    # area smaller than the margin -> minimum, not division by zero
    assert display.window_fit_factor(W, H, 1.0, 10, 10) == display.WINDOW_MIN_FIT


# --------------------------------------------------------------------------
# How CTk really multiplies (installed customtkinter)
# --------------------------------------------------------------------------

class _OknoBezTk(tkinter.Tk):
    """Empty object CTk recognises as a window (isinstance Tk) - no Tcl."""

    def __init__(self):            # noqa: D401 - deliberately without tkinter.Tk.__init__
        pass

    def __getattr__(self, meno):
        raise AttributeError(meno)

    def __repr__(self):
        return "<_OknoBezTk>"


def test_ctk_nasobi_dpi_okna_a_mierku_appky(monkeypatch):
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker as ST
    okno = _OknoBezTk()
    monkeypatch.setitem(ST.window_dpi_scaling_dict, okno, 1.5)
    monkeypatch.setattr(ST, "window_scaling", 0.87)
    monkeypatch.setattr(ST, "widget_scaling", 0.87)
    assert ST.get_window_scaling(okno) == pytest.approx(1.5 * 0.87)
    assert ST.get_widget_scaling(okno) == pytest.approx(1.5 * 0.87)


def test_ctk_set_scaling_prepise_nenasobi(monkeypatch):
    """That is why ui_kit multiplies ITSELF: `set_window_scaling(x)` sets x,
    not x * the current value (and it does not go below 0.4)."""
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker as ST
    monkeypatch.setattr(ST, "window_scaling", 1.2)
    monkeypatch.setattr(ST, "widget_scaling", 1.2)
    monkeypatch.setattr(ST, "update_scaling_callbacks_all", classmethod(lambda cls: None))
    ST.set_window_scaling(0.9)
    ST.set_widget_scaling(0.9)
    assert ST.window_scaling == 0.9 and ST.widget_scaling == 0.9
    ST.set_window_scaling(0.1)
    assert ST.window_scaling == 0.4
    assert display.WINDOW_MIN_FIT > 0.4


# --------------------------------------------------------------------------
# ui_kit with a substitute tracker that computes like CTk
# --------------------------------------------------------------------------

class _Tracker:
    """Stand-in for `ScalingTracker`: same maths, no global state."""

    deactivate_automatic_dpi_awareness = False

    def __init__(self, okno=None, dpi_okna=1.0, mierka=1.0):
        self.window_scaling = mierka
        self.widget_scaling = mierka
        self.window_dpi_scaling_dict = {}
        if okno is not None:
            self.window_dpi_scaling_dict[okno] = dpi_okna
        self.volania = []

    def set_widget_scaling(self, x):
        self.volania.append(("widget", x))
        self.widget_scaling = max(x, 0.4)

    def set_window_scaling(self, x):
        self.volania.append(("window", x))
        self.window_scaling = max(x, 0.4)

    def update_scaling_callbacks_for_window(self, okno):
        self.volania.append(("dpi", self.window_dpi_scaling_dict[okno]))

    def get_window_scaling(self, okno):
        return self.window_dpi_scaling_dict[okno] * self.window_scaling


class _Okno:
    """A window that only remembers `geometry()` - how CTk converts logical
    sizes to physical ones is computed by `fyzicky_rozmer` with the
    tracker."""

    def __init__(self, tracker):
        self.tracker = tracker
        self.geometrie = []

    def geometry(self, text):
        self.tracker.volania.append(("geometry", text))
        self.geometrie.append(text)

    def fyzicky_obdlznik(self):
        rozmer, x, y = self.geometrie[-1].split("+")
        w, h = (int(v) for v in rozmer.split("x"))
        s = self.tracker.get_window_scaling(self)
        return int(x), int(y), round(w * s), round(h * s)


def _priprav(monkeypatch, dpi_okna=1.0, mierka=1.0, mon=None):
    tracker = _Tracker(dpi_okna=dpi_okna, mierka=mierka)
    okno = _Okno(tracker)
    tracker.window_dpi_scaling_dict[okno] = dpi_okna
    monkeypatch.setattr(ui_kit, "_ctk_tracker", lambda: tracker)
    if mon is not None:
        monkeypatch.setattr(ui_kit.display_mod, "monitor_at_cursor", lambda *_a: mon)
    return tracker, okno


def test_notebook_150_zmensi_celu_appku_jednym_faktorom(monkeypatch):
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5)
    f = ui_kit.prisposob_mierku_monitoru(W, H, LAPTOP_1080_150)
    assert f == pytest.approx(0.87)
    # elements AND window by the same factor - otherwise the content would
    # spill out of the window
    assert ("widget", pytest.approx(0.87)) in tracker.volania
    assert ("window", pytest.approx(0.87)) in tracker.volania
    assert tracker.widget_scaling == tracker.window_scaling


@pytest.mark.parametrize("meno", ["1080p@100", "1440p@100", "4K@150"])
def test_kde_sa_zmesti_mierka_ostane(monkeypatch, meno):
    mon = ZOSTAVY[meno]
    tracker, _okno = _priprav(monkeypatch, dpi_okna=display.dpi_scale(mon))
    assert ui_kit.prisposob_mierku_monitoru(W, H, mon) == 1.0
    assert tracker.volania == []
    assert tracker.window_scaling == 1.0 and tracker.widget_scaling == 1.0


def test_druhe_volanie_nezmensi_znova(monkeypatch):
    tracker, _okno = _priprav(monkeypatch, dpi_okna=1.5)
    ui_kit.prisposob_mierku_monitoru(W, H, LAPTOP_1080_150)
    pred = list(tracker.volania)
    assert ui_kit.prisposob_mierku_monitoru(W, H, LAPTOP_1080_150) == 1.0
    assert tracker.volania == pred


def test_skladanie_s_uz_nastavenou_mierkou(monkeypatch):
    """If the app ever had its own scale, the factor is multiplied onto it."""
    tracker, _okno = _priprav(monkeypatch, dpi_okna=1.0, mierka=1.1)
    f = ui_kit.prisposob_mierku_monitoru(W, H, LAPTOP_1366_100)
    assert f < 1.0
    assert tracker.window_scaling == pytest.approx(1.1 * f)
    assert round(H * 1.0 * tracker.window_scaling) + OKRAJ <= 720


def test_bez_dpi_v_ctk_sa_rata_len_mierka_appky(monkeypatch):
    tracker, _okno = _priprav(monkeypatch)
    tracker.deactivate_automatic_dpi_awareness = True
    assert ui_kit.dpi_mierka_monitora(LAPTOP_1080_150) == 1.0
    # CTk would multiply only by 1.0 -> 760 + 16 fits into 1008
    assert ui_kit.prisposob_mierku_monitoru(W, H, LAPTOP_1080_150) == 1.0
    assert ui_kit.zosuladi_dpi_s_monitorom(_okno, LAPTOP_1080_150) is False


def test_dpi_okna_sa_nastavi_na_cielovy_monitor(monkeypatch):
    """Root is created on the main monitor (150 %); when it goes to the
    second one (100 %), the CTk scale switches right away - not only once
    the widgets are built."""
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5)
    assert ui_kit.zosuladi_dpi_s_monitorom(okno, DESKTOP_1080_100) is True
    assert tracker.window_dpi_scaling_dict[okno] == 1.0
    assert tracker.volania == [("dpi", 1.0)]
    # same DPI -> no recalculation
    assert ui_kit.zosuladi_dpi_s_monitorom(okno, DESKTOP_1080_100) is False
    assert tracker.volania == [("dpi", 1.0)]
    # a window CTk does not know is left alone
    assert ui_kit.zosuladi_dpi_s_monitorom(object(), DESKTOP_1080_100) is False


def test_stred_sa_rata_z_dpi_cieloveho_monitora(monkeypatch):
    # root still "sits" on the 150 % monitor, the target has 100 %
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5)
    geo = ui_kit.vycentrovana_geometria(okno, 720, 600, DESKTOP_1080_100)
    assert geo == "720x600+%d+%d" % ((1920 - 720) // 2, (1032 - 600) // 2)


def test_stred_bez_monitora_je_monitor_pod_kurzorom(monkeypatch):
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.0, mon=BOK_VPRAVO)
    geo = ui_kit.vycentrovana_geometria(okno, 720, 600)
    assert geo == "720x600+%d+%d" % (1982 + (1304 - 720) // 2, (768 - 600) // 2)


def test_stred_pri_chybe_vrati_len_rozmer(monkeypatch):
    def _zle(*_a):
        raise OSError("ziadny monitor")
    _priprav(monkeypatch)
    monkeypatch.setattr(ui_kit.display_mod, "monitor_at_cursor", _zle)
    assert ui_kit.vycentrovana_geometria(object(), 720, 600) == "720x600"


@pytest.mark.parametrize("meno", sorted(ZOSTAVY) + ["primaly@200"])
def test_cely_postup_okno_v_ploche(monkeypatch, meno):
    """umiestni_pevne_okno from start to finish, root was always created on
    the main monitor at 150 % (as on a computer with 4K + 1080p)."""
    mon = ZOSTAVY.get(meno, PRIMALY_200)
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5, mon=mon)
    f, pouzity = ui_kit.umiestni_pevne_okno(okno, W, H)
    assert pouzity is mon
    x, y, pw, ph = okno.fyzicky_obdlznik()
    assert okno.geometrie[-1].startswith("%dx%d+" % (W, H)), "logicky rozmer sa nemeni"
    assert mon.work_x <= x and x + pw <= mon.work_x + mon.work_width
    assert y >= mon.work_y
    if f > display.WINDOW_MIN_FIT:
        assert y + ph + OKRAJ // 2 <= mon.work_y + mon.work_height
    else:
        assert y == mon.work_y
    # order: target monitor DPI -> scale -> geometry
    druhy = [v[0] for v in tracker.volania]
    assert druhy[-1] == "geometry"
    if "dpi" in druhy and "window" in druhy:
        assert druhy.index("dpi") < druhy.index("window")


def test_cely_postup_notebook_150(monkeypatch):
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5, mon=LAPTOP_1080_150)
    f, _mon_ = ui_kit.umiestni_pevne_okno(okno, W, H)
    assert f == pytest.approx(0.87)
    # 1540 x 992 physical, in the centre of the 1920 x 1008 area
    assert okno.geometrie[-1] == "1180x760+190+8"


def test_cely_postup_bez_monitora(monkeypatch):
    def _zle(*_a):
        raise OSError("ziadny monitor")
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.0)
    monkeypatch.setattr(ui_kit.display_mod, "monitor_at_cursor", _zle)
    assert ui_kit.umiestni_pevne_okno(okno, W, H) == (1.0, None)
    assert okno.geometrie == ["1180x760"]
    assert tracker.window_scaling == 1.0


# --------------------------------------------------------------------------
# app.py and the first-start guide
# --------------------------------------------------------------------------

def test_app_umiestni_okno_skor_nez_vzniknu_widgety():
    init = zdroj_metody("__init__")
    volanie = init.index("ui_kit.umiestni_pevne_okno(")
    assert volanie < init.index("OnboardingWizard(")
    assert volanie < init.index("self._build_ui()")
    assert volanie < init.index("enable_frameless(self.root)")
    # fixed dashboard stays: minsize == maxsize == WINDOW_W/H, after placing
    assert volanie < init.index("self.root.minsize(self.WINDOW_W, self.WINDOW_H)")
    assert "self.root.maxsize(self.WINDOW_W, self.WINDOW_H)" in init
    # no second geometry() without a position that would drop the centring
    assert 'self.root.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}")' not in init


def test_logicky_rozmer_okna_sa_nezmenil():
    strom = ast.parse(zdroj_suboru("app.py"))
    trieda = next(u for u in strom.body
                  if isinstance(u, ast.ClassDef) and u.name == "DandurfApp")
    for uzol in trieda.body:
        if (isinstance(uzol, ast.Assign) and isinstance(uzol.targets[0], ast.Tuple)
                and [t.id for t in uzol.targets[0].elts] == ["WINDOW_W", "WINDOW_H"]):
            assert ast.literal_eval(uzol.value) == (1180, 760)
            break
    else:
        raise AssertionError("WINDOW_W, WINDOW_H nie su v DandurfApp")


def test_known_issues_hovori_to_iste_co_kod():
    # Since 0.3 (batch 4) the version history is in CHANGELOG.md.
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8-sig") as fh:
        text = " ".join(fh.read().split())
    sekcia = text[text.index("## What 0.3 changes"):text.index("## What 0.2.1 fixes")]
    assert "The window didn't fit smaller laptop screens." in sekcia
    assert "down to %d %% at most" % round(display.WINDOW_MIN_FIT * 100) in sekcia
    assert "the screen with the mouse pointer" in sekcia
    assert "the title bar stays at the top of the screen" in sekcia


def test_sprievodca_pouziva_spolocny_stred(monkeypatch):
    import ui_dialogs
    tracker, okno = _priprav(monkeypatch, dpi_okna=1.5, mon=LAPTOP_1366_100)
    geo = ui_dialogs.OnboardingWizard._centered_geometry(okno, 720, 600)
    assert geo == ui_kit.vycentrovana_geometria(okno, 720, 600, LAPTOP_1366_100)
    assert geo == "720x600+%d+%d" % ((1366 - 720) // 2, (720 - 600) // 2)
