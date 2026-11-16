# -*- coding: utf-8 -*-
"""The ring at high heart rate (experiment, off by default).

While the smoothed heart rate (`HeartStats.display_bpm`) is above the
player's limit (default 110 BPM), slot 3's breath ring breathes in a loop;
once it drops, the ring finishes breathed out and fades. Guarded here:

  * the loop (overlay.py): it starts with the exhale, loops and never ends
    by itself; a finish asked for in an exhale / an inhale ends breathed out
    (the empty ring), then fades; a new request while finishing keeps it
    breathing with no restart; the immediate stop; the drag test; a failed
    start leaves no window; new inhale/exhale lengths while it loops; a new
    size / position / monitor applies to the running loop at once,
  * the app tick (`_tick_high_hr_ring`): every condition that starts,
    keeps, finishes or stops it, waiting for a cue that is on screen, one
    app.log line at the start and one at the end, the showings as
    (start, end) - also on "not now", stop and session close,
  * cues wait while it is on screen (`_cue_can_fire`),
  * the settings: default, clamp, roundtrip, not in profiles,
  * the measurement windows: the new reason, the edges of the overlap, a
    ring still on screen when the session closes,
  * with the switch off nothing changes,
  * the Breath card in In-game pictures (it opens with the saved switch
    and limit) and its texts in all languages.

No Tk window: `LayeredSurface`, the monitor, the clock and the drawing are
the fakes from tests/test_03x_vydych_vizual.py, the Tk `.after()` queue is
driven by hand.
"""
import ast
import json
import re
import time as _time
import types

import pytest

import app as app_mod
import app_session
import display
import hud_paint
import i18n
import measure
import overlay
import settings_model as sm
import test_022b_data_nastavenia as nastavenia
import test_022b_data_vypnutie as vypnutie
import test_03x_vydych_vizual as vv
import test_cue_words as slova
import test_teraz_nie as teraz_nie
from _zdroj_appky import uzol_metody, zdroj_metody, zdroj_suboru

OUT, IN = vv.OUT, vv.IN
D = app_mod.DandurfApp
FADE = (overlay._SlotOverlay.FADE_MS // overlay._SlotOverlay.TICK_MS) \
    * overlay._SlotOverlay.TICK_MS / 1000.0


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------

class _Plocha(vv._Plocha):
    """`vv._Plocha` that can also be moved (`LayeredSurface.move`)."""

    def __init__(self, root):
        super().__init__(root)
        self.posuny = 0

    def move(self, x, y):
        self.posuny += 1
        self.rect = (x, y) + tuple(self.rect[2:])
        if self.top is not None:
            self.top.x, self.top.y = x, y


@pytest.fixture
def svet(monkeypatch):
    """The real `SomaticOverlayManager` on the fakes of test_03x_vydych_vizual."""
    hodiny = vv._Hodiny()
    root = types.SimpleNamespace(fronta=vv._Fronta(hodiny), plochy=[],
                                 pokazit_vytvorenie=False)
    kresba = []

    def _breath(w, h, style, phase=0.0, inhale=True, cycle_text=None, ss=2):
        kresba.append(("breath", inhale, phase, cycle_text, hodiny.t))
        return object()

    def _visual(name, w, h, style, t=1.0, label=None, ss=2):
        kresba.append((name, None, t, label, hodiny.t))
        return object()

    monkeypatch.setattr(overlay, "LayeredSurface", _Plocha)
    monkeypatch.setattr(overlay, "time", hodiny)
    monkeypatch.setattr(hud_paint, "render_breath", _breath)
    monkeypatch.setattr(hud_paint, "render_visual", _visual)
    monkeypatch.setattr(display, "resolve_target",
                        lambda *_a, **_k: display.Monitor(0, 0, 1920, 1080))
    m = overlay.SomaticOverlayManager(root)
    m.set_labels({0: "G", 1: "J", 2: "R"}, breath_inhale=IN, breath_exhale=OUT)
    for i in range(4):
        m.configure(i, enabled=True)
    return types.SimpleNamespace(m=m, root=root, fronta=root.fronta,
                                 hodiny=hodiny, kresba=kresba)


def _kruh(svet):
    return svet.m._slots[svet.m.BREATH_INDEX]


def _dych(svet):
    """Breath ring frames as (inhale, phase, caption, time)."""
    return [k[1:] for k in svet.kresba if k[0] == "breath"]


class _Log:
    """Stands in for `app_session.app_log` - what the app writes to app.log."""

    def __init__(self):
        self.riadky = []

    def info(self, sprava, *args):
        self.riadky.append(sprava % args if args else sprava)

    warning = info

    def exception(self, sprava, *args):
        self.riadky.append("CHYBA " + (sprava % args if args else sprava))

    def kruh(self):
        return [r for r in self.riadky if r.startswith("kruh pri vysokom tepe")]


def _appka(svet, bpm=120, **navyse):
    """DandurfApp without Tk with everything `_tick_high_hr_ring` reads:
    listening, a session, heart rate coming (smoothed `bpm`), the switch on,
    limit 110, the real overlay manager on fakes."""
    a = D.__new__(D)
    a.listening = True
    a._hr_session_open = True
    a._hr_state = "connected"
    a._hr_last_bpm = bpm
    a._hr_lost = False
    a._snooze_job = None
    a.high_hr_ring = True
    a.high_hr_ring_bpm = 110
    a._high_hr_ring_since = None
    a._high_hr_ring_spans = []
    a._high_hr_ring_retry_at = 0.0
    a.hr_stats = types.SimpleNamespace(display_bpm=bpm, steps_per_min=lambda: None)
    a.overlay_manager = svet.m
    # what `_cue_can_fire` reads besides that
    a.overlay_configs = sm.default_overlay_configs()
    a._hr_overlay_warned = False
    a.log = lambda _m: None
    a.last_global_trigger_time = 0.0
    a.cooldown_value = 0.0
    a.__dict__.update(navyse)
    return a


@pytest.fixture
def hra(svet, monkeypatch):
    """`svet` + the dummy app + app.log, the app's clock = the overlay's."""
    log = _Log()
    monkeypatch.setattr(app_session, "app_log", log)
    monkeypatch.setattr(app_session, "time", svet.hodiny)
    a = _appka(svet)

    def tik(sekund=0.25, krok=0.25):
        """Runs the `.after()` queue and the app tick 4x per second."""
        koniec = svet.hodiny.t + sekund
        while svet.hodiny.t < koniec - 1e-9:
            svet.fronta.bez(min(krok, koniec - svet.hodiny.t))
            D._tick_high_hr_ring(a, now=svet.hodiny.t)

    return types.SimpleNamespace(a=a, log=log, tik=tik, **vars(svet))


# --------------------------------------------------------------------------
# the loop (overlay.py)
# --------------------------------------------------------------------------

def test_slucka_zacina_vydychom_a_sama_neskonci(svet):
    kruh = _kruh(svet)
    assert svet.m.start_high_hr_ring() is True
    assert kruh._breath_mode == kruh.BREATH_LOOP
    assert svet.m.is_active(3) and svet.m.high_hr_ring_showing()
    assert not svet.m.high_hr_ring_finishing()
    # slot 3's own ring: its position and size
    assert kruh.surface.rect == (875, 714, 170, 170), "kruh nie je na mieste slotu 3"
    assert _dych(svet)[0][:3] == (False, 0.0, OUT), "zacina plny, vo vydychu"

    svet.fronta.bez(120.0)
    assert kruh.is_active and svet.m.high_hr_ring_showing(), "slucka sama neskonci"
    snimky = _dych(svet)
    behy = vv._behy(snimky)
    assert behy[0] is False and len(behy) >= 20, "vydych -> nadych -> vydych ..."
    assert all(a != b for a, b in zip(behy, behy[1:]))
    for inhale, faza, popis, _t in snimky:
        assert popis == (IN if inhale else OUT), "popis ide podla fazy"
        assert 0.0 <= faza <= 1.0
    assert len(svet.root.plochy) == 1, "jedno okno po celu dobu"


def test_slucka_dycha_dlzky_hraca(svet):
    svet.m.set_breath_seconds(3.0, 7.0)
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    assert kruh.breath_phases() == ((False, 7.0), (True, 3.0)), "jeden kolobeh slucky"
    for elapsed, stav in ((0.0, (False, 0.0)), (3.5, (False, 0.5)), (7.0, (True, 0.0)),
                          (8.5, (True, 0.5)), (10.0, (False, 0.0)), (17.0, (True, 0.0)),
                          (1000.0, (False, 0.0))):
        inhale, faza = kruh.breath_state(elapsed)
        assert (inhale, round(faza, 6)) == stav, elapsed
    assert kruh.is_active, "breath_state slucku neukonci"


def test_dokoncenie_vo_vydychu_dokonci_ten_vydych(svet):
    kruh = _kruh(svet)
    start = svet.hodiny.t
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 2.0)                    # in the first exhale
    svet.kresba.clear()
    assert svet.m.finish_high_hr_ring() is True
    assert svet.m.high_hr_ring_finishing() and svet.m.high_hr_ring_showing()
    _prazdny_kruh_zmizne(svet, start + FADE + 6.0)

    snimky = _dych(svet)
    assert vv._behy(snimky) == [False], "dokonci vydych, nadych uz nie"
    fazy = [s[1] for s in snimky]
    assert fazy == sorted(fazy) and fazy[-1] == 1.0, "konci vydychnuty (prazdny kruh)"
    assert snimky[-1][3] - start == pytest.approx(FADE + 6.0, abs=0.1)
    assert not kruh.is_active and not svet.m.high_hr_ring_showing()
    assert all(p.zavrete for p in svet.root.plochy)
    assert not svet.fronta.ulohy, "after() uloha ostala"


def _prazdny_kruh_zmizne(svet, prazdny):
    """Runs the ring to its end: the empty ring drawn at `prazdny` stays on
    screen and fades out (the usual fade-out), only then the window closes."""
    kruh = _kruh(svet)
    plocha = kruh.surface
    svet.fronta.bez(prazdny + 0.1 - svet.hodiny.t)
    assert _dych(svet)[-1][:2] == (False, 1.0), "prazdny kruh"
    assert kruh.is_active and not plocha.zavrete, "zmizol naraz, bez fade-out"
    assert 0.0 < plocha.alfa < 1.0, "prazdny kruh sa ma pomaly stratit"
    snimky = len(svet.kresba)
    svet.fronta.bez(FADE)
    assert plocha.zavrete and not kruh.is_active, "po fade-out je okno zavrete"
    assert plocha.alfa == 0.0
    assert len(svet.kresba) == snimky, "pocas fade-out sa uz nekresli"
    svet.fronta.bez(30.0)


def test_dokoncenie_v_nadychu_dodycha_a_vydychne(svet):
    kruh = _kruh(svet)
    start = svet.hodiny.t
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 7.0)                    # inhale: 6..10 s
    svet.kresba.clear()
    svet.m.finish_high_hr_ring()
    _prazdny_kruh_zmizne(svet, start + FADE + 16.0)

    snimky = _dych(svet)
    assert vv._behy(snimky) == [True, False], "dodycha nadych a este jeden vydych"
    assert snimky[-1][:2] == (False, 1.0), "konci vydychnuty"
    assert snimky[-1][3] - start == pytest.approx(FADE + 16.0, abs=0.1)
    assert not kruh.is_active


def test_nova_poziadavka_pocas_dokoncenia_dycha_dalej(svet):
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 2.0)
    svet.m.finish_high_hr_ring()
    svet.fronta.bez(1.0)
    plocha = kruh.surface
    svet.kresba.clear()
    assert svet.m.start_high_hr_ring() is True
    assert not svet.m.high_hr_ring_finishing() and svet.m.high_hr_ring_showing()
    assert kruh.surface is plocha and len(svet.root.plochy) == 1, "bez restartu"
    svet.fronta.bez(0.1)
    assert _dych(svet)[0][1] > 0.4, "kruh nezacal znova od plneho - neblikol"
    svet.fronta.bez(60.0)
    assert kruh.is_active, "dokoncenie je zrusene, slucka bezi"
    assert True in vv._behy(_dych(svet)), "po vydychu prisiel nadych"


def test_okamzite_zastavenie(svet):
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(3.0)
    stara = kruh.surface
    assert svet.m.stop_high_hr_ring() is True
    assert not kruh.is_active and stara.zavrete
    assert not svet.m.high_hr_ring_showing()
    pocet = len(svet.kresba)
    svet.fronta.bez(10.0)
    assert len(svet.kresba) == pocet, "po zastaveni sa uz nic nekresli"
    assert not svet.fronta.ulohy
    assert svet.m.stop_high_hr_ring() is False


def test_zastavenie_necha_ine_zobrazenie_kruhu(svet):
    """`stop_high_hr_ring` stops only the loop - not the breath cue, not the
    drag test."""
    svet.m.trigger(3)
    assert svet.m.stop_high_hr_ring() is False
    assert svet.m.is_active(3)
    svet.m.stop_all()
    svet.m.test(3)
    assert svet.m.stop_high_hr_ring() is False
    assert svet.m.is_testing(3) and svet.m.is_active(3)


def test_nikdy_pocas_drag_testu(svet):
    for index in range(4):
        svet.m.test(index)
        assert svet.m.start_high_hr_ring() is False, index
        assert not svet.m.high_hr_ring_showing()
        assert _kruh(svet)._breath_mode != _kruh(svet).BREATH_LOOP
        svet.m.stop_test(index)
    assert not svet.m.is_active(3)


def test_drag_test_kruhu_slucku_cisto_nahradi(svet):
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(2.0)
    svet.m.finish_high_hr_ring()
    stara = kruh.surface
    assert svet.m.test(3) is True
    assert stara.zavrete and kruh.surface is not stara
    assert kruh._test_mode and kruh._breath_mode == kruh.BREATH_FULL
    assert not svet.m.high_hr_ring_showing() and not svet.m.high_hr_ring_finishing()
    svet.fronta.bez(60.0)
    assert kruh.is_active, "test sam neskonci - nedokoncil ho stary pokyn"
    svet.m.stop_test(3)
    assert not kruh.is_active and not svet.m.high_hr_ring_showing()
    svet.kresba.clear()
    assert svet.m.start_high_hr_ring() is True, "po teste sa da znova spustit"
    assert _dych(svet)[0][:2] == (False, 0.0)
    assert not svet.m.high_hr_ring_finishing(), "ziadny zvysok stareho dokoncenia"


def test_slucka_kresli_aj_pri_vypnutom_obrazku_dychu(svet):
    """The feature has its own switch: slot 3's own one does not decide."""
    svet.m.configure(3, enabled=False)
    assert svet.m.start_high_hr_ring() is True
    svet.m.configure(3, enabled=False, scale=1.2)
    assert svet.m.high_hr_ring_showing(), "zmena karty kruhu slucku neprerusi"
    svet.m.configure(3, enabled=True)
    assert svet.m.high_hr_ring_showing()


def test_sprievodny_vydych_slucku_neprerusi(svet):
    """▶ Test of a grounding / jaw / release cue while the loop breathes: the
    picture comes, the ring just goes on (no restart into one exhale)."""
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(2.0)
    plocha = kruh.surface
    assert svet.m.trigger(0) is True
    assert svet.m.is_active(0)
    assert kruh.surface is plocha and kruh._breath_mode == kruh.BREATH_LOOP
    assert svet.m.high_hr_ring_showing()


@pytest.mark.parametrize("ako", ["okno", "fade", "start_loop"])
def test_zlyhany_start_nenecha_okno(svet, ako):
    """Whatever fails while starting, no half-built ring stays open - it
    would count as a running visual for good and `_cue_can_fire` would hold
    back every cue of the session."""
    kruh = _kruh(svet)

    def _zlyhaj(*_a, **_k):
        raise RuntimeError("zlyhanie")
    if ako == "okno":
        svet.root.pokazit_vytvorenie = True
    else:
        # only on this ring's instance
        setattr(kruh, "_fade" if ako == "fade" else "start_loop", _zlyhaj)
    assert svet.m.start_high_hr_ring() is False
    assert not any(svet.m.is_active(i) for i in range(4)), "polovicny kruh ostal"
    assert all(p.zavrete for p in svet.root.plochy)
    assert not svet.m.high_hr_ring_showing()
    svet.fronta.bez(10.0)
    assert not svet.m.is_active(3)

    svet.root.pokazit_vytvorenie = False
    kruh.__dict__.pop("_fade", None)
    kruh.__dict__.pop("start_loop", None)
    assert svet.m.start_high_hr_ring() is True, "ked kruh zase ide, slucka sa ukaze"


def test_zmena_dlzok_pocas_slucky_nespadne(svet):
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 5.0)                    # exhale at 5 of 6 s
    svet.m.set_breath_seconds(4.0, 2.0)            # shorter than the time already breathed
    svet.kresba.clear()
    svet.fronta.bez(0.1)
    assert _dych(svet)[-1][0] is True, "kratsi vydych uz je za nim - ide nadych"
    for nadych, vydych in ((10.0, 10.0), (2.0, 2.0), (0.1, 99.0), (6.0, 3.0)):
        svet.m.set_breath_seconds(nadych, vydych)
        svet.fronta.bez(7.0)
        assert kruh.is_active and svet.m.high_hr_ring_showing()
    assert all(0.0 <= s[1] <= 1.0 for s in _dych(svet))
    svet.m.finish_high_hr_ring()
    svet.fronta.bez(30.0)
    assert _dych(svet)[-1][:2] == (False, 1.0) and not kruh.is_active


def test_poloha_karty_plati_pre_slucku_hned(svet):
    """The loop has no end of its own: a new X/Y of the Breath card moves the
    running ring with its next frame - the same window, no restart."""
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 2.0)
    plocha = kruh.surface
    svet.kresba.clear()
    svet.m.configure(3, enabled=True, scale=1.0, pos=(10.0, 10.0))
    svet.fronta.bez(0.1)
    ciel = display.place(display.Monitor(0, 0, 1920, 1080), 170, 170, 10.0, 10.0)
    assert kruh.surface is plocha and len(svet.root.plochy) == 1, "to iste okno"
    assert plocha.rect == ciel + (170, 170), "kruh sa neposunul"
    assert _dych(svet)[0][1] > 0.3, "dycha dalej, nezacal od plneho"
    # the same values again (a colour change sends them too): nothing moves
    svet.m.configure(3, enabled=True, scale=1.0, pos=(10.0, 10.0), color="#123456")
    svet.fronta.bez(1.0)
    assert plocha.posuny == 1 and kruh.surface is plocha


def _velkost_sa_zmeni(svet, zmen, rect):
    """Changes the size / monitor of a breathing loop with `zmen()`: a new
    window at `rect`, the animation goes on in it - no fade-in, no restart -
    and the loop still ends breathed out."""
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 2.0)
    stara = kruh.surface
    faza = _dych(svet)[-1][1]
    svet.kresba.clear()
    zmen()
    svet.fronta.bez(0.05)
    nova = kruh.surface
    assert nova is not stara and stara.zavrete, "stare okno ostalo otvorene"
    assert nova.rect == rect
    assert nova.alfa == 1.0, "nove okno je hned cele viditelne, bez fade-in"
    prva = _dych(svet)[0]
    assert prva[0] is False and prva[1] >= faza, "dycha dalej, nezacal od plneho"
    assert svet.m.high_hr_ring_showing() and len(svet.fronta.ulohy) == 1
    svet.m.finish_high_hr_ring()
    svet.fronta.bez(30.0)
    assert _dych(svet)[-1][:2] == (False, 1.0) and not kruh.is_active
    assert all(p.zavrete for p in svet.root.plochy) and not svet.fronta.ulohy


def test_velkost_karty_plati_pre_slucku_hned(svet):
    ciel = display.place(display.Monitor(0, 0, 1920, 1080), 340, 340, 50.0, 50.0)
    _velkost_sa_zmeni(svet, lambda: svet.m.configure(3, scale=2.0, pos=(50.0, 50.0)),
                      ciel + (340, 340))


def test_zmena_monitora_plati_pre_slucku_hned(svet, monkeypatch):
    druhy = display.Monitor(1920, 0, 2560, 1440)

    def _zmen():
        monkeypatch.setattr(display, "resolve_target", lambda *_a, **_k: druhy)
        svet.m.set_monitor_target("primary")
    velkost = int(round(170 * druhy.scale))
    ciel = display.place(druhy, velkost, velkost, *_kruh(svet).pos)
    _velkost_sa_zmeni(svet, _zmen, ciel + (velkost, velkost))


def test_zlyhane_nove_okno_nenecha_polovicny_kruh(svet):
    """The window in the new size cannot be built: the ring goes (no
    half-built window that would hold back every cue), and it can start
    again later."""
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    svet.fronta.bez(FADE + 2.0)
    svet.root.pokazit_vytvorenie = True
    svet.m.configure(3, scale=1.5)
    svet.fronta.bez(1.0)
    assert not any(svet.m.is_active(i) for i in range(4)), "polovicny kruh ostal"
    assert not svet.m.high_hr_ring_showing() and not svet.fronta.ulohy
    assert all(p.zavrete or p.top is None for p in svet.root.plochy)
    svet.root.pokazit_vytvorenie = False
    assert svet.m.start_high_hr_ring() is True
    assert kruh.surface.rect[2:] == (255, 255), "nova slucka ma uz novu velkost"


def test_poloha_pocas_nabehu_plati_po_nabehu(svet):
    """A change during the fade-in is applied with the first frame after it."""
    kruh = _kruh(svet)
    svet.m.start_high_hr_ring()
    plocha = kruh.surface
    svet.m.configure(3, pos=(90.0, 10.0))
    svet.fronta.bez(FADE + 0.1)
    ciel = display.place(display.Monitor(0, 0, 1920, 1080), 170, 170, 90.0, 10.0)
    assert kruh.surface is plocha and plocha.rect == ciel + (170, 170)


def test_ina_ukazka_kruhu_polohu_neprevezme(svet):
    """Only the loop follows the card at once - a cue's exhale ring keeps
    its placement until it ends, as before."""
    svet.m.trigger(0)
    svet.fronta.bez(FADE + 1.0)
    plocha = _kruh(svet).surface
    rect = plocha.rect
    svet.m.configure(3, scale=2.0, pos=(10.0, 10.0))
    svet.m.set_monitor_target("primary")
    svet.fronta.bez(1.0)
    assert _kruh(svet).surface is plocha and plocha.rect == rect and not plocha.posuny
    assert not _kruh(svet)._relayout_pending


def test_bez_slucky_sa_nic_nemeni(svet):
    """Nobody started the loop (the switch is off): its API does nothing and
    the other showings of the ring work as before."""
    m = svet.m
    assert not m.high_hr_ring_showing() and not m.high_hr_ring_finishing()
    assert m.finish_high_hr_ring() is False and m.stop_high_hr_ring() is False
    assert not svet.root.plochy and not svet.kresba
    assert m.trigger(1) is True and m.is_active(3)
    assert _kruh(svet)._breath_mode == _kruh(svet).BREATH_EXHALE
    assert m.finish_high_hr_ring() is False and m.stop_high_hr_ring() is False
    assert m.is_active(3), "sprievodny vydych bezi dalej"
    m.configure(3, enabled=False)
    assert not m.is_active(3), "vypnuty obrazok dychu stale zastavi svoj kruh"


# --------------------------------------------------------------------------
# the app tick (`_tick_high_hr_ring`)
# --------------------------------------------------------------------------

def test_tep_nad_hranicou_ukaze_kruh_raz(hra):
    hra.a.hr_stats.display_bpm = 111
    hra.tik()
    assert hra.m.high_hr_ring_showing()
    assert hra.a._high_hr_ring_since == hra.hodiny.t
    assert hra.log.kruh() == ["kruh pri vysokom tepe: zobrazeny (tep 111, hranica 110)"]
    hra.tik(30.0)
    assert hra.m.high_hr_ring_showing() and len(hra.root.plochy) == 1
    assert len(hra.log.kruh()) == 1, "ziadny riadok za kazdy tik"
    assert not hra.a._high_hr_ring_spans, "kym bezi, interval nie je uzavrety"


@pytest.mark.parametrize("bpm", [110, 109, 60, None])
def test_tep_na_hranici_alebo_pod_nou_kruh_nezobrazi(hra, bpm):
    hra.a.hr_stats.display_bpm = bpm
    hra.tik(10.0)
    assert not hra.root.plochy and not hra.log.kruh()


@pytest.mark.parametrize("hranica, bpm, ukaze", [
    (140, 115, False), (140, 130, False), (140, 140, False), (140, 141, True),
    (90, 95, True), (90, 90, False), (80, 81, True), (200, 199, False),
])
def test_tik_cita_hranicu_hraca(hra, hranica, bpm, ukaze):
    """The limit is the player's own (`high_hr_ring_bpm`), not the default 110."""
    hra.a.high_hr_ring_bpm = hranica
    hra.a.hr_stats.display_bpm = bpm
    hra.tik(5.0)
    assert hra.m.high_hr_ring_showing() is ukaze, (hranica, bpm)
    if ukaze:
        assert hra.log.kruh() == [
            "kruh pri vysokom tepe: zobrazeny (tep %d, hranica %d)" % (bpm, hranica)]
    else:
        assert not hra.root.plochy and not hra.log.kruh()


def test_pod_vlastnou_hranicou_kruh_dokonci(hra):
    hra.a.high_hr_ring_bpm = 140
    hra.a.hr_stats.display_bpm = 150
    _bezi(hra)
    hra.a.hr_stats.display_bpm = 141
    hra.tik(2.0)
    assert hra.m.high_hr_ring_showing() and not hra.m.high_hr_ring_finishing()
    hra.a.hr_stats.display_bpm = 135               # above 110, below the player's 140
    hra.tik()
    assert hra.m.high_hr_ring_finishing(), "pod hranicou hraca ma dokoncit"
    hra.tik(10.0)
    assert not hra.m.is_active(3) and len(hra.a._high_hr_ring_spans) == 1


def test_rozhoduje_vyhladene_cislo_nie_surova_vzorka(svet, monkeypatch):
    """A single spike (the HUD would not even show it) does not start it;
    the smoothed number above the limit does."""
    import hr_stats
    monkeypatch.setattr(app_session, "app_log", _Log())
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 5000.0
    for _ in range(4):
        st.add(100, ts=t)
        t += 0.7
    st.add(150, ts=t)                              # the spike
    a = _appka(svet, bpm=150, hr_stats=st)
    assert st.last_bpm == 150 and st.display_bpm == 100
    D._tick_high_hr_ring(a, now=svet.hodiny.t)
    assert not svet.m.is_active(3)
    for _ in range(6):
        t += 0.7
        st.add(125, ts=t)
    assert st.display_bpm > 110
    D._tick_high_hr_ring(a, now=svet.hodiny.t)
    assert svet.m.high_hr_ring_showing()


@pytest.mark.parametrize("zmena", [
    {"high_hr_ring": False}, {"listening": False}, {"_hr_session_open": False},
    {"_hr_state": "linked"}, {"_hr_state": "connecting"}, {"_hr_last_bpm": None},
    {"_hr_lost": True}, {"_snooze_job": "after#9"},
])
def test_bez_podmienky_sa_kruh_nezobrazi(hra, zmena):
    hra.a.__dict__.update(zmena)
    hra.a.hr_stats.display_bpm = 150
    hra.tik(10.0)
    assert not hra.root.plochy, zmena
    assert not hra.log.kruh() and not hra.a._high_hr_ring_spans


def test_pocas_drag_testu_sa_kruh_nezobrazi(hra):
    hra.m.test(1)
    hra.tik(10.0)
    assert not hra.m.is_active(3) and not hra.log.kruh()
    hra.m.stop_test(1)
    hra.tik()
    assert hra.m.high_hr_ring_showing(), "po teste uz ano"


def _bezi(hra, sekund=FADE + 2.0):
    """The ring started by the tick and breathing in its first exhale."""
    hra.tik()
    assert hra.m.high_hr_ring_showing()
    hra.tik(sekund)
    return hra.a._high_hr_ring_since


@pytest.mark.parametrize("zmena", [
    {"bpm": 110}, {"bpm": 95}, {"bpm": None}, {"high_hr_ring": False},
    {"_hr_state": "linked"}, {"_hr_last_bpm": None}, {"_hr_lost": True},
])
def test_bez_dovodu_kruh_dokonci_vydych(hra, zmena):
    """The heart rate dropped (or is gone, or the switch is off): no cut-off -
    the running exhale is finished, then the fade-out."""
    od = _bezi(hra)
    zmena = dict(zmena)
    if "bpm" in zmena:
        hra.a.hr_stats.display_bpm = zmena.pop("bpm")
    hra.a.__dict__.update(zmena)
    hra.tik()
    assert hra.m.high_hr_ring_finishing() and hra.m.is_active(3), "este dycha"
    hra.tik(10.0)
    assert not hra.m.is_active(3)
    assert _dych(hra)[-1][:2] == (False, 1.0), "konci vydychnuty"
    [(zaciatok, koniec)] = hra.a._high_hr_ring_spans
    assert zaciatok == od
    assert koniec - zaciatok == pytest.approx(FADE + 6.0, abs=0.3)
    assert hra.log.kruh()[-1] == "kruh pri vysokom tepe: skoncil po %.0f s" % (koniec - od)
    assert len(hra.log.kruh()) == 2
    assert hra.a._high_hr_ring_since is None


def test_tep_znova_hore_pocas_dokoncenia_kruh_dycha_dalej(hra):
    _bezi(hra)
    hra.a.hr_stats.display_bpm = 100
    hra.tik()
    assert hra.m.high_hr_ring_finishing()
    plocha = _kruh(hra).surface
    hra.a.hr_stats.display_bpm = 125
    hra.tik()
    assert not hra.m.high_hr_ring_finishing() and hra.m.high_hr_ring_showing()
    assert _kruh(hra).surface is plocha, "ziadny restart ani fade"
    hra.tik(40.0)
    assert hra.m.high_hr_ring_showing() and len(hra.root.plochy) == 1
    assert len(hra.log.kruh()) == 1 and not hra.a._high_hr_ring_spans


@pytest.mark.parametrize("zmena", [
    {"_snooze_job": "after#9"}, {"listening": False}, {"_hr_session_open": False},
])
def test_teraz_nie_stop_a_koniec_relacie_kruh_hned_zrusia(hra, zmena):
    od = _bezi(hra)
    hra.a.__dict__.update(zmena)
    hra.tik()
    assert not hra.m.is_active(3), "ide hned, nedokoncuje"
    assert hra.a._high_hr_ring_spans == [(od, hra.hodiny.t)]
    assert hra.log.kruh()[-1].startswith("kruh pri vysokom tepe: skoncil po ")
    hra.tik(10.0)
    assert not hra.root.plochy[-1].top and len(hra.root.plochy) == 1, "nevratil sa"


def test_kruh_pocka_na_hlasku_a_neprerusi_ju(hra):
    """A cue's picture and its exhale ring are on screen: the ring waits for
    them, then starts."""
    hra.m.trigger(0)
    sprievod = _kruh(hra).surface
    t_hlasky = hra.hodiny.t
    hra.tik()
    assert _kruh(hra).surface is sprievod, "sprievodny vydych neprerusi"
    assert _kruh(hra)._breath_mode == _kruh(hra).BREATH_EXHALE
    assert not hra.m.high_hr_ring_showing()
    hra.tik(30.0)
    assert hra.m.high_hr_ring_showing(), "po hlaske prisiel"
    assert hra.a._high_hr_ring_since > t_hlasky + 6.0, "az ked vydych hlasky dobehol"
    assert len(hra.log.kruh()) == 1


def test_kruh_pocka_aj_na_obrazok_bez_kruhu(hra):
    """With the breath picture off a cue comes without the ring - the loop
    still waits for its picture, and then draws (its own switch)."""
    hra.m.configure(3, enabled=False)
    hra.m.trigger(2)
    assert hra.m.is_active(2) and not hra.m.is_active(3)
    hra.tik(2.0)
    assert not hra.m.is_active(3)
    hra.tik(3.0)
    assert hra.m.high_hr_ring_showing()


def test_drag_test_inej_karty_kruh_dokonci(hra):
    _bezi(hra)
    hra.m.test(1)
    hra.tik()
    assert hra.m.high_hr_ring_finishing()
    hra.tik(10.0)
    assert not hra.m.is_active(3) and len(hra.a._high_hr_ring_spans) == 1


def test_drag_test_kruhu_uzavrie_zobrazenie(hra):
    od = _bezi(hra)
    hra.m.test(3)
    hra.tik()
    assert hra.a._high_hr_ring_spans == [(od, hra.hodiny.t)]
    hra.tik(20.0)
    assert hra.m.is_testing(3) and not hra.m.high_hr_ring_showing(), "test ostava"
    hra.m.stop_test(3)
    hra.tik()
    assert hra.m.high_hr_ring_showing(), "po teste znova"
    assert len(hra.log.kruh()) == 3


def test_hlasky_cakaju_kym_je_kruh_na_obrazovke(hra):
    """`_cue_can_fire` holds back every cue while ANY slot is active - and the
    loop is slot 3's ring, so no voice and no picture comes meanwhile."""
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is True
    hra.tik()
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is False
    hra.tik(60.0)
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is False, "cely cas, co dycha"
    hra.a.hr_stats.display_bpm = 90
    hra.tik(0.5)
    assert hra.m.is_active(3)
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is False, "ani kym dokoncuje"
    hra.tik(12.0)
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is True, "potom hlaska moze prist"


def test_zlyhany_kruh_neskusa_kazdy_tik(hra):
    hra.root.pokazit_vytvorenie = True
    hra.tik(10.0)
    assert len(hra.root.plochy) == 1, "jeden pokus, nie styri za sekundu"
    assert not hra.m.is_active(3)
    assert len(hra.log.kruh()) == 1 and "nepodarilo" in hra.log.kruh()[0]
    hra.root.pokazit_vytvorenie = False
    hra.tik(app_session.KRUH_TEP_ZNOVA_S)
    assert hra.m.high_hr_ring_showing(), "dalsi pokus po prestavke"


def test_tik_znesie_stareho_manazera(svet):
    a = _appka(svet, overlay_manager=types.SimpleNamespace(is_active=lambda i: False))
    D._tick_high_hr_ring(a, now=1.0)
    a = _appka(svet, overlay_manager=None)
    D._tick_high_hr_ring(a, now=1.0)


def test_tik_ma_vlastny_try_pred_spustacom_hlasky():
    uzol = uzol_metody("_tick_activity")
    pokusy = [u for u in ast.walk(uzol) if isinstance(u, ast.Try)
              and any("self._tick_high_hr_ring()" in ast.unparse(x) for x in u.body)]
    assert len(pokusy) == 1 and len(pokusy[0].body) == 1, "vlastny try"
    assert "app_log.exception(" in ast.unparse(pokusy[0].handlers[0])
    zdroj = zdroj_metody("_tick_activity")
    assert zdroj.index("self._tick_high_hr_ring()") < zdroj.index("self._tick_cue_trigger()")


def test_vypnuty_prepinac_nic_nemeni(hra):
    """Off by default: heart rate far above the limit for a minute, and the
    app does not touch the ring, writes nothing and cues are not held."""
    hra.a.high_hr_ring = False
    hra.a.hr_stats.display_bpm = 180
    hra.tik(60.0)
    assert not hra.root.plochy and not hra.kresba
    assert not hra.log.riadky and not hra.a._high_hr_ring_spans
    assert hra.a._high_hr_ring_since is None
    assert D._cue_can_fire(hra.a, hra.hodiny.t) is True


# --------------------------------------------------------------------------
# "not now", stop listening, session close
# --------------------------------------------------------------------------

def test_teraz_nie_kruh_hned_zrusi(svet, monkeypatch):
    a = teraz_nie._appka(monkeypatch)
    monkeypatch.setattr(app_session, "app_log", _Log())
    a.overlay_manager = svet.m
    svet.m.start_high_hr_ring()
    od = _time.time() - 5.0
    a._high_hr_ring_since = od
    a._high_hr_ring_spans = []
    a._start_snooze(30)
    assert not svet.m.is_active(3)
    [(zaciatok, koniec)] = a._high_hr_ring_spans
    assert zaciatok == od and koniec - zaciatok == pytest.approx(5.0, abs=2.0)


def test_stop_pocuvania_kruh_hned_zrusi(svet, monkeypatch):
    monkeypatch.setattr(app_session, "app_log", _Log())
    monkeypatch.setattr(app_session, "time", svet.hodiny)
    a = _appka(svet)
    nic = lambda *_a, **_k: None  # noqa: E731
    a.gamepad = types.SimpleNamespace(stop=nic)
    a.activity = types.SimpleNamespace(set_gamepad_watched=nic)
    a._suspend_cue_trigger = nic
    a._apply_listening_visuals = nic
    a.update_tray_icon = nic
    a._dopriprav_hlasky_po_hre = nic
    a._close_hr_session = nic
    D._tick_high_hr_ring(a, now=svet.hodiny.t)
    od = a._high_hr_ring_since
    svet.fronta.bez(4.0)
    D.stop_listening(a)
    assert not svet.m.is_active(3)
    assert a._high_hr_ring_spans == [(od, svet.hodiny.t)]


@pytest.mark.parametrize("koniec", [None, "spanok"])
def test_kruh_na_obrazovke_pri_konci_relacie(svet, monkeypatch, tmp_path, koniec):
    """A ring still on screen when the session closes goes, and its showing
    ends at the session's end - before the windows are built. After the PC
    slept (`koniec`), at the last tick before the gap."""
    monkeypatch.setattr(app_session, "app_log", _Log())
    monkeypatch.setattr(app_session, "time", svet.hodiny)
    a = vypnutie._appka(tmp_path)
    a.overlay_manager = svet.m
    svet.m.start_high_hr_ring()
    a._high_hr_ring_since = svet.hodiny.t - 40.0
    a._high_hr_ring_spans = [(svet.hodiny.t - 900.0, svet.hodiny.t - 800.0)]
    pri_oknach = []
    a._save_measure_windows = lambda: pri_oknach.append(
        (svet.m.is_active(3), list(a._high_hr_ring_spans)))
    if koniec is None:
        a._close_hr_session()
        cas = svet.hodiny.t
    else:
        cas = svet.hodiny.t - 10.0
        a._close_hr_session(koniec=cas)
    assert pri_oknach == [(False, [(svet.hodiny.t - 900.0, svet.hodiny.t - 800.0),
                                   (svet.hodiny.t - 40.0, cas)])]
    assert not svet.m.is_active(3) and a._high_hr_ring_since is None


def test_nova_relacia_zacina_bez_zobrazeni():
    zdroj = ast.unparse(uzol_metody("_open_hr_session"))
    assert "self._high_hr_ring_spans = []" in zdroj
    assert "self._high_hr_ring_since = None" in zdroj
    # ... after the previous session was closed (with its ring)
    assert zdroj.index("self._close_hr_session()") < zdroj.index(
        "self._high_hr_ring_spans = []")


def test_appka_ma_stav_kruhu_od_startu():
    init = ast.unparse(uzol_metody("__init__"))
    for riadok in ("self.high_hr_ring = settings.get('high_hr_ring') is True",
                   "self.high_hr_ring_bpm = normalize_high_hr_ring_bpm(",
                   "self._high_hr_ring_since = None", "self._high_hr_ring_spans = []"):
        assert riadok in init, riadok


# --------------------------------------------------------------------------
# measurement windows
# --------------------------------------------------------------------------

T0 = 10_000.0
CUE = T0 + 300.0


def _vzorky(od=T0, do=CUE + 200.0):
    return [(od + i * 2.0, 90.0) for i in range(int((do - od) / 2.0))]


def _hlaska(ts=CUE):
    return {"ts": ts, "category": "jaw", "cue_id": "slot1", "arm": "voice",
            "source": "auto", "delivered": True}


def test_kruh_v_okne_hlasky_ho_zneplatni():
    assert measure.R_KRUH_TEP == "kruh_pri_vysokom_tepe"
    w = measure.build_window(_hlaska(), _vzorky(), [CUE])
    assert w["valid"] is True and not w["reasons"]
    w = measure.build_window(_hlaska(), _vzorky(), [CUE],
                             ring_spans=[(CUE + 30.0, CUE + 75.0)])
    assert w["valid"] is False and w["reasons"] == [measure.R_KRUH_TEP]


@pytest.mark.parametrize("zobrazenie, zasahuje", [
    ((CUE - 120.0, CUE - 60.0), True),             # ends exactly at -60
    ((CUE - 120.0, CUE - 60.1), False),
    ((CUE + 180.0, CUE + 240.0), True),            # starts exactly at +180
    ((CUE + 180.1, CUE + 240.0), False),
    ((CUE - 500.0, CUE + 500.0), True),            # covers the whole window
    ((CUE - 10.0, CUE - 5.0), True),               # inside the pre-window
    ((CUE + 100.0, CUE + 100.0), True),            # zero length, inside
    ((CUE - 1000.0, CUE - 900.0), False),
])
def test_okraje_prekryvu(zobrazenie, zasahuje):
    assert measure.ring_conflict(CUE, [zobrazenie]) is zasahuje
    w = measure.build_window(_hlaska(), _vzorky(), [CUE], ring_spans=[zobrazenie])
    assert (measure.R_KRUH_TEP in w["reasons"]) is zasahuje


def test_pokazene_zobrazenie_sa_preskoci():
    zle = [None, ("a", 1.0), (1.0,), (float("nan"), CUE), {}, "xy"]
    assert measure.ring_conflict(CUE, zle) is False
    assert measure.ring_conflict(CUE, zle + [(CUE, CUE + 1.0)]) is True


def test_kazda_hlaska_relacie_sa_meria_zvlast():
    hlasky = [_hlaska(CUE), _hlaska(CUE + 600.0)]
    okna = measure.build_windows(hlasky, _vzorky(do=CUE + 900.0),
                                 ring_spans=[(CUE + 700.0, CUE + 720.0)])
    assert [measure.R_KRUH_TEP in w["reasons"] for w in okna] == [False, True]


# The windows `measure.build_windows` built from the input of
# `test_bez_kruhu_su_okna_bajt_po_bajte_rovnake` BEFORE the experiment
# (d6a5124, alpha 0.3.1) - the fixed point the "switch off = nothing
# changes" promise is checked against.
_OKNA_PRED_POKUSOM = [
    {"ts": 10300.0, "arm": "voice", "source": "auto", "category": "jaw",
     "cue_id": "slot1", "delivery": None, "pre_bpm": 90.0, "post_bpm": 90.0,
     "durability_bpm": 90.0, "pre_load": None, "post_load": None,
     "pre_activity": None, "post_activity": None, "valid": False,
     "reasons": ["refraktern_zona"], "session_started": 10000.0, "offset_s": 300.0,
     "game": "hra"},
    {"ts": 10420.0, "arm": "voice", "source": "auto", "category": "jaw",
     "cue_id": "slot1", "delivery": None, "pre_bpm": 90.0, "post_bpm": 90.0,
     "durability_bpm": 90.0, "pre_load": None, "post_load": None,
     "pre_activity": None, "post_activity": None, "valid": True,
     "reasons": [], "session_started": 10000.0, "offset_s": 420.0,
     "game": "hra"},
]


def test_bez_kruhu_su_okna_bajt_po_bajte_rovnake():
    """Pinned against the windows from before the experiment, not against
    themselves: a new key, a changed value or another key order with the
    switch off shows up here."""
    hlasky = [_hlaska(CUE), _hlaska(CUE + 120.0)]
    zaklad = json.dumps(_OKNA_PRED_POKUSOM)
    okna = measure.build_windows(hlasky, _vzorky(), game="hra", session_started=T0)
    assert json.dumps(okna) == zaklad, "okna sa zmenili oproti 0.3.1"
    for spans in (None, [], ()):
        okna = measure.build_windows(hlasky, _vzorky(), game="hra",
                                     session_started=T0, ring_spans=spans)
        assert json.dumps(okna) == zaklad, spans


def _okna_appky(monkeypatch, spans):
    zavolane = {}
    povodna = measure.build_windows

    def _spy(*args, **kwargs):
        zavolane.update(kwargs)
        return povodna(*args, **kwargs)

    ulozene = []
    monkeypatch.setattr(measure, "build_windows", _spy)
    monkeypatch.setattr(measure, "save_windows",
                        lambda cesta, okna, log=None: ulozene.extend(okna) or True)
    a = types.SimpleNamespace(
        hr_stats=types.SimpleNamespace(cues=[_hlaska()], _all=_vzorky(), _load=[],
                                       session_start=T0),
        activity=types.SimpleNamespace(samples=[]), active_profile_name="",
        cue_trigger=types.SimpleNamespace(params={}, silent_share=0.1, armed_count=1),
        _session_world="play", hr_windows_path="x", log_threadsafe=lambda _m: None)
    if spans is not None:
        a._high_hr_ring_spans = spans
    D._save_measure_windows(a)
    return zavolane, ulozene


@pytest.mark.parametrize("spans", [None, []])
def test_appka_bez_zobrazeni_posle_none(monkeypatch, spans):
    zavolane, [okno] = _okna_appky(monkeypatch, spans)
    assert zavolane["ring_spans"] is None
    assert okno["valid"] is True


def test_appka_posle_zobrazenia_relacie(monkeypatch):
    zavolane, [okno] = _okna_appky(monkeypatch, [(CUE + 20.0, CUE + 40.0)])
    assert zavolane["ring_spans"] == [(CUE + 20.0, CUE + 40.0)]
    assert okno["valid"] is False and okno["reasons"] == [measure.R_KRUH_TEP]


def test_zatvorenie_relacie_zastavi_kruh_pred_oknami():
    zdroj = ast.unparse(uzol_metody("_close_hr_session"))
    assert "_ak_vies(self, '_stop_high_hr_ring', koniec)" in zdroj
    assert zdroj.index("'_stop_high_hr_ring'") < zdroj.index("self._save_measure_windows()")


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------

@pytest.fixture
def subor(tmp_path, monkeypatch):
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]
    yield cesta
    i18n.set_lang(povodny)


def _citaj(cesta):
    with open(cesta, encoding="utf-8") as fh:
        return json.load(fh)


def test_predvolene_vypnute_110(subor):
    data, _ = nastavenia._nacitaj()                # no file yet
    assert data["high_hr_ring"] is False and data["high_hr_ring_bpm"] == 110
    nastavenia._zapis(subor, nastavenia._platne())  # an older file without the keys
    data, _ = nastavenia._nacitaj()
    assert data["high_hr_ring"] is False and data["high_hr_ring_bpm"] == 110
    assert (sm.DEFAULT_HIGH_HR_RING_BPM, sm.HIGH_HR_RING_BPM_MIN,
            sm.HIGH_HR_RING_BPM_MAX) == (110, 80, 200)


def test_ulozenie_a_nacitanie(subor):
    nastavenia._zapis(subor, nastavenia._platne())
    data, _ = nastavenia._nacitaj()
    nastavenia._uloz(data, high_hr_ring=True, high_hr_ring_bpm=132)
    ulozene = _citaj(subor)
    assert ulozene["high_hr_ring"] is True and ulozene["high_hr_ring_bpm"] == 132
    data, _ = nastavenia._nacitaj()
    assert data["high_hr_ring"] is True and data["high_hr_ring_bpm"] == 132
    # a save without them (an older dummy) writes the defaults
    nastavenia._uloz(data)
    ulozene = _citaj(subor)
    assert ulozene["high_hr_ring"] is False and ulozene["high_hr_ring_bpm"] == 110


@pytest.mark.parametrize("hodnota, cakane", [
    (130, 130), (80, 80), (200, 200), (79, 80), (250, 200), (-5, 80), (125.6, 126),
    ("120", 120), ("abc", 110), (None, 110), (True, 110), (False, 110), ([], 110),
    (float("nan"), 110), (float("inf"), 110), (float("-inf"), 110),
])
def test_hranica_sa_orezie_a_nezmysel_je_110(subor, hodnota, cakane):
    assert sm.normalize_high_hr_ring_bpm(hodnota) == cakane
    nastavenia._zapis(subor, dict(nastavenia._platne(), high_hr_ring_bpm=hodnota))
    data, obnova = nastavenia._nacitaj()
    assert data["high_hr_ring_bpm"] == cakane and obnova is None
    assert data["volume"] == 37, "zly kluc nezhodi zvysok nastaveni"


@pytest.mark.parametrize("hodnota, cakane", [
    (True, True), (False, False), ("yes", False), (1, False), ("true", False),
    (None, False), ({}, False),
])
def test_pokus_zapne_len_skutocne_true(subor, hodnota, cakane):
    nastavenia._zapis(subor, dict(nastavenia._platne(), high_hr_ring=hodnota))
    data, _ = nastavenia._nacitaj()
    assert data["high_hr_ring"] is cakane


def test_nie_je_v_profiloch_ani_v_kode_profilu():
    for slot in sm.default_slots():
        assert not any(k.startswith("high_hr") for k in slot)
    assert not any(k.startswith("high_hr") for k in sm.ZDIELANE_POLIA_SLOTU)
    for metoda in ("export_profile_code", "import_profile_from_code"):
        assert "high_hr" not in zdroj_metody(metoda), metoda


def test_zmena_v_nastaveniach_plati_hned_a_ulozi_sa():
    a = types.SimpleNamespace(high_hr_ring=False, high_hr_ring_bpm=110, ulozene=0)
    a.save_settings = lambda: setattr(a, "ulozene", a.ulozene + 1)
    D.on_high_hr_ring_change(a, enabled=True)
    assert a.high_hr_ring is True and a.ulozene == 1
    for bpm, cakane in ((125, 125), (300, 200), ("x", 110), (79.6, 80)):
        D.on_high_hr_ring_change(a, bpm=bpm)
        assert a.high_hr_ring_bpm == cakane
    D.on_high_hr_ring_change(a, enabled=False)
    assert a.high_hr_ring is False and a.high_hr_ring_bpm == 80 and a.ulozene == 6


# --------------------------------------------------------------------------
# the Breath card and its texts
# --------------------------------------------------------------------------

def _metoda_dialogu(meno):
    strom = ast.parse(zdroj_suboru("ui_dialogs.py"))
    trieda = next(u for u in strom.body
                  if isinstance(u, ast.ClassDef) and u.name == "OverlaySettingsDialog")
    return ast.unparse(next(f for f in trieda.body
                            if isinstance(f, ast.FunctionDef) and f.name == meno))


def test_karta_dychu_ma_prepinac_hranicu_a_vysvetlivku():
    dych = _metoda_dialogu("_build_breath_seconds_rows")
    # right below the inhale/exhale sliders
    assert dych.index("tr('overlay.breath_exhale')") < dych.index(
        "self._build_high_hr_ring_rows(row, pal)")
    kruh = _metoda_dialogu("_build_high_hr_ring_rows")
    for kus in ("ui_kit.switch(", "tr('overlay.high_hr_ring')",
                "self.app.on_high_hr_ring_change(enabled=var.get())",
                "ui_kit.slider(", "from_=HIGH_HR_RING_BPM_MIN", "to=HIGH_HR_RING_BPM_MAX",
                "tr('overlay.high_hr_ring_bpm', bpm=bpm)",
                "self.app.on_high_hr_ring_change(bpm=bpm)",
                "tr('overlay.high_hr_ring_hint')", "pal['text_faint']"):
        assert kus in kruh, kus


class _Prvok:
    """A widget of the Breath card without Tk: what it was made with."""

    def __init__(self, druh, prvky, *_a, **k):
        self.druh, self.k = druh, dict(k)
        prvky.append(self)

    def pack(self, *_a, **_k):
        return None

    def configure(self, **k):
        self.k.update(k)


class _Premenna:
    def __init__(self, value=None):
        self.hodnota = value

    def get(self):
        return self.hodnota

    def set(self, value):
        self.hodnota = value


@pytest.mark.parametrize("zapnute, hranica", [(True, 140), (False, 95), (True, 200)])
def test_karta_dychu_ukaze_ulozene_nastavenie(monkeypatch, zapnute, hranica):
    """The switch and the slider open with what the app really uses - not
    with the defaults - and a change goes straight to the app."""
    import ui_dialogs
    prvky, zmeny = [], []
    monkeypatch.setattr(ui_dialogs, "tk", types.SimpleNamespace(
        BooleanVar=_Premenna, DoubleVar=_Premenna))
    monkeypatch.setattr(ui_dialogs, "ctk", types.SimpleNamespace(
        CTkFrame=lambda *a, **k: _Prvok("ram", prvky, *a, **k),
        CTkLabel=lambda *a, **k: _Prvok("text", prvky, *a, **k)))
    monkeypatch.setattr(ui_dialogs, "ui_kit", types.SimpleNamespace(
        switch=lambda *a, **k: _Prvok("prepinac", prvky, *a, **k),
        slider=lambda *a, **k: _Prvok("posuvnik", prvky, *a, **k),
        ui=lambda velkost: velkost))
    povodny = i18n._lang["code"]
    i18n.set_lang("en")
    try:
        app = types.SimpleNamespace(
            high_hr_ring=zapnute, high_hr_ring_bpm=hranica,
            on_high_hr_ring_change=lambda **k: zmeny.append(k))
        dialog = types.SimpleNamespace(app=app)
        pal = {"text_dim": "#999", "text_faint": "#777"}
        ui_dialogs.OverlaySettingsDialog._build_high_hr_ring_rows(dialog, None, pal)

        [prepinac] = [p for p in prvky if p.druh == "prepinac"]
        [posuvnik] = [p for p in prvky if p.druh == "posuvnik"]
        assert prepinac.k["variable"].get() is zapnute, "prepinac neukazuje ulozeny stav"
        assert posuvnik.k["variable"].get() == hranica, "posuvnik neukazuje ulozenu hranicu"
        assert any(p.k.get("text") == "Above %d BPM" % hranica for p in prvky), \
            "popis neukazuje ulozenu hranicu"

        prepinac.k["variable"].set(not zapnute)
        prepinac.k["command"]()
        posuvnik.k["variable"].set(123.4)
        posuvnik.k["command"](123.4)
        assert zmeny == [{"enabled": not zapnute}, {"bpm": 123}]
        assert any(p.k.get("text") == "Above 123 BPM" for p in prvky)
    finally:
        i18n.set_lang(povodny)


_KLUCE = ("overlay.high_hr_ring", "overlay.high_hr_ring_bpm", "overlay.high_hr_ring_hint")


def test_texty_vo_vsetkych_jazykoch():
    S = i18n.STRINGS
    assert S["overlay.high_hr_ring"]["sk"] == "Kruh aj pri vysokom tepe (pokus)"
    assert S["overlay.high_hr_ring"]["en"] == "Ring at high heart rate too (experiment)"
    assert S["overlay.high_hr_ring_bpm"]["sk"] == "Nad {bpm} BPM"
    assert S["overlay.high_hr_ring_bpm"]["en"] == "Above {bpm} BPM"
    assert S["overlay.high_hr_ring_hint"]["sk"] == (
        "Dychový kruh dýcha dokola, kým je tep nad touto hranicou, a keď klesne, "
        "skončí po výdychu. Medzitým nepríde iná pripomienka.")
    for kluc in _KLUCE:
        zaznam = S[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk in i18n.LANGUAGES:
            if jazyk != "en":
                assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk, "anglicky")
        assert len(set(zaznam.values())) >= 10, (kluc, "preklady sa opakuju")
    for jazyk in i18n.LANGUAGES:
        text = i18n.tr_lang(jazyk, "overlay.high_hr_ring_bpm", bpm=145)
        assert text.count("145") == 1 and "BPM" in text, (jazyk, text)
    # Czech on its own, not the Slovak text
    for kluc in ("overlay.high_hr_ring", "overlay.high_hr_ring_hint"):
        assert S[kluc]["cs"] != S[kluc]["sk"], kluc


def test_ziadny_text_neprikazuje_upokojit_sa():
    zle = [(kluc, jazyk, najdene) for kluc in _KLUCE for jazyk in i18n.LANGUAGES
           for najdene in [slova._zakazane(i18n.STRINGS[kluc][jazyk])] if najdene]
    assert not zle, zle


def test_v_hre_ziadny_novy_text():
    """In the game the ring keeps the inhale/exhale captions it always had -
    the new texts are only for Settings, outside the in-game prefixes."""
    for kluc in _KLUCE:
        assert not kluc.startswith(slova._PREFIXY_V_HRE), kluc
    assert "high_hr" not in zdroj_suboru("hud_paint.py")
    zdroj = zdroj_suboru("overlay.py")
    assert not re.search(r"\btr\(", zdroj) and "i18n" not in zdroj
