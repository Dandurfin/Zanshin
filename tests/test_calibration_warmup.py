# -*- coding: utf-8 -*-
"""Kalibracia na zaciatku relacie (B3b, KNOWN_ISSUES §7)."""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats  # noqa: E402
import hud_paint  # noqa: E402
import i18n  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_appky  # noqa: E402

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _feed(stats, values, start=1000.0, step=1.5):
    for i, bpm in enumerate(values):
        stats.add(bpm, ts=start + i * step)
    return start + len(values) * step


def test_kalibruje_sa_kym_nie_je_prva_zakladna():
    stats = hr_stats.HeartStats(110)
    assert stats.is_calibrating
    end = _feed(stats, [72] * 29)
    assert stats.is_calibrating and stats.baseline is None
    _feed(stats, [72], start=end)
    assert not stats.is_calibrating and stats.baseline is not None


def test_voci_minimu_prvych_sekund_sa_zataz_nepocita():
    stats = hr_stats.HeartStats(110)
    end = _feed(stats, [50] + [80] * 28)
    assert stats.is_calibrating
    assert stats.stress == 0.0
    _feed(stats, [80] * 60, start=end)
    assert not stats.is_calibrating
    assert stats.zone == hr_stats.ZONE_CALM
    assert stats.peak_stress < 5


def test_pocas_kalibracie_plati_dlhodoba_zakladna():
    stats = hr_stats.HeartStats(110)
    stats.long_baseline = 62.0
    _feed(stats, [90] * 10)
    assert stats.is_calibrating
    assert stats._zakladna_bez_odhadu() == 62.0
    assert stats.stress > 0.0
    assert stats.zone_seconds[hr_stats.ZONE_CALM] == 0.0
    assert stats.zone_seconds[hr_stats.ZONE_HIGH] > 0.0


@pytest.mark.parametrize("dlhodoba", [None, 70.0])
def test_zakladna_cez_hranicu_kalibracie_ide_len_nadol(dlhodoba):
    stats = hr_stats.HeartStats(110)
    stats.long_baseline = dlhodoba
    rng = random.Random(3)
    t = 1000.0
    videne = []
    for i in range(400):
        bpm = 78 + rng.randint(-6, 6) + (25 if 150 < i < 260 else 0)
        stats.add(bpm, ts=t)
        t += 1.5
        base = stats._zakladna_bez_odhadu()
        if base is not None:
            videne.append(base)
    assert videne
    for pred, po in zip(videne, videne[1:]):
        assert po <= pred, f"zakladna stupla z {pred} na {po}"


def test_kotva_prezije_dlhy_vypadok():
    stats = hr_stats.HeartStats(110)
    t = _feed(stats, [62] * 200)
    stats.clear_live()
    t += hr_stats.BASELINE_SECONDS + 100
    _feed(stats, [85] * 5, start=t)
    assert stats.baseline is None
    assert not stats.is_calibrating
    assert stats._zakladna_bez_odhadu() == 62
    assert stats.stress > 0.0


def test_spicka_a_cas_vo_vysokej_ignoruju_kalibraciu():
    stats = hr_stats.HeartStats(110)
    stats.long_baseline = 60.0
    end = _feed(stats, [130] * 29)
    assert stats.is_calibrating and stats.stress > 50
    assert stats.peak_stress == 0.0
    assert stats.time_high == 0.0
    assert stats._load == []
    _feed(stats, [130] * 30, start=end)
    assert not stats.is_calibrating
    assert stats.peak_stress > 50
    assert len(stats._load) == 30
    assert stats.time_high > 0.0


def test_prah_zo_starych_relacii_vynecha_kalibraciu():
    relacia = {"curve": [70 + (i % 20) for i in range(600)], "duration_s": 600.0}
    body = hr_stats.load_z_krivky(relacia, 65.0, 110)
    assert len(body) == int(600.0 / 1.5) - 29


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _automat(**params):
    h = Hodiny()
    t = trigger.CueTrigger(params=params, rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0)
    return t, h


def test_kalibracia_nenatiahne_ani_pri_citlivosti_viac():
    t, h = _automat(**trigger.params_for(trigger.CITLIVOST_VIAC))
    for _ in range(90):
        assert t.note_load(90.0, h.t, calibrating=True) is None
        h.t += 1.0
    assert t.state == trigger.IDLE
    assert t.armed_count == 0


def test_cas_z_kalibracie_sa_do_drzania_nepocita():
    t, h = _automat()
    drzanie = t.params["stress_hold_s"]
    for _ in range(40):
        t.note_load(80.0, h.t, calibrating=True)
        h.t += 1.0
    koniec_kalibracie = h.t
    natiahnute = None
    for _ in range(200):
        if t.note_load(80.0, h.t):
            natiahnute = h.t
            break
        h.t += 1.0
    assert natiahnute is not None
    assert natiahnute - koniec_kalibracie >= drzanie


def test_bez_priznaku_sa_spravanie_nemeni():
    t, h = _automat()
    for _ in range(200):
        if t.note_load(80.0, h.t):
            break
        h.t += 1.0
    assert t.is_armed
    assert h.t - 1000.0 == pytest.approx(t.params["stress_hold_s"], abs=1.0)


def test_appka_aj_simulacia_podavaju_kalibraciu_spustacu():
    app_src = zdroj_appky()
    with open(os.path.join(PROJ, "simulate.py"), encoding="utf-8") as fh:
        sim_src = fh.read()
    assert "calibrating=self.hr_stats.is_calibrating" in app_src
    assert "calibrating=stats.is_calibrating" in sim_src


def test_kluc_kalibrujem_existuje():
    zaznam = i18n.STRINGS["hud.calibrating"]
    assert zaznam["sk"] == "kalibrujem…"
    assert zaznam["en"] == "calibrating…"
    assert set(zaznam) == set(i18n.LANGUAGES)


@pytest.fixture
def style():
    if not hud_paint.PIL_AVAILABLE:
        pytest.skip("pillow nie je nainstalovany")
    import theme as theme_mod
    return hud_paint.Style(theme_mod.tokens(theme_mod.MODERN))


def _hud(style, stress, calibrating, labels=None):
    return hud_paint.render_hud(style, bpm=128, stress=stress,
                                history=[70 + i % 40 for i in range(90)],
                                threshold=110, baseline=None,
                                labels=labels or {}, pulse=0.3,
                                session="0:40", calibrating=calibrating, ss=2)


def test_hud_pocas_kalibracie_zataz_neukaze(style):
    nizka = _hud(style, 5.0, True)
    vysoka = _hud(style, 95.0, True)
    assert nizka.tobytes() == vysoka.tobytes()
    assert vysoka.tobytes() != _hud(style, 95.0, False).tobytes()


def test_hud_pocas_kalibracie_pise_kalibrujem(style, monkeypatch):
    napisane = []
    povodny = hud_paint.Painter.text

    def zapis(self, x, y, text, *args, **kwargs):
        napisane.append(text)
        return povodny(self, x, y, text, *args, **kwargs)

    monkeypatch.setattr(hud_paint.Painter, "text", zapis)
    labels = {"load": "ZÁŤAŽ", "critical": "Špička",
              "calibrating": "kalibrujem…"}
    _hud(style, 95.0, True, labels)
    assert "KALIBRUJEM..." in napisane
    assert "ŠPIČKA" not in napisane
    napisane.clear()
    _hud(style, 95.0, False, labels)
    assert "ŠPIČKA" in napisane and "KALIBRUJEM..." not in napisane
