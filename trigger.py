"""When a cue arms and when it fires.

WHY THIS IS NOT IN app.py
-------------------------
Not a single test in tests/ imports `app.py` - it pulls in tkinter,
customtkinter, pynput and pygame (audio_engine runs pygame.mixer.init() on
import). Logic that lived there could not be tested. This module is purely
data: no Tk, no I/O, the clock can be injected. The same discipline as
`measure.py` and `activity.py`.

HOW IT WORKS
------------
    load over threshold GATHERS `stress_hold_s` (default 45 s)   (not a spike!)
         v                (not continuous - cumulative in a sliding window, see
         v                 `note_load`; real combat goes back down in cycles)
    ARMED  -  the app does nothing yet, it only waits
         v
    waits for a pause in activity >= 2,5 s, at most `max_wait_s`
         v
    pause came, gate lets through  ->  cue (voice + visual)
    pause came, gate holds         ->  keeps waiting, for the next pause
    `max_wait_s` without a cue     ->  silent visual without voice - but only
                                       if the gate lets it through; otherwise
                                       the arming is cancelled

THE GATE (0.2, stress-gate). A cue goes only when:
  * the heart-rate zone is known and not critical (`zona` from `note_load`,
    i.e. `HeartStats.known_zone` = `zone_of_bpm`; NEVER the load zones
    `zone_for`),
  * the load is no longer rising (`_stupa`: the last value is not more than
    `STUPA_O` higher than the one from before `VRCHOL_OKNO_S`; too little
    data = rising),
  * and the app is allowed to (`can_fire`).
This applies to both arms and to the silent visual after `max_wait_s`. At the
peak and above the high heart-rate limit a cue is more likely to get in the
way than to help (this is not verified in games - it is caution); the app
would rather wait until things start to ease, and if that does not happen,
it stays silent. Calm does NOT cancel the cue - there is no safety reason
for that and cancelling would only take cues away from those who already
get few.

In the work world (0.2, B3-worlds) the voice is off for the whole session
(`open_session(voice=False)`): everything else runs the same, only every
cue goes as a silent visual.

The numbers above are defaults for the average player (`default_params`);
over time they get replaced by a threshold computed from one's own data
(`hr_stats.dynamicky_prah_zataze`).
Why not on a spike: a jump after a headshot is not stress, a longer load is.
Why the postponement to a pause: the highest need and the worst moment to
interrupt are the same second.

TWO THINGS THAT MUST NOT BE MERGED
----------------------------------
`arm` and `delivery` are DIFFERENT things and must stay separate all the way
to the analysis:

  arm       "voice" / "silent"  - drawn by lot at ARMING, even before
                                  anything happens. This is the silent
                                  control arm.
  delivery  "pause" / "timeout" - how it was delivered in the end.

When the pause does not come, the cue goes silently - but that is NOT the
control arm. If both were written as "silent", `measure.summarize()` would
compare two completely different things: one group had a pause, the other
did not, and the difference would measure exactly that. The control group
would stop being a control.

THE DRAW HAS ITS OWN GENERATOR
------------------------------
`random.Random()` and not the module `random`: `app.fire_slot` uses
`random.uniform` for jitter and any `random.seed()` elsewhere in the app
would shift the arm too. The control group would stop being random and
nobody would notice.
"""

import random
import time

import measure

# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------

DORMANT = "dormant"      # no session running, heart rate dropped out, or snooze running
IDLE = "idle"            # session running, load is below the threshold
RISING = "rising"        # load holds above the threshold, continuity is counted
ARMED = "armed"          # armed, waiting for a pause
COOLDOWN = "cooldown"    # just delivered, keeping the gap

# Events the module returns to the caller
E_ARMED = "armed"
E_DELIVER = "deliver"
E_ABORT = "abort"

# Why the arming was cancelled - recorded so it can be debugged
A_ZATAZ_KLESLA = "zataz_klesla"
A_ODISIEL = "odisiel_od_pc"
A_TEP_VYPADOL = "tep_vypadol"
A_SNOOZE = "snooze"
A_KONIEC_RELACIE = "koniec_relacie"
# After `max_wait_s` the gate would let the silent visual through, but the
# app was not allowed (`can_fire`: gap, snooze, walking, visual switched off).
A_NEDALO_SA = "nedalo_sa"
# After `max_wait_s` the gate did not let even the silent visual through
# (0.2, stress-gate):
A_BEZ_PAUZY = "bez_pauzy"              # ... and no pause came during the whole wait
A_NEVHODNA_CHVILA = "nevhodna_chvila"  # ... pauses came, the gate stopped each one

# Cancellations where the app ITSELF decided to stay silent. They count into
# the session summary (`zadrzane`); snooze, leaving, a dropout or the end of
# the session do not belong among them - the app did not decide those.
ZADRZANE = (A_BEZ_PAUZY, A_NEVHODNA_CHVILA, A_NEDALO_SA)

# Heart-rate zone from `hr_stats` (`zone_of_bpm`). A string, not an import:
# the module stays self-contained. None = we do not know the zone
# (calibration, heart rate returning) -> the gate does not let it through.
ZONA_KRITICKA = "critical"

# "Not rising": the last load is not more than STUPA_O higher than the last
# sample at least VRCHOL_OKNO_S old. History is kept for HIST_S seconds.
VRCHOL_OKNO_S = 15.0
STUPA_O = 1.0
HIST_S = 40.0

# What stopped the pause (counted once per pause, into the event as `skipped`).
P_NEZNAME = "nezname_pasmo"
P_KRITICKE = "kriticke"
P_STUPA = "stupa"
P_NESMIE = "nesmie"

ARM_VOICE = "voice"
ARM_SILENT = "silent"

D_PAUSE = "pause"
D_TIMEOUT = "timeout"


def default_params():
    """Starting numbers. They are from the literature, not from the player's
    body - the spec counts on that too, and the first evenings are for
    tuning them.

    Every session saves them with itself (spec §3.3): without that, a month
    later you cannot tell whether a difference came from what changed or
    from how well the player slept.
    """
    return {
        # Load (hr_stats.stress, 0-100). The zone word on the HUD/Today has
        # NOTHING to do with it - that is heart rate against rest
        # (HeartStats.zone); so "Vysoka" does not mean "above the threshold" or
        # "a cue is coming".
        "stress_threshold": 55.0,
        # How long it must hold above the threshold before it arms.
        #
        # 90 -> 45 AFTER THE FIRST REAL EVENING. The Finals, 36 minutes, load
        # peak 87 at threshold 55, 2:40 in the upper zones - and ZERO cues. So
        # the threshold was not the problem; "continuous" was never filled.
        # The original 90 s was written for "two minutes at 120", which is a
        # different type of game. In a round-based shooter the body goes up
        # and down in cycles of tens of seconds: you die, respawn, calm. 90 s
        # without a dip longer than five seconds practically never happens
        # there.
        "stress_hold_s": 45.0,
        # A short dip below the threshold does NOT cancel the arming - stress
        # is smoothed by an exponential average and oscillates at the boundary.
        # A longer dip does.
        #
        # 5 -> 20 for the same reason: 5 s bridges the oscillation of the
        # smoothed average, but not a respawn. Twenty seconds bridges that
        # too, so one combat stretch does not fall apart into three short ones.
        "dip_grace_s": 20.0,
        # A pause in activity that counts as a breakpoint.
        # NOTE: 2,5 s is the author's decision. Published research
        # (Iqbal & Bailey, CHI 2008) says that the finest breakpoints did
        # worse than medium and coarse ones. That is why it is a parameter and
        # why it is written into every window - it can be checked back from
        # the data.
        "pause_s": 2.5,
        # The longest wait for a pause. 90 s is a published notification
        # delay accepted by players.
        "max_wait_s": 90.0,
        # A longer pause is not a micropause any more - the player left the PC.
        "away_s": 120.0,
        # Minimum gap between cues. MUST be bigger than
        # measure.REFRACTORY_AFTER_S (180), otherwise two cues invalidate each
        # other's measurement windows and a month of measuring is worthless.
        "min_gap_s": 240.0,
        # Cap on cues per hour (spec §2). `min_gap_s` alone is not enough:
        # a 240 s gap allows up to 15 per hour. Measured by simulation - on a
        # heated evening it came to 6,9 per hour, i.e. above the spec.
        #
        # The gap and the cap are two different things: the gap protects the
        # MEASUREMENT (so two cues do not invalidate the windows), the cap
        # protects the PLAYER (so the app is not chatty). That is why they are
        # two parameters and not one.
        "max_per_hour": 5.0,
        # May it arm at all? False = the "pauza" rung of the ladder
        # (`rebrik.py`): the state machine behaves as when the hourly cap is
        # full - it does not arm, but diagnostics (runs above the threshold,
        # pauses) are still collected.
        "cues_enabled": True,
        # Gate marker (0.2, stress-gate). Every window carries its parameters
        # (`app._save_measure_windows`), so windows after a timing change do
        # not merge with older ones (`measure.by_category`).
        "brana": "po_vrchole",
    }


# --------------------------------------------------------------------------
# How often the app speaks up - one control instead of four numbers
# --------------------------------------------------------------------------
#
# Threshold, hold, gap and cap CANNOT be set separately without them
# contradicting each other: lowering the threshold without shortening the
# hold does almost nothing (the body swings over the threshold, but the
# continuous stretch still does not fill up), and shortening the gap
# without raising the cap does not either (the cap cuts in sooner). That is
# why all four move at once, with one choice.
#
# The rest of the numbers (pause_s, max_wait_s, away_s, dip_grace_s) does
# NOT change: those are properties of the moment of delivery, not of how
# often it speaks up.

# A HARD SAFETY NET, not a setting.
#
# After a cue a measurement window runs for `measure.REFRACTORY_AFTER_S`
# (180 s). If the gap fell below it, the second cue would land in the first
# one's window, both windows would be invalidated - and nothing would be
# left from the whole evening to evaluate.
# The 30 s reserve covers the fact that a cue does not fire at the moment of
# arming, but only at the next pause.
MIN_GAP_FLOOR_S = measure.REFRACTORY_AFTER_S + 30.0   # 210 s

CITLIVOST_MENEJ = "menej"
CITLIVOST_BEZNE = "bezne"
CITLIVOST_VIAC = "viac"
CITLIVOSTI = (CITLIVOST_MENEJ, CITLIVOST_BEZNE, CITLIVOST_VIAC)

_CITLIVOST = {
    # For evenings when the app disturbs more than it helps.
    CITLIVOST_MENEJ: {"stress_threshold": 65.0, "stress_hold_s": 60.0,
                      "min_gap_s": 420.0, "max_per_hour": 3.0},
    # Numbers from the spec - what is in `default_params()`.
    CITLIVOST_BEZNE: {},
    # For a body that swings over the threshold only briefly. The gap goes
    # down to the safety net, not below it.
    CITLIVOST_VIAC: {"stress_threshold": 48.0, "stress_hold_s": 30.0,
                     "min_gap_s": MIN_GAP_FLOOR_S, "max_per_hour": 8.0},
}


def params_for(citlivost):
    """Complete parameters for the chosen sensitivity.

    Returns the WHOLE dictionary, not just the difference - the caller can
    use it right away and does not need to know which keys change. An
    unknown value falls back to "bezne".
    """
    out = default_params()
    out.update(_CITLIVOST.get(citlivost, _CITLIVOST[CITLIVOST_BEZNE]))
    # The safety net holds even when someone makes a mistake in the table.
    out["min_gap_s"] = max(out["min_gap_s"], MIN_GAP_FLOOR_S)
    return out


# The cumulative window is a multiple of the required hold: with
# `stress_hold_s` 45 s it looks at the last 90 s. It is deliberately NOT
# another parameter - it would be a fifth knob for the same thing and nobody
# would know how to set it against the others.
OKNO_NASOBOK = 2.0

# A CAP ON CREDIT: at most this many seconds from ONE gap between samples
# are credited to the cumulative window as "measured". A longer gap counts
# only up to this limit - time that nobody measured does not count as
# holding.
#
# The watch cadence is NOT 1,5 s, as it said here before. Measured: ~0,9 s
# and ~2,9 s per sample depending on what the watch sends (since 20. 9. the
# heart rate in OBS alternates with steps - sources Tep/Steps/steps), and at
# ~2,9 s one lost packet is a gap of ~5,6 s. A tail of gaps just above 5 s is
# therefore NORMAL, not a dropout - only `DIERA_S` decides a dropout.
MAX_KROK_S = 5.0

# FROM WHAT GAP IT IS A DROPOUT, not just a sparser watch cadence.
#
# The same number as `heart_rate.HeartRateMonitor.STALE_AFTER_S` (a test
# guards it): the app does not consider a shorter gap a dropout - the HUD
# shows the last heart rate and does not report "Disconnected" - so the
# trigger must not consider it a dropout either.
#
# Before, `MAX_KROK_S` (5 s) did this job and every longer gap erased the
# whole accumulated time. Evenings since 20. 9. (cadence ~2,9 s): 199
# stretches above the threshold, 194 of them cancelled by a "dropout", ONE
# cue in over 4 hours - and after the evening the sentence "Tep 119x
# vypadol" (heart rate dropped out 119x), although there could have been at
# most 5 real dropouts (12 s and more) that evening.
DIERA_S = 12.0

# The window in which the cap is counted. Not a parameter: "per hour" is
# the unit from the spec, `max_per_hour` is what changes.
HOUR_S = 3600.0


def _nove_preskocene():
    """Counts of pauses the gate stopped, by obstacle (since arming)."""
    return {P_NEZNAME: 0, P_KRITICKE: 0, P_STUPA: 0, P_NESMIE: 0}


class CueTrigger:
    """State machine of one session. No Tk, no I/O, with an injectable clock -
    so it can be run through entirely in tests without waiting."""

    def __init__(self, params=None, rng=None, clock=time.time):
        self.params = dict(default_params())
        if params:
            self.params.update(params)
        self._rng = rng if rng is not None else random.Random()
        self._clock = clock
        self.silent_share = 0.0
        # May the cue be heard at all? False in the WORK world (B3-worlds):
        # there every cue goes only as a picture. Applies to the whole
        # session - the world is decided when it opens (`open_session`), not
        # on the fly.
        self.voice = True
        self._delivered_at = []
        self.reset()

    # ---------- life cycle ----------

    def reset(self):
        self.state = DORMANT
        self._above_since = None     # since when the load holds above the threshold
        self._below_since = None     # since when it is below it (for the tolerance)
        # Sum of finished tolerated dips in this stretch. They do NOT count
        # towards the hold - see `_nad_v_behu`. Reset everywhere along with
        # `_above_since`.
        self._prepady_s = 0.0
        self._armed_at = None
        self._arm = None             # the drawn arm, already at arming
        self._cooldown_until = 0.0
        self._last_load = None
        # Why the state machine is suspended. See `suspend` / `resume`.
        self._suspended_by = None
        self.armed_count = 0
        self.delivered_count = 0
        self._delivered_at = []
        # WHY THIS IS COUNTED
        # The first real evening (The Finals, 36 min) ended with ZERO cues,
        # although the load peak was 87 at threshold 55. So the threshold was
        # not the problem - the "CONTINUOUS stress_hold_s" condition failed.
        # But from the session summary this could not be told apart from a
        # completely different cause (heart-rate dropouts, which reset the
        # continuity counter).
        #
        # These four numbers tell them apart without storing the whole curve:
        # when the longest run is 40 s, the rule is strict; when it is 10 s
        # and there are dozens of runs, they are dropouts.
        # [(time, length)] of stretches above the threshold in the cumulative
        # window
        self._nad_okno = []
        self._posledny_load_ts = None
        self._posledny_nad_koniec = None
        # The longest stretch above the threshold - ONLY time really above the
        # threshold, tolerated dips do not count (0.2.1, `_nad_v_behu`). The
        # sentence after the session compares it with `stress_hold_s`, so it
        # must measure the same thing as the trigger.
        self.najdlhsi_nad_s = 0.0
        self.behov_nad = 0           # how many times such a stretch started
        self.zrusenych_prepadom = 0  # ... and ended by dropping below the threshold
        # ... or by a heart-rate dropout: a gap >= DIERA_S, or
        # suspend(A_TEP_VYPADOL). Snooze does NOT belong here.
        self.zrusenych_vypadkom = 0
        # THE GATE (see the module header).
        self._zona = None            # heart-rate zone from the last sample
        self._load_hist = []         # [(time, load)] over HIST_S
        self._vrchol = None          # the highest load since arming
        self._preskocene = _nove_preskocene()
        self._preskocena_pauza = None
        # HOW MANY PAUSES THE APP SAW AT ALL IN THE SESSION (transitions into a
        # pause >= `pause_s`). Zero over a long evening means the voice never
        # had a chance to be heard - and often that something reports input
        # nonstop (the gyro in a controller). Without this number it could not
        # be told apart from calm.
        self.pause_episodes = 0
        self._v_pauze = False
        # How many armings the app cancelled itself, by reason (`ZADRZANE`).
        self.zadrzane = {r: 0 for r in ZADRZANE}

    def open_session(self, now=None, silent_share=0.10, voice=True):
        """New session. The hourly cap is NOT reset.

        "Five per hour" is about the player, not the session. If the cap
        were cleared with every session, switching the sensor off and on
        would be enough for the app to keep talking - and the player would
        do that exactly when it annoys them.

        `voice=False` = the work world: the state machine runs the same
        (arming, pause, the arm is still drawn), only `hlas` at delivery is
        always False - the cue goes only as a picture. The arm is NOT
        OVERWRITTEN: it is drawn before delivery and must not be merged with
        the way of delivery (see the module header); the window carries the
        world, so the two can be separated.
        """
        historia = list(self._delivered_at)
        self.reset()
        self._delivered_at = historia
        self.silent_share = float(silent_share)
        self.voice = bool(voice)
        self.state = IDLE
        self._cooldown_until = 0.0
        return None

    def close_session(self, now=None):
        """Session ends. If it was waiting for a pause, that is information -
        by how often that happens, `max_wait_s` can be tuned."""
        now = self._clock() if now is None else now
        udalost = None
        if self.state == ARMED:
            udalost = self._abort(A_KONIEC_RELACIE, now)
        self.state = DORMANT
        return udalost

    def suspend(self, reason, now=None):
        """Snooze or heart-rate dropout. The arming is cancelled, not kept.

        THE REASON IS REMEMBERED. Without it `resume` cannot tell whether it
        may lift it: a heart-rate dropout should be lifted by the very next
        sample, but snooze or stopped listening should not.
        """
        now = self._clock() if now is None else now
        udalost = self._abort(reason, now) if self.state == ARMED else None
        if self._above_since is not None:
            # A running stretch above the threshold ends by suspension, not
            # by a drop. That is a different cause and must be
            # distinguishable - see `reset`.
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._nad_v_behu())
            # ONLY a heart-rate dropout counts as a dropout. "Not now"
            # (snooze) is the player's decision, not a watch fault -
            # otherwise after the evening the app would write "Tep 3x
            # vypadol, daj hodinky blizsie" (heart rate dropped out 3x, move
            # the watch closer), although they only silenced it three times.
            if reason == A_TEP_VYPADOL:
                self.zrusenych_vypadkom += 1
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        # THE TIME COLLECTED ABOVE THE THRESHOLD MUST BE THROWN AWAY HERE TOO.
        #
        # `note_load` has a safety net against a hole in the data, but it only
        # runs when `_above_since is not None` - and `suspend` has just reset
        # that. Without this, after a dropout longer than `DIERA_S` but shorter
        # than the `OKNO_NASOBOK*drzanie` window, the old collected load would
        # survive and the first sample after the return would arm a cue on time
        # nobody measured (B4).
        # `_posledny_load_ts=None` also guarantees that the first step after
        # the return is 0 (no fictitious increment).
        self._nad_okno = []
        self._posledny_load_ts = None
        # Not even "rising/not rising" is compared across the hole - after the
        # return the load history is collected from scratch.
        self._load_hist = []
        # A WEAKER REASON DOES NOT OVERWRITE A STRONGER ONE. A heart-rate
        # dropout during "not now" (since 24. 9. it does not close the
        # session, measuring goes on) would otherwise overwrite the reason
        # with `A_TEP_VYPADOL` - and the first sample after the return would
        # silently cancel the snooze via `resume()` without `force`
        # (REVIZIA_2_NALEZY).
        if not (reason == A_TEP_VYPADOL
                and self._suspended_by not in (None, A_TEP_VYPADOL)):
            self._suspended_by = reason
        self.state = DORMANT
        return udalost

    def resume(self, now=None, force=False):
        """Lifts the suspension. The 90 s are counted FROM SCRATCH - a half-armed
        state does not exist.

        `force=False` means "a heart-rate sample came" and lifts ONLY a
        heart-rate dropout. It is called from `_apply_hr_bpm`, i.e. EVERY
        SECOND, and that is why it must not lift anything else: "not now"
        would be cancelled by the first heartbeat a second later. Measured -
        with a 30-minute snooze it armed 10x this way and an inflated
        `natiahnuti` was written into every measurement window of the
        session.

        `force=True` is a deliberate lift: end of snooze, cancelling snooze,
        starting listening.

        THE GAP BETWEEN CUES IS NOT LOST. Before, the state went straight to
        IDLE and nobody read `_cooldown_until` any more, because it is read
        only in the COOLDOWN state - so one heart-rate dropout erased four
        minutes of gap. And that gap MUST be bigger than
        `measure.REFRACTORY_AFTER_S`, otherwise two cues invalidate each
        other's measurement windows.
        """
        if self.state != DORMANT:
            return None
        if not force and self._suspended_by not in (None, A_TEP_VYPADOL):
            return None
        now = self._clock() if now is None else now
        self._suspended_by = None
        self.state = COOLDOWN if now < self._cooldown_until else IDLE
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        return None

    # ---------- inputs ----------

    def note_load(self, stress, now=None, calibrating=False, zona=None):
        """One load sample. Called from `_apply_hr_bpm` (Tk thread).

        Returns the E_ARMED event when it has just armed, otherwise None.

        `calibrating=True` (`HeartStats.is_calibrating`) means the session
        does not have its own baseline yet and the load is only an estimate.
        Then NOTHING is collected: without this, with the "viac" sensitivity
        (30 s hold) it could arm even during calibration, and with the normal
        one the time collected during it would shorten the wait right after
        it. Better a quiet first minute than a cue built on a number the app
        itself does not trust.

        `zona` is the HEART-RATE zone (`HeartStats.known_zone`), not the load
        zone. None = unknown - and then the gate does not let the cue through.
        The default is None on purpose: a caller who forgets to pass the zone
        gets silence, not a voice above the high heart-rate limit.
        """
        now = self._clock() if now is None else now
        self._last_load = stress
        # THE GATE is fed on EVERY sample - even in the ARMED state, because
        # that is exactly when it is used to decide (hence before the
        # return below).
        self._zona = zona
        self._load_hist.append((now, stress))
        while self._load_hist and self._load_hist[0][0] < now - HIST_S:
            self._load_hist.pop(0)
        if self.state == ARMED:
            self._vrchol = (stress if self._vrchol is None
                            else max(self._vrchol, stress))
        if self.state in (DORMANT, ARMED):
            return None
        if calibrating:
            # Like a hole in the data: the collected time is gone and the first
            # step after calibration is zero (`_posledny_load_ts=None`), not a
            # fictitious increment for the whole calibration.
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            self._nad_okno = []
            self._posledny_load_ts = None
            if self.state == RISING:
                self.state = IDLE
            return None
        if self.state == COOLDOWN:
            if now < self._cooldown_until:
                return None
            self.state = IDLE
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0

        prah = self.params["stress_threshold"]
        drzanie = self.params["stress_hold_s"]

        # A CUMULATIVE WINDOW instead of "continuously above the threshold".
        #
        # The original rule required one uninterrupted stretch. In a real game
        # the body goes back down in cycles of tens of seconds (you die,
        # respawn, calm), so a continuous 45 s stretch practically never
        # happens. A measured evening showed it literally: 88 minutes, 13 runs
        # above the threshold, ALL cancelled by a dip, the longest 44,1 s with
        # 45,0 required - one second was missing and the app said nothing the
        # whole evening.
        #
        # Now it counts how much time was above the threshold in the last
        # `OKNO_NASOBOK * drzanie` seconds. A dip does not erase the run, it
        # is just not added - that is exactly the difference between "the body
        # is under load" and "the body holds one long curve".
        krok = 0.0
        diera = False
        if self._posledny_load_ts is not None:
            surovy = max(0.0, now - self._posledny_load_ts)
            # Two different limits, two different questions (see `DIERA_S`): a
            # dropout is a gap of `DIERA_S` or more, the credit from one gap is
            # at most `MAX_KROK_S`.
            diera = surovy >= DIERA_S
            krok = min(surovy, MAX_KROK_S)
        self._posledny_load_ts = now

        # A HOLE IN THE DATA IS NOT HOLDING ABOVE THE THRESHOLD.
        #
        # The app also reacts to a heart-rate dropout itself
        # (`_suspend_cue_trigger` with A_TEP_VYPADOL after
        # `heart_rate.STALE_AFTER_S`), but relying on that is not enough:
        # between the last sample and declaring the dropout there is a window
        # in which nothing is measured - and without this safety net all that
        # time would be credited as a continuous stretch above the threshold.
        # A twenty-minute connection dropout would arm a cue right after the
        # return, based on time nobody measured.
        #
        # A SPARSER CADENCE, HOWEVER, IS NOT A HOLE. A gap shorter than
        # `DIERA_S` does not cancel the stretch or erase the window; at most
        # `MAX_KROK_S` of it goes into the window.
        # HONESTLY: that applies only to the window (`nazbierane`). The
        # continuous path below (`_nad_v_behu`) measures wall-clock time, so
        # silence shorter than `DIERA_S` after a sample ABOVE the threshold IS
        # counted in it - just as the app elsewhere considers it "connected"
        # and the HUD then shows the last heart rate. Time BELOW the threshold
        # (a tolerated dip), however, is not counted in it.
        if diera and self._above_since is not None:
            # Up to the last sample above the threshold, not to `now` - nobody
            # measured the hole (`_nad_v_behu`).
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._nad_v_behu())
            self.zrusenych_vypadkom += 1
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            self._nad_okno = []
            if self.state == RISING:
                self.state = IDLE
        if stress >= prah:
            self._posledny_nad_koniec = now
            if krok > 0.0:
                self._nad_okno.append((now, krok))
        hranica = now - OKNO_NASOBOK * drzanie
        while self._nad_okno and self._nad_okno[0][0] < hranica:
            self._nad_okno.pop(0)
        nazbierane = sum(d for _, d in self._nad_okno)

        if stress >= prah:
            if self._below_since is not None:
                # The tolerated dip has ended. The stretch lives on, but the
                # time below the threshold is not added to the hold
                # (`_nad_v_behu`).
                self._prepady_s += now - self._below_since
            self._below_since = None
            if self._above_since is None:
                self._above_since = now
                self.behov_nad += 1
                self.state = RISING
            else:
                self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                          self._nad_v_behu())
            # `_nad_v_behu()` here is the time up to `now` - this sample is the
            # last one above the threshold (`_posledny_nad_koniec = now`
            # above).
            if (self._above_since is not None
                    and (self._nad_v_behu() >= drzanie
                         or nazbierane >= drzanie)):
                if (self._hodina_plna(now)
                        or not self.params.get("cues_enabled", True)):
                    # The cap is used up (or the cue ladder switched it off) -
                    # it does NOT ARM at all. Arming and then not delivering
                    # would mean the ring on the enso lights up and nothing
                    # comes; better that it stays completely silent.
                    # It counts from scratch, so it is tried again in
                    # another 90 s, not on every sample.
                    self._above_since = now
                    self._prepady_s = 0.0
                    self._nad_okno = []
                    return None
                return self._arm_now(now)
            return None

        # below the threshold - tolerate a short dip, cancel on a longer one
        if self._above_since is None:
            return None
        if self._below_since is None:
            self._below_since = now
        elif now - self._below_since > self.params["dip_grace_s"]:
            self.najdlhsi_nad_s = max(self.najdlhsi_nad_s,
                                      self._nad_v_behu())
            self.zrusenych_prepadom += 1
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            self.state = IDLE
        return None

    def tick(self, pause_s, now=None, can_fire=True):
        """Called 4x per second from `_tick_activity` (Tk thread).

        `pause_s` comes from `activity.ActivityTracker.pause_s()` and may be
        None - that means "the system does not report idle, we do not know".
        Then it does NOT wait for a pause forever, but does not pretend there
        is one either: `max_wait_s` is allowed to run out and then the same
        applies as without a pause (a silent visual, if the gate lets it
        through). A voice without a pause is never heard.

        `can_fire` is decided by the app - cooldowns, snooze, visual
        availability. When it is False, the arming is NOT USED UP: waiting
        goes on.

        THE GATE (see the module header) applies at a pause and after
        `max_wait_s`, the same for both arms - otherwise the silent arm would
        stop being a control.
        """
        now = self._clock() if now is None else now

        # Pauses are counted in EVERY state (even outside arming): the question
        # is whether the app sees them at all over the evening, not whether it
        # is waiting for one right now.
        pauza = pause_s is not None and pause_s >= self.params["pause_s"]
        if pauza and not self._v_pauze:
            self.pause_episodes += 1
        self._v_pauze = pauza

        if self.state == COOLDOWN and now >= self._cooldown_until:
            self.state = IDLE
            self._above_since = None
            self._below_since = None
            self._prepady_s = 0.0
            return None
        if self.state != ARMED:
            return None

        cakane = now - self._armed_at

        # The player left the PC - not a micropause that is being waited for.
        if pause_s is not None and pause_s > self.params["away_s"]:
            return self._abort(A_ODISIEL, now)

        prekazka = self._prekazka(now)

        if cakane >= self.params["max_wait_s"]:
            # A silent picture without a pause - but not at the peak or above
            # the high heart-rate limit. Better nothing than a picture in the
            # middle of the worst.
            if prekazka is None:
                if can_fire:
                    return self._fire(D_TIMEOUT, now, cakane)
                return self._abort(A_NEDALO_SA, now)
            dovod = (A_NEVHODNA_CHVILA if any(self._preskocene.values())
                     else A_BEZ_PAUZY)
            return self._abort(dovod, now)

        if not pauza:
            return None
        if prekazka is None and not can_fire:
            prekazka = P_NESMIE
        if prekazka is None:
            return self._fire(D_PAUSE, now, cakane)
        # A pause came, but the moment is not suitable - waiting for the next
        # one. Counted once per pause, not 4x per second.
        if self._preskocena_pauza != self.pause_episodes:
            self._preskocene[prekazka] += 1
            self._preskocena_pauza = self.pause_episodes
        return None

    # ---------- internals ----------

    def _nad_v_behu(self):
        """How many seconds of the running stretch were really ABOVE the
        threshold - up to the last sample above it.

        A TOLERATED DIP IS NOT HOLDING (0.2.1). `dip_grace_s` only keeps
        the stretch alive so that a respawn does not break it into three
        short ones. But the continuous path used to be computed as
        `now - _above_since`, i.e. by wall-clock time INCLUDING dips: the
        pattern "1 s above the threshold, 19 s below it" armed a cue after a
        minute, although only four samples were above the threshold. The
        README promises a cue when the load above the limit "spends enough
        time" - and the app should rather stay silent than speak up for
        nothing.

        A dip lasts from the first sample below the threshold to the first
        one above it (`_prepady_s`). A short silence AFTER A SAMPLE ABOVE
        the threshold counts as above when the stretch continues with
        another sample above the threshold - see HONESTLY in `note_load`.

        WHY UP TO THE LAST SAMPLE ABOVE THE THRESHOLD, and not up to `now`.
        Exactly this number is seen by the arming condition, and from it
        `najdlhsi_nad_s` goes into the sentence "longest X s, Y s needed". If
        at the end of the stretch the time after the last sample above the
        threshold were added too - a running dip, or 12 s without data
        before `suspend(A_TEP_VYPADOL)` - the sentence would claim "longest
        46 s, 45 s needed" about a stretch that did not arm.

        `is None`, not truthiness: time 0.0 is a valid time (the clock can be
        injected), not an "error".
        """
        if self._above_since is None or self._posledny_nad_koniec is None:
            return 0.0
        return max(0.0, self._posledny_nad_koniec - self._above_since
                   - self._prepady_s)

    def _prekazka(self, now):
        """What in the body prevents a cue RIGHT NOW, or None.

        The order is the order of importance: unknown zone, critical zone,
        rising load. `can_fire` does not belong here - that is not the body
        but the app (and it goes into the cancellation reason separately)."""
        if self._zona is None:
            return P_NEZNAME
        if self._zona == ZONA_KRITICKA:
            return P_KRITICKE
        if self._stupa(now):
            return P_STUPA
        return None

    def _stupa(self, now):
        """Is the load still rising? Last value vs. the last sample at least
        `VRCHOL_OKNO_S` old. When it cannot be told (fewer than two samples,
        or none that old), it is taken as "rising" - erring towards silence,
        not towards a voice at the peak."""
        h = self._load_hist
        if len(h) < 2:
            return True
        ref = None
        for ts, hodnota in h:
            if ts <= now - VRCHOL_OKNO_S:
                ref = hodnota
            else:
                break
        if ref is None:
            return True
        return h[-1][1] - ref > STUPA_O

    def _hodina_plna(self, now):
        """Have `max_per_hour` cues already fired in the last hour?

        A sliding window, not a fixed hour from switching on: with a fixed
        one it could speak up 5x right before and 5x right after the turn of
        the hour, i.e. 10 cues in a short stretch, and the cap would formally
        hold.
        """
        strop = self.params.get("max_per_hour")
        try:
            strop = float(strop)
        except (TypeError, ValueError):
            return False
        if strop <= 0:
            return False            # 0 or negative = no cap
        self._delivered_at = [t for t in self._delivered_at
                              if now - t < HOUR_S]
        return len(self._delivered_at) >= strop

    def _arm_now(self, now):
        """Arming. The arm is drawn HERE - before anything happens, so that it
        can be logged even when the cue in the end is not delivered at all."""
        self.state = ARMED
        self._armed_at = now
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        # The collected time was used up on THIS arming. Without clearing,
        # right after the cooldown a single sample above the threshold would
        # be enough and the window would already be full from last time.
        self._nad_okno = []
        # Gate: peak tracked from this moment on, skipped pauses from scratch.
        self._vrchol = self._last_load
        self._preskocene = _nove_preskocene()
        self._preskocena_pauza = None
        self._arm = (ARM_SILENT if self._rng.random() < self.silent_share
                     else ARM_VOICE)
        self.armed_count += 1
        return {"typ": E_ARMED, "ts": now, "arm": self._arm,
                "load": self._last_load}

    def _fire(self, delivery, now, waited):
        """Delivers. `arm` is the drawn arm, `delivery` is the way - they are
        two different things (see the module header).

        The sound plays only when BOTH hold: it is the voice arm and the pause
        really came. The visual is always shown, in both arms - otherwise the
        arms could not be compared. In the work world (`voice=False`) the
        sound never plays.
        """
        self.state = COOLDOWN
        self._cooldown_until = now + self.params["min_gap_s"]
        self._armed_at = None
        self.delivered_count += 1
        self._delivered_at.append(now)
        arm = self._arm
        self._arm = None
        return {"typ": E_DELIVER, "ts": now, "arm": arm,
                "delivery": delivery, "waited_s": round(waited, 1),
                "hlas": (arm == ARM_VOICE and delivery == D_PAUSE
                         and self.voice),
                "load": self._last_load, **self._brana_zaznam()}

    def _abort(self, reason, now):
        cakane = (now - self._armed_at) if self._armed_at else 0.0
        arm = self._arm
        self.state = IDLE
        self._armed_at = None
        self._arm = None
        self._above_since = None
        self._below_since = None
        self._prepady_s = 0.0
        if reason in self.zadrzane:
            self.zadrzane[reason] += 1
        return {"typ": E_ABORT, "ts": now, "reason": reason, "arm": arm,
                "waited_s": round(cakane, 1), **self._brana_zaznam()}

    def _brana_zaznam(self):
        """What the gate saw - into the event (hr_events), so it can be checked
        afterwards that the voice did not sound at the peak or above the
        limit."""
        return {"zone_at": self._zona, "load_peak": self._vrchol,
                "skipped": dict(self._preskocene)}

    # ---------- for the UI and for recording ----------

    @property
    def is_armed(self):
        return self.state == ARMED

    def snapshot(self):
        """State for the UI - the Today page shows 'armed' as a ring."""
        return {"state": self.state, "armed": self.state == ARMED,
                "armed_count": self.armed_count,
                "delivered_count": self.delivered_count}


def silent_share_for(session_count, calibration_sessions=15,
                     during=0.25, after=0.10):
    """Share of silent cues. 25 % during calibration, then 10 % forever.

    Never zero: it is the only fixed point once the choice of cues starts
    to move. Without a control arm the result is always "it works", even if
    the app stayed silent - heart rate comes back down on its own too.
    """
    return during if session_count < calibration_sessions else after
