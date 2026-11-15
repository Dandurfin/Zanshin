# -*- coding: utf-8 -*-
"""A sparser watch cadence is not a dropout (C1).

Since 20. 9. the watch sends the heart rate every ~2.9 s (in OBS it
alternates with steps), and one lost packet is a gap of ~5.6 s. Until then
the trigger took every gap over 5 s (`MAX_KROK_S`) as a dropout and wiped
all the accumulated time: 194 of 199 runs above the threshold cancelled by
a "dropout", one cue in over 4 hours.

The fix separates two questions: how much time one gap ADDS (at most
`MAX_KROK_S`) and from what gap size it is a DROPOUT (`DIERA_S` = the
disconnect threshold).
"""
import os
import random
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import heart_rate  # noqa: E402
import hr_stats  # noqa: E402
import trigger  # noqa: E402


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def spusti(**params):
    h = Hodiny()
    t = trigger.CueTrigger(params=params, rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0)
    return t, h


def ridke_kroky(n, krok=2.8, kazdy=5):
    """Cadence ~2.8 s; every `kazdy`-th gap is a lost packet (2x the step,
    i.e. ~5.6 s - just above the old 5 s threshold)."""
    for i in range(n):
        yield krok * 2 if i % kazdy == kazdy - 1 else krok


# --------------------------------------------------------------------------
# A sparser cadence arms
# --------------------------------------------------------------------------

def test_ridka_kadencia_pod_zatazou_sa_natiahne():
    """Exactly the pattern from the evenings since 20. 9.: the load stays up,
    the watch sends every ~2.8 s and every fifth packet is lost. Before: it
    never armed."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    start = h.t
    ev = None
    for krok in ridke_kroky(60):
        ev = t.note_load(80.0, h.t)
        if ev:
            break
        h.posun(krok)
    assert ev and ev["typ"] == trigger.E_ARMED, "ridka kadencia sa nenatiahla"
    assert t.zrusenych_vypadkom == 0, "strateny paket nie je vypadok"
    assert t.behov_nad == 1, "jeden usek nad prahom, nie desiatky kratkych"
    assert h.t - start <= 45.0 + 2 * 2.8, h.t - start


def test_ridka_kadencia_kumulativne_okno_prezije():
    """A round-based pattern (up, a long drop, up again) with a sparse cadence.

    Here the drop cancels the continuous run, so the CUMULATIVE window has
    to arm - and before, every lost packet wiped it, so it never filled up."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0, dip_grace_s=20.0)
    kroky = ridke_kroky(10_000)
    ev = None
    for _ in range(3):                         # three rounds
        koniec = h.t + 35.0                    # 35 s in combat
        while h.t < koniec and not ev:
            ev = t.note_load(80.0, h.t)
            h.posun(next(kroky))
        if ev:
            break
        koniec = h.t + 30.0                    # 30 s respawn, longer than the tolerance
        while h.t < koniec:
            t.note_load(20.0, h.t)
            h.posun(next(kroky))
    assert ev and ev["typ"] == trigger.E_ARMED
    assert t.zrusenych_prepadom >= 1, "prvy usek mal zrusit prepad"
    assert t.zrusenych_vypadkom == 0


# --------------------------------------------------------------------------
# The credit cap stays 5 s
# --------------------------------------------------------------------------

def test_medzera_nepripise_viac_nez_max_krok():
    """Time nobody measured is not added to the window - even when the gap is
    no longer a dropout."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    assert t.note_load(80.0, h.t) is None
    for _ in range(3):
        h.posun(10.0)                          # 10 s: over 5 s, under DIERA_S
        assert t.note_load(80.0, h.t) is None
    nazbierane = sum(d for _, d in t._nad_okno)
    assert nazbierane == pytest.approx(3 * trigger.MAX_KROK_S)
    assert t.zrusenych_vypadkom == 0
    assert t.behov_nad == 1


def test_medzera_tesne_pod_dierou_okno_nezmaze():
    """Boundary: 11.5 s of silence is not a dropout yet."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    for _ in range(20):                        # 19 s added (the first step is 0)
        assert t.note_load(80.0, h.t) is None
        h.posun(1.0)
    h.posun(trigger.DIERA_S - 0.5 - 1.0)       # gap since the last sample 11.5 s
    assert t.note_load(80.0, h.t) is None
    assert sum(d for _, d in t._nad_okno) == pytest.approx(19.0 + trigger.MAX_KROK_S)
    assert t.zrusenych_vypadkom == 0
    assert t.behov_nad == 1


# --------------------------------------------------------------------------
# A real dropout still wipes (B4 without suspend)
# --------------------------------------------------------------------------

def test_skutocny_vypadok_okno_stale_zahodi():
    """A gap of `DIERA_S` or more is a dropout - even if the app has not yet
    declared it via `suspend`. The old accumulated time must not survive."""
    t, h = spusti(stress_threshold=50.0, stress_hold_s=30.0)
    for _ in range(29):                        # 28 s in the window, just under 30
        assert t.note_load(80.0, h.t) is None
        h.posun(1.0)
    h.posun(trigger.DIERA_S - 1.0)             # gap since the last sample = DIERA_S
    ev = t.note_load(80.0, h.t)
    assert ev is None, "natiahlo sa z casu spred vypadku"
    assert t.zrusenych_vypadkom == 1
    assert sum(d for _, d in t._nad_okno) <= trigger.MAX_KROK_S
    # and it can arm, but from scratch - not a few seconds sooner thanks to the
    # old time
    po_vypadku = h.t
    ev = None
    while not ev:
        h.posun(1.0)
        ev = t.note_load(80.0, h.t)
    assert h.t - po_vypadku >= 30.0 - trigger.MAX_KROK_S


def test_diera_sedi_s_hranicou_odpojenia():
    """The trigger and the watchdog must have the same dropout threshold. The
    app does not treat a shorter gap as a dropout (the HUD does not report
    "Disconnected") - nor does the trigger."""
    assert trigger.DIERA_S == heart_rate.HeartRateMonitor.STALE_AFTER_S
    assert trigger.DIERA_S > trigger.MAX_KROK_S


# --------------------------------------------------------------------------
# The gap and the cap apply with a sparse cadence too
# --------------------------------------------------------------------------

def test_ridka_kadencia_drzi_strop_a_odstup():
    """The fix must not make the app chatty: two hours of continuous load with
    a sparse cadence (~15 % of gaps 5.1–6.8 s), a pause in activity always
    at hand."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    rng = random.Random(7)
    dorucene = []
    koniec = h.t + 2 * trigger.HOUR_S
    while h.t < koniec:
        t.note_load(80.0, h.t, zona="high")    # zone known, not critical
        ev = t.tick(3.0, h.t)                  # pause >= 2.5 s, delivered right away
        if ev and ev["typ"] == trigger.E_DELIVER:
            dorucene.append(ev["ts"])
        h.posun(2.8 if rng.random() > 0.15 else rng.uniform(5.1, 6.8))
    prva_hodina = [x for x in dorucene if x < dorucene[0] + trigger.HOUR_S]
    assert 1 <= len(prva_hodina) <= 5, dorucene
    for a, b in zip(dorucene, dorucene[1:]):
        assert b - a >= 240.0, (a, b)
    for t0 in dorucene:
        v_hodine = [x for x in dorucene if t0 <= x < t0 + trigger.HOUR_S]
        assert len(v_hodine) <= 5, v_hodine
    assert t.zrusenych_vypadkom == 0


# --------------------------------------------------------------------------
# Snooze is not a dropout
# --------------------------------------------------------------------------

def test_snooze_sa_nerata_ako_vypadok():
    """"Not now" is the player's decision. If it counted as a dropout, after
    the evening the app would advise them to put the watch closer to the
    computer."""
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    for _ in range(20):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_SNOOZE, now=h.t)
    assert t.zrusenych_vypadkom == 0
    assert t.najdlhsi_nad_s >= 19.0, "usek sa aj tak zapise"
    assert t._nad_okno == [], "nazbierany cas ide prec aj pri snooze (B4)"

    # a heart-rate dropout MUST be counted
    t.resume(now=h.t, force=True)
    for _ in range(20):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    assert t.zrusenych_vypadkom == 1


# --------------------------------------------------------------------------
# Tag and collect: cadence and threshold in the session summary
# --------------------------------------------------------------------------

def _ridke_vzorky(n, ts=1_700_000_000.0):
    out = []
    for krok in ridke_kroky(n):
        out.append((ts, 70.0))
        ts += krok
    return out


def test_kadencia_vzoriek_su_tri_agregaty():
    vzorky = _ridke_vzorky(100)                # 99 gaps: 80x 2.8 s, 19x 5.6 s
    k = hr_stats.kadencia_vzoriek(vzorky)
    assert set(k) == {"sample_dt_median_s", "sample_dt_p90_s",
                      "sample_gaps_over_5s"}
    assert k["sample_dt_median_s"] == pytest.approx(2.8)
    assert k["sample_dt_p90_s"] == pytest.approx(5.6)
    assert k["sample_gaps_over_5s"] == 19


def test_kadencia_bez_dat_nic_netvrdi():
    for vzorky in ([], [(1000.0, 70.0)]):
        k = hr_stats.kadencia_vzoriek(vzorky)
        assert k["sample_dt_median_s"] is None
        assert k["sample_dt_p90_s"] is None
        assert k["sample_gaps_over_5s"] == 0


def test_suhrn_relacie_ma_kadenciu():
    st = hr_stats.HeartStats(critical_bpm=110)
    for ts, bpm in _ridke_vzorky(50):          # 49 gaps, 9 of them 5.6 s
        st.add(bpm, ts=ts)
    s = st.summary()
    assert s["sample_dt_median_s"] == pytest.approx(2.8)
    assert s["sample_dt_p90_s"] == pytest.approx(5.6)
    assert s["sample_gaps_over_5s"] == 9
    # aggregates, not a curve of gaps
    for kluc in ("sample_dt_median_s", "sample_dt_p90_s", "sample_gaps_over_5s"):
        assert not isinstance(s[kluc], (list, tuple, dict)), kluc


def _zavri_relaciu(monkeypatch, tmp_path, prah, dlhodoba):
    """Runs the real `DandurfApp._close_hr_session` on a minimal dummy and
    returns the summary that would be saved."""
    import app as app_mod
    ulozene = []

    def uloz(path, summary, log=None):
        ulozene.append(summary)
        return False                           # nothing else (dialog, history)

    monkeypatch.setattr(app_mod.hr_stats, "save_session", uloz)
    ct = trigger.CueTrigger(params={"stress_threshold": prah},
                            rng=random.Random(1))
    ct.open_session(silent_share=0.0)
    st = hr_stats.HeartStats(critical_bpm=110)
    st.long_baseline = dlhodoba
    nic = lambda *a, **k: None                 # noqa: E731
    atrapa = types.SimpleNamespace(
        _hr_session_open=True, cue_trigger=ct, hr_stats=st, _cue_log=[],
        _set_enso_armed=nic, _save_measure_windows=nic,
        hr_events_path=str(tmp_path / "udalosti.jsonl"),
        _hud_tick_t=None, _hud_vis_s=0.0, _hud_active_s=0.0,
        _hud_is_visible=lambda: False,
        hr_sessions_path=str(tmp_path / "relacie.json"),
        log_threadsafe=nic)
    # The summary is built by the real `_suhrn_relacie` (0.3, `_close_hr_session`
    # calls it).
    atrapa._suhrn_relacie = types.MethodType(app_mod.DandurfApp._suhrn_relacie, atrapa)
    app_mod.DandurfApp._close_hr_session(atrapa)
    assert len(ulozene) == 1
    return ulozene[0]


def test_suhrn_relacie_nesie_prah_a_dlhodobu_zakladnu(monkeypatch, tmp_path):
    """Without the threshold, after 3–5 evenings you cannot tell what number an
    evening ran on, nor separate the evenings before and after the trigger
    fix."""
    s = _zavri_relaciu(monkeypatch, tmp_path, prah=72.0, dlhodoba=61.0)
    assert s["stress_threshold"] == 72.0
    assert s["long_baseline_bpm"] == 61.0
    # next to the trigger's other counters
    for kluc in ("above_runs", "runs_cancelled_gap", "stress_hold_s"):
        assert kluc in s, kluc


def test_suhrn_bez_dlhodobej_zakladne_je_none(monkeypatch, tmp_path):
    s = _zavri_relaciu(monkeypatch, tmp_path, prah=55.0, dlhodoba=None)
    assert s["stress_threshold"] == 55.0
    assert s["long_baseline_bpm"] is None
