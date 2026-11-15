# -*- coding: utf-8 -*-
"""Learning your own limits (0.2.1): what the README promises, the code does.

  1. Session world: the "Playing / Working" answer in the questionnaire is
     a CORRECTION of the world - it also moves the session into the
     learning of the critical heart rate and the threshold. Deliberately
     (see the comment at `hr_stats.WORLD_DEFAULT`); these tests hold it so
     that it does not change quietly and the README can say it honestly.
  2. The critical heart rate (the high heart-rate limit) is learned only
     from sessions of at least 5 min, by the same rule as the load
     threshold (`je_dost_dlha`). Three short sessions while pairing the
     watch no longer replace the fallback 110.
  3. Load threshold: "three sessions of about ten minutes are enough,
     three of five are not" also holds with ordinary signal coverage
     (85-90 %), not only at 100 %.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats  # noqa: E402


def _relacia(minut, pokrytie=None, kadencia_s=1.0, bodov=None, **kw):
    """Session summary like `HeartStats.summary`, only fields learning reads.

    `pokrytie` None = an old session without `zone_seconds` (the whole
    duration is replayed). Otherwise the zones together are
    `trvanie * pokrytie` and the curve has as many points as the watch
    with the given cadence would send in that time (at most
    `CURVE_POINTS`, like `downsample`). A smooth wave - `je_podozriva`
    leaves it alone.
    """
    trvanie = minut * 60.0
    signal = trvanie * (pokrytie if pokrytie is not None else 1.0)
    if bodov is None:
        bodov = min(hr_stats.CURVE_POINTS, int(signal / kadencia_s))
    s = {"duration_s": trvanie, "baseline_bpm": 70.0, "max_bpm": 95.0,
         "curve": [round(75 + 15 * math.sin(i / 7.0), 1) for i in range(bodov)]}
    if pokrytie is not None:
        s["zone_seconds"] = {"calm": signal * 0.5, "raised": signal * 0.3,
                             "high": signal * 0.2, "critical": 0.0}
    s.update(kw)
    return s


def _prah(relacie):
    return hr_stats.dynamicky_prah_zataze(relacie, baseline=70.0, critical=110)


# --------------------------------------------------------------------------
# 3. Load threshold: three of ten minutes are enough even with signal gaps
# --------------------------------------------------------------------------

def test_relacia_da_bodov_podla_signalu_bez_kalibracie():
    """Arithmetic from the comment at `PRAH_MIN_BODOV`: step 1.5 s, only time
    with signal, the first 29 steps are calibration."""
    for minut, p in ((10, 0.85), (10, 0.9), (10, 1.0), (5, 1.0)):
        body = hr_stats.load_z_krivky(_relacia(minut, p), 70.0, 110)
        assert len(body) == int(minut * 60 * p / 1.5) - 29, (minut, p)


@pytest.mark.parametrize("pokrytie", [0.85, 0.9, 0.95, 1.0, None])
@pytest.mark.parametrize("kadencia_s", [1.0, 2.0])
def test_tri_relacie_po_desat_minut_staci_aj_pri_beznom_pokryti(pokrytie, kadencia_s):
    """README: "three of about ten minutes are enough". With the old minimum
    of 1000 points they already failed at 90 % coverage (3 x 331 = 993)."""
    relacie = [_relacia(10, pokrytie, kadencia_s) for _ in range(3)]
    assert all(not hr_stats.je_podozriva(r) for r in relacie)
    prah = _prah(relacie)
    assert prah is not None, (pokrytie, kadencia_s)
    lo, hi = hr_stats.PRAH_ROZSAH
    assert lo <= prah <= hi


@pytest.mark.parametrize("bodov", [None, hr_stats.CURVE_POINTS])
def test_tri_relacie_po_pat_minut_nestacia_ani_pri_plnom_pokryti(bodov):
    """README: "three of five are not" - neither with full coverage, nor with
    a curve densified to the full `CURVE_POINTS` (time is replayed, not
    the curve points)."""
    for pokrytie in (1.0, None):
        relacie = [_relacia(5, pokrytie, bodov=bodov) for _ in range(3)]
        assert _prah(relacie) is None, (pokrytie, bodov)


def test_minimum_bodov_lezi_medzi_slubenymi_hranami():
    """Concrete numbers from the comment - so that the minimum does not shift
    such that the README would lie again in one direction or the other."""
    def spolu(minut, p):
        return 3 * len(hr_stats.load_z_krivky(_relacia(minut, p), 70.0, 110))
    assert spolu(5, 1.0) < hr_stats.PRAH_MIN_BODOV      # three of five not
    assert spolu(8, 1.0) < hr_stats.PRAH_MIN_BODOV      # nor three of eight
    assert spolu(10, 0.85) >= hr_stats.PRAH_MIN_BODOV   # three of ten yes
    # "about half an hour of heart rate": the minimum together with the
    # calibration of three sessions
    tep_min = (hr_stats.PRAH_MIN_BODOV + 3 * 29) * 1.5 / 60.0
    assert 20.0 <= tep_min <= 30.0, tep_min


def test_dlha_relacia_s_dierami_sa_do_prahu_rata_ako_doteraz():
    """A new minimum does not change WHICH sessions count, only points needed.

    Two long sessions have enough points even on their own, so the result
    is decided only by the number of sessions and their length, not by
    the point minimum."""
    dve = [_relacia(20, 0.9) for _ in range(2)]
    assert sum(len(hr_stats.load_z_krivky(r, 70.0, 110))
               for r in dve) >= hr_stats.PRAH_MIN_BODOV
    assert _prah(dve) is None, "tri relacie ostavaju podmienkou"
    assert _prah(dve + [_relacia(4.9, 1.0)]) is None, "5 minut tiez"
    assert _prah(dve + [_relacia(5, 1.0)]) is not None


# --------------------------------------------------------------------------
# 2. Critical heart rate: only from sessions of at least 5 minutes
# --------------------------------------------------------------------------

def test_je_dost_dlha_to_iste_pravidlo_ako_prah():
    assert hr_stats.je_dost_dlha({"duration_s": hr_stats.PRAH_MIN_TRVANIE_S})
    assert hr_stats.je_dost_dlha({"duration_s": 3600})
    assert not hr_stats.je_dost_dlha({"duration_s": hr_stats.PRAH_MIN_TRVANIE_S - 0.1})
    for zla in ({}, {"duration_s": None}, {"duration_s": "dlho"},
                {"duration_s": [600]}, {"duration_s": float("nan")},
                {"duration_s": float("inf")}, {"duration_s": -600}):
        assert not hr_stats.je_dost_dlha(zla), zla
    assert not hr_stats.je_dost_dlha(None)
    assert not hr_stats.je_dost_dlha("relacia")


def test_tri_kratke_relacie_nenahradia_zalohu_kritickeho_tepu():
    """Three two-minute sessions (pairing the watch, heart rate at rest) have
    360 curve points in total - above `KRITICKY_MIN_BODOV`. Until 0.2.1
    they produced a limit of 80 instead of the fallback 110."""
    kratke = [_relacia(2, 1.0) for _ in range(3)]
    assert sum(len(r["curve"]) for r in kratke) >= hr_stats.KRITICKY_MIN_BODOV
    assert hr_stats.dynamicky_kriticky(kratke) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        kratke, baseline=70.0) == hr_stats.KRITICKY_ZALOHA
    # Check that the test measures length, not points: the same curve with
    # 5 minutes does give its own limit.
    dlhe = [dict(r, duration_s=hr_stats.PRAH_MIN_TRVANIE_S) for r in kratke]
    assert hr_stats.dynamicky_kriticky(dlhe) != hr_stats.KRITICKY_ZALOHA


def test_kratke_relacie_sa_do_troch_potrebnych_nerataju():
    dve_dlhe = [_relacia(20, 1.0) for _ in range(2)]
    kratke = [_relacia(3, 1.0) for _ in range(3)]
    assert hr_stats.dynamicky_kriticky(dve_dlhe + kratke) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        dve_dlhe + kratke + [_relacia(20, 1.0)]) != hr_stats.KRITICKY_ZALOHA


def test_kratke_relacie_nevytlacia_dlhe_z_okna_poslednych_dvadsiatich():
    """Filtering happens BEFORE picking the last `KRITICKY_Z_RELACII` - just
    like for the threshold. Otherwise a few short sessions at the end
    would push out the long evenings."""
    # The first five long evenings are tenser. If the window were cut first
    # and filtered only afterwards, those would be the ones to drop out - with
    # identical curves the test would not notice (15 identical evenings give
    # the same percentile as 20).
    napate = [_relacia(20, 1.0, curve=[120.0] * 400) for _ in range(5)]
    dlhe = napate + [_relacia(20, 1.0)
                     for _ in range(hr_stats.KRITICKY_Z_RELACII - 5)]
    kratke = [_relacia(2, 1.0, curve=[150.0] * 120) for _ in range(5)]
    assert hr_stats.dynamicky_kriticky(dlhe + kratke) == \
        hr_stats.dynamicky_kriticky(dlhe)
    # Test assumption: without the tense evenings a different limit comes out.
    assert hr_stats.dynamicky_kriticky(dlhe[5:]) != \
        hr_stats.dynamicky_kriticky(dlhe)


def test_pokazene_trvanie_nezhodi_vypocet_ani_neuci():
    """`float("dlho")` used to raise an exception in the threshold - and in
    `_open_hr_session` the long-term baseline would crash with it too."""
    dobre = [_relacia(10, 1.0) for _ in range(3)]
    zla = _relacia(10, 1.0, duration_s="dlho")
    assert _prah(dobre + [zla]) == _prah(dobre)
    assert hr_stats.dynamicky_kriticky(dobre + [zla]) == \
        hr_stats.dynamicky_kriticky(dobre)


def test_zakladna_berie_aj_kratke_relacie():
    """The 5-minute rule is for the limits, not for the resting baseline."""
    kratke = [_relacia(2, 1.0, baseline_bpm=b) for b in (60.0, 62.0, 64.0)]
    assert hr_stats.dlhodoba_zakladna(kratke) is not None


# --------------------------------------------------------------------------
# 1. World: the questionnaire answer is a correction - for learning too
# --------------------------------------------------------------------------

def test_praca_odpovedana_ako_hra_sa_uci_ako_hra():
    """I forgot to switch from Work and played - I answer "Playing" and the
    evening counts towards the critical heart rate and the load threshold
    of Play."""
    hra = [_relacia(15, 0.95, world="play") for _ in range(2)]
    oprava = _relacia(15, 0.95, world="work", activity="play")
    herna = hr_stats.sessions_in_world(hra + [oprava], "play")
    assert herna == hra + [oprava]
    assert hr_stats.dynamicky_kriticky(herna) != hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is not None
    # without an answer the stamp from the start stays - and play has only
    # two sessions
    bez_odpovede = dict(oprava)
    del bez_odpovede["activity"]
    herna = hr_stats.sessions_in_world(hra + [bez_odpovede], "play")
    assert herna == hra
    assert hr_stats.dynamicky_kriticky(herna) == hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is None


def test_hra_odpovedana_ako_praca_z_ucenia_vypadne():
    hra = [_relacia(15, 0.95, world="play") for _ in range(2)]
    praca = _relacia(15, 0.95, world="play", activity="work")
    herna = hr_stats.sessions_in_world(hra + [praca], "play")
    assert herna == hra
    assert hr_stats.dynamicky_kriticky(herna) == hr_stats.KRITICKY_ZALOHA
    assert _prah(herna) is None
    # the baseline comes from everything - there is one body, the world does
    # not change it
    assert hr_stats.dlhodoba_zakladna(hra + [praca]) is not None
