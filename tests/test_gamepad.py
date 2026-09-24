# -*- coding: utf-8 -*-
"""Ovladac ako zdroj aktivity (gamepad.py) - JOY* aj CONTROLLER* udalosti.

Odmeral zadavatel na G7 Pro (pygame-ce 2.5.8 / SDL 2.32.10): pygame
posiela LEN JOY* udalosti, nikdy CONTROLLER*. Listener pocuval len
CONTROLLER*, takze hranie na ovladaci nevidel nikdy - a hraca s ovladacom
mohla hlaska zastihnut uprostred boja.

Testy bezia bez zariadenia: falosne udalosti cez `pygame.event.Event`,
ulohy osi z realneho SDL mapovania G7 Pro. Cas re-assertu sa podava
priamo, nic necaka v realnom case.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pygame = pytest.importorskip("pygame")

import gamepad  # noqa: E402

# Skutocne SDL mapovanie G7 Pro zadavatela ("(Xbox 360 Controller for
# Windows)", 6 osi, 11 tlacidiel, 1 hat) - spuste su a4/a5 a kluduju na -1.0.
G7_MAPPING = {
    'a': 'b0', 'b': 'b1', 'x': 'b2', 'y': 'b3', 'back': 'b6', 'guide': 'b10',
    'start': 'b7', 'leftstick': 'b8', 'rightstick': 'b9',
    'leftshoulder': 'b4', 'rightshoulder': 'b5', 'dpup': 'h0.1',
    'dpdown': 'h0.4', 'dpleft': 'h0.8', 'dpright': 'h0.2',
    'leftx': 'a0', 'lefty': 'a1', 'rightx': 'a2', 'righty': 'a3',
    'lefttrigger': 'a4', 'righttrigger': 'a5', 'crc': '1ea9',
    'platform': 'Windows'}
# XInput backend SDL: ine poradie - spuste su a2/a5, prava pacicka a3/a4.
XINPUT_MAPPING = {
    'leftx': 'a0', 'lefty': 'a1', 'lefttrigger': 'a2', 'rightx': 'a3',
    'righty': 'a4', 'righttrigger': 'a5', 'a': 'b0'}

IID = 7


class _Listener:
    """Listener bez vlakna a bez zariadenia + zoznam toho, co z neho odislo."""

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
        """Posunie cas a spusti re-assert - ako slucka listenera."""
        self.t += s
        self.gl._reassert_activity(now=self.t)

    def activity_during(self, seconds):
        """Kolko hlaseni aktivity odislo za `seconds` bez novych udalosti."""
        pred = len(self.out)
        for _ in range(int(seconds / 0.25)):
            self.tick()
        return len(self.out) - pred


# --------------------------------------------------------------------------
# mapovanie SDL -> ulohy osi
# --------------------------------------------------------------------------

def test_mapovanie_g7_pro_a_xinput_backendu():
    assert gamepad.axis_roles(G7_MAPPING) == {
        0: "lx", 1: "ly", 2: "rx", 3: "ry", 4: "lt", 5: "rt"}
    # rovnaky ovladac cez XInput backend: spuste inde - poradie sa nehada
    assert gamepad.axis_roles(XINPUT_MAPPING) == {
        0: "lx", 1: "ly", 2: "lt", 3: "rx", 4: "ry", 5: "rt"}


def test_mapovanie_polovicnej_osi_a_nezmyslov():
    # DirectInput: obe spuste na jednej osi s kludom v strede
    roles = gamepad.axis_roles({'lefttrigger': '+a2', 'righttrigger': '-a2',
                                'lefty': 'a1~'})
    assert roles == {2: "half", 1: "ly"}
    assert gamepad.axis_roles({'lefttrigger': 'b6', 'leftx': 'h0.1'}) == {}
    assert gamepad.axis_roles(None) == {}


def test_mapovanie_polovic_obratenych_a_zdielanych_osi():
    """Zapis SDL: '+a4' / '-a4' je polovica osi, 'a3~' obratena os. Vzory su
    zo vstavanej databazy SDL 2.32 (Steam Virtual Gamepad, PS3 cez
    DirectInput, SL-6555-SBK)."""
    assert gamepad.axis_roles({'lefttrigger': '+a2', 'righttrigger': '-a2'}) == {2: "half"}
    assert gamepad.axis_roles({'lefttrigger': 'a3~', 'righttrigger': 'a4~'}) == {
        3: "lt~", 4: "rt~"}
    assert gamepad.axis_roles({'lefttrigger': '-a4', 'righttrigger': 'a4'}) == {4: "half"}
    assert gamepad.axis_roles({'righttrigger': '+a5'}) == {5: "half+"}
    # obratena polovica osi a dve pacicky na jednej osi: radsej bez ulohy
    assert gamepad.axis_roles({'lefttrigger': '+a2~', 'leftx': 'a0',
                               'rightx': 'a0'}) == {}


def test_mrtve_zony_su_nativne_xinput():
    assert gamepad.LEFT_STICK_DEADZONE == pytest.approx(7849 / 32767)
    assert gamepad.RIGHT_STICK_DEADZONE == pytest.approx(8689 / 32767)
    assert gamepad.TRIGGER_DEADZONE == pytest.approx(30 / 255)
    assert gamepad.REASSERT_S == pytest.approx(0.2)


# --------------------------------------------------------------------------
# JOY* udalosti (to, co pygame naozaj posiela)
# --------------------------------------------------------------------------

def test_kludovy_sum_pod_mrtvou_zonou_nie_je_aktivita():
    """G7 Pro s vlastnou mrtvou zonou 0 posielal v kludnej polohe ~3000
    JOYAXISMOTION za sekundu. Ziadna z nich nesmie byt aktivita."""
    L = _Listener()
    L.axis(4, -1.0)
    L.axis(5, -1.0)
    for i in range(3000):
        s = 1 if i % 2 else -1
        L.axis(0, s * 0.15)
        L.axis(1, -s * 0.15)          # kruhovo 0.21 < 0.2395
        L.axis(2, s * 0.25)           # 0.25 < prava 0.2652
        L.axis(4, -1.0 + 0.02)        # spust sa len jemne chveje
    assert L.out == []
    assert L.activity_during(2.0) == 0


def test_pacicka_za_mrtvou_zonou_je_aktivita_aj_drzana():
    L = _Listener()
    L.axis(0, 0.6)
    assert L.out == [gamepad.ACTIVITY]
    # drzana stojaca pacicka nove udalosti neposiela - potvrdi ju re-assert
    assert L.activity_during(1.0) >= 4
    L.axis(0, 0.05)
    assert L.activity_during(1.0) == 0


def test_lava_a_prava_pacicka_maju_svoje_zony_kruhovo():
    L = _Listener()
    L.axis(0, 0.25)                    # lava: 0.25 > 0.2395
    assert len(L.out) == 1
    L.axis(0, 0.0)
    L.axis(2, 0.25)                    # prava: 0.25 < 0.2652
    assert len(L.out) == 1
    L.axis(3, 0.2)                     # prava kruhovo: hypot(0.25, 0.2) = 0.32
    assert len(L.out) == 2


def test_spust_v_klude_na_minus_jedna_nie_je_aktivita():
    L = _Listener()
    L.axis(4, -1.0)
    L.axis(5, -1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(5, -1.0 + 2 * 0.05)         # 5 % zdvihu < 30/255
    assert L.out == []
    L.axis(5, -1.0 + 2 * 0.3)          # 30 % zdvihu - drzany plyn/strelba
    assert L.out == [gamepad.ACTIVITY]
    assert L.activity_during(1.0) >= 4
    L.axis(5, -1.0)
    assert L.activity_during(1.0) == 0


def test_xinput_backend_spust_na_a2_nie_je_pacicka_vlavo():
    """Stara logika by os 2 na -1.0 pri XInput poradi brala ako pacicku
    vytocenu na doraz - a hrac by bol "aktivny" navzdy."""
    L = _Listener(mapping=XINPUT_MAPPING)
    L.axis(2, -1.0)
    L.axis(5, -1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(3, -1.0)                    # toto JE prava pacicka na doraz
    assert L.out == [gamepad.ACTIVITY]


def test_spust_ktora_kluduje_inde_nie_je_stlacena_navzdy():
    L = _Listener()
    L.axis(4, 0.0)                     # prva hodnota = kludova (zvlastny HW)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(4, 1.0)
    assert L.out == [gamepad.ACTIVITY]


def test_polovica_osi_v_klude_na_minus_jedna_nie_je_aktivita():
    """'+a5': stlacenie ide do plusu. Os v klude na -1.0 nie je vychylka -
    inak by hrac bol "aktivny" navzdy a pauza by neprisla."""
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
    L.axis(2, -0.6)                    # prava spust
    assert L.out == [gamepad.ACTIVITY]
    L.axis(2, 0.0)
    assert L.activity_during(1.0) == 0


def test_obratena_spust_kluduje_na_plus_jedna():
    """PS3 cez DirectInput ('a3~'): klud +1.0, stlacena -1.0. Bez otocenia
    by spust nebola aktivita nikdy - ani ked ju hrac drzi."""
    L = _Listener(mapping={'lefttrigger': 'a3~'})
    L.axis(3, 1.0)
    assert L.out == [] and L.activity_during(1.0) == 0
    L.axis(3, -0.2)                    # 60 % zdvihu
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
    """Tlacidlo drzane pri odpojeni by inak ostalo "drzane" navzdy a appka
    by uz nikdy nevidela pauzu."""
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
# CONTROLLER* udalosti (keby ich nejake zariadenie predsa poslalo)
# --------------------------------------------------------------------------

def test_controller_udalosti_s_celociselnymi_hodnotami():
    L = _Listener(mapping=None)        # CONTROLLER osi maju pevne ulohy
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
# zariadenie bez SDL mapovania, sukromie, otvaranie
# --------------------------------------------------------------------------

def test_os_bez_mapovania_rata_pohyb_nie_polohu():
    """Knipel/volant bez mapovania: kde ma os klud, sa nevie. Aktivita je
    pohyb nad mrtvou zonou; drzana poloha sa nepotvrdzuje, aby os nikdy
    nehlasila aktivitu navzdy."""
    L = _Listener(mapping=None)
    L.axis(3, -1.0)                    # prva hodnota = povodna (kludova)
    L.axis(3, -0.9)                    # chvenie
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
    """Pri starte otvori ovladac slucka aj JOYDEVICEADDED toho isteho
    zariadenia - v denniku ma byt jedno "pripojeny", nie dve."""
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
