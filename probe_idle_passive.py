"""Kontrolne meranie: nuluje sa idle timer aj ked sa NIKTO niceho nedotyka?

Toto musi prejst PRED merania s gamepadom. Ak idle nerastie ani vtedy, ked
je vsetko v pokoji, tak nulove idle pocas hybania ovladacom nedokazuje nic -
nuluje to nieco ine.

Spustenie:
    python probe_idle_passive.py

Potom 15 sekund NEROB NIC. Nedotykaj sa mysi ani klavesnice, nehyb
ovladacom, neprepinaj okna.
"""
import ctypes
import time
from ctypes import wintypes

DURATION_S = 15.0
SAMPLE_S = 0.05

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
user32.GetLastInputInfo.restype = wintypes.BOOL
kernel32.GetTickCount.restype = wintypes.DWORD


def idle_ms():
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return (kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF


print(__doc__.split("Spustenie")[0].rstrip())
print("-" * 66)
print(f"Mera {DURATION_S:.0f} s. TERAZ SA NICOHO NEDOTYKAJ.")
print("-" * 66)

start = time.monotonic()
prev = idle_ms()
peak = prev
resets = []
next_report = start + 1.0

while True:
    now = time.monotonic()
    elapsed = now - start
    if elapsed >= DURATION_S:
        break
    v = idle_ms()
    if v < prev - 200:            # idle spadlo = prisiel nejaky vstup
        resets.append(round(elapsed, 2))
    peak = max(peak, v)
    prev = v
    if now >= next_report:
        print(f"  {elapsed:5.1f} s   idle = {v:6d} ms")
        next_report += 1.0
    time.sleep(SAMPLE_S)

print("-" * 66)
print(f"najvyssie idle za {DURATION_S:.0f} s : {peak} ms")
print(f"pocet vynulovani             : {len(resets)}")
if resets:
    print(f"kedy (s od startu)           : {resets[:20]}")

print()
if peak > DURATION_S * 1000 * 0.8:
    print("VYSLEDOK: idle rastie normalne. Prostredie je ciste,")
    print("          meranie s gamepadom bude platne.")
elif peak < 2000:
    print("VYSLEDOK: idle vobec nerastie - nieco vstup generuje NEUSTALE.")
    print("          Meranie s gamepadom by bolo bezcenne.")
    print("          Podozrivi: Steam Input, Armoury Crate, Logitech/Razer")
    print("          software, Discord overlay, ci ruka polozena na mysi.")
else:
    print("VYSLEDOK: idle rastie, ale nieco ho priebezne nuluje.")
    print(f"          Dosiahlo len {peak} ms z ocakavanych {int(DURATION_S*1000)} ms.")
    print("          Meranie s gamepadom bude nespolahlive, kym sa to")
    print("          nenajde a nevypne.")
