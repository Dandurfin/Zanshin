"""Analysis of the heart-rate session history - gentle tips, not diagnoses.

What it does
------------
Goes through the saved session summaries (hr_sessions.json) and looks for
patterns ACROSS sessions that cannot be seen from one session:

  * the resting baseline rises/falls week by week,
  * heart-rate recovery (HRR) gets better/worse,
  * when in a session the breathing triggers come more densely (the first
    hour vs. only after two hours),
  * the time above the limit grows.

Every result is (i18n key, parameters, tone). The texts are worded as
"what we see and what you could try" - never "you are healthy/ill". The
module is purely data: no Tk, no network, no I/O except save/load JSON,
so it can run in the background (threading) and be tested directly.

The thresholds are deliberately conservative (at least 3 sessions, a
difference of at least 4 BPM, triggers at least 2x denser and not by
chance), so that the app does not report a "trend" from two random
evenings.
"""

import json
import math
import time

import hr_stats
from paths import nahrad_subor

MIN_SESSIONS = 3
BASELINE_DELTA_BPM = 4.0       # from how many BPM a baseline change is a "trend"
HRR_DELTA_BPM = 4.0
WEEK_S = 7 * 86400.0
LONG_SESSION_S = 90 * 60.0
VERY_LONG_SESSION_S = 150 * 60.0

# When the triggers come (insight 3). What is compared is the DENSITY - how
# many triggers there are per session time in the window - not their share.
# (Session time, not playing time: `duration_s` runs from when the sensor is
# switched on, also through menus and AFK.)
# The share is wrong already with evenly spread triggers: in a 90-min session
# the first hour is two thirds of the time, so even perfectly even triggers
# give ~67 % "in the first hour" and the old 66 % threshold reported a
# pattern that was not there. In 4-5 h sessions the same happened with
# "after two hours" (50 % threshold) - and with the "watch" tone at that.
EARLY_WINDOW_S = 3600.0        # "in the first hour"
LATE_FROM_S = 7200.0           # "only after two hours"
RATE_RATIO = 2.0               # the window must be at least 2x denser than the rest
MIN_TRIGGERS = 6               # fewer triggers in the comparison = an evening, not a pattern
# How much the imbalance may be chance. With a few triggers even 2x is
# chance: a simulation of evenly spread triggers (3-5 sessions of 90-300
# min, 1-3 per hour, with the gap and cap from trigger.py) gave, with just
# "2x and at least 6 triggers", the message in 4-18 % of cases, with this
# safeguard around 2 % (even when the tense evenings are shorter or longer
# than the calm ones - see the per-session expectation in analyze()).
# The price: from three 90-min sessions a real ramp-up shows rarely (after
# the first hour there is only half an hour in them to compare) - the
# insight only comes with further sessions. Rather silence than a false
# alarm.
CHANCE_P = 0.05

# How many of the LAST sessions the tips about silence ask about. Three is
# the minimum from which you can say "it keeps happening" and not "you had
# one calm evening".
TICHYCH_RELACII = 3
# When the longest stretch above the threshold is at least this share of
# the required hold, it is a "near miss" - then it makes sense to suggest a
# policy change. When it is deep below, the problem is elsewhere
# (threshold, heart-rate limit) and the tip would mislead.
TESNE_VEDLA = 0.5
# From how many dropout cancellations per session it can no longer be
# put down to chance.
VYPADKOV_VELA = 3.0

TONE_INFO = "info"
TONE_GOOD = "good"
TONE_WATCH = "watch"


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _zadrzanych(sessions):
    """How many armings the app cancelled ITSELF in these sessions
    (`cues_withheld`, 0.2 stress-gate). Old sessions do not have it - 0;
    a broken value is not counted."""
    spolu = 0.0
    for s in sessions:
        zadrzane = s.get("cues_withheld")
        if not isinstance(zadrzane, dict):
            continue
        for v in zadrzane.values():
            try:
                spolu += float(v or 0)
            except (TypeError, ValueError):
                pass
    return spolu


def _cislo_or_0(hodnota):
    """A number from the session summary; missing or broken = 0."""
    try:
        return float(hodnota or 0)
    except (TypeError, ValueError):
        return 0.0


def _valid(sessions):
    out = []
    for s in sessions or []:
        if not isinstance(s, dict):
            continue
        # An imported session is someone else's body. An insight "your resting
        # heart rate is rising" built on it would be a claim about someone
        # else.
        if s.get("imported"):
            continue
        # A broken session (steps read as heart rate) used to get through here
        # and produced a non-existent warning and the message "recovery
        # +50 BPM" from the step count (B8). The same filter as for
        # calibration.
        if hr_stats.je_podozriva(s):
            continue
        try:
            if float(s.get("duration_s", 0)) < 60 or int(s.get("samples", 0)) < 10:
                continue
        except (TypeError, ValueError):
            continue
        out.append(s)
    out.sort(key=lambda s: float(s.get("started", 0)))
    return out


def _insight(key, tone=TONE_INFO, **params):
    return {"key": key, "tone": tone, "params": params}


def _binom_tail(k, n, p):
    """P(X >= k) for X ~ Bin(n, p). In logarithms, so that it does not overflow
    even with thousands of triggers over years of playing (math.comb * float
    would fail)."""
    lp, lq = math.log(p), math.log1p(-p)
    ln_n = math.lgamma(n + 1)
    return sum(math.exp(ln_n - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * lp + (n - i) * lq)
               for i in range(k, n + 1))


def _denser(inside, outside, t_inside, t_outside):
    """Do the triggers in the window come CLEARLY more densely than outside it?

    `inside`/`outside` are trigger counts, `t_inside`/`t_outside` how many
    of them there would be in the window and outside it if they came evenly
    in every session (the sum of the window shares over the triggers). Both
    must hold:
      * in the window there are at least RATE_RATIO times more of them
        relative to expectation than outside it - so that it is a
        difference worth a sentence;
      * with an even spread such an imbalance would come about by chance
        with a probability of at most CHANCE_P. The binomial tail with the
        average share is more cautious with different session lengths than
        the exact one (Hoeffding 1956), so the error goes towards silence.
    """
    n = inside + outside
    if n < MIN_TRIGGERS or t_inside <= 0 or t_outside <= 0:
        return False
    # inside/t_inside >= RATE_RATIO * outside/t_outside, no division by zero
    if inside * t_outside < RATE_RATIO * outside * t_inside:
        return False
    p = t_inside / (t_inside + t_outside)
    if not 0.0 < p < 1.0:       # broken duration (inf/nan) - rather silence
        return False
    return _binom_tail(inside, n, p) <= CHANCE_P


def _split_recent(sessions, now, field):
    """Sessions with the given field: the last week vs. the week before it.
    If there were fewer than 2 in either week, it falls back to 'last 3 vs.
    previous 3' - we always compare comparable pieces."""
    with_field = [s for s in sessions if s.get(field) is not None]
    recent = [s for s in with_field if now - float(s.get("started", 0)) <= WEEK_S]
    previous = [s for s in with_field
                if WEEK_S < now - float(s.get("started", 0)) <= 2 * WEEK_S]
    if len(recent) >= 2 and len(previous) >= 2:
        return recent, previous, "week"
    if len(with_field) >= 6:
        return with_field[-3:], with_field[-6:-3], "sessions"
    return None, None, None


def analyze(sessions, now=None):
    """Returns the list of insights for the given history (may be empty)."""
    now = float(now) if now else time.time()
    valid = _valid(sessions)
    insights = []
    if len(valid) < MIN_SESSIONS:
        insights.append(_insight("need_more", TONE_INFO, n=len(valid), need=MIN_SESSIONS))
        return insights

    flagged = False

    # 1. resting baseline - rising or falling
    recent, previous, basis = _split_recent(valid, now, "baseline_bpm")
    if recent:
        diff = _mean(s["baseline_bpm"] for s in recent) - _mean(s["baseline_bpm"] for s in previous)
        if diff >= BASELINE_DELTA_BPM:
            insights.append(_insight("resting_up", TONE_WATCH, delta=int(round(diff))))
            flagged = True
        elif diff <= -BASELINE_DELTA_BPM:
            insights.append(_insight("resting_down", TONE_GOOD, delta=int(round(-diff))))

    # 2. heart-rate recovery (HRR)
    recent, previous, basis = _split_recent(valid, now, "hrr_bpm")
    if recent:
        diff = _mean(s["hrr_bpm"] for s in recent) - _mean(s["hrr_bpm"] for s in previous)
        if diff >= HRR_DELTA_BPM:
            insights.append(_insight("hrr_up", TONE_GOOD, delta=int(round(diff))))
        elif diff <= -HRR_DELTA_BPM:
            insights.append(_insight("hrr_down", TONE_WATCH, delta=int(round(-diff))))
            flagged = True

    # 3. when the breathing triggers come
    #
    # "Early" = the first hour against the rest, in sessions from 90 min.
    # "Late" = after two hours against the first two, only in sessions from
    # 150 min - only there is there at least half an hour after two hours to
    # compare.
    #
    # The expectation is computed PER SESSION, not from the sum of times: every
    # trigger brings the window share in ITS OWN session. With a sum of times a
    # tense 90-min session next to calm 5-h sessions would look like "the first
    # hour is denser", although it was not in any session (Simpson's paradox).
    early = after_early = 0
    t_early = t_after_early = 0.0
    late = before_late = 0
    t_late = t_before_late = 0.0
    for s in valid:
        offsets = s.get("trigger_offsets_s") or []
        dur = float(s.get("duration_s", 0))
        # nan/inf: skip only this session, do not silence the insight forever
        if not math.isfinite(dur) or dur < LONG_SESSION_S:
            continue
        very_long = dur >= VERY_LONG_SESSION_S
        p_early = EARLY_WINDOW_S / dur
        p_late = (dur - LATE_FROM_S) / dur
        for off in offsets:
            try:
                off = float(off)
            except (TypeError, ValueError):
                continue
            t_early += p_early
            t_after_early += 1.0 - p_early
            if very_long:
                t_late += p_late
                t_before_late += 1.0 - p_late
            if off <= EARLY_WINDOW_S:
                early += 1
            else:
                after_early += 1
            if very_long:
                if off >= LATE_FROM_S:
                    late += 1
                else:
                    before_late += 1
    # {share} stays the plain share of triggers in the window - the sentence
    # "X % of triggers came in the first hour" is literally true; that it is
    # MORE than the time would correspond to was checked by _denser.
    if _denser(early, after_early, t_early, t_after_early):
        insights.append(_insight("triggers_early", TONE_INFO,
                                 share=int(round(100.0 * early / (early + after_early)))))
    elif _denser(late, before_late, t_late, t_before_late):
        insights.append(_insight("triggers_late", TONE_WATCH,
                                 share=int(round(100.0 * late / (late + before_late)))))
        flagged = True

    # 4. time above the limit grows (share of the session)
    def over_share(s):
        dur = float(s.get("duration_s", 0)) or 1.0
        return float(s.get("time_over_s", 0)) / dur
    if len(valid) >= 6:
        recent_share = _mean(over_share(s) for s in valid[-3:])
        previous_share = _mean(over_share(s) for s in valid[-6:-3])
        recent_abs = _mean(float(s.get("time_over_s", 0)) for s in valid[-3:])
        if previous_share is not None and recent_abs >= 300 \
                and recent_share >= 1.5 * max(previous_share, 0.02):
            insights.append(_insight("over_up", TONE_WATCH,
                                     minutes=int(round(recent_abs / 60.0))))
            flagged = True

    # 5. WHY THE APP IS SILENT
    #
    # These are the only tips that tell the player WHAT TO DO - and that is
    # why they stand on hard numbers from the trigger (`longest_above_s`,
    # `above_runs`, `runs_cancelled_gap`), not on an impression of the heart
    # rate.
    #
    # The order is NOT arbitrary. Dropouts are asked about first: with them
    # the "longest stretch" is chopped up by holes in the data, so the tip
    # "speak up more often" would send the player to tune the threshold
    # instead of the watch.
    posledne = [s for s in valid if s.get("above_runs") is not None][-TICHYCH_RELACII:]
    if len(posledne) >= TICHYCH_RELACII:
        hlasok = sum(int(s.get("auto_triggers") or 0) for s in posledne)
        vypadkov = _mean(float(s.get("runs_cancelled_gap") or 0) for s in posledne)
        behov = sum(int(s.get("above_runs") or 0) for s in posledne)

        if vypadkov >= VYPADKOV_VELA:
            insights.append(_insight("cue_dropouts", TONE_WATCH,
                                     n=int(round(vypadkov))))
            flagged = True
        elif hlasok == 0 and any(s.get("cue_rung") == "pause" for s in posledne):
            # 0.2 (cue ladder): the app had switched cues off itself - "I had
            # no reason to speak up", "only briefly" or "I haven't noticed
            # anything" would not be true. Why, the sentence in History and the
            # questionnaire say.
            flagged = True
        elif hlasok == 0 and any(_cislo_or_0(s.get("snoozed_s")) > 0
                                 for s in posledne):
            # 24. 9.: "not now" no longer closes the session. While it was in
            # effect, the state machine slept and neither `above_runs` nor
            # `longest_above_s` see that time - "did not get above the limit" /
            # "only briefly" would explain a silence the player chose
            # themselves. What happened, the questionnaire says.
            flagged = True
        elif hlasok == 0 and behov == 0:
            # The body did not get above the threshold even once - the policy
            # will not help, the heart-rate limit is set too high for the
            # player.
            insights.append(_insight("cue_never_above", TONE_INFO,
                                     n=len(posledne)))
            flagged = True
        elif hlasok == 0 and _zadrzanych(posledne) > 0:
            # 0.2 (stress-gate): the trigger armed, but the app stayed silent
            # itself (gate, gap). So the load held up and "only briefly" /
            # "it was close" would lie. Rather no tip at all (not even "I
            # haven't noticed anything") - what happened, the questionnaire
            # after the session says.
            flagged = True
        elif hlasok == 0 and behov > 0:
            najdlhsi = max(float(s.get("longest_above_s") or 0) for s in posledne)
            treba = max(float(s.get("stress_hold_s") or 0) for s in posledne)
            if treba and najdlhsi >= TESNE_VEDLA * treba:
                insights.append(_insight("cue_almost", TONE_INFO,
                                         sec=int(round(najdlhsi)),
                                         need=int(round(treba))))
            else:
                insights.append(_insight("cue_far", TONE_INFO,
                                         sec=int(round(najdlhsi)),
                                         need=int(round(treba))))
            flagged = True

    if not flagged and len(insights) == 0:
        insights.append(_insight("steady", TONE_GOOD, n=len(valid)))
    return insights


# --------------------------------------------------------------------------
# Saving the result (so it does not have to be computed on every page open)
# --------------------------------------------------------------------------

def save_insights(path, insights, log=None, world=None):
    """`world` = the world whose sessions the insights came from (B3-worlds).

    Without it, after the world was switched at start, the insights of the
    other world would show up - so on a mismatch the app throws them away
    and recomputes them (see app.py)."""
    try:
        payload = {"computed_at": time.time(), "insights": list(insights or [])}
        if world is not None:
            payload["world"] = world
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        nahrad_subor(tmp, path, uprac_zdroj=True)
        return True
    except Exception as exc:
        if log:
            log(f"HR insights: save failed: {exc}")
        return False


def load_insights(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("insights"), list):
            return data
    except Exception:
        pass
    return {"computed_at": None, "insights": [], "world": None}
