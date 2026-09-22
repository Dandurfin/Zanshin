"""Meranie k otazke c. 1 zo zadania:

    "Gamepad listener ostava, alebo ho nahradi GetLastInputInfo?"

Zadanie odporuca nahradit ho s odovodnenim, ze "GetLastInputInfo pokryva aj
gamepad cez raw input" - a zaroven ziada overit to meranim, nie predpokladom.
Toto je to meranie.

PRECO SU TU TRI FAZY
--------------------
Prve meranie skoncilo verdiktom "GetLastInputInfo gamepad VIDI", ale bolo
neplatne: pocas referencnej fazy, ked sa nikto niceho nedotykal, idle ostalo
na nule. Nieco vstup generovalo neustale, takze nulove idle pocas hybania
ovladacom nedokazovalo vobec nic.

Preto su tu tri fazy a dve kontroly kludu - pred aj po. Ak sa idle nezdvihne
v OBOCH, meranie sa vyhlasi za neplatne a ziadny verdikt sa nevydava.

POZOR NA STEAM
--------------
Ak bezi Steam so zapnutym Steam Input, ovladac sa moze mapovat na syntetickú
klavesnicu a mys. Tie idle timer naozaj nuluju - ale nie preto, ze by
GetLastInputInfo videlo gamepad, ale preto, ze Steam z neho robi klavesnicu.
Pre appku je to zasadny rozdiel: fungovalo by to na tomto pocitaci a zlyhalo
u hraca, ktory ma Steam Input vypnuty alebo ktoreho hra cita XInput priamo.

Spusti to preto DVAKRAT:
  1. so zapnutym Steamom (ako bezne hravas)
  2. s uplne vypnutym Steamom
Ak sa vysledky lisia, odpoved je "robi to Steam", nie "robi to Windows".

AKO TO SPUSTIT
--------------
    python probe_idle_vs_gamepad.py

Pripoj ovladac. Skript ti povie, kedy mas co robit. Pocas CELEHO merania sa
nedotykaj klavesnice ani mysi - ani sa o nu neopieraj.
"""

import ctypes
import os
import sys
import time
from ctypes import wintypes

QUIET_A_S = 8.0        # kontrola kludu pred
ACTIVE_S = 12.0        # hybanie ovladacom
QUIET_B_S = 8.0        # kontrola kludu po
SAMPLE_S = 0.05

# Ak idle pocas kludu vystupi aspon na tolko, povazujeme klud za cisty.
QUIET_OK_MS = 3000
# Ak pocas hybania ovladacom idle nikdy nepresiahne tolko, GLII gamepad vidi.
SEEN_MS = 600

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL
kernel32.GetTickCount.restype = wintypes.DWORD


def idle_ms():
    """Ms od posledneho vstupu podla Windows. Ziadny hook - GetLastInputInfo
    vracia len cislo, nie to, ktora klavesa a ani ci to klavesa bola."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return (kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except Exception as exc:
    sys.exit(f"pygame sa nepodarilo importovat: {exc}")

pygame.init()
pygame.joystick.init()

pads = []
for i in range(pygame.joystick.get_count()):
    joy = pygame.joystick.Joystick(i)
    joy.init()
    pads.append(joy)

if not pads:
    sys.exit("Nie je pripojeny ziadny ovladac - meranie nema co merat.")

# Posledna znama poloha kazdej osi. Bez toho by sa kludova poloha spusti
# (LT/RT lezia na -1.0) pocitala ako nekonecny prud udalosti.
axis_last = {}


def drain_events():
    """Pocet SKUTOCNYCH udalosti z ovladaca od posledneho volania."""
    n = 0
    for event in pygame.event.get():
        if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP,
                          pygame.JOYHATMOTION,
                          pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
            n += 1
        elif event.type in (pygame.JOYAXISMOTION, pygame.CONTROLLERAXISMOTION):
            key = (getattr(event, "instance_id", 0), getattr(event, "axis", 0))
            val = float(getattr(event, "value", 0.0))
            prev = axis_last.get(key)
            axis_last[key] = val
            # len skutocny pohyb, nie sum ani kludova poloha
            if prev is not None and abs(val - prev) > 0.15:
                n += 1
    return n


def run_phase(label, duration, instruction):
    print()
    print("=" * 68)
    print(f"{label}  ({duration:.0f} s)")
    print(f"  {instruction}")
    print("=" * 68)
    for i in (3, 2, 1):
        print(f"  zacina o {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  BEZI                    ")

    start = time.monotonic()
    peak = 0
    events = 0
    next_report = start + 2.0
    drain_events()
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed >= duration:
            break
        events += drain_events()
        v = idle_ms()
        if v > peak:
            peak = v
        if now >= next_report:
            print(f"   {elapsed:5.1f} s   idle = {v:6d} ms   "
                  f"najvyssie zatial = {peak:6d} ms   udalosti = {events}")
            next_report += 2.0
        time.sleep(SAMPLE_S)
    print(f"  -> najvyssie idle: {peak} ms,  udalosti z ovladaca: {events}")
    return peak, events


print(__doc__.split("AKO TO SPUSTIT")[0].rstrip())
print()
for joy in pads:
    print(f"ovladac: {joy.get_name()}")

quiet_a, ev_a = run_phase(
    "FAZA 1 - kontrola kludu", QUIET_A_S,
    "NEROB NIC. Ruky prec od mysi aj klavesnice, ovladac nechaj lezat.")

active, ev_active = run_phase(
    "FAZA 2 - len ovladac", ACTIVE_S,
    "Hyb pakami a mackaj tlacidla NEPRETRZITE. Nicoho ineho sa nedotykaj.")

quiet_b, ev_b = run_phase(
    "FAZA 3 - kontrola kludu", QUIET_B_S,
    "Zase NEROB NIC. Ovladac poloz a nechaj tak.")

print()
print("=" * 68)
print("VYHODNOTENIE")
print("=" * 68)
print(f"  klud pred   : idle vystupilo na {quiet_a:6d} ms   (udalosti: {ev_a})")
print(f"  ovladac     : idle vystupilo na {active:6d} ms   (udalosti: {ev_active})")
print(f"  klud po     : idle vystupilo na {quiet_b:6d} ms   (udalosti: {ev_b})")
print()

if ev_active < 20:
    print("NEPLATNE: z ovladaca prislo prilis malo udalosti "
          f"({ev_active}). Vo faze 2 treba hybat nepretrzite.")
    sys.exit(3)

if quiet_a < QUIET_OK_MS or quiet_b < QUIET_OK_MS:
    print("NEPLATNE: idle nerastie ani pocas kludu - nieco na tomto")
    print("          pocitaci generuje vstup neustale. Kym sa to nenajde,")
    print("          nizke idle pocas hybania ovladacom nic nedokazuje.")
    print()
    print("  Podozrivi, v poradi pravdepodobnosti:")
    print("    - Steam Input (mapuje ovladac na klavesnicu/mys)")
    print("    - Armoury Crate / Logitech / Razer software")
    print("    - Discord overlay")
    print("    - ruka polozena na mysi (staci sa o nu opriet)")
    print()
    print("  Spusti probe_idle_passive.py - ten meria len klud a povie,")
    print("  ci je to vobec o ovladaci.")
    sys.exit(4)

if active < SEEN_MS:
    print("VYSLEDOK: GetLastInputInfo gamepad VIDI.")
    print(f"          Pocas nepretrziteho hybania idle nikdy neprekrocilo")
    print(f"          {active} ms, kym v klude vystupilo na {max(quiet_a, quiet_b)} ms.")
    print()
    print("          -> SDL/pygame vrstvu je mozne odstranit.")
    print("          ALE: over to este raz s UPLNE VYPNUTYM Steamom. Ak sa")
    print("          vtedy vysledok obrati, robi to Steam Input a nie")
    print("          Windows - a na to sa appka spolahnut nemoze.")
else:
    print("VYSLEDOK: GetLastInputInfo gamepad NEVIDI.")
    print(f"          Idle vystupilo na {active} ms aj pocas nepretrziteho")
    print("          hybania ovladacom - Windows to za vstup nepovazuje.")
    print()
    print("          -> gamepad listener musi ostat. Bez neho by appka")
    print("             hraca na ovladaci povazovala za neaktivneho a")
    print("             hlasku by mu dorucila uprostred hrania (alebo vobec).")
