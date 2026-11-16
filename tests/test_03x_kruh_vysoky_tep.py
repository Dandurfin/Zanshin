# -*- coding: utf-8 -*-
"""The ring at high heart rate (off by default).

When the smoothed heart rate (`HeartStats.display_bpm`) goes above the
player's limit (default 110 BPM), slot 3's breath ring breathes in a loop;
it keeps breathing while the heart rate stays above the limit minus a
margin (`app_session.KRUH_TEP_REZERVA_BPM`, 3 BPM), and once it drops to
that or below, the ring finishes breathed out and fades. Guarded here:

  * the loop (overlay.py): it starts with the exhale, loops and never ends
    by itself; a finish asked for in an exhale / an inhale ends breathed out
    (the empty ring), then fades; a new request while finishing keeps it
    breathing with no restart; the immediate stop; the drag test; a failed
    start leaves no window; new inhale/exhale lengths while it loops; a new
    size / position / monitor applies to the running loop at once,
  * the app tick (`_tick_high_hr_ring`): every condition that starts,
    keeps, finishes or stops it, the margin below the limit, waiting for a
    cue that is on screen, one app.log line at the start and one at the
    end, the showings as (start, end) - also on "not now", stop and
    session close,
  * cues wait while it is on screen (`_cue_can_fire`),
  * "not now" pressed while it is on screen does not count against the
    last cue (the cue ladder),
  * the session summary carries how long it showed (`high_hr_ring_s`,
    only when it did) and how many ready cues it held back, counted at the
    cancellation itself (`cues_withheld_ring`, only when above zero); the
    questionnaire says the ring held the cue back only when it held back
    every such cue (`SessionEndDialog._preco_ticho`); import, export and
    History take both fields,
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
import random
import re
import time as _time
import types

import pytest

import app as app_mod
import app_session
import data_io
import display
import hr_stats
import hud_paint
import i18n
import measure
import overlay
import rebrik
import settings_model as sm
import test_022b_data_nastavenia as nastavenia
import test_022b_data_vypnutie as vypnutie
import test_03x_vydych_vizual as vv
import test_cue_words as slova
import test_teraz_nie as teraz_nie
import trigger
from _zdroj_appky import uzol_metody, zdroj_metody, zdroj_suboru

OUT, IN = vv.OUT, vv.IN
D = app_mod.DandurfApp
REZERVA = app_session.KRUH_TEP_REZERVA_BPM
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
    {"bpm": 110 - REZERVA}, {"bpm": 95}, {"bpm": None}, {"high_hr_ring": False},
    {"_hr_state": "linked"}, {"_hr_last_bpm": None}, {"_hr_lost": True},
])
def test_bez_dovodu_kruh_dokonci_vydych(hra, zmena):
    """The heart rate dropped to the limit minus the margin or below (or is
    gone, or the switch is off): no cut-off - the running exhale is
    finished, then the fade-out."""
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


# --------------------------------------------------------------------------
# the margin below the limit (hysteresis, `KRUH_TEP_REZERVA_BPM`)
#
# A heart rate hovering at 110-111 with the limit 110 made the ring come and
# go every few seconds. It starts above the limit (unchanged), but once it
# breathes it keeps breathing while the heart rate is above the limit minus
# the margin, and finishes at or below that.
# --------------------------------------------------------------------------

def test_rezerva_su_tri_bpm():
    assert REZERVA == 3 and isinstance(REZERVA, int)
    zdroj = zdroj_suboru("app_session.py")
    assert zdroj.index("KRUH_TEP_ZNOVA_S = ") < zdroj.index("KRUH_TEP_REZERVA_BPM = "), \
        "konstanta ma byt vedla KRUH_TEP_ZNOVA_S"


@pytest.mark.parametrize("bpm", [110 - i for i in range(REZERVA)])      # 110, 109, 108
def test_v_rezerve_pod_hranicou_kruh_dycha_dalej(hra, bpm):
    _bezi(hra)
    hra.a.hr_stats.display_bpm = bpm
    hra.tik(60.0)
    assert hra.m.high_hr_ring_showing(), bpm
    assert not hra.m.high_hr_ring_finishing(), "v rezerve pod hranicou nema dokoncit"
    assert len(hra.root.plochy) == 1 and not hra.a._high_hr_ring_spans
    assert len(hra.log.kruh()) == 1, "ziadne nove zobrazenie ani koniec"


@pytest.mark.parametrize("bpm", [110 - REZERVA, 110 - REZERVA - 1, 90])  # 107, 106, 90
def test_na_rezerve_alebo_pod_nou_kruh_dokonci(hra, bpm):
    od = _bezi(hra)
    hra.a.hr_stats.display_bpm = bpm
    hra.tik()
    assert hra.m.high_hr_ring_finishing() and hra.m.is_active(3), bpm
    hra.tik(10.0)
    assert not hra.m.is_active(3)
    assert _dych(hra)[-1][:2] == (False, 1.0), "konci vydychnuty"
    [(zaciatok, _koniec)] = hra.a._high_hr_ring_spans
    assert zaciatok == od and len(hra.log.kruh()) == 2


@pytest.mark.parametrize("bpm", [110 - i for i in range(REZERVA + 1)])  # 110 .. 107
def test_rezerva_neplati_pre_novy_kruh(hra, bpm):
    """A ring that is not on screen needs more than the limit itself."""
    hra.a.hr_stats.display_bpm = bpm
    hra.tik(10.0)
    assert not hra.root.plochy and not hra.log.kruh(), bpm


def test_tep_nad_rezervou_zrusi_dokoncenie(hra):
    _bezi(hra)
    hra.a.hr_stats.display_bpm = 110 - REZERVA                 # 107: finishes
    hra.tik()
    assert hra.m.high_hr_ring_finishing()
    plocha = _kruh(hra).surface
    hra.a.hr_stats.display_bpm = 110 - REZERVA + 1             # 108: back in the margin
    hra.tik()
    assert not hra.m.high_hr_ring_finishing() and hra.m.high_hr_ring_showing()
    assert _kruh(hra).surface is plocha and len(hra.root.plochy) == 1, "ziadny restart ani fade"
    hra.tik(40.0)
    assert hra.m.high_hr_ring_showing() and not hra.a._high_hr_ring_spans
    assert len(hra.log.kruh()) == 1


def test_po_zmiznuti_treba_znova_nad_hranicu(hra):
    _bezi(hra)
    hra.a.hr_stats.display_bpm = 110 - REZERVA
    while hra.m.high_hr_ring_showing():
        hra.tik()
    # breathed out, the fade-out is running: the margin no longer holds it
    assert hra.m.is_active(3)
    hra.a.hr_stats.display_bpm = 110
    hra.tik()
    assert not hra.m.high_hr_ring_showing() and not hra.m.high_hr_ring_finishing()
    hra.tik(2.0)
    assert not hra.m.is_active(3) and len(hra.a._high_hr_ring_spans) == 1
    for bpm in (110 - REZERVA + 1, 109, 110):
        hra.a.hr_stats.display_bpm = bpm
        hra.tik(5.0)
        assert not hra.m.is_active(3), bpm
    assert len(hra.log.kruh()) == 2
    hra.a.hr_stats.display_bpm = 111
    hra.tik()
    assert hra.m.high_hr_ring_showing(), "nad hranicou znova"
    assert hra.log.kruh()[-1] == "kruh pri vysokom tepe: zobrazeny (tep 111, hranica 110)"


@pytest.mark.parametrize("hranica", [80, 125, 140, 200])
def test_rezerva_plati_pod_vlastnou_hranicou(hra, hranica):
    hra.a.high_hr_ring_bpm = hranica
    hra.a.hr_stats.display_bpm = hranica
    hra.tik(3.0)
    assert not hra.root.plochy, "na hranici sa neukaze"
    hra.a.hr_stats.display_bpm = hranica + 1
    _bezi(hra)
    hra.a.hr_stats.display_bpm = hranica - REZERVA + 1
    hra.tik(30.0)
    assert hra.m.high_hr_ring_showing() and not hra.m.high_hr_ring_finishing(), hranica
    hra.a.hr_stats.display_bpm = hranica - REZERVA
    hra.tik()
    assert hra.m.high_hr_ring_finishing(), hranica
    hra.tik(12.0)
    assert not hra.m.is_active(3) and len(hra.a._high_hr_ring_spans) == 1


@pytest.mark.parametrize("zmena", [
    {"bpm": None}, {"high_hr_ring": False}, {"_hr_state": "linked"},
    {"_hr_last_bpm": None}, {"_hr_lost": True}, "drag_test",
])
def test_bez_tepu_kruh_dokonci_aj_v_rezerve(hra, zmena):
    """No heart rate, the switch off or a drag test finish it whatever the
    number - the margin is only about the heart rate."""
    _bezi(hra)
    hra.a.hr_stats.display_bpm = 109                           # in the margin
    hra.tik()
    assert not hra.m.high_hr_ring_finishing()
    if zmena == "drag_test":
        hra.m.test(1)
    else:
        zmena = dict(zmena)
        if "bpm" in zmena:
            hra.a.hr_stats.display_bpm = zmena.pop("bpm")
        hra.a.__dict__.update(zmena)
    hra.tik()
    assert hra.m.high_hr_ring_finishing() and hra.m.is_active(3), zmena
    hra.tik(10.0)
    assert not hra.m.high_hr_ring_showing() and len(hra.a._high_hr_ring_spans) == 1


@pytest.mark.parametrize("zmena", [
    {"_snooze_job": "after#9"}, {"listening": False}, {"_hr_session_open": False},
])
def test_v_rezerve_teraz_nie_stop_a_koniec_relacie_kruh_hned_zrusia(hra, zmena):
    od = _bezi(hra)
    hra.a.hr_stats.display_bpm = 108
    hra.tik()
    hra.a.__dict__.update(zmena)
    hra.tik()
    assert not hra.m.is_active(3), "ide hned, nedokoncuje"
    assert hra.a._high_hr_ring_spans == [(od, hra.hodiny.t)]


def test_tik_cita_rezervu_z_konstanty():
    zdroj = ast.unparse(uzol_metody("_tick_high_hr_ring"))
    assert "prah - KRUH_TEP_REZERVA_BPM if showing else prah" in zdroj
    assert "bpm > hranica" in zdroj and "bpm > prah" not in zdroj


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


# "Not now" while the ring is on screen dismisses the ring, not the last cue:
# it must not count for the cue ladder (`_zapis_snooze_po_hlaske`), or the
# cues would go a step quieter for something they did not do.

_RIADOK_REBRIKA = ("rebrik hlasky: teraz nie pocas kruhu pri vysokom tepe - "
                   "do rebrika sa nepocita")


def _teraz_nie_po_hlaske(svet, monkeypatch, kruh):
    """A delivered automatic cue, 20 s later "not now" - with the ring
    breathing, finishing, or not on screen (`kruh` None)."""
    import app_controls
    h = teraz_nie._Hodiny(2_000_000.0)
    a = teraz_nie._appka(monkeypatch, h)
    log = _Log()
    monkeypatch.setattr(app_controls, "app_log", log)
    monkeypatch.setattr(app_session, "app_log", log)
    a.overlay_manager = svet.m
    a._high_hr_ring_since = None
    a._high_hr_ring_spans = []
    a.hr_stats.note_trigger(ts=h.t, auto=True, source="auto", delivered=True)
    h.t += 20.0
    if kruh is not None:
        assert svet.m.start_high_hr_ring()
        a._high_hr_ring_since = h.t - 5.0
        if kruh == "dokoncuje":
            assert svet.m.finish_high_hr_ring() and svet.m.high_hr_ring_finishing()
    a._start_snooze(30)
    return a, h, log


@pytest.mark.parametrize("kruh", ["dycha", "dokoncuje"])
def test_teraz_nie_pri_kruhu_sa_do_rebrika_nepocita(svet, monkeypatch, tmp_path, kruh):
    a, h, log = _teraz_nie_po_hlaske(svet, monkeypatch, kruh)
    assert a._snooze_po_hlaske is None, "teraz nie pri kruhu sa zapisalo do rebrika"
    assert "snooze_after_s" not in a.hr_stats.cues[-1]
    assert log.riadky.count(_RIADOK_REBRIKA) == 1
    # everything else about "not now" as before
    assert not svet.m.is_active(3) and a._high_hr_ring_since is None, "kruh ostal"
    assert a._high_hr_ring_spans == [(h.t - 5.0, h.t)]
    assert a._snooze_rel_od == h.t, "cas stisenia sa nerata"
    assert a.cue_trigger._suspended_by == trigger.A_SNOOZE
    assert a.root.ulohy[a._snooze_job][0] == 30 * 60 * 1000
    assert a.denn[-1] == i18n.tr("log.snooze_started", minutes=30)
    h.t += 600.0                                    # play goes on
    s = teraz_nie._zavri(monkeypatch, a, tmp_path)
    assert "snooze_after_cue_s" not in s and "snooze_then_s" not in s
    assert rebrik.signal_dole(s) is None, "pripomienky stichli kvoli kruhu"
    assert s["snoozed_s"] == 600.0
    assert s["high_hr_ring_s"] == 5.0


def test_teraz_nie_bez_kruhu_sa_do_rebrika_pocita_ako_predtym(svet, monkeypatch, tmp_path):
    a, h, log = _teraz_nie_po_hlaske(svet, monkeypatch, None)
    assert a._snooze_po_hlaske == (20.0, h.t)
    assert a.hr_stats.cues[-1]["snooze_after_s"] == 20.0
    assert _RIADOK_REBRIKA not in log.riadky
    h.t += 600.0
    s = teraz_nie._zavri(monkeypatch, a, tmp_path)
    assert (s["snooze_after_cue_s"], s["snooze_then_s"]) == (20.0, 600.0)
    assert rebrik.signal_dole(s) == rebrik.D_SNOOZE
    assert "high_hr_ring_s" not in s


def test_teraz_nie_po_zmiznutom_kruhu_sa_pocita(svet, monkeypatch):
    """The ring breathed out and the tick closed its showing: "not now" now
    counts again, as with no ring at all."""
    import app_controls
    h = teraz_nie._Hodiny(2_000_000.0)
    a = teraz_nie._appka(monkeypatch, h)
    monkeypatch.setattr(app_controls, "app_log", _Log())
    a.overlay_manager = svet.m
    a._high_hr_ring_since = None
    a._high_hr_ring_spans = [(h.t - 50.0, h.t - 10.0)]
    a.hr_stats.note_trigger(ts=h.t - 30.0, auto=True, source="auto", delivered=True)
    a._start_snooze(30)
    assert a._snooze_po_hlaske == (30.0, h.t)


def test_kruh_na_obrazovke_zisti_aj_stary_manazer():
    a = D.__new__(D)
    a._high_hr_ring_since = None
    for om in (None, types.SimpleNamespace(is_active=lambda i: False),
               types.SimpleNamespace(high_hr_ring_showing=lambda: False)):
        a.overlay_manager = om
        assert a._high_hr_ring_on_screen() is False, om

    def _zlyhaj():
        raise RuntimeError("zlyhanie")
    a.overlay_manager = types.SimpleNamespace(high_hr_ring_showing=_zlyhaj)
    assert a._high_hr_ring_on_screen() is False
    a.overlay_manager = types.SimpleNamespace(high_hr_ring_showing=lambda: True)
    assert a._high_hr_ring_on_screen() is True
    a.overlay_manager = None
    a._high_hr_ring_since = 123.0
    assert a._high_hr_ring_on_screen() is True
    del a.__dict__["_high_hr_ring_since"]           # a dummy without the state
    assert a._high_hr_ring_on_screen() is False


def test_teraz_nie_sa_pyta_na_kruh_pred_jeho_zastavenim():
    uzol = uzol_metody("_start_snooze")
    [vetva] = [u for u in ast.walk(uzol) if isinstance(u, ast.If)
               and ast.unparse(u.test) == "self._high_hr_ring_on_screen()"]
    assert "app_log.info(" in ast.unparse(vetva.body[0])
    assert [ast.unparse(u) for u in vetva.orelse] == ["self._zapis_snooze_po_hlaske(now)"]
    telo = ast.unparse(uzol)
    assert telo.index("self._high_hr_ring_on_screen()") < telo.index(
        "self._stop_high_hr_ring()"), "na kruh sa treba spytat skor, nez zmizne"
    assert telo.count("self._zapis_snooze_po_hlaske(") == 1


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
    # the cues it held back belong to the session too
    assert "self._cues_withheld_ring = 0" in zdroj
    # ... after the previous session was closed (with its ring)
    assert zdroj.index("self._close_hr_session()") < zdroj.index(
        "self._high_hr_ring_spans = []")
    assert zdroj.index("self._close_hr_session()") < zdroj.index(
        "self._cues_withheld_ring = 0")


def test_appka_ma_stav_kruhu_od_startu():
    init = ast.unparse(uzol_metody("__init__"))
    for riadok in ("self.high_hr_ring = settings.get('high_hr_ring') is True",
                   "self.high_hr_ring_bpm = normalize_high_hr_ring_bpm(",
                   "self._high_hr_ring_since = None", "self._high_hr_ring_spans = []",
                   "self._cues_withheld_ring = 0"):
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
                "tr('overlay.high_hr_ring_hint', margin=KRUH_TEP_REZERVA_BPM)",
                "pal['text_faint']"):
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
        [vysvetlivka] = [p for p in prvky
                         if "No other cue comes meanwhile" in str(p.k.get("text"))]
        assert "at least %d BPM below it" % REZERVA in vysvetlivka.k["text"], \
            "vysvetlivka neuvadza skutocnu rezervu pod hranicou"
        assert "{" not in vysvetlivka.k["text"]

        prepinac.k["variable"].set(not zapnute)
        prepinac.k["command"]()
        posuvnik.k["variable"].set(123.4)
        posuvnik.k["command"](123.4)
        assert zmeny == [{"enabled": not zapnute}, {"bpm": 123}]
        assert any(p.k.get("text") == "Above 123 BPM" for p in prvky)
    finally:
        i18n.set_lang(povodny)


_KLUCE = ("overlay.high_hr_ring", "overlay.high_hr_ring_bpm", "overlay.high_hr_ring_hint",
         "dnes.high_hr_ring_quick")


def test_texty_vo_vsetkych_jazykoch():
    S = i18n.STRINGS
    assert S["overlay.high_hr_ring"]["sk"] == "Kruh aj pri vysokom tepe"
    assert S["overlay.high_hr_ring"]["en"] == "Ring at high heart rate too"
    assert S["dnes.high_hr_ring_quick"]["sk"] == "Dychový kruh nad {bpm} BPM"
    assert S["dnes.high_hr_ring_quick"]["en"] == "Breath ring above {bpm} BPM"
    assert S["overlay.high_hr_ring_bpm"]["sk"] == "Nad {bpm} BPM"
    assert S["overlay.high_hr_ring_bpm"]["en"] == "Above {bpm} BPM"
    assert S["overlay.high_hr_ring_hint"]["sk"] == (
        "Dychový kruh sa ukáže, keď tep prekročí túto hranicu, a dýcha dokola, "
        "kým neklesne aspoň o {margin} BPM pod ňu; potom skončí po výdychu. "
        "Medzitým nepríde iná pripomienka.")
    assert S["overlay.high_hr_ring_hint"]["en"] == (
        "The breath ring shows when your heart rate goes above this limit and keeps "
        "breathing until it drops at least {margin} BPM below it; then it ends after "
        "an exhale. No other cue comes meanwhile.")
    for kluc in _KLUCE:
        zaznam = S[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk in i18n.LANGUAGES:
            if jazyk != "en":
                assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk, "anglicky")
        assert len(set(zaznam.values())) >= 10, (kluc, "preklady sa opakuju")
    for kluc in ("overlay.high_hr_ring_bpm", "dnes.high_hr_ring_quick"):
        for jazyk in i18n.LANGUAGES:
            text = i18n.tr_lang(jazyk, kluc, bpm=145)
            assert text.count("145") == 1 and "BPM" in text, (kluc, jazyk, text)
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


def test_texty_uz_nehovoria_pokus():
    """The author tested the ring and keeps it (16. 11. 2026) - the switches
    do not call it an experiment any more, in no language."""
    znacky = ("pokus", "experiment", "эксперимент", "експеримент", "essai",
              "試験", "试验")
    zle = [(kluc, jazyk) for kluc in _KLUCE for jazyk in i18n.LANGUAGES
           if any(z in i18n.STRINGS[kluc][jazyk].lower() for z in znacky)]
    assert not zle, zle


# --------------------------------------------------------------------------
# the quick row on Today (under "On-screen HR panel")
# --------------------------------------------------------------------------

def _stavba_dnes():
    return zdroj_metody("_build_dnes_page")


def test_rychly_riadok_na_dnes_je_medzi_panelom_a_statistikami():
    zdroj = _stavba_dnes()
    hud = zdroj.index('tr("hud.quick_label")')
    kruh = zdroj.index("self._high_hr_ring_quick_text()")
    stat = zdroj.index('tr("dashboard.stats_title")')
    assert hud < kruh < stat, "riadok kruhu ma byt medzi panelom tepu a Moje statistiky"
    plochy = re.sub(r"\s+", "", zdroj)
    for kus in ("tk.BooleanVar(value=bool(self.high_hr_ring))",
                "self.on_high_hr_ring_change(enabled=self.high_hr_ring_quick_var.get())",
                "command=self.open_overlay_settings"):
        assert kus in plochy, kus


class _Text:
    def __init__(self):
        self.text = None

    def configure(self, **k):
        self.text = k.get("text", self.text)


def _appka_dnes(zapnute=False, hranica=110):
    a = types.SimpleNamespace(high_hr_ring=zapnute, high_hr_ring_bpm=hranica, ulozene=0,
                              high_hr_ring_quick_var=_Premenna(zapnute),
                              high_hr_ring_quick_label=_Text())
    a.save_settings = lambda: setattr(a, "ulozene", a.ulozene + 1)
    a._high_hr_ring_quick_text = lambda: D._high_hr_ring_quick_text(a)
    return a


def test_prepinac_v_dialogu_pohne_prepinacom_na_dnes():
    a = _appka_dnes(zapnute=False)
    D.on_high_hr_ring_change(a, enabled=True)
    assert a.high_hr_ring_quick_var.get() is True, "prepinac na Dnes neprebral zapnutie"
    D.on_high_hr_ring_change(a, enabled=False)
    assert a.high_hr_ring_quick_var.get() is False, "prepinac na Dnes neprebral vypnutie"
    # a change of the limit alone does not touch the switch
    a.high_hr_ring_quick_var.set("netknute")
    D.on_high_hr_ring_change(a, bpm=130)
    assert a.high_hr_ring_quick_var.get() == "netknute"
    assert a.ulozene == 3


def test_hranica_sa_ukaze_v_riadku_na_dnes():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    try:
        a = _appka_dnes(hranica=110)
        assert D._high_hr_ring_quick_text(a) == "DYCHOVÝ KRUH NAD 110 BPM"
        D.on_high_hr_ring_change(a, bpm=135)
        assert a.high_hr_ring_quick_label.text == "DYCHOVÝ KRUH NAD 135 BPM"
        D.on_high_hr_ring_change(a, bpm=999)
        assert a.high_hr_ring_quick_label.text == "DYCHOVÝ KRUH NAD 200 BPM"
        a.high_hr_ring_quick_label.text = "netknute"
        D.on_high_hr_ring_change(a, enabled=True)
        assert a.high_hr_ring_quick_label.text == "netknute",             "zapnutie samo popis nema prepisovat"
    finally:
        i18n.set_lang(povodny)


def test_zmena_bez_riadku_na_dnes_nespadne():
    """Before the Today page is built (or in a dummy) the row does not exist."""
    a = types.SimpleNamespace(high_hr_ring=False, high_hr_ring_bpm=110, ulozene=0)
    a.save_settings = lambda: setattr(a, "ulozene", a.ulozene + 1)
    D.on_high_hr_ring_change(a, enabled=True, bpm=120)
    assert a.high_hr_ring is True and a.high_hr_ring_bpm == 120 and a.ulozene == 1


# --------------------------------------------------------------------------
# the session summary: how long the ring showed (`high_hr_ring_s`)
# --------------------------------------------------------------------------

def test_suhrn_nesie_cas_kruhu_len_ked_sa_ukazal(tmp_path):
    """Only a session in which the ring showed gets the field - every other
    one stays the same as before, byte for byte."""
    a = vypnutie._appka(tmp_path)
    teraz = _time.time()
    pred = a._suhrn_relacie(koniec=teraz)          # a dummy without the ring's state
    assert "high_hr_ring_s" not in pred
    a._high_hr_ring_spans = []
    a._high_hr_ring_since = None
    assert json.dumps(a._suhrn_relacie(koniec=teraz)) == json.dumps(pred)
    a._high_hr_ring_spans = [(teraz - 50.0, teraz - 50.0)]   # zero length
    assert json.dumps(a._suhrn_relacie(koniec=teraz)) == json.dumps(pred)

    spans = [(teraz - 300.0, teraz - 240.0), (teraz - 100.0, teraz - 99.5)]
    a._high_hr_ring_spans = list(spans)
    a._high_hr_ring_since = teraz - 10.0            # still on screen
    s = a._suhrn_relacie(koniec=teraz)
    assert s["high_hr_ring_s"] == 70.5
    assert {k: v for k, v in s.items() if k != "high_hr_ring_s"} == pred
    # no side effects - the checkpoint asks in the middle of a session
    assert a._high_hr_ring_spans == spans and a._high_hr_ring_since == teraz - 10.0
    assert a._suhrn_relacie(koniec=teraz) == s


def test_kruh_na_obrazovke_pri_zatvoreni_je_v_ulozenom_suhrne(svet, monkeypatch, tmp_path):
    monkeypatch.setattr(app_session, "app_log", _Log())
    a = vypnutie._appka(tmp_path)
    a.overlay_manager = svet.m
    svet.m.start_high_hr_ring()
    teraz = _time.time()
    a._high_hr_ring_since = teraz - 40.0
    a._high_hr_ring_spans = [(teraz - 900.0, teraz - 800.0)]
    a._close_hr_session()
    [ulozena] = vypnutie._historia(a)
    assert ulozena["high_hr_ring_s"] == pytest.approx(140.0, abs=2.0)
    [dotaznik] = a.dotazniky
    assert dotaznik["high_hr_ring_s"] == ulozena["high_hr_ring_s"]
    assert not svet.m.is_active(3)


def test_relacia_bez_kruhu_pole_nema(tmp_path):
    a = vypnutie._appka(tmp_path)
    a._cues_withheld_ring = 0
    a._close_hr_session()
    [ulozena] = vypnutie._historia(a)
    [dotaznik] = a.dotazniky
    for pole in ("high_hr_ring_s", "cues_withheld_ring"):
        assert pole not in ulozena, pole
        assert pole not in dotaznik, pole


def test_suhrn_nesie_podrzane_hlasky_len_ked_nejake_boli(tmp_path):
    """`cues_withheld_ring` only when the ring held back at least one ready
    cue - every other session stays the same as before, byte for byte. Only
    a whole count (the app's own counter), never a bool or a text."""
    a = vypnutie._appka(tmp_path)
    teraz = _time.time()
    pred = a._suhrn_relacie(koniec=teraz)          # a dummy without the counter
    assert "cues_withheld_ring" not in pred
    for nic in (0, -1, None, True, "2", 2.5):
        a._cues_withheld_ring = nic
        assert json.dumps(a._suhrn_relacie(koniec=teraz)) == json.dumps(pred), nic
    a._cues_withheld_ring = 2
    s = a._suhrn_relacie(koniec=teraz)
    assert s["cues_withheld_ring"] == 2
    assert {k: v for k, v in s.items() if k != "cues_withheld_ring"} == pred
    # no side effects - the checkpoint asks in the middle of a session
    assert a._cues_withheld_ring == 2 and a._suhrn_relacie(koniec=teraz) == s


def test_podrzane_hlasky_su_v_ulozenom_suhrne(tmp_path):
    a = vypnutie._appka(tmp_path)
    a.cue_trigger.zadrzane[trigger.A_NEDALO_SA] = 3
    a._cues_withheld_ring = 3
    a._close_hr_session()
    [ulozena] = vypnutie._historia(a)
    assert ulozena["cues_withheld_ring"] == 3
    assert ulozena["cues_withheld"][trigger.A_NEDALO_SA] == 3
    [dotaznik] = a.dotazniky
    assert dotaznik["cues_withheld_ring"] == 3


def test_suhrn_rata_cas_kruhu_cez_metodu_kruhu():
    zdroj = ast.unparse(uzol_metody("_suhrn_relacie"))
    assert "getattr(self, '_high_hr_ring_seconds', None)" in zdroj
    assert "round(sekundy(teraz), 1)" in zdroj
    assert "if kruh_s > 0.0:" in zdroj


def test_suhrn_bez_metod_kruhu_nespadne(tmp_path, monkeypatch):
    """A dummy that borrows only `_suhrn_relacie` (tests/test_022_ukoncenie_
    dennik.py) has no ring at all - no field, no error in app.log."""
    import app_data
    log = _Log()
    monkeypatch.setattr(app_data, "app_log", log)
    a = vypnutie._appka(tmp_path)
    a._high_hr_ring_seconds = None
    assert "high_hr_ring_s" not in a._suhrn_relacie()
    assert not log.riadky


def test_import_a_export_preberu_cas_kruhu(tmp_path):
    relacia = {"started": 1789000000.0, "duration_s": 3600.0, "high_hr_ring_s": 412.5,
               "cues_withheld_ring": 2,
               "cues_withheld": {"bez_pauzy": 0, "nevhodna_chvila": 0, "nedalo_sa": 2}}
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([relacia], []))
    sessions, _okna, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0 and sessions == [dict(relacia, imported=True)]
    for pole in ("high_hr_ring_s", "cues_withheld_ring"):
        assert data_io._TYPY_RELACIE[pole] is data_io._konecne, pole
        for zle in ("412", True, [1.0], {"a": 1}, float("nan"), float("inf")):
            cista = data_io.clean_session(dict(relacia, **{pole: zle}))
            assert cista is not None, (pole, zle)
            assert pole not in cista, (pole, zle)
            assert cista["cues_withheld"] == relacia["cues_withheld"]


def test_historia_znesie_cas_kruhu(tmp_path):
    import hr_insights
    relacie = [{"started": 1789000000.0 + i * 86400.0, "duration_s": 2400.0,
                "samples": 900, "avg_bpm": 95, "max_bpm": 131, "baseline_bpm": 70,
                "auto_triggers": 0, "above_runs": 3, "longest_above_s": 30.0,
                "runs_cancelled_gap": 0, "stress_hold_s": 45.0,
                "cues_withheld": {"bez_pauzy": 0, "nevhodna_chvila": 0, "nedalo_sa": 1}}
               for i in range(4)]
    s_kruhom = [dict(r, high_hr_ring_s=300.0 + i, cues_withheld_ring=1)
                for i, r in enumerate(relacie)]
    cesta = str(tmp_path / "r.csv")
    assert hr_stats.export_sessions_csv(s_kruhom, cesta) == 4
    with open(cesta, encoding="utf-8-sig") as fh:
        riadky = [r for r in fh.read().splitlines() if r]
    assert len(riadky) == 5
    assert all(len(r.split(";")) == len(hr_stats.CSV_COLUMNS) for r in riadky)
    a = D.__new__(D)
    assert D._history_detail_values(a, s_kruhom[-1]) == D._history_detail_values(a, relacie[-1])

    def kluce(rel):
        return sorted(i["key"] for i in hr_insights.analyze(rel, now=1789500000.0))
    assert kluce(s_kruhom) == kluce(relacie)


# --------------------------------------------------------------------------
# the cues the ring held back (`cues_withheld_ring`), counted at the
# cancellation itself - not "the ring showed some time in the session"
# --------------------------------------------------------------------------

_RIADOK_PODRZAL = "natiahnutie zrusene: hlasku podrzal kruh pri vysokom tepe"


def _zrusenie(dovod=trigger.A_NEDALO_SA):
    return {"typ": trigger.E_ABORT, "ts": 1.0, "reason": dovod, "arm": None,
            "waited_s": 90.0}


def _vsetky_obrazky_vypnute():
    return [dict(c, enabled=False) for c in sm.default_overlay_configs()]


def _appka_zrusenia(monkeypatch, **navyse):
    """DandurfApp without Tk with what `_on_cue_event` and `_cue_held_by_ring`
    read: listening, no "not now", the default pictures (on), the ring on
    screen (an open showing)."""
    import app_today
    log = _Log()
    monkeypatch.setattr(app_today, "app_log", log)
    a = D.__new__(D)
    a.listening = True
    a._snooze_job = None
    a.overlay_configs = sm.default_overlay_configs()
    a._high_hr_ring_since = 100.0
    a.overlay_manager = None
    a._cue_log = []
    a._cues_withheld_ring = 0
    a._set_enso_armed = lambda _armed: None
    a.__dict__.update(navyse)
    return a, log


def test_zrusenie_pri_kruhu_sa_zrata(monkeypatch):
    a, log = _appka_zrusenia(monkeypatch)
    a._on_cue_event(_zrusenie())
    a._on_cue_event(_zrusenie())
    assert a._cues_withheld_ring == 2
    assert log.riadky.count(_RIADOK_PODRZAL) == 2
    assert len(a._cue_log) == 2, "zrusenie sa zapisuje ako predtym"
    # the ring found through the overlay's own state, with no open showing
    a, _log = _appka_zrusenia(monkeypatch, _high_hr_ring_since=None,
                              overlay_manager=types.SimpleNamespace(
                                  high_hr_ring_showing=lambda: True))
    a._on_cue_event(_zrusenie())
    assert a._cues_withheld_ring == 1
    # a dummy without the counter
    a, _log = _appka_zrusenia(monkeypatch)
    del a.__dict__["_cues_withheld_ring"]
    a._on_cue_event(_zrusenie())
    assert a._cues_withheld_ring == 1


@pytest.mark.parametrize("zmena", [
    {"_high_hr_ring_since": None},              # the ring is not on screen
    # all pictures off: `_cue_can_fire` stops there BEFORE it looks at the
    # ring - no cue could come even without it
    {"overlay_configs": _vsetky_obrazky_vypnute()},
    {"overlay_configs": None},
    {"listening": False},
    {"_snooze_job": "uloha"},
])
def test_zrusenie_bez_kruhu_ako_dovodu_sa_nezrata(monkeypatch, zmena):
    a, log = _appka_zrusenia(monkeypatch, **zmena)
    a._on_cue_event(_zrusenie())
    assert a._cues_withheld_ring == 0, zmena
    assert _RIADOK_PODRZAL not in log.riadky
    assert len(a._cue_log) == 1


@pytest.mark.parametrize("dovod", [
    trigger.A_BEZ_PAUZY, trigger.A_NEVHODNA_CHVILA, trigger.A_SNOOZE,
    trigger.A_ODISIEL, trigger.A_TEP_VYPADOL, trigger.A_ZATAZ_KLESLA,
    trigger.A_KONIEC_RELACIE, None,
])
def test_ine_zrusenie_pri_kruhu_sa_nezrata(monkeypatch, dovod):
    a, log = _appka_zrusenia(monkeypatch)
    a._on_cue_event(_zrusenie(dovod))
    assert a._cues_withheld_ring == 0, dovod
    assert _RIADOK_PODRZAL not in log.riadky


def test_kruh_ako_dovod_nikdy_nespadne(monkeypatch):
    a, _log = _appka_zrusenia(monkeypatch)
    del a.__dict__["overlay_configs"]
    assert a._cue_held_by_ring() is False

    def _zlyhaj():
        raise RuntimeError("zlyhanie")
    a, _log = _appka_zrusenia(monkeypatch, _high_hr_ring_on_screen=_zlyhaj)
    assert a._cue_held_by_ring() is False
    a, _log = _appka_zrusenia(monkeypatch)
    assert a._cue_held_by_ring() is True


def test_kruh_ako_dovod_ide_v_poradi_cue_can_fire():
    """`_cue_held_by_ring` follows `_cue_can_fire`: listening, "not now" and
    all pictures off come before the check for a running visual (the order
    itself is guarded in `test_vseobecna_veta_hovori_len_dovody_z_cue_can_fire`)."""
    zdroj = ast.unparse(uzol_metody("_cue_held_by_ring"))
    assert (zdroj.index("'listening'") < zdroj.index("'_snooze_job'")
            < zdroj.index("self._hr_overlay_available()")
            < zdroj.index("'_high_hr_ring_on_screen'"))
    moze = ast.unparse(uzol_metody("_cue_can_fire"))
    assert moze.index("self._hr_overlay_available()") < moze.index(
        "self.overlay_manager.is_active(i)")


def _natiahni(a, hodiny):
    """Arms a cue in the real state machine: load 90 above the threshold
    (55) for the hold, zone high, steady (not rising)."""
    for _ in range(300):
        a.cue_trigger.note_load(90.0, hodiny.t, zona="high")
        if a.cue_trigger.is_armed:
            return
        hodiny.t += 1.0
    raise AssertionError("hlaska sa nenatiahla")


@pytest.fixture
def hra_s_hlaskou(hra, monkeypatch):
    """`hra` + the real cue state machine and `_tick_cue_trigger` on the same
    clock; no pause in the input, so an armed cue waits `max_wait_s` and is
    then delivered silently - or cancelled `nedalo_sa` when it may not."""
    import app_today
    log = _Log()
    monkeypatch.setattr(app_today, "app_log", log)
    monkeypatch.setattr(app_today, "time", hra.hodiny)
    a = hra.a
    a.cue_trigger = trigger.CueTrigger(rng=random.Random(1), clock=hra.hodiny.time)
    a.cue_trigger.open_session(silent_share=0.0)
    a.activity = types.SimpleNamespace(pause_s=lambda now: 0.0)
    a.hud_config = {"enabled": False}
    a._hud_tick_t = None
    a._hud_active_s = 0.0
    a._hud_vis_s = 0.0
    a._cue_log = []
    a._cues_withheld_ring = 0
    a._set_enso_armed = lambda _armed: None

    def tik(sekund):
        """The ring's tick and the cue's tick, 4x per second, in the order
        of `_tick_activity`."""
        koniec = hra.hodiny.t + sekund
        while hra.hodiny.t < koniec - 1e-9:
            hra.fronta.bez(0.25)
            D._tick_high_hr_ring(a, now=hra.hodiny.t)
            D._tick_cue_trigger(a)

    return types.SimpleNamespace(hra=hra, a=a, log=log, tik=tik)


def _suhrn_hry(a, teraz):
    """What `_suhrn_relacie` writes for the cue and the ring."""
    suhrn = dict(ZAKLAD, cues_withheld=dict(a.cue_trigger.zadrzane))
    kruh_s = round(a._high_hr_ring_seconds(teraz), 1)
    if kruh_s > 0.0:
        suhrn["high_hr_ring_s"] = kruh_s
    if a._cues_withheld_ring > 0:
        suhrn["cues_withheld_ring"] = a._cues_withheld_ring
    return suhrn


def test_kruh_v_hre_podrzi_hlasku_a_zrata_sa(hra_s_hlaskou):
    h = hra_s_hlaskou
    _natiahni(h.a, h.hra.hodiny)
    h.tik(1.0)
    assert h.hra.m.high_hr_ring_showing()
    h.tik(trigger.default_params()["max_wait_s"] + 1.0)
    assert h.a.cue_trigger.zadrzane[trigger.A_NEDALO_SA] == 1
    assert h.a._cues_withheld_ring == 1
    assert h.log.riadky.count(_RIADOK_PODRZAL) == 1
    assert _preco(**_suhrn_hry(h.a, h.hra.hodiny.t)) == i18n.tr("session.end.none_ring")


def test_vsetky_obrazky_vypnute_kruh_neobvinia(hra_s_hlaskou):
    """The ring does not look at the in-game pictures, so it breathes even
    with all of them off - but then no cue could come anyway: the cue is
    held back by "all pictures off", and the questionnaire says the general
    sentence that names it, not the ring one."""
    h = hra_s_hlaskou
    h.a.overlay_configs = _vsetky_obrazky_vypnute()
    h.a._hr_overlay_warned = True
    _natiahni(h.a, h.hra.hodiny)
    h.tik(1.0)
    assert h.hra.m.high_hr_ring_showing(), "kruh dycha aj bez obrazkov"
    h.tik(trigger.default_params()["max_wait_s"] + 1.0)
    assert h.hra.m.high_hr_ring_showing()
    assert h.a.cue_trigger.zadrzane[trigger.A_NEDALO_SA] == 1
    assert h.a._cues_withheld_ring == 0
    assert _RIADOK_PODRZAL not in h.log.riadky
    assert _preco(**_suhrn_hry(h.a, h.hra.hodiny.t)) == i18n.tr("session.end.none_blocked")


def test_skorsi_kruh_neobvinia_za_neskorsie_kroky(hra_s_hlaskou):
    """The ring breathed for a while early in the session and is gone; later
    a ready cue is held back by steps from the watch. The session has
    `high_hr_ring_s`, but the ring was not on screen then - the general
    sentence, not the ring one."""
    h = hra_s_hlaskou
    h.tik(20.0)
    assert h.hra.m.high_hr_ring_showing()
    h.a.hr_stats.display_bpm = 100
    h.tik(20.0)
    assert not h.hra.m.is_active(3) and h.a._high_hr_ring_spans, "kruh dodychal"
    h.a.hr_stats.steps_per_min = lambda: 120.0
    _natiahni(h.a, h.hra.hodiny)
    h.tik(trigger.default_params()["max_wait_s"] + 1.0)
    assert h.a.cue_trigger.zadrzane[trigger.A_NEDALO_SA] == 1
    assert h.a._cues_withheld_ring == 0
    suhrn = _suhrn_hry(h.a, h.hra.hodiny.t)
    assert suhrn["high_hr_ring_s"] > 0 and "cues_withheld_ring" not in suhrn
    assert _preco(**suhrn) == i18n.tr("session.end.none_blocked")


def test_bez_kruhu_sa_hlaska_v_hre_dalej_dorucuje(hra_s_hlaskou, monkeypatch):
    """No ring (heart rate below the limit): the armed cue comes after its
    wait as before - nothing held back, nothing counted."""
    h = hra_s_hlaskou
    dorucene = []
    monkeypatch.setattr(D, "_fire_somatic_cue",
                        lambda self, ev: dorucene.append(ev) or True)
    h.a.hr_stats.display_bpm = 95
    _natiahni(h.a, h.hra.hodiny)
    h.tik(trigger.default_params()["max_wait_s"] + 1.0)
    assert len(dorucene) == 1 and not h.hra.m.is_active(3)
    assert sum(h.a.cue_trigger.zadrzane.values()) == 0
    assert h.a._cues_withheld_ring == 0


# --------------------------------------------------------------------------
# the questionnaire: a cue was ready, but could not come (`nedalo_sa`)
# --------------------------------------------------------------------------

def _preco(**summary):
    import ui_dialogs
    return ui_dialogs.SessionEndDialog._preco_ticho(summary)


ZAKLAD = dict(above_runs=4, runs_cancelled_gap=0, runs_cancelled_dip=4,
              longest_above_s=30.0, stress_hold_s=45.0, duration_s=1800.0,
              pause_episodes=12)


def _zadrzane(nedalo_sa=0, brana=0):
    return {trigger.A_BEZ_PAUZY: 0, trigger.A_NEVHODNA_CHVILA: brana,
            trigger.A_NEDALO_SA: nedalo_sa}


@pytest.mark.parametrize("nedalo_sa", [1, 4, 2.0, "3"])
def test_kruh_podrzal_hlasku(nedalo_sa):
    """The ring held back every ready cue that could not come: the line says
    so, not "your load's longest stretch was 30 s, I need 45 s"."""
    veta = _preco(**ZAKLAD, cues_withheld=_zadrzane(nedalo_sa), high_hr_ring_s=340.5,
                  cues_withheld_ring=int(float(nedalo_sa)))
    assert veta == i18n.tr("session.end.none_ring")
    assert veta != i18n.tr("session.end.none_short", najdlhsie=30, treba=45)


@pytest.mark.parametrize("kruh", [None, 0, 0.0, -5.0, "x", float("nan"), [], "chyba"])
def test_bez_kruhu_vseobecna_veta(kruh):
    suhrn = dict(ZAKLAD, cues_withheld=_zadrzane(2), high_hr_ring_s=300.0)
    if kruh != "chyba":
        suhrn["cues_withheld_ring"] = kruh
    assert _preco(**suhrn) == i18n.tr("session.end.none_blocked"), kruh


def test_kruh_v_relacii_bez_podrzanych_hlasok_vseobecna_veta():
    """The ring showed in the session (`high_hr_ring_s`), but it held back
    none of the cues that could not come - steps, all pictures off, another
    picture: the general sentence. Showing some time is not enough."""
    for kruh_s in (20.0, 340.5, 3600.0):
        assert _preco(**ZAKLAD, cues_withheld=_zadrzane(1), high_hr_ring_s=kruh_s) == \
            i18n.tr("session.end.none_blocked"), kruh_s


@pytest.mark.parametrize("kruhom,nedalo_sa", [(1, 3), (2, 3), (1, 2)])
def test_kruh_len_pri_niektorych_hlaskach_vseobecna_veta(kruhom, nedalo_sa):
    """Only some of the held-back cues were the ring's: the general sentence
    (the ring is one of the pictures on screen) is true for all of them, the
    ring one would not be."""
    assert _preco(**ZAKLAD, cues_withheld=_zadrzane(nedalo_sa), high_hr_ring_s=300.0,
                  cues_withheld_ring=kruhom) == i18n.tr("session.end.none_blocked")


@pytest.mark.parametrize("zadrzane", [
    _zadrzane(0), None, "zle", ["a"], {}, {trigger.A_NEDALO_SA: "x"},
    {trigger.A_NEDALO_SA: None},
])
def test_bez_nedalo_sa_sa_veta_nemeni(zadrzane):
    kratko = i18n.tr("session.end.none_short", najdlhsie=30, treba=45)
    for kruh in ({}, {"high_hr_ring_s": 300.0},
                 {"high_hr_ring_s": 300.0, "cues_withheld_ring": 2}):
        assert _preco(**ZAKLAD, cues_withheld=zadrzane, **kruh) == kratko, (zadrzane, kruh)
        assert _preco(**dict(ZAKLAD, above_runs=0), cues_withheld=zadrzane,
                      **kruh) == i18n.tr("session.end.none_never"), (zadrzane, kruh)


def test_poradie_kontrol_ostava():
    """The new line comes after the gate and before the sentences about the
    load - the checks before it keep their order."""
    zadrzane = _zadrzane(3)
    kruh = {"high_hr_ring_s": 300.0, "cues_withheld_ring": 3}
    assert _preco(**ZAKLAD, cues_withheld=_zadrzane(3, brana=1), **kruh) == \
        i18n.tr("session.end.none_withheld")
    assert _preco(**dict(ZAKLAD, runs_cancelled_gap=5, runs_cancelled_dip=1),
                  cues_withheld=zadrzane, **kruh) == i18n.tr("session.end.none_dropouts", n=5)
    assert _preco(**ZAKLAD, cues_withheld=zadrzane, snoozed_s=600.0, **kruh) == \
        i18n.tr("session.end.none_snoozed", min=10)
    assert _preco(**dict(ZAKLAD, pause_episodes=0), cues_withheld=zadrzane, **kruh) == \
        i18n.tr("session.end.none_nopause")
    assert _preco(**ZAKLAD, cues_withheld=zadrzane, cue_rung=rebrik.PAUZA, **kruh) == \
        i18n.tr("session.end.none_paused")
    stara = {k: v for k, v in ZAKLAD.items() if k != "above_runs"}
    assert _preco(**stara, cues_withheld=zadrzane, **kruh) == ""
    zdroj = ast.unparse(next(
        f for f in ast.walk(ast.parse(zdroj_suboru("ui_dialogs.py")))
        if isinstance(f, ast.FunctionDef) and f.name == "_preco_ticho"))
    assert (zdroj.index("tr('session.end.none_withheld')")
            < zdroj.index("trigger.A_NEDALO_SA")
            < zdroj.index("tr('session.end.none_ring')")
            < zdroj.index("tr('session.end.none_blocked')")
            < zdroj.index("tr('session.end.none_never')")
            < zdroj.index("tr('session.end.none_short'"))


def test_vseobecna_veta_hovori_len_dovody_z_cue_can_fire():
    """`nedalo_sa` = the gate let the cue through, but `_cue_can_fire` said
    no. Of its conditions only three can make that happen while a cue is
    armed in a game: a picture on screen, steps from the watch, all
    pictures off - the sentence names exactly these. Listening off closes
    the session and "not now" suspends the state machine, so neither gets
    here; the 5 s gap after a manual Test click is left out (it would take
    a Test click right when a cue's wait runs out). A new condition there
    means a new look at the sentence."""
    uzol = uzol_metody("_cue_can_fire")
    podmienky = [ast.unparse(u.test) for u in ast.walk(uzol) if isinstance(u, ast.If)]
    assert podmienky == [
        "not self.listening",
        "getattr(self, '_snooze_job', None) is not None",
        "not self._hr_overlay_available()",
        "any((self.overlay_manager.is_active(i) for i in range(4)))",
        "kroky is not None and kroky >= self.KROKY_PRAH_ZA_MIN",
        "now - self.last_global_trigger_time < self.cooldown_value",
    ], "nova podmienka v _cue_can_fire - over vetu session.end.none_blocked"
    assert sm.DEFAULT_COOLDOWN <= 5.0
    S = i18n.STRINGS["session.end.none_blocked"]
    for kus in ("na obrazovke už bol obrázok", "hodinky hlásili kroky",
                "všetky obrázky vypnuté"):
        assert kus in S["sk"], kus
    for kus in ("a picture was already on screen", "your watch was reporting steps",
                "all pictures were off"):
        assert kus in S["en"], kus
    for jazyk in i18n.LANGUAGES:
        assert "teraz nie" not in S[jazyk].lower() and "not now" not in S[jazyk].lower()


_KLUCE_KONCA = ("session.end.none_ring", "session.end.none_blocked")


def test_vety_na_konci_relacie_vo_vsetkych_jazykoch():
    S = i18n.STRINGS
    assert S["session.end.none_ring"]["sk"] == (
        "Pripomienka bola pripravená, ale na obrazovke práve dýchal dychový kruh "
        "pri vysokom tepe, tak som ju podržala.")
    assert S["session.end.none_ring"]["en"] == (
        "A cue was ready, but the breath ring for high heart rate was breathing on "
        "screen, so I held it back.")
    assert S["session.end.none_blocked"]["sk"] == (
        "Pripomienka bola pripravená, ale v tej chvíli nemohla prísť — na obrazovke "
        "už bol obrázok, hodinky hlásili kroky alebo boli všetky obrázky vypnuté.")
    assert S["session.end.none_blocked"]["en"] == (
        "A cue was ready, but it could not come at that moment — a picture was already "
        "on screen, your watch was reporting steps, or all pictures were off.")
    # the app speaks about itself in the feminine, Czech is Czech
    assert "som ju podržala" in S["session.end.none_ring"]["sk"]
    assert "jsem ji podržela" in S["session.end.none_ring"]["cs"]
    assert "nemohla přijít" in S["session.end.none_blocked"]["cs"]
    for kluc in _KLUCE_KONCA:
        zaznam = S[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        for jazyk in i18n.LANGUAGES:
            if jazyk != "en":
                assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk, "anglicky")
            assert "{" not in zaznam[jazyk], (kluc, jazyk)
        assert len(set(zaznam.values())) == len(i18n.LANGUAGES), (kluc, "preklady sa opakuju")
        assert zaznam["cs"] != zaznam["sk"], kluc
        assert not kluc.startswith(slova._PREFIXY_V_HRE), kluc
    zle = [(kluc, jazyk, najdene) for kluc in _KLUCE_KONCA for jazyk in i18n.LANGUAGES
           for najdene in [slova._zakazane(S[kluc][jazyk])] if najdene]
    assert not zle, zle
    zdroj = zdroj_suboru("ui_dialogs.py")
    for kluc in _KLUCE_KONCA:
        assert zdroj.count('tr("%s")' % kluc) == 1, kluc


# --------------------------------------------------------------------------
# the hint on the Breath card quotes the real margin
# --------------------------------------------------------------------------

def test_vysvetlivka_uvadza_rezervu_z_konstanty():
    """The number in the hint is the app's constant in every language - a
    placeholder, so changing the margin cannot leave the text behind."""
    import ui_dialogs
    assert ui_dialogs.KRUH_TEP_REZERVA_BPM is app_session.KRUH_TEP_REZERVA_BPM
    zaznam = i18n.STRINGS["overlay.high_hr_ring_hint"]
    for jazyk in i18n.LANGUAGES:
        surovy = zaznam[jazyk]
        assert surovy.count("{margin}") == 1, jazyk
        assert not re.search(r"\d", surovy.replace("{margin}", "")), \
            (jazyk, "ine cislo v texte")
        text = i18n.tr_lang(jazyk, "overlay.high_hr_ring_hint", margin=REZERVA)
        assert re.findall(r"\d+", text) == [str(REZERVA)], (jazyk, text)
        assert "%d BPM" % REZERVA in text, (jazyk, text)
    assert "aspoň o 3 BPM pod ňu" in i18n.tr_lang("sk", "overlay.high_hr_ring_hint",
                                                  margin=REZERVA)
    assert "at least 3 BPM below it" in i18n.tr_lang("en", "overlay.high_hr_ring_hint",
                                                     margin=REZERVA)
