# -*- coding: utf-8 -*-
"""The heart-rate number on screen is smoothed, the measurement is not (0.3).

The watch app can write two heart-rate streams into one source (5-10 BPM
apart, ~2 messages per second). The screen showed the last raw value, so
the number jumped up and down within the same second.

Guarded:
  * the HUD, Today and the label by the switch show `HeartStats.display_bpm` -
    the median of the samples from the last `ZOBRAZ_OKNO_S` seconds, always
    at least the last one,
  * EVERY sample goes into measuring as before (`add`, session summary,
    zone, `_hr_last_bpm` for decisions),
  * the window is reset on a dropout and stop (`clear_live`) and on a new
    session (`reset_session`) - where `_hr_last_bpm` is reset.

All streams are artificial - no real measured data.
"""
import os
import sys
import time
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

T0 = 1_700_000_000.0
# Artificial values of two streams (7 BPM apart) - made up, not measured.
HORE, DOLE = 97, 90


def _nic(*_a, **_k):
    return None


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _dva_rady(st, t=T0, n=10, hore=HORE, dole=DOLE):
    """Artificial streams: each second the higher, 0,5 s later the lower."""
    for _ in range(n):
        st.add(hore, ts=t)
        st.add(dole, ts=t + 0.5)
        t += 1.0
    return t


# --------------------------------------------------------------------------
# HeartStats.display_bpm
# --------------------------------------------------------------------------

def test_okno_je_tri_sekundy_a_ohranicene():
    assert hr_stats.ZOBRAZ_OKNO_S == 3.0
    st = hr_stats.HeartStats()
    for i in range(500):
        st.add(80, ts=T0 + i * 0.01)
    assert len(st._zobraz) <= hr_stats.ZOBRAZ_MAX_VZORIEK


def test_bez_tepu_nic_a_prva_vzorka_hned():
    st = hr_stats.HeartStats()
    assert st.display_bpm is None
    st.add(73, ts=T0)
    assert st.display_bpm == 73, "aspon posledna vzorka, ziadne cakanie"


def test_dva_rady_nerozskacu_cislo():
    st = hr_stats.HeartStats()
    t = _dva_rady(st)
    zobrazene = set()
    for _ in range(6):
        st.add(HORE, ts=t)
        zobrazene.add(st.display_bpm)
        st.add(DOLE, ts=t + 0.5)
        zobrazene.add(st.display_bpm)
        t += 1.0
    # the raw value jumps HORE <-> DOLE, the number holds between the streams
    assert st.last_bpm == DOLE
    assert all(DOLE < z < HORE for z in zobrazene), zobrazene
    assert max(zobrazene) - min(zobrazene) <= 2, zobrazene


def test_median_zahodi_jednu_ujdenu_hodnotu():
    st = hr_stats.HeartStats()
    for i, bpm in enumerate((80, 81, 80, 81, 80)):
        st.add(bpm, ts=T0 + i)
    st.add(140, ts=T0 + 5)             # one spike
    assert st.last_bpm == 140
    assert st.display_bpm in (80, 81)


def test_starsie_nez_okno_sa_nepocita():
    st = hr_stats.HeartStats()
    for i in range(5):
        st.add(70, ts=T0 + i)
    # after a gap longer than the window only the new value counts
    st.add(95, ts=T0 + 4 + hr_stats.ZOBRAZ_OKNO_S + 0.1)
    assert st.display_bpm == 95
    # the window is measured from the last sample, not from the clock - the
    # number does not drift
    assert st.display_bpm == 95


def test_hodiny_posunute_dozadu_neberu_vzorky_z_buducnosti():
    st = hr_stats.HeartStats()
    st.add(80, ts=T0 + 10)
    st.add(80, ts=T0 + 11)
    st.add(120, ts=T0 + 5)             # the PC clock jumped back
    assert st.display_bpm == 120


def test_cislo_ide_s_tepom_do_par_sekund():
    """Smoothing must not hide a real rise in heart rate."""
    st = hr_stats.HeartStats()
    t = T0
    for _ in range(10):
        st.add(70, ts=t)
        t += 1.0
    for _ in range(3):
        st.add(100, ts=t)
        t += 1.0
    assert st.display_bpm == 100


def test_vypadok_a_nova_relacia_okno_vynuluju():
    st = hr_stats.HeartStats()
    t = _dva_rady(st)
    st.clear_live()                    # dropout / sensor switched off
    assert st.display_bpm is None
    st.add(90, ts=t)                   # in the same 3 s window - old ones are not
    assert st.display_bpm == 90
    _dva_rady(st, t + 1.0)
    st.reset_session()                 # new session (`_open_hr_session`)
    assert st.display_bpm is None
    st.add(66, ts=t + 12.0)
    assert st.display_bpm == 66


def test_meranie_dostava_kazdu_vzorku():
    """Raw samples stay in every measurement - only the number is smoothed."""
    st = hr_stats.HeartStats(critical_bpm=110)
    hodnoty = []
    t = T0
    for i in range(40):
        for bpm in (HORE + i % 3, DOLE - 2 - i % 2):
            st.add(bpm, ts=t)
            hodnoty.append((t, float(bpm)))
            t += 0.5
    assert st._all == hodnoty
    assert st.session_count == len(hodnoty)
    assert st.session_max == max(b for _, b in hodnoty)
    assert st.session_min == min(b for _, b in hodnoty)
    assert st.average == pytest.approx(sum(b for _, b in hodnoty) / len(hodnoty))
    assert st.last_bpm == hodnoty[-1][1]
    # zone still from the median of 5 RAW samples, not the number on screen
    posledne = sorted(b for _, b in hodnoty[-hr_stats.ZONE_MEDIAN_SAMPLES:])
    base = st._zakladna_bez_odhadu()
    assert base is not None
    assert st.zone == hr_stats.zone_of_bpm(posledne[2], base, st.critical_bpm)


# --------------------------------------------------------------------------
# The app: where the raw sample goes and what is shown
# --------------------------------------------------------------------------

class _Stats:
    """Dummy `hr_stats` that remembers what came into measuring."""

    def __init__(self):
        self.prijate = []
        self.last_bpm = None

    def add(self, bpm, ts=None):
        self.prijate.append(bpm)
        self.last_bpm = bpm


def _prijem(stats):
    return types.SimpleNamespace(
        _hr_generation=3, _hr_state="connecting", _hr_bind_retries=0,
        _hr_last_bpm=None, hr_stats=stats, _hr_lost=False,
        _hr_session_open=False,
        hud=types.SimpleNamespace(set_connected=_nic),
        _refresh_hud_session_text=_nic, _refresh_dnes_stats=_nic,
        refresh_hr_status_label=_nic, _refresh_kamae_state_text=_nic)


def test_apply_hr_bpm_posiela_do_merania_kazdu_surovu_vzorku():
    stats = _Stats()
    a = _prijem(stats)
    rad = [HORE, DOLE, HORE + 1, DOLE - 2, HORE - 1, DOLE + 1]
    for bpm in rad:
        _app()._apply_hr_bpm(a, bpm, 3)
        # decisions (dropout, indicator, nonstop input) come from the raw one
        assert a._hr_last_bpm == bpm
    assert stats.prijate == rad


def test_rozhodovanie_cita_surovy_tep_nie_vyhladeny():
    """`_hr_last_bpm` stays the last raw sample and is read only as
    "heart rate coming / not coming" - the smoothed number has no business
    there."""
    telo = zdroj_metody("_apply_hr_bpm")
    assert "self._hr_last_bpm = bpm" in telo
    assert "self.hr_stats.add(bpm)" in telo
    assert "display_bpm" not in telo
    for metoda in ("_zaznamenaj_vypadok", "_tick_nonstop_input"):
        assert "display_bpm" not in zdroj_metody(metoda), metoda


def _stitok_atrapa(st, **navyse):
    a = types.SimpleNamespace(
        _hr_generation=5, _hr_state="connected", _hr_last_bpm=None,
        hr_critical_bpm=110, pal=theme.tokens(theme.DEFAULT_THEME),
        hr_stats=st)
    a.__dict__.update(navyse)
    return a


def test_stitok_pri_prepinaci_ukazuje_vyhladene_cislo():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    a = _stitok_atrapa(st, _hr_last_bpm=DOLE)
    text, _farba = _app()._hr_status_display(a)
    assert text == f"❤️ {st.display_bpm} BPM"
    assert st.display_bpm != DOLE


def test_stitok_farbu_berie_z_vyhladeneho_cisla():
    """Raw 107 would be below the 110 limit, smoothed 112 is above it - the
    colour follows what the player sees."""
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4, hore=117, dole=107)
    assert st.display_bpm == 112
    a = _stitok_atrapa(st, _hr_last_bpm=107)
    assert _app()._hr_status_display(a)[1] == theme.zone_color(a.pal, "critical")


def test_stitok_bez_tepu_neukaze_cislo_ani_po_vypadku():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    st.clear_live()
    a = _stitok_atrapa(st, _hr_state="linked", _hr_last_bpm=None)
    assert "BPM" not in _app()._hr_status_display(a)[0]


class _Widget:
    def __init__(self, mapped=True):
        self.kw, self.mapped = {}, mapped

    def configure(self, **kw):
        self.kw.update(kw)

    def set_value(self, *_a, **_k):
        pass

    def set_series(self, *_a, **_k):
        pass

    def set_right(self, *_a):
        pass

    def winfo_ismapped(self):
        return self.mapped

    def pack(self, **_k):
        self.mapped = True

    def pack_forget(self):
        self.mapped = False


def test_dnes_ukazuje_vyhladene_cislo():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    a = types.SimpleNamespace(
        hr_stats=st, _hr_state="connected", _hr_lost=False,
        pal=theme.tokens(theme.MODERN), hr_critical_bpm=110,
        dnes_bpm=_Widget(), dnes_spark=_Widget(), dnes_load=_Widget(),
        dnes_zone=_Widget(), hr_panel=_Widget(),
        dnes_empty=_Widget(mapped=False), dnes_live=_Widget(),
        _refresh_session_trace=_nic, _refresh_zone_panel=_nic,
        _refresh_dashboard_stats=_nic, _refresh_last_cue=_nic,
        _stop_dnes_hero=_nic, _start_dnes_hero=_nic)
    _app()._refresh_dnes_stats(a)
    assert getattr(a, "_dnes_refresh_fails", 0) == 0
    assert a.dnes_bpm.kw["text"] == str(st.display_bpm)
    assert st.display_bpm != int(st.last_bpm)


def test_hud_kresli_vyhladene_cislo(monkeypatch):
    import hud as hud_mod
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    zachytene = {}

    def render(style, **kw):
        zachytene.update(kw)
        return object()

    monkeypatch.setattr(hud_mod.hud_paint, "render_hud", render)
    h = hud_mod.StatsHud(None, st, style=None)
    h.set_connected(True)
    h.surface = types.SimpleNamespace(draw=_nic, show=_nic)
    h._last_reposition = time.time()
    h._draw()
    assert zachytene["bpm"] == st.display_bpm
    assert zachytene["bpm"] != st.last_bpm
    # the curve stays raw - the two streams remain visible in it
    assert HORE in zachytene["history"] and DOLE in zachytene["history"]
