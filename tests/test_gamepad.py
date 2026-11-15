# -*- coding: utf-8 -*-
"""Controller as activity source (gamepad.py) - JOY* and CONTROLLER* events.

Measured by the requester on a G7 Pro (pygame-ce 2.5.8 / SDL 2.32.10): pygame
sends ONLY JOY* events, never CONTROLLER*. The listener listened only to
CONTROLLER*, so it never saw playing on a controller - and a cue could catch
a player with a controller in the middle of a fight.

Tests run without a device: fake events via `pygame.event.Event`, axis
roles from the real SDL mapping of the G7 Pro. The re-assert time is passed
directly, nothing waits in real time.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pygame = pytest.importorskip("pygame")

import gamepad  # noqa: E402

# The requester's real SDL mapping of the G7 Pro ("(Xbox 360 Controller for
# Windows)", 6 axes, 11 buttons, 1 hat) - triggers are a4/a5, rest at -1.0.
G7_MAPPING = {
    'a': 'b0', 'b': 'b1', 'x': 'b2', 'y': 'b3', 'back': 'b6', 'guide': 'b10',
    'start': 'b7', 'leftstick': 'b8', 'rightstick': 'b9',
    'leftshoulder': 'b4', 'rightshoulder': 'b5', 'dpup': 'h0.1',
    'dpdown': 'h0.4', 'dpleft': 'h0.8', 'dpright': 'h0.2',
    'leftx': 'a0', 'lefty': 'a1', 'rightx': 'a2', 'righty': 'a3',
    'lefttrigger': 'a4', 'righttrigger': 'a5', 'crc': '1ea9',
    'platform': 'Windows'}
# SDL XInput backend: different order - triggers a2/a5, right stick a3/a4.
XINPUT_MAPPING = {
    'leftx': 'a0', 'lefty': 'a1', 'lefttrigger': 'a2', 'rightx': 'a3',
    'righty': 'a4', 'righttrigger': 'a5', 'a': 'b0'}

IID = 7


class _Listener:
    """Listener without thread or device + a list of what it sent out."""

    def __init__(self, mapping=G7_MAPPING, iid=IID):
        self.out = []
        self.status = []
        self.gl = gamepad.GamepadListener(self.out.append, self.status.append)
        if mapping is not None:
            self.gl._roles[iid] = gamepad.axis_roles(mapping)
        self.t = 1000.0

    def send(self, kind, **kw):
        kw.setdefault("instance_id", IID)
        self.gl._handle(pygame.event.Event(kind, **kw))

    def axis(self, axis, value, iid=IID):
        self.send(pygame.JOYAXISMOTION, axis=axis, value=value, instance_id=iid)

    def tick(self, s=0.25):
        """Advances time and runs the re-assert - like the listener loop."""
        self.t += s
        self.gl._reassert_activity(now=self.t)

    def activity_during(self, seconds):
        """How many activity reports left in `seconds` without new events."""
        pred = len(self.out)
        for _ in range(int(seconds / 0.25)):
            self.tick()
        return len(self.out) - pred


# --------------------------------------------------------------------------
# SDL mapping -> axis roles
# --------------------------------------------------------------------------

def test_mapovanie_g7_pro_a_xinput_backendu():
    assert gamepad.axis_roles(G7_MAPPING) == {
        0: "lx", 1: "ly", 2: "rx", 3: "ry", 4: "lt", 5: "rt"}
    # same controller via XInput: triggers elsewhere - order is not guessed
    assert gamepad.axis_roles(XINPUT_MAPPING) == {
        0: "lx", 1: "ly", 2: "lt", 3: "rx", 4: "ry", 5: "rt"}


def test_mapovanie_polovicnej_osi_a_nezmyslov():
    # DirectInput: both triggers on one axis with rest in the middle
    roles = gamepad.axis_roles({'lefttrigger': '+a2', 'righttrigger': '-a2',
                                'lefty': 'a1~'})
    assert roles == {2: "half", 1: "ly"}
    assert gamepad.axis_roles({'lefttrigger': 'b6', 'leftx': 'h0.1'}) == {}
    assert gamepad.axis_roles(None) == {}


def test_mapovanie_polovic_obratenych_a_zdielanych_osi():
    """SDL notation: '+a4' / '-a4' is half an axis, 'a3~' an inverted axis. The
    patterns are from the built-in SDL 2.32 database (Steam Virtual Gamepad,
    PS3 via DirectInput, SL-6555-SBK)."""
    assert gamepad.axis_roles({'lefttrigger': '+a2', 'righttrigger': '-a2'}) == {2: "half"}
    assert gamepad.axis_roles({'lefttrigger': 'a3~', 'righttrigger': 'a4~'}) == {
        3: "lt~", 4: "rt~"}
    assert gamepad.axis_roles({'lefttrigger': '-a4', 'righttrigger': 'a4'}) == {4: "half"}
    assert gamepad.axis_roles({'righttrigger': '+a5'}) == {5: "half+"}
    # an inverted half-axis and two sticks on one axis: better no role
    assert gamepad.axis_roles({'lefttrigger': '+a2~', 'leftx': 'a0',
                               'rightx': 'a0'}) == {}


def test_mrtve_zony_su_nativne_xinput():
    assert gamepad.LEFT_STICK_DEADZONE == pytest.approx(7849 / 32767)
    assert gamepad.RIGHT_STICK_DEADZONE == pytest.approx(8689 / 32767)
    assert gamepad.TRIGGER_DEADZONE == pytest.approx(30 / 255)
    assert gamepad.REASSERT_S == pytest.approx(0.2)


# --------------------------------------------------------------------------
# JOY* events (what pygame really sends)
# --------------------------------------------------------------------------

def test_kludovy_sum_pod_mrtvou_zonou_nie_je_aktivita():
    """The G7 Pro with its own dead zone 0 sent ~3000 JOYAXISMOTION per second
    at rest. None of them may be activity."""
    L = _Listener()
    L.axis(4, -1.0)
    L.axis(5, -1.0)
    for i in range(3000):
        s = 1 if i % 2 else -1
        L.axis(0, s * 0.15)
        L.axis(1, -s * 0.15)          # circular 0.21 < 0.2395
        L.axis(2, s * 0.25)           # 0.25 < right 0.2652
        L.axis(4, -1.0 + 0.02)        # the trigger only trembles slightly
    assert L.out == []
    assert L.activity_during(2.0) == 0


def test_pacicka_za_mrtvou_zonou_je_aktivita_aj_drzana():
    L = _Listener()
    L.axis(0, 0.6)
    assert L.out == [gamepad.ACTIVITY]
    # a held still stick sends no new events - the re-assert confirms it
    assert L.activity_during(1.0) >= 4
    L.axis(0, 0.05)
    assert L.activity_during(1.0) == 0


def test_lava_a_prava_pacicka_maju_svoje_zony_kruhovo():
    L = _Listener()
    L.axis(0, 0.25)                    # left: 0.25 > 0.2395
    assert len(L.out) == 1
    L.axis(0, 0.0)
    L.axis(2, 0.25)                    # right: 0.25 < 0.2652
    assert len(L.out) == 1
    L.axis(3, 0.2)                     # right, circular: hypot(0.25, 0.2) = 0.32
    assert len(L.out) == 2


def test_spust_v_klude_na_minus_jedna_nie_je_aktivita():
    L = _Listener()
    L.axis(4, -1.0)
    L.axis(5, -1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(5, -1.0 + 2 * 0.05)         # 5 % of travel < 30/255
    assert L.out == []
    L.axis(5, -1.0 + 2 * 0.3)          # 30 % of travel - held throttle/fire
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(1.0) >= 4
    L.axis(5, -1.0)
    assert L.activity_during(1.0) == 0


def test_xinput_backend_spust_na_a2_nie_je_pacicka_vlavo():
    """The old logic would take axis 2 at -1.0 in the XInput order as a stick
    pushed all the way - and the player would be "active" forever."""
    L = _Listener(mapping=XINPUT_MAPPING)
    L.axis(2, -1.0)
    L.axis(5, -1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(3, -1.0)                    # this IS the right stick pushed all the way
    assert L.out == [gamepad.ACTIVITY]


def test_spust_ktora_kluduje_inde_nie_je_stlacena_navzdy():
    L = _Listener()
    L.axis(4, 0.0)                     # first value = the rest value (odd HW)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(4, 1.0)
    assert L.out == [gamepad.ACTIVITY]


def test_polovica_osi_v_klude_na_minus_jedna_nie_je_aktivita():
    """'+a5': pressing goes into plus. An axis resting at -1.0 is not a
    deflection - otherwise the player would be "active" forever and the
    pause would never come."""
    L = _Listener(mapping={'righttrigger': '+a5'})
    L.axis(5, -1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(5, 0.5)
    assert L.out == [gamepad.ACTIVITY]
    L.axis(5, -1.0)
    assert L.activity_during(1.0) == 0


def test_dve_spuste_na_jednej_osi_kluduju_v_strede():
    L = _Listener(mapping={'lefttrigger': '+a2', 'righttrigger': '-a2'})
    L.axis(2, 0.02)
    assert L.out == []
    L.axis(2, -0.6)                    # right trigger
    assert L.out == [gamepad.ACTIVITY]
    L.axis(2, 0.0)
    assert L.activity_during(1.0) == 0


def test_obratena_spust_kluduje_na_plus_jedna():
    """PS3 via DirectInput ('a3~'): rest +1.0, pressed -1.0. Without inverting,
    the trigger would never be activity - not even when the player holds it."""
    L = _Listener(mapping={'lefttrigger': 'a3~'})
    L.axis(3, 1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(3, -0.2)                    # 60 % of travel
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(1.0) >= 4
    L.axis(3, 1.0)
    assert L.activity_during(1.0) == 0


def test_hat_mimo_stredu_je_aktivita_kym_je_drzany():
    L = _Listener()
    L.send(pygame.JOYHATMOTION, hat=0, value=(0, 1))
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(1.0) >= 4
    L.send(pygame.JOYHATMOTION, hat=0, value=(0, 0))
    assert L.activity_during(1.0) == 0


def test_drzane_tlacidlo_je_aktivita_az_do_pustenia():
    L = _Listener()
    L.send(pygame.JOYBUTTONDOWN, button=5)
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(2.0) >= 8
    L.send(pygame.JOYBUTTONUP, button=5)
    assert L.activity_during(1.0) == 0


def test_re_assert_ide_kazdych_0_2_s_nie_castejsie():
    L = _Listener()
    L.send(pygame.JOYBUTTONDOWN, button=0)
    pred = len(L.out)
    for t in (500.0, 500.1, 500.19, 500.21, 500.3, 500.42):
        L.gl._reassert_activity(now=t)
    assert len(L.out) - pred == 3      # 500.0, 500.21, 500.42


def test_odpojenie_zariadenia_zahodi_vsetko_drzane():
    """A button held at disconnect would otherwise stay "held" forever and the
    app would never see a pause again."""
    L = _Listener()
    L.send(pygame.JOYBUTTONDOWN, button=1)
    L.axis(0, 0.9)
    L.axis(5, 0.5)
    L.send(pygame.JOYHATMOTION, hat=0, value=(1, 0))
    L.gl._devices[IID] = object()
    L.send(pygame.JOYDEVICEREMOVED)
    assert L.gl._held == set()
    assert L.activity_during(1.0) == 0
    assert L.status == ["disconnected"]
    assert IID not in L.gl._roles


def test_odpojenie_ovladaca_cez_controller_udalost_tiez_zahodi_stav():
    L = _Listener()
    L.send(pygame.CONTROLLERBUTTONDOWN, button=0)
    L.send(pygame.CONTROLLERDEVICEREMOVED)
    assert L.gl._held == set()
    assert L.activity_during(1.0) == 0


def test_odpojenie_ineho_zariadenia_necha_drzane_to_druhe():
    L = _Listener()
    L.send(pygame.JOYBUTTONDOWN, button=1)
    L.send(pygame.JOYDEVICEREMOVED, instance_id=IID + 1)
    assert L.activity_during(0.5) >= 2


# --------------------------------------------------------------------------
# CONTROLLER* events (in case some device does send them)
# --------------------------------------------------------------------------

def test_controller_udalosti_s_celociselnymi_hodnotami():
    L = _Listener(mapping=None)        # CONTROLLER axes have fixed roles
    ax = pygame.CONTROLLERAXISMOTION
    L.send(ax, axis=pygame.CONTROLLER_AXIS_LEFTX, value=5000)      # 0.15
    L.send(ax, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT, value=0)
    L.send(ax, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=3000)   # 0.09
    assert L.out == [] and L.activity_during(1.0) == 0
    L.send(ax, axis=pygame.CONTROLLER_AXIS_LEFTX, value=20000)     # 0.61
    assert L.out == [gamepad.ACTIVITY]
    L.send(ax, axis=pygame.CONTROLLER_AXIS_LEFTX, value=0)
    L.send(ax, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=8000)   # 0.24
    assert len(L.out) == 2
    assert L.activity_during(1.0) >= 4
    L.send(ax, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT, value=0)
    assert L.activity_during(1.0) == 0


def test_controller_tlacidlo_drzane_a_pustene():
    L = _Listener(mapping=None)
    L.send(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A)
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(0.5) >= 2
    L.send(pygame.CONTROLLERBUTTONUP, button=pygame.CONTROLLER_BUTTON_A)
    assert L.activity_during(1.0) == 0


# --------------------------------------------------------------------------
# a device without SDL mapping, privacy, opening
# --------------------------------------------------------------------------

def test_os_bez_mapovania_rata_pohyb_nie_polohu():
    """Joystick/wheel without a mapping: where the axis rests is unknown.
    Activity is movement above the dead zone; a held position is not
    confirmed, so that the axis never reports activity forever."""
    L = _Listener(mapping=None)
    L.axis(3, -1.0)                    # first value = the original (rest)
    L.axis(3, -0.9)                    # trembling
    assert L.out == []
    L.axis(3, 0.5)
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(1.0) == 0


def test_z_listenera_odchadza_len_aktivita():
    L = _Listener()
    L.send(pygame.JOYBUTTONDOWN, button=3)
    L.send(pygame.JOYHATMOTION, hat=0, value=(-1, 0))
    L.axis(1, -0.8)
    L.axis(4, 0.9)
    L.send(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_Y)
    L.activity_during(1.0)
    assert L.out and set(L.out) == {gamepad.ACTIVITY}


class _FakeJoy:
    def __init__(self, index):
        self.index = index

    def get_instance_id(self):
        return 40 + self.index

    def get_name(self):
        return "Fake Pad"

    def quit(self):
        pass


def test_otvorenie_precita_ulohy_a_neotvara_dvakrat(monkeypatch):
    """At start the controller is opened both by the loop and by JOYDEVICEADDED
    of the same device - the journal should have one "pripojeny" (connected)
    line, not two."""
    monkeypatch.setattr(gamepad.pygame.joystick, "Joystick", _FakeJoy)
    monkeypatch.setattr(gamepad, "_axis_roles_for",
                        lambda index: gamepad.axis_roles(G7_MAPPING))
    L = _Listener(mapping=None)
    L.gl._open(0)
    L.send(pygame.JOYDEVICEADDED, device_index=0)
    assert L.status == ["connected:Fake Pad"]
    assert L.gl._roles[40][4] == "lt"


def test_bez_sdl_mapovania_su_ulohy_prazdne(monkeypatch):
    monkeypatch.setattr(gamepad, "_sdl_controller", None)
    assert gamepad._axis_roles_for(0) == {}
