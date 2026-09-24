"""Ovladac (Xbox aj PlayStation) ako druhy zdroj informacie o aktivite.

Od fazy 3 uz NIC NESPUSTA. Hlasi len "hrac prave hra" - popri
`GetLastInputInfo` (activity.py), ktory ovladac na tomto Windowse vidi tiez
(MERANIE_GAMEPAD.md), ale je to jeden pocitac. Z listenera odchadza iba
aktivita (`on_button("activity")`) a meno pripojeneho zariadenia do dennika.
Ktore tlacidlo, pacicka ci spust to bola, NEODCHADZA nikam (SAFETY.md);
vnutri sa drzi len to, co je PRAVE drzane, a pri pusteni sa to zahodi.

JOY*, NIE CONTROLLER* (odmeral zadavatel na G7 Pro, pygame-ce 2.5.8 /
SDL 2.32.10): pygame posiela LEN udalosti JOY* (JOYAXISMOTION,
JOYBUTTONDOWN/UP, JOYHATMOTION). CONTROLLER* udalosti SDL posiela len pre
zariadenie otvorene ako SDL_GameController - a listener ho otvara ako
joystick. Povodna verzia pocuvala len CONTROLLER*, takze bola hlucha:
hranie na ovladaci nevidela ako aktivitu nikdy. CONTROLLER* ostava
obsluzene, keby ich nejake zariadenie predsa poslalo.

HODNOTY OSI
  * JOY: float -1..1. pygame deli SDL Sint16 cislom 32768 - overene na
    virtualnom SDL joysticku: 20000 -> 0.61, -32768 -> -1.0.
  * CONTROLLER: int -32768..32767, spuste 0..32767 (dokumentacia
    pygame._sdl2.controller) - tu sa delia 32767.
  * SPUSTE V JOYSTICK API KLUDUJU NA -1.0, nie na 0 (XInput, RawInput aj
    HIDAPI ich davaju ako plnu os). Ktora os je spust, sa NEHADA z poradia -
    to sa lisi podla backendu (XInput a2/a5, RawInput a4/a5) - ale povie to
    SDL mapovanie ovladaca, to iste, z ktoreho SDL sklada CONTROLLER*
    udalosti. Spust v kludovej polohe teda NIE JE aktivita.

MRTVE ZONY = nativne XInput: lava pacicka 7849/32767, prava 8689/32767
(kruhovo, ako v ukazke Microsoftu k XInputGetState), spust 30/255 zdvihu.
Pod nimi je to sum stojaceho ovladaca - G7 Pro s vlastnou mrtvou zonou 0
posielal v kludovej polohe ~3000 JOYAXISMOTION za sekundu.

Beh je v samostatnom vlakne s vlastnou udalostnou sluckou (SDL_VIDEODRIVER
"dummy", takze sa neotvara ziadne okno).
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
    # SDL mapovanie ovladaca - z neho sa vie, ktora os joysticku je pacicka
    # a ktora spust. Bez neho (stary pygame) sa osi sleduju opatrnejsie.
    from pygame._sdl2 import controller as _sdl_controller
except Exception:
    _sdl_controller = None

# Nativne mrtve zony XInput (XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE,
# ..._RIGHT_THUMB_DEADZONE, XINPUT_GAMEPAD_TRIGGER_THRESHOLD). Pod nimi je
# vychylka len klud/sum stojaceho ovladaca, nad nimi hrac naozaj hybe.
# Drzana pacicka/spust nad nimi sa rata ako aktivita - inak by mierenie
# vyzeralo ako pauza a hlaska by padla uprostred boja.
LEFT_STICK_DEADZONE = 7849 / 32767.0
RIGHT_STICK_DEADZONE = 8689 / 32767.0
TRIGGER_DEADZONE = 30 / 255.0
# Os, ktorej ulohu SDL nepozna (zariadenie bez mapovania - volant, knipel):
# nevie sa, kde ma klud, takze aktivita je POHYB o viac nez vacsia z mrtvych
# zon, nie poloha. Drzana poloha takej osi sa preto nepotvrdzuje - radsej to
# nez os, ktora by svojou kludovou polohou hlasila aktivitu navzdy.
UNKNOWN_AXIS_STEP = RIGHT_STICK_DEADZONE
# Ako casto sa potvrdi drzany vstup - hlboko pod prahom pauzy 2,5 s.
REASSERT_S = 0.2
# Jedine, co z listenera o vstupe odchadza.
ACTIVITY = "activity"

_STICK_ROLES = ("lx", "ly", "rx", "ry")
_TRIGGER_ROLES = ("lt", "rt")
# Obratena plna os spuste ('a3~', PS3 cez DirectInput): klud +1.0, stlacena
# -1.0. Hodnota sa otoci a dalej je to obycajna spust.
_INVERTED = "~"
_INVERTED_TRIGGER_ROLES = tuple(r + _INVERTED for r in _TRIGGER_ROLES)
# Spust na POLOVICI osi: '+a4' = stlacenie ide do plusu, '-a4' do minusu
# (klud moze byt v strede aj na opacnom konci osi). DirectInput mava obe
# spuste na jednej osi s kludom v strede ('+a2' aj '-a2') - to je `half`
# a stlacenie je vychylka na hociktoru stranu.
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
    """SDL mapovanie ovladaca -> {index osi joysticku: uloha}.

    `mapping` je slovnik z `Controller.get_mapping()`; G7 Pro zadavatela ma
    {'leftx': 'a0', 'lefty': 'a1', 'rightx': 'a2', 'righty': 'a3',
    'lefttrigger': 'a4', 'righttrigger': 'a5', ...}. Zapis je SDL-ovsky:
    '+a4' / '-a4' je polovica osi (uloha `half+` / `half-`), 'a3~' obratena
    os (uloha `lt~` / `rt~`). Dve spuste na jednej osi (DirectInput '+a2' a
    '-a2') su `half` s kludom v strede. Co sa precitat neda alebo si
    odporuje, vynecha sa - os bez ulohy sa sleduje opatrnejsie
    (`UNKNOWN_AXIS_STEP`), aby ziadna kludova poloha nebola aktivita navzdy.
    """
    claims = {}
    for key, role in _MAPPING_ROLES.items():
        m = _AXIS_REF.match(str((mapping or {}).get(key, "")).strip())
        if not m:
            continue
        half, axis, inverted = m.group(1), int(m.group(2)), m.group(3)
        if role in _TRIGGER_ROLES:
            if half and inverted:
                continue            # obratena polovica osi - klud sa nevie
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
            roles[axis] = _HALF_TRIGGER     # viac spusti na jednej osi
    return roles


def _axis_roles_for(index):
    """Ulohy osi zariadenia `index` zo SDL mapovania; {} ked ho SDL nepozna."""
    if _sdl_controller is None:
        return {}
    try:
        if not _sdl_controller.get_init():
            _sdl_controller.init()
        if not _sdl_controller.is_controller(index):
            return {}
        # Otvara sa len na precitanie mapovania a hned sa zatvara: otvoreny
        # SDL_GameController by popri JOY* posielal aj CONTROLLER* a kazdy
        # vstup by prisiel zbytocne dvakrat.
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
    """Vlastne vlakno, ktore pri aktivite na ovladaci zavola
    `on_button("activity")` - pri stlaceni/vychyleni hned, pri drzani
    kazdych `REASSERT_S`. Nic ine o vstupe nevracia."""

    def __init__(self, on_button, on_status=None):
        self.on_button = on_button
        self.on_status = on_status
        self._thread = None
        self._running = False
        self._devices = {}                # instance_id -> Joystick
        self._reset_state()

    def _reset_state(self):
        self._roles = {}                  # instance_id -> {os: uloha}
        # PRAVE drzane/vychylene prvky: (instance_id, zdroj, druh, index).
        # Len aby drzany vstup nevyzeral ako pauza - nikam neodchadza a pri
        # pusteni (alebo odpojeni zariadenia) sa zahodi.
        self._held = set()
        self._sticks = {}                 # (iid, zdroj, "l"/"r") -> [x, y]
        self._trigger_rest = {}           # (iid, os) -> najnizsia videna hodnota
        self._anchors = {}                # (iid, os) -> kotva osi bez ulohy
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
        # Nic nesmie ostat "drzane" do dalsieho zapnutia pocuvania.
        self._reset_state()

    def _activity(self):
        self.on_button(ACTIVITY)

    def _reassert_activity(self, now=None):
        """Drzane tlacidlo ani stojaca vychylena pacicka NEgeneruju nove
        udalosti, takze bez tohto by hrac drziaci mierenie/beh vyzeral ako
        necinny (pause_s rastie) a ARMED spustac by sa ozval uprostred boja -
        presny opak zameru "ozvi sa v pauze". Kazdych `REASSERT_S` (hlboko pod
        prahom pauzy 2.5 s) potvrdime aktivitu, kym nieco drzi alebo je
        pacicka/spust za mrtvou zonou."""
        now = time.time() if now is None else now
        if now - self._last_activity_poll < REASSERT_S:
            return
        self._last_activity_poll = now
        if self._held:
            self._activity()

    def _open(self, index):
        try:
            # pygame 2 zariadenie otvara uz tu (`init()` je od 2.4 zastarane).
            joy = pygame.joystick.Joystick(index)
            iid = joy.get_instance_id()
            if iid in self._devices:
                # Uz otvorene: pri starte ho otvori slucka aj JOYDEVICEADDED.
                return
            self._devices[iid] = joy
            self._roles[iid] = _axis_roles_for(index)
            self._notify(f"connected:{joy.get_name()}")
        except Exception:
            # Ovladac sa nepodarilo otvorit - hrac by inak nevedel, preco mu
            # appka gamepad "nevidi". Otvaranie je zriedkave, staci warning.
            log.warning("gamepad: index %s sa nepodarilo otvorit", index, exc_info=True)

    def _forget(self, iid):
        """Zariadenie odislo: zahod vsetko, co od neho bolo drzane. Inak by
        tlacidlo drzane v momente odpojenia ostalo "drzane" navzdy a appka
        by uz nikdy nevidela pauzu."""
        self._held = {k for k in self._held if k[0] != iid}
        for store in (self._sticks, self._trigger_rest, self._anchors):
            for key in [k for k in store if k[0] == iid]:
                del store[key]

    def _set_held(self, key, on):
        """Prvok presiel za mrtvu zonu (aktivita hned) alebo sa vratil."""
        if on:
            if key not in self._held:
                self._held.add(key)
                self._activity()
        else:
            self._held.discard(key)

    def _stick(self, iid, src, role, value):
        """Pacicka kruhovo, ako v ukazke XInput: velkost vychylky (x, y)."""
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
            # Plna os: klud -1.0, stlacena +1.0, zdvih je teda (v - klud) / 2.
            # Klud = najnizsia videna hodnota; prva udalost osi nesie jej
            # povodnu hodnotu (SDL ju posle pred prvym pohybom). Keby spust
            # niekde kludovala inde nez na -1, nebude aspon "stlacena" navzdy.
            rest = min(value, self._trigger_rest.get((iid, axis), value))
            self._trigger_rest[(iid, axis)] = rest
            self._set_held((iid, "joy", "t", axis),
                           (value - rest) / 2.0 > TRIGGER_DEADZONE)
        elif role in _HALF_ROLES:
            # Zdvih je vychylka na stranu stlacenia; pri `half` na hociktoru.
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
