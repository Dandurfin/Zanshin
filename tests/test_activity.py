# -*- coding: utf-8 -*-
"""Sledovanie aktivity bez klavesoveho hooku.

`ActivityTracker` dostava hodiny aj zdroj idle zvonku, takze sa da cely
prejst bez Windowsu a bez cakania v realnom case - test posuva cas sam.

Dolezite je hlavne to, ze pauza sa pocita od POSLEDNEHO VSTUPU, nie od
momentu, kedy si to appka vsimla. Na tom stoji cely odklad hlasky na
pauzu vo faze 2: keby sa pauza merala az od merania, prah 2,5 s by sa
podla nahody trafil raz po 2,5 s a inokedy po 2,75 s.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import activity  # noqa: E402


class Hodiny:
    """Rucne posuvany cas, aby test nemusel nic cakat."""

    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def sleduj(idle_values, hodiny=None, **kw):
    """Tracker, ktoremu idle diktuje zoznam - jedna hodnota na poll()."""
    hodiny = hodiny or Hodiny()
    postupnost = iter(idle_values)
    tracker = activity.ActivityTracker(
        idle_fn=lambda: next(postupnost), clock=hodiny, **kw)
    return tracker, hodiny


def test_modul_sa_da_importovat_aj_ked_win32_nejde():
    """Import nesmie padnut - inak by spadol import celej appky."""
    assert isinstance(activity.AVAILABLE, bool)
    assert activity.idle_ms() is None or activity.idle_ms() >= 0


def test_aktivny_a_pauza_sa_prepinaju():
    tracker, hodiny = sleduj([100, 200, 5000, 50])

    tracker.poll()
    assert tracker.is_active is True
    assert tracker.pause_s() == 0.0

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is True

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is False

    hodiny.posun(activity.POLL_S)
    tracker.poll()
    assert tracker.is_active is True
    assert tracker.pause_s() == 0.0


def test_pauza_sa_pocita_od_posledneho_vstupu_nie_od_merania():
    """Idle 4000 ms znamena, ze pauza trva 4 s - aj ked meriame prave teraz."""
    tracker, hodiny = sleduj([4000])
    tracker.poll()
    assert tracker.pause_s() == 4.0
    # a rastie dalej s casom, bez dalsieho pollu
    hodiny.posun(2.0)
    assert tracker.pause_s() == 6.0


def test_zaznam_je_redsi_nez_pytanie():
    """Pyta sa 4x za sekundu, do zaznamu ide 1x - inak by za styri hodiny
    narastol na desiatky tisic dvojic zbytocne."""
    tracker, hodiny = sleduj([100] * 20)
    for _ in range(20):
        tracker.poll()
        hodiny.posun(activity.POLL_S)
    # 20 pollov po 0,25 s = 5 sekund
    assert 5 <= len(tracker.samples) <= 7


def test_druhy_zdroj_sa_beri_ako_minimum():
    """Gamepad (ak sa ukaze, ze treba) je dalsi zdroj vstupu, nie nahrada.

    Vysledne idle je "od posledneho vstupu ODKIALKOLVEK", cize minimum.
    """
    tracker, _ = sleduj([9000], extra_idle_fn=lambda: 100)
    assert tracker.poll() == 100
    assert tracker.is_active is True


def test_rozbity_druhy_zdroj_neposkodi_meranie():
    def zlyha():
        raise RuntimeError("ovladac sa odpojil")

    tracker, _ = sleduj([300], extra_idle_fn=zlyha)
    assert tracker.poll() == 300


def test_chybajuci_zdroj_idle_nespadne():
    """Na systeme bez GetLastInputInfo sa len nic nevie - nepadne to."""
    tracker = activity.ActivityTracker(idle_fn=lambda: None, clock=Hodiny())
    assert tracker.poll() is None
    assert tracker.is_active is False


def test_neznama_pauza_nie_je_nulova_pauza():
    """None znamena "neviem", nie "ziadna pauza" - a je to rozdiel.

    Faza 2 odklada hlasku na pauzu. Keby sa "neviem" tvarilo ako nula,
    na stroji bez idle by pauza nikdy nenastala, vsetky hlasky by spadli
    do vetvy "pauza neprisla" a tiche kontrolne rameno by sa s nimi
    zmiesalo. Meranie by vyslo bez jedinej hlasnej hlasky.
    """
    slepy = activity.ActivityTracker(idle_fn=lambda: None, clock=Hodiny())
    slepy.poll()
    assert slepy.pause_s() is None

    hodiny = Hodiny()
    vidiaci = activity.ActivityTracker(idle_fn=lambda: 100, clock=hodiny)
    vidiaci.poll()
    assert vidiaci.pause_s() == 0.0      # vie, ze pauza nie je


def test_zapnutie_senzora_vynuluje_zaznam():
    tracker, hodiny = sleduj([100] * 10)
    for _ in range(10):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.samples
    tracker.reset_session()
    assert tracker.samples == []
    assert tracker.pause_since is None


def test_podiel_aktivity_nad_vlastnym_zaznamom():
    hodiny = Hodiny()
    idle = [100, 100, 9000, 9000]
    postupnost = iter(idle)
    tracker = activity.ActivityTracker(idle_fn=lambda: next(postupnost),
                                       clock=hodiny)
    start = hodiny.t
    for _ in range(4):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.active_share(start, hodiny.t) == 0.5
    assert tracker.active_share(start - 100.0, start - 50.0) is None


def test_zaznam_ma_strop():
    """Appka nechana bezat cez vikend nesmie zrat pamat donekonecna."""
    povodny = activity.MAX_SAMPLES
    activity.MAX_SAMPLES = 10
    try:
        hodiny = Hodiny()
        tracker = activity.ActivityTracker(idle_fn=lambda: 100, clock=hodiny)
        for _ in range(40):
            tracker.poll()
            hodiny.posun(1.0)
        assert len(tracker.samples) == 10
        # ostavaju NAJNOVSIE
        assert tracker.samples[-1][0] == hodiny.t - 1.0
    finally:
        activity.MAX_SAMPLES = povodny


# --------------------------------------------------------------------------
# Z čoho hráč práve hrá (ovládač vs klávesnica)
# --------------------------------------------------------------------------

def test_bez_gamepad_listenera_zdroj_nevieme():
    """NEVIEME nie je to isté čo „klávesnica".

    Keby sa mlčanie ovládača hlásilo ako klávesnica, na stroji s vypnutým
    listenerom by appka hráčovi s ovládačom napísala nepravdu — a bolo by to
    na obrazovke, čiže by tomu veril.
    """
    tracker, hodiny = sleduj([50] * 5)
    for _ in range(5):
        tracker.poll()
        hodiny.posun(1.0)
    assert tracker.source(now=hodiny.t) is None


def test_cerstvy_vstup_z_ovladaca_sa_rozozna():
    tracker, hodiny = sleduj([50] * 5)
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD


def test_ked_ovladac_mlci_je_to_klavesnica():
    """`GetLastInputInfo` hlási vstup, ovládač nie — takže to bolo niečo iné."""
    tracker, hodiny = sleduj([50] * 5)
    tracker.set_gamepad_watched(True)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_KB


def test_prechod_z_ovladaca_na_klavesnicu():
    """Hráč odloží ovládač a začne písať do chatu."""
    tracker, hodiny = sleduj([50] * 6)
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    hodiny.posun(5.0)                       # ovládač už nehlási nič
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_KB


def test_zdroj_prezije_kratku_prestavku():
    """Bez pamäte by piktogram pri každej prestávke zhasol a pri každom
    stlačení sa rozsvietil — presne ten putujúci pohyb, ktorý ruší."""
    tracker, hodiny = sleduj([50, 50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    hodiny.posun(activity.SOURCE_MEMORY_S - 1.0)
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    hodiny.posun(2.0)
    assert tracker.source(now=hodiny.t) is None, "po dlhej pauze sa už netvrdí nič"


def test_vypnutie_listenera_zdroj_zabudne():
    tracker, hodiny = sleduj([50, 50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) == activity.SRC_PAD
    tracker.set_gamepad_watched(False)
    assert tracker.source(now=hodiny.t) is None


def test_zdroj_nikdy_nedrzi_co_sa_stlacilo():
    """SAFETY.md: appka sa nedozvie, ktoré tlačidlo to bolo. Zisťuje sa
    trieda zariadenia a nič viac."""
    tracker, hodiny = sleduj([50])
    tracker.set_gamepad_watched(True)
    tracker.note_external_input(now=hodiny.t)
    tracker.poll()
    assert tracker.source(now=hodiny.t) in (activity.SRC_PAD, activity.SRC_KB)
    ulozene = [v for v in vars(tracker).values() if isinstance(v, str)]
    assert all(v in (activity.SRC_PAD, activity.SRC_KB) for v in ulozene), ulozene
