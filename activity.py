"""Whether the player is doing something right now - without a keyboard hook.

WHY NOT PYNPUT
--------------
Until now the app listened to the keyboard with a global hook (`pynput`,
`WH_KEYBOARD_LL`), because keys were the trigger for cues. That is the only
part of the app that looks like a keylogger from the outside - and on a
platform where people run Vanguard, EAC and BattlEye, that is needlessly
costly.

`GetLastInputInfo` is a Win32 function that returns ONE number only: how
many milliseconds have passed since the last input. It does not reveal which
key it was, or whether it was a key at all. No hook is installed, so not a
single character of what the player types can reach the app.

From that one number you can derive everything the new mode needs:
  * whether the player is active right now,
  * when a pause happened (the break point for delivering a cue),
  * a rough pace of activity as a third channel next to heart rate.

GAMEPAD - MEASURED, IT SEES IT
------------------------------
It used to say here that GetLastInputInfo does not track the gamepad (the
classic argument: that is why the screensaver kicks in while playing on a
controller). On this Windows 11 that does NOT HOLD. Measured 14. 9. 2026,
three runs, see MERANIE_GAMEPAD.md:

  DualSense over HID, G7 Pro over XInput, Steam on and off:
  idle while moving the controller had a median of 15-16 ms, while in
  resting stretches it jumped to 50-65 seconds. The cursor did not move once
  in 348 samples, so it is neither Steam Input nor a gyroscope mapped to the
  mouse.

The `extra_idle_fn` slot nevertheless stays and is NOT dead: this is one
computer. If on another machine the gamepad turned out not to be seen, the
player would be permanently idle for the app - and that is a silent failure
that does not show up as an error, only as an app that stays silent or
speaks up at the worst moment. The resulting idle is the MINIMUM of all
sources, i.e. "since the last input from ANYWHERE".

The module has no Tk and no I/O. `idle_ms()` can be replaced in tests, so
the whole logic can be checked without a display and without the test
waiting in real time.
"""

import time

# How often it asks Windows. 4x per second is enough to recognise a pause
# of 2.5 s with a precision of a quarter of a second, and it is cheap enough
# to run for the whole time you play.
POLL_S = 0.25

# For the measurement-window record, 1x per second is enough - the
# same density as heart rate from the watch. 4 Hz would grow to ~58k pairs
# over four hours.
LOG_EVERY_S = 1.0

# Under this many ms since the last input = the player is doing something
# right now.
ACTIVE_IDLE_MS = 1000

# Cap on the record. At 1 Hz that is ~16 hours, i.e. longer than any
# session - but it stops an app left running over the weekend from eating
# memory forever. When the sensor is switched on, the record is reset anyway.
MAX_SAMPLES = 60000

# --------------------------------------------------------------------------
# WHAT THE PLAYER IS PLAYING WITH RIGHT NOW
# --------------------------------------------------------------------------
# The app knows two things about input at once: `GetLastInputInfo` (sees
# EVERYTHING including the controller, see MERANIE_GAMEPAD.md) and reports
# from `gamepad.py` (sees ONLY the controller). From their intersection the
# device class can be derived:
#
#   controller reports fresh input              -> controller
#   controller silent, but system reports input -> keyboard/mouse
#   gamepad listener not running at all         -> UNKNOWN (not "keyboard"!)
#
# The last row matters: if "don't know" were reported as keyboard, then on a
# machine with the listener switched off the app would tell a player with a
# controller something untrue - and it would be written on the screen, so
# they would believe it.
#
# Only the DEVICE CLASS is determined, nothing more. Which button it was the
# app does not learn here (`note_external_input` takes no name), nor from
# `GetLastInputInfo`, which returns only a number of milliseconds.
SRC_PAD = "pad"
SRC_KB = "kb"

# How long the source is remembered after the player stops playing. Without
# it the pictogram would go dark at every break and light up at every press -
# and that is exactly the "wandering movement" that peripheral vision
# notices the most.
SOURCE_MEMORY_S = 300.0


# --------------------------------------------------------------------------
# Win32 - the only thing that asks the operating system
# --------------------------------------------------------------------------

def _make_idle_reader():
    """Return an idle_ms() function, or None when this system cannot do it.

    Separate from the rest for the tests and because the module must be
    importable even where there is no user32 (CI, other OS) - otherwise the
    import of the whole app would fail.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        user32.GetLastInputInfo.restype = wintypes.BOOL
        kernel32.GetTickCount.restype = wintypes.DWORD

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)

        def idle_ms():
            if not user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            # GetTickCount is 32-bit and wraps around after ~49 days;
            # masking to 32 bits keeps the difference correct across the wrap.
            return (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF

        idle_ms()          # check that it really works now, not only during play
        return idle_ms
    except Exception:
        return None


_SYSTEM_IDLE = _make_idle_reader()
AVAILABLE = _SYSTEM_IDLE is not None


def idle_ms():
    """Ms since the last input, or None when the system cannot tell."""
    return _SYSTEM_IDLE() if _SYSTEM_IDLE else None


# --------------------------------------------------------------------------
# Watching activity during the session
# --------------------------------------------------------------------------

class ActivityTracker:
    """Tracks whether the player is active, pause length and the window record.

    Called EXCLUSIVELY from the GUI thread (from `_tick_activity`), just like
    `HeartStats` - that is why there is no lock here.
    """

    def __init__(self, idle_fn=None, extra_idle_fn=None, clock=time.time):
        self._idle_fn = idle_fn if idle_fn is not None else idle_ms
        self._extra_idle_fn = extra_idle_fn
        self._clock = clock
        # Is the gamepad listener running? Until it runs, the device class
        # CANNOT be determined - see the module header. The app switches this
        # on at `gamepad.start()`.
        self._gamepad_watched = False
        self.reset_session()

    def set_gamepad_watched(self, watched):
        """The app reports whether the gamepad listener is really running.

        Without this, "no reports from the controller" could not be told
        apart from "nobody is watching the controller" and the app would
        tell a player with a controller that they are playing on the
        keyboard.
        """
        self._gamepad_watched = bool(watched)
        if not self._gamepad_watched:
            self._source = None
            self._source_at = None

    # ---------- session ----------

    def reset_session(self):
        self.samples = []           # [(timestamp, idle_ms)] ~1x per second
        self.last_idle = None
        self.active_since = None
        self.pause_since = None
        self._last_log_ts = None
        self._external_at = None    # when another source last reported input
        # Device class, not a specific input. See the module header.
        self._source = None
        self._source_at = None

    def note_external_input(self, now=None):
        """Another source reports input RIGHT NOW (e.g. a controller button).

        WHAT it was is not recorded - only that something happened.
        `gamepad.py` sends controller activity here (buttons, d-pad, sticks
        and triggers beyond the dead zone, held ones every 0.2 s) since
        phase 3, when it stopped being a cue trigger and became a second
        source of information about activity.
        """
        now = self._clock() if now is None else now
        self._external_at = now

    def set_extra_source(self, fn):
        """Attach a second activity source (e.g. the gamepad).

        `fn()` returns ms since the last input from that source, or None.
        The resulting idle is the minimum of all sources.
        """
        self._extra_idle_fn = fn

    # ---------- collection ----------

    def poll(self, now=None):
        """One measurement. Returns the current idle in ms (or None).

        A record into `samples` is made only once per `LOG_EVERY_S`, even
        though it asks 4x more often - the more frequent sampling is needed
        to recognise a pause, not for the file.
        """
        now = self._clock() if now is None else now
        idle = self._idle_fn()
        if self._extra_idle_fn is not None:
            try:
                extra = self._extra_idle_fn()
            except Exception:
                extra = None
            if extra is not None:
                idle = extra if idle is None else min(idle, extra)

        # Input reported by another source (gamepad) counts as "something
        # happened just now" - the freshest of the two is taken.
        if self._external_at is not None:
            vonkajsie = max(0.0, (now - self._external_at) * 1000.0)
            idle = vonkajsie if idle is None else min(idle, vonkajsie)

        self.last_idle = idle
        self._urci_zdroj(now, idle)

        if idle is not None:
            if idle < ACTIVE_IDLE_MS:
                # the player is doing something right now
                if self.active_since is None:
                    self.active_since = now
                self.pause_since = None
            else:
                # the pause started at the moment of the last input, not now
                if self.pause_since is None:
                    self.pause_since = now - idle / 1000.0
                self.active_since = None

        if self._last_log_ts is None or now - self._last_log_ts >= LOG_EVERY_S:
            self.samples.append((now, idle))
            self._last_log_ts = now
            if len(self.samples) > MAX_SAMPLES:
                del self.samples[:len(self.samples) - MAX_SAMPLES]
        return idle

    # ---------- what the player is playing with ----------

    def _urci_zdroj(self, now, idle):
        """Device class from intersecting both sources. See module header."""
        if not self._gamepad_watched:
            return
        if idle is None or idle >= ACTIVE_IDLE_MS:
            return                  # nothing happening now, source unchanged
        cerstvy_pad = (self._external_at is not None
                       and (now - self._external_at) * 1000.0 < ACTIVE_IDLE_MS)
        self._source = SRC_PAD if cerstvy_pad else SRC_KB
        self._source_at = now

    def source(self, now=None):
        """SRC_PAD / SRC_KB, or None when it cannot be told.

        None means WE DON'T KNOW, not "no input": the gamepad listener may
        not be running, or the player has not pressed anything yet. The
        caller should then stay silent, not guess - it is information that
        goes on the screen and the player will believe it.
        """
        if self._source is None or self._source_at is None:
            return None
        now = self._clock() if now is None else now
        if now - self._source_at > SOURCE_MEMORY_S:
            return None
        return self._source

    # ---------- derived ----------

    @property
    def is_active(self):
        return self.last_idle is not None and self.last_idle < ACTIVE_IDLE_MS

    def pause_s(self, now=None):
        """How long the current pause has been going on.

        0.0 = the player is doing something right now.
        None = WE DON'T KNOW - the system does not report idle (other OS,
        failed user32).

        The difference between zero and None matters. Phase 2 postpones a
        cue to a pause; if "don't know" pretended to be "no pause", then on
        a machine without idle a pause would never come and ALL cues would
        fall into the "pause did not come" branch - i.e. they would be
        delivered silently and the silent control arm would get mixed in
        with them. The measurement would come out without a single voiced
        cue and nobody would know why.
        """
        if self.last_idle is None:
            return None
        if self.pause_since is None:
            return 0.0
        now = self._clock() if now is None else now
        return max(0.0, now - self.pause_since)

    def active_share(self, t0, t1):
        """Share of the time <t0,t1> in which the player was active (0.0-1.0).

        The same as `measure.active_share` - here as a convenience over its
        own record, so the caller does not have to reach into `samples`.
        """
        inside = [idle for ts, idle in self.samples if t0 <= ts <= t1]
        if not inside:
            return None
        active = sum(1 for idle in inside if idle is not None and idle < ACTIVE_IDLE_MS)
        return active / float(len(inside))


# --------------------------------------------------------------------------
# Input without a single pause
# --------------------------------------------------------------------------
# Measured on the author's setup: a G7 Pro with the gyroscope on ("Motion
# Always On") reset `GetLastInputInfo` every ~16 ms, so the app saw no pause
# until the gyro was switched off - and a cue waiting for a pause never got
# a chance to come.
# A person playing makes a short pause (menu, respawn, loading) within 20
# minutes; if none is seen, the PC more likely has something that reports
# input by itself. The app does not know for sure, so it is only a quiet
# line on Today, once per session.
NONSTOP_INPUT_S = 20 * 60.0
# The longest step that is counted - a sleeping PC or a frozen window must
# not "add" minutes without a pause in a single tick.
_NONSTOP_MAX_STEP_S = 5.0


class NonstopInputWatch:
    """Whether the app has not seen even a short pause in the input for long.

    `update()` is called with every `poll` (4x per second) with the current
    `pause_s` and with whether watching makes sense - the app is listening
    and heart rate is coming in, i.e. the player has the watch on their
    wrist and is at the PC (the app has no better sign). Time without a
    pause is counted only then; a short heart-rate dropout does not reset
    it, it just does not grow. Only a pause resets it. Returns whether the
    line should be shown.

    Once per session: when the line disappears (a pause came), it will not
    be shown again in this session. A new session is started by `reset()`.
    """

    def __init__(self, after_s=NONSTOP_INPUT_S):
        self.after_s = float(after_s)
        self.reset()

    def reset(self):
        self._bez_pauzy_s = 0.0
        self._last = None
        self.shown = False      # already shown in this session
        self.active = False     # showing right now

    def update(self, now, pause_s, watching, pause_needed_s=2.5):
        last, self._last = self._last, now
        if pause_s is not None and pause_s >= pause_needed_s:
            # A pause came - so input is not arriving nonstop.
            self._bez_pauzy_s = 0.0
            self.active = False
            return False
        if watching and pause_s is not None and last is not None:
            self._bez_pauzy_s += max(0.0, min(now - last, _NONSTOP_MAX_STEP_S))
        if not self.shown and self._bez_pauzy_s >= self.after_s:
            self.shown = True
            self.active = True
        return self.active
