"""Tests for what the charts are drawn from: the session shape, zones, the
calendar grid, day streaks and the "usual range".

All without Tk. Where only the drawing can be checked (ui_kit), the test
reads the SOURCE - the same approach as test_theme_recolor.py, because no
GUI runs here.
"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats
import theme as theme_mod
from _zdroj_appky import zdroj_metody


def _read(name):
    with open(os.path.join(os.path.dirname(__file__), "..", name),
              encoding="utf-8") as fh:
        return fh.read()


def _samples(values, start=1000.0, step=1.0):
    return [(start + i * step, float(v)) for i, v in enumerate(values)]


def _session(started, **kwargs):
    base = {"started": started, "duration_s": 3600.0, "samples": 3600}
    base.update(kwargs)
    return base


# --------------------------------------------------------------------------
# downsample / trace / curve
# --------------------------------------------------------------------------

def test_downsample_prerieduje_cely_usek_nie_len_koniec():
    """Truncating would keep only the last 10 min of a two-hour session."""
    out = hr_stats.downsample(list(range(1000)), 10)
    assert len(out) == 10
    assert out[0] == 0
    assert out[-1] >= 880, "posledny bod ma byt z konca relacie"
    assert out == sorted(out), "poradie sa nesmie zamiesat"


def test_downsample_kratky_vstup_nechava_tak():
    assert hr_stats.downsample([1, 2, 3], 10) == [1, 2, 3]
    assert hr_stats.downsample([], 10) == []


def test_trace_je_cela_relacia_a_series_je_zive_okno():
    stats = hr_stats.HeartStats(110)
    for i, bpm in enumerate([60 + (i % 40) for i in range(2000)]):
        stats.add(bpm, ts=1000.0 + i)
    trace = stats.trace()
    assert len(trace) == hr_stats.CURVE_POINTS
    # `series` holds only HISTORY_SECONDS, `trace` the whole evening - those
    # are two different questions and must not return the same thing
    assert trace[0] != stats.series(hr_stats.CURVE_POINTS)[0]


def test_summary_uklada_krivku_relacie():
    stats = hr_stats.HeartStats(110)
    for i in range(600):
        stats.add(70 + (i % 20), ts=1000.0 + i)
    summary = stats.summary()
    curve = summary["curve"]
    assert len(curve) == hr_stats.CURVE_POINTS
    assert all(isinstance(v, int) for v in curve), "krivka ma byt cela cisla"
    assert summary["baseline_bpm"] and summary["critical_bpm"], (
        "pasma krivky sa dopocitavaju z tychto dvoch - bez nich sa nakreslit neda")


def test_historia_uchova_dost_relacii_na_rocny_pohlad():
    """The History page offers the period 'Year'. With 60 sessions the
    yearly chart would show two months and pretend to be a year."""
    assert hr_stats.PERIOD_YEAR in hr_stats.PERIODS
    assert hr_stats.MAX_SESSIONS >= 365


# --------------------------------------------------------------------------
# zones
# --------------------------------------------------------------------------

def test_zone_of_bpm_hranice():
    assert hr_stats.zone_of_bpm(65, 60, 110) == hr_stats.ZONE_CALM
    assert hr_stats.zone_of_bpm(70, 60, 110) == hr_stats.ZONE_RAISED
    assert hr_stats.zone_of_bpm(85, 60, 110) == hr_stats.ZONE_HIGH
    assert hr_stats.zone_of_bpm(110, 60, 110) == hr_stats.ZONE_CRITICAL


def test_time_in_zones_pocita_tou_istou_funkciou_ako_graf():
    """The zone bar in the chart and the sum of seconds under it must agree."""
    values = [62] * 60 + [75] * 60 + [90] * 60 + [120] * 60
    zones = hr_stats.time_in_zones(_samples(values), critical_bpm=110, baseline=60)
    for bpm, zone in ((62, hr_stats.ZONE_CALM), (75, hr_stats.ZONE_RAISED),
                      (90, hr_stats.ZONE_HIGH), (120, hr_stats.ZONE_CRITICAL)):
        assert zones[hr_stats.zone_of_bpm(bpm, 60, 110)] > 0
        assert hr_stats.zone_of_bpm(bpm, 60, 110) == zone


def test_kazde_pasmo_ma_v_oboch_temach_inu_farbu():
    """Regression: the zones were drawn success -> accent -> warn -> danger,
    but `accent` and `warn` in Sumi are two almost identical golds. So the
    four zones could not be told apart on one strip."""
    for kluc in (theme_mod.ZEN, theme_mod.MODERN):
        pal = theme_mod.tokens(kluc)
        farby = [theme_mod.zone_color(pal, z).lower()
                 for z in ("calm", "raised", "high", "critical")]
        assert len(set(farby)) == 4, f"tema {kluc}: pasma maju spolocnu farbu ({farby})"


def test_hud_v_hre_farbi_pasma_rovnako_ako_okno():
    """Regression: the HUD had its own success/accent pair, so after every
    theme got its own sequence, it glowed green in game even where the app
    window already drew blue."""
    import hud_paint
    for kluc in (theme_mod.ZEN, theme_mod.MODERN):
        pal = theme_mod.tokens(kluc)
        style = hud_paint.Style(pal)
        for zona in ("calm", "raised", "high", "critical"):
            # `Style` holds colours as RGB triples, the theme as #rrggbb
            assert (hud_paint.zone_color(style, zona)
                    == hud_paint._hex(theme_mod.zone_color(pal, zona))), \
                f"tema {kluc}, pasmo {zona}"


def test_hud_style_bez_palety_nepadne():
    """Style() without a palette (tests, fallback) must have zones too."""
    import hud_paint
    style = hud_paint.Style()
    for zona in ("calm", "raised", "high", "critical"):
        farba = hud_paint.zone_color(style, zona)
        assert isinstance(farba, tuple) and len(farba) == 3


def test_zone_tokens_pokryvaju_vsetky_pasma():
    zony = (hr_stats.ZONE_CALM, hr_stats.ZONE_RAISED, hr_stats.ZONE_HIGH,
            hr_stats.ZONE_CRITICAL)
    assert set(theme_mod.ZONE_TOKENS) == set(zony)


# --------------------------------------------------------------------------
# usual range, metric series
# --------------------------------------------------------------------------

def test_usual_range_je_kvartilovy_pas():
    lo, hi = hr_stats.usual_range([10, 20, 30, 40, 50, 60, 70, 80])
    assert lo < hi
    assert 10 < lo <= 30 and 50 <= hi < 80


def test_usual_range_mlci_pri_malo_datach():
    assert hr_stats.usual_range([60, 62, 61]) is None
    assert hr_stats.usual_range([]) is None


def test_usual_range_ignoruje_none_a_nezmysly():
    assert hr_stats.usual_range([60, None, 62, "x", 64, 66]) is not None


def test_metric_series_preskakuje_chybajuce_hodnoty():
    sessions = [_session(1000, baseline_bpm=60), _session(2000),
                _session(3000, baseline_bpm=64)]
    assert hr_stats.metric_series(sessions, "baseline_bpm") == [60.0, 64.0]


def test_metric_series_vracia_poslednych_n_chronologicky():
    sessions = [_session(1000 * i, baseline_bpm=i) for i in range(1, 11)]
    assert hr_stats.metric_series(sessions, "baseline_bpm", n=3) == [8.0, 9.0, 10.0]


# --------------------------------------------------------------------------
# day grid and streaks
# --------------------------------------------------------------------------

def _ts(days_ago, now):
    return (datetime.fromtimestamp(now) - timedelta(days=days_ago)).timestamp()


def test_day_activity_ma_aj_prazdne_dni():
    """The gaps are what the grid is read for - they must not drop out."""
    now = time.time()
    cells = hr_stats.day_activity([_session(_ts(2, now), duration_s=600.0)],
                                  days=10, now=now)
    assert len(cells) == 10
    assert cells[-1]["date"] == datetime.fromtimestamp(now).date()
    assert sum(1 for c in cells if c["seconds"] == 0) == 9
    assert [c["seconds"] for c in cells if c["seconds"]] == [600.0]


def test_day_activity_scita_viac_relacii_za_den():
    now = time.time()
    cells = hr_stats.day_activity(
        [_session(_ts(1, now), duration_s=600.0),
         _session(_ts(1, now), duration_s=900.0)], days=5, now=now)
    den = [c for c in cells if c["count"]][0]
    assert den["count"] == 2 and den["seconds"] == 1500.0


def test_day_activity_ignoruje_relacie_mimo_okna():
    now = time.time()
    cells = hr_stats.day_activity([_session(_ts(40, now))], days=7, now=now)
    assert all(c["count"] == 0 for c in cells)


def test_seria_dni_uz_v_appke_nie_je():
    """A safeguard against a quiet comeback.

    `streaks()` was dropped deliberately - it is the only thing in the app
    that can be broken, and the app is meant to calm. If anyone (including
    my future self) brought it back, let it fail here and not only in the
    head of a player who notices that the app counts how many evenings in a
    row they played.
    """
    assert not hasattr(hr_stats, "streaks")


def test_pocet_dni_s_relaciou_sa_da_spocitat_z_mriezky():
    """Replacement for the streak: how many days in the window had at least
    one session.

    A gap between days has no effect on it - that is the whole point.
    """
    now = time.time()
    sessions = [_session(_ts(d, now)) for d in (10, 9, 8, 6, 5)]
    cells = hr_stats.day_activity(sessions, days=14, now=now)
    assert sum(1 for c in cells if c["count"]) == 5


# --------------------------------------------------------------------------
# drawing - what, without Tk, can only be checked from the source
# --------------------------------------------------------------------------

def test_sparkline_nezahadzuje_nulu():
    """Regression: the filter was `if v`, so zero also dropped out of the
    chart. For heart rate it does not matter (0 BPM does not exist), but
    History also sends 'time over the limit' here - and there zero is a
    valid value, not a missing point."""
    src = _read("ui_kit.py")
    start = src.index("class Sparkline(")
    telo = src[start:src.index("class SegmentBar(", start)]
    assert "if v is not None" in telo
    assert "(values or []) if v]" not in telo


def test_graf_historie_kresli_popisky_osi():
    """`aggregate_by_period` computes the bucket label - the chart must use
    it, otherwise the line hangs in empty space without saying when and how
    much."""
    assert "label" in hr_stats.aggregate_by_period(
        [_session(time.time())], hr_stats.PERIOD_DAY)[0]
    telo = zdroj_metody("_refresh_history_trend")
    assert "labels=labels" in telo, "graf trendu ma dostat popisky osi x"
    assert "band=band" in telo, "graf trendu ma kreslit bezne rozpatie"


def test_pasma_beru_farbu_z_jedneho_miesta():
    """Whoever colours zones alone drifts from the legend sooner or later."""
    ui = _read("ui_kit.py")
    for trieda in ("class ZoneBar(", "class SessionTrace("):
        start = ui.index(trieda)
        koniec = ui.index("\nclass ", start + 1)
        assert "theme_mod.zone_color(" in ui[start:koniec], f"{trieda} farbi sam"


def test_note_trigger_zapise_sposob_dorucenia():
    """`_fire_somatic_cue` passes `delivery` from the state machine's event;
    without that it would not get into the measurement (found by a review)."""
    import hr_stats as hs
    st = hs.HeartStats(critical_bpm=110)
    st.session_start = 1000.0
    st.note_trigger(ts=1010.0, auto=True, arm="voice", source="auto",
                    delivery="pause")
    assert st.cues[-1]["delivery"] == "pause"
    st.note_trigger(ts=1020.0, auto=False, source="hud_panel")
    assert st.cues[-1]["delivery"] is None, "klik v paneli nemá spôsob doručenia"
