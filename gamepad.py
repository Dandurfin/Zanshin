"""Controller (Xbox and PlayStation) as a second source of activity info.

Since phase 3 it TRIGGERS NOTHING any more. It only reports "the player is
playing right now" - alongside `GetLastInputInfo` (activity.py), which on
this Windows sees the controller too (MERANIE_GAMEPAD.md), but it is one
computer. Only the activity (`on_button("activity")`) and the name of the
connected device, for the journal, leave the listener. Which button, stick
or trigger it was goes NOWHERE (SAFETY.md); inside, only what is held RIGHT
NOW is kept, and it is dropped on release.

JOY*, NOT CONTROLLER* (measured by the author on a G7 Pro, pygame-ce
2.5.8 / SDL 2.32.10): pygame sends ONLY JOY* events (JOYAXISMOTION,
JOYBUTTONDOWN/UP, JOYHATMOTION). SDL sends CONTROLLER* events only for a
device opened as an SDL_GameController - and the listener opens it as a
joystick. The original version listened only to CONTROLLER*, so it was
deaf: it never saw playing on the controller as activity. CONTROLLER* stays
handled, in case some device does send them after all.

AXIS VALUES
  * JOY: float -1..1. pygame divides the SDL Sint16 by 32768 - verified on
    a virtual SDL joystick: 20000 -> 0.61, -32768 -> -1.0.
  * CONTROLLER: int -32768..32767, triggers 0..32767 (documentation of
    pygame._sdl2.controller) - divided by 32767 here.
  * IN THE JOYSTICK API, TRIGGERS REST AT -1.0, not at 0 (XInput, RawInput
    and HIDAPI all give them as a full axis). Which axis is a trigger is NOT
    GUESSED from the order - that differs by backend (XInput a2/a5,
    RawInput a4/a5) - but the SDL controller mapping tells it, the same one
    SDL builds the CONTROLLER* events from. So a trigger at rest is NOT
    activity.

DEAD ZONES = native XInput: left stick 7849/32767, right 8689/32767
(circular, as in Microsoft's XInputGetState sample), trigger 30/255 of
travel. Below them it is the noise of an idle controller - a G7 Pro with
its own dead zone of 0 sent ~3000 JOYAXISMOTION per second at rest.

It runs in a separate thread with its own event loop (SDL_VIDEODRIVER
"dummy", so no window is opened).
"""

import math
import os
import re
import threading
import time

import logging_setup

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

log = logging_setup.get_logger("gamepad")

try:
    import pygame
    GAMEPAD_AVAILABLE = True
except Exception:
    pygame = None
    GAMEPAD_AVAILABLE = False

try:
    # The SDL controller mapping - it tells which joystick axis is a stick
    # and which a trigger. Without it (old pygame) the axes are watched
    # more cautiously.
    from pygame._sdl2 import controller as _sdl_controller
except Exception:
    _sdl_controller = None

# Native XInput dead zones (XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE,
# ..._RIGHT_THUMB_DEADZONE, XINPUT_GAMEPAD_TRIGGER_THRESHOLD). Below them
# the deflection is only the rest/noise of an idle controller; above them
# the player is really moving. A stick/trigger held above them counts as
# activity - otherwise aiming would look like a pause and a cue would
# land in the middle of a fight.
LEFT_STICK_DEADZONE = 7849 / 32767.0
RIGHT_STICK_DEADZONE = 8689 / 32767.0
TRIGGER_DEADZONE = 30 / 255.0
# An axis whose role SDL does not know (a device without a mapping - a
# wheel, a flight stick): where it rests is unknown, so activity is
# MOVEMENT by more than the larger of the dead zones, not position. A held
# position of such an axis is therefore not reasserted - better that than
# an axis that would report activity forever from its rest position.
UNKNOWN_AXIS_STEP = RIGHT_STICK_DEADZONE
# How often a held input is reasserted - far below the 2.5 s pause threshold.
REASSERT_S = 0.2
# The only thing about input that leaves the listener.
ACTIVITY = "activity"

_STICK_ROLES = ("lx", "ly", "rx", "ry")
_TRIGGER_ROLES = ("lt", "rt")
# An inverted full trigger axis ('a3~', PS3 via DirectInput): rest +1.0,
# pressed -1.0. The value is flipped, and from then on it is an ordinary
# trigger.
_INVERTED = "~"
_INVERTED_TRIGGER_ROLES = tuple(r + _INVERTED for r in _TRIGGER_ROLES)
# A trigger on HALF an axis: '+a4' = pressing goes positive, '-a4'
# negative (rest may be in the middle or at the opposite end of the axis).
# DirectInput often has both triggers on one axis with rest in the middle
# ('+a2' and '-a2') - that is `half`, and a press is a deflection to
# either side.
_HALF_TRIGGER = "half"
_HALF_ROLES = (_HALF_TRIGGER, _HALF_TRIGGER + "+", _HALF_TRIGGER + "-")
_MAPPING_ROLES = {"leftx": "lx", "lefty": "ly", "rightx": "rx",
                  "righty": "ry", "lefttrigger": "lt", "righttrigger": "rt"}
_AXIS_REF = re.compile(r"^([+-]?)a(\d+)(~?)$")

_CONTROLLER_ROLES = {}
if GAMEPAD_AVAILABLE:
    _CONTROLLER_ROLES = {
        pygame.CONTROLLER_AXIS_LEFTX: "lx",
        pygame.CONTROLLER_AXIS_LEFTY: "ly",
        pygame.CONTROLLER_AXIS_RIGHTX: "rx",
        pygame.CONTROLLER_AXIS_RIGHTY: "ry",
        pygame.CONTROLLER_AXIS_TRIGGERLEFT: "lt",
        pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "rt",
    }


def axis_roles(mapping):
    """SDL controller mapping -> {joystick axis index: role}.

    `mapping` is the dict from `Controller.get_mapping()`; the author's
    G7 Pro has {'leftx': 'a0', 'lefty': 'a1', 'rightx': 'a2', 'righty': 'a3',
    'lefttrigger': 'a4', 'righttrigger': 'a5', ...}. The notation is SDL's:
    '+a4' / '-a4' is half an axis (role `half+` / `half-`), 'a3~' an
    inverted axis (role `lt~` / `rt~`). Two triggers on one axis
    (DirectInput '+a2' and '-a2') are `half` with rest in the middle.
    Whatever cannot be read or contradicts itself is skipped - an axis
    without a role is watched more cautiously (`UNKNOWN_AXIS_STEP`), so
    that no rest position is activity forever.
    """
    claims = {}
    for key, role in _MAPPING_ROLES.items():
        m = _AXIS_REF.match(str((mapping or {}).get(key, "")).strip())
        if not m:
            continue
        half, axis, inverted = m.group(1), int(m.group(2)), m.group(3)
        if role in _TRIGGER_ROLES:
            if half and inverted:
                continue            # inverted half axis - rest unknown
            if half:
                role = _HALF_TRIGGER + half
            elif inverted:
                role += _INVERTED
        claims.setdefault(axis, []).append(role)
    roles = {}
    for axis, found in claims.items():
        if len(found) == 1:
            roles[axis] = found[0]
        elif not any(r in _STICK_ROLES for r in found):
            roles[axis] = _HALF_TRIGGER     # several triggers on one axis
    return roles


def _axis_roles_for(index):
    """Device `index`'s axis roles (SDL mapping); {} if SDL doesn't know it."""
    if _sdl_controller is None:
        return {}
    try:
        if not _sdl_controller.get_init():
            _sdl_controller.init()
        if not _sdl_controller.is_controller(index):
            return {}
        # Opened only to read the mapping and closed right away: an open
        # SDL_GameController would send CONTROLLER* alongside JOY*, and every
        # input would needlessly arrive twice.
        ctl = _sdl_controller.Controller(index)
        try:
            mapping = ctl.get_mapping()
        finally:
            ctl.quit()
    except Exception:
        log.warning("gamepad: mapovanie ovladaca %s sa nepodarilo precitat",
                    index, exc_info=True)
        return {}
    return axis_roles(mapping)


class GamepadListener:
    """Its own thread that calls `on_button("activity")` on controller
    activity - right away on a press/deflection, every `REASSERT_S` while
    held. It returns nothing else about the input."""

    def __init__(self, on_button, on_status=None):
        self.on_button = on_button
        self.on_status = on_status
        self._thread = None
        self._running = False
        self._devices = {}                # instance_id -> Joystick
        self._reset_state()

    def _reset_state(self):
        self._roles = {}                  # instance_id -> {axis: role}
        # Elements held/deflected RIGHT NOW: (instance_id, source, kind,
        # index). Only so that a held input does not look like a pause - it
        # goes nowhere and is dropped on release (or when the device
        # disconnects).
        self._held = set()
        self._sticks = {}                 # (iid, source, "l"/"r") -> [x, y]
        self._trigger_rest = {}           # (iid, axis) -> lowest value seen
        self._anchors = {}                # (iid, axis) -> anchor of an axis without a role
        self._last_activity_poll = 0.0    # throttling of the activity re-assert

    @property
    def available(self):
        return GAMEPAD_AVAILABLE

    def start(self):
        if not GAMEPAD_AVAILABLE or self._running:
            return False
        try:
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=1.0)

    def _notify(self, message):
        if self.on_status:
            try:
                self.on_status(message)
            except Exception:
                pass

    def _loop(self):
        try:
            for i in range(pygame.joystick.get_count()):
                self._open(i)
        except Exception:
            pass

        while self._running:
            try:
                for event in pygame.event.get():
                    self._handle(event)
            except Exception:
                # An error in event handling would otherwise silently kill all
                # input from the controller. We log it once, so the loop does
                # not flood the log.
                if not getattr(self, "_loop_warned", False):
                    self._loop_warned = True
                    log.exception("gamepad: spracovanie udalosti zlyhalo "
                                  "(dalsie sa uz nevypisu)")
            self._reassert_activity()
            time.sleep(0.01)

        for joy in self._devices.values():
            try:
                joy.quit()
            except Exception:
                pass
        self._devices.clear()
        # Nothing may stay "held" until listening is turned on next time.
        self._reset_state()

    def _activity(self):
        self.on_button(ACTIVITY)

    def _reassert_activity(self, now=None):
        """A held button or a deflected stick held still DOES NOT generate
        new events, so without this a player holding aim/sprint would look
        idle (pause_s grows) and an ARMED trigger would speak up mid-fight -
        the exact opposite of the intent "speak up during a pause". Every
        `REASSERT_S` (far below the 2.5 s pause threshold) we reassert
        activity while something is held or a stick/trigger is beyond the
        dead zone."""
        now = time.time() if now is None else now
        if now - self._last_activity_poll < REASSERT_S:
            return
        self._last_activity_poll = now
        if self._held:
            self._activity()

    def _open(self, index):
        try:
            # pygame 2 already opens the device here (`init()` is
            # deprecated since 2.4).
            joy = pygame.joystick.Joystick(index)
            iid = joy.get_instance_id()
            if iid in self._devices:
                # Already open: at start both the loop and
                # JOYDEVICEADDED open it.
                return
            self._devices[iid] = joy
            self._roles[iid] = _axis_roles_for(index)
            self._notify(f"connected:{joy.get_name()}")
        except Exception:
            # The controller could not be opened - otherwise the player would
            # not know why the app does not "see" the gamepad. Opening is
            # rare, a warning is enough.
            log.warning("gamepad: index %s sa nepodarilo otvorit", index, exc_info=True)

    def _forget(self, iid):
        """The device went away: drop everything that was held from it.
        Otherwise a button held at the moment of unplugging would stay
        "held" forever and the app would never see a pause again."""
        self._held = {k for k in self._held if k[0] != iid}
        for store in (self._sticks, self._trigger_rest, self._anchors):
            for key in [k for k in store if k[0] == iid]:
                del store[key]

    def _set_held(self, key, on):
        """An element crossed the dead zone (activity at once) or came back."""
        if on:
            if key not in self._held:
                self._held.add(key)
                self._activity()
        else:
            self._held.discard(key)

    def _stick(self, iid, src, role, value):
        """Stick, circular as in the XInput sample: (x, y) deflection size."""
        side = role[0]
        xy = self._sticks.setdefault((iid, src, side), [0.0, 0.0])
        xy[0 if role[1] == "x" else 1] = value
        deadzone = LEFT_STICK_DEADZONE if side == "l" else RIGHT_STICK_DEADZONE
        self._set_held((iid, src, "s", side), math.hypot(xy[0], xy[1]) > deadzone)

    def _joy_axis(self, iid, axis, value):
        role = self._roles.get(iid, {}).get(axis)
        if role in _STICK_ROLES:
            self._stick(iid, "joy", role, value)
        elif role in _TRIGGER_ROLES or role in _INVERTED_TRIGGER_ROLES:
            if role in _INVERTED_TRIGGER_ROLES:
                value = -value
            # Full axis: rest -1.0, pressed +1.0, so the travel is
            # (v - rest) / 2. Rest = the lowest value seen; the first event
            # of the axis carries its initial value (SDL sends it before the
            # first movement). If a trigger rested somewhere other than -1,
            # at least it will not be "pressed" forever.
            rest = min(value, self._trigger_rest.get((iid, axis), value))
            self._trigger_rest[(iid, axis)] = rest
            self._set_held((iid, "joy", "t", axis),
                           (value - rest) / 2.0 > TRIGGER_DEADZONE)
        elif role in _HALF_ROLES:
            # Travel = deflection to the press side; with `half`, either side.
            if role.endswith("+"):
                travel = value
            elif role.endswith("-"):
                travel = -value
            else:
                travel = abs(value)
            self._set_held((iid, "joy", "t", axis), travel > TRIGGER_DEADZONE)
        else:
            anchor = self._anchors.get((iid, axis))
            if anchor is None:
                self._anchors[(iid, axis)] = value
            elif abs(value - anchor) > UNKNOWN_AXIS_STEP:
                self._anchors[(iid, axis)] = value
                self._activity()

    def _controller_axis(self, iid, axis, value):
        role = _CONTROLLER_ROLES.get(axis)
        if role in _STICK_ROLES:
            self._stick(iid, "ctl", role, max(-1.0, min(1.0, value / 32767.0)))
        elif role in _TRIGGER_ROLES:
            self._set_held((iid, "ctl", "t", axis), value / 32767.0 > TRIGGER_DEADZONE)

    def _handle(self, event):
        kind = event.type
        if kind == pygame.JOYDEVICEADDED:
            self._open(event.device_index)
            return
        iid = getattr(event, "instance_id", None)
        if kind == pygame.JOYDEVICEREMOVED:
            known = self._devices.pop(iid, None) is not None
            self._roles.pop(iid, None)
            self._forget(iid)
            if known:
                self._notify("disconnected")
        elif kind == pygame.CONTROLLERDEVICEREMOVED:
            self._forget(iid)
        elif kind in (pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN):
            src = "joy" if kind == pygame.JOYBUTTONDOWN else "ctl"
            self._held.add((iid, src, "b", event.button))
            self._activity()
        elif kind in (pygame.JOYBUTTONUP, pygame.CONTROLLERBUTTONUP):
            src = "joy" if kind == pygame.JOYBUTTONUP else "ctl"
            self._held.discard((iid, src, "b", event.button))
        elif kind == pygame.JOYHATMOTION:
            self._set_held((iid, "joy", "h", event.hat),
                           tuple(event.value) != (0, 0))
        elif kind == pygame.JOYAXISMOTION:
            self._joy_axis(iid, event.axis, float(event.value))
        elif kind == pygame.CONTROLLERAXISMOTION:
            self._controller_axis(iid, event.axis, event.value)
