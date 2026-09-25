# -*- coding: utf-8 -*-
"""Tolerovaný prepad nie je čas nad prahom (0.2.1).

Súvislá cesta natiahnutia sa počítala ako `now - _above_since`, teda
nástennými hodinami VRÁTANE prepadov kratších než `dip_grace_s` (20 s).
Vzorec „1 s nad prahom, 19 s pod ním" preto natiahol hlášku po minúte, hoci
nad prahom boli štyri vzorky. README pritom sľubuje hlášku, keď záťaž nad
hranicou „strávi dosť času", a SOUL radšej mlčí, než by sa ozval naplano.

Oprava odpočíta z úseku čas strávený v tolerovaných prepadoch. Tolerancia
úsek naďalej drží nažive (nerozbije sa na nové behy) a krátke TICHO po
vzorke nad prahom (menej než `DIERA_S`) sa na súvislej ceste počíta ďalej —
to je zámerné a zdokumentované (POCTIVO v `note_load`).
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402

PRAH = 55.0
NAD = 80.0
POD = 40.0


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def spusti(t0=1000.0, **params):
    h = Hodiny(t0)
    t = trigger.CueTrigger(params=params, rng=random.Random(1), clock=h)
    t.open_session(silent_share=0.0)
    return t, h


def odohraj(t, h, vzor, limit_s):
    """Prehrá vzor [(sekund, stress), ...] dookola po 1 s. Vráti
    (posun natiahnutia od štartu alebo None, počet vzoriek nad prahom)."""
    start = h.t
    nad = 0
    while h.t - start <= limit_s:
        for sekund, stress in vzor:
            for _ in range(sekund):
                if h.t - start > limit_s:
                    return None, nad
                if stress >= PRAH:
                    nad += 1
                if t.note_load(stress, h.t, zona="high"):
                    return h.t - start, nad
                h.posun(1.0)
    return None, nad


# --------------------------------------------------------------------------
# Presne vzorce zo zadania
# --------------------------------------------------------------------------

def test_kmitanie_1_nad_19_pod_nenatiahne():
    """Chyba z revízie: 1 s nad / 19 s pod natiahlo po 60 s so štyrmi
    vzorkami nad prahom. Za päť minút je nad prahom 15 s - na 45 s držania
    to nie je ani tretina."""
    t, h = spusti()                              # predvolené: 45 s, tolerancia 20 s
    kedy, nad = odohraj(t, h, [(1, NAD), (19, POD)], limit_s=300.0)
    assert kedy is None, f"natiahlo sa po {kedy} s s {nad} s nad prahom"
    assert not t.is_armed
    # Tolerancia úsek drží nažive (žiadny prepad nie je dlhší než 20 s)...
    assert t.behov_nad == 1
    assert t.zrusenych_prepadom == 0
    # ... ale dĺžka úseku hovorí o čase NAD prahom, nie o nástenných hodinách.
    assert t.najdlhsi_nad_s <= 16.0, t.najdlhsi_nad_s


def test_suvisle_45_s_nad_prahom_stale_natiahne():
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(1, NAD)], limit_s=120.0)
    assert kedy == pytest.approx(45.0)
    assert t.is_armed
    assert t.najdlhsi_nad_s >= 45.0


def test_prepad_10_s_natiahne_az_po_45_s_nad_prahom():
    """30 s nad, 10 s pod (v tolerancii), potom zas nad. Predtým natiahlo
    na 45. sekunde nástenných hodín (35 s nad prahom), teraz až keď je nad
    prahom naozaj 45 s: 30 + 15 = na 55. sekunde."""
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(30, NAD), (10, POD), (1000, NAD)], limit_s=200.0)
    assert kedy == pytest.approx(55.0), kedy
    assert nad >= 45
    assert t.behov_nad == 1, "tolerovaný prepad nie je nový beh"
    assert t.zrusenych_prepadom == 0


def test_dlhy_usek_s_prepadmi_natiahne_suvislou_cestou_az_po_45_s_nad():
    """10 s nad / 15 s pod: za 90 s kumulatívne okno nikdy nedá 45 s, takže
    natiahnuť môže len súvislá cesta - a tá smie až po 45 s NAD prahom
    (4 kolá po 10 s + 5 s piateho). Predtým natiahla na 50. sekunde
    s 21 vzorkami nad prahom."""
    t, h = spusti()
    kedy, nad = odohraj(t, h, [(10, NAD), (15, POD)], limit_s=400.0)
    assert kedy == pytest.approx(105.0), kedy
    assert nad == 46                             # 45 s nad prahom + aktuálna vzorka
    assert t.behov_nad == 1


# --------------------------------------------------------------------------
# Čo sa zmeniť NESMELO
# --------------------------------------------------------------------------

def test_kratke_ticho_nad_prahom_sa_na_suvislej_ceste_stale_pocita():
    """POCTIVO v `note_load`: medzera kratšia než `DIERA_S` po vzorke nad
    prahom sa na súvislej ceste počíta (appka ju inde tiež berie ako
    „pripojené"). Pri vzorke každých 11 s dá okno len 5 s za vzorku, takže
    natiahnuť musí súvislá cesta - na 55. sekunde, ako doteraz."""
    assert 11.0 < trigger.DIERA_S
    t, h = spusti()
    start = h.t
    kedy = None
    for _ in range(20):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t - start
            break
        h.posun(11.0)
    assert kedy == pytest.approx(55.0), kedy
    assert t.zrusenych_vypadkom == 0


def test_dlhy_prepad_usek_stale_zrusi():
    """Sémantika `dip_grace_s` pre zrušenie úseku ostáva."""
    t, h = spusti(dip_grace_s=20.0)
    odohraj(t, h, [(30, NAD), (25, POD)], limit_s=54.0)
    assert t.zrusenych_prepadom == 1
    assert t.state == trigger.IDLE
    assert 29.0 <= t.najdlhsi_nad_s <= 30.0, t.najdlhsi_nad_s


# --------------------------------------------------------------------------
# Nový stav sa nuluje všade, kde sa končí úsek
# --------------------------------------------------------------------------

def _usek_s_prepadom(t, h):
    """20 s nad, 10 s tolerovaný prepad, 5 s nad: `_prepady_s` je 10."""
    for sekund, stress in ((20, NAD), (10, POD), (5, NAD)):
        for _ in range(sekund):
            assert t.note_load(stress, h.t, zona="high") is None
            h.posun(1.0)
    assert t._prepady_s == pytest.approx(10.0)


def test_prepady_sa_nulujú_pri_uspani():
    for dovod in (trigger.A_SNOOZE, trigger.A_TEP_VYPADOL):
        t, h = spusti()
        _usek_s_prepadom(t, h)
        t.suspend(dovod, now=h.t)
        assert t._prepady_s == 0.0, dovod
        # dĺžka úseku bez prepadu: 20 + 5 s nad prahom (+ držanie poslednej)
        assert 24.0 <= t.najdlhsi_nad_s <= 26.0, t.najdlhsi_nad_s


def test_prepady_sa_nulujú_pri_kalibracii():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    t.note_load(NAD, h.t, calibrating=True, zona="high")
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_vypadku():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    h.posun(trigger.DIERA_S)
    t.note_load(NAD, h.t, zona="high")
    assert t.zrusenych_vypadkom == 1
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_dlhom_prepade():
    t, h = spusti(dip_grace_s=20.0)
    _usek_s_prepadom(t, h)
    for _ in range(25):
        t.note_load(POD, h.t, zona="high")
        h.posun(1.0)
    assert t.zrusenych_prepadom == 1
    assert t._prepady_s == 0.0


def test_prepady_sa_nulujú_pri_natiahnuti_a_plnej_hodine():
    t, h = spusti()
    _usek_s_prepadom(t, h)
    ev = None
    while not ev:
        ev = t.note_load(NAD, h.t, zona="high")
        h.posun(1.0)
    assert t._prepady_s == 0.0

    # Plná hodina / vypnuté hlášky: úsek sa počíta odznova od `now`.
    t, h = spusti(cues_enabled=False)
    _usek_s_prepadom(t, h)
    for _ in range(40):
        t.note_load(NAD, h.t, zona="high")
        if t._above_since == h.t:
            break
        h.posun(1.0)
    assert t._above_since == h.t, "vetva plnej hodiny sa nespustila"
    assert t._prepady_s == 0.0


def test_novy_usek_nededi_prepady_stareho():
    """Keby sa `_prepady_s` nevynuloval, ďalší úsek by sa natiahol neskôr,
    než má (ticho navyše). Pri vzorke každých 11 s rozhoduje súvislá cesta:
    so zdedenými 15 s by sa natiahlo až na 66. sekunde."""
    t, h = spusti(dip_grace_s=20.0)
    for sekund, stress in ((20, NAD), (15, POD), (5, NAD)):
        for _ in range(sekund):
            t.note_load(stress, h.t, zona="high")
            h.posun(1.0)
    assert t._prepady_s == pytest.approx(15.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    h.posun(100.0)                               # staré okno vyprší
    t.resume(now=h.t)
    start = h.t
    kedy = None
    for _ in range(20):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t - start
            break
        h.posun(11.0)
    assert kedy == pytest.approx(55.0), kedy


# --------------------------------------------------------------------------
# Cas 0.0 je platny cas
# --------------------------------------------------------------------------

def test_vzorka_v_case_nula_sa_na_suvislej_ceste_pocita():
    """`if self._posledny_nad_koniec` bral čas 0.0 ako „chýba". Vzorka nad
    prahom každých 11 s, posledná presne v čase 0.0: súvislá cesta má 55 s
    (okno len 5 x 5 s), takže sa natiahne práve v čase 0.0 - nie o vzorku
    neskôr."""
    t, h = spusti(t0=-55.0)
    kedy = None
    for _ in range(10):
        if t.note_load(NAD, h.t, zona="high"):
            kedy = h.t
            break
        h.posun(11.0)
    assert kedy == 0.0, kedy
    assert t.najdlhsi_nad_s == pytest.approx(55.0)


# --------------------------------------------------------------------------
# Veta po relacii: "najdlhsie X s, treba Y s" nesmie tvrdit X >= Y o useku,
# ktory sa nenatiahol
# --------------------------------------------------------------------------

def test_vypadok_cez_appku_nepripise_ticho_do_dlzky_useku():
    """Appka volá `suspend(A_TEP_VYPADOL)` až po `STALE_AFTER_S` bez dát,
    teda 12 s po poslednej vzorke. Tie sekundy nikto nemeral: 35 vzoriek nad
    prahom nesmie v súhrne vyjsť ako 46 s pri potrebných 45 s."""
    t, h = spusti()
    for _ in range(35):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(1.0)
    posledna = h.t - 1.0
    t.suspend(trigger.A_TEP_VYPADOL, now=posledna + trigger.DIERA_S)
    assert t.armed_count == 0
    assert t.zrusenych_vypadkom == 1
    assert t.najdlhsi_nad_s == pytest.approx(34.0)


def test_dlhy_prepad_tesne_pod_drzanim_netvrdi_drzanie():
    """45 vzoriek po 1 s: podmienka natiahnutia videla najviac 44 s, takže
    sa nenatiahlo. Súhrn nesmie tvrdiť 45 s („najdlhšie 45 s, treba 45 s")."""
    t, h = spusti()
    for _ in range(45):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(1.0)
    for _ in range(25):
        assert t.note_load(POD, h.t, zona="high") is None
        h.posun(1.0)
    assert t.zrusenych_prepadom == 1
    assert t.armed_count == 0
    assert t.najdlhsi_nad_s == pytest.approx(44.0)


def test_ridka_kadencia_a_prepad_netvrdia_drzanie():
    """Kadencia ~2,9 s: 16 vzoriek nad prahom je 43,5 s, nenatiahne sa.
    Medzera k prvej vzorke pod prahom (2,9 s) sa do úseku pripočítať nesmie -
    inak by súhrn tvrdil 46 s."""
    t, h = spusti()
    for _ in range(16):
        assert t.note_load(NAD, h.t, zona="high") is None
        h.posun(2.9)
    for _ in range(12):
        assert t.note_load(POD, h.t, zona="high") is None
        h.posun(2.9)
    assert t.zrusenych_prepadom == 1
    assert t.armed_count == 0
    assert t.najdlhsi_nad_s == pytest.approx(43.5)


def test_bez_natiahnutia_najdlhsie_nikdy_nedosiahne_drzanie():
    """Všeobecná poistka: kým sa nič nenatiahlo, `najdlhsi_nad_s` je vždy
    pod `stress_hold_s`. Úseky 30-50 s s náhodnou kadenciou (aj redšou, pod
    `DIERA_S`) a krátkymi prepadmi, ukončené dlhým prepadom, dierou v dátach
    alebo výpadkom cez appku (`suspend` 12 s po poslednej vzorke)."""
    drzanie = trigger.default_params()["stress_hold_s"]
    tesne = 0
    for seed in range(300):
        rng = random.Random(seed)
        t, h = spusti()
        for _ in range(6):
            koniec = h.t + rng.uniform(30.0, 50.0)
            posledna = h.t
            while h.t < koniec and not t.armed_count:
                stress = POD if rng.random() < 0.1 else NAD
                t.note_load(stress, h.t, zona="high")
                posledna = h.t
                h.posun(rng.choice((0.9, 1.0, 2.9, 5.6, 11.0)))
            if t.armed_count:
                break
            sposob = rng.randrange(3)
            if sposob == 0:                          # dlhý prepad
                for _ in range(25):
                    t.note_load(POD, h.t, zona="high")
                    h.posun(1.0)
            elif sposob == 1:                        # diera v dátach
                h.posun(trigger.DIERA_S)
                t.note_load(POD, h.t, zona="high")
            else:                                    # výpadok cez appku
                t.suspend(trigger.A_TEP_VYPADOL,
                          now=posledna + trigger.DIERA_S)
                h.t = posledna + trigger.DIERA_S + 5.0
                t.resume(now=h.t)
            assert t.armed_count == 0
            assert t.najdlhsi_nad_s < drzanie, (seed, sposob, t.najdlhsi_nad_s)
            if t.najdlhsi_nad_s >= drzanie - 10.0:
                tesne += 1
    assert tesne >= 50, "test nič neoveril - skoro žiadny úsek nebol tesne"


# --------------------------------------------------------------------------
# Všeobecná poistka: natiahnuté = naozaj 45 s nad prahom
# --------------------------------------------------------------------------

def test_natiahnutie_nikdy_bez_45_s_nad_prahom():
    """Náhodné striedanie nad/pod (1-30 s), vzorka každú sekundu. Nech
    natiahne ktorákoľvek cesta, vzoriek nad prahom musí byť aspoň 45 -
    inak sa hláška natiahla na čase, ktorý nad prahom nebol."""
    natiahnutych = 0
    for seed in range(300):
        rng = random.Random(seed)
        vzor = []
        for _ in range(40):
            vzor.append((rng.randint(1, 30), NAD))
            vzor.append((rng.randint(1, 30), POD))
        t, h = spusti()
        kedy, nad = odohraj(t, h, vzor, limit_s=1500.0)
        if kedy is not None:
            natiahnutych += 1
            assert nad >= t.params["stress_hold_s"], (seed, kedy, nad)
    assert natiahnutych >= 50, "test nič neoveril - skoro nič sa nenatiahlo"
