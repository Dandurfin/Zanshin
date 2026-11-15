"""Tests of metrics from pure BPM (hr_stats), history analysis
(hr_insights) and candidate IPs (netinfo). All without Tk, without network
(netinfo only reads addresses from the OS, sends nothing anywhere).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_insights
import hr_stats
import netinfo


def _samples(values, start=1000.0, step=1.0):
    return [(start + i * step, float(v)) for i, v in enumerate(values)]


def _feed(stats, values, start=1000.0, step=1.0):
    for i, bpm in enumerate(values):
        stats.add(bpm, ts=start + i * step)
    return start + len(values) * step


# --------------------------------------------------------------------------
# HRR
# --------------------------------------------------------------------------

def test_hrr_is_peak_minus_bpm_one_minute_later():
    """Heart rate 170 at the peak, a minute later 140 -> HRR 30 (spec)."""
    # 3 min of rest at 70, rise to 170, then linearly down to 140 over 60 s
    values = [70] * 180 + [100, 130, 160, 170] + [170 - (30 * i / 60.0) for i in range(1, 61)] + [140] * 30
    events = hr_stats.heart_rate_recovery(_samples(values))
    assert events, "vrchol 170 musi byt najdeny"
    top = max(events, key=lambda e: e["peak_bpm"])
    assert top["peak_bpm"] == 170
    assert abs(top["recovery"] - 30) <= 1
    assert hr_stats.hrr_headline(events) == 30


def test_hrr_ignores_small_wiggles_and_peaks_without_a_minute_after():
    stats_wiggle = hr_stats.heart_rate_recovery(_samples([70, 72, 71, 73, 70, 74, 71] * 30))
    assert stats_wiggle == [], "drobne zuby +-4 BPM nie su vrchol"
    # peak at the very end - there is nothing a minute after it -> no event
    events = hr_stats.heart_rate_recovery(_samples([70] * 120 + [120, 150, 160]))
    assert events == []


def test_hrr_negative_when_heart_rate_keeps_rising_after_local_peak():
    values = [70] * 120 + [110, 100, 95, 92] + [92] * 60 + [130] * 10
    events = hr_stats.heart_rate_recovery(_samples(values))
    assert any(e["peak_bpm"] == 110 and e["recovery"] > 0 for e in events)


def test_heartstats_exposes_hrr_and_summary_fields():
    stats = hr_stats.HeartStats(110)
    values = [70] * 180 + [170] + [170 - (30 * i / 60.0) for i in range(1, 61)] + [140] * 30
    _feed(stats, values)
    assert stats.hrr == 30
    summary = stats.summary()
    for key in ("baseline_bpm", "zone_seconds", "hrr_bpm", "hrr_events", "hrpi",
                "trigger_offsets_s"):
        assert key in summary, key
    assert summary["hrr_bpm"] == 30 and summary["hrr_events"] >= 1


# --------------------------------------------------------------------------
# Session resting baseline + trend
# --------------------------------------------------------------------------

def test_session_baseline_is_20th_percentile_of_whole_session():
    values = [60] * 50 + [100] * 150        # 25 % of samples at 60 -> 20th percentile = 60
    assert hr_stats.session_baseline(_samples(values)) == 60
    assert hr_stats.session_baseline(_samples([60] * 20 + [100] * 180)) == 100
    assert hr_stats.session_baseline(_samples([60] * 10)) is None


def test_baseline_trend_across_sessions_rising():
    day = 86400.0
    sessions = [{"started": 1000 + i * day, "baseline_bpm": 60 + i} for i in range(7)]
    trend = hr_stats.baseline_trend(sessions)
    assert trend["first"] == 60 and trend["last"] == 66 and trend["delta"] == 6
    assert 6.5 < trend["slope_per_week"] < 7.5
    assert trend["insufficient_span"] is False
    assert hr_stats.baseline_trend([])["points"] == []
    assert hr_stats.baseline_trend([{"started": 1, "avg_bpm": 80}])["slope_per_week"] == 0.0


def test_baseline_trend_flags_insufficient_span_instead_of_exploding():
    """Bug (fixed): sessions a few minutes apart gave "-3009 BPM/tyzden"
    (per week) and similar nonsense, because the regression divided by an
    almost zero time spread. Now the slope is not given at all with a
    short spacing."""
    sessions = [
        {"started": 1000.0, "baseline_bpm": 62.0},
        {"started": 1000.0 + 5 * 60, "baseline_bpm": 58.0},   # 5 minutes later
        {"started": 1000.0 + 11 * 60, "baseline_bpm": 61.0},  # another 6 minutes on
    ]
    trend = hr_stats.baseline_trend(sessions)
    assert trend["insufficient_span"] is True
    assert trend["slope_per_week"] == 0.0
    # first/last/delta are independent of the regression and may stay usable
    assert trend["first"] == 62.0 and trend["last"] == 61.0

    # exactly at the limit (2 days) the spacing is already sufficient
    sessions_ok = [
        {"started": 1000.0, "baseline_bpm": 60.0},
        {"started": 1000.0 + hr_stats.MIN_TREND_SPAN_S, "baseline_bpm": 64.0},
    ]
    assert hr_stats.baseline_trend(sessions_ok)["insufficient_span"] is False


# --------------------------------------------------------------------------
# Time periods (History: Day / Week / Month / Year)
# --------------------------------------------------------------------------

def test_aggregate_by_period_buckets_same_day_together():
    # a realistic (current era) base - datetime.timestamp() on Windows cannot
    # handle negative/near-epoch values, which "started" would never actually
    # have (always from time.time())
    base = time.mktime((2026, 3, 10, 9, 0, 0, 0, 0, -1))
    day = 86400.0
    sessions = [
        {"started": base, "baseline_bpm": 60.0, "hrr_bpm": 10, "time_over_s": 30, "peak_stress": 20},
        {"started": base + 3600, "baseline_bpm": 70.0, "hrr_bpm": 20, "time_over_s": 90, "peak_stress": 40},
        {"started": base + day, "baseline_bpm": 80.0, "hrr_bpm": None, "time_over_s": 0, "peak_stress": 10},
    ]
    buckets = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    assert len(buckets) == 2, "prve dve relacie su v ten isty den"
    first, second = buckets
    assert first["count"] == 2
    assert first["baseline"] == 65.0          # (60+70)/2
    assert first["hrr"] == 15.0               # (10+20)/2
    assert first["over_s"] == 60.0            # (30+90)/2
    assert second["count"] == 1
    assert second["baseline"] == 80.0
    assert second["hrr"] is None, "None sa nezapocitava do priemeru"
    assert first["started"] < second["started"]


def test_aggregate_by_period_month_and_year_bucketing():
    """"Month -> daily averages, year -> monthly" - exactly as in the spec."""
    sessions = [
        {"started": time.mktime((2026, 1, 5, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 60.0},
        {"started": time.mktime((2026, 1, 5, 18, 0, 0, 0, 0, -1)), "baseline_bpm": 62.0},
        {"started": time.mktime((2026, 1, 20, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 70.0},
        {"started": time.mktime((2026, 6, 1, 10, 0, 0, 0, 0, -1)), "baseline_bpm": 65.0},
    ]
    by_day = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    assert len(by_day) == 3, "5.1. (x2), 20.1., 1.6. -> 3 dni"
    by_month = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_MONTH)
    assert len(by_month) == 2, "januar + jun"
    assert by_month[0]["count"] == 3 and by_month[1]["count"] == 1


def test_aggregate_by_period_skips_sessions_without_started():
    assert hr_stats.aggregate_by_period([{"baseline_bpm": 60.0}, "junk", None],
                                        hr_stats.PERIOD_WEEK) == []


def test_period_start_ts_week_is_a_monday_midnight():
    # Thursday 2026-01-15 15:30 -> Monday 2026-01-12 00:00
    thursday = time.mktime((2026, 1, 15, 15, 30, 0, 0, 0, -1))
    start = hr_stats.period_start_ts(hr_stats.PERIOD_WEEK, now=thursday)
    start_struct = time.localtime(start)
    assert start_struct.tm_wday == 0        # Monday
    assert (start_struct.tm_hour, start_struct.tm_min, start_struct.tm_sec) == (0, 0, 0)
    assert start <= thursday


def test_count_sessions_since_filters_and_sums_duration():
    sessions = [
        {"started": 100.0, "duration_s": 120.0},
        {"started": 200.0, "duration_s": 60.0},
        {"started": 50.0, "duration_s": 999.0},   # before the limit
        "junk",
    ]
    count, duration = hr_stats.count_sessions_since(sessions, since_ts=100.0)
    assert count == 2 and duration == 180.0


# --------------------------------------------------------------------------
# Time in bands - in seconds, not in samples
# --------------------------------------------------------------------------

def test_time_in_zones_counts_seconds_not_samples():
    critical = 110
    slow = _samples([60] * 60 + [130] * 60, step=1.0)            # 60 s calm, 60 s critical
    fast = _samples([60] * 120 + [130] * 120, step=0.5)          # the same at 2 Hz
    zs = hr_stats.time_in_zones(slow, critical, baseline=60)
    zf = hr_stats.time_in_zones(fast, critical, baseline=60)
    assert abs(zs[hr_stats.ZONE_CRITICAL] - 60) <= 1.5
    assert abs(zf[hr_stats.ZONE_CRITICAL] - 60) <= 1.5
    assert abs(zs[hr_stats.ZONE_CALM] - zf[hr_stats.ZONE_CALM]) <= 1.5


def test_live_zone_seconds_accumulate_in_seconds():
    slow = hr_stats.HeartStats(100)
    _feed(slow, [62] * 120 + [130] * 120, step=1.0)
    fast = hr_stats.HeartStats(100)
    _feed(fast, [62] * 240 + [130] * 240, step=0.5)
    total_slow = sum(slow.zone_seconds.values())
    total_fast = sum(fast.zone_seconds.values())
    assert abs(total_slow - total_fast) < 2.0
    assert slow.zone_seconds[hr_stats.ZONE_CRITICAL] + slow.zone_seconds[hr_stats.ZONE_HIGH] > 60


# --------------------------------------------------------------------------
# HRPI
# --------------------------------------------------------------------------

def test_hrpi_is_largest_k_with_bpm_at_least_k_for_k_seconds():
    # 120 BPM for 2 minutes -> k = 120 (120 s >= 120)
    assert hr_stats.persistence_index(_samples([120] * 121)) == 120
    # 120 BPM for only 91 s -> k is 91 (91 s at >= 91 BPM holds, 92 no longer)
    assert hr_stats.persistence_index(_samples([120] * 91)) == 91
    # 85 BPM for 3 hours -> 85
    assert hr_stats.persistence_index(_samples([85] * 3 * 3600)) == 85
    assert hr_stats.persistence_index([]) == 0


def test_hrpi_uses_time_not_sample_count():
    one_hz = hr_stats.persistence_index(_samples([100] * 100, step=1.0))
    two_hz = hr_stats.persistence_index(_samples([100] * 200, step=0.5))
    assert one_hz == two_hz == 100


# --------------------------------------------------------------------------
# History analysis
# --------------------------------------------------------------------------

def _session(started, duration_s=3600, baseline=62, hrr=18, triggers=(), over=0):
    return {"started": started, "duration_s": duration_s, "samples": duration_s,
            "baseline_bpm": baseline, "hrr_bpm": hrr, "avg_bpm": baseline + 15,
            "min_bpm": baseline - 2, "max_bpm": 140, "time_over_s": over,
            "trigger_offsets_s": list(triggers), "triggers": len(triggers),
            "peak_stress": 60}


def test_analysis_survives_empty_and_single_history():
    assert hr_insights.analyze([]) [0]["key"] == "need_more"
    assert hr_insights.analyze(None)[0]["key"] == "need_more"
    one = hr_insights.analyze([_session(1000)])
    assert one[0]["key"] == "need_more" and one[0]["params"]["n"] == 1
    # broken records are ignored, it does not crash
    assert hr_insights.analyze([None, "x", {"duration_s": "abc"}])[0]["key"] == "need_more"


def test_analysis_detects_rising_resting_baseline():
    now = 20 * 86400.0
    prev = [_session(now - 12 * 86400 + i * 3600, baseline=60) for i in range(3)]
    recent = [_session(now - 2 * 86400 + i * 3600, baseline=67) for i in range(3)]
    keys = [i["key"] for i in hr_insights.analyze(prev + recent, now=now)]
    assert "resting_up" in keys and "steady" not in keys


def test_analysis_detects_improving_hrr():
    now = 20 * 86400.0
    prev = [_session(now - 12 * 86400 + i * 3600, hrr=14) for i in range(3)]
    recent = [_session(now - 2 * 86400 + i * 3600, hrr=24) for i in range(3)]
    out = hr_insights.analyze(prev + recent, now=now)
    hrr = next(i for i in out if i["key"] == "hrr_up")
    assert hrr["tone"] == hr_insights.TONE_GOOD and hrr["params"]["delta"] == 10


def test_analysis_flags_late_triggers_in_long_sessions():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=3 * 3600,
                         triggers=(8000, 8500, 9000)) for i in range(3)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert "triggers_late" in keys


# --------------------------------------------------------------------------
# When triggers come - density, not share (B3a)
#
# In a 90-min session the first hour is two thirds of the time, so even
# evenly spread triggers gave ~67 % "in the first hour" and the old 66 %
# threshold reported a pattern that was not there. The same for "after
# two hours" in 4-5 h sessions.
# --------------------------------------------------------------------------

def _timing_keys(duration_s, triggers, n=3):
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=duration_s, triggers=triggers)
                for i in range(n)]
    return {i["key"]: i for i in hr_insights.analyze(sessions, now=now)}


def test_even_triggers_in_90min_sessions_are_not_early():
    # every 15 min, in the middle of a stretch: 4 in the first hour, 2 after
    # it = 67 %, but the density is the same everywhere
    out = _timing_keys(90 * 60, (450, 1350, 2250, 3150, 4050, 4950))
    assert "triggers_early" not in out and "triggers_late" not in out


def test_front_loaded_triggers_are_early():
    out = _timing_keys(90 * 60, (300, 1200, 2100, 3000))
    assert out["triggers_early"]["params"]["share"] == 100
    assert out["triggers_early"]["tone"] == hr_insights.TONE_INFO


def test_front_loading_is_seen_even_below_two_thirds_in_long_sessions():
    # 3 h: the first hour 3 triggers, the next two hours 2 - share only 60 %,
    # but the first hour is 3x denser. The old share missed that.
    out = _timing_keys(3 * 3600, (600, 1500, 2400, 5000, 9000), n=4)
    assert out["triggers_early"]["params"]["share"] == 60


def test_few_front_loaded_triggers_stay_quiet():
    # 6 of 6 in the first hour of a 90-min session - with an even spread this
    # comes out by chance in almost every tenth case (2/3)^6 = 8.8 %
    out = _timing_keys(90 * 60, (900, 2700))
    assert "triggers_early" not in out


def test_even_triggers_in_5h_sessions_are_not_late():
    # every 30 min: 6 of 10 only after two hours (60 % > old threshold 50 %),
    # but those hours are also 60 % of the time - nothing gets denser late
    out = _timing_keys(5 * 3600, tuple(900 + 1800 * k for k in range(10)))
    assert "triggers_late" not in out and "triggers_early" not in out


def test_timing_survives_years_of_history_and_broken_duration():
    # 300 sessions = 1500 triggers: naive math.comb(1500, k) * float overflows
    now = 400 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=90 * 60,
                         triggers=(300, 1200, 2100, 3000, 4000)) for i in range(300)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert "triggers_early" in keys
    # an infinite duration (broken JSON) must not crash the background analysis
    broken = [_session(now - i * 86400, duration_s=90 * 60, triggers=(300, 1200))
              for i in range(3)]
    broken.append(dict(broken[0], duration_s=float("inf"), started=now - 5 * 86400))
    hr_insights.analyze(broken, now=now)


def _even(duration_s, n):
    # n triggers, each in the middle of an equal stretch - perfectly even
    return tuple(duration_s * (i + 0.5) / n for i in range(n))


def _mixed_keys(parts):
    now = 30 * 86400.0
    sessions, i = [], 0
    for count, duration_s, triggers in parts:
        for _ in range(count):
            sessions.append(_session(now - i * 86400, duration_s=duration_s,
                                     triggers=triggers))
            i += 1
    return {x["key"] for x in hr_insights.analyze(sessions, now=now)}


def test_tense_short_evenings_next_to_calm_long_ones_are_not_early():
    # In EVERY session the triggers are even. Only the short evenings are
    # tense, the long ones are calm - summed time would turn that into "the
    # first hour is denser" (Simpson). The per-session expectation must not.
    keys = _mixed_keys([(3, 90 * 60, _even(90 * 60, 7)),
                        (4, 5 * 3600, _even(5 * 3600, 5))])
    assert "triggers_early" not in keys


def test_tense_long_evenings_next_to_calm_ones_are_not_late():
    # two tense 5-h sessions (2/h evenly) + six calm 150-min ones without a
    # trigger: nothing came "only after two hours", just the long evenings
    # were tense from the start
    keys = _mixed_keys([(2, 5 * 3600, _even(5 * 3600, 10)),
                        (6, 150 * 60, ())])
    assert "triggers_late" not in keys


def test_one_broken_duration_does_not_silence_timing_forever():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400, duration_s=90 * 60,
                         triggers=(300, 1200, 2100, 3000)) for i in range(3)]
    for bad in (float("nan"), float("inf")):
        broken = sessions + [dict(sessions[0], duration_s=bad, started=now - 5 * 86400)]
        keys = {x["key"] for x in hr_insights.analyze(broken, now=now)}
        assert "triggers_early" in keys


def test_analysis_reports_steady_when_nothing_stands_out():
    now = 10 * 86400.0
    sessions = [_session(now - i * 86400) for i in range(4)]
    keys = [i["key"] for i in hr_insights.analyze(sessions, now=now)]
    assert keys == ["steady"]


def test_insights_save_and_load(tmp_path):
    path = str(tmp_path / "hr_insights.json")
    assert hr_insights.save_insights(path, [{"key": "steady", "tone": "good", "params": {}}])
    loaded = hr_insights.load_insights(path)
    assert loaded["insights"][0]["key"] == "steady" and loaded["computed_at"]
    assert hr_insights.load_insights(str(tmp_path / "nope.json"))["insights"] == []


# --------------------------------------------------------------------------
# netinfo
# --------------------------------------------------------------------------

def test_local_ip_candidates_are_real_ipv4_without_loopback():
    import ipaddress
    cands = netinfo.local_ip_candidates()
    for ip in cands:
        addr = ipaddress.IPv4Address(ip)
        assert not addr.is_loopback and not addr.is_link_local
    assert len(cands) == len(set(cands)), "bez duplicit"
    preferred = netinfo.preferred_local_ip()
    if preferred:
        assert cands[0] == preferred, "preferovana adresa musi byt prva"


# --------------------------------------------------------------------------
# Recommendations about silence (18. 9.)
#
# The only insights that tell the player WHAT TO DO. That is why they rest
# on hard numbers from the trigger, not on an impression from heart rate —
# and why it matters that they do not hit the wrong cause: the advice
# "speak up more often" with a watch that keeps dropping out would send
# them to tune the threshold instead of the connection.
# --------------------------------------------------------------------------

def _relacia(**kw):
    zaklad = {"started": 1789000000.0, "duration_s": 2400.0, "samples": 900,
              "baseline_bpm": 70, "auto_triggers": 0, "above_runs": 0,
              "longest_above_s": 0.0, "runs_cancelled_gap": 0,
              "stress_hold_s": 45.0}
    zaklad.update(kw)
    return zaklad


def _kluce(relacie):
    return {i["key"] for i in hr_insights.analyze(relacie, now=1789200000.0)}


def test_vypadky_maju_prednost_pred_ladenim():
    """With dropouts, the "longest stretch" is chopped up by gaps in the
    data, not by physiology. Advising by it would send the player to fix
    the wrong thing."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=9, longest_above_s=11.0,
                        runs_cancelled_gap=8) for i in range(4)]
    kluce = _kluce(relacie)
    assert "cue_dropouts" in kluce
    assert "cue_almost" not in kluce and "cue_far" not in kluce


def test_telo_sa_ani_raz_nedostalo_hore():
    """Policy will not help — the heart-rate limit is set too high."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0) for i in range(4)]
    assert "cue_never_above" in _kluce(relacie)


def test_tesne_vedla_radi_zmenu_politiky():
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=5, longest_above_s=38.0) for i in range(4)]
    assert "cue_almost" in _kluce(relacie)


def test_hlboko_pod_radi_hranicu_tepu():
    """The body goes up and down faster than the app waits — shortening the
    wait is not enough here and the advice must say so."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0) for i in range(4)]
    kluce = _kluce(relacie)
    assert "cue_far" in kluce and "cue_almost" not in kluce


def test_zadrzane_hlasky_netvrdia_ze_zataz_nevydrzala():
    """0.2 (stress-gate): the trigger armed and the app itself stayed silent.
    So the load did stay up — "only briefly" would lie, and "I didn't
    notice anything" too. Better no advice."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0,
                        cues_withheld={"bez_pauzy": 0, "nevhodna_chvila": 2,
                                       "nedalo_sa": 0})
               for i in range(4)]
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_almost", "cue_far", "steady"})
    # a broken value does not crash the analysis and pretends nothing
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        above_runs=6, longest_above_s=9.0,
                        cues_withheld={"nevhodna_chvila": "x"})
               for i in range(4)]
    assert "cue_far" in _kluce(relacie)


def test_ked_hlasky_chodia_sa_nerieskuje_nic():
    """No silence recommendation for an evening in which the app spoke."""
    relacie = [_relacia(started=1789000000.0 + i * 86400.0,
                        auto_triggers=4, above_runs=6, longest_above_s=60.0)
               for i in range(4)]
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_never_above", "cue_almost", "cue_far"})


def test_stare_relacie_bez_pocitadiel_neradia_nic():
    """Sessions saved before 17. 9. do not have those numbers. Advising from
    missing data would mean guessing."""
    relacie = []
    for i in range(4):
        r = _relacia(started=1789000000.0 + i * 86400.0)
        for k in ("above_runs", "longest_above_s", "runs_cancelled_gap",
                  "stress_hold_s"):
            del r[k]
        relacie.append(r)
    kluce = _kluce(relacie)
    assert not (kluce & {"cue_dropouts", "cue_never_above", "cue_almost", "cue_far"})


def test_kroky_su_rozdiel_nie_kumulativny_sucet():
    """The watch sends a daily total — that says nothing about movement NOW."""
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(4):
        st.note_metrics(steps=1000, ts=t + i * 1.5)
    assert st.steps_per_min(now=t + 5) == 0.0, "stojaci počet = sedí"

    t2 = t + 10
    for i, spolu in enumerate(range(1000, 1090, 10)):
        st.note_metrics(steps=spolu, ts=t2 + i * 1.5)
    assert 70 <= st.steps_per_min(now=t2 + 13) <= 90


def test_bez_krokov_je_to_nevieme_nie_nula():
    """"We don't know" and "zero steps" are two different things.

    Swapping them would mean claiming the player is sitting whenever the
    watch does not send steps — and window exclusion is supposed to rest
    exactly on that.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.steps_per_min(now=1000.0) is None
    st.note_metrics(speed=0.0, ts=1000.0)
    assert st.steps_per_min(now=1000.0) is None, "rychlost nie je pocet krokov"


def test_restart_pocitadla_na_hodinkach_nevyrobi_kroky():
    """At midnight (or on a watch app restart) the total drops to zero.

    A negative difference must be thrown away — otherwise it would turn
    into a huge negative increment or, with a naive abs(), a fake batch of
    steps.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    st.note_metrics(steps=9000, ts=t)
    st.note_metrics(steps=5, ts=t + 1.5)
    assert st.steps_per_min(now=t + 2) == 0.0


def test_appka_mlci_kym_chodia_kroky():
    """Heart rate can't be told from movement, so no speaking up while walking.

    Uendes et al. (2026, JMIR, N=127): a model with 55 ECG features has, at
    moderate physical activity, a specificity of 0.418 — it marks almost
    six of ten walking windows as stress. One BPM every 1.5 s cannot manage
    that.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._cue_can_fire)
    assert "steps_per_min" in telo, "brana na pohyb chyba"
    assert "KROKY_PRAH_ZA_MIN" in telo
    # `None` (the watch does not send steps) must not silence the app
    assert "kroky is not None" in telo, "neznalost by umlcala appku"


def test_pokazena_relacia_sa_pozna_podla_nemoznych_skokov():
    """Heart rate does not move by 30 bpm between two samples (~1.5 s).

    On 19. 9. this was caused by a parser that, after steps and speed were
    added to the watch message, read heart rate one time and the step count
    another. The result was a 52-minute session with an average of 124 and
    a maximum of 235 — and that would otherwise have permanently skewed both
    the baseline and the computed limit.
    """
    zdrava = {"curve": [78, 80, 79, 82, 85, 83, 81, 79, 80, 84, 82, 80]}
    assert not hr_stats.je_podozriva(zdrava)

    pokazena = {"curve": [135, 69, 135, 145, 79, 145, 145, 91, 145, 182, 111, 182]}
    assert hr_stats.je_podozriva(pokazena)

    # too short a curve is not judged - better keep it than drop an innocent
    assert not hr_stats.je_podozriva({"curve": [80, 120]})


def test_podozriva_relacia_neurcuje_zakladnu_ani_hranicu():
    # `duration_s` since 0.2.1: the critical heart rate is learned only from
    # sessions of at least 5 min (`je_dost_dlha`) - without it both sides
    # would end up on the fallback and the equality below would measure
    # nothing.
    zdrave = [{"curve": [78, 80, 79, 82, 81, 80, 79, 83, 82, 80] * 30,
               "baseline_bpm": 78, "duration_s": 1800.0} for _ in range(4)]
    pokazena = {"curve": [135, 69, 135, 145, 79, 145, 182, 91, 222, 111] * 30,
                "baseline_bpm": 135, "duration_s": 1800.0}
    assert hr_stats.dlhodoba_zakladna(zdrave + [pokazena]) == \
        hr_stats.dlhodoba_zakladna(zdrave)
    assert hr_stats.dynamicky_kriticky(zdrave) != hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(zdrave + [pokazena]) == \
        hr_stats.dynamicky_kriticky(zdrave)


def test_kriticky_tep_bez_dat_padne_na_zalohu():
    """Until there's data to compute from, no claiming a computed number."""
    assert hr_stats.dynamicky_kriticky([]) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(
        [{"curve": [80] * 120}]) == hr_stats.KRITICKY_ZALOHA


def test_kriticky_tep_nesmie_sadnut_na_zakladnu():
    """Headroom must not be merely nominal.

    `headroom = max(12, kritický − základňa)`. If the computed limit sat
    just above the baseline, load would be scaled over a few beats and the
    app would react to noise.
    """
    # `duration_s` since 0.2.1 (a session of at least 5 min) - otherwise the
    # fallback 110 and the test would pass without the safety net ever being
    # tried.
    pokojne = [{"curve": [70] * 120, "baseline_bpm": 69, "duration_s": 600.0}
               for _ in range(4)]
    h = hr_stats.dynamicky_kriticky(pokojne, baseline=69)
    assert h != hr_stats.KRITICKY_ZALOHA
    assert h >= 69 + hr_stats.KRITICKY_MIN_NAD_ZAKLADNOU


def test_kriticky_tep_uz_nie_je_nastavenie():
    """The "Heart rate at which to help" field is gone from the system.

    It could not be set well: with a baseline of 77, anything up to 89 gave
    the same result (headroom floor 12), so the player moved the number and
    nothing changed — and at the same time it turned a calm evening into
    52 % of the time in the red.
    """
    from _zdroj_appky import zdroj_appky
    zdroj = zdroj_appky()
    assert "hr_critical_bpm_var" not in zdroj, "policko sa vratilo"
    assert '"hr_critical_bpm": int(self.hr_critical_bpm)' not in zdroj, \
        "hodnota sa stale uklada ako nastavenie"
    assert "hr_stats.dynamicky_kriticky(" in zdroj, "nic to nepocita"


def test_krivka_aktivity_rozlisi_hru_menu_a_odchod():
    """Estimating "when there was real play" without reading the game.

    Overwolf would tell it precisely (`scene`), but it is a dead end —
    unusable licence-wise and technically an injector. What remains is the
    input density from `GetLastInputInfo`, which the app measures anyway.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(60):                      # game: input almost constantly
        st.note_activity(True, ts=t + i)
    for i in range(60):                      # menu: an occasional click
        st.note_activity(i % 6 == 0, ts=t + 60 + i)
    for i in range(60):                      # away from the PC
        st.note_activity(False, ts=t + 120 + i)

    k = st.activity_trace(points=12)
    assert len(k) == 12
    hra = sum(k[0:4]) / 4
    menu = sum(k[4:8]) / 4
    prec = sum(k[8:12]) / 4
    assert hra > 0.9 and menu < 0.4 and prec == 0.0, (hra, menu, prec)


def test_krivka_aktivity_je_podiel_nie_okamih():
    """A curve point is the SHARE of activity in a stretch, not an instant.

    Otherwise it would be random noise of ones and zeros instead of what we
    care about: how densely the game was played.
    """
    st = hr_stats.HeartStats(critical_bpm=110)
    t = 1000.0
    for i in range(100):
        st.note_activity(i % 2 == 0, ts=t + i)   # exactly half
    k = st.activity_trace(points=5)
    assert all(0.3 <= b <= 0.7 for b in k), k


def test_bez_vzoriek_je_krivka_prazdna():
    """No data is not the same as zero activity."""
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.activity_trace() == []


# --------------------------------------------------------------------------
# Poisoning of calibration by broken / foreign data (B8–B12)
# --------------------------------------------------------------------------

def test_pokazena_relacia_bez_krivky_je_podozriva():
    """B11/B12: an impossible maximum (steps read as heart rate) must be
    caught even when the curve is missing or downsampling smoothed it out.
    `max_bpm` comes from the raw ones."""
    assert hr_stats.je_podozriva({"max_bpm": 235, "avg_bpm": 124}) is True
    assert hr_stats.je_podozriva(
        {"max_bpm": 235, "avg_bpm": 124, "curve": [120] * 600}) is True
    # a healthy session (even an intense one) passes
    assert hr_stats.je_podozriva(
        {"max_bpm": 165, "avg_bpm": 100,
         "curve": [90 + i % 20 for i in range(600)]}) is False


def test_importovana_relacia_sa_nezapocita_do_kalibracie():
    """B10: a foreign body must not set the baseline or the thresholds."""
    vlastna = {"curve": [90] * 600, "baseline_bpm": 72, "max_bpm": 150,
               "avg_bpm": 95, "duration_s": 1800}
    cudzia = dict(vlastna, imported=True, baseline_bpm=55)
    assert cudzia not in hr_stats.ciste_relacie([vlastna, cudzia])
    assert len(hr_stats.ciste_relacie([vlastna, cudzia])) == 1


def test_kriticky_tep_ma_strop():
    """B9: one nonsensical curve must not push the critical threshold out of
    reach and silence the app. `dynamicky_prah_zataze` has a cap, this one
    must have one too."""
    nezmysel = [{"curve": [235] * 600, "baseline_bpm": 70, "max_bpm": 180,
                 "avg_bpm": 160, "duration_s": 1800} for _ in range(3)]
    h = hr_stats.dynamicky_kriticky(nezmysel, baseline=70)
    assert h <= hr_stats.KRITICKY_STROP[1]


def test_hr_insights_filtruje_pokazene_relacie():
    """B8: a broken session must not produce false advice."""
    import hr_insights
    zdrave = [{"started": 1000.0 + i, "duration_s": 1800, "samples": 500,
               "baseline_bpm": 72, "max_bpm": 150, "avg_bpm": 95,
               "curve": [90] * 600} for i in range(4)]
    pokazena = {"started": 9000.0, "duration_s": 1800, "samples": 500,
                "baseline_bpm": 135, "max_bpm": 235, "avg_bpm": 160,
                "curve": [235] * 600}
    # analysis with and without the broken one is the same — it added nothing
    assert hr_insights.analyze(zdrave + [pokazena]) == hr_insights.analyze(zdrave)


# --------------------------------------------------------------------------
# Signal coverage (C4): the threshold learns only from time with heart rate
# --------------------------------------------------------------------------

_ZONY_1800 = {"calm": 900.0, "raised": 600.0, "high": 300.0, "critical": 0.0}


def _vlna(hore, opakovani=60):
    """Smooth body-like curve - no jumps that `je_podozriva` would catch."""
    vlna = []
    for _ in range(opakovani):
        vlna.extend(range(70, hore, 5))
        vlna.extend(range(hore, 70, -5))
    return vlna


def test_pokrytie_signalu_z_ulozenych_poli():
    """Sum of bands / duration - from what every summary already stores."""
    p = hr_stats.pokrytie_signalu(
        {"duration_s": 1000.0,
         "zone_seconds": {"calm": 600.0, "raised": 200.0, "high": 100.0,
                          "critical": 0.0}})
    assert abs(p - 0.9) < 1e-9
    # rounding in the summary can give a hair more than the duration - cap is 1
    assert hr_stats.pokrytie_signalu(
        {"duration_s": 100.0, "zone_seconds": {"calm": 100.4}}) == 1.0


def test_pokrytie_signalu_ked_sa_to_nevie_je_none():
    """Not knowing is not "0 %": old sessions, broken files and watches that
    sent less often than every 12 s (every gap a dropout, sum zero)."""
    zony = {"calm": 500.0}
    for relacia in (
            {"duration_s": 1000.0},                              # old
            {"duration_s": 1000.0, "zone_seconds": {}},
            {"duration_s": 1000.0, "zone_seconds": None},
            {"duration_s": 0, "zone_seconds": zony},
            {"duration_s": -5.0, "zone_seconds": zony},
            {"zone_seconds": zony},                              # without duration
            {"duration_s": 1000.0, "zone_seconds": {"calm": 0.0}},
            {"duration_s": 1000.0, "zone_seconds": {"calm": "x"}},
            {"duration_s": 1000.0, "zone_seconds": {"calm": None}},
            {"duration_s": 1000.0, "zone_seconds": [1, 2, 3]},
            {"duration_s": "dlho", "zone_seconds": zony},
            {"duration_s": float("nan"), "zone_seconds": zony},
            {"duration_s": 1000.0, "zone_seconds": {"calm": float("nan")}},
            None, "relacia", 42, []):
        assert hr_stats.pokrytie_signalu(relacia) is None, relacia


def test_prehravanie_prahu_nevazi_vecer_podla_dier():
    """The curve is thinned by samples, not by time - it has no gaps.

    The same evening with a double `duration_s` (half the time the watch
    was silent) and the same sum of bands must be replayed the same way -
    the same number of points, the same 80th percentile. Before, it was
    stretched over the whole time and weighed twice as much in the
    threshold.
    """
    celistvy = {"curve": _vlna(130), "duration_s": 1800.0,
                "zone_seconds": dict(_ZONY_1800)}
    dierava = dict(celistvy, duration_s=3600.0)
    assert hr_stats.pokrytie_signalu(dierava) == 0.5
    a = hr_stats.load_z_krivky(celistvy, 70.0, 110)
    b = hr_stats.load_z_krivky(dierava, 70.0, 110)
    assert a and abs(len(a) - len(b)) <= 1
    assert hr_stats._percentile(sorted(a), 0.8) == \
        hr_stats._percentile(sorted(b), 0.8)
    # no bands (old session): stretched over the whole duration as before
    stara = {k: v for k, v in dierava.items() if k != "zone_seconds"}
    assert len(hr_stats.load_z_krivky(stara, 70.0, 110)) > 1.9 * len(a)


def test_relacia_bez_pokrytia_sa_prehra_ako_doteraz():
    """Without bands, with a zero sum, with full coverage - as before C4."""
    krivka = [70 + (i % 20) for i in range(600)]
    bez = {"curve": krivka, "duration_s": 600.0}
    ocakavane = hr_stats.load_z_krivky(bez, 65.0, 110)
    assert len(ocakavane) == int(600.0 / 1.5) - 29   # like the calibration test
    for zony in ({"calm": 0.0, "raised": 0.0}, {"calm": 400.0, "raised": 200.0},
                 {"calm": 700.0}):
        assert hr_stats.load_z_krivky(
            dict(bez, zone_seconds=zony), 65.0, 110) == ocakavane, zony


def test_do_prahu_patri_ta_ista_relacia_aj_s_malym_pokrytim():
    """The "at least 5 minutes" condition stays on `duration_s` - which
    sessions count towards the threshold (and towards "computed from n
    sessions") does not change."""
    relacia = {"curve": [70 + (i % 20) for i in range(600)], "duration_s": 600.0,
               "zone_seconds": {"calm": 180.0}}             # coverage 0.3
    body = hr_stats.load_z_krivky(relacia, 65.0, 110)
    assert len(body) == int(180.0 / 1.5) - 29


def test_dierava_relacia_neposunie_prah_viac_nez_celistva():
    """An evening with gaps weighs the same in the threshold as without them.

    Before C4 its curve was stretched over the gaps too, so it put twice as
    many points into the 80th percentile as its unbroken twin and shifted
    the threshold (here 76 -> 78).
    """
    zdrave = [{"curve": _vlna(110), "duration_s": 1800.0, "baseline_bpm": 70,
               "zone_seconds": dict(_ZONY_1800)} for _ in range(4)]
    dierava = {"curve": _vlna(140), "duration_s": 3600.0, "baseline_bpm": 70,
               "zone_seconds": dict(_ZONY_1800)}
    dvojca = dict(dierava, duration_s=1800.0)
    assert not hr_stats.je_podozriva(dierava)
    s_dierami = hr_stats.dynamicky_prah_zataze(
        zdrave + [dierava], baseline=70, critical=110)
    assert s_dierami is not None
    assert s_dierami == hr_stats.dynamicky_prah_zataze(
        zdrave + [dvojca], baseline=70, critical=110)
    # check that the test measures something: stretched over the gaps, it
    # would shift the threshold
    natiahnuta = {k: v for k, v in dierava.items() if k != "zone_seconds"}
    assert hr_stats.dynamicky_prah_zataze(
        zdrave + [natiahnuta], baseline=70, critical=110) != s_dierami


def test_brana_na_pokrytie_zamerne_nie_je():
    """An evening with low coverage is NOT excluded from learning (C4, see the
    comment at `pokrytie_signalu`): the ratio drops also with a sleeping PC
    or the watch on the charger, and those evenings have good data. Whoever
    builds the gate changes this test knowingly - and with data from a
    real bad evening."""
    slaba = {"curve": [80 + i % 5 for i in range(600)], "duration_s": 3600.0,
             "max_bpm": 90, "zone_seconds": {"calm": 700.0}}   # coverage ~0.19
    assert hr_stats.pokrytie_signalu(slaba) < 0.5
    assert hr_stats.ciste_relacie([slaba]) == [slaba]


# --------------------------------------------------------------------------
# Live coverage for the signal quality widget
# --------------------------------------------------------------------------

def test_zive_pokrytie_je_none_kym_nie_je_z_coho():
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.signal_coverage_at(now=5000.0) is None          # no sample
    koniec = _feed(st, [75] * 30, start=1000.0)
    assert st.signal_coverage_at(now=koniec) is None           # 30 s < a minute
    assert st.signal_coverage_at(now=1000.0 + 59.9) is None
    assert st.signal_coverage_at(now=1000.0 + 60.0) is not None


def test_zive_pokrytie_nekolise_medzi_vzorkami():
    """The watch sends every ~3 s. Between two samples the number must not
    drop and jump back at the next - the open interval is counted (at most
    5 s)."""
    st = hr_stats.HeartStats(critical_bpm=110)
    koniec = _feed(st, [75] * 40, start=1000.0, step=3.0)    # the last one 1117
    posledna = koniec - 3.0
    for po in (0.0, 1.0, 2.9, 4.99):
        assert abs(st.signal_coverage_at(now=posledna + po) - 1.0) < 1e-9, po
    # after 5 s of silence no more time with signal (same cap as `add`)
    pokr = st.signal_coverage_at(now=posledna + 8.0)
    assert abs(pokr - (117.0 + 5.0) / 125.0) < 1e-9


def test_zive_pokrytie_meria_od_prvej_vzorky_nie_od_zapnutia():
    """Waiting for the watch to connect is not a weak signal."""
    st = hr_stats.HeartStats(critical_bpm=110)
    st.session_start = 0.0                     # session opened long before
    koniec = _feed(st, [75] * 120, start=1000.0)
    assert abs(st.signal_coverage_at(now=koniec - 0.5) - 1.0) < 1e-9


def test_zive_pokrytie_sedi_s_vypadkom_a_je_vedla_neho():
    """Dropout: coverage drops by exactly the blind time and the widget also
    has the number of dropouts (`dropouts`) and blind seconds
    (`blind_seconds`) next to it."""
    st = hr_stats.HeartStats(critical_bpm=110)
    _feed(st, [75] * 60, start=1000.0)                       # 1000..1059
    st.note_dropout(od=1059.0)
    st.clear_live()
    # during a dropout there is no open interval - heart rate is not coming
    pocas = st.signal_coverage_at(now=1080.0)
    assert abs(pocas - 59.0 / 80.0) < 1e-9
    _feed(st, [75] * 60, start=1090.0)                       # 1090..1149
    teraz = 1149.5
    pokr = st.signal_coverage_at(now=teraz)
    assert st.dropouts == 1
    assert st.blind_seconds(now=teraz) == 31.0
    assert abs(pokr - (1.0 - 31.0 / (teraz - 1000.0))) < 1e-9


def test_zive_pokrytie_zarata_aj_sekundy_z_kalibracie():
    """First evening without a baseline: the seconds wait in `_zony_cakaju`
    until the baseline arrives - they too are time with signal."""
    st = hr_stats.HeartStats(critical_bpm=110)
    koniec = _feed(st, [75] * 25, start=1000.0, step=3.0)    # 1000..1072
    assert st.is_calibrating and st._zony_cakaju
    assert abs(st.signal_coverage_at(now=koniec - 2.0) - 1.0) < 1e-9


def test_zive_pokrytie_je_vlastnost_pre_widget_a_nuluje_sa_s_relaciou():
    st = hr_stats.HeartStats(critical_bpm=110)
    t0 = time.time() - 120.0
    _feed(st, [75] * 120, start=t0)
    pokr = st.signal_coverage
    assert pokr is not None and pokr > 0.95
    st.note_dropout()
    st.reset_session()
    assert st.signal_coverage is None
    assert st.dropouts == 0 and st.blind_seconds() == 0.0
