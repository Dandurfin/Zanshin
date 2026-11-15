# -*- coding: utf-8 -*-
"""A tolerated dip is not time above the threshold (0.2.1).

The continuous arming path was counted as `now - _above_since`, i.e. by
wall-clock time INCLUDING dips shorter than `dip_grace_s` (20 s). The
pattern "1 s above the threshold, 19 s below it" therefore armed a cue after
a minute, although only four samples were above the threshold. Yet the
README promises a cue when the load above the limit "spends enough time",
and SOUL would rather stay silent than speak up for nothing.

The fix subtracts the time spent in tolerated dips from the stretch. The
tolerance still keeps the stretch alive (it does not break into new runs)
and a short SILENCE after a sample above the threshold (less than
`DIERA_S`) keeps counting on the continuous path - that is deliberate and
documented (POCTIVO in `note_load`).
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402

PRAH = 55.0
NAD = 80.0
POD = 40.0


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def spusti(t0=1000.0, **params):
    h = Hodiny(t0)
    t = trigger.CueTrigger(params=params, rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0)
    return t, h


def odohraj(t, h, vzor, limit_s):
    """Plays the pattern [(seconds, stress), ...] in a loop at 1 s. Returns
    (arming offset from start or None, number of samples above threshold)."""
    start = h.t
    nad = 0
    while h.t - start <= limit_s:
        for sekund, stress in vzor:
            for _ in range(sekund):
                if h.t - start > limit_s:
                    return None, nad
                if stress >= PRAH:
                    nad += 1
                if t.note_load(stress, h.t, zona="high"):
                    return h.t - start, nad
                h.posun(1.0)
    return None, nad


# --------------------------------------------------------------------------
# Exact patterns from the spec
# --------------------------------------------------------------------------

def test_kmitanie_1_nad_19_pod_nenatiahne():
    """Bug from the review: 1 s above / 19 s below armed after 60 s with four
    samples above the threshold. In five minutes 15 s are above the
    threshold - for 45 s of holding that is not even a third."""
    t, h = spusti()                              # default: 45 s, tolerance 20 s
    kedy, nad = odohraj(t, h, [(1, NAD), (19, POD)], limit_s=300.0)
    assert kedy is None, f"natiahlo sa po {kedy} s s {nad} s nad prahom"
    assert not t.is_armed
    # The tolerance keeps the stretch alive (no dip is longer than 20 s)...
    assert t.behov_nad == 1
    assert t.zrusenych_prepadom == 0
    # ... but the stretch length is about time ABOVE the threshold, not
    # wall-clock time.
    assert t.najdlhsi_nad_s <= 16.0, t.najdlhsi_nad_s


def test_suvisle_45_s_nad_prahom_stale_natiahne():
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(1, NAD)], limit_s=120.0)
    assert kedy == pytest.approx(45.0)
    assert t.is_armed
    assert t.najdlhsi_nad_s >= 45.0


def test_prepad_10_s_natiahne_az_po_45_s_nad_prahom():
    """30 s above, 10 s below (within tolerance), then above again. Before,
    it armed at second 45 of wall-clock time (35 s above the threshold),
    now only when it has really been above the threshold for 45 s:
    30 + 15 = at second 55."""
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(30, NAD), (10, POD), (1000, NAD)], limit_s=200.0)
    assert kedy == pytest.approx(55.0), kedy
    assert nad >= 45
    assert t.behov_nad == 1, "tolerovaný prepad nie je nový beh"
    assert t.zrusenych_prepadom == 0


def test_dlhy_usek_s_prepadmi_natiahne_suvislou_cestou_az_po_45_s_nad():
    """10 s above / 15 s below: in 90 s the cumulative window never gives
    45 s, so only the continuous path can arm - and only after 45 s ABOVE
    the threshold (4 rounds of 10 s + 5 s of the fifth). Before, it armed
    at second 50 with 21 samples above the threshold."""
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(10, NAD), (15, POD)], limit_s=400.0)
    assert kedy == pytest.approx(105.0), kedy
    assert nad == 46                             # 45 s above the threshold + the current sample
    assert t.behov_nad == 1


# --------------------------------------------------------------------------
# What must NOT change
# --------------------------------------------------------------------------

def test_kratke_ticho_nad_prahom_sa_na_suvislej_ceste_stale_pocita():
    """POCTIVO in `note_load`: a gap shorter than `DIERA_S` after a sample
    above the threshold is counted on the continuous path (the app also
    treats it as "connected" elsewhere). With a sample every 11 s the
    window gives only 5 s per sample, so the continuous path has to arm -
    at second 55, as before."""
    assert 11.0 < trigger.DIERA_S
    t, h = spusti()
    start = h.t
    kedy = None
    for _ in range(20):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t - start
            break
        h.posun(11.0)
    assert kedy == pytest.approx(55.0), kedy
    assert t.zrusenych_vypadkom == 0


def test_dlhy_prepad_usek_stale_zrusi():
    """The `dip_grace_s` semantics for cancelling a stretch stay."""
    t, h = spusti(dip_grace_s=20.0)
    odohraj(t, h, [(30, NAD), (25, POD)], limit_s=54.0)
    assert t.zrusenych_prepadom == 1
    assert t.state == trigger.IDLE
    assert 29.0 <= t.najdlhsi_nad_s <= 30.0, t.najdlhsi_nad_s


# --------------------------------------------------------------------------
# The new state is reset everywhere a stretch ends
# --------------------------------------------------------------------------

def _usek_s_prepadom(t, h):
    """20 s above, a 10 s tolerated dip, 5 s above: `_prepady_s` is 10."""
    for sekund, stress in ((20, NAD), (10, POD), (5, NAD)):
        for _ in range(sekund):
            assert t.note_load(stress, h.t, zona="high") is None
            h.posun(1.0)
    assert t._prepady_s == pytest.approx(10.0)


def test_prepady_sa_nulujú_pri_uspani():
    for dovod in (trigger.A_SNOOZE, trigger.A_TEP_VYPADOL):
        t, h = spusti()
        _usek_s_prepadom(t, h)
        t.suspend(dovod, now=h.t)
        assert t._prepady_s == 0.0, dovod
        # stretch length without the dip: 20 + 5 s above the threshold (+
        # holding the last one)
        assert 24.0 <= t.najdlhsi_nad_s <= 26.0, t.najdlhsi_nad_s


def test_prepady_sa_nulujú_pri_kalibracii():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    t.note_load(NAD, h.t, calibrating=True, zona="high")
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_vypadku():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    h.posun(trigger.DIERA_S)
    t.note_load(NAD, h.t, zona="high")
    assert t.zrusenych_vypadkom == 1
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_dlhom_prepade():
    t, h = spusti(dip_grace_s=20.0)
    _usek_s_prepadom(t, h)
    for _ in range(25):
        t.note_load(POD, h.t, zona="high")
        h.posun(1.0)
    assert t.zrusenych_prepadom == 1
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_natiahnuti_a_plnej_hodine():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    ev = None
    while not ev:
        ev = t.note_load(NAD, h.t, zona="high")
        h.posun(1.0)
    assert t._prepady_s == 0.0

    # Full hour / cues off: the stretch is counted again from `now`.
    t, h = spusti(cues_enabled=False)
    _usek_s_prepadom(t, h)
    for _ in range(40):
        t.note_load(NAD, h.t, zona="high")
        if t._above_since == h.t:
            break
        h.posun(1.0)
    assert t._above_since == h.t, "vetva plnej hodiny sa nespustila"
    assert t._prepady_s == 0.0


def test_novy_usek_nededi_prepady_stareho():
    """If `_prepady_s` were not reset, the next stretch would arm later than
    it should (extra silence). With a sample every 11 s the continuous
    path decides: with the inherited 15 s it would arm only at second 66."""
    t, h = spusti(dip_grace_s=20.0)
    for sekund, stress in ((20, NAD), (15, POD), (5, NAD)):
        for _ in range(sekund):
            t.note_load(stress, h.t, zona="high")
            h.posun(1.0)
    assert t._prepady_s == pytest.approx(15.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    h.posun(100.0)                               # the old window expires
    t.resume(now=h.t)
    start = h.t
    kedy = None
    for _ in range(20):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t - start
            break
        h.posun(11.0)
    assert kedy == pytest.approx(55.0), kedy


# --------------------------------------------------------------------------
# Time 0.0 is a valid time
# --------------------------------------------------------------------------

def test_vzorka_v_case_nula_sa_na_suvislej_ceste_pocita():
    """`if self._posledny_nad_koniec` took time 0.0 as "missing". A sample
    above the threshold every 11 s, the last one exactly at time 0.0: the
    continuous path has 55 s (the window only 5 x 5 s), so it arms right
    at time 0.0 - not one sample later."""
    t, h = spusti(t0=-55.0)
    kedy = None
    for _ in range(10):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t
            break
        h.posun(11.0)
    assert kedy == 0.0, kedy
    assert t.najdlhsi_nad_s == pytest.approx(55.0)


# --------------------------------------------------------------------------
# Post-session sentence: "longest X s, I need Y s" must not claim X >= Y
# about a stretch that did not arm
# --------------------------------------------------------------------------

def test_vypadok_cez_appku_nepripise_ticho_do_dlzky_useku():
    """The app calls `suspend(A_TEP_VYPADOL)` only after `STALE_AFTER_S`
    without data, i.e. 12 s after the last sample. Nobody measured those
    seconds: 35 samples above the threshold must not come out in the
    summary as 46 s when 45 s are needed."""
    t, h = spusti()
    for _ in range(35):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(1.0)
    posledna = h.t - 1.0
    t.suspend(trigger.A_TEP_VYPADOL, now=posledna + trigger.DIERA_S)
    assert t.armed_count == 0
    assert t.zrusenych_vypadkom == 1
    assert t.najdlhsi_nad_s == pytest.approx(34.0)


def test_dlhy_prepad_tesne_pod_drzanim_netvrdi_drzanie():
    """45 samples at 1 s: the arming condition saw at most 44 s, so it did
    not arm. The summary must not claim 45 s ("longest 45 s, need 45 s")."""
    t, h = spusti()
    for _ in range(45):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(1.0)
    for _ in range(25):
        assert t.note_load(POD, h.t, zona="high") is None
        h.posun(1.0)
    assert t.zrusenych_prepadom == 1
    assert t.armed_count == 0
    assert t.najdlhsi_nad_s == pytest.approx(44.0)


def test_ridka_kadencia_a_prepad_netvrdia_drzanie():
    """Cadence ~2,9 s: 16 samples above the threshold are 43,5 s, no arming.
    The gap to the first sample below the threshold (2,9 s) must not be
    added to the stretch - otherwise the summary would claim 46 s."""
    t, h = spusti()
    for _ in range(16):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(2.9)
    for _ in range(12):
        assert t.note_load(POD, h.t, zona="high") is None
        h.posun(2.9)
    assert t.zrusenych_prepadom == 1
    assert t.armed_count == 0
    assert t.najdlhsi_nad_s == pytest.approx(43.5)


def test_bez_natiahnutia_najdlhsie_nikdy_nedosiahne_drzanie():
    """General safeguard: while nothing has armed, `najdlhsi_nad_s` is always
    below `stress_hold_s`. Stretches of 30-50 s with random cadence (also
    sparser, below `DIERA_S`) and short dips, ended by a long dip, a gap in
    the data or a dropout via the app (`suspend` 12 s after the last
    sample)."""
    drzanie = trigger.default_params()["stress_hold_s"]
    tesne = 0
    for seed in range(300):
        rng = random.Random(seed)
        t, h = spusti()
        for _ in range(6):
            koniec = h.t + rng.uniform(30.0, 50.0)
            posledna = h.t
            while h.t < koniec and not t.armed_count:
                stress = POD if rng.random() < 0.1 else NAD
                t.note_load(stress, h.t, zona="high")
                posledna = h.t
                h.posun(rng.choice((0.9, 1.0, 2.9, 5.6, 11.0)))
            if t.armed_count:
                break
            sposob = rng.randrange(3)
            if sposob == 0:                          # long dip
                for _ in range(25):
                    t.note_load(POD, h.t, zona="high")
                    h.posun(1.0)
            elif sposob == 1:                        # gap in the data
                h.posun(trigger.DIERA_S)
                t.note_load(POD, h.t, zona="high")
            else:                                    # dropout via the app
                t.suspend(trigger.A_TEP_VYPADOL,
                          now=posledna + trigger.DIERA_S)
                h.t = posledna + trigger.DIERA_S + 5.0
                t.resume(now=h.t)
            assert t.armed_count == 0
            assert t.najdlhsi_nad_s < drzanie, (seed, sposob, t.najdlhsi_nad_s)
            if t.najdlhsi_nad_s >= drzanie - 10.0:
                tesne += 1
    assert tesne >= 50, "test nič neoveril - skoro žiadny úsek nebol tesne"


# --------------------------------------------------------------------------
# General safeguard: armed = really 45 s above the threshold
# --------------------------------------------------------------------------

def test_natiahnutie_nikdy_bez_45_s_nad_prahom():
    """Random alternation above/below (1-30 s), a sample every second.
    Whichever path arms, there must be at least 45 samples above the
    threshold - otherwise the cue armed on time that was not above the
    threshold."""
    natiahnutych = 0
    for seed in range(300):
        rng = random.Random(seed)
        vzor = []
        for _ in range(40):
            vzor.append((rng.randint(1, 30), NAD))
            vzor.append((rng.randint(1, 30), POD))
        t, h = spusti()
        kedy, nad = odohraj(t, h, vzor, limit_s=1500.0)
        if kedy is not None:
            natiahnutych += 1
            assert nad >= t.params["stress_hold_s"], (seed, kedy, nad)
    assert natiahnutych >= 50, "test nič neoveril - skoro nič sa nenatiahlo"
