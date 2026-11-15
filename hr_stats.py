"""Heart rate statistics - resting baseline, load index, session progress.

What "load" is and what it is NOT
---------------------------------
Only one number comes from the watch: BPM, roughly once a second. That is
NOT HRV, and neither RMSSD nor SDNN can be computed from it - that needs the
distances between individual beats (R-R intervals), which the app does not
get. Anything called "HRV" here would be a made-up number.

That is why `stress` (in the UI "Záťaž", i.e. "Load") is computed as an
openly admitted compound of three things that CAN be found out FROM BPM:

  1. `over`      - how far the heart rate is above the player's own resting
                   baseline, scaled to their critical limit (55 % weight)
  2. `slope`     - how fast the heart rate is rising right now (20 %
                   weight); a sharp onset is what the player feels as "it
                   kicked in", even before the number is high
  3. `sustained` - how much of the last 2 minutes they spent above the
                   baseline (25 % weight); a short spike after a headshot
                   is not stress, two minutes at 120 BPM is

The result is smoothed with an exponential average so that the bar on the
HUD does not jump at every beat.

The baseline (`baseline`) is not a constant from the settings: it is taken
as the 20th percentile of the last ~10 minutes, i.e. "what heart rate this
player has when the game is not pushing them anywhere right now". Someone
with a resting heart rate of 52 and someone with 78 thus get comparable
results without having to set anything.

Metrics that CAN be computed from plain BPM (and are in the session summary)
----------------------------------------------------------------------------
  * HRR - Heart Rate Recovery: how much the heart rate dropped within 1 min
    after a peak. A standard clinical metric (Cleveland Clinic: normal 12-23
    BPM, trained 29+). Computed from the session's local peaks, the main
    number is the recovery after the HIGHEST peak (see heart_rate_recovery).
  * baseline_bpm - resting baseline of the WHOLE session (20th percentile),
    so that a trend across sessions can be watched (a baseline rising day
    after day = fatigue/stress, not necessarily from gaming).
  * zone_seconds - time in the calm/raised/high/critical zones, in SECONDS
    (not in samples - the same trap as time_over).
  * HRPI - Heart Rate Persistence Index: the largest k for which the heart
    rate was at least k BPM for at least k SECONDS (cumulative). Analogous
    to the h-index: combines height and duration into one number (see
    persistence_index).
None of this is HRV and none of this is a diagnosis.
"""

import json
import os
import shutil
import time
from collections import deque
from datetime import datetime, timedelta

# os.replace that survives a short file lock on Windows (antivirus,
# indexing). `paths` does not pull in any app module - no cycle.
from paths import nahrad_subor

HISTORY_SECONDS = 180.0        # what we keep for the HUD curve
BASELINE_SECONDS = 600.0       # what the resting baseline is computed from
# The shape of the WHOLE session, stored in the summary.
#
# 120 -> 600. For a 15-minute session that is one point per 1.5 s instead
# of 7.4 s, i.e. roughly the real density of samples from the watch. Lower
# resolution meant that the question "why didn't it speak up then" could
# not be answered afterwards - interpolation from 120 points makes up a
# smoothness that was not there, and it leads to a different conclusion
# than the real course.
#
# The cost is a few kilobytes per session. Being able to recompute your own
# settings from your own data is worth it.
CURVE_POINTS = 600
SLOPE_WINDOW_S = 20.0
SUSTAINED_WINDOW_S = 120.0

SMOOTHING = 0.25               # weight of the new value when smoothing

ZONE_CALM = "calm"
ZONE_RAISED = "raised"
ZONE_HIGH = "high"
ZONE_CRITICAL = "critical"

# From how many of the latest heart rate samples the median is taken for
# the LIVE zone word (`HeartStats.zone`). A single sample would flip between
# two words and colours when the heart rate is at the edge of a zone; five,
# at the watch's cadence (~0.9 to ~2.9 s per sample), is roughly 5 to 15
# seconds - still "now", but no longer noise.
ZONE_MEDIAN_SAMPLES = 5

# THE HEART RATE NUMBER ON SCREEN (0.3) is the median of the samples from
# the last that many seconds, not the last raw value. Screen only - every
# sample goes into the measurement (`add`, load, zones, session summary)
# as before.
#
# Why: the app on the watch can write TWO different heart rates into one
# source (on the author's setup ~2 messages per second, one stream 5-10 BPM
# lower than the other), and the number then jumped up and down by those
# 5-10 BPM within the same second.
# Why 3 s: the sensor changes roughly once a second, so the window holds ~3
# readings of one stream - the median throws away one stray value. With two
# streams (~6 values in the window, half and half) it falls between them and
# does not jump. The number lags behind a real rise in heart rate by roughly
# a second (two of three readings must be new), less than the zone word
# (median of 5 samples, 5 to 15 s) - so the number and the colour do not
# drift apart. A longer window would already show as a delay on a sharp
# heart rate onset.
ZOBRAZ_OKNO_S = 3.0
# Cap on samples in the window - 3 s won't hold more even at 10 messages/s.
ZOBRAZ_MAX_VZORIEK = 32


def zone_for(stress):
    """FIXED LOAD zones (25/50/75) - now only for `time_high_s`.

    The zone word and colour the player sees (HUD, Today, heart rate
    indicator) have NOT been computed from here since 0.2, but from the
    heart rate relative to their resting level (`HeartStats.zone`,
    `zone_of_bpm`). This stays here because `time_high_s` is a stored
    metric and has to mean the same as in older sessions (see
    `HeartStats.add`).
    """
    if stress >= 75:
        return ZONE_CRITICAL
    if stress >= 50:
        return ZONE_HIGH
    if stress >= 25:
        return ZONE_RAISED
    return ZONE_CALM


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * pct))
    return ordered[max(0, min(len(ordered) - 1, idx))]


# --------------------------------------------------------------------------
# Pure computations over [(timestamp, bpm)] - stateless, directly testable
# --------------------------------------------------------------------------

MAX_SAMPLE_GAP_S = 5.0         # longer gap = dropout, time is not credited


def _durations(samples):
    """How many seconds each sample "counts" - until the next sample, max 5 s.
    The last sample gets the typical interval (median), so it is not zero."""
    n = len(samples)
    if n == 0:
        return []
    gaps = []
    for i in range(n - 1):
        gaps.append(max(0.0, min(MAX_SAMPLE_GAP_S, samples[i + 1][0] - samples[i][0])))
    last = sorted(gaps)[len(gaps) // 2] if gaps else 1.0
    gaps.append(min(MAX_SAMPLE_GAP_S, max(0.0, last)) or 1.0)
    return gaps


def kadencia_vzoriek(samples):
    """How often the watch sent heart rate - three summary numbers, no curve.

    WHY
    The cue trigger tells a sparser cadence apart from a dropout
    (`trigger.DIERA_S`), and that boundary rests on how often the watch really
    sends. Until now this could only be estimated afterwards from other
    counters. With these three numbers in the session summary it can be
    verified after a few evenings by measurement, not by a model: the
    median and the 90th percentile of the gap between samples, and the
    number of gaps over 5 s (the credit cap of `trigger.MAX_KROK_S` and
    `MAX_SAMPLE_GAP_S`).

    They are aggregates - neither timestamps nor a curve of the gaps are
    stored. Fewer than two samples: median and p90 are None, count 0.
    """
    medzery = [max(0.0, b[0] - a[0]) for a, b in zip(samples, samples[1:])]
    median = _percentile(medzery, 0.5)
    p90 = _percentile(medzery, 0.9)
    return {
        "sample_dt_median_s": round(median, 2) if median is not None else None,
        "sample_dt_p90_s": round(p90, 2) if p90 is not None else None,
        # 5.0 hard-coded, not a constant: it is the number in the key's name.
        "sample_gaps_over_5s": sum(1 for d in medzery if d > 5.0),
    }


def session_baseline(samples, min_samples=30):
    """Resting baseline of the whole session - 20th percentile of all samples.
    Below 30 samples None (the same threshold as the live baseline)."""
    values = [b for _, b in samples]
    if len(values) < min_samples:
        return None
    return _percentile(values, 0.20)


def downsample(values, points):
    """Evenly thins the list down to `points` values.

    Not truncation: truncating would turn a two-hour session into a curve
    of the last ten minutes. The same principle as `HeartStats.series`.
    """
    values = list(values)
    if points < 1 or len(values) <= points:
        return values
    step = len(values) / float(points)
    return [values[int(i * step)] for i in range(points)]


DLHODOBA_MIN_RELACII = 3       # fewer sessions = nothing to average
DLHODOBA_Z_RELACII = 20        # computed from this many latest sessions
DLHODOBA_PODLAHA = 40.0        # lower is not a resting heart rate but an error


# Share of physiologically impossible jumps above which a session is suspect.
#
# The heart rate does not move by 30 bpm between two neighbouring curve
# points. WARNING: the jumps are counted on `curve` (thinned to
# `CURVE_POINTS`), not on the raw samples. While a session has fewer than
# 600 samples, point = sample (watch cadence ~0.9 to ~2.9 s); a longer
# session has a point every duration/600 (2 h = 12 s). The 30 bpm limit
# does not scale with that. When this happens repeatedly, it is not the
# body being measured but something else - on 19. 9. it was the parser,
# which, after steps and speed were added to the message from the watch,
# sometimes read the heart rate and sometimes the step count. The result
# was a 52-minute session with an average of 124 and a maximum of 235.
#
# The 5 % limit is generously low: in 12 healthy sessions there were 0 % of
# such jumps, in the broken one 18 %. There is nothing in between.
PODOZRIVE_SKOKY = 0.05
NEMOZNY_SKOK_BPM = 30.0
# Above this value it is no longer a human heart rate but a misread number
# (steps). Deliberately high above the real maximum of even a young player,
# so that it does not catch a genuine spike - it catches a broken reading
# (max 235 from steps).
NEMOZNE_MAX_BPM = 220.0


def je_podozriva(session):
    """True when the session does not look like a human heart rate.

    It is not thrown away - it just does not count towards anything that
    draws conclusions from the data.
    """
    if not isinstance(session, dict):
        return True
    # INDEPENDENT OF THE CURVE: an impossible heart rate maximum = steps read
    # as heart rate (the broken session had avg 124, max 235). This also
    # catches a session WITHOUT a curve (B12) and one where downsampling
    # smoothed out the bpm/steps alternation (B11) - `curve` is thinned to 600
    # points, `max_bpm` is from the raw ones.
    try:
        mx = float(session.get("max_bpm") or 0)
    except (TypeError, ValueError):
        return True
    if mx > NEMOZNE_MAX_BPM:
        return True
    krivka = session.get("curve") or []
    if len(krivka) < 10:
        return False        # too short to judge, we leave it be
    try:
        skoky = [abs(float(krivka[i + 1]) - float(krivka[i]))
                 for i in range(len(krivka) - 1)]
    except (TypeError, ValueError):
        return True
    if not skoky:
        return False
    podiel = sum(1 for x in skoky if x > NEMOZNY_SKOK_BPM) / float(len(skoky))
    return podiel >= PODOZRIVE_SKOKY


def ciste_relacie(sessions):
    """Sessions it is OK to compute from: no suspect and no FOREIGN ones.

    Imported sessions (`imported`) are a foreign body - a different
    baseline, a different critical heart rate. `measure` and `hr_insights`
    already exclude them; `hr_stats` did not do it until now, so a single
    import of someone else's export shifted the player's baseline, critical
    heart rate and load threshold (B10).

    Since the research of 2026-09-22 CONFOUNDED sessions are excluded too
    (`je_confounded`: alcohol, illness, physical exertion right before
    playing) - otherwise one drunk evening gets into the long-term 20th
    percentile via the per-session baseline and skews dozens of clean
    sessions. Sessions are NOT DELETED, the app just does not learn from
    the skewed ones.

    RECOVERED SESSIONS (`recovered`, 0.3) do not count either -
    deliberately cautious. They are real evenings of the player, but the
    app did not close normally then (crash, Task Manager, power cut): they
    are missing the end since the last checkpoint (up to 5 minutes, often
    exactly the calming down after the game) and they never got the
    questionnaire, so they know nothing about the alcohol or illness that
    `je_confounded` excludes. So thresholds are not learned from them (no
    graduation either); in History and in the export they are like any other
    session. This happens only rarely - shutting Windows down saves the
    session normally (`app._pri_vypinani_windows`).

    APP SETUP (`setup`, 0.3) does not count either, for the same reason
    as the 110 -> 80 drop during pairing: introduction, pairing and the
    tour easily take more than 5 minutes, and they are minutes of calm at
    the desk, not playing. Such a session would pull both the threshold
    and the limit towards calm. The tag goes to the first saved session
    after the introduction (`app._relacia_nastavovania`) and to any
    session for which the player ticks "Just setting up the app" in the
    questionnaire (`attach_context`). It stays in History.
    """
    return [x for x in (sessions or [])
            if isinstance(x, dict) and not x.get("imported")
            and not x.get("recovered") and not x.get("setup")
            and not je_podozriva(x) and not je_confounded(x)]


def pokrytie_signalu(session):
    """Share of the session that really had heart rate: 0..1, None if unknown.

    `sum(zone_seconds) / duration_s`, at most 1. Every stored summary has
    both fields, so it can be computed afterwards too - no new field is
    stored.

    WHY THE SUM OF ZONES IS THE TIME WITH SIGNAL
    `HeartStats.add` credits to the zone the time since the previous
    sample, at most 5 s (`min(5.0, ...)`), and after a dropout `clear_live`
    throws away `_last_ts`, so the gap after a dropout adds nothing. A gap
    of 5 to 12 s is counted as 5 s: coverage is, if anything, slightly
    overestimated rather than underestimated.

    `duration_s` is wall-clock time since the session was opened, including
    waiting for the first sample. A short session therefore has lower
    coverage (in tests during development 0.79 to 0.96 at 1 to 1.5 min,
    long evenings 0.974 to 1.0).

    None when `zone_seconds` is missing or empty (old and imported
    sessions), when `duration_s <= 0`, on broken input - and when the sum
    of zones is zero. That is not an evening without heart rate (that one
    would have no curve), but a watch that sent less often than every 12 s:
    every gap was a dropout and credited nothing. The gauge does not know
    then, it is not "0 %".
    """
    try:
        trvanie = float(session.get("duration_s") or 0)
        zony = session.get("zone_seconds")
        if not zony:
            return None
        signal = sum(float(v) for v in zony.values())
    except (TypeError, ValueError, AttributeError):
        return None
    # The upper bound also catches NaN and infinity from a broken file.
    if not (0.0 < trvanie < float("inf") and 0.0 < signal < float("inf")):
        return None
    return min(1.0, signal / trvanie)


# COVERAGE GATE in `ciste_relacie` - weighed and DELIBERATELY NOT BUILT (C4).
#
# The candidate was "below 0.5 the app does not learn from the evening"
# (`je_slaby_signal`, next to `je_confounded`). It was not built because:
#   * after the fix to the replay in `load_z_krivky` no learning weights a
#     session by coverage anymore - the long-term baseline takes one
#     `baseline_bpm` per session, the critical heart rate at most
#     CURVE_POINTS curve points, and the threshold now replays only the
#     time with signal;
#   * the ratio also drops when the PC is asleep, the watch is on the
#     charger or the app is listening while you are away (a dropout does
#     not close the session) - such an evening has good data and the gate
#     would throw it away;
#   * on the test data (9 sessions) it would not exclude a single one;
#   * coverage can be computed from what every summary already stores, so
#     a gate added later takes effect on the whole history at once. Waiting
#     costs nothing.
# It makes sense to build it only once a real evening with coverage below
# 50 % turns up whose baseline or critical heart rate clearly deviates from
# the neighbouring evenings - i.e. the heart rate would drop out
# non-randomly (e.g. exactly during movement in tense moments), not just
# thin out.

# The live coverage (`HeartStats.signal_coverage`) returns a number only a
# minute after the FIRST SAMPLE (not after a minute of uninterrupted heart
# rate), until then None - the widget has to have its own state for that
# time. After 15 seconds a single 12-second gap would show 20 % - that is
# start-up noise, not the connection state.
POKRYTIE_ZIVE_MIN_S = 60.0


# --------------------------------------------------------------------------
# Critical heart rate: a computation, not a setting
# --------------------------------------------------------------------------

KRITICKY_PERCENTIL = 0.90      # "the top ten percent of your playing"
KRITICKY_MIN_RELACII = 3
KRITICKY_MIN_BODOV = 300
KRITICKY_Z_RELACII = 20
KRITICKY_ZALOHA = 110.0        # until there is something to compute from
KRITICKY_MIN_NAD_ZAKLADNOU = 20.0
KRITICKY_MIN_BOD, KRITICKY_MAX_BOD = 25.0, 250.0   # curve point outside = noise
KRITICKY_STROP = (80.0, 200.0)  # critical threshold kept in a sane range


def dynamicky_kriticky(sessions, baseline=None):
    """Critical heart rate computed from the player's own sessions.

    WHY IT IS NOT A SETTING
    It used to be one - and it could not be set well. The number enters the
    load formula as `headroom = max(12, kriticky - zakladna)`, so with a
    baseline of 77 anything up to 89 gives the same result (the floor of
    12) and the player has no way to find out that moving it from 80 to 90
    changes nothing. At the same time it defines the "critical" zone, so a
    value that is too low turns a calm evening into 52 % in the red.

    WHAT IS COMPUTED
    The 90th percentile of the merged curves of the last `KRITICKY_Z_RELACII`
    CLEAN sessions at least `PRAH_MIN_TRVANIE_S` long - i.e. "the heart rate
    you go above in the top tenth of your playing".
    On the test data this gives e.g. 105 with a baseline of 77: headroom 28,
    and the critical zone covers 10 % of the time.

    Returns `KRITICKY_ZALOHA` until there is something to compute from.
    `baseline` is only a safeguard so that the result does not end up just
    above the baseline.
    """
    # MINIMUM 5 MINUTES PER SESSION (0.2.1) - the same rule as for the load
    # threshold (`je_dost_dlha`). Until now 300 curve points IN TOTAL were
    # enough, so three two-minute sessions while pairing the watch (you sit,
    # heart rate at rest) replaced the fallback of 110 with a limit just above
    # the baseline. A lower limit = less headroom = higher load and more
    # "Peak" - the app would cry wolf from data that says nothing about
    # playing. A short session is NOT DELETED, the limit is just not learned
    # from it; the baseline (`dlhodoba_zakladna`) still takes it.
    ciste = [r for r in ciste_relacie(sessions)
             if je_dost_dlha(r)][-KRITICKY_Z_RELACII:]
    if len(ciste) < KRITICKY_MIN_RELACII:
        return KRITICKY_ZALOHA
    body = []
    for r in ciste:
        for b in (r.get("curve") or []):
            try:
                v = float(b)
            except (TypeError, ValueError):
                continue
            # Points outside a human heart rate do not belong in the
            # percentile - otherwise one broken stretch would push the
            # critical threshold up (B9).
            if KRITICKY_MIN_BOD <= v <= KRITICKY_MAX_BOD:
                body.append(v)
    if len(body) < KRITICKY_MIN_BODOV:
        return KRITICKY_ZALOHA
    hodnota = _percentile(sorted(body), KRITICKY_PERCENTIL)
    if baseline:
        # The headroom must not be merely symbolic - otherwise the load gets
        # scaled over a few beats and the app will react to noise.
        hodnota = max(hodnota, float(baseline) + KRITICKY_MIN_NAD_ZAKLADNOU)
    # CAP: its sister `dynamicky_prah_zataze` has one (PRAH_ROZSAH), this
    # one did not - a single nonsensical curve could push the critical
    # threshold up to 235 and the app would never mark anything as critical
    # again and go quiet (B9).
    return float(round(max(KRITICKY_STROP[0], min(KRITICKY_STROP[1], hodnota))))


PRAH_PERCENTIL = 0.80          # ~20 % of playing time should be above the threshold
PRAH_MIN_RELACII = 3
# How many load points the sessions must give IN TOTAL. Point = a 1.5 s
# replay step (`load_z_krivky`), only time with signal is replayed
# (`duration_s * pokrytie`) and the first 29 steps of each session are
# calibration (`HeartStats` wants 30 samples), which does not count. So a
# session gives `int(signal_s / 1.5) - 29` points.
#
# 1000 -> 900 (0.2.1). The README promises "three sessions of roughly ten
# minutes are enough, three of five are not". At 1000 that held only with
# coverage above ~91 %: 3 x 10 min gives at 100 % 3 x 371 = 1113, at 90 %
# 3 x 331 = 993 and at 85 % 3 x 311 = 933 - so a normal evening with a few
# holes in the signal would stay below the threshold. 900 lets 3 x 10 min
# through down to a coverage of ~82 %, and still does not let through
# 3 x 5 min (3 x 171 = 513 not even at full coverage) nor 3 x 8 min at
# full coverage (873). Together with calibration, for three sessions it is
# (900 + 3 x 29) x 1.5 s = ~25 minutes of heart rate - "roughly half an
# hour" from the README.
PRAH_MIN_BODOV = 900
PRAH_Z_RELACII = 20
PRAH_MIN_TRVANIE_S = 300.0
PRAH_ROZSAH = (35.0, 85.0)


def je_dost_dlha(session):
    """True when the session lasts at least `PRAH_MIN_TRVANIE_S` (5 minutes).

    One rule for both the load threshold and the critical heart rate: no
    personal limit is learned from a shorter session. A broken or missing
    `duration_s` behaves as zero - the session is not learned from, but it
    does not bring down the whole computation either (in
    `app._open_hr_session` an exception would also throw away the
    long-term baseline). The upper-bound comparison catches NaN and
    infinity from a broken file, same as in `pokrytie_signalu`.

    The sentences in the settings "computed from n sessions"
    (`app._kriticky_popis`, `_prah_z_relacii`) must count n by THIS rule -
    otherwise with three short sessions they would claim a computed limit
    while the fallback applies.
    """
    try:
        trvanie = float(session.get("duration_s") or 0)
    except (TypeError, ValueError, AttributeError):
        return False
    return PRAH_MIN_TRVANIE_S <= trvanie < float("inf")


def load_z_krivky(session, baseline, critical, krok_s=1.5):
    """Replays a session's stored curve and returns the LOAD over time from it.

    A session stores heart rate, not load - here it is recomputed with the
    same code that runs live (`HeartStats`), so the result cannot drift
    apart from what the app computed in real time.
    """
    krivka = session.get("curve") or []
    trvanie = float(session.get("duration_s") or 0)
    if len(krivka) < 10 or trvanie < PRAH_MIN_TRVANIE_S:
        return []
    # The curve is thinned by NUMBER of samples, not by time (`trace` ->
    # `downsample`), so the gaps after dropouts are not in it. Stretched over
    # the whole `duration_s`, an evening with gaps weighed 1/coverage times
    # more than the others and had its time axis stretched. So only the time
    # when the heart rate really came in is replayed (`trvanie * p` is the
    # sum of the zones). The condition above stays on `duration_s` so that it
    # does not change which sessions count towards the threshold, nor "computed
    # from n sessions" in the settings. Without coverage (old sessions, None)
    # the whole duration is replayed as before.
    p = pokrytie_signalu(session)
    if p:
        trvanie *= p
    st = HeartStats(critical_bpm=int(critical or 110))
    st.long_baseline = baseline
    out = []
    t = 0.0
    for i in range(int(trvanie / krok_s)):
        x = i * krok_s / trvanie * (len(krivka) - 1)
        a = int(x)
        b = min(a + 1, len(krivka) - 1)
        try:
            hodnota = krivka[a] + (krivka[b] - krivka[a]) * (x - a)
        except (TypeError, ValueError):
            continue
        t += krok_s
        st.add(hodnota, ts=t)
        # Calibration is skipped: live, the trigger does not see it
        # (`note_load` with `calibrating=True`), so it must not move the
        # threshold either.
        if not st.is_calibrating:
            out.append(st.stress)
    return out


def dynamicky_prah_zataze(sessions, baseline=None, critical=None):
    """Load threshold at which the app starts arming. Or None.

    WHY IT IS NOT A SETTING
    It was - as a "how often I speak up" option with three positions. But
    the player has no way to know what each position does FOR THEM: the
    load is scaled against their own baseline, so the same number means
    something different for everyone.

    HOW IT IS COMPUTED
    The 80th percentile of their own load across clean sessions - i.e. "the
    limit above which they spend a fifth of their playing". Measured on the
    test data this gives a threshold of 73 and 3.7 delivered cues per hour,
    which fits under the cap of 5 from the spec. A lower threshold only
    uses up the cap sooner and the cues fall on less heated moments.

    So the threshold does not decide HOW MANY cues come - that is done by
    `max_per_hour` and `min_gap_s`. It decides WHICH moments qualify for
    them.

    Returns None until there is something to compute from - the caller
    then keeps the numbers for an average player from
    `trigger.default_params()`.
    """
    pouzitelne = [r for r in ciste_relacie(sessions)
                  if je_dost_dlha(r) and r.get("curve")][-PRAH_Z_RELACII:]
    if len(pouzitelne) < PRAH_MIN_RELACII:
        return None
    body = []
    for r in pouzitelne:
        body.extend(load_z_krivky(r, baseline, critical))
    if len(body) < PRAH_MIN_BODOV:
        return None
    prah = _percentile(sorted(body), PRAH_PERCENTIL)
    lo, hi = PRAH_ROZSAH
    return float(round(max(lo, min(hi, prah))))


def dlhodoba_zakladna(sessions):
    """The player's resting baseline across sessions, or None.

    WHY COMPUTING IT FROM ONE SESSION IS NOT ENOUGH
    The baseline within a session is the 20th percentile of the last 10
    minutes. When the player turns the app on only in the middle of a
    fight - or when the heart rate stays up the whole evening - that window
    never sees calm and the baseline settles on stress. Load is computed
    against it, so in sustained stress the app sees zero load.

    But the player has a resting heart rate even when they did not show it
    tonight - it is recorded in previous sessions. The 20th percentile of
    the baselines from the last `DLHODOBA_Z_RELACII` sessions is taken: the
    same statistic, just one floor higher, so a single bad evening does not
    decide the result.
    """
    hodnoty = []
    # A suspect session (broken heart rate reading) must not determine the
    # baseline - see `je_podozriva`.
    for s in ciste_relacie(sessions)[-DLHODOBA_Z_RELACII:]:
        try:
            b = float(s.get("baseline_bpm") or 0)
        except (TypeError, ValueError):
            continue
        if b >= DLHODOBA_PODLAHA:
            hodnoty.append(b)
    if len(hodnoty) < DLHODOBA_MIN_RELACII:
        return None
    return _percentile(sorted(hodnoty), 0.20)



# --------------------------------------------------------------------------
# "Full Zanshin" - graduation (easter egg). Detection over the STORED
# history, against the player's OWN baseline; never over the live sensor.
# Fires ONCE. The numbers are chosen against the baseline (not fixed):
# base+12 (~"under 90" normally), base+18 (~"under 95" at peaks), 5 of the
# last 7, min 10 sessions and 10 days.
# --------------------------------------------------------------------------
ZEN_REG_MARGIN = 12.0
ZEN_SPIKE_MARGIN = 18.0
ZEN_REG_QUANTILE = 0.80
ZEN_SPIKE_QUANTILE = 0.95
ZEN_MAX_CRIT_CROSSINGS = 1
ZEN_MIN_DURATION_S = 900.0
ZEN_MIN_SAMPLES = 300
ZEN_WINDOW = 7
ZEN_NEEDED = 5
ZEN_MIN_TOTAL = 10
ZEN_MIN_SPAN_DAYS = 10.0
# Only PLAY sessions count towards the streak (0.2, B3-worlds) - same as
# the critical heart rate and the load threshold (`app.ALGORITMUS_SVET`).
# A calm afternoon at work is not calm while playing; and the message
# talks about "the next match". The world is decided by `session_world`
# (answer in the questionnaire > world at start > Play).
ZEN_SVET = "play"


def _rising_crossings(curve, threshold):
    """How many times the curve crosses the threshold RISING (only crossings
    from below upwards - one jump = one crossing, not every point above the
    threshold)."""
    n = 0
    hore = False
    for v in curve:
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if not hore and x >= threshold:
            n += 1
            hore = True
        elif hore and x < threshold:
            hore = False
    return n


def je_plne_zanshin(session):
    """Was the session "full Zanshin"? True / False / None.

    None = the session does NOT COUNT (short, no data, suspect, imported) -
    deliberately, so that days off and quick peeks NEVER punish (the app
    must not create a streak that can be lost; see the removed
    `streaks()`).

    Otherwise PASS iff (against the player's OWN baseline):
      1. 80 % of the course <= base + ZEN_REG_MARGIN   (~under 90, usual calm)
      2. even the hottest 5 % <= base + ZEN_SPIKE_MARGIN  (~under 95 at peaks)
      3. <= ZEN_MAX_CRIT_CROSSINGS rising crossings of the critical line
    Percentiles (not max_bpm): the module does not trust single extremes -
    one artefact beat must not cancel a calm evening.

    THE BASELINE HAS THE SAME CAP AS THE ZONES (0.2, C2). The session
    baseline is the 20th percentile of this evening; the long-term baseline
    (`long_baseline_bpm`, stored in the summary) is its CAP - exactly as in
    `HeartStats.baseline`, against which both the load and the "Calm" zone
    are computed. Without the cap an evening that stayed evenly HIGH the
    whole time (coffee, sustained stress) would pass: the 20th percentile
    follows it up and the spread stays small. Old sessions without the
    field have only the session baseline.

    LENGTH = TIME WITH HEART RATE. `duration_s` also includes dropouts
    (watch away, PC asleep); since C3 the summary carries `blind_s`, so
    dropouts up to 15 minutes do not count. Otherwise 5 minutes of heart
    rate and 20 minutes of silence would pass as a whole calm evening.
    Waiting for the first sample is not subtracted - `blind_s` does not
    know it, because the heart rate was not coming in yet (see
    `note_dropout`). Without the field (old sessions) the whole duration is
    taken.

    Load, zones (`zone_seconds`) and the trigger threshold do not enter
    here, so their calibration changes nothing: these are only stored HEART
    RATES (`curve`, also from the first seconds), baselines, `critical_bpm`
    and counts.
    """
    try:
        if session is None or je_podozriva(session) or session.get("imported"):
            return None
        base = float(session.get("baseline_bpm") or 0)
        dlhodoba = float(session.get("long_baseline_bpm") or 0)
        if dlhodoba > 0 and base > 0:
            base = min(base, dlhodoba)
        crit = float(session.get("critical_bpm") or 0)
        curve = [float(x) for x in (session.get("curve") or [])
                 if isinstance(x, (int, float))]
        dur = (float(session.get("duration_s") or 0)
               - max(0.0, float(session.get("blind_s") or 0)))
        samples = int(session.get("samples") or 0)
    except (TypeError, ValueError):
        return None
    if (base <= 0 or crit <= 0 or dur < ZEN_MIN_DURATION_S
            or samples < ZEN_MIN_SAMPLES or len(curve) < 30):
        return None
    body = sorted(curve)
    if _percentile(body, ZEN_REG_QUANTILE) > base + ZEN_REG_MARGIN:
        return False
    if _percentile(body, ZEN_SPIKE_QUANTILE) > base + ZEN_SPIKE_MARGIN:
        return False
    if _rising_crossings(curve, crit) > ZEN_MAX_CRIT_CROSSINGS:
        return False
    return True


def _zen_eligible(sessions):
    """Clean PLAY sessions (no suspect/imported/confounded, only `ZEN_SVET`)
    with the je_plne_zanshin evaluation, sorted by time; None (does not
    count) is skipped."""
    out = []
    for s in ciste_relacie(sessions_in_world(sessions, ZEN_SVET)):
        r = je_plne_zanshin(s)
        if r is None:
            continue
        out.append((s, r))
    out.sort(key=lambda sr: float(sr[0].get("started") or 0))
    return out


def zanshin_streak(sessions):
    """Streak state - RECOMPUTED from history (nothing saved, self-healing)."""
    elig = _zen_eligible(sessions)
    window = elig[-ZEN_WINDOW:]
    passed = sum(1 for _, r in window if r)
    current = bool(elig and elig[-1][1])
    return {"eligible": len(elig), "passed_in_window": passed,
            "current_pass": current, "streak": passed}


def zanshin_graduation(sessions, already_graduated=False):
    """Should graduation fire? Returns a dict with `fire` (once) and `reason`.

    Safeguards: it fires only with >=ZEN_MIN_TOTAL clean play sessions, spread
    over at least ZEN_MIN_SPAN_DAYS days, with an existing stable baseline,
    and only when the last evening was calm (the circle closes after calm,
    not after stress).
    """
    if already_graduated:
        return {"fire": False, "graduated": True, "reason": "already"}
    elig = _zen_eligible(sessions)
    if len(elig) < ZEN_MIN_TOTAL:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "need_more"}
    prvy = float(elig[0][0].get("started") or 0)
    posl = float(elig[-1][0].get("started") or 0)
    if (posl - prvy) < ZEN_MIN_SPAN_DAYS * 86400.0:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "too_soon"}
    if dlhodoba_zakladna(sessions) is None:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "no_baseline"}
    window = elig[-ZEN_WINDOW:]
    passed = sum(1 for _, r in window if r)
    current = bool(elig[-1][1])
    fire = passed >= ZEN_NEEDED and current
    return {"fire": fire, "graduated": False, "eligible": len(elig),
            "passed_in_window": passed, "reason": "fire" if fire else "not_yet"}

def zone_of_bpm(bpm, baseline, critical_bpm):
    """The zone of one heart rate value against the player's OWN baseline.

    The single source of truth for zones: it is used by the time sum
    (`time_in_zones`), every chart that draws a zone band (the session
    trace), and the live zone word and colour on the HUD, on Today and on
    the heart rate indicator (`HeartStats.zone`). If each computed it on
    its own, the bar and the numbers under it would stop matching over
    time - and "High" would mean two different things on one page.
    """
    if bpm >= critical_bpm:
        return ZONE_CRITICAL
    if bpm >= baseline + 25:
        return ZONE_HIGH
    if bpm >= baseline + 10:
        return ZONE_RAISED
    return ZONE_CALM


def time_in_zones(samples, critical_bpm, baseline=None):
    """Seconds in zones by DEVIATION FROM THE BASELINE, not by the live
    load (that is a smoothed state and cannot be reconstructed afterwards).

    Zones: calm < base+10, raised < base+25, high < critical, critical >=
    critical. The result is a dict {zone: seconds}. Used for an
    after-the-fact recomputation from raw samples (e.g. in tests or on
    import); a live session computes its zones continuously from the
    current load."""
    out = {ZONE_CALM: 0.0, ZONE_RAISED: 0.0, ZONE_HIGH: 0.0, ZONE_CRITICAL: 0.0}
    if not samples:
        return out
    base = baseline if baseline is not None else (session_baseline(samples) or min(b for _, b in samples))
    for (ts, bpm), dur in zip(samples, _durations(samples)):
        out[zone_of_bpm(bpm, base, critical_bpm)] += dur
    return out


def heart_rate_recovery(samples, recovery_s=60.0, min_prominence=15.0,
                        tolerance_s=5.0, peak_window_s=30.0, lookback_s=180.0):
    """Heart Rate Recovery: how far heart rate fell 1 minute after a local peak.

    Returns a list of events {peak_ts, peak_bpm, after_bpm, recovery} - one
    for each peak that:
      * is the highest in the window +-peak_window_s (local maximum),
      * is at least `min_prominence` BPM above the minimum of the preceding
        `lookback_s` (a short little blip in a calm heart rate is not a
        "peak"),
      * has a sample roughly recovery_s after it (tolerance tolerance_s) -
        otherwise the recovery cannot be measured and the event is skipped.

    recovery = peak_bpm - after_bpm (negative = the heart rate kept rising).
    Definition: Cleveland Clinic - HRR is the difference between the heart
    rate at the peak and a minute after it; normal 12-23, trained 29+.
    """
    n = len(samples)
    events = []
    if n < 3:
        return events
    ts_list = [t for t, _ in samples]
    j0 = 0
    for i in range(n):
        ts, bpm = samples[i]
        # local maximum in the window +-peak_window_s (the first one on a tie)
        is_peak = True
        k = i - 1
        while k >= 0 and ts - ts_list[k] <= peak_window_s:
            if samples[k][1] >= bpm:
                is_peak = False
                break
            k -= 1
        if not is_peak:
            continue
        k = i + 1
        while k < n and ts_list[k] - ts <= peak_window_s:
            if samples[k][1] > bpm:
                is_peak = False
                break
            k += 1
        if not is_peak:
            continue
        # prominence against the minimum of the preceding lookback_s
        while j0 < i and ts - ts_list[j0] > lookback_s:
            j0 += 1
        floor = min(b for _, b in samples[j0:i + 1])
        if bpm - floor < min_prominence:
            continue
        # sample ~recovery_s after the peak
        target = ts + recovery_s
        best = None
        for m in range(i + 1, n):
            gap = ts_list[m] - target
            if gap > tolerance_s:
                break
            if abs(gap) <= tolerance_s and (best is None or abs(gap) < abs(ts_list[best] - target)):
                best = m
        if best is None:
            continue
        events.append({"peak_ts": ts, "peak_bpm": bpm, "after_bpm": samples[best][1],
                       "recovery": bpm - samples[best][1]})
    return events


def hrr_headline(events):
    """One number for the UI: recovery after the session's HIGHEST peak (that
    is how HRR is measured clinically too - after maximum load). None
    without events."""
    if not events:
        return None
    top = max(events, key=lambda e: e["peak_bpm"])
    return int(round(top["recovery"]))


def persistence_index(samples):
    """Heart Rate Persistence Index (HRPI): the largest whole k such that the
    heart rate was at least k BPM for at least k SECONDS (cumulative, time
    in seconds from the sample spacing, not the number of samples).

    Analogous to the h-index: a session "120 BPM for 2 minutes" gives
    k = 120, a session "85 BPM for 3 hours" gives k = 85. One number
    combines both height and duration. 0 for empty data.
    """
    if not samples:
        return 0
    pairs = sorted(zip((b for _, b in samples), _durations(samples)), reverse=True)
    cum = 0.0
    best = 0
    # we go from the highest heart rate down; cum = seconds with heart
    # rate >= the current bpm
    idx = 0
    n = len(pairs)
    for k in range(int(pairs[0][0]), 0, -1):
        while idx < n and pairs[idx][0] >= k:
            cum += pairs[idx][1]
            idx += 1
        if cum >= k:
            best = k
            break
    return best


# Below this time span (first -> last session) a regression slope makes
# no sense - see baseline_trend() below.
MIN_TREND_SPAN_S = 2 * 86400.0  # 2 days


def baseline_trend(sessions, min_span_s=MIN_TREND_SPAN_S):
    """Trend of the resting baseline across sessions.

    Returns {"points": [(started, baseline)], "first", "last", "delta",
    "slope_per_week", "insufficient_span"}; slope is a linear regression of
    the baseline against time (days). Sessions without baseline_bpm are
    skipped.

    Bug (fixed here): a regression over points close together in time gave
    nonsensical values like "-3009 BPM/week" - two sessions e.g. 5 minutes
    apart have almost zero time variance, so even a small baseline
    difference, after dividing by this variance (and multiplying x7 for
    "per week"), shoots up into the thousands. Solution: if the span
    between the FIRST and the LAST session is less than `min_span_s`
    (default 2 days), `slope_per_week` stays 0.0 and
    `insufficient_span=True` - the UI should then show "I need more data",
    not a number. At >=2 days the computation is identical to before (the
    existing test with sessions 1 day apart across a week must give the
    same result).
    """
    points = [(float(s.get("started", 0)), float(s["baseline_bpm"]))
              for s in sessions
              if isinstance(s, dict) and s.get("baseline_bpm")]
    points.sort()
    out = {"points": points, "first": None, "last": None, "delta": 0.0,
           "slope_per_week": 0.0, "insufficient_span": True}
    if not points:
        return out
    out["first"], out["last"] = points[0][1], points[-1][1]
    out["delta"] = points[-1][1] - points[0][1]
    span_s = points[-1][0] - points[0][0]
    out["insufficient_span"] = len(points) < 2 or span_s < min_span_s
    if not out["insufficient_span"]:
        xs = [(t - points[0][0]) / 86400.0 for t, _ in points]
        ys = [b for _, b in points]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        var = sum((x - mx) ** 2 for x in xs)
        if var > 0:
            slope_day = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
            out["slope_per_week"] = slope_day * 7.0
    return out


def count_sessions_since(sessions, since_ts):
    """Number of sessions since `since_ts` (unix time) and their total length.

    Used by Today ("Sessions this week") - the caller computes the start of
    the period itself (e.g. Monday midnight, see period_start_ts), this
    function only filters and sums."""
    count, duration = 0, 0.0
    for s in sessions:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)) or started < since_ts:
            continue
        count += 1
        duration += float(s.get("duration_s") or 0.0)
    return count, duration


# --------------------------------------------------------------------------
# What is usual for THIS player (chart, stat cards, day grid)
# --------------------------------------------------------------------------

def metric_series(sessions, field, n=8):
    """The last `n` values of one summary field, chronologically.

    For the sparkline next to a number: "62 BPM" on its own says nothing,
    "62, and over the last seven sessions it went down" says everything.
    Sessions without that field are skipped (not with zero - a zero would
    make the curve lie).
    """
    ordered = sorted((s for s in sessions if isinstance(s, dict)
                      and isinstance(s.get("started"), (int, float))),
                     key=lambda s: s["started"])
    values = []
    for s in ordered:
        try:
            value = s.get(field)
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values[-n:] if n else values


def usual_range(values, lo_pct=0.25, hi_pct=0.75, min_values=4):
    """(p25, p75) - "your usual range" as a band behind the chart.

    Below `min_values` values None: quartiles from three numbers are
    decoration, not a range. Deliberately percentiles, not mean +-
    deviation - one panicky evening would stretch the range into nonsense.
    """
    vals = []
    for value in values or []:
        try:
            if value is not None:
                vals.append(float(value))
        except (TypeError, ValueError):
            continue
    if len(vals) < min_values:
        return None
    return _percentile(vals, lo_pct), _percentile(vals, hi_pct)


def day_activity(sessions, days=112, now=None):
    """Calendar grid: [{"date", "seconds", "count"}] for the last `days` days
    including today, oldest first.

    Days WITHOUT a session are in the list too (with zeros) - the gaps are
    exactly what a person reads on the grid, so they must not be left out.
    """
    now_dt = datetime.fromtimestamp(now if now is not None else time.time())
    today = now_dt.date()
    first = today - timedelta(days=days - 1)
    cells = {first + timedelta(days=i): {"seconds": 0.0, "count": 0}
             for i in range(days)}
    for s in sessions or []:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)):
            continue
        cell = cells.get(datetime.fromtimestamp(started).date())
        if cell is None:
            continue
        cell["count"] += 1
        cell["seconds"] += float(s.get("duration_s") or 0.0)
    return [{"date": day, "seconds": cell["seconds"], "count": cell["count"]}
            for day, cell in sorted(cells.items())]


# NOTE: here used to be `streaks()` - the current and the longest streak
# of consecutive days. It was dropped on purpose, not because it did not
# work. A streak is the only thing in the app that can be BROKEN, and the
# app is meant to calm: the best published evidence on streaks is
# unfavourable (runners who kept a streak ran through injuries and
# described it as an addiction). Instead, the History page shows the
# number of days on which some session took place - the same "you keep at
# it", but nothing in it can be lost by one skipped evening. The day grid
# (`day_activity`) stays.


# --------------------------------------------------------------------------
# Values of one STORED session (History: chart and detail; card on Today)
# --------------------------------------------------------------------------
# Everything is computed from fields the summary already stores - no new
# stored field. None everywhere means "we don't know" (an old, imported or
# broken session), never zero: zero minutes in calm is a statement,
# missing zones are not.

def _cislo(value):
    """float, or None for None / text / NaN / infinity."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def cas_v_pokoji_s(session):
    """Session seconds in the CALM zone (`zone_seconds["calm"]`), or None.

    The zone is the same as everywhere else (`zone_of_bpm`): heart rate
    less than 10 BPM above resting. None when the session has no zones -
    not 0."""
    try:
        zony = session.get("zone_seconds")
        if not zony:
            return None
        v = _cislo(zony.get(ZONE_CALM) or 0.0)
    except AttributeError:
        return None
    return v if v is not None and v >= 0.0 else None


def hlasky_relacie(session):
    """How many cues the app sent ON ITS OWN in the session (`auto_triggers`;
    old sessions only have `triggers`), or None. ONE number per session
    everywhere: the History table, session detail, the History chart and
    the CSV column "breathing" (`session_row`)."""
    try:
        v = _cislo(session.get("auto_triggers", session.get("triggers")))
    except AttributeError:
        return None
    return int(v) if v is not None and v >= 0 else None


def namerana_zataz_0_10(session):
    """Measured load of the session on a 0-10 scale - so that it can stand
    next to the perceived load from the questionnaire (also 0-10), or None.

    It is the session's load PEAK (`peak_stress`, 0-100) divided by ten and
    rounded half up (45 -> 5, not banker's 4). There is no other stored
    load number for the whole session; the average load is not stored. The
    player can read about it in the card's ⓘ and under the History table
    (`metric.felt_vs_measured.more`).
    """
    try:
        v = _cislo(session.get("peak_stress"))
    except AttributeError:
        return None
    if v is None or v < 0.0:
        return None
    return min(10, int(v / 10.0 + 0.5))


def citene_a_merane(session):
    """(citene, merane): felt load (questionnaire) and measured, both 0-10.

    None when the player skipped the questionnaire (did not enter the
    perceived load) - without it there is nothing to compare. `merane` can
    be None (a session without a load peak). DELIBERATELY two numbers, not
    a difference, a ratio or a verdict: neither one is "right" - the heart
    rate does not see how you felt, and you do not feel every beat.
    """
    if not isinstance(session, dict):
        return None
    citene = normalize_felt_load(session.get("felt_load"))
    if citene is None:
        return None
    return citene, namerana_zataz_0_10(session)


def posledna_relacia(sessions):
    """The last STORED session (by `started`), or None.

    Stored = finished: the current session gets into the file only when it
    is closed (`app._close_hr_session`). Imported sessions (`imported`) are
    skipped - they are someone else's data (`data_io`), not "your last
    session"; otherwise, after merging someone else's export, the card
    would show someone else's numbers."""
    najnovsia = None
    for s in sessions or []:
        if not isinstance(s, dict) or s.get("imported"):
            continue
        started = _cislo(s.get("started"))
        if started is None:
            continue
        if najnovsia is None or started >= najnovsia[0]:
            najnovsia = (started, s)
    return najnovsia[1] if najnovsia else None


# --------------------------------------------------------------------------
# Time periods (History: Day / Week / Month / Year)
# --------------------------------------------------------------------------

PERIOD_HOUR = "hour"
PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_YEAR = "year"
PERIODS = (PERIOD_DAY, PERIOD_WEEK, PERIOD_MONTH, PERIOD_YEAR)

# Which buckets sessions are grouped into in the chart FOR THE chosen
# period - "month" shows daily averages, "year" monthly ones (exactly as in
# the spec).
CHART_BUCKET_FOR_PERIOD = {
    PERIOD_DAY: PERIOD_HOUR,
    PERIOD_WEEK: PERIOD_DAY,
    PERIOD_MONTH: PERIOD_DAY,
    PERIOD_YEAR: PERIOD_MONTH,
}


def _period_floor(dt, period):
    if period == PERIOD_HOUR:
        return dt.replace(minute=0, second=0, microsecond=0)
    if period == PERIOD_DAY:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_WEEK:
        start = dt - timedelta(days=dt.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_MONTH:
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_YEAR:
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"neznamy period: {period}")


def period_start_ts(period, now=None):
    """Start of the CURRENT period (e.g. "this week" = Monday 00:00) as unix
    time in local time. `now` (unix time) is for tests."""
    dt = datetime.fromtimestamp(now if now is not None else time.time())
    return _period_floor(dt, period).timestamp()


PERIOD_SPAN_S = {
    PERIOD_DAY: 86400.0,
    PERIOD_WEEK: 7 * 86400.0,
    PERIOD_MONTH: 30 * 86400.0,
    PERIOD_YEAR: 365 * 86400.0,
}


def rolling_start_ts(period, now=None):
    """Start of a ROLLING window ("the last 7 days"), not a calendar
    period.

    The trend chart wants a window, the calendar hurts it: on a Monday
    morning "this week" (since midnight) would show an empty chart with the
    message "Nothing in this period yet", even though the player played the
    whole weekend. The "Sessions this week" card, on the other hand, really
    wants the calendar - there a week should mean a week, and that is why
    `period_start_ts` stays and is still used.
    """
    now = float(now) if now is not None else time.time()
    return now - PERIOD_SPAN_S.get(period, 7 * 86400.0)


_BUCKET_LABEL_FMT = {
    PERIOD_HOUR: "%H:%M", PERIOD_DAY: "%d.%m", PERIOD_WEEK: "%d.%m",
    PERIOD_MONTH: "%m.%Y", PERIOD_YEAR: "%Y",
}


# Metrics that a bucket averages - each is an average PER SESSION in the
# bucket. The last four were added in 0.2 (History = the whole picture):
# session length, time in calm, signal coverage (0..1) and the number of
# cues the app sent on its own.
BUCKET_METRICS = ("baseline", "hrr", "over_s", "peak",
                  "duration_s", "calm_s", "coverage", "cues")


def aggregate_by_period(sessions, period):
    """Groups sessions into buckets by calendar period (hour/day/
    week/month/year) and averages the key metrics in each of them.

    Returns a chronologically sorted list of dicts {"started", "label",
    "count"} + one value for each key from `BUCKET_METRICS` - each metric
    is the average of the sessions in the given bucket, or None if no
    session in the bucket has it. Sessions without `started` are skipped.
    """
    buckets = {}
    for s in sessions:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)):
            continue
        dt = datetime.fromtimestamp(started)
        floor = _period_floor(dt, period)
        key = floor.timestamp()
        b = buckets.get(key)
        if b is None:
            b = buckets[key] = {"label": floor.strftime(_BUCKET_LABEL_FMT[period]),
                               "count": 0}
            b.update({m: [] for m in BUCKET_METRICS})
        b["count"] += 1
        if s.get("baseline_bpm"):
            b["baseline"].append(float(s["baseline_bpm"]))
        if s.get("hrr_bpm") is not None:
            b["hrr"].append(float(s["hrr_bpm"]))
        if s.get("time_over_s") is not None:
            b["over_s"].append(float(s["time_over_s"]))
        if s.get("peak_stress") is not None:
            b["peak"].append(float(s["peak_stress"]))
        # The new metrics go through the helpers above: a broken value from an
        # import is skipped (None), it does not bring down the whole chart.
        trvanie = _cislo(s.get("duration_s"))
        if trvanie is not None and trvanie > 0:
            b["duration_s"].append(trvanie)
        for kluc, hodnota in (("calm_s", cas_v_pokoji_s(s)),
                              ("coverage", pokrytie_signalu(s)),
                              ("cues", hlasky_relacie(s))):
            if hodnota is not None:
                b[kluc].append(float(hodnota))

    def avg(values):
        return sum(values) / len(values) if values else None

    out = []
    for key, b in sorted(buckets.items()):
        row = {"started": key, "label": b["label"], "count": b["count"]}
        row.update({m: avg(b[m]) for m in BUCKET_METRICS})
        out.append(row)
    return out


def _period_next(dt, period):
    if period == PERIOD_HOUR:
        return dt + timedelta(hours=1)
    if period == PERIOD_DAY:
        return dt + timedelta(days=1)
    if period == PERIOD_WEEK:
        return dt + timedelta(days=7)
    if period == PERIOD_MONTH:
        return (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    if period == PERIOD_YEAR:
        return dt.replace(year=dt.year + 1)
    raise ValueError(f"neznamy period: {period}")


EMPTY_BUCKET_LIMIT = 400        # safeguard against a nonsensical range


def bucket_axis(buckets, period, start, end=None):
    """Adds EMPTY buckets between `start` and `end` so the axis is continuous.

    `aggregate_by_period` makes a bucket only for a period in which some
    session really took place. The chart then drew Wednesday right next to
    Monday, and Tuesday, when nobody played, vanished from the axis - even
    though the pause itself is information. Filled-in buckets have count 0
    and all metrics None, so they are not drawn in the chart, but they take
    up space on the axis.
    """
    existujuce = {b["started"]: b for b in buckets}
    end = float(end) if end is not None else time.time()
    dt = _period_floor(datetime.fromtimestamp(start), period)
    posledny = _period_floor(datetime.fromtimestamp(end), period)
    out = []
    while dt <= posledny and len(out) < EMPTY_BUCKET_LIMIT:
        key = dt.timestamp()
        prazdny = {"started": key, "label": dt.strftime(_BUCKET_LABEL_FMT[period]),
                   "count": 0}
        prazdny.update({m: None for m in BUCKET_METRICS})
        out.append(existujuce.get(key) or prazdny)
        dt = _period_next(dt, period)
    return out


# While the chosen step source is sending, the others are ignored. When it
# goes quiet for this many seconds, another one may take over. A minute is
# enough so that it does not flip at every Wi-Fi dropout, and short enough
# that switching the source on the phone does not cost the player a whole
# evening without movement detection.
PRELADENIE_ZDROJA_S = 60.0

# "I haven't picked a source yet" - distinct from `None`, which is a valid
# source (UDP and watches that do not send a source name).
_NEURCENY = object()


class HeartStats:
    """Holds the heart rate history and everything derived from it.

    The class is purely data - no Tk, no I/O except saving the session
    summary at the end. It is called EXCLUSIVELY from the GUI thread (from
    `_apply_hr_bpm`), so it does not need a lock.
    """

    def __init__(self, critical_bpm=110):
        self.critical_bpm = int(critical_bpm)
        self._samples = []          # [(timestamp, bpm)] for HISTORY_SECONDS
        self._long = []             # [(timestamp, bpm)] for BASELINE_SECONDS
        self.stress = 0.0
        self._raw_stress = 0.0
        # Resting heart rate from PREVIOUS evenings. The app sets it when
        # opening a session (`_open_hr_session`); it is a property of the
        # person, not of the session, so `reset_session` does not clear it.
        self.long_baseline = None
        self.reset_session()

    # ---------- session ----------

    def reset_session(self):
        now = time.time()
        self.session_start = now
        self.session_min = None
        self.session_max = None
        self.session_sum = 0.0
        self.session_count = 0
        self.time_over = 0.0        # seconds above the critical limit
        self.time_high = 0.0        # seconds in the high/critical zone
        self.triggers = 0
        self.auto_triggers = 0      # of these, fired by the app itself (high HR)
        self.peak_stress = 0.0
        self._last_ts = None
        self.last_bpm = None
        self.last_beat_ts = now
        # [(time, bpm)] of the last few seconds ONLY for the number on screen
        # (`display_bpm`). It is cleared together with `last_bpm` - here and in
        # `clear_live` - so after a dropout or a new session it does not pull
        # up an old value.
        self._zobraz = deque(maxlen=ZOBRAZ_MAX_VZORIEK)
        # The lowest baseline we have seen in this session. See `baseline`.
        self._baseline_kotva = None
        # [(time, step increment)] and [(time, speed)] for the last 10 minutes
        self._steps = []
        self._speed = []
        self._last_steps = None
        # Which source I take steps from. The first one that sends some wins
        # and the others are ignored - see `note_metrics`.
        self._zdroj_krokov = _NEURCENY
        self._krok_naposledy = 0.0
        # [(time, 0..1)] share of time with input - filled by the app from
        # `activity.ActivityTracker`. Used to estimate "when the player was
        # really playing".
        self._aktivita = []
        # the whole session (for HRR, HRPI, the session baseline) - 1 sample/s,
        # even a 4-hour session is only ~15k pairs
        self._all = []
        # Load over time, parallel to `_all`. It cannot be added to `_all` -
        # that goes into `persistence_index` and `heart_rate_recovery`, which
        # expect (time, bpm) pairs. But the measurement window also wants
        # "what the load was before and after", and it cannot be recomputed
        # afterwards: it is smoothed with an exponential average, so it
        # depends on the order in which the samples arrived.
        self._load = []
        self.zone_seconds = {ZONE_CALM: 0.0, ZONE_RAISED: 0.0,
                             ZONE_HIGH: 0.0, ZONE_CRITICAL: 0.0}
        # [(bpm, seconds)] from the first evening's calibration, until there
        # is a baseline
        self._zony_cakaju = []
        self.trigger_offsets = []   # seconds since the start of the session
        # Cues with absolute time and which one it was. `trigger_offsets` is
        # not enough for the measurement windows: it is rounded to 0.1 s and
        # counted from when the sensor was switched on, not from the first
        # sample.
        self.cues = []
        self._metric_cache = {}
        # Heart rate dropouts in this session: how many times the app stopped
        # hearing a heart rate it had heard before, and how many seconds it
        # was blind in total. Only these two numbers tell how often the app is
        # really without data - an estimate from cancelled trigger stretches
        # cannot tell that (see `note_dropout`).
        self.dropouts = 0
        self.blind_s = 0.0
        # When the last sample before an open dropout came (None = heart rate
        # is coming in). The first valid sample in `add` closes it.
        self._slepy_od = None

    def note_trigger(self, ts=None, auto=False, category=None, cue_id=None,
                     arm="voice", source=None, delivery=None, delivered=True,
                     rung=None, audible=None, load_at=None, load_peak=None,
                     zone_at=None):
        """Records a fired cue.

        `arm` is "voice" or "silent" - the silent control arm arrives in
        phase 2, the field is already here so that data from both phases
        has the same shape. `source` tells whether the cue was fired by
        the body ("auto") or a key ("key"); the key triggers go away in
        phase 3, until then they are handy for checking that the
        measurements work.

        DELIVERY RECORD (0.2, ladder + gate): `rung` is the session's
        ladder rung, `audible` whether something really sounded,
        `load_at` / `load_peak` the load at delivery and the highest since
        arming, `zone_at` the heart rate zone. They are stored only
        when the caller sends them - older records do not have them and
        `measure.build_window` then does not write them into the window.
        """
        self.triggers += 1
        if auto:
            self.auto_triggers += 1
        # `if ts` would silently fall back to time.time() on ts=0.0 - with
        # absolute times that is unlikely, in tests with their own clock it is
        # not.
        now = float(ts) if ts is not None else time.time()
        self.trigger_offsets.append(round(max(0.0, now - self.session_start), 1))
        zaznam_dorucenia = {k: v for k, v in (
            ("rung", rung), ("audible", None if audible is None else bool(audible)),
            ("load_at", load_at), ("load_peak", load_peak), ("zone_at", zone_at))
            if v is not None}
        self.cues.append({
            "ts": now,
            "category": category,
            "cue_id": cue_id,
            "arm": arm,
            "source": source if source is not None else ("auto" if auto else "key"),
            # "pause" / "timeout" - HOW it was delivered. It must not be
            # merged with `arm` (see the header of `trigger.py`), but it MUST
            # be recorded: without it there is no way to find out afterwards
            # which cues came at a pause and which only after 90 s of silence,
            # and the pause threshold cannot be checked against the data.
            "delivery": delivery,
            # Was the visual really drawn? The silent arm has the visual as its
            # only stimulus - when it failed, the window would measure the cue
            # against nothing. `measure` invalidates such a window (bug B17).
            # True/False, not None: old records lack the field and `measure`
            # keeps them valid.
            "delivered": bool(delivered),
            **zaznam_dorucenia,
        })

    def last_auto_cue_ts(self):
        """Time of the last cue the app sent on its own in THIS session and
        that was really shown - or None until none has come.

        On its own = `source == "auto"` (key and the "Test" button do not
        count, same as `auto_triggers`). Shown = `delivered`: a cue whose
        visual was not drawn does not count as the last one - the player
        saw nothing of it. `reset_session` clears the `cues` list, so the
        previous session does not reach in here.
        """
        for cue in reversed(self.cues):
            if cue.get("source") == "auto" and cue.get("delivered", True):
                return cue.get("ts")
        return None

    # ---------- collection ----------

    def add(self, bpm, ts=None):
        """Adds one heart rate value and recomputes everything derived."""
        try:
            bpm = float(bpm)
        except (TypeError, ValueError):
            return
        if not (25.0 <= bpm <= 250.0):
            return
        now = float(ts) if ts else time.time()

        # The first valid sample after a dropout closes it: the blind time runs
        # from the last sample before it to this one (including the 12 s until
        # the app noticed).
        if self._slepy_od is not None:
            self.blind_s += max(0.0, now - self._slepy_od)
            self._slepy_od = None

        # we credit the time spent in a zone BACKWARDS over the interval since
        # the last sample - otherwise a faster watch (2 Hz) would gather double
        if self._last_ts is not None:
            delta = max(0.0, min(5.0, now - self._last_ts))
            if self.last_bpm is not None and self.last_bpm > self.critical_bpm:
                self.time_over += delta
            # During calibration the app shows the load nowhere - so it must
            # not quietly write it into the session summary either.
            #
            # `time_high` stays DELIBERATELY on the fixed load zones
            # (`zone_for`: 50/75), not on `self.zone`, which since 0.2 talks
            # about heart rate relative to rest. It is a stored metric
            # (`time_high_s`) and must mean the same as in sessions from
            # before 0.2 - whoever "unifies" this here quietly changes the
            # meaning of the whole history.
            if (not self.is_calibrating
                    and zone_for(self.stress) in (ZONE_HIGH, ZONE_CRITICAL)):
                self.time_high += delta
            # Zones are credited by HEART RATE relative to the player's own
            # baseline - with the same function that colours the band in the
            # chart (`zone_of_bpm`). Before, they were computed from the
            # smoothed load, which cannot be reconstructed from the stored
            # data afterwards: the zone band and the numbers under it would
            # thus never quite match. `time_high` stays on the load
            # deliberately - that is a different question ("how long it
            # pushed you"), not a split of the session time.
            if self.last_bpm is not None:
                base = self._zakladna_bez_odhadu()
                if base is None:
                    # The first seconds of the first evening: the seconds
                    # are put aside and credited only once the baseline
                    # arrives (further down in `add`) - not against a
                    # minimum that one bad sample drags down.
                    self._zony_cakaju.append((self.last_bpm, delta))
                else:
                    self.zone_seconds[
                        zone_of_bpm(self.last_bpm, base, self.critical_bpm)] += delta
        self._last_ts = now

        self._samples.append((now, bpm))
        self._long.append((now, bpm))
        self._all.append((now, bpm))
        cutoff = now - HISTORY_SECONDS
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.pop(0)
        long_cutoff = now - BASELINE_SECONDS
        while self._long and self._long[0][0] < long_cutoff:
            self._long.pop(0)

        self.last_bpm = bpm
        self.last_beat_ts = now
        self._zobraz.append((now, bpm))
        self.session_count += 1
        self.session_sum += bpm
        self.session_min = bpm if self.session_min is None else min(self.session_min, bpm)
        self.session_max = bpm if self.session_max is None else max(self.session_max, bpm)

        # Steps are counted SEPARATELY from heart rate: the message does not
        # have to contain them. The baseline anchor moves ONLY downwards and
        # that is done here, not in `baseline` - a property with a hidden side
        # effect is a trap for anyone who calls it once "just to have a look".
        if len(self._long) >= 30:
            ziva = _percentile([b for _, b in self._long], 0.20)
            if self._baseline_kotva is None or ziva < self._baseline_kotva:
                self._baseline_kotva = ziva

        if self._zony_cakaju:
            base = self._zakladna_bez_odhadu()
            if base is not None:
                for b, d in self._zony_cakaju:
                    self.zone_seconds[zone_of_bpm(b, base, self.critical_bpm)] += d
                self._zony_cakaju = []

        self._recompute(now)
        # Load from calibration goes neither into the peak nor into the trace
        # for the measurement windows (`pre_load` would otherwise average an
        # estimate or zeros).
        if not self.is_calibrating:
            self._load.append((now, self.stress))
            self.peak_stress = max(self.peak_stress, self.stress)

    def note_metrics(self, steps=None, speed=None, ts=None, zdroj=None):
        """Steps and speed from the watch. Both are optional.

        The DIFFERENCE in steps between messages is kept, not their
        absolute count: the watch sends a cumulative total for the day,
        and that on its own says nothing about movement right now. A
        negative difference (midnight, app restart on the watch) is thrown
        away.

        `None` means "we don't know", not "zero". Mixing them up would mean
        claiming that the player is sitting whenever the watch does not
        send steps - and window rejection is supposed to rest on exactly
        that.

        STEPS ARE TAKEN FROM ONE SOURCE ONLY.
        `zdroj` is the name of the OBS source the message came from. The
        app on the watch can write the same step count into several
        sources at once (on the author's setup both `Steps` and `steps`). The
        difference between two counters is not distance walked - it is
        their mutual delay. With a lag of 5 steps and four messages per
        second this came out as 595 steps per minute at a threshold of 15,
        so the app would never say a word again.

        So the first source that sends steps wins and the others are
        quietly skipped. When it goes quiet for `PRELADENIE_ZDROJA_S`,
        another one takes over - otherwise a switched-off source would
        silence steps forever.
        """
        now = time.time() if ts is None else float(ts)
        if steps is not None:
            try:
                steps = int(steps)
            except (TypeError, ValueError):
                steps = None
        if steps is not None:
            if self._zdroj_krokov is _NEURCENY:
                self._zdroj_krokov = zdroj
            elif zdroj != self._zdroj_krokov:
                if now - self._krok_naposledy < PRELADENIE_ZDROJA_S:
                    steps = None            # duplicate from the second counter
                else:
                    # The original source went quiet. This one takes
                    # over, but without a difference - the other
                    # counter is just anchored first.
                    self._zdroj_krokov = zdroj
                    self._last_steps = None
        if steps is not None:
            if self._last_steps is not None and steps >= self._last_steps:
                self._steps.append((now, steps - self._last_steps))
            self._last_steps = steps
            self._krok_naposledy = now
        if speed is not None:
            try:
                self._speed.append((now, float(speed)))
            except (TypeError, ValueError):
                pass
        cutoff = now - BASELINE_SECONDS
        while self._steps and self._steps[0][0] < cutoff:
            self._steps.pop(0)
        while self._speed and self._speed[0][0] < cutoff:
            self._speed.pop(0)

    def note_activity(self, aktivny, ts=None):
        """One activity reading: True/False, whether input just came in.

        The whole session is kept, not a sliding window - the curve is
        stored in the summary and we want it for the whole evening. At
        one-second sampling that is a few tens of thousands of values for
        a long evening, i.e. negligible.
        """
        now = time.time() if ts is None else float(ts)
        self._aktivita.append((now, 1.0 if aktivny else 0.0))

    def activity_trace(self, points=CURVE_POINTS):
        """Activity curve with as many points as `trace()` has for heart rate.

        Each point is the SHARE of activity in the given stretch (0..1),
        not the value at an instant - otherwise it would be random noise of
        ones and zeros instead of what we care about: how dense the playing
        was.
        """
        if not self._aktivita:
            return []
        t0 = self._aktivita[0][0]
        t1 = self._aktivita[-1][0]
        if t1 <= t0:
            return []
        sirka = (t1 - t0) / float(points)
        sucty = [0.0] * points
        pocty = [0] * points
        for t, v in self._aktivita:
            i = min(points - 1, int((t - t0) / sirka))
            sucty[i] += v
            pocty[i] += 1
        return [round(sucty[i] / pocty[i], 3) if pocty[i] else None
                for i in range(points)]

    def steps_per_min(self, window_s=60.0, now=None):
        """Steps in the last minute, or None when we don't know.

        None means "we don't know", not "zero". When the watch does not
        send steps at all (`_last_steps is None`), or stopped sending (the
        last message is older than the window), it is UNKNOWN - not that
        the player stood still (B32). While messages come in, even a zero
        increment is a valid zero.
        """
        if self._last_steps is None:
            return None
        now = time.time() if now is None else float(now)
        if now - self._krok_naposledy > window_s:
            return None                 # steps stopped coming = we don't know
        v_okne = [d for t, d in self._steps if t >= now - window_s]
        if not v_okne:
            return 0.0
        return sum(v_okne) * (60.0 / window_s)

    def clear_live(self):
        """Sensor disconnected - curve and load go, the session summary stays."""
        self._samples.clear()
        self.last_bpm = None
        self._zobraz.clear()
        self.stress = 0.0
        self._raw_stress = 0.0
        self._last_ts = None

    def note_dropout(self, od=None):
        """The heart rate the app heard in this session stopped coming in.

        The app calls it on `disconnected` / `client_gone` - BEFORE
        `clear_live`, and only when the heart rate was really coming in
        before (a dropout before the first sample is not a dropout, that
        is "nothing has arrived yet"). `od` is the time of the last
        sample; without it `last_beat_ts` is taken.

        A second call during the same dropout (the watch drops the TCP
        connection only after `disconnected`) does not count - it is still
        the same dropout.
        """
        if self._slepy_od is not None:
            return
        self.dropouts += 1
        self._slepy_od = float(od) if od is not None else float(self.last_beat_ts)

    def blind_seconds(self, now=None):
        """How many seconds of the session the app was without the heart rate
        it had heard before - including a dropout that is still going on
        (the session is being closed blind)."""
        slepy = self.blind_s
        if self._slepy_od is not None:
            now = time.time() if now is None else float(now)
            slepy += max(0.0, now - self._slepy_od)
        return slepy

    def signal_coverage_at(self, now=None):
        """Share of time since the first sample with heart rate: 0..1, or None.

        A live number for signal quality, with the same gauge as the
        stored `pokrytie_signalu`: time with signal is the sum of the
        zones (each gap at most 5 s, a hole after a dropout nothing) plus
        the currently open interval since the last sample, also at most
        5 s. Without it the number would drop between every two samples
        and jump back at the next one.

        It is measured from the FIRST SAMPLE, not from opening the
        session: waiting until the watch connects is not a weak signal -
        the app shows that separately. The stored coverage counts it,
        because the summary does not have the time of the first sample;
        replaying the threshold does not care (`load_z_krivky` replays the
        sum of the zones).

        None until at least `POKRYTIE_ZIVE_MIN_S` have passed since the
        first sample. Next to it for the same widget: `dropouts` (how many
        times the heart rate dropped out) and `blind_seconds()` (how many
        seconds the app was blind in total).
        """
        if not self._all:
            return None
        now = time.time() if now is None else float(now)
        od_prvej = now - self._all[0][0]
        if not od_prvej >= POKRYTIE_ZIVE_MIN_S:
            return None
        signal = (sum(self.zone_seconds.values())
                  + sum(d for _, d in self._zony_cakaju))
        if self._last_ts is not None:
            # The same cap as in `add`: after 5 s of silence no time is added.
            signal += max(0.0, min(MAX_SAMPLE_GAP_S, now - self._last_ts))
        return max(0.0, min(1.0, signal / od_prvej))

    @property
    def signal_coverage(self):
        """`signal_coverage_at()` now - for the signal quality widget."""
        return self.signal_coverage_at()

    def calm_seconds(self):
        """Seconds of THIS session in the calm zone, or None while unknown.

        The same zone as everywhere (`zone_of_bpm`: heart rate less than
        10 BPM above rest) and the same sum that the "Where the session
        went" panel draws from. None without a single sample - and on the
        first evening, while the app has no baseline: the seconds then
        wait in `_zony_cakaju` and their zone cannot be determined yet (a
        zero would claim you were not calm for even a minute).
        """
        if not self.session_count or self._zony_cakaju:
            return None
        return max(0.0, float(self.zone_seconds.get(ZONE_CALM, 0.0) or 0.0))

    # ---------- derived values ----------

    @property
    def baseline(self):
        """The player's resting baseline. Within a session it may only go DOWN.

        Until there are at least 30 samples we return None: better nothing
        than a baseline computed from 5 seconds of panicked heart rate.

        WHY AN ANCHOR AND NOT A BARE PERCENTILE
        Until 19. 9. it was the 20th percentile of the last 10 minutes, and
        nothing more. That sounds reasonable, but it has one consequence
        that broke the app exactly where it was supposed to be strongest:
        when the heart rate stays up for a long time, the whole ten-minute
        window is high, the baseline follows it up - and `_recompute`
        computes both `over` and `sustained` AGAINST IT. The longer the
        stress lasts, the LESS load the app sees.

        Simulated over this module: a heart rate of 115 BPM held for a
        whole hour at critical_bpm=110 ended with a baseline of 114 and a
        peak load of 21 - i.e. deep below the threshold of 55. Zero cues in
        an hour of sustained stress. Real sessions in hr_sessions.json
        confirm it too.

        The anchor cures this without bringing in a foreign number: the
        baseline is the lowest value the session has seen. When the player
        calms down, it drops with them; when they are stressed, it stays
        down and the load has something to grow against. The upward drift
        is gone, the downward adjustment stayed.

        It carries one limitation and it is fair to admit it: whoever turns
        the app on only in the middle of a fight has a first baseline that
        is too high - until they calm down once. That is why the anchor is
        computed from every sample, not once at the start.
        """
        values = [b for _, b in self._long]
        if len(values) < 30:
            return None
        ziva = _percentile(values, 0.20)
        kotva = self._baseline_kotva
        base = ziva if kotva is None else min(kotva, ziva)
        # The long-term baseline is a CAP, not a replacement: tonight may show
        # that the player is calmer than usual, but not that they are "calm"
        # at 115 BPM just because they have been there for an hour.
        if self.long_baseline:
            base = min(base, float(self.long_baseline))
        return base

    @property
    def is_calibrating(self):
        """The session has no baseline of its own yet - load is not shown yet.

        Calibration happens ONCE PER SESSION: from switching on until 30
        samples arrive (depending on the watch cadence: at ~0.9 s per
        sample just under half a minute, at ~2.9 s roughly a minute and a
        half). While that holds, the HUD and the Today page write
        "calibrating…" and the cue trigger does not arm - the app does
        not state a number it does not trust itself.

        After a dropout longer than `BASELINE_SECONDS` it does NOT
        calibrate again, even though `baseline` then returns None (the
        ten-minute window is empty). The anchor from this evening still
        applies and the load is computed against it (see
        `_zakladna_bez_odhadu`). A second calibration would not be more
        honest, it would just forget what we already know about this
        evening.
        """
        return self._baseline_kotva is None and self.baseline is None

    @property
    def is_settling(self):
        """The heart rate just came back (after a dropout or after the sensor
        was switched on again) and the load is only just getting going -
        the zone is not shown yet.

        `clear_live` throws away the live samples and the load, so after
        the return the smoothed load starts from zero and its "sustained"
        part needs at least 5 samples (`len(window) >= 5` in `_recompute`).
        The first samples would therefore show "Calm" even though the
        heart rate is up. While there are fewer than 5 of them, the HUD and
        Today write a quiet "…" instead of the zone (the same way as
        calibration).

        It is only a patch for a false "Calm": for a few samples after that
        the load may still show less than it really is. The error leans
        towards silence.

        Since C2 the zone word is heart rate relative to rest (`zone`), so
        on its own it would no longer say "Calm". It is still muted because
        of the bar: its length is the load, and that starts from zero after
        the return.
        """
        return 0 < len(self._samples) < 5 and not self.is_calibrating

    def _zakladna_bez_odhadu(self):
        """The baseline the app stands behind - or None.

        Outside calibration it is `baseline`. When that is missing, the
        smaller of these two applies, if we know at least one:

          * the session anchor - after a long dropout. Before, the minimum
            of the new samples was taken here: after 12 minutes without the
            watch and a return at 85 BPM the baseline jumped from 62 to 85
            and the load showed zero. The anchor may only go down within a
            session; so it cannot be bypassed here either.
          * the long-term baseline from previous evenings - `baseline` is
            capped from above by it, so the transition from calibration to
            the live baseline only goes DOWN.

        The minimum of the first seconds deliberately does not belong here.
        It is a rough estimate (one misread sample at 50 BPM and everything
        else looks like load) and the transition from it to the live
        baseline goes UP. The load is not computed against it at all -
        during calibration nobody sees it anyway.
        """
        base = self.baseline
        if base is not None:
            return base
        znama = [float(x) for x in (self._baseline_kotva, self.long_baseline) if x]
        return min(znama) if znama else None

    @property
    def zone(self):
        """The zone RIGHT NOW - one word and one colour for the HUD, Today and
        the heart rate indicator. It is computed only here; drawing
        functions get it ready-made and have no zone boundary of their own.

        It is HEART RATE relative to REST, not load: `zone_of_bpm` over the
        median of the last `ZONE_MEDIAN_SAMPLES` samples and over the same
        baseline that the load is computed against (`_zakladna_bez_odhadu`).
        Raised from rest + 10, high from + 25, critical from the measured
        high heart rate limit (`critical_bpm`). The same zones are computed
        by the "Where the session went" panel, the session trace and
        History - so "High" means one thing on one page.

        WHY NOT LOAD ZONES (25/50/75), as until 0.2
        At rest 76 and a limit of 109, a steady 95 BPM gives a load of
        about 57 - and that was "High" at a heart rate that the app, on the
        same page, counted as "raised" in the "Where the session went"
        panel. The load number, the bar length, the trigger and
        `time_high_s` do not change because of this; only the word and the
        colour change.

        Without heart rate or without a baseline it returns calm. Callers
        do not read it without a connection, during calibration and after
        the heart rate returns (`is_settling`) - there they have their own
        quiet state, which takes precedence.
        """
        base = self._zakladna_bez_odhadu()
        posledne = sorted(b for _, b in self._samples[-ZONE_MEDIAN_SAMPLES:])
        if base is None or not posledne:
            return ZONE_CALM
        n = len(posledne)
        median = (posledne[n // 2] if n % 2
                  else (posledne[n // 2 - 1] + posledne[n // 2]) / 2.0)
        return zone_of_bpm(median, base, self.critical_bpm)

    @property
    def known_zone(self):
        """The same zone as `zone` - or None when the app does NOT KNOW it.

        For the cue gate (`trigger.CueTrigger.note_load(zona=...)`). `zone`
        without heart rate, without a baseline, during calibration and
        right after the heart rate returns gives "calm" as a quiet fallback
        for the screen; but the gate must not take it as "not critical".
        Where the HUD writes "…", here it is None - and then no cue goes
        out.

        NEVER the load zones (`zone_for`): those are about the bar, not
        about whether the heart rate is above the high heart rate limit.
        """
        if self.is_calibrating or self.is_settling or not self._samples:
            return None
        if self._zakladna_bez_odhadu() is None:
            return None
        return self.zone

    @property
    def average(self):
        if not self.session_count:
            return None
        return self.session_sum / self.session_count

    def series(self, points=90):
        """The last `points` values for the curve on the HUD (old -> new)."""
        values = [b for _, b in self._samples]
        if len(values) <= points:
            return values
        # even thinning, not just truncation - otherwise with a faster watch
        # the curve would show a shorter time span
        step = len(values) / float(points)
        return [values[int(i * step)] for i in range(points)]

    def trace(self, points=CURVE_POINTS):
        """The shape of the WHOLE session (old -> new), thinned to `points`.

        `series()` is the live window of the last three minutes for the
        HUD; this is the whole evening for the "session trace" on the
        Today page. These are two different questions, hence two methods.
        """
        return downsample([b for _, b in self._all], points)

    @property
    def display_bpm(self):
        """Heart rate number for the screen (HUD, Today, label by the switch) -
        a whole number, or None while the app has no heart rate.

        Median of the samples over the last `ZOBRAZ_OKNO_S` seconds, always
        at least the last one. The window is measured from the LAST
        SAMPLE, not from the clock: between two messages the number stands
        still and does not drift away by itself. Measurement does not read
        this - `last_bpm` and everything else stays on the raw samples.
        """
        if self.last_bpm is None:
            return None
        if not self._zobraz:
            # `last_bpm` with no sample in the window (set from outside) -
            # at least that.
            return int(round(self.last_bpm))
        posledna = self._zobraz[-1][0]
        # `0 <=`: if the PC clock moved backwards, older samples "from the
        # future" are not counted - the last sample always stays in the window.
        okno = sorted(b for t, b in self._zobraz
                      if 0.0 <= posledna - t < ZOBRAZ_OKNO_S)
        n = len(okno)
        median = (okno[n // 2] if n % 2
                  else (okno[n // 2 - 1] + okno[n // 2]) / 2.0)
        return int(round(median))

    def beat_phase(self, now=None):
        """0..1 beat phase - so the HUD heart beats in the real rhythm."""
        if not self.last_bpm:
            return 0.0
        now = now or time.time()
        period = 60.0 / max(30.0, self.last_bpm)
        return ((now - self.last_beat_ts) % period) / period

    def _recompute(self, now):
        # Without a baseline the app stands behind (the first seconds of the
        # first evening), the load is not computed - it stays where it was. The
        # smoothed average then gets going only from the real baseline, not
        # from an estimate from the minimum.
        base = self._zakladna_bez_odhadu()
        if not base:
            return

        headroom = max(12.0, float(self.critical_bpm) - base)
        over = (self.last_bpm - base) / headroom
        over = max(0.0, min(1.25, over))

        recent = [(t, b) for t, b in self._samples if t >= now - SLOPE_WINDOW_S]
        slope = 0.0
        if len(recent) >= 3:
            span = recent[-1][0] - recent[0][0]
            if span > 2.0:
                per_min = (recent[-1][1] - recent[0][1]) * 60.0 / span
                slope = max(0.0, min(1.0, per_min / 25.0))

        window = [(t, b) for t, b in self._samples if t >= now - SUSTAINED_WINDOW_S]
        sustained = 0.0
        if len(window) >= 5:
            above = sum(1 for _, b in window if b > base + 10.0)
            sustained = above / float(len(window))

        raw = 100.0 * min(1.0, 0.55 * over + 0.20 * slope + 0.25 * sustained)
        self._raw_stress = raw
        self.stress = self.stress + (raw - self.stress) * SMOOTHING

    # ---------- derived metrics of the whole session ----------

    def hrr_events(self):
        return heart_rate_recovery(self._all)

    def _cached(self, name, fn, every=30):
        """HRR/HRPI are asked for every second (the Today page), but they are
        computed from the whole session - at 4 hours that is tens of
        thousands of samples. So we recompute them at most once per
        `every` new samples."""
        cache = getattr(self, "_metric_cache", None)
        if cache is None:
            cache = self._metric_cache = {}
        hit = cache.get(name)
        if hit is None or self.session_count - hit[0] >= every:
            hit = (self.session_count, fn())
            cache[name] = hit
        return hit[1]

    @property
    def hrr(self):
        """Recovery after the session's highest peak (BPM), None if none yet."""
        return self._cached("hrr", lambda: hrr_headline(self.hrr_events()))

    @property
    def hrpi(self):
        return self._cached("hrpi", lambda: persistence_index(self._all))

    @property
    def session_baseline(self):
        return session_baseline(self._all)

    # ---------- summary ----------

    def _zony_do_suhrnu(self):
        """The session ended while still calibrating: the set-aside seconds are
        credited against the minimum (the original behaviour), so that the
        sum matches the duration."""
        out = dict(self.zone_seconds)
        if self._zony_cakaju:
            base = min(b for b, _ in self._zony_cakaju)
            for b, d in self._zony_cakaju:
                out[zone_of_bpm(b, base, self.critical_bpm)] += d
        return out

    def summary(self, koniec=None):
        """Session summary. `koniec` (time) = the session ended before now -
        the last tick before the PC went to sleep
        (`app._rozdel_relaciu_po_medzere`, 0.3). Without it the duration
        is counted up to this moment, as before."""
        teraz = time.time() if koniec is None else float(koniec)
        elapsed = max(0.0, teraz - self.session_start)
        events = self.hrr_events()          # always fresh here, not from the cache
        base = self.session_baseline
        return {
            "started": self.session_start,
            "duration_s": round(elapsed, 1),
            "min_bpm": int(self.session_min) if self.session_min else None,
            "avg_bpm": int(round(self.average)) if self.average else None,
            "max_bpm": int(self.session_max) if self.session_max else None,
            "time_over_s": round(self.time_over, 1),
            "time_high_s": round(self.time_high, 1),
            "peak_stress": int(round(self.peak_stress)),
            "triggers": self.triggers,
            "auto_triggers": self.auto_triggers,
            "critical_bpm": self.critical_bpm,
            "samples": self.session_count,
            # How often the watch sent (see `kadencia_vzoriek`) - three
            # aggregates, not a curve of the gaps.
            **kadencia_vzoriek(self._all),
            # Heart rate dropouts: how many times and how many seconds in
            # total the app was blind (see `note_dropout`). A dropout that
            # is still going on at closing is counted up to this moment.
            "dropouts": self.dropouts,
            "blind_s": round(self.blind_seconds(now=teraz), 1),
            # new metrics from plain BPM (see the module header)
            "baseline_bpm": int(round(base)) if base else None,
            "zone_seconds": {z: round(s, 1) for z, s in self._zony_do_suhrnu().items()},
            "hrr_bpm": hrr_headline(events),
            "hrr_events": len(events),
            "hrpi": persistence_index(self._all),
            "trigger_offsets_s": list(self.trigger_offsets),
            # The shape of the session - 120 numbers (~0.5 kB). Without it a
            # session in the history can only be read as a table row; with it
            # it can be LOOKED AT. The zones are recomputed from the curve
            # only when drawing, via `baseline_bpm` and `critical_bpm` above -
            # storing them again would be the same number twice.
            "curve": [int(round(b)) for b in self.trace()],
            # Activity curve next to the heart rate curve - from it one can
            # find out afterwards when the player was really playing and
            # when they sat in a menu. The threshold will be computed from it
            # once there is enough data (see `PRAH_HRANIA`).
            "activity_curve": self.activity_trace(),
        }


# --------------------------------------------------------------------------
# Saving the session history
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Session context
# --------------------------------------------------------------------------

# What was going on during the session. It is NOT about feelings - it is
# for CLEANING THE DATA.
#
# Talking is the worst confounder in this measurement: when you talk, your
# breathing changes and the heart rate goes up. A cue that sounds into
# that looks ineffective, even though it has nothing to do with it.
# Laughing likewise. A grind, on the other hand, keeps the heart rate flat
# for hours.
#
# The ids are ENGLISH and are NOT TRANSLATED - the id goes into the data
# file and must survive a change of the UI language, same as the keys of
# SFX sets and cue categories. Only the label in the UI is translated
# (`session.context.<id>`).
# What was going on WHILE playing.
CONTEXT_DIANIE = ("call", "laugh", "grind", "competitive", "chill")

# What the player had IN THEM. Kept apart on purpose: the first are events
# during the evening, the second is the state the evening started in - and
# they shift completely different things.
#
# WHY IT EXISTS AT ALL: caffeine, nicotine or alcohol before playing push
# the resting baseline up a bit - and otherwise there would be NOTHING
# about it in the data. If thirty evenings like that were collected, the
# variance could not be explained and could not be subtracted either.
#
# Spec 2.1b, B2: "every variable that explains variance reduces n."
# Stimulants are probably the biggest explainable source of variance in
# this measurement - bigger than talking, which the whole dialog was
# created for. `supplement` is deliberately general, not a brand name: the
# app goes into all its languages and a specific pre-workout would mean
# nothing to anyone elsewhere. For the data what matters is that it was a
# stimulant, not which one.
# `food` is here because digestion itself raises the heart rate - a meal
# right before playing shifts the baseline even without any stress.
# `illness` and `exercise_before` were added from the research of
# 2026-09-22 as CONFOUNDERS of the resting baseline (an infection raises
# rest by +10-20 bpm for days; exercise right before playing keeps the
# heart rate settling for 10-30 min and sets the anchor too high). `tired`
# is gone - it was replaced by the finer `sleep` (3 levels, see
# normalize_sleep).
CONTEXT_TELO = ("caffeine", "supplement", "alcohol", "nicotine", "food",
                "illness", "exercise_before")

CONTEXT_IDS = CONTEXT_DIANIE + CONTEXT_TELO


def normalize_context(raw):
    """List of valid context ids, in a fixed order, without duplicates.

    None means something other than an empty list: None = the player has
    not answered yet, [] = they explicitly said "none of these". That is
    why None is not swapped for [].
    """
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return None
    vybrane = {c for c in raw if c in CONTEXT_IDS}
    return [c for c in CONTEXT_IDS if c in vybrane]


# The activity during which the session happened. Self-report in the
# questionnaire: only the player knows whether they played or worked at
# the PC. It is NOT a confounder to be "subtracted" - it is a different
# KIND of evening. We collect the real answer; whether work and play
# differ will be decided from DATA, not by guessing (no separate
# thresholds until there are numbers for it).
ACTIVITY_KINDS = ("play", "work")


def normalize_activity(raw):
    """'play' / 'work' / None (player did not answer). Other values -> None."""
    return raw if raw in ACTIVITY_KINDS else None


# SESSION WORLD (0.2, B3-worlds): "two worlds, one body".
#
# Play and work have separate history, insights and look. Every session
# records, when it is OPENED, the world it started in (`world`, stamped by
# `app._open_hr_session`). The switch in the middle of a session changes
# only the look and the views - a running session is not relabelled.
#
# `activity` stays what it was: the player's answer in the questionnaire.
# It is stored only when they really clicked it, so later one can
# honestly tell "came from the switch" apart from "the player confirmed
# it". When they answered, their word wins.
#
# DELIBERATELY for learning too, not just for history (verified in
# 0.2.1). The question is "Did you play, or work?" - that is a CORRECTION
# of the world, not a remark. Whoever forgot to switch from Work before
# playing answers "I played" and the evening moves to Play INCLUDING the
# critical heart rate and the load threshold (`sessions_in_world` in
# `app._open_hr_session`); conversely a session started in Play and
# answered "I worked" drops out of them.
# The stamp from the start would lie here about what the player was doing
# - and they know it better.
# "A running session stays in the world it started in" holds until the
# questionnaire: the switch in the middle does not relabel it, only the
# player's answer after the end does.
#
# Sessions without a label (older app versions, skipped questionnaire)
# belong to Play by a FIXED rule - not by the "main world", otherwise they
# would move between worlds when it changes. That is why the file is
# never rewritten.
WORLD_DEFAULT = "play"


def session_world(session):
    """Which world the session belongs to: 'play' or 'work'.

    Order: the answer in the questionnaire (`activity`) > the world from
    the session start (`world`) > Play. A broken value behaves as a
    missing one.
    """
    if not isinstance(session, dict):
        return WORLD_DEFAULT
    return (normalize_activity(session.get("activity"))
            or normalize_activity(session.get("world"))
            or WORLD_DEFAULT)


def sessions_in_world(sessions, world):
    """Only the given world's sessions, in original order, minus non-dicts.

    An unknown world is taken as Play (same as `session_world`)."""
    svet = normalize_activity(world) or WORLD_DEFAULT
    return [s for s in (sessions or [])
            if isinstance(s, dict) and session_world(s) == svet]


# The player's own note on the evening. Free text, no interpretation - the
# app only keeps it and shows it. A length cap, so that one record does
# not bloat the file.
NOTE_MAX = 280


def normalize_note(raw):
    """Trimmed free text, or None. Empty/nonsensical input -> None."""
    if not isinstance(raw, str):
        return None
    txt = raw.strip()
    if not txt:
        return None
    return txt[:NOTE_MAX]


# --------------------------------------------------------------------------
# SUBJECTIVE LAYER (research of 2026-09-22): what the HEART RATE DOES NOT
# SEE. Arousal (heart rate) and valence (good/bad) are two INDEPENDENT
# axes. The main evaluation metric is the MISMATCH measured x felt - that is why
# the subjective axes are kept as ordinal ids (like CONTEXT_IDS, they
# survive all languages), not free text.
# Everywhere None != "not chosen" - None = the player did not answer.
# --------------------------------------------------------------------------

# Sleep last night - replaces the binary 'tired'. 3 levels or None.
SLEEP_LEVELS = ("rested", "mid", "broken")


def normalize_sleep(raw):
    """'rested'/'mid'/'broken' or None. Other values -> None."""
    return raw if raw in SLEEP_LEVELS else None


def normalize_felt_load(raw):
    """Perceived load 0-10 (the player's own rating), or None."""
    try:
        v = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return max(0, min(10, v))


def normalize_valence(raw):
    """Valence -2..+2 (bad .. good), or None."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    return v if -2 <= v <= 2 else None


# The body during the peak - EXPERIENCE tiles, multiple choice. NOT
# symptom screening (no severity, no duration, no cardiac term) - it is
# framed as "how it was in the body", not "did you feel sick?". English
# ids because of all the languages.
BODY_PEAK_IDS = ("ok", "flow", "wired", "tense", "sick")


def normalize_body_peak(raw):
    """List of valid ids in a fixed order, or None (did not answer)."""
    if raw is None or not isinstance(raw, (list, tuple, set)):
        return None
    vybrane = {c for c in raw if c in BODY_PEAK_IDS}
    return [c for c in BODY_PEAK_IDS if c in vybrane]


# Verdict about the cue - a direct check of whether the cue does the right
# thing. landed/unneeded/disruptive/agitated when the cue SOUNDED; missed =
# "there was a moment when it should have, and it stayed silent". None =
# did not answer / not applicable.
# `agitated` ("it wound me up", 0.2) separates "it got me worked up"
# (arousal, exactly the worry about feedback) from "it disrupted"
# (attention). Both move the cue ladder one rung lower (`rebrik.py`).
CUE_VERDICTS = ("landed", "unneeded", "disruptive", "agitated", "missed")


def normalize_cue_verdict(raw):
    """One of CUE_VERDICTS or None."""
    return raw if raw in CUE_VERDICTS else None


# CONFOUNDED session: physiologically so skewed that it would poison the
# RESTING BASELINE (the denominator of everything). It is NOT DELETED - it
# stays in the history and in the subjective analysis, it just does NOT
# ENTER the percentile pools (baseline/critical/threshold). Decided by the
# research of 2026-09-22: alcohol (raises rest even the next day),
# illness, physical exertion right before playing.
CONFOUND_TAGS = ("alcohol", "illness", "exercise_before")


def je_confounded(session):
    """True when the resting baseline MUST NOT be learned from the session."""
    if not isinstance(session, dict):
        return True
    ctx = session.get("context") or []
    return any(t in ctx for t in CONFOUND_TAGS)


def attach_context(path, started, context, activity=None, note=None,
                   sleep=None, felt_load=None, valence=None, body_peak=None,
                   cue_verdict=None, log=None, setup=None):
    """Adds context to an already saved session. Returns True on success.

    The session is saved when it closes, the questionnaire asks only after
    that - that is why the record is looked up by `started`. Every case in
    which the context is not saved is WRITTEN via `log` (if given):
    context is the biggest explainable source of variance in the
    measurement, and losing it silently is exactly what the app avoids.
    The caller (`app.save_session_context`) reads the return value and on
    False tells the player (bug B16).
    """
    try:
        if not os.path.exists(path):
            if log:
                log("kontext: súbor relácií neexistuje")
            return False
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            if log:
                log("kontext: súbor relácií nie je zoznam")
            return False
        zmenene = False
        for s in data:
            if isinstance(s, dict) and s.get("started") == started:
                s["context"] = normalize_context(context)
                # Activity (played/worked) and a free note. They are stored
                # only when the player entered them: None = did not answer, we
                # keep the old state. An empty note ("") is an explicit
                # instruction to delete a possible older one.
                akt = normalize_activity(activity)
                if akt is not None:
                    s["activity"] = akt
                pozn = normalize_note(note)
                if pozn is not None:
                    s["note"] = pozn
                elif isinstance(note, str):
                    s.pop("note", None)
                # Subjective layer (sleep, perceived load, valence, body,
                # verdict about the cue). Stored only when the player entered
                # it (None = I leave it as is).
                for kluc, hodnota, norm in (
                        ("sleep", sleep, normalize_sleep),
                        ("felt_load", felt_load, normalize_felt_load),
                        ("valence", valence, normalize_valence),
                        ("body_peak", body_peak, normalize_body_peak),
                        ("cue_verdict", cue_verdict, normalize_cue_verdict)):
                    nova = norm(hodnota)
                    if nova is not None:
                        s[kluc] = nova
                # "Just setting up the app" (0.3, `ciste_relacie`). The chip
                # is a toggle, not several options: True switches it on, False
                # cancels it (the first session after the introduction has it
                # switched on by the app, and a player who really played in it
                # switches it off), None = leave unchanged.
                if setup is True:
                    s["setup"] = True
                elif setup is False:
                    s.pop("setup", None)
                zmenene = True
                break
        if not zmenene:
            # The dialog opens ONLY after the session was saved successfully,
            # so when the session is not found here, it is a real loss
            # (MAX_SESSIONS rotation, `started` mismatch), not a harmless case
            # of a short session.
            if log:
                log("kontext: relácia sa v súbore nenašla (started=%s)" % (started,))
            return False
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        nahrad_subor(tmp, path, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"kontext relacie sa nepodarilo ulozit: {exc}")
        return False


# How many sessions we keep. It used to be 60 - two months of daily
# playing, even though the History page offers a "Year" period; the
# yearly chart thus showed a slice and pretended to be a whole year. At
# ~0.9 kB per session (curve included) 400 sessions are about 350 kB of
# JSON - a year of daily playing fits.
MAX_SESSIONS = 400


def je_ulozitelna(summary):
    """Can the summary be stored as a session? Not under 1 min or 10 samples.

    One rule for both `save_session` and the recovery of an unfinished
    session (`obnov_rozpracovanu`) - recovery must not let into the
    history anything that a normal close would not let through. A broken
    number (None, text) behaves as zero, not as an exception.
    """
    if not isinstance(summary, dict) or not summary:
        return False
    try:
        return (float(summary.get("samples", 0) or 0) >= 10
                and float(summary.get("duration_s", 0) or 0) >= 60)
    except (TypeError, ValueError):
        return False


def _odloz_pokazeny(path):
    """Moves broken `path` aside under `.corrupt-<cas>` so it can be rescued.

    By moving it via `nahrad_subor` (survives a short lock, does NOT
    DELETE the source). When another process holds it longer, at least by
    copying - a held file can be read (like
    `app_prefs.nacitaj_nastavenia`). When even the copy fails and the file
    is still there, it raises the move error: `path` is the ONLY copy and
    the caller must not overwrite it. The write that follows the set-aside
    retries too - if the lock were released only during its retries, the
    write would otherwise overwrite the broken file with no copy (back
    then a bare `os.replace` failed on the same lock and the file
    stayed)."""
    odlozene = "%s.corrupt-%d" % (path, int(time.time()))
    try:
        nahrad_subor(path, odlozene)
        return
    except OSError as exc:
        chyba = exc
    try:
        shutil.copy2(path, odlozene)
        return
    except OSError:
        pass
    if os.path.exists(path):
        raise chyba


def save_session(path, summary, log=None):
    """Adds a session summary to the JSON file (keeps the last MAX_SESSIONS).

    Sessions shorter than a minute or without a single sample are thrown
    away - switching the sensor on and right off is not a "session" and it
    would only add noise to the averages in the overview
    (`je_ulozitelna`).
    """
    if not je_ulozitelna(summary):
        return False
    try:
        data = []
        if os.path.exists(path):
            citatelne = None
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    obsah = json.load(fh)
                if isinstance(obsah, list):
                    citatelne = obsah
            except Exception as exc:
                if log:
                    log(f"HR: história sa nedala prečítať: {exc}")
            if citatelne is not None:
                data = citatelne
            else:
                # THE EXISTING FILE IS BROKEN (unreadable or not a list).
                #
                # Overwriting it with a new session would throw away all the
                # previous evenings FOREVER - and from then on every next one
                # would be lost just as quietly (bug B15). Instead we set it
                # aside as `.corrupt-<čas>`, so it can be rescued, and carry
                # on saving with an empty list.
                #
                # When it cannot be set aside (or copied), `_odloz_pokazeny`
                # raises an error and the session ends up unsaved (the except
                # below -> hr_session_pending.json), not by overwriting the
                # only copy.
                _odloz_pokazeny(path)
                if log:
                    log("HR: pokazený súbor histórie odložený na záchranu")
        data.append(summary)
        if summary.get("recovered"):
            # A session ADDED AFTERWARDS (checkpoint, an unsaved session from
            # before - `obnov_cakajuce`) may be OLDER than the last one in the
            # file: after an unsaved session the next one is saved normally
            # and the earlier one is added only after it. History takes the
            # last one in the file as the newest (detail, table), so it goes
            # to its place by `started`.
            _zarad_poslednu(data)
        data = data[-MAX_SESSIONS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        nahrad_subor(tmp, path, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"HR: session log failed: {exc}")
        return False


def _zarad_poslednu(data):
    """Moves the last item of `data` before sessions that started later.
    The order of the rest is unchanged; without a usable `started` it
    stays at the end."""
    try:
        zaciatok = float(data[-1].get("started"))
    except (AttributeError, IndexError, TypeError, ValueError):
        return
    i = len(data) - 1
    while i > 0:
        try:
            pred = float(data[i - 1].get("started"))
        except (AttributeError, TypeError, ValueError):
            break
        if not pred > zaciatok:          # NaN stays in place too
            break
        i -= 1
    if i < len(data) - 1:
        data.insert(i, data.pop())


# --------------------------------------------------------------------------
# Unfinished session (checkpoint)
# --------------------------------------------------------------------------
#
# WHY: a session is written to hr_sessions.json only when it closes
# (`app._close_hr_session`). An app crash, ending it via Task Manager, a
# power cut or `build.bat`, which kills the running app, thus threw away
# a whole evening. So while a session is open its summary is written here
# every few minutes (the same summary that closing would save) and at the
# next start it is added to the history with `recovered: True`.
#
# The same data as hr_sessions.json, the same folder - "Delete history"
# deletes it too (`data_io.MAZATELNE`).
ROZPRACOVANA_MENO = "hr_session_open.json"
# A session start outside this range is not a real time - the same
# year-2000 limit as on import (`data_io`). A session must not end in the
# future; 5 minutes of tolerance for a shifted clock (time sync after
# start).
ROZPRACOVANA_OD = 946684800.0
ROZPRACOVANA_TOLERANCIA_S = 300.0


def cesta_rozpracovanej(sessions_path):
    """The checkpoint sits next to hr_sessions.json (not fixed in DATA_DIR):
    a test that redirects the history to tmp redirects the checkpoint too."""
    return os.path.join(os.path.dirname(os.path.abspath(sessions_path)),
                        ROZPRACOVANA_MENO)


def zapis_rozpracovanu(sessions_path, summary, log=None):
    """Atomically writes the summary of the open session (.tmp + os.replace).

    A crash in the middle of the write thus leaves the previous checkpoint
    whole, not half a JSON. Returns True on success."""
    cesta = cesta_rozpracovanej(sessions_path)
    tmp = cesta + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False)
        nahrad_subor(tmp, cesta, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"HR: rozpracovaná relácia sa nedala zapísať: {exc}")
        return False


def zahod_rozpracovanu(sessions_path):
    """Deletes the checkpoint (session closed normally). True = it existed."""
    try:
        os.remove(cesta_rozpracovanej(sessions_path))
        return True
    except OSError:
        return False


def _preco_neobnovit(summary, now):
    """The reason why the checkpoint is not a credible session, or None."""
    if not je_ulozitelna(summary):
        return "kratka alebo bez dat"
    try:
        zaciatok = float(summary.get("started"))
        trvanie = float(summary.get("duration_s"))
    except (TypeError, ValueError):
        return "bez casu zaciatku"
    # Upper-bound comparisons catch NaN and infinity too (all are False then).
    if not ROZPRACOVANA_OD <= zaciatok < float("inf"):
        return "nemozny cas zaciatku"
    if not 0.0 <= trvanie < float("inf"):
        return "nemozne trvanie"
    if not zaciatok + trvanie <= now + ROZPRACOVANA_TOLERANCIA_S:
        return "konci v buducnosti"
    return None


def _uz_v_historii(sessions, started):
    for s in sessions or ():
        if not isinstance(s, dict):
            continue
        try:
            if abs(float(s.get("started")) - float(started)) < 1e-3:
                return True
        except (TypeError, ValueError):
            continue
    return False


def obnov_rozpracovanu(sessions_path, now=None, log=None):
    """At start: adds last time's unfinished session to the history. ONCE.

    Returns the saved summary (with `recovered: True`), or None. An
    implausible checkpoint (short, with an impossible time, unreadable) or
    one that is already in the history (the app crashed only after saving
    the session) is deleted without writing - otherwise it would be judged
    again at every start. When writing to the history fails (full disk),
    the file STAYS and it is retried at the next start.
    """
    cesta = cesta_rozpracovanej(sessions_path)
    if not os.path.exists(cesta):
        return None
    now = time.time() if now is None else now
    try:
        with open(cesta, "r", encoding="utf-8") as fh:
            summary = json.load(fh)
    except Exception as exc:
        summary = None
        if log:
            log(f"HR: rozpracovaná relácia sa nedala prečítať: {exc}")
    dovod = _preco_neobnovit(summary, now)
    if dovod is None and _uz_v_historii(load_sessions(sessions_path),
                                        summary.get("started")):
        dovod = "uz je v historii"
    if dovod is not None:
        if log:
            log(f"HR: rozpracovanú reláciu neobnovujem ({dovod})")
        zahod_rozpracovanu(sessions_path)
        return None
    summary["recovered"] = True
    if not save_session(sessions_path, summary, log=log):
        return None
    zahod_rozpracovanu(sessions_path)
    return summary


# --------------------------------------------------------------------------
# Unsaved session (0.3)
# --------------------------------------------------------------------------
#
# WHY: on a write error (full disk, access denied, locked file)
# `save_session` returned False and the session vanished - only a
# technical line was left in the journal. Now its summary is set aside
# here (a list, there may be more of them) and at the next start or after
# the next successful save it is added to the history the same way as the
# checkpoint - with `recovered: True`, so thresholds are not learned from
# it (`ciste_relacie`). The file is deleted only AFTER a successful write.
#
# The same folder as hr_sessions.json - "Delete history" deletes it too
# (`data_io.MAZATELNE`).
CAKAJUCA_MENO = "hr_session_pending.json"


def cesta_cakajucej(sessions_path):
    """Unsaved sessions lie next to hr_sessions.json (like the checkpoint)."""
    return os.path.join(os.path.dirname(os.path.abspath(sessions_path)),
                        CAKAJUCA_MENO)


def nacitaj_cakajuce(sessions_path):
    """List of pending summaries. Unreadable file = empty list."""
    try:
        with open(cesta_cakajucej(sessions_path), "r", encoding="utf-8") as fh:
            obsah = json.load(fh)
    except Exception:
        return []
    if isinstance(obsah, dict):
        obsah = [obsah]
    if not isinstance(obsah, list):
        return []
    return [s for s in obsah if isinstance(s, dict)]


def _zapis_cakajuce(sessions_path, zoznam):
    cesta = cesta_cakajucej(sessions_path)
    if not zoznam:
        try:
            os.remove(cesta)
        except OSError:
            pass
        return True
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(list(zoznam), fh, ensure_ascii=False)
    nahrad_subor(tmp, cesta, uprac_zdroj=True)
    return True


def _odloz_pokazenu_cakajucu(sessions_path, prisne=False):
    """The pending sessions file exists but is unreadable (not a JSON list)?

    Then it is NOT DELETED and NOT OVERWRITTEN - it holds whole evenings
    that are nowhere else. It is set aside as `.corrupt-<cas>` like the
    broken history in `save_session` (`_odloz_pokazeny`), so it can be
    rescued; "Delete history" deletes it too (`data_io` also deletes
    `hr_session_pending.json.*`). Returns True when the file is NOT
    readable (even if setting it aside failed) - then it must not be
    deleted. `prisne=True` (the caller overwrites it right away): when
    neither the move nor the copy works, it raises an error - it must not
    be overwritten."""
    cesta = cesta_cakajucej(sessions_path)
    if not os.path.exists(cesta):
        return False
    try:
        with open(cesta, "r", encoding="utf-8") as fh:
            if isinstance(json.load(fh), (list, dict)):
                return False
    except Exception:
        pass
    try:
        _odloz_pokazeny(cesta)
    except OSError:
        if prisne:
            raise
    return True


def zapis_cakajucu(sessions_path, summary, log=None):
    """Sets aside a summary of a session that failed to save. True on success.

    The same session (the same `started`) is not set aside twice - the
    newer summary replaces the older one. Atomic (.tmp + os.replace). An
    unreadable file from before is not overwritten by the new list, it is
    set aside (`_odloz_pokazenu_cakajucu`)."""
    if not je_ulozitelna(summary):
        return False
    try:
        # strict: an unreadable file that could be neither set aside nor
        # copied would be overwritten by the write below - better False (the
        # checkpoint stays).
        _odloz_pokazenu_cakajucu(sessions_path, prisne=True)
        zoznam = [s for s in nacitaj_cakajuce(sessions_path)
                  if not _uz_v_historii([s], summary.get("started"))]
        zoznam.append(summary)
        return _zapis_cakajuce(sessions_path, zoznam)
    except Exception as exc:
        if log:
            log(f"HR: neuloženú reláciu sa nepodarilo odložiť: {exc}")
        return False


def obnov_cakajuce(sessions_path, now=None, log=None):
    """Adds pending sessions to history. Returns the summaries really saved.

    Each one gets `recovered: True` (thresholds are not learned from it,
    like from the checkpoint). One that is already in the history (the
    same `started`), or an implausible one (`_preco_neobnovit`), is thrown
    away without writing. One that could not be saved even now STAYS in
    the file for the next attempt; the file goes away only when it is
    empty."""
    zoznam = nacitaj_cakajuce(sessions_path)
    if not zoznam:
        # An empty one is deleted; an unreadable one is set aside, not deleted.
        if (os.path.exists(cesta_cakajucej(sessions_path))
                and not _odloz_pokazenu_cakajucu(sessions_path)):
            _zapis_cakajuce(sessions_path, [])
        return []
    now = time.time() if now is None else now
    ulozene, ostava = [], []
    for summary in zoznam:
        dovod = _preco_neobnovit(summary, now)
        if dovod is None and _uz_v_historii(load_sessions(sessions_path),
                                            summary.get("started")):
            dovod = "uz je v historii"
        if dovod is not None:
            if log:
                log(f"HR: neuloženú reláciu nedopĺňam ({dovod})")
            continue
        summary["recovered"] = True
        if save_session(sessions_path, summary, log=log):
            ulozene.append(summary)
        else:
            ostava.append(summary)
    try:
        _zapis_cakajuce(sessions_path, ostava)
    except Exception as exc:
        if log:
            log(f"HR: zoznam neuložených relácií sa nedal prepísať: {exc}")
    return ulozene


def delete_session(path, started, log=None):
    """Deletes ONE session from the history (by `started`). True = deleted.

    The detail in History ("Delete this session", 0.3): e.g. a 14-hour
    "session" over a sleeping PC, which otherwise pushes the sleeping heart
    rate into the resting baseline. Atomic (.tmp + os.replace); an
    unreadable file is NOT OVERWRITTEN - better nothing than throwing away
    the whole history."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        if log:
            log(f"HR: história sa nedala prečítať: {exc}")
        return False
    if not isinstance(data, list):
        return False
    ostava = [s for s in data
              if not (isinstance(s, dict) and _uz_v_historii([s], started))]
    if len(ostava) == len(data):
        return False
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(ostava, fh, ensure_ascii=False, indent=2)
        nahrad_subor(tmp, path, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"HR: reláciu sa nepodarilo zmazať: {exc}")
        return False


# --------------------------------------------------------------------------
# Export to a spreadsheet
# --------------------------------------------------------------------------

# WHY CSV AND NOT .xlsx
# Excel opens CSV with a double click just like its own format, so for the
# player it is the same - but the app needs no extra library for it, and
# so nothing extra in the build either (openpyxl is ~2 MB and another part
# that can break in the packaged app). It does need two things, though,
# otherwise Excel in central Europe opens it as one column:
#   * a SEMICOLON separator (in a locale with a decimal comma, that is the
#     one),
#   * a BOM at the start, otherwise Excel reads the file as ANSI and
#     mangles the diacritics.
CSV_SEPARATOR = ";"
CSV_COLUMNS = ("date", "start", "duration_min", "avg_bpm", "min_bpm", "max_bpm",
               "baseline_bpm", "over_min", "breathing", "peak_stress",
               "hrr_bpm", "hrpi", "calm_min", "raised_min", "high_min",
               "critical_min",
               # WHY IT DID (NOT) SPEAK UP. Without these columns "0 cues" is
               # just a statement: there would be no way to tell "the body was
               # not up" from "it was, but not long enough" and from "the heart
               # rate kept dropping out".
               "longest_above_s", "above_runs", "cancelled_dip",
               "cancelled_gap", "hold_s",
               # What the player said about the evening (caffeine, alcohol,
               # a call...). The biggest explainable source of variance in the
               # whole measurement.
               "context",
               # Activity (played/worked), what % of the session the HUD was
               # visible (biofeedback - a heart rate that is seen gets
               # regulated subconsciously) and the player's free note. Real
               # data for telling evenings apart, not guesses.
               "activity", "hud_seen", "note",
               # Subjective layer (research of 2026-09-22): sleep, perceived
               # load 0-10, valence, body during the peak, verdict about the
               # cue. Main evaluation = the MISMATCH measured (heart rate) x
               # felt (these). `confounded` = whether the session was kept OUT
               # of baseline learning (alcohol/illness/exertion).
               "sleep", "felt_load", "valence", "body_peak", "cue_verdict",
               "confounded",
               # Signal coverage (0.2): what share of the session the heart
               # rate really came in (`pokrytie_signalu`). At the END, not
               # next to the zones it is computed from: the columns before it
               # thus stay in their places for anyone who already processes
               # the export by column order.
               "signal",
               # 0.2, also at the end for the same reason: the session world
               # (`session_world` - the same one History sorts it by), how
               # many times the heart rate dropped out and how many seconds
               # the app was blind, and how many pauses in input it saw per
               # session (the cue gate waits for them). Old sessions do not
               # have them - an empty cell.
               "world", "dropouts", "blind_s", "pause_episodes")


def _csv_cell(value, decimals=1):
    """A number with a decimal COMMA (otherwise Excel in SK/CZ sees text),
    empty for a missing value."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",")
    return str(value)


def _csv_context(ctx):
    """Session context into a cell. It distinguishes three states (B20):

      None -> the player did not answer  (empty)
      []   -> "none of these happened"  (dash)
      [..] -> listed items
    """
    if ctx is None:
        return ""
    if not ctx:
        return "-"
    return " ".join(ctx)


def _csv_hud_seen(summary):
    """What % of the session the HUD was visible, or empty (an old session
    does not have that number). A whole percent - easier to read in CSV
    than a fraction."""
    frac = summary.get("hud_visible_frac")
    if frac is None:
        return ""
    try:
        return f"{round(float(frac) * 100)}%"
    except (TypeError, ValueError):
        return ""


def _csv_signal(summary):
    """Signal coverage in whole percent ("97%"), or empty when unknown (a
    session without zones). The same form as `hud_seen`."""
    pokrytie = pokrytie_signalu(summary)
    if pokrytie is None:
        return ""
    return f"{round(pokrytie * 100)}%"


def _csv_pocet(value):
    """A non-negative count (dropouts, pauses) as a whole number, or empty
    when the session does not have it or it is broken (import, manual
    edit)."""
    v = _cislo(value)
    if v is None or v < 0:
        return ""
    return str(int(v))


def _csv_sekundy(value):
    """Non-negative seconds with a decimal comma, or empty."""
    v = _cislo(value)
    if v is None or v < 0:
        return ""
    return _csv_cell(v)


def _csv_note(note):
    """Free note into a cell. `;` is the column separator and a newline breaks
    the CSV row - both are replaced so that one note does not wreck the
    table."""
    if not note:
        return ""
    return str(note).replace(";", ",").replace("\n", " ").replace("\r", " ")


def session_row(summary):
    """One session as a list of cells in `CSV_COLUMNS` order."""
    started = summary.get("started")
    when = datetime.fromtimestamp(started) if started else None
    zones = summary.get("zone_seconds") or {}

    def minutes(seconds):
        try:
            return float(seconds or 0.0) / 60.0
        except (TypeError, ValueError):
            return 0.0

    return [
        when.strftime("%d.%m.%Y") if when else "",
        when.strftime("%H:%M") if when else "",
        _csv_cell(minutes(summary.get("duration_s"))),
        _csv_cell(summary.get("avg_bpm")),
        _csv_cell(summary.get("min_bpm")),
        _csv_cell(summary.get("max_bpm")),
        _csv_cell(summary.get("baseline_bpm")),
        _csv_cell(minutes(summary.get("time_over_s"))),
        # The same number as the table, detail and chart of History.
        _csv_cell(hlasky_relacie(summary)),
        _csv_cell(summary.get("peak_stress")),
        _csv_cell(summary.get("hrr_bpm")),
        _csv_cell(summary.get("hrpi")),
        _csv_cell(minutes(zones.get(ZONE_CALM))),
        _csv_cell(minutes(zones.get(ZONE_RAISED))),
        _csv_cell(minutes(zones.get(ZONE_HIGH))),
        _csv_cell(minutes(zones.get(ZONE_CRITICAL))),
        _csv_cell(summary.get("longest_above_s")),
        _csv_cell(summary.get("above_runs")),
        _csv_cell(summary.get("runs_cancelled_dip")),
        _csv_cell(summary.get("runs_cancelled_gap")),
        _csv_cell(summary.get("stress_hold_s")),
        # None = the player did not answer, [] = "none of these" - two
        # different things, guarded elsewhere by their own test. CSV merged
        # them into an empty cell (B20).
        _csv_context(summary.get("context")),
        # Via normalize_activity: it guarantees a string ('play'/'work'/''),
        # so not even a number/nonsense from an imported or hand-edited
        # session brings down the WHOLE export (otherwise this was the only
        # cell here that did not go through the sanitizer).
        normalize_activity(summary.get("activity")) or "",
        _csv_hud_seen(summary),
        _csv_note(summary.get("note")),
        # Subjective layer - everything through the normalisers, so that a
        # bad import does not bring down the export (the same safeguard as for
        # activity).
        normalize_sleep(summary.get("sleep")) or "",
        _csv_cell(normalize_felt_load(summary.get("felt_load"))),
        _csv_cell(normalize_valence(summary.get("valence"))),
        _csv_context(normalize_body_peak(summary.get("body_peak"))),
        normalize_cue_verdict(summary.get("cue_verdict")) or "",
        "áno" if je_confounded(summary) else "",
        _csv_signal(summary),
        session_world(summary),
        _csv_pocet(summary.get("dropouts")),
        _csv_sekundy(summary.get("blind_s")),
        _csv_pocet(summary.get("pause_episodes")),
    ]


def export_sessions_csv(sessions, path, headers=None):
    """Writes sessions to a CSV for Excel. Returns the number of rows written.

    `headers` are translated column names in `CSV_COLUMNS` order; without
    them the English keys are used (the module does not deal with
    translations).
    """
    rows = sorted((s for s in sessions or [] if isinstance(s, dict)),
                  key=lambda s: float(s.get("started") or 0))
    names = list(headers) if headers else list(CSV_COLUMNS)
    lines = [CSV_SEPARATOR.join(names)]
    for summary in rows:
        lines.append(CSV_SEPARATOR.join(session_row(summary)))
    tmp = path + ".tmp"
    # utf-8-sig = UTF-8 with BOM; without it Excel ate the diacritics
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
    nahrad_subor(tmp, path, uprac_zdroj=True)
    return len(rows)


def load_sessions(path, log=None):
    # "The file does not exist" = the player has not measured anything
    # yet; that is fine and quiet.
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if log:
            log("HR: súbor histórie nie je zoznam")
    except Exception as exc:
        # WARNING: an empty list here means "COULD NOT BE READ", not "no
        # sessions". Without a record History would claim you measured
        # nothing, even though a file with months of data lies next to it
        # (bug B15). At the next session `save_session` sets the broken file
        # aside and starts clean.
        if log:
            log(f"HR: história sa nedala prečítať: {exc}")
    return []
