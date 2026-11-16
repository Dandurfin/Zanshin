"""Measurement windows around a cue - what the body did before and after it.

WHY THIS EXISTS
---------------
Without measuring you cannot say whether a cue does anything. And it is very
easy to measure it badly: a cue fires exactly when the heart rate is up, and
the heart rate also comes back down on its own. So when "before" and "after"
are compared without a control, the result is "it works" every time - even
if the app stayed silent. That is why every window is written with an arm
(`arm`), so the silent arm can be compared with the voice arm. The silent
arm is already LIVE (drawn by `trigger.CueTrigger`): some armings are
deliberately not delivered by voice, only visually, and are measured the
same way - otherwise "it works" would always come out.

WINDOW SHAPE
------------
    -60 s          0        +10 s              +70 s        +180 s
      |----pre----| cue  |--dead time--|----post----|--durability--|

The +10 s dead time is there so that "after" does not include the state
still running out from the moment of the cue - at least one whole breathing
cycle.

WHAT INVALIDATES A WINDOW
-------------------------
  * refractory zone - if another cue sounded within -60/+180 s, it is
    impossible to say which of them caused what; the same for the ring at
    high heart rate on screen within -60/+180 s
  * a gap in the data - the sensor dropped out; `HeartStats.clear_live()`
    clears only the live curve, `_all` keeps growing, so the gap is NOT
    marked by anything and can only be found from timestamp differences
  * a shortened window - the cue came less than 60 s after the session
    start, or the session ended before +180 s passed

An invalid window is WRITTEN, not thrown away - with the reason in
`reasons`. In the first evenings it will matter more to see how many windows
failed and why than to have a clean file. Filtering happens only during
analysis (`valid=True`).

The module is purely data: no Tk, no I/O except saving at the end, the same
as `hr_stats.py`. All calculations are pure functions over
`[(timestamp, hodnota)]`, so they can be tested without a display.
"""

import json
import os

from paths import nahrad_subor

# --------------------------------------------------------------------------
# Window dimensions (seconds). The starting values come from the literature,
# not from a specific player's body - they will be tuned in the first
# evenings, which is why they are in one place.
# --------------------------------------------------------------------------

PRE_S = 60.0                 # -60 .. 0
DEAD_S = 10.0                # 0 .. +10   dead time (one breathing cycle)
POST_S = 70.0                # +10 .. +70
DURABILITY_S = 180.0         # +70 .. +180 (optional)

REFRACTORY_BEFORE_S = 60.0
REFRACTORY_AFTER_S = 180.0

# A longer gap between samples = sensor dropout. THE SAME NUMBER as
# `trigger.DIERA_S` (= `heart_rate.HeartRateMonitor.STALE_AFTER_S`, 12 s) -
# a test guards it. Not imported: `trigger` imports `measure`.
#
# It used to be 5 s here (like `hr_stats.MAX_SAMPLE_GAP_S`, which however
# is the cap of CREDIT for one gap, not a dropout limit). Since 20. 9. the
# watch sends the heart rate every ~2.9 s and one lost packet is a gap of
# ~5.6 s - so almost every measurement window got `diera_v_datach`,
# although neither the app nor the trigger consider it a dropout and the
# HUD showed the heart rate the whole time.
MAX_GAP_S = 12.0

# Below this many milliseconds since the last input we consider the player
# active.
ACTIVE_IDLE_MS = 1000

# Cue categories. They are the same four somatic visuals that the app draws
# into the game (`hud_paint.render_slot_icon`) and that correspond to slots
# 0-3. The names are English and are NOT TRANSLATED - the category id goes
# into the data file and must survive a change of the UI language, just
# like the SFX set keys.
CATEGORIES = ("grounding", "jaw", "release", "breath")


def next_slot(available, last=None):
    """Which slot should sound now. Returns an index or None.

    WHY ROTATION
    ------------
    Until 18. 9. the app ALWAYS played one fixed slot (the breathing one).
    That has one strong property - all measurement windows are from one
    category, so they can be compared without another variable - and one
    fatal one: the same sentence a hundred times an evening stops working.
    Habituation is exactly what the whole app stands against.

    WHY ROUND-ROBIN AND NOT RANDOM
    ------------------------------
    A random choice would sometimes repeat the same category three times
    in a row and not let another one through at all for a whole evening.
    Rotating in a circle keeps the categories EVENLY represented, which is
    also what the analysis needs: each has a similar number of windows.

    WHAT IT COSTS
    -------------
    The windows are no longer from one category, so between-category
    variance enters the effect estimate. But it is not a loss: the
    category is written into the window (`category_for_slot`), so phase 8
    will have the data to split them - and it collects it from TODAY, not
    only from when phase 8 opens.

    `available` are the indexes of the ENABLED slots. When only one is
    enabled, it is returned - repetition cannot be avoided then.
    """
    zoznam = sorted({int(i) for i in (available or [])})
    if not zoznam:
        return None
    if last is None or int(last) not in zoznam:
        return zoznam[0]
    kde = zoznam.index(int(last))
    return zoznam[(kde + 1) % len(zoznam)]


def category_for_slot(index):
    """Category for slot 0-3, or None for anything else."""
    try:
        index = int(index)
    except (TypeError, ValueError):
        return None
    return CATEGORIES[index] if 0 <= index < len(CATEGORIES) else None


# Reasons why a window is not valid.
# Share of time with keyboard/mouse input below which the window is not
# valid.
#
# `pre_activity` and `post_activity` were written from the start, but had no
# effect on the window's validity - and that was a hole. When the player
# gets up and goes for a coffee, their heart rate rises from WALKING, not
# from the game: the app sees it as load, speaks up, and after they come
# back and sit down the heart rate drops. Such a window looks like an
# effective cue, while it measures nothing but the fact that the person sat
# down.
#
# 0.25 is deliberately low: a micro-pause at the desk barely changes the
# share (the windows are 60 s before and 180 s after), while leaving the PC
# drops it to zero.
MIN_AKTIVITA = 0.25

R_NEAKTIVNY = "nebol_pri_klavesnici"
R_REFRACTORY = "refraktern_zona"
R_GAP = "diera_v_datach"
R_PRE_SHORT = "skratene_pred"
R_POST_SHORT = "skratene_po"
R_NO_DATA = "ziadne_data"
# The visual was not drawn (the only stimulus of the silent arm). The window
# would measure the cue against nothing, so we exclude it (bug B17).
R_NEDORUCENE = "nedorucene"
# The ring at high heart rate (`app_session._tick_high_hr_ring`, off by
# default) was on screen within the cue's refractory span: a second
# stimulus, so it is impossible to say which of them did what - the same
# reason as `R_REFRACTORY`, only the other stimulus is not a cue.
R_KRUH_TEP = "kruh_pri_vysokom_tepe"


# --------------------------------------------------------------------------
# Pure calculations over [(timestamp, value)]
# --------------------------------------------------------------------------

def slice_span(series, t0, t1):
    """Samples with time in <t0, t1) - the start is inside, the end is not.

    Half-open on purpose, for two reasons:

      * a sample exactly at the moment of the cue belongs neither to
        "before" nor to "after" - it is the moment of intervention. With a
        pre-window <-60, 0> it would otherwise leak in and pull the mean by
        exactly the number that triggered the cue,
      * the post-window ends where durability begins (+70 s). With closed
        intervals a sample on the boundary would be counted twice.

    Assumes increasing times.
    """
    return [(ts, v) for ts, v in series if t0 <= ts < t1]


def mean_in(series, t0, t1):
    """Mean of the values in the interval, or None when it is empty."""
    values = [v for _, v in slice_span(series, t0, t1)]
    if not values:
        return None
    return sum(values) / float(len(values))


def gaps(series, t0, t1):
    """(gap at the start, largest gap inside, gap at the end).

    These three are told apart on purpose, because they mean different
    things:

      * a gap at the START of the pre-window = the session began only
        during it, i.e. the window is SHORTENED (the cue came less than
        60 s after switching on),
      * a gap at the END of the post-window = the session ended early,
        also shortened,
      * a gap INSIDE = the sensor dropped out; `clear_live()` does not
        mark it in any way, so it can only be found here.

    If all three were added up into one number, a shortened window would
    be reported as a sensor dropout and in the first evenings it would be
    impossible to tell whether the fault is in the watch or only in the
    session being short.
    """
    inside = slice_span(series, t0, t1)
    if not inside:
        return (t1 - t0, 0.0, 0.0)
    inner = 0.0
    for i in range(len(inside) - 1):
        inner = max(inner, inside[i + 1][0] - inside[i][0])
    return (inside[0][0] - t0, inner, t1 - inside[-1][0])


def active_share(activity, t0, t1, active_idle_ms=ACTIVE_IDLE_MS):
    """Share of samples in the interval where the player was active (0.0-1.0).

    It is deliberately coarse: "how much they were doing in that window",
    not what they were doing.
    `activity` is [(timestamp, idle_ms)] from `activity.ActivityTracker`.
    """
    inside = slice_span(activity, t0, t1)
    if not inside:
        return None
    active = sum(1 for _, idle in inside if idle is not None and idle < active_idle_ms)
    return active / float(len(inside))


def refractory_conflict(ts, other_ts,
                        before=REFRACTORY_BEFORE_S, after=REFRACTORY_AFTER_S):
    """Did another cue sound in this cue's refractory zone?

    `other_ts` are the times of ALL cues of the session including this
    one - its own time is skipped by an equality comparison, so the
    caller does not have to filter anything.
    """
    for other in other_ts:
        if other == ts:
            continue
        if ts - before <= other <= ts + after:
            return True
    return False


def ring_conflict(ts, ring_spans,
                  before=REFRACTORY_BEFORE_S, after=REFRACTORY_AFTER_S):
    """Was the ring at high heart rate on screen anywhere in this cue's
    refractory span [ts - before, ts + after]?

    `ring_spans` are its showings as (start, end). The edges count, as in
    `refractory_conflict`: a showing that ends exactly at ts - 60 or starts
    exactly at ts + 180 still touches the window. A broken span (not two
    numbers) is skipped."""
    lo, hi = ts - before, ts + after
    for span in ring_spans or ():
        try:
            a, b = float(span[0]), float(span[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if a != a or b != b:            # NaN
            continue
        if min(a, b) <= hi and max(a, b) >= lo:
            return True
    return False


# --------------------------------------------------------------------------
# Building a window
# --------------------------------------------------------------------------

def build_window(cue, samples, all_cue_ts, activity=None,
                 session_started=None, game=None, ring_spans=None):
    """One measurement window around one cue.

    `cue` is a record from `HeartStats.cues`:
    {ts, category, cue_id, arm, source}.
    `samples` is [(timestamp, bpm)], `activity` is [(timestamp, idle_ms)].
    `ring_spans` are the showings of the ring at high heart rate as
    [(start, end)] - None or empty when it was not shown (the window is
    then exactly what it was before the ring existed).
    Always returns a dict - even when the window is invalid, so that it is
    possible to count how many windows dropped out and why.
    """
    ts = float(cue["ts"])
    reasons = []

    pre_a, pre_b = ts - PRE_S, ts
    post_a, post_b = ts + DEAD_S, ts + POST_S
    dur_a, dur_b = ts + POST_S, ts + DURABILITY_S

    pre_bpm = mean_in(samples, pre_a, pre_b)
    post_bpm = mean_in(samples, post_a, post_b)
    dur_bpm = mean_in(samples, dur_a, dur_b)

    if pre_bpm is None and post_bpm is None:
        reasons.append(R_NO_DATA)
    else:
        # Durability (+70..+180) is optional, its gaps do not invalidate the
        # window.
        pre_start, pre_inner, pre_end = gaps(samples, pre_a, pre_b)
        post_start, post_inner, post_end = gaps(samples, post_a, post_b)

        if pre_bpm is None or pre_start > MAX_GAP_S:
            reasons.append(R_PRE_SHORT)      # the session began only in the pre-window
        if post_bpm is None or post_end > MAX_GAP_S:
            reasons.append(R_POST_SHORT)     # the session ended in the post-window
        # R_GAP = the sensor dropped out IN THE MIDDLE, i.e. a gap surrounded
        # by data. An empty side is not a gap but a SHORTENED window (already
        # marked above). Without this condition an empty post-window got,
        # besides the correct `skratene_po`, also a false `diera_v_datach`: for
        # an empty window `gaps()` returns (whole range, 0, 0), i.e.
        # `post_start` = the whole range. While debugging, it claimed the watch
        # had dropped out, although the player had just finished playing (B5).
        diery = []
        if pre_bpm is not None:
            diery += [pre_inner, pre_end]
        if post_bpm is not None:
            diery += [post_start, post_inner]
        if diery and max(diery) > MAX_GAP_S:
            reasons.append(R_GAP)            # the sensor dropped out in the middle

    if refractory_conflict(ts, all_cue_ts):
        reasons.append(R_REFRACTORY)
    if ring_spans and ring_conflict(ts, ring_spans):
        reasons.append(R_KRUH_TEP)

    # The visual was not drawn? `is False`, not `not`: old records do not have
    # the `delivered` field (None = we do not know) and those must not be
    # invalidated retroactively - the same rule as for activity.
    if cue.get("delivered") is False:
        reasons.append(R_NEDORUCENE)

    # Was the player at the computer at all? Low activity BEFORE the cue means
    # that the raised heart rate did not come from playing; low activity AFTER
    # it means that the drop does not measure the cue's effect, but the fact
    # that the person came back and sat down.
    # The window is not thrown away - it is written with a reason and is left
    # out of the effectiveness.
    pre_act = active_share(activity or [], pre_a, pre_b)
    post_act = active_share(activity or [], post_a, post_b)
    # `None` means "we do not know" (an old session, or activity was not
    # tracked), not "was away". Not knowing must not invalidate the window -
    # otherwise the whole history that did not record activity yet would be
    # thrown away retroactively.
    if ((pre_act is not None and pre_act < MIN_AKTIVITA)
            or (post_act is not None and post_act < MIN_AKTIVITA)):
        reasons.append(R_NEAKTIVNY)

    window = {
        "ts": round(ts, 1),
        "arm": cue.get("arm", "voice"),
        "source": cue.get("source", "auto"),
        "category": cue.get("category"),
        "cue_id": cue.get("cue_id"),
        # DIFFERENT things: `arm` is the drawn arm (voice/silent), `delivery`
        # is the way of delivery (pause/timeout). They must not be merged, but
        # both must be in the window - otherwise the pause threshold cannot be
        # checked against the measurements.
        "delivery": cue.get("delivery"),
        "pre_bpm": _round(pre_bpm),
        "post_bpm": _round(post_bpm),
        "durability_bpm": _round(dur_bpm),
        "pre_load": _round(mean_in(cue.get("load_series") or [], pre_a, pre_b)),
        "post_load": _round(mean_in(cue.get("load_series") or [], post_a, post_b)),
        "pre_activity": _round(pre_act, 3),
        "post_activity": _round(post_act, 3),
        "valid": not reasons,
        "reasons": reasons,
    }
    # DELIVERY RECORD (0.2, ladder + gate): the ladder rung, whether something
    # really sounded, the load at delivery and its peak since arming, the
    # heart-rate zone and how many seconds after the cue "not now" came. Only
    # when the cue record has them - older records do not and the window is
    # built anyway.
    for kluc in ("rung", "audible", "load_at", "load_peak", "zone_at",
                 "snooze_after_s"):
        if cue.get(kluc) is not None:
            window[kluc] = cue[kluc]
    if session_started is not None:
        window["session_started"] = round(float(session_started), 1)
        window["offset_s"] = round(ts - float(session_started), 1)
    if game:
        window["game"] = game
    return window


def _round(value, decimals=1):
    return None if value is None else round(float(value), decimals)


def build_windows(cues, samples, load=None, activity=None,
                  session_started=None, game=None, ring_spans=None):
    """Measurement windows for all cues of one session.

    Called once, when the session closes - by then `samples` is complete
    and nothing needs timing. It also means that the window of the last
    cue may be shortened if the session ended earlier than +70 s; such a
    window is written with a reason, not thrown away.

    `ring_spans`: the session's showings of the ring at high heart rate,
    see `build_window`.
    """
    cues = sorted(cues, key=lambda c: float(c["ts"]))
    all_ts = [float(c["ts"]) for c in cues]
    out = []
    for cue in cues:
        enriched = dict(cue)
        enriched["load_series"] = load or []
        window = build_window(enriched, samples, all_ts, activity=activity,
                              session_started=session_started, game=game,
                              ring_spans=ring_spans)
        out.append(window)
    return out


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

# With a cap of 5 cues per hour and three hours of play a day that is ~15
# windows a day, i.e. a year of daily play. One window is ~300 B of JSON,
# so 5000 windows are ~1.5 MB.
MAX_WINDOWS = 5000


def load_windows(path):
    """Saved windows, or an empty list. Never raises an exception."""
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [w for w in data if isinstance(w, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def save_windows(path, windows, log=None):
    """Appends windows to the JSON file (we keep the last MAX_WINDOWS).

    Written via `.tmp` + `paths.nahrad_subor`, the same as
    `hr_stats.save_session` - so an app crash in the middle of the write
    cannot leave a half-written file on disk, and a short file lock in
    Windows (Defender, search indexing) does not break the write; on
    failure the .tmp is deleted.

    When the existing file is unreadable, it RATHER WRITES NOTHING than
    overwrite it with an empty list: a badly read file is no reason to
    throw away everything measured up to then.
    """
    if not windows:
        return False
    try:
        data = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if not isinstance(loaded, list):
                raise ValueError("hr_windows.json nie je zoznam")
            data = loaded
        data.extend(windows)
        data = data[-MAX_WINDOWS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        nahrad_subor(tmp, path, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"measure: zapis okien zlyhal: {exc}")
        return False


# --------------------------------------------------------------------------
# Overview (only phase 4 will use it, but it belongs to the data, not the UI)
# --------------------------------------------------------------------------

# Critical values of Student's t for a two-sided 95% interval, df = n-1.
# A table and not `scipy`: `measure.py` is a purely data module and must be
# importable without heavy dependencies (spec 2.1b, B2: "no scipy").
# Above 30 degrees of freedom the difference from 1.96 is already under 4 %.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
    14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
    20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

# Below this many windows the number is NOT SHOWN. It is not a matter of
# taste: with three windows the interval is as wide as the whole range and
# the chart would claim something that is not in the data. Better "I need
# more" than convincing-looking noise.
MIN_OKIEN = 5


def _interval95(hodnoty):
    """(mean, 95% interval half-width). Half-width is None if impossible."""
    n = len(hodnoty)
    if n == 0:
        return None, None
    priemer = sum(hodnoty) / float(n)
    if n < 2:
        return priemer, None
    odchylka = (sum((h - priemer) ** 2 for h in hodnoty) / float(n - 1)) ** 0.5
    if odchylka == 0.0:
        return priemer, 0.0
    t = _T95.get(n - 1, 1.96)
    return priemer, t * odchylka / (n ** 0.5)


def _ma_branu(window):
    """Window made with the cue gate (0.2)? The marker is in `params`."""
    params = window.get("params")
    return isinstance(params, dict) and bool(params.get("brana"))


def by_category(windows, only_valid=True, arm="voice"):
    """Effectiveness by cue CATEGORY, not by arm.

    Since the categories rotate (`next_slot`), one can also ask "which of
    them works". This is the input for phase 8 - and for now mainly for
    the chart in the app, so the player sees where they stand.

    Computed only from the VOICE arm: silent windows are the reference
    for whether a cue works AT ALL, not for comparing categories with each
    other. Mixing them would mean comparing a category with silence.

    Returns {category: {"n", "delta_bpm", "ci95", "dost_dat"}}.
    `delta_bpm` is the shift after the cue: negative = heart rate dropped.
    `ci95` is the HALF-WIDTH of the interval, or None for a single window.
    `dost_dat` says whether it may be shown as a number.

    IT DELIBERATELY DRAWS NO CONCLUSION. It returns no "best category" and
    no ranking - that would turn overlapping intervals into a leaderboard
    the data cannot carry.

    WHAT COUNTS (0.2, ladder + gate): only cues delivered AT A PAUSE (a
    silent picture after `max_wait_s` is not a voiced cue) that really
    SOUNDED (`audible` False = the "picture" rung, a style without sound,
    a slot without sound; a missing field = an older window, back then
    the voice arm at a pause did sound), and not from WORK (there a cue
    is only a picture). And once a window with the gate exists
    (`params.brana`), ONLY those count - since 0.2 a cue comes only when
    the load is not rising, so older windows would measure something
    else.
    """
    okna = [w for w in windows or ()
            # OTHER PEOPLE'S DATA DO NOT COUNT TOWARDS EFFECTIVENESS.
            #
            # `data_io.clean_window` marks imported records with `imported:
            # True` and that module's header explicitly promises it - but
            # nobody here read it. Whoever imported a backup from a friend saw
            # in their effectiveness chart the friend's body mixed with their
            # own and had no way to find out.
            if isinstance(w, dict) and not w.get("imported")]
    if any(_ma_branu(w) for w in okna):
        okna = [w for w in okna if _ma_branu(w)]
    podla = {}
    for w in okna:
        if only_valid and not w.get("valid"):
            continue
        if arm is not None and w.get("arm") != arm:
            continue
        if w.get("delivery") != "pause":
            continue
        if w.get("world") == "work":
            continue
        if arm == "voice" and w.get("audible") is False:
            continue
        pre, post = w.get("pre_bpm"), w.get("post_bpm")
        if pre is None or post is None:
            continue
        kat = w.get("category")
        if kat is None:
            continue
        podla.setdefault(kat, []).append(post - pre)

    out = {}
    for kat, hodnoty in podla.items():
        priemer, polsirka = _interval95(hodnoty)
        out[kat] = {
            "n": len(hodnoty),
            "delta_bpm": round(priemer, 2),
            "ci95": None if polsirka is None else round(polsirka, 2),
            "dost_dat": len(hodnoty) >= MIN_OKIEN,
        }
    return out


def summarize(windows, only_valid=True):
    """Number of windows per arm and the mean BPM shift in them.

    Deliberately draws NO conclusion - returns numbers. Whether the
    difference is anything more than noise can only be decided with
    enough windows (the spec talks about 30 per arm) and with a confidence
    interval.
    """
    out = {}
    for w in windows:
        # Other people's windows do not belong here - see `by_category`.
        if w.get("imported"):
            continue
        if only_valid and not w.get("valid"):
            continue
        pre, post = w.get("pre_bpm"), w.get("post_bpm")
        if pre is None or post is None:
            continue
        bucket = out.setdefault(w.get("arm", "voice"), {"n": 0, "delta_sum": 0.0})
        bucket["n"] += 1
        bucket["delta_sum"] += post - pre
    for bucket in out.values():
        bucket["delta_bpm"] = round(bucket["delta_sum"] / bucket["n"], 2)
        del bucket["delta_sum"]
    return out
