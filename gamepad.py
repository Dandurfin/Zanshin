"""Podpora gamepadov (Xbox aj PlayStation) ako dalsieho typu triggeru.

Pouziva pygame/SDL2 "game controller" vrstvu, ktora automaticky
zjednocuje rozlozenie tlacidiel Xbox aj PlayStation ovladacov (cez
vstavanu SDL databazu gamecontrollerdb) do jednej sady nazvov: A/B/X/Y,
LB/RB, LT/RT, Select/Start, L3/R3, D-pad. Fyzicky teda funguju oba typy
ovladacov - len sa na DualShock/DualSense volaju tlacidla inak
(Cross=A, Circle=B, Square=X, Triangle=Y, L1=LB, R1=RB, L2=LT, R2=RT).

Beh je v samostatnom vlakne s vlastnou udalostnou sluckou (SDL_VIDEODRIVER
"dummy", takze sa neotvara ziadne okno). Analogove spuste (LT/RT) sa
prevadzaju na digitalne stlacenie/pustenie prekrocenim prahu.
"""

import os
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

TRIGGER_THRESHOLD = 0.55
# Mrtva zona paciciek: nad nou sa vychylka rata ako aktivita (mierenie, beh),
# pod nou je to len klud/drift stojaceho ovladaca. 0.35 je nad beznym driftom
# (~0.2) a hlboko pod skutocnym mierenim (0.6-1.0) - viz oprava "controller
# false-pause": drzana pacicka/tlacidlo inak vyzeraju ako pauza a spustac by
# padol uprostred boja.
STICK_DEADZONE = 0.35

# SDL_GameController tlacidlo -> kratky, znackovo neutralny nazov.
_BUTTON_LABELS = {}
if GAMEPAD_AVAILABLE:
    _BUTTON_LABELS = {
        pygame.CONTROLLER_BUTTON_A: "A",
        pygame.CONTROLLER_BUTTON_B: "B",
        pygame.CONTROLLER_BUTTON_X: "X",
        pygame.CONTROLLER_BUTTON_Y: "Y",
        pygame.CONTROLLER_BUTTON_BACK: "Select",
        pygame.CONTROLLER_BUTTON_GUIDE: "Guide",
        pygame.CONTROLLER_BUTTON_START: "Start",
        pygame.CONTROLLER_BUTTON_LEFTSTICK: "L3",
        pygame.CONTROLLER_BUTTON_RIGHTSTICK: "R3",
        pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "LB",
        pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "RB",
        pygame.CONTROLLER_BUTTON_DPAD_UP: "D-Up",
        pygame.CONTROLLER_BUTTON_DPAD_DOWN: "D-Down",
        pygame.CONTROLLER_BUTTON_DPAD_LEFT: "D-Left",
        pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "D-Right",
    }
    _AXIS_LABELS = {
        pygame.CONTROLLER_AXIS_TRIGGERLEFT: "LT",
        pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "RT",
    }
    # Osi paciciek - nesledujeme ich ako spustace, ale ako AKTIVITU (mierenie).
    _STICK_AXES = {pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY,
                   pygame.CONTROLLER_AXIS_RIGHTX, pygame.CONTROLLER_AXIS_RIGHTY}
else:
    _AXIS_LABELS = {}
    _STICK_AXES = set()


class GamepadListener:
    """Analogicke k pynput.keyboard/mouse.Listener - vlastne vlakno,
    ktore pri stlaceni tlacidla zavola `on_button(label)`."""

    def __init__(self, on_button, on_status=None):
        self.on_button = on_button
        self.on_status = on_status
        self._thread = None
        self._running = False
        self._devices = {}
        self._trigger_pressed = {}
        self._buttons_down = set()        # drzane tlacidla (nerobia repeat)
        self._axis_values = {}            # posledna hodnota paciciek
        self._last_activity_poll = 0.0    # skrtenie re-assertu aktivity

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
                # Chyba v spracovani udalosti by inak ticho zabila vsetok
                # vstup z ovladaca. Zalogujeme raz, nech to slucka nezaplavi.
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

    def _reassert_activity(self):
        """Drzane tlacidlo ani stojaca vychylena pacicka NEgeneruju nove
        udalosti, takze bez tohto by hrac drziaci mierenie/beh vyzeral ako
        necinny (pause_s rastie) a ARMED spustac by sa ozval uprostred boja -
        presny opak zameru "ozvi sa v pauze". Kazdych ~0.2 s (hlboko pod prahom
        pauzy 2.5 s) potvrdime aktivitu, kym nieco drzi alebo je pacicka za
        mrtvou zonou. `on_button` len zapise aktivitu (meno sa nikam neuklada)."""
        now = time.time()
        if now - self._last_activity_poll < 0.2:
            return
        self._last_activity_poll = now
        aktivny = (bool(self._buttons_down)
                   or any(self._trigger_pressed.values())
                   or any(abs(v) > STICK_DEADZONE for v in self._axis_values.values()))
        if aktivny:
            self.on_button("activity")

    def _open(self, index):
        try:
            joy = pygame.joystick.Joystick(index)
            joy.init()
            self._devices[index] = joy
            self._notify(f"connected:{joy.get_name()}")
        except Exception:
            # Ovladac sa nepodarilo otvorit - hrac by inak nevedel, preco mu
            # appka gamepad "nevidi". Otvaranie je zriedkave, staci warning.
            log.warning("gamepad: index %s sa nepodarilo otvorit", index, exc_info=True)

    def _handle(self, event):
        if event.type == pygame.JOYDEVICEADDED:
            self._open(event.device_index)
        elif event.type == pygame.JOYDEVICEREMOVED:
            self._devices.pop(event.instance_id, None)
            self._notify("disconnected")
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            self._buttons_down.add(event.button)
            label = _BUTTON_LABELS.get(event.button)
            if label:
                self.on_button(label)
        elif event.type == pygame.CONTROLLERBUTTONUP:
            self._buttons_down.discard(event.button)
        elif event.type == pygame.CONTROLLERAXISMOTION:
            if event.axis in _STICK_AXES:
                self._axis_values[event.axis] = event.value   # aktivita, nie spustac
                return
            label = _AXIS_LABELS.get(event.axis)
            if not label:
                return
            pressed = event.value > TRIGGER_THRESHOLD
            was_pressed = self._trigger_pressed.get(label, False)
            if pressed and not was_pressed:
                self.on_button(label)
            self._trigger_pressed[label] = pressed
