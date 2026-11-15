# -*- coding: utf-8 -*-
"""Activity watching without a keyboard hook.

`ActivityTracker` gets both the clock and the idle source from outside, so
it can be run through entirely without Windows and without waiting in real
time - the test moves time itself.

What matters most is that the pause is counted from the LAST INPUT, not
from the moment the app noticed it. The whole postponing of a cue to a
pause in phase 2 rests on that: if the pause were measured only from the
measurement, the 2.5 s threshold would by chance be hit once after 2.5 s
and another time after 2.75 s.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import activity  # noqa: E402


class Hodiny:
    """Manually advanced time, so that the test does not have to wait."""

    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def sleduj(idle_values, hodiny=None, **kw):
    """A tracker whose idle is dictated by a list - one value per poll()."""
    hodiny = hodiny or Hodiny()
    postupnost = iter(idle_values)
    tracker = activity.ActivityTracker(
        idle_fn=lambda: next(postupnost), clock=hodiny, **kw)
    return tracker, hodiny


def test_modul_sa_da_importovat_aj_ked_win32_nejde():
    """Import must not crash - otherwise the whole app's import would crash."""
    assert isinstance(activity.AVAILABLE, bool)
    assert activity.idle_ms() is None or activity.idle_ms() >= 0


def test_aktivny_a_pauza_sa_prepinaju():
    tracker, hodiny = sleduj([100, 200, 5000, 50])

    tracker.poll()
    assert tracker.is_active is True
    assert tracker.pause_s() == 0.0

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is True

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is False

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is True
    assert tracker.pause_s() == 0.0


def test_pauza_sa_pocita_od_posledneho_vstupu_nie_od_merania():
    """Idle 4000 ms means the pause has lasted 4 s - even if we measure now."""
    tracker, hodiny = sleduj([4000])
    tracker.poll()
    assert tracker.pause_s() == 4.0
    # and it keeps growing with time, without another poll
    hodiny.posun(2.0)
    assert tracker.pause_s() == 6.0


def test_zaznam_je_redsi_nez_pytanie():
    """It asks 4x a second, 1x goes into the record - otherwise in four hours
    it would needlessly grow to tens of thousands of pairs."""
    tracker, hodiny = sleduj([100] * 20)
    for _ in range(20):
        tracker.poll()
        hodiny.posun(activity.POLL_S)
    # 20 polls of 0.25 s = 5 seconds
    assert 5 <= len(tracker.samples) <= 7


def test_druhy_zdroj_sa_beri_ako_minimum():
    """A gamepad (if it proves needed) is another input, not a replacement.

    The resulting idle is "since the last input FROM ANYWHERE", i.e. the
    minimum.
    """
    tracker, _ = sleduj([9000], extra_idle_fn=lambda: 100)
    assert tracker.poll() == 100
    assert tracker.is_active is True


def test_rozbity_druhy_zdroj_neposkodi_meranie():
    def zlyha():
        raise RuntimeError("ovladac sa odpojil")

    tracker, _ = sleduj([300], extra_idle_fn=zlyha)
    assert tracker.poll() == 300


def test_chybajuci_zdroj_idle_nespadne():
    """On a system without GetLastInputInfo nothing is known - no crash."""
    tracker = activity.ActivityTracker(idle_fn=lambda: None, clock=Hodiny())
    assert tracker.poll() is None
    assert tracker.is_active is False


def test_neznama_pauza_nie_je_nulova_pauza():
    """None means "I don't know", not "no pause" - and that is a difference.

    Phase 2 postpones a cue to a pause. If "I don't know" pretended to be
    zero, on a machine without idle a pause would never occur, all cues
    would fall into the "pause did not come" branch and the silent control
    arm would get mixed up with them. The measurement would come out
    without a single loud cue.
    """
    slepy = activity.ActivityTracker(idle_fn=lambda: None, clock=Hodiny())
    slepy.poll()
    assert slepy.pause_s() is None

    hodiny = Hodiny()
    vidiaci = activity.ActivityTracker(idle_fn=lambda: 100, clock=hodiny)
    vidiaci.poll()
    assert vidiaci.pause_s() == 0.0      # knows there is no pause


def test_zapnutie_senzora_vynuluje_zaznam():
    tracker, hodiny = sleduj([100] * 10)
    for _ in range(10):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.samples
    tracker.reset_session()
    assert tracker.samples == []
    assert tracker.pause_since is None


def test_podiel_aktivity_nad_vlastnym_zaznamom():
    hodiny = Hodiny()
    idle = [100, 100, 9000, 9000]
    postupnost = iter(idle)
    tracker = activity.ActivityTracker(idle_fn=lambda: next(postupnost),
                                       clock=hodiny)
    start = hodiny.t
    for _ in range(4):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.active_share(start, hodiny.t) == 0.5
    assert tracker.active_share(start - 100.0, start - 50.0) is None


def test_zaznam_ma_strop():
    """An app left running over the weekend must not eat memory forever."""
    povodny = activity.MAX_SAMPLES
    activity.MAX_SAMPLES = 10
    try:
        hodiny = Hodiny()
        tracker = activity.ActivityTracker(idle_fn=lambda: 100, clock=hodiny)
        for _ in range(40):
            tracker.poll()
            hodiny.posun(1.0)
        assert len(tracker.samples) == 10
        # the NEWEST ones stay
        assert tracker.samples[-1][0] == hodiny.t - 1.0
    finally:
        activity.MAX_SAMPLES = povodny


# --------------------------------------------------------------------------
# What the player is playing with right now (controller vs keyboard)
# --------------------------------------------------------------------------

def test_bez_gamepad_listenera_zdroj_nevieme():
    """WE DON'T KNOW is not the same as "keyboard".

    If the controller's silence were reported as keyboard, on a machine with
    the listener turned off the app would tell a player with a controller an
    untruth - and it would be on the screen, so they would believe it.
    """
    tracker, hodiny = sleduj([50] * 5)
    for _ in range(5):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.source(now=hodiny.t) is None


def test_cerstvy_vstup_z_ovladaca_sa_rozozna():
    tracker, hodiny = sleduj([50] * 5)
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD


def test_ked_ovladac_mlci_je_to_klavesnica():
    """`GetLastInputInfo` has input, the controller none - so something else."""
    tracker, hodiny = sleduj([50] * 5)
    tracker.set_gamepad_watched(True)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_KB


def test_prechod_z_ovladaca_na_klavesnicu():
    """The player puts the controller down and starts typing in chat."""
    tracker, hodiny = sleduj([50] * 6)
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    hodiny.posun(5.0)                       # the controller reports nothing any more
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_KB


def test_zdroj_prezije_kratku_prestavku():
    """Without memory the pictogram would go out at every break and light up
    at every press - exactly the wandering motion that distracts."""
    tracker, hodiny = sleduj([50, 50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    hodiny.posun(activity.SOURCE_MEMORY_S - 1.0)
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    hodiny.posun(2.0)
    assert tracker.source(now=hodiny.t) is None, "po dlhej pauze sa už netvrdí nič"


def test_vypnutie_listenera_zdroj_zabudne():
    tracker, hodiny = sleduj([50, 50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    tracker.set_gamepad_watched(False)
    assert tracker.source(now=hodiny.t) is None


def test_zdroj_nikdy_nedrzi_co_sa_stlacilo():
    """SAFETY.md: the app never learns which button it was. Only the class of
    the device is detected, nothing more."""
    tracker, hodiny = sleduj([50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) in (activity.SRC_PAD, activity.SRC_KB)
    ulozene = [v for v in vars(tracker).values() if isinstance(v, str)]
    assert all(v in (activity.SRC_PAD, activity.SRC_KB) for v in ulozene), ulozene
