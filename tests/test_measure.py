# -*- coding: utf-8 -*-
"""Measurement windows - what makes a window valid and what invalidates it.

The pure `measure` module is tested over made-up data, so it runs without
Tk, without a watch and without waiting in real time.

Why so many tests for "invalid" cases: a window that looks valid and is not
is worse than none - a silent bias does not show up in the chart as an
error, only as a different result.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import measure  # noqa: E402

T0 = 10_000.0          # an arbitrary "absolute" time, so the numbers are readable
CUE = T0 + 300.0       # a cue 5 minutes after the session start


def rad(start, end, bpm=80.0, krok=1.0, vynechaj=None):
    """Samples once per second from `start` to `end`.

    `vynechaj` is (from, to) - a gap that simulates a sensor dropout.
    `bpm` can be a number or a function of time.
    """
    out = []
    t = start
    while t <= end:
        if vynechaj and vynechaj[0] <= t <= vynechaj[1]:
            t += krok
            continue
        out.append((t, bpm(t) if callable(bpm) else bpm))
        t += krok
    return out


def okno(samples, cues=None, **kw):
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "voice",
           "source": "auto"}
    return measure.build_window(cue, samples, cues or [CUE], **kw)


# --------------------------------------------------------------------------
# Pure calculations
# --------------------------------------------------------------------------

def test_priemer_berie_len_vzorky_v_intervale():
    samples = [(100.0, 60.0), (150.0, 80.0), (200.0, 100.0)]
    assert measure.mean_in(samples, 140.0, 210.0) == 90.0
    assert measure.mean_in(samples, 300.0, 400.0) is None


def test_diery_sa_rozlisuju_podla_toho_kde_su():
    """Start, inside and end must be three different numbers.

    If they were added up, a shortened window would be reported as a
    sensor dropout.
    """
    samples = rad(110.0, 190.0)
    zaciatok, vnutro, koniec = measure.gaps(samples, 100.0, 200.0)
    assert zaciatok == 10.0
    assert vnutro == 1.0
    assert koniec == 10.0

    # A continuous series: at most one sampling period remains at the edges
    # (the interval is half-open, so a sample exactly at the end no longer
    # belongs inside).
    diera = rad(100.0, 200.0, vynechaj=(140.0, 160.0))
    zaciatok, vnutro, koniec = measure.gaps(diera, 100.0, 200.0)
    assert zaciatok == 0.0
    assert vnutro > 20.0
    assert koniec <= 1.0


def test_prazdny_interval_je_cely_diera():
    assert measure.gaps([], 100.0, 200.0) == (100.0, 0.0, 0.0)


def test_refrakterna_zona_preskakuje_seba_sameho():
    """The caller sends the times of ALL cues including this one."""
    assert measure.refractory_conflict(CUE, [CUE]) is False
    assert measure.refractory_conflict(CUE, [CUE, CUE + 30.0]) is True
    assert measure.refractory_conflict(CUE, [CUE, CUE - 30.0]) is True
    # just past the zone: -60 and +180 are the limits, anything beyond them no
    # longer matters
    assert measure.refractory_conflict(CUE, [CUE, CUE + 181.0]) is False
    assert measure.refractory_conflict(CUE, [CUE, CUE - 61.0]) is False


def test_podiel_aktivity():
    aktivita = [(CUE - 10.0, 100), (CUE - 5.0, 5000), (CUE - 1.0, 200)]
    assert measure.active_share(aktivita, CUE - 12.0, CUE) == 2 / 3
    assert measure.active_share([], CUE - 12.0, CUE) is None


def test_kategoria_podla_slotu():
    assert measure.category_for_slot(0) == "grounding"
    assert measure.category_for_slot(3) == "breath"
    assert measure.category_for_slot(4) is None
    assert measure.category_for_slot(None) is None


# --------------------------------------------------------------------------
# Building a window
# --------------------------------------------------------------------------

def test_cele_okno_je_platne():
    samples = rad(CUE - 120.0, CUE + 240.0)
    w = okno(samples)
    assert w["valid"] is True
    assert w["reasons"] == []
    assert w["pre_bpm"] == 80.0
    assert w["post_bpm"] == 80.0
    assert w["arm"] == "voice"
    assert w["category"] == "breath"


def test_mrtvy_cas_sa_do_po_okna_nepocita():
    """The first 10 s after the cue must drop out of the mean - otherwise the
    state from the moment of the cue would still leak into it."""
    def bpm(t):
        return 200.0 if CUE <= t < CUE + measure.DEAD_S else 80.0

    w = okno(rad(CUE - 120.0, CUE + 240.0, bpm=bpm))
    assert w["post_bpm"] == 80.0


def test_druha_hlaska_v_zone_zneplatni_obe():
    samples = rad(CUE - 120.0, CUE + 400.0)
    cues = [
        {"ts": CUE, "category": "breath", "arm": "voice"},
        {"ts": CUE + 30.0, "category": "jaw", "arm": "voice"},
    ]
    okna = measure.build_windows(cues, samples)
    assert len(okna) == 2
    for w in okna:
        assert w["valid"] is False
        assert measure.R_REFRACTORY in w["reasons"]


def test_vypadok_senzora_zneplatni_okno_ako_diera():
    samples = rad(CUE - 120.0, CUE + 240.0, vynechaj=(CUE + 20.0, CUE + 50.0))
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_GAP in w["reasons"]
    # NOT as a shortened window - the session went on, only the sensor dropped
    # out
    assert measure.R_POST_SHORT not in w["reasons"]


def test_hlaska_prilis_skoro_je_skratene_pred_okno_nie_diera():
    """The session began 20 s before the cue - the pre-window wants 60 s."""
    samples = rad(CUE - 20.0, CUE + 240.0)
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_PRE_SHORT in w["reasons"]
    assert measure.R_GAP not in w["reasons"]


def test_relacia_skoncila_skoro_je_skratene_po_okno():
    samples = rad(CUE - 120.0, CUE + 30.0)
    w = okno(samples)
    assert w["valid"] is False
    assert measure.R_POST_SHORT in w["reasons"]
    assert measure.R_PRE_SHORT not in w["reasons"]


def test_ziadne_data_je_vlastny_dovod():
    w = okno([])
    assert w["valid"] is False
    assert measure.R_NO_DATA in w["reasons"]


def test_okno_nesie_zataz_a_aktivitu():
    samples = rad(CUE - 120.0, CUE + 240.0)
    load = rad(CUE - 120.0, CUE + 240.0, bpm=lambda t: 70.0 if t < CUE else 30.0)
    aktivita = rad(CUE - 120.0, CUE + 240.0, bpm=lambda t: 100 if t < CUE else 9000)
    cue = {"ts": CUE, "category": "breath", "arm": "voice", "load_series": load}
    w = measure.build_window(cue, samples, [CUE], activity=aktivita)
    assert w["pre_load"] == 70.0
    assert w["post_load"] == 30.0
    assert w["pre_activity"] == 1.0
    assert w["post_activity"] == 0.0


def test_offset_a_hra_sa_zapisu_ked_su_zname():
    samples = rad(CUE - 120.0, CUE + 240.0)
    w = okno(samples, session_started=T0, game="Elden Ring")
    assert w["offset_s"] == 300.0
    assert w["game"] == "Elden Ring"


def test_okna_su_zoradene_podla_casu():
    samples = rad(CUE - 400.0, CUE + 600.0)
    cues = [{"ts": CUE + 400.0}, {"ts": CUE}, {"ts": CUE + 200.0}]
    okna = measure.build_windows(cues, samples)
    assert [w["ts"] for w in okna] == sorted(w["ts"] for w in okna)


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

def test_ulozenie_a_nacitanie(tmp_path):
    path = str(tmp_path / "hr_windows.json")
    assert measure.load_windows(path) == []
    assert measure.save_windows(path, [{"ts": 1.0, "valid": True}]) is True
    assert measure.save_windows(path, [{"ts": 2.0, "valid": True}]) is True
    ulozene = measure.load_windows(path)
    assert [w["ts"] for w in ulozene] == [1.0, 2.0]


def test_zapis_neostane_polovicny(tmp_path):
    """No `.tmp` may stay next to it after the write - it went via a rename."""
    path = str(tmp_path / "hr_windows.json")
    measure.save_windows(path, [{"ts": 1.0}])
    assert not os.path.exists(path + ".tmp")


def test_poskodeny_subor_sa_neprepise(tmp_path):
    """An unreadable file is no reason to throw away everything measured.

    Better to write nothing - the person notices that windows are not being
    added, and it can be rescued. Overwriting with an empty list would
    rescue nothing.
    """
    path = str(tmp_path / "hr_windows.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("toto nie je JSON")
    assert measure.save_windows(path, [{"ts": 1.0}]) is False
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "toto nie je JSON"


def test_strop_poctu_okien(tmp_path):
    path = str(tmp_path / "hr_windows.json")
    vela = [{"ts": float(i)} for i in range(measure.MAX_WINDOWS + 50)]
    measure.save_windows(path, vela)
    ulozene = measure.load_windows(path)
    assert len(ulozene) == measure.MAX_WINDOWS
    # the OLDEST are thrown away
    assert ulozene[-1]["ts"] == float(measure.MAX_WINDOWS + 49)


def test_prehlad_pocita_len_platne_okna():
    okna = [
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 90.0},
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 94.0},
        {"arm": "voice", "valid": False, "pre_bpm": 100.0, "post_bpm": 10.0},
        {"arm": "silent", "valid": True, "pre_bpm": 100.0, "post_bpm": 98.0},
    ]
    prehlad = measure.summarize(okna)
    assert prehlad["voice"]["n"] == 2
    assert prehlad["voice"]["delta_bpm"] == -8.0
    assert prehlad["silent"]["n"] == 1
    assert prehlad["silent"]["delta_bpm"] == -2.0


def test_prehlad_nerobi_ziadny_zaver():
    """Returns numbers, not a verdict - deciding needs enough windows."""
    prehlad = measure.summarize([
        {"arm": "voice", "valid": True, "pre_bpm": 100.0, "post_bpm": 50.0}])
    assert set(prehlad["voice"]) == {"n", "delta_bpm"}


# --------------------------------------------------------------------------
# `delivery` in the window - found by the review
# --------------------------------------------------------------------------

def test_okno_nesie_aj_sposob_dorucenia():
    """`arm` and `delivery` differ, and both must be in the window.

    Without `delivery` it cannot be found out afterwards which cues came at
    a pause and which only after 90 s of silence - and the pause threshold
    is exactly the number under dispute. There would be nothing to check it
    against.
    """
    cue = {"ts": 1000.0, "category": "breath", "cue_id": "slot3",
           "arm": "voice", "source": "auto", "delivery": "timeout"}
    vzorky = [(1000.0 - 60 + i, 70.0) for i in range(140)]
    okno = measure.build_window(cue, vzorky, [1000.0])
    assert okno["delivery"] == "timeout"
    assert okno["arm"] == "voice", "timeout nesmie prepísať rameno"


def test_stare_okno_bez_delivery_nepadne():
    """Data from sessions before this change have no `delivery`. They must
    still be loadable - otherwise the fix would throw away what was measured
    up to then."""
    cue = {"ts": 1000.0, "arm": "silent", "source": "auto"}
    vzorky = [(1000.0 - 60 + i, 70.0) for i in range(140)]
    okno = measure.build_window(cue, vzorky, [1000.0])
    assert okno["delivery"] is None


# --------------------------------------------------------------------------
# Category rotation (18. 9.)
#
# Until 18. 9. the app always played one fixed slot. That had one strong
# property - all windows from one category - and one fatal one: the same
# sentence a hundred times an evening stops working.
# --------------------------------------------------------------------------

def test_striedanie_ide_kolo_dokola():
    assert [measure.next_slot([0, 1, 2, 3], p) for p in (None, 0, 1, 2, 3)] \
        == [0, 1, 2, 3, 0]


def test_striedanie_preskoci_vypnute_sloty():
    """Disabled slot = the player's decision; automation must not bypass it."""
    assert [measure.next_slot([1, 3], p) for p in (None, 1, 3)] == [1, 3, 1]


def test_striedanie_pri_jedinom_slote_opakuje():
    """With one enabled slot repetition cannot be avoided - and it is better
    than silence."""
    assert measure.next_slot([2], 2) == 2


def test_striedanie_bez_slotov_vrati_none():
    """The caller then reaches for a fallback, not a random index."""
    assert measure.next_slot([], None) is None
    assert measure.next_slot(None, 1) is None


def test_striedanie_znesie_neznamy_posledny():
    """The player may have switched the slot off meanwhile. It must not crash
    or get the rotation stuck on one category."""
    assert measure.next_slot([0, 2], 1) == 0


# --------------------------------------------------------------------------
# Effectiveness by category
# --------------------------------------------------------------------------

def _okno(kat, pre, post, arm="voice", valid=True, **kw):
    # A cue delivered at a pause (0.2: the chart counts only those) - see
    # below.
    okno = {"category": kat, "pre_bpm": pre, "post_bpm": post,
            "arm": arm, "valid": valid, "delivery": "pause"}
    okno.update(kw)
    return okno


def test_ucinnost_pocita_len_hlasne_rameno():
    """Silent windows are the reference for whether a cue works AT ALL - not
    for comparing categories with each other. Mixing them would mean
    comparing a category with silence."""
    okna = [_okno("breath", 100, 95) for _ in range(6)]
    okna += [_okno("breath", 100, 60, arm="silent") for _ in range(6)]
    von = measure.by_category(okna)
    assert von["breath"]["n"] == 6
    assert von["breath"]["delta_bpm"] == -5.0


def test_ucinnost_preskoci_neplatne_okna():
    okna = [_okno("jaw", 100, 90, valid=False) for _ in range(9)]
    assert measure.by_category(okna) == {}


def test_ucinnost_pod_prahom_nedovoli_tvrdit():
    """With three windows the interval is as wide as the whole range. A chart
    that drew a bar from that would claim something that is not in the
    data."""
    okna = [_okno("jaw", 100, 96 + i) for i in range(3)]
    von = measure.by_category(okna)["jaw"]
    assert von["n"] == 3
    assert von["dost_dat"] is False


def test_ucinnost_vracia_interval_nie_hole_cislo():
    """Spec 2.1b, B2: "let the output be an estimate with an interval, never a
    bare number"."""
    okna = [_okno("release", 100, 100 - d) for d in (2, 4, 6, 4, 5, 3, 5)]
    von = measure.by_category(okna)["release"]
    assert von["dost_dat"] is True
    assert von["ci95"] is not None and von["ci95"] > 0


def test_ucinnost_jedineho_okna_nema_interval():
    """A variance cannot be computed from one value - and making one up would
    be worse than not having it."""
    von = measure.by_category([_okno("breath", 100, 94)])["breath"]
    assert von["ci95"] is None and von["dost_dat"] is False


def test_ucinnost_nerobi_zaver():
    """Returns no ranking and no "best category". From overlapping intervals
    that would make a leaderboard the data cannot carry."""
    okna = [_okno("breath", 100, 94) for _ in range(6)]
    okna += [_okno("jaw", 100, 99) for _ in range(6)]
    von = measure.by_category(okna)
    assert set(von) == {"breath", "jaw"}
    assert all(isinstance(v, dict) for v in von.values())
    assert "best" not in von and "poradie" not in von


def test_rucna_hlaska_sa_do_merania_nezapisuje():
    """A click on Test must not end up in the effectiveness chart.

    `fire_slot` is today triggered only by the Test button and a click in
    the HUD preview - both while setting up, often several times in a row
    and without playing. `by_category` filters only by `valid` and `arm`,
    it does not read `source`, so every such click would count as a cue
    and its time would also take the refractory zone from a real cue a few
    seconds later.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._note_cue)
    # only the CODE below the docstring - the note mentions the call on purpose
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "note_trigger" not in telo, "rucna hlaska sa zapisuje do merania"


def test_hlaska_bez_vizualu_sa_nedoruci():
    """A slot without an enabled in-game visual must not get into the rotation.

    In the silent arm the visual is the ONLY thing that gets delivered. A
    slot with its visual off would therefore do nothing in the silent arm,
    the window would be written as valid - and the comparison of arms,
    i.e. the whole reason why the silent cue exists, would measure silence
    against silence.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._dalsi_cue_slot)
    assert "overlay_configs" in telo, "vyber kategorie neoveruje vizual"


def test_importovane_okna_sa_do_ucinnosti_nerataju():
    """`data_io` promises imported records are excluded from effectiveness.

    It set the `imported: True` marker, but NOBODY read it - neither
    `by_category`, nor `summarize`, nor `hr_insights._valid`. Whoever
    imported a backup from a friend saw the friend's body in their chart
    mixed with their own and had no way to find out.
    """
    okna = [
        {"valid": True, "arm": "voice", "category": "jaw",
         "pre_bpm": 100.0, "post_bpm": 90.0, "delivery": "pause"},
        {"valid": True, "arm": "voice", "category": "jaw",
         "pre_bpm": 100.0, "post_bpm": 40.0, "delivery": "pause",
         "imported": True},
    ]
    podla = measure.by_category(okna)
    assert podla["jaw"]["n"] == 1, "cudzie okno sa zaratalo"
    assert abs(podla["jaw"]["delta_bpm"] - (-10.0)) < 0.001

    suhrn = measure.summarize(okna)
    assert suhrn["voice"]["n"] == 1, "cudzie okno sa zaratalo do suhrnu"


def _aktivita(t0, t1, idle_ms):
    """Even activity in a stretch - [(time, idle_ms)] like ActivityTracker."""
    return [(t, idle_ms) for t in range(int(t0), int(t1), 2)]


def test_hlaska_mimo_klavesnice_sa_do_ucinnosti_nerata():
    """When the player gets up and leaves, WALKING raises their heart rate.

    The app sees it as load, speaks up - and after they come back and sit
    down the heart rate drops. The window then looks like an effective cue,
    while it measures nothing but the person sitting down. `pre_activity`
    was written from the start, but had no effect on the window's validity.
    """
    ts = 10_000.0
    vzorky = [(t, 90.0) for t in range(int(ts - 200), int(ts + 400), 2)]
    cue = {"ts": ts, "arm": "voice", "category": "jaw", "cue_id": "slot1"}

    # at the keyboard (idle 0 ms = input is coming) -> valid
    pri_stole = _aktivita(ts - 200, ts + 400, 0)
    okno = measure.build_window(cue, vzorky, [ts], activity=pri_stole)
    assert okno["valid"], okno["reasons"]
    assert okno["pre_activity"] > 0.9

    # away from the PC (idle grows above the threshold) -> invalid, with a
    # reason
    prec = [(t, 60_000) for t in range(int(ts - 200), int(ts + 400), 2)]
    okno = measure.build_window(cue, vzorky, [ts], activity=prec)
    assert not okno["valid"]
    assert measure.R_NEAKTIVNY in okno["reasons"]


def test_neznama_aktivita_okno_nezneplatni():
    """`None` means "we do not know", not "was away".

    Older sessions did not record activity. If not knowing invalidated it,
    the whole history would be thrown away retroactively.
    """
    ts = 10_000.0
    vzorky = [(t, 90.0) for t in range(int(ts - 200), int(ts + 400), 2)]
    cue = {"ts": ts, "arm": "voice", "category": "jaw", "cue_id": "slot1"}
    okno = measure.build_window(cue, vzorky, [ts], activity=None)
    assert measure.R_NEAKTIVNY not in okno["reasons"], okno["reasons"]


def test_prepocet_okien_pouziva_rovnake_pravidlo_ako_measure():
    """`prepocitaj_okna.py` must not have its own idea of validity.

    It is the second place where it is decided whether a window is valid.
    If it diverged from `measure.build_window`, the file and the charts
    would each claim something different - and nobody would know which
    number is the right one.
    """
    import prepocitaj_okna

    # below the threshold before and after -> reason
    for pre, post in ((0.1, 1.0), (1.0, 0.0), (0.1, 0.1)):
        okno = {"pre_activity": pre, "post_activity": post}
        assert prepocitaj_okna._dovody_z_aktivity(okno) == [measure.R_NEAKTIVNY], (pre, post)

    # above the threshold -> nothing
    assert prepocitaj_okna._dovody_z_aktivity(
        {"pre_activity": 0.9, "post_activity": 0.9}) == []

    # "we do not know" must not invalidate
    assert prepocitaj_okna._dovody_z_aktivity(
        {"pre_activity": None, "post_activity": None}) == []


def test_prepocet_nesiaha_na_dovody_zo_surovych_vzoriek():
    """Reasons like `skratene_po` were computed from heart-rate samples that
    are not in the file. Computing them retroactively would mean making up
    numbers nobody measured - so the tool must not touch them.
    """
    import prepocitaj_okna
    zdroj = inspect_source(prepocitaj_okna._dovody_z_aktivity)
    for dovod in ("R_POST_SHORT", "R_PRE_SHORT", "R_GAP", "R_REFRACTORY"):
        assert dovod not in zdroj, dovod


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


# --------------------------------------------------------------------------
# An undelivered cue must not be measured (B17)
# --------------------------------------------------------------------------

def test_nevykresleny_vizual_zneplatni_okno():
    """B17: the silent arm has the visual as its only stimulus. When it was
    not drawn, the window would compare the cue against nothing - it must
    drop out of the measurement."""
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "silent",
           "source": "auto", "delivered": False}
    w = measure.build_window(cue, samples, [CUE])
    assert w["valid"] is False
    assert measure.R_NEDORUCENE in w["reasons"]


def test_dorucena_hlaska_ostava_platna():
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "silent",
           "source": "auto", "delivered": True}
    assert measure.build_window(cue, samples, [CUE])["valid"] is True


def test_stary_zaznam_bez_delivered_sa_nezneplatni():
    """Old windows have no `delivered` field (None = we do not know) - they
    must not be thrown away retroactively, the same rule as for activity."""
    samples = rad(T0, CUE + 200.0)
    cue = {"ts": CUE, "category": "breath", "cue_id": "x", "arm": "voice",
           "source": "auto"}   # no 'delivered'
    w = measure.build_window(cue, samples, [CUE])
    assert measure.R_NEDORUCENE not in w["reasons"]


# --------------------------------------------------------------------------
# A clean end of a session is not a sensor dropout (B5)
# --------------------------------------------------------------------------

def test_cisty_koniec_relacie_nie_je_diera_v_datach():
    """B5: when a cue comes at the end of the evening and the player turns off
    listening, the post-window is empty. It correctly gets `skratene_po`,
    but must NOT also get `diera_v_datach` - while debugging it claimed the
    watch had dropped out, although the player had just finished playing.
    (`gaps()` returns the whole range as the start for an empty window.)"""
    pred = rad(CUE - 60.0, CUE)              # data before the cue
    w = measure.build_window(
        {"ts": CUE, "category": "b", "cue_id": "x", "arm": "voice",
         "source": "auto"}, pred, [CUE])
    assert measure.R_POST_SHORT in w["reasons"]
    assert measure.R_GAP not in w["reasons"], "čistý koniec nie je výpadok (B5)"


def test_skutocna_diera_uprostred_ostava_diera():
    """The B5 fix must not silence the detection of a real dropout: a gap
    surrounded by data on both sides must still be `diera_v_datach`."""
    a = int(CUE + measure.DEAD_S)
    b = int(CUE + measure.POST_S)
    po = ([(t, 80.0) for t in range(a, a + 5)]
          + [(t, 80.0) for t in range(b - 5, b + 1)])   # gap in the middle of the post-window
    w = measure.build_window(
        {"ts": CUE, "category": "b", "cue_id": "x", "arm": "voice",
         "source": "auto"}, rad(CUE - 60.0, CUE) + po, [CUE])
    assert measure.R_GAP in w["reasons"]
