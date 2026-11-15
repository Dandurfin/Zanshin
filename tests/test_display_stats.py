"""Tests for resolution/monitors (display.py) and HR statistics (hr_stats.py).

Both are purely computational modules without Tk and without network, so
they can be tested directly - which is exactly why they were separated from
the rest of the app like this.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import display
import hr_stats


# --------------------------------------------------------------------------
# display.py
# --------------------------------------------------------------------------

def test_scale_is_relative_to_1080p():
    """The 4K fix's core: a visual must take the same SHARE of the screen."""
    assert display.Monitor(0, 0, 1920, 1080).scale == 1.0
    assert display.Monitor(0, 0, 3840, 2160).scale == 2.0
    assert display.Monitor(0, 0, 2560, 1440).scale > 1.3


def test_scale_is_clamped():
    """No half-screen visual on an 8K wall, and no unreadable one on 720p."""
    assert display.Monitor(0, 0, 7680, 4320).scale <= display.MAX_SCALE
    assert display.Monitor(0, 0, 1280, 720).scale >= display.MIN_SCALE


def test_place_centers_on_percentage():
    mon = display.Monitor(0, 0, 1920, 1080)
    x, y = display.place(mon, 200, 100, 50.0, 50.0)
    assert (x, y) == (860, 490)


def test_place_respects_negative_monitor_origin():
    """A monitor to the left of the primary one has a negative X - the
    original code clipped it to zero and the visual ended up on the
    primary screen."""
    mon = display.Monitor(-1920, 0, 1920, 1080)
    x, _ = display.place(mon, 300, 200, 50.0, 50.0)
    assert x < 0
    assert mon.x <= x <= mon.x + mon.width - 300


def test_place_clamps_into_target_monitor():
    mon = display.Monitor(0, 0, 1920, 1080)
    x, y = display.place(mon, 400, 300, 100.0, 100.0)
    assert x == 1920 - 400 and y == 1080 - 300
    x, y = display.place(mon, 400, 300, 0.0, 0.0)
    assert (x, y) == (0, 0)


def test_resolve_target_falls_back_when_index_missing():
    """The player unplugged the monitor the overlay was on - it must not end
    up outside the visible area."""
    mon = display.resolve_target("6")
    assert mon is not None and mon.width > 0


# --------------------------------------------------------------------------
# hr_stats.py
# --------------------------------------------------------------------------

def _feed(stats, values, start=1000.0, step=1.0):
    for i, bpm in enumerate(values):
        stats.add(bpm, ts=start + i * step)
    return start + len(values) * step


def test_rejects_implausible_values():
    """9999 or a unix timestamp is no heart rate - the previous value stays."""
    stats = hr_stats.HeartStats(110)
    stats.add(72, ts=1000.0)
    stats.add(9999, ts=1001.0)
    stats.add(1700000000, ts=1002.0)
    assert stats.last_bpm == 72


def test_baseline_needs_enough_samples():
    stats = hr_stats.HeartStats(110)
    _feed(stats, [70] * 10)
    assert stats.baseline is None, "zakladna z 10 sekund by bola nezmysel"
    _feed(stats, [70] * 40, start=1010.0)
    assert stats.baseline is not None


def test_calm_session_stays_in_calm_zone():
    stats = hr_stats.HeartStats(110)
    _feed(stats, [62, 63, 61, 62, 64, 63] * 20)
    assert stats.zone == hr_stats.ZONE_CALM
    assert stats.stress < 25


def test_sustained_elevation_raises_load():
    stats = hr_stats.HeartStats(110)
    end = _feed(stats, [62] * 120)
    calm = stats.stress
    _feed(stats, [105] * 120, start=end)
    assert stats.stress > calm + 20
    assert stats.zone in (hr_stats.ZONE_HIGH, hr_stats.ZONE_CRITICAL)


def test_time_over_threshold_is_measured_in_seconds_not_samples():
    """A faster watch (2 Hz) must not collect double the time."""
    slow = hr_stats.HeartStats(100)
    _feed(slow, [130] * 30, step=1.0)
    fast = hr_stats.HeartStats(100)
    _feed(fast, [130] * 60, step=0.5)
    assert abs(slow.time_over - fast.time_over) < 1.5


def test_series_keeps_timespan_when_downsampling():
    stats = hr_stats.HeartStats(110)
    _feed(stats, list(range(60, 160)))
    series = stats.series(20)
    assert len(series) == 20
    assert series[0] < series[-1], "krivka musi ostat od najstarsej po najnovsiu"


def test_clear_live_keeps_session_summary():
    stats = hr_stats.HeartStats(110)
    _feed(stats, [80] * 60)
    stats.note_trigger()
    stats.clear_live()
    assert stats.last_bpm is None and stats.stress == 0.0
    summary = stats.summary()
    assert summary["samples"] == 60 and summary["triggers"] == 1


def test_short_sessions_are_not_saved(tmp_path):
    """Sensor on and right off is not a session - it would muddy averages."""
    path = str(tmp_path / "hr_sessions.json")
    stats = hr_stats.HeartStats(110)
    _feed(stats, [80] * 5)
    assert hr_stats.save_session(path, stats.summary()) is False
    assert not os.path.exists(path)


def test_real_session_is_saved_and_reloaded(tmp_path):
    path = str(tmp_path / "hr_sessions.json")
    stats = hr_stats.HeartStats(110)
    _feed(stats, [80] * 200)
    stats.session_start = time.time() - 600
    assert hr_stats.save_session(path, stats.summary()) is True
    loaded = hr_stats.load_sessions(path)
    assert len(loaded) == 1 and loaded[0]["max_bpm"] == 80


def test_session_log_is_capped(tmp_path):
    # `tmp_path` (as in the tests above), not a hard-coded "/tmp/..." - that
    # path does not exist on Windows, the write silently failed and the test
    # failed on an empty list instead of checking the cap.
    path = str(tmp_path / "hr_sessions_cap.json")
    stats = hr_stats.HeartStats(110)
    _feed(stats, [80] * 200)
    summary = stats.summary()
    summary["duration_s"] = 600
    for _ in range(hr_stats.MAX_SESSIONS + 10):
        hr_stats.save_session(path, dict(summary))
    assert len(hr_stats.load_sessions(path)) == hr_stats.MAX_SESSIONS
