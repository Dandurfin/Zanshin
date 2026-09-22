# -*- coding: utf-8 -*-
"""Da sa pocas hrania vobec precitat stav OHLASENYCH klaves?

NA CO TO JE
-----------
Zvazuje sa funkcia, kde si hrac VOPRED OHLASI zoznam klaves (napr. W A S D R C)
a appka sa pyta Windowsu `GetAsyncKeyState` LEN na tieto kody - aby vedela, co sa
priblizne dialo v hre, ked telu stupla zataz. Ziadny hook, ziadna simulacia
vstupu, ziadny zasah do hry.

Skor nez sa taka funkcia napise, treba vediet jedinu vec: FUNGUJE TO VOBEC?

Microsoft dokumentuje, ze `GetAsyncKeyState` vrati nulu, ked
"the foreground thread belongs to another process and the calling thread does not
have DESKTOP_HOOKCONTROL or DESKTOP_JOURNALRECORD access to its desktop".
Hry s anti-cheatom casto bezia elevovane; nasa appka zamerne NIE
(`uac_admin=False` je tvrda podmienka zo zadania §5). V takom pripade by sme
dostali same nuly a cela funkcia je mrtva este pred prvym riadkom.

ROZHODUJUCI UDAJ
----------------
Nie "kolko stlaceni sme videli", ale ROZPOR:

    system hlasi, ze hrac prave teraz nieco stlacil   (GetLastInputInfo)
    ale ani jedna z ohlasenych klaves nie je dole     (GetAsyncKeyState)

Ked sa tento rozpor deje sustavne, sme slepi - a nezachrani to ziadne ladenie.
Preto sa meria OBOJE naraz a vysledok sa vykazuje ako podiel "slepych" vzoriek
na kazdy proces v popredi zvlast.

CO TENTO NASTROJ NEROBI
-----------------------
Neinstaluje hook. Nesimuluje vstup. Nezapisuje, KTORA klavesa padla v akom
poradi - drzi len POCITADLA na ohlasene klavese. Nedotyka sa nastaveni appky ani
jej suborov. Da sa spustit aj samostatne, bez zvysku projektu.

POUZITIE
--------
    python probe_klavesy_pasivne.py --poznamka "cod elevovany"
    python probe_klavesy_pasivne.py --klavesy "W,A,S,D,R,C,SPACE,SHIFT"

Nechaj bezat, zahraj si normalne, a ukonci Ctrl+C. Medzivysledok sa vypisuje
kazdych 20 s, aby sa nemuselo cakat do konca.
"""

import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

# --------------------------------------------------------------------------
# Kody klaves. Zamerne ich je malo a su to HERNE klavese - nie pismena, z
# ktorych sa da skladat text. Kto si sem doplni cele abecedu, spravil z tohto
# nastroja nieco ine, nez cim je.
# --------------------------------------------------------------------------

VK = {
    "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "Q": 0x51, "E": 0x45, "R": 0x52, "F": 0x46, "C": 0x43, "V": 0x56,
    "SPACE": 0x20, "SHIFT": 0x10, "CTRL": 0x11, "ALT": 0x12, "TAB": 0x09,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "MYS_LAVE": 0x01, "MYS_PRAVE": 0x02,
}

PREDVOLENE = "W,A,S,D,R,C,SPACE,SHIFT,MYS_LAVE,MYS_PRAVE"

POLL_HZ = 60.0
VYPIS_KAZDYCH_S = 20.0
# Kolko ms od posledneho vstupu este znamena "prave teraz nieco stlacil".
# Pri 60 Hz je 120 ms bezpecne nad periodou a pod reakcnym casom cloveka.
CERSTVY_VSTUP_MS = 120
# Jedno Ctrl+C sondu NEZASTAVI - druhe do tolkoto sekund ano. Kym sa hra,
# Ctrl+C aj tak chodi do hry; nebezpecne je to az po prepnuti von, a vtedy
# je to takmer vzdy omyl. Necha sa tym stratit najviac par sekund merania
# namiesto celeho vecera.
POTVRDENIE_S = 4.0

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_ms():
    """Kolko ms od posledneho vstupu. Jedine cislo, ziadny obsah."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return None
    return kernel32.GetTickCount() - lii.dwTime


def proces_v_popredi():
    """(meno procesu, titulok) okna v popredi. Nic sa z neho necita."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "(ziadne)", ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    meno = "(neznamy)"
    try:
        import psutil
        meno = psutil.Process(pid.value).name()
    except Exception:
        pass
    dlzka = user32.GetWindowTextLengthW(hwnd)
    titulok = ""
    if dlzka:
        buf = ctypes.create_unicode_buffer(dlzka + 1)
        user32.GetWindowTextW(hwnd, buf, dlzka + 1)
        titulok = buf.value
    return meno, titulok


def sme_elevovani():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


class Zaznam(object):
    """Pocitadla pre jeden proces v popredi."""

    __slots__ = ("vzoriek", "sekund", "stlaceni", "vstup_bol", "slepych",
                 "drzane_s")

    def __init__(self):
        self.vzoriek = 0        # kolko krat sme sa pytali
        self.sekund = 0.0
        self.stlaceni = {}      # meno klavesy -> pocet zostupnych hran
        self.vstup_bol = 0      # vzorky, kde system hlasil cerstvy vstup
        self.slepych = 0        # ... a pritom ziadna ohlasena klavesa nebola dole
        self.drzane_s = {}      # meno klavesy -> sekundy, co bola dole

    def ako_slovnik(self):
        podiel = (100.0 * self.slepych / self.vstup_bol) if self.vstup_bol else None
        return {
            "vzoriek": self.vzoriek,
            "sekund": round(self.sekund, 1),
            "stlaceni": dict(sorted(self.stlaceni.items(),
                                    key=lambda p: -p[1])),
            "stlaceni_spolu": sum(self.stlaceni.values()),
            "vzoriek_s_cerstvym_vstupom": self.vstup_bol,
            "z_toho_slepych": self.slepych,
            "podiel_slepych_pct": round(podiel, 1) if podiel is not None else None,
            "drzane_s": {k: round(v, 1) for k, v in
                         sorted(self.drzane_s.items(), key=lambda p: -p[1])},
        }


def nazov_suboru(poznamka):
    slug = "".join(c if c.isalnum() else "_" for c in (poznamka or "beh").lower())
    slug = "_".join(x for x in slug.split("_") if x)[:40] or "beh"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    priecinok = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "logs", "probe_klavesy")
    os.makedirs(priecinok, exist_ok=True)
    return os.path.join(priecinok, "klavesy_%s_%s.json" % (stamp, slug))


def zhrnutie(zaznamy):
    """Jedna veta na kazdy proces - to, kvoli comu sa to spustalo."""
    riadky = []
    for meno, z in sorted(zaznamy.items(), key=lambda p: -p[1].sekund):
        if z.sekund < 5:
            continue
        spolu = sum(z.stlaceni.values())
        # POZOR NA VYKLAD: vysoky podiel "slepych" vzoriek NIE JE slepota.
        # Znamena len, ze hrac stlacal klavese, ktore nie su v ohlasenom
        # zozname - pri pisani textu to je 90 % a je to spravne.
        #
        # Rozhodujuce je nieco ine a je to BINARNE: videli sme ASPON JEDNO
        # stlacenie? Ak ano, `GetAsyncKeyState` pre ten proces v popredi
        # funguje a funkcia sa da postavit. Ak nie, ani pri dlhom hrani,
        # sme slepi a ziadne ladenie to nezmeni.
        podiel = (100.0 * z.slepych / z.vstup_bol) if z.vstup_bol else 0.0
        if z.vstup_bol == 0:
            verdikt = "ziadny vstup - hralo sa vobec?"
        elif spolu == 0:
            verdikt = ("SLEPI: %d vzoriek so vstupom, ani jedno stlacenie"
                       % z.vstup_bol)
        else:
            verdikt = "VIDIME (%d stlaceni; %.0f %% vstupu boli ine klavese)" % (
                spolu, podiel)
        riadky.append("  %-28s %6.0f s   %s" % (meno[:28], z.sekund, verdikt))
    return riadky


def zloz_vysledok(args, mena, zaznamy, trvanie, prerusene):
    """Cely vysledok ako slovnik. Vydeleny z `main`, aby sa dal zapisat aj
    PRIEBEZNE - dve hodiny hrania sa nesmu stratit preto, ze sa okno zavrelo
    inak nez cez Ctrl+C."""
    return {
        "poznamka": args.poznamka,
        "kedy": time.strftime("%Y-%m-%d %H:%M:%S"),
        "trvanie_s": round(trvanie, 1),
        "prerusene_uzivatelom": prerusene,
        "dokoncene": prerusene,
        "sledovane_klavesy": mena,
        "poll_hz": POLL_HZ,
        "nasa_elevacia": sme_elevovani(),
        "python": sys.version.split()[0],
        "procesy": {m: z.ako_slovnik() for m, z in zaznamy.items()
                    if z.sekund >= 5},
    }


def zapis(subor, data):
    with open(subor, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poznamka", default="",
                    help="do nazvu suboru, napr. \"cod elevovany\"")
    ap.add_argument("--klavesy", default=PREDVOLENE,
                    help="ciarkou oddelene, z: " + ", ".join(sorted(VK)))
    args = ap.parse_args()

    mena = [k.strip().upper() for k in args.klavesy.split(",") if k.strip()]
    nezname = [k for k in mena if k not in VK]
    if nezname:
        print("neznama klavesa: %s" % ", ".join(nezname))
        print("dostupne: %s" % ", ".join(sorted(VK)))
        return 2
    sledovane = [(k, VK[k]) for k in mena]

    print(__doc__.split("POUZITIE")[0].rstrip())
    print()
    print("sledujem: %s" % ", ".join(mena))
    print("nasa elevacia: %s" % ("ANO" if sme_elevovani() else "nie"))
    print("ukoncenie: Ctrl+C DVAKRAT po sebe (jedno stlacenie nestaci).")
    print("medzivysledok a zapis na disk kazdych %d s." % VYPIS_KAZDYCH_S)
    print("-" * 66, flush=True)

    subor = nazov_suboru(args.poznamka)
    print("zapisujem priebezne do: %s" % subor, flush=True)
    print("-" * 66, flush=True)

    zaznamy = {}
    dole_predtym = {k: False for k, _ in sledovane}
    perioda = 1.0 / POLL_HZ
    zaciatok = time.time()
    posledny_vypis = zaciatok
    prerusene = False

    posledne_ctrlc = 0.0

    while True:
        try:
            t0 = time.time()
            meno, _titulok = proces_v_popredi()
            z = zaznamy.setdefault(meno, Zaznam())
            z.vzoriek += 1
            z.sekund += perioda

            nieco_dole = False
            for k, kod in sledovane:
                stav = user32.GetAsyncKeyState(kod)
                dole = bool(stav & 0x8000)
                if dole:
                    nieco_dole = True
                    z.drzane_s[k] = z.drzane_s.get(k, 0.0) + perioda
                if dole and not dole_predtym[k]:
                    z.stlaceni[k] = z.stlaceni.get(k, 0) + 1
                dole_predtym[k] = dole

            ms = idle_ms()
            if ms is not None and ms <= CERSTVY_VSTUP_MS:
                z.vstup_bol += 1
                if not nieco_dole:
                    z.slepych += 1

            if t0 - posledny_vypis >= VYPIS_KAZDYCH_S:
                posledny_vypis = t0
                # flush=True: bez neho si Python vystup drzi, kym nedobehne -
                # a tento nastroj sa spusta prave preto, aby bolo vidiet
                # priebezne, ci sa nieco cita.
                print("[%5.0f s]" % (t0 - zaciatok), flush=True)
                for r in zhrnutie(zaznamy):
                    print(r, flush=True)
                print("-" * 66, flush=True)
                zapis(subor, zloz_vysledok(args, mena, zaznamy,
                                           t0 - zaciatok, False))

            spi = perioda - (time.time() - t0)
            if spi > 0:
                time.sleep(spi)

        except KeyboardInterrupt:
            # JEDNO Ctrl+C NESTACI. Zapise, co je zmerane, a meria dalej.
            teraz = time.time()
            if teraz - posledne_ctrlc <= POTVRDENIE_S:
                prerusene = True
                break
            posledne_ctrlc = teraz
            zapis(subor, zloz_vysledok(args, mena, zaznamy,
                                       teraz - zaciatok, False))
            print(flush=True)
            print("Ctrl+C -- pre ukoncenie stlac ESTE RAZ do %.0f s."
                  % POTVRDENIE_S, flush=True)
            print("   (doteraz zmerane je prave zapisane, meram dalej)",
                  flush=True)
            continue

        except Exception:
            # Aj necakany pad ma nechat to, co sa uz zmeralo.
            import traceback
            traceback.print_exc()
            zapis(subor, zloz_vysledok(args, mena, zaznamy,
                                       time.time() - zaciatok, False))
            print("spadlo, ale zmerane data su ulozene: %s" % subor)
            raise

    trvanie = time.time() - zaciatok
    print()
    print("=" * 66)
    print("KONIEC po %.0f s" % trvanie)
    for r in zhrnutie(zaznamy):
        print(r)

    zapis(subor, zloz_vysledok(args, mena, zaznamy, trvanie, prerusene))
    print()
    print("zapisane: %s" % subor)
    print()
    print("CO S TYM: hladaj riadok pri svojej HRE (nie pri prehliadaci).")
    print("  VIDIME  = citanie funguje, funkcia sa da postavit. Percento v")
    print("            zatvorke je len to, kolko vstupu boli ine klavese -")
    print("            pri pisani textu je vysoke a nic zle neznamena.")
    print("  SLEPI   = dlho sa hralo a nevideli sme ani jedno stlacenie.")
    print("            To uz ziadne ladenie nezmeni - su to pravidla")
    print("            Windowsu (DESKTOP_HOOKCONTROL), nie chyba v kode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
