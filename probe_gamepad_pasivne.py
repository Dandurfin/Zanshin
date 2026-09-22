"""Vidí Windows gamepad ako vstup? Meranie, pri ktorom sa len HRÁ.

PRECO NIE SIMULACIA
-------------------
Simulovat vstup sa tu pouzit neda. `SendInput` vie syntetizovat len
klavesnicu a mys a injektovany vstup `GetLastInputInfo` NULUJE vzdy -
vysledok by bol zarucene "ano, vidi" a o gamepade by nehovoril nic.
Skutocny virtualny ovladac (ViGEmBus) je ovladac do jadra, cize dalsia
premenna prave v tom, co sa meria.

PRECO SA PRI TOM LEN HRA
------------------------
Predosly trojfazovy test ziadal sediet a nehybat sa. To sa da pokazit
(staci polozena ruka na mysi) a prve meranie sa tak aj pokazilo: idle
neraslo ani pocas "kludu". Tu netreba ziadnu disciplinu - spusti sa a
hra sa. Vyhodnotenie si samo najde useky, v ktorych chodil len ovladac.

CO SA MERIA
-----------
Stykrat za minutu: kolko ms uplynulo od posledneho vstupu podla Windows
(`GetLastInputInfo`), ci sa pohla niektora os alebo tlacidlo ovladaca, a
ci sa pohol kurzor mysi.

  * ak Windows gamepad VIDI, tak v useku, kde sa nepretrzite hybe
    ovladacom, idle nikdy nevyskoci - stale sa nuluje,
  * ak ho NEVIDI, idle v takom useku rastie presne tak, akoby hrac
    nerobil vobec nic.

Kontrolou je opacny usek: cas, ked sa nedeje nic. Tam idle rast MUSI.
Ked nerastie, nieco na tom pocitaci generuje vstup neustale a meranie
sa vyhlasi za neplatne.

DVA SPOSOBY, AKO SI VYROBIT SPRAVNY VYSLEDOK ZO ZLEHO DOVODU
------------------------------------------------------------
1. STEAM INPUT. Ked bezi Steam a ma zapnuty Steam Input, ovladac sa moze
   mapovat na syntetickú klavesnicu a mys - a tie idle nuluju. Skript
   zisti, ci Steam bezi, a napise to do vysledku. Ideal je odmerat to
   dvakrat: raz ako bezne hravas, raz s uplne vypnutym Steamom.

2. GYROSKOP AKO MYS. Niektore ovladace (napr. GameSir G7 Pro s Motion
   nastavenym na "Always On") posielaju z gyroskopu pohyb MYSI. Potom je
   ovladac v ociach Windowsu mys, nie gamepad, a idle sa nuluje uplne
   inym kanalom. Detegovat sa to z procesov neda - preto skript sleduje
   polohu kurzora a ak sa hybe v usekoch, kde ide len ovladac, oznaci
   meranie za neplatne a povie preco.

POUZITIE
--------
    python probe_gamepad_pasivne.py              # bezi, kym ho nezastavis
    python probe_gamepad_pasivne.py --minuty 30  # alebo s casovym stropom

Spusti a hraj cely vecer. Cim dlhsie, tym lepsie: o vysledku nerozhoduje
jeden vykyv, ale to, ako sa idle sprava naprie VSETKYMI usekmi. Ctrl+C
meranie ukonci a vyhodnoti. Kazdych par minut sa uklada medzivysledok,
takze ani pad appky o vecer merania nepripravi.
"""

import argparse
import ctypes
import json
import os
import statistics
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import activity          # v projekte: meria sa tym istym kodom ako v appke
    _Z_PROJEKTU = True
except ImportError:
    # Aby sa dal tento subor poslat kamaratovi SAMOSTATNE. Vtedy staci
    # Python a `pip install pygame` - nie cely projekt. Je to tych par
    # riadkov z activity.py, ktore toto meranie naozaj potrebuje.
    _Z_PROJEKTU = False

    class _Idle:
        def __init__(self):
            self._u = ctypes.WinDLL("user32", use_last_error=True)
            self._k = ctypes.WinDLL("kernel32", use_last_error=True)
            self._k.GetTickCount.restype = wintypes.DWORD

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

            self._info = LASTINPUTINFO()
            self._info.cbSize = ctypes.sizeof(self._info)

        def poll(self):
            if not self._u.GetLastInputInfo(ctypes.byref(self._info)):
                return None
            return (self._k.GetTickCount() - self._info.dwTime) & 0xFFFFFFFF

    class activity:          # noqa: N801 - zastupuje modul, nie triedu
        ActivityTracker = _Idle

VZORKA_S = 0.25            # ako casto merat
MIN_USEK_S = 10.0          # kratsi usek nic nedokazuje
TICHO_PRE_USEK_S = 2.0     # medzera v ovladaci, ktora usek ukonci
OS_PRAH = 0.15             # mensia zmena osi = sum, nie pohyb
VIDI_PRAH_MS = 600         # pod tolko = Windows gamepad vidi
KLUD_PRAH_MS = 3000        # nad tolko musi idle vyjst v kludnom useku
# Medzivysledok na disk. Kratko zamerne: subor ma par stoviek bajtov, kym
# meranie je cas cloveka, ktory sedi a hybe ovladacom. Pri piatich minutach
# sa raz uz stalo, ze kratsi beh nezanechal vobec nic.
ULOZ_KAZDYCH_S = 20.0


# --------------------------------------------------------------------------
# Kurzor - kvoli ovladacom, ktore z gyroskopu robia mys
# --------------------------------------------------------------------------

_user32 = ctypes.WinDLL("user32", use_last_error=True)


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def poloha_kurzora():
    bod = _POINT()
    if _user32.GetCursorPos(ctypes.byref(bod)):
        return (bod.x, bod.y)
    return None


# --------------------------------------------------------------------------
# Ovladac - cita sa STAV, nie prud udalosti
# --------------------------------------------------------------------------

def otvor_ovladace():
    """(mena ovladacov, funkcia vracajuca True ked sa nieco pohlo).

    Stav namiesto udalosti zamerne: pri 1000 Hz report rate posle ovladac
    medzi dvoma vzorkami stovky sprav a SDL fronta ich zacne zahadzovat.
    Porovnanie polohy osi a stavu tlacidiel s predoslou vzorkou je proti
    tomu imunne a je aj lacnejsie.

    Prah na osiach je nutny: pri deadzone nastavenej na nulu paky v kludu
    drobne sumia a bez neho by sa lezaci ovladac tvaril, ze sa s nim hra.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    try:
        import pygame
    except Exception as exc:
        raise SystemExit(f"pygame sa nepodarilo importovat: {exc}")

    pygame.init()
    pygame.joystick.init()
    pady, mena = [], []
    for i in range(pygame.joystick.get_count()):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        pady.append(joy)
        mena.append(joy.get_name())

    stav = {}

    def snimka():
        out = {}
        for j, joy in enumerate(pady):
            out[("os", j)] = tuple(joy.get_axis(a) for a in range(joy.get_numaxes()))
            out[("tl", j)] = tuple(joy.get_button(b) for b in range(joy.get_numbuttons()))
            out[("hat", j)] = tuple(joy.get_hat(h) for h in range(joy.get_numhats()))
        return out

    def pohlo_sa():
        pygame.event.pump()          # bez toho sa stav neaktualizuje
        nova = snimka()
        zmena = False
        for kluc, hod in nova.items():
            stara = stav.get(kluc)
            if stara is None or len(stara) != len(hod):
                stav[kluc] = hod
                continue
            if kluc[0] == "os":
                if any(abs(a - b) > OS_PRAH for a, b in zip(hod, stara)):
                    zmena = True
            elif hod != stara:
                zmena = True
            stav[kluc] = hod
        return zmena

    def usadit(sekund=0.6):
        """Necha SDL naplnit stav osi, kym sa z neho robi referencia.

        Bez toho sa prva referencna snimka vezme z neinicializovaneho
        stavu a prve porovnanie vyhodi obrovsky rozdiel. Na Xboxe to
        preslo nahodou; DualSense ma spuste L2/R2 v kludu na -1.0 a
        inicializuju sa inak, takze hlasil skok o 2.0 - cely rozsah osi -
        a test driftu ho oznacil za pokazeny ovladac.
        """
        koniec = time.monotonic() + sekund
        while time.monotonic() < koniec:
            pygame.event.pump()
            time.sleep(0.05)

    usadit()
    pohlo_sa()                       # az teraz je referencia zmysluplna

    def kludovy_sum(sekund=4.0):
        """Najvacsia zmena osi, kym ovladac LEZI. Test na drift.

        Ovladac s driftom (typicky s deadzone na nule) hlasi pohyb aj
        vtedy, ked sa ho nikto nedotyka. Cele meranie by potom vyzeralo
        ako "hybalo sa ovladacom a idle pritom rastie" - cize falosne
        NEVIDI. Preto sa to zmeria hned na zaciatku a ked je sum nad
        prahom, skript to povie a nema zmysel pokracovat.
        """
        usadit()
        predch = snimka()
        naj = 0.0
        koniec = time.monotonic() + sekund
        while time.monotonic() < koniec:
            time.sleep(0.05)
            pygame.event.pump()
            teraz = snimka()
            for kluc, hod in teraz.items():
                if kluc[0] != "os":
                    continue
                stara = predch.get(kluc, hod)
                if len(stara) == len(hod):
                    naj = max(naj, max((abs(a - b) for a, b in zip(hod, stara)),
                                       default=0.0))
            predch = teraz
        pohlo_sa()                   # zresetuj referenciu po merani sumu
        return round(naj, 4)

    return mena, pohlo_sa, kludovy_sum


def prostredie():
    """Co na tomto pocitaci moze vysledok ovplyvnit."""
    info = {"steam_bezi": False, "podozrive": []}
    try:
        import psutil
        mena = {p.info["name"].lower() for p in psutil.process_iter(["name"])
                if p.info.get("name")}
        info["steam_bezi"] = any("steam" in m for m in mena)
        for vzor in ("ds4windows", "x360ce", "rewasd", "vigem", "hidhide",
                     "antimicro", "joytokey", "gamesir", "nexus", "armourycrate",
                     "logi", "razer", "icue"):
            info["podozrive"] += [m for m in mena if vzor in m]
        info["podozrive"] = sorted(set(info["podozrive"]))
    except Exception as exc:
        info["chyba"] = str(exc)
    return info


# --------------------------------------------------------------------------
# Vyhodnotenie
# --------------------------------------------------------------------------

def useky(vzorky, s_ovladacom):
    """Suvisle useky, v ktorych ovladac (ne)chodil.

    `vzorky` je [(cas, idle_ms, pohol_sa_pad, pohol_sa_kurzor)].
    """
    out, zac, posledny = [], None, None
    for i, (t, _idle, pad, _mys) in enumerate(vzorky):
        if pad:
            posledny = t
        if s_ovladacom:
            drzi = pad or (posledny is not None and t - posledny <= TICHO_PRE_USEK_S)
        else:
            drzi = not pad
        if drzi and zac is None:
            zac = i
        elif not drzi and zac is not None:
            out.append((zac, i))
            zac = None
    if zac is not None:
        out.append((zac, len(vzorky)))
    return [(a, b) for a, b in out if vzorky[b - 1][0] - vzorky[a][0] >= MIN_USEK_S]


def vrcholy_idle(vzorky, rozsahy):
    """Najvyssie idle v KAZDOM useku zvlast.

    Zamerne nie jedno cislo za vsetko: pri dlhom merani staci jeden cudny
    okamih (appka na sekundu zamrzne) a maximum cez vsetko by rozhodlo samo.
    Zo zoznamu vrcholov sa da vziat median.
    """
    out = []
    for a, b in rozsahy:
        naj = 0
        for _t, idle, _p, _m in vzorky[a:b]:
            if idle is not None:
                naj = max(naj, idle)
        out.append(naj)
    return out


def idle_pri_pohybe(vzorky):
    """`idle` presne vo vzorkach, kde sa ovladac POHOL.

    Toto je ten pravy test a je jednoduchsi nez delenie na useky: ak
    Windows gamepad vidi, tak pohyb sam idle vynuluje, takze v takej
    vzorke MUSI byt idle mensie nez vzorkovacia perioda. Ak ho nevidi,
    idle tam bude take, ake bolo od posledneho dotyku klavesnice ci mysi
    - cize lubovolne velke.

    Vzorky, v ktorych sa hybal aj kurzor, sa vynechavaju: mys idle nuluje
    sama a o gamepade by nepovedali nic.

    PRECO NIE MAXIMUM V USEKU: usek ma na konci dvojsekundovu toleranciu,
    aby ho kratka pauza neroztrhla - lenze pocas nej sa uz nicim nehybe a
    idle v nej prirodzene vylezie na ~2000 ms. Merala by sa tak vlastna
    tolerancia, nie gamepad. Prva verzia tohto skriptu to robila a davala
    kvoli tomu 640 ms tam, kde ma byt bud skoro nula, alebo vela sekund.
    """
    return sorted(idle for _t, idle, pad, mys in vzorky
                  if pad and not mys and idle is not None)


def vyhodnot(vzorky):
    s_pad = useky(vzorky, True)
    bez_pad = useky(vzorky, False)
    vr_pad = vrcholy_idle(vzorky, s_pad)
    vr_klud = vrcholy_idle(vzorky, bez_pad)

    # V kolkych usekoch "len ovladac" sa popri nom hybal aj kurzor?
    s_mysou = 0
    for a, b in s_pad:
        if sum(1 for _t, _i, _p, m in vzorky[a:b] if m) >= 3:
            s_mysou += 1

    pri_pohybe = idle_pri_pohybe(vzorky)

    def kvantil(zoznam, p):
        return int(zoznam[min(len(zoznam) - 1, int(len(zoznam) * p))]) if zoznam else 0

    return {
        "vzoriek": len(vzorky),
        "minut": round(vzorky[-1][0] / 60, 1) if vzorky else 0,
        # HLAVNY TEST: idle vo vzorkach, kde sa ovladac pohol a mys nie
        "vzoriek_pohyb_bez_mysi": len(pri_pohybe),
        "idle_pri_pohybe_median_ms": kvantil(pri_pohybe, 0.5),
        "idle_pri_pohybe_p90_ms": kvantil(pri_pohybe, 0.9),
        "idle_pri_pohybe_max_ms": pri_pohybe[-1] if pri_pohybe else 0,
        # Surove pocty, nezavisle od delenia na useky. Bez nich sa neda
        # rozlisit "hybal kratko" od "ovladac nevidime vobec" - a to je
        # presne ta otazka, ktora sa pyta ako prva, ked vyjde 0 usekov.
        "vzoriek_s_pohybom_ovladaca": sum(1 for _t, _i, p, _m in vzorky if p),
        "vzoriek_s_pohybom_kurzora": sum(1 for _t, _i, _p, m in vzorky if m),
        "usekov_s_ovladacom": len(s_pad),
        "najdlhsi_usek_s_ovladacom_s": round(
            max((vzorky[b - 1][0] - vzorky[a][0] for a, b in s_pad), default=0), 1),
        "median_vrcholu_pri_ovladaci_ms": int(statistics.median(vr_pad)) if vr_pad else 0,
        "max_vrchol_pri_ovladaci_ms": max(vr_pad, default=0),
        "usekov_kde_idle_vyskocilo": sum(1 for v in vr_pad if v >= VIDI_PRAH_MS),
        "usekov_kde_sa_hybal_aj_kurzor": s_mysou,
        "usekov_bez_vstupu": len(bez_pad),
        "median_vrcholu_v_kludu_ms": int(statistics.median(vr_klud)) if vr_klud else 0,
        "max_vrchol_v_kludu_ms": max(vr_klud, default=0),
    }


def verdikt(v):
    # --- hlavny test: idle vo vzorkach, kde sa ovladac pohol -------------
    k = v["vzoriek_pohyb_bez_mysi"]
    median, p90 = v["idle_pri_pohybe_median_ms"], v["idle_pri_pohybe_p90_ms"]
    if v["vzoriek_s_pohybom_ovladaca"] and k >= 20:
        if v["max_vrchol_v_kludu_ms"] < KLUD_PRAH_MS:
            return "NEPLATNE", (
                "Idle nevyskocilo ani vtedy, ked sa nedialo nic (najviac "
                f"{v['max_vrchol_v_kludu_ms']} ms). Nieco na tomto pocitaci "
                "generuje vstup neustale.")
        if median <= 300 and p90 <= 500:
            return "VIDI", (
                f"V {k} vzorkach, kde sa ovladac pohol a mys nie, bolo idle "
                f"medianovo {median} ms a v 90 % pod {p90} ms - cize sa nulovalo "
                "pri kazdom pohybe. Windows povazuje gamepad za vstup. "
                "POZOR, tento smer je slabsi: idle nuluje aj klavesnica a ci si "
                "pritom pisal, sa bez hooku zistit neda. Ak si popri ovladaci "
                "pisal, over to behom, pri ktorom sa klavesnice nedotknes.")
        if median >= 1000:
            return "NEVIDI", (
                f"V {k} vzorkach, kde sa ovladac pohol a mys nie, bolo idle "
                f"medianovo {median} ms (max {v['idle_pri_pohybe_max_ms']} ms). "
                "Keby Windows gamepad videl, pohyb sam by idle vynuloval a tieto "
                "cisla by boli pod vzorkovacou periodou. Nie su - appka teda "
                "potrebuje aj SDL vrstvu, inak by hraca na ovladaci povazovala "
                "za neaktivneho.")
        return "NEJEDNOZNACNE", (
            f"V {k} vzorkach s pohybom ovladaca bolo idle medianovo {median} ms, "
            f"v 90 % pod {p90} ms. Ani jasne nula, ani jasne vela. "
            "Najpravdepodobnejsie islo popri ovladaci aj nieco ine - zopakuj to "
            "tak, ze sa okrem ovladaca nedotknes nicoho.")

    n = v["usekov_s_ovladacom"]
    if v["vzoriek_s_pohybom_ovladaca"] == 0:
        return "NEVIDIME OVLADAC", (
            "Za cely cas merania sa ovladac nepohol ani raz - a to nie je "
            "o dlzke usekov, je to surovy pocet. Bud sa s nim naozaj nehybalo, "
            "alebo ho tento skript necita: ovladac mohol zaspat (GameSir ma "
            "Auto On/Off), odpojit sa, alebo ho drzi ina appka. Skus stlacit "
            "tlacidlo a pozri, ci sa cislo pohne.")
    if n < 3:
        return "NEPRESVEDCIVE", (
            f"Ovladac sa hybal ({v['vzoriek_s_pohybom_ovladaca']} vzoriek), ale "
            f"nasli sa len {n} useky aspon {MIN_USEK_S:.0f} s. Hybaj s nim "
            "suvislejsie - aspon 15 sekund v kuse, potom rovnako dlho ruky prec.")

    if v["usekov_kde_sa_hybal_aj_kurzor"] >= n * 0.5:
        return "NEPLATNE", (
            f"V {v['usekov_kde_sa_hybal_aj_kurzor']} z {n} usekov sa popri ovladaci "
            "hybal aj kurzor mysi. Bud si popri hrani pouzival mys, alebo - a to je "
            "pravdepodobnejsie, ak si sa jej nedotkol - ti ovladac posiela pohyb mysi "
            "z gyroskopu. Potom je v ociach Windowsu mys, nie gamepad, a idle sa "
            "nuluje uplne inym kanalom. Vypni Motion output na mys a zmeraj znova.")

    if v["max_vrchol_v_kludu_ms"] < KLUD_PRAH_MS:
        return "NEPLATNE", (
            "Idle nevyskocilo ani vtedy, ked sa nedialo nic (najviac "
            f"{v['max_vrchol_v_kludu_ms']} ms). Nieco na tomto pocitaci generuje "
            "vstup neustale, takze nizke idle pri ovladaci nic nedokazuje.")

    vyskocilo = v["usekov_kde_idle_vyskocilo"]
    median = v["median_vrcholu_pri_ovladaci_ms"]
    if median < VIDI_PRAH_MS and vyskocilo <= n * 0.1:
        return "VIDI", (
            f"Z {n} usekov s ovladacom idle vyskocilo len v {vyskocilo}; bezne "
            f"nevystupilo nad {median} ms, kym v klude siahalo na "
            f"{v['max_vrchol_v_kludu_ms']} ms. Windows povazuje gamepad za vstup. "
            "POZOR, tento smer je slabsi nez opacny: idle nuluje aj klavesnica, "
            "a ci si popri ovladaci pisal, sa bez hooku zistit neda (kurzor "
            "sledovany je, klavesy zamerne nie). Ak si popri hrani aj pisal, "
            "over to este raz behom, pri ktorom sa klavesnice nedotknes. "
            "Opacny vysledok (NEVIDI) taku slabinu nema - ked idle RASTIE, "
            "nerobil v tej chvili nic ani ovladac, ani nic ine.")
    if median >= VIDI_PRAH_MS and vyskocilo >= n * 0.9:
        return "NEVIDI", (
            f"Z {n} usekov idle vyskocilo v {vyskocilo} a bezne vystupilo na "
            f"{median} ms, hoci sa suvisle hybalo ovladacom. Windows ho za vstup "
            "nepovazuje - appka teda potrebuje aj SDL vrstvu, inak by hraca na "
            "ovladaci povazovala za neaktivneho.")
    return "NEJEDNOZNACNE", (
        f"Z {n} usekov idle vyskocilo v {vyskocilo}, medianovy vrchol je {median} ms. "
        "Ani jasne ano, ani jasne nie - najpravdepodobnejsie islo v niektorych "
        "usekoch popri ovladaci aj klavesnica. Dlhsie meranie to rozhodne.")


def nazov_suboru(poznamka):
    """Kazdy beh do vlastneho suboru, aby sa dali porovnat.

    Bez toho by druhy beh (napr. s vypnutym Steam Input) prepisal prvy -
    a prave ich porovnanie je to, co ma cenu.
    """
    slug = "".join(c if c.isalnum() else "_" for c in (poznamka or "beh").lower())
    slug = "_".join(filter(None, slug.split("_")))[:40] or "beh"
    return f"gamepad_probe_{slug}.json"


def uloz(vysledok, kde, subor):
    os.makedirs(kde, exist_ok=True)
    cesta = os.path.join(kde, subor)
    tmp = cesta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(vysledok, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, cesta)
    return cesta


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minuty", type=float, default=None,
                    help="casovy strop; bez neho bezi, kym ho nezastavis (Ctrl+C)")
    ap.add_argument("--poznamka", default="",
                    help='co je na tomto behu ine, napr. "steam input vypnuty". '
                         'Ide do vysledku aj do nazvu suboru, aby sa dva behy '
                         'dali porovnat a neprepisali sa.')
    args = ap.parse_args()

    mena, pohlo_sa, kludovy_sum = otvor_ovladace()
    if not mena:
        raise SystemExit("Nie je pripojeny ziadny ovladac - meranie nema co merat.")

    prost = prostredie()
    sledovac = activity.ActivityTracker()   # to iste, co pouziva appka
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

    print(__doc__.split("POUZITIE")[0].rstrip())
    print("-" * 72)
    for m in mena:
        print(f"ovladac: {m}")
    if prost["steam_bezi"]:
        print("Steam bezi  <- odmeraj to potom este raz s uplne vypnutym Steamom")
    if prost["podozrive"]:
        print(f"software okolo vstupu: {', '.join(prost['podozrive'])}")
    if not _Z_PROJEKTU:
        print("(samostatny beh - meria sa vlastnym citacom idle, nie activity.py)")
    print("-" * 72)
    print("Test driftu - NECHAJ OVLADAC LEZAT 4 sekundy...", flush=True)
    sum_v_klude = kludovy_sum()
    if sum_v_klude > OS_PRAH:
        print(f"  !! osi sa v klude hybu o {sum_v_klude} (prah je {OS_PRAH})")
        print("     Ovladac driftuje - hlasil by pohyb aj ked sa ho nikto")
        print("     nedotyka a cele meranie by vyslo falosne NEVIDI.")
        print("     Zvys deadzone v software k ovladacu a spusti znova.")
        raise SystemExit(2)
    print(f"  OK - v klude sa osi hybu najviac o {sum_v_klude} (prah {OS_PRAH})")
    print("-" * 72)
    strop = f"{args.minuty:.0f} minut" if args.minuty else "kym nedas Ctrl+C"
    print(f"Meram {strop}. TERAZ HRAJ - ovladacom aj klavesnicou, ako normalne.")
    print("Skript si useky najde sam.")
    print("-" * 72)

    vzorky = []
    kurzor = poloha_kurzora()
    start = time.monotonic()
    dalsi_vypis = start + 60.0
    dalsie_ulozenie = start + ULOZ_KAZDYCH_S

    subor = nazov_suboru(args.poznamka)

    def zbal():
        v = vyhodnot(vzorky)
        stav, preco = verdikt(v)
        return {"stav": stav, "preco": preco, "poznamka": args.poznamka,
                "merania": v, "ovladace": mena, "prostredie": prost}

    try:
        while True:
            teraz = time.monotonic()
            uplynulo = teraz - start
            if args.minuty and uplynulo >= args.minuty * 60:
                break

            pad = pohlo_sa()
            nova_poloha = poloha_kurzora()
            mys = nova_poloha is not None and nova_poloha != kurzor
            kurzor = nova_poloha
            idle = sledovac.poll()
            vzorky.append((uplynulo, idle, pad, mys))

            if teraz >= dalsi_vypis:
                v = vyhodnot(vzorky)
                # flush: pri behu na pozadi si Python vystup buferuje a pri
                # tvrdom ukonceni by sa stratil aj ten
                print(f"  {uplynulo/60:5.0f} min   usekov s ovladacom: "
                      f"{v['usekov_s_ovladacom']:3d}   z toho s kurzorom: "
                      f"{v['usekov_kde_sa_hybal_aj_kurzor']:3d}", flush=True)
                dalsi_vypis += 60.0
            if teraz >= dalsie_ulozenie:
                uloz(zbal(), log_dir, subor)
                dalsie_ulozenie += ULOZ_KAZDYCH_S
            time.sleep(VZORKA_S)
    except KeyboardInterrupt:
        print("\n  (ukoncene)")

    if not vzorky:
        raise SystemExit("Ziadne vzorky.")

    vysledok = zbal()
    v = vysledok["merania"]
    print()
    print("=" * 72)
    print(f"VYSLEDOK: {vysledok['stav']}     ({v['minut']} minut merania)")
    print("=" * 72)
    print(f"  {vysledok['preco']}")
    print()
    print("  --- hlavny test: idle vo vzorkach, kde sa ovladac pohol ---")
    print(f"  takych vzoriek (bez mysi)          : {v['vzoriek_pohyb_bez_mysi']}")
    print(f"  idle medianovo                     : {v['idle_pri_pohybe_median_ms']} ms")
    print(f"  idle v 90 % pod                    : {v['idle_pri_pohybe_p90_ms']} ms")
    print(f"  idle najviac                       : {v['idle_pri_pohybe_max_ms']} ms")
    print("  --- kontrola ---")
    print(f"  najvyssie idle v klude             : {v['max_vrchol_v_kludu_ms']} ms")
    print(f"  sum osi v klude (drift)            : {sum_v_klude}")

    cesta = uloz(vysledok, log_dir, subor)
    print(f"\n  ulozene do: {cesta}")
    print("  (su v nom len tieto cisla a meno ovladaca - ziadny zaznam toho,")
    print("   co sa stlacalo, a nic, co by islo von z pocitaca)")


if __name__ == "__main__":
    main()
