"""Statistika tepu - pokojova zakladna, index zataze, priebeh relacie.

Co je a co NIE je "zataz"
------------------------
Z hodiniek chodi jedine cislo: BPM, zhruba raz za sekundu. To NIE je HRV
a nie je z toho mozne pocitat ani RMSSD, ani SDNN - na to su potrebne
vzdialenosti medzi jednotlivymi udermi (R-R intervaly), ktore appka
nedostava. Cokolvek, co by sa tu volalo "HRV", by bolo vymyslene cislo.

Preto sa pocita `stress` (v UI "Záťaž") ako otvorene priznana zlozenina
troch veci, ktore sa Z BPM zistit DAJU:

  1. `over`      - o kolko je tep nad vlastnou pokojovou zakladnou hraca,
                   skalovane k jeho kritickej hranici (55 % vahy)
  2. `slope`     - ako rychlo tep prave stupa (20 % vahy); prudky nastup
                   je to, co hrac citi ako "nakoplo ma to", este skor nez
                   je cislo vysoke
  3. `sustained` - kolko z poslednych 2 minut stravil nad zakladnou
                   (25 % vahy); kratky spike po headshote nie je stres,
                   dve minuty na 120 BPM ano

Vysledok je vyhladeny exponencialnym priemerom, aby pruh na HUD-e
neposkakoval pri kazdom udere.

Zakladna (`baseline`) nie je konstanta z nastaveni: berie sa ako 20.
percentil poslednych ~10 minut, cize "aky tep ma tento hrac, ked ho hra
prave nikam netlaci". Kto ma pokojovy tep 52 a kto 78, dostanu tak
porovnatelny vysledok bez toho, aby cokolvek nastavovali.

Metriky, ktore sa z cisteho BPM spocitat DAJU (a v suhrne relacie su)
----------------------------------------------------------------------
  * HRR - Heart Rate Recovery: o kolko klesol tep za 1 min po vrchole.
    Standardna klinicka metrika (Cleveland Clinic: bezne 12-23 BPM,
    trenovani 29+). Pocita sa z lokalnych vrcholov relacie, hlavne cislo
    je zotavenie po NAJVYSSOM vrchole (viz heart_rate_recovery).
  * baseline_bpm - pokojova zakladna CELEJ relacie (20. percentil), aby sa
    dal sledovat trend naprieC relaciami (stupajuca zakladna den za dnom =
    unava/stres, nie nutne z hrania).
  * zone_seconds - cas v pasmach pokoj/zvysena/vysoka/kriticka, v SEKUNDACH
    (nie vo vzorkach - rovnaka pasca ako time_over).
  * HRPI - Heart Rate Persistence Index: najvacsie k, pri ktorom bol tep
    aspon k BPM po dobu aspon k SEKUND (kumulativne). Analogia h-indexu:
    spaja vysku a trvanie do jedneho cisla (viz persistence_index).
Nic z toho nie je HRV a nic z toho nie je diagnoza.
"""

import json
import os
import time
from datetime import datetime, timedelta

HISTORY_SECONDS = 180.0        # co drzime na krivku HUD-u
BASELINE_SECONDS = 600.0       # z coho sa rata pokojova zakladna
# Tvar CELEJ relacie ulozeny do suhrnu.
#
# 120 -> 600. Pri 15-minutovej relacii to je jeden bod na 1,5 s namiesto
# 7,4 s, teda priblizne skutocna hustota vzoriek z hodiniek. Nizsie
# rozlisenie znamenalo, ze sa spatne nedalo odpovedat na otazku "preco sa
# vtedy neozvala" - interpolacia zo 120 bodov vyrobi hladkost, ktora tam
# nebola, a z nej vyjde iny zaver nez z realneho priebehu.
#
# Cena je par kilobajtov na relaciu. Za moznost prepocitat si vlastne
# nastavenie z vlastnych dat to stoji.
CURVE_POINTS = 600
SLOPE_WINDOW_S = 20.0
SUSTAINED_WINDOW_S = 120.0

SMOOTHING = 0.25               # vaha novej hodnoty pri vyhladzovani

ZONE_CALM = "calm"
ZONE_RAISED = "raised"
ZONE_HIGH = "high"
ZONE_CRITICAL = "critical"


def zone_for(stress):
    if stress >= 75:
        return ZONE_CRITICAL
    if stress >= 50:
        return ZONE_HIGH
    if stress >= 25:
        return ZONE_RAISED
    return ZONE_CALM


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * pct))
    return ordered[max(0, min(len(ordered) - 1, idx))]


# --------------------------------------------------------------------------
# Ciste vypocty nad [(timestamp, bpm)] - bez stavu, testovatelne priamo
# --------------------------------------------------------------------------

MAX_SAMPLE_GAP_S = 5.0         # dlhsia diera = vypadok, cas sa nepripisuje


def _durations(samples):
    """Kolko sekund "plati" kazda vzorka - do dalsej vzorky, max 5 s.
    Posledna vzorka dostane typicky interval (median), aby nebola nula."""
    n = len(samples)
    if n == 0:
        return []
    gaps = []
    for i in range(n - 1):
        gaps.append(max(0.0, min(MAX_SAMPLE_GAP_S, samples[i + 1][0] - samples[i][0])))
    last = sorted(gaps)[len(gaps) // 2] if gaps else 1.0
    gaps.append(min(MAX_SAMPLE_GAP_S, max(0.0, last)) or 1.0)
    return gaps


def session_baseline(samples, min_samples=30):
    """Pokojova zakladna celej relacie - 20. percentil vsetkych vzoriek.
    Pod 30 vzoriek None (rovnaky prah ako ziva zakladna)."""
    values = [b for _, b in samples]
    if len(values) < min_samples:
        return None
    return _percentile(values, 0.20)


def downsample(values, points):
    """Rovnomerne prerieduje zoznam na `points` hodnot.

    Nie orezanie: orezanim by sa z dvojhodinovej relacie stala krivka
    poslednych desiatich minut. Rovnaky princip ako `HeartStats.series`.
    """
    values = list(values)
    if points < 1 or len(values) <= points:
        return values
    step = len(values) / float(points)
    return [values[int(i * step)] for i in range(points)]


DLHODOBA_MIN_RELACII = 3       # menej relacii = nemame co priemerovat
DLHODOBA_Z_RELACII = 20        # z kolkych poslednych relacii sa rata
DLHODOBA_PODLAHA = 40.0        # nizsie uz to nie je pokojovy tep, ale chyba


# Podiel fyziologicky nemoznych skokov, od ktoreho je relacia podozriva.
#
# Tep sa medzi dvoma vzorkami (~1,5 s) o 30 bpm neposunie. Ked sa to deje
# opakovane, nemeria sa telo, ale nieco ine - 19. 9. to bol parser, ktory po
# pridani krokov a rychlosti do spravy z hodiniek cital raz tep a raz pocet
# krokov. Vysledkom bola 52-minutova relacia s priemerom 124 a maximom 235.
#
# Hranica 5 % je velkoryso nizko: v 12 zdravych relaciach bolo takych skokov
# 0 %, v tej pokazenej 18 %. Medzi tym nie je nic.
PODOZRIVE_SKOKY = 0.05
NEMOZNY_SKOK_BPM = 30.0
# Nad tuto hodnotu uz nejde o ludsky tep, ale o zle precitane cislo (kroky).
# Zamerne vysoko nad realnym maximom aj mladeho hraca, nech to nechyti
# ozajstnu spicku - chyta pokazene citanie (max 235 z krokov).
NEMOZNE_MAX_BPM = 220.0


def je_podozriva(session):
    """True, ked relacia nevyzera ako ludsky tep.

    Nezahadzuje sa - len sa nerata do niceho, co z dat vyvodzuje zavery.
    """
    if not isinstance(session, dict):
        return True
    # NEZÁVISLE OD KRIVKY: nemožné maximum tepu = čítanie krokov ako tepu
    # (pokazená relácia mala avg 124, max 235). Toto chytí aj reláciu BEZ
    # krivky (B12) aj takú, kde podvzorkovanie striedanie bpm/steps zahladilo
    # (B11) - `curve` je preriedená na 600 bodov, `max_bpm` je zo surových.
    try:
        mx = float(session.get("max_bpm") or 0)
    except (TypeError, ValueError):
        return True
    if mx > NEMOZNE_MAX_BPM:
        return True
    krivka = session.get("curve") or []
    if len(krivka) < 10:
        return False        # prikratka na posudenie, nechame ju byt
    try:
        skoky = [abs(float(krivka[i + 1]) - float(krivka[i]))
                 for i in range(len(krivka) - 1)]
    except (TypeError, ValueError):
        return True
    if not skoky:
        return False
    podiel = sum(1 for x in skoky if x > NEMOZNY_SKOK_BPM) / float(len(skoky))
    return podiel >= PODOZRIVE_SKOKY


def ciste_relacie(sessions):
    """Relacie, z ktorych sa smie pocitat: bez podozrivych a bez CUDZICH.

    Importovane relacie (`imported`) su cudzie telo - ina zakladna, iny
    kriticky tep. `measure` aj `hr_insights` ich uz vylucuju; `hr_stats` to
    doteraz nerobil, takze jeden import cudzieho exportu posunul hracovi
    zakladnu, kriticky tep aj prah zataze (B10).

    Od vyskumu 2026-09-22 sa vylucuju aj CONFOUNDED relacie (`je_confounded`:
    alkohol, choroba, fyzicka namaha tesne pred hranim) - jeden opity vecer cez
    per-session baseline inak vojde do dlhodobeho 20. percentilu a skresli
    desiatky cistych relacii. Relacie sa NEMAZU, len sa neucia zo skreslenych.
    """
    return [x for x in (sessions or [])
            if isinstance(x, dict) and not x.get("imported")
            and not je_podozriva(x) and not je_confounded(x)]


# --------------------------------------------------------------------------
# Kriticky tep: vypocet, nie nastavenie
# --------------------------------------------------------------------------

KRITICKY_PERCENTIL = 0.90      # "hornych desat percent tvojho hrania"
KRITICKY_MIN_RELACII = 3
KRITICKY_MIN_BODOV = 300
KRITICKY_Z_RELACII = 20
KRITICKY_ZALOHA = 110.0        # kym nie je z coho ratat
KRITICKY_MIN_NAD_ZAKLADNOU = 20.0
KRITICKY_MIN_BOD, KRITICKY_MAX_BOD = 25.0, 250.0   # bod krivky mimo = sum
KRITICKY_STROP = (80.0, 200.0)  # kriticky prah sa drzi v rozumnom rozsahu


def dynamicky_kriticky(sessions, baseline=None):
    """Kriticky tep spocitany z vlastnych relacii hraca.

    PRECO TO NIE JE NASTAVENIE
    Bolo nim - a nedalo sa nastavit dobre. Cislo vstupuje do vzorca zataze
    ako `headroom = max(12, kriticky - zakladna)`, takze pri zakladni 77
    dava hocico do 89 rovnaky vysledok (podlahu 12) a hrac nema ako zistit,
    ze posuvanim z 80 na 90 nic nemeni. Zaroven urcuje pasmo "kriticka",
    takze prilis nizka hodnota spravi z pokojneho vecera 52 % v cervenom.

    CO SA RATA
    90. percentil zo zlucenych krivok poslednych `KRITICKY_Z_RELACII` CISTYCH
    relacii - teda "tep, nad ktory sa dostanes v hornej desatine hrania".
    Na testovacich datach to dava 105 pri zakladni 77: headroom 28 a pasmo
    kriticka pokryva 10 % casu.

    Vracia `KRITICKY_ZALOHA`, kym nie je z coho ratat. `baseline` je len
    poistka, aby vysledok neskoncil tesne nad zakladnou.
    """
    ciste = ciste_relacie(sessions)[-KRITICKY_Z_RELACII:]
    if len(ciste) < KRITICKY_MIN_RELACII:
        return KRITICKY_ZALOHA
    body = []
    for r in ciste:
        for b in (r.get("curve") or []):
            try:
                v = float(b)
            except (TypeError, ValueError):
                continue
            # Body mimo ludskeho tepu do percentilu nepatria - jedna pokazena
            # plocha by inak vytlacila kriticky prah nahor (B9).
            if KRITICKY_MIN_BOD <= v <= KRITICKY_MAX_BOD:
                body.append(v)
    if len(body) < KRITICKY_MIN_BODOV:
        return KRITICKY_ZALOHA
    hodnota = _percentile(sorted(body), KRITICKY_PERCENTIL)
    if baseline:
        # Headroom nesmie byt symbolicky - inak sa zataz vyskaluje na
        # niekolkych uderoch a appka bude reagovat na sum.
        hodnota = max(hodnota, float(baseline) + KRITICKY_MIN_NAD_ZAKLADNOU)
    # STROP: sesterska `dynamicky_prah_zataze` ho ma (PRAH_ROZSAH), tato ho
    # nemala - jedna nezmyselna krivka mohla vytlacit kriticky prah az k 235
    # a appka by uz nikdy neoznacila nic ako kriticke a stichla (B9).
    return float(round(max(KRITICKY_STROP[0], min(KRITICKY_STROP[1], hodnota))))


PRAH_PERCENTIL = 0.80          # nad prahom ma byt ~20 % casu hrania
PRAH_MIN_RELACII = 3
PRAH_MIN_BODOV = 1000
PRAH_Z_RELACII = 20
PRAH_MIN_TRVANIE_S = 300.0
PRAH_ROZSAH = (35.0, 85.0)


def load_z_krivky(session, baseline, critical, krok_s=1.5):
    """Prehra ulozenu krivku relacie a vrati z nej priebeh ZATAZE.

    Relacia si uklada tep, nie zataz - tu sa dopocita tym istym kodom, aky
    bezi naostro (`HeartStats`), takze sa vysledok nemoze rozist s tym, co
    appka pocitala v realnom case.
    """
    krivka = session.get("curve") or []
    trvanie = float(session.get("duration_s") or 0)
    if len(krivka) < 10 or trvanie < PRAH_MIN_TRVANIE_S:
        return []
    st = HeartStats(critical_bpm=int(critical or 110))
    st.long_baseline = baseline
    out = []
    t = 0.0
    for i in range(int(trvanie / krok_s)):
        x = i * krok_s / trvanie * (len(krivka) - 1)
        a = int(x)
        b = min(a + 1, len(krivka) - 1)
        try:
            hodnota = krivka[a] + (krivka[b] - krivka[a]) * (x - a)
        except (TypeError, ValueError):
            continue
        t += krok_s
        st.add(hodnota, ts=t)
        out.append(st.stress)
    return out


def dynamicky_prah_zataze(sessions, baseline=None, critical=None):
    """Prah zataze, pri ktorom sa appka zacne natahovat. Alebo None.

    PRECO TO NIE JE NASTAVENIE
    Bolo - ako volba "ako casto sa ozvem" s tromi polohami. Lenze hrac nema
    ako vediet, co ktora poloha urobi PRAVE JEMU: zataz je skalovana voci
    jeho vlastnej zakladne, takze to iste cislo znamena u kazdeho nieco ine.

    AKO SA TO RATA
    80. percentil jeho vlastnej zataze napriec cistymi relaciami - teda
    "hranica, nad ktorou travi patinu hrania". Odmerane na testovacich datach
    to dava prah 73 a 3,7 dorucenych hlasok za hodinu, co sedi pod strop 5
    zo zadania. Nizsi prah strop len vycerpa skor a hlasky padnu na menej
    vyhrotene momenty.

    Prah teda neurcuje, KOLKO hlasok pride - to robi `max_per_hour` a
    `min_gap_s`. Urcuje, KTORE momenty sa na ne kvalifikuju.

    Vracia None, kym nie je z coho ratat - volajuci vtedy necha cisla pre
    priemerneho hraca z `trigger.default_params()`.
    """
    pouzitelne = [r for r in ciste_relacie(sessions)
                  if float(r.get("duration_s") or 0) >= PRAH_MIN_TRVANIE_S
                  and r.get("curve")][-PRAH_Z_RELACII:]
    if len(pouzitelne) < PRAH_MIN_RELACII:
        return None
    body = []
    for r in pouzitelne:
        body.extend(load_z_krivky(r, baseline, critical))
    if len(body) < PRAH_MIN_BODOV:
        return None
    prah = _percentile(sorted(body), PRAH_PERCENTIL)
    lo, hi = PRAH_ROZSAH
    return float(round(max(lo, min(hi, prah))))


def dlhodoba_zakladna(sessions):
    """Pokojova zakladna hraca naprieč relaciami, alebo None.

    PRECO TO NESTACI RATAT Z JEDNEJ RELACIE
    Zakladna vnutri relacie je 20. percentil poslednych 10 minut. Ked hrac
    zapne appku az uprostred boja - alebo ked tep drzi hore cely vecer -
    to okno pokoj nikdy neuvidi a zakladna sa ustali na strese. Zataz sa
    pocita voci nej, takze appka v suvislom strese vidi zataz nula.

    Hrac ma ale pokojovy tep aj vtedy, ked ho dnes vecer neukazal - je
    zapisany v predchadzajucich relaciach. Berie sa 20. percentil zakladien
    z poslednych `DLHODOBA_Z_RELACII` relacii: ta ista statistika, len o
    poschodie vyssie, takze jeden zly vecer vysledok neurcí.
    """
    hodnoty = []
    # Podozriva relacia (pokazene citanie tepu) nesmie urcovat zakladnu -
    # viz `je_podozriva`.
    for s in ciste_relacie(sessions)[-DLHODOBA_Z_RELACII:]:
        try:
            b = float(s.get("baseline_bpm") or 0)
        except (TypeError, ValueError):
            continue
        if b >= DLHODOBA_PODLAHA:
            hodnoty.append(b)
    if len(hodnoty) < DLHODOBA_MIN_RELACII:
        return None
    return _percentile(sorted(hodnoty), 0.20)



# --------------------------------------------------------------------------
# "Plny Zanshin" - promocia (easter egg). Detekcia nad ULOZENOU historiou,
# voci VLASTNEJ zakladni hraca; nikdy nad zivym senzorom. Spusti sa RAZ.
# Cisla su volene voci baseline (nie fixne): base+12 (~"pod 90" bezne),
# base+18 (~"pod 95" v spickach), 5 z poslednych 7, min 10 relacii a 10 dni.
# --------------------------------------------------------------------------
ZEN_REG_MARGIN = 12.0
ZEN_SPIKE_MARGIN = 18.0
ZEN_REG_QUANTILE = 0.80
ZEN_SPIKE_QUANTILE = 0.95
ZEN_MAX_CRIT_CROSSINGS = 1
ZEN_MIN_DURATION_S = 900.0
ZEN_MIN_SAMPLES = 300
ZEN_WINDOW = 7
ZEN_NEEDED = 5
ZEN_MIN_TOTAL = 10
ZEN_MIN_SPAN_DAYS = 10.0


def _rising_crossings(curve, threshold):
    """Kolkokrat krivka STUPAJUCO prekroci prah (len prechody zdola nahor -
    jedno vyskocenie = jedno prekrocenie, nie kazdy bod nad prahom)."""
    n = 0
    hore = False
    for v in curve:
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if not hore and x >= threshold:
            n += 1
            hore = True
        elif hore and x < threshold:
            hore = False
    return n


def je_plne_zanshin(session):
    """Bola relacia "plny Zanshin"? True / False / None.

    None = relacia sa NEPOCITA (kratka, bez dat, podozriva, importovana) -
    zamerne, aby volne dni a rychle nahliadnutia NIKDY netrestali (appka
    nesmie vytvorit seriu, ktora sa da stratit; viz zrusene `streaks()`).

    Inak PASS iff (voci VLASTNEJ zakladni):
      1. 80 % priebehu <= base + ZEN_REG_MARGIN   (~pod 90, bezny pokoj)
      2. aj najhorucejsich 5 % <= base + ZEN_SPIKE_MARGIN  (~pod 95 v spickach)
      3. <= ZEN_MAX_CRIT_CROSSINGS stupajucich prekroceni kritickej linie
    Percentily (nie max_bpm): modul neveri jednotlivym extremom - jeden
    artefaktovy uder nesmie zrusit pokojny vecer.
    """
    try:
        if session is None or je_podozriva(session) or session.get("imported"):
            return None
        base = float(session.get("baseline_bpm") or 0)
        crit = float(session.get("critical_bpm") or 0)
        curve = [float(x) for x in (session.get("curve") or [])
                 if isinstance(x, (int, float))]
        dur = float(session.get("duration_s") or 0)
        samples = int(session.get("samples") or 0)
    except (TypeError, ValueError):
        return None
    if (base <= 0 or crit <= 0 or dur < ZEN_MIN_DURATION_S
            or samples < ZEN_MIN_SAMPLES or len(curve) < 30):
        return None
    body = sorted(curve)
    if _percentile(body, ZEN_REG_QUANTILE) > base + ZEN_REG_MARGIN:
        return False
    if _percentile(body, ZEN_SPIKE_QUANTILE) > base + ZEN_SPIKE_MARGIN:
        return False
    if _rising_crossings(curve, crit) > ZEN_MAX_CRIT_CROSSINGS:
        return False
    return True


def _zen_eligible(sessions):
    """Ciste relacie (bez podozrivych/importovanych) s vyhodnotenim
    je_plne_zanshin, zoradene podla casu; None (nepocita sa) sa vynecha."""
    out = []
    for s in ciste_relacie(sessions):
        r = je_plne_zanshin(s)
        if r is None:
            continue
        out.append((s, r))
    out.sort(key=lambda sr: float(sr[0].get("started") or 0))
    return out


def zanshin_streak(sessions):
    """Stav serie - PREPOCITA sa z historie (nic sa neuklada, self-healing)."""
    elig = _zen_eligible(sessions)
    window = elig[-ZEN_WINDOW:]
    passed = sum(1 for _, r in window if r)
    current = bool(elig and elig[-1][1])
    return {"eligible": len(elig), "passed_in_window": passed,
            "current_pass": current, "streak": passed}


def zanshin_graduation(sessions, already_graduated=False):
    """Ma sa spustit promocia? Vracia dict s `fire` (raz) a `reason`.

    Poistky: spusti sa az pri >=ZEN_MIN_TOTAL cistych relaciach, rozpatych
    aspon ZEN_MIN_SPAN_DAYS dni, pri existujucej stabilnej zakladni, a len
    ked posledny vecer bol pokojny (kruh sa uzavrie po pokoji, nie po strese).
    """
    if already_graduated:
        return {"fire": False, "graduated": True, "reason": "already"}
    elig = _zen_eligible(sessions)
    if len(elig) < ZEN_MIN_TOTAL:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "need_more"}
    prvy = float(elig[0][0].get("started") or 0)
    posl = float(elig[-1][0].get("started") or 0)
    if (posl - prvy) < ZEN_MIN_SPAN_DAYS * 86400.0:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "too_soon"}
    if dlhodoba_zakladna(sessions) is None:
        return {"fire": False, "graduated": False,
                "eligible": len(elig), "reason": "no_baseline"}
    window = elig[-ZEN_WINDOW:]
    passed = sum(1 for _, r in window if r)
    current = bool(elig[-1][1])
    fire = passed >= ZEN_NEEDED and current
    return {"fire": fire, "graduated": False, "eligible": len(elig),
            "passed_in_window": passed, "reason": "fire" if fire else "not_yet"}

def zone_of_bpm(bpm, baseline, critical_bpm):
    """Pasmo jednej hodnoty tepu voci VLASTNEJ zakladne hraca.

    Jediny zdroj pravdy pre pasma: pouziva to sucet casu (`time_in_zones`)
    aj kazdy graf, ktory pas pasiem kresli (stopa relacie). Keby to kazdy
    pocital sam, pruh a cisla pod nim by si po case prestali sediet.
    """
    if bpm >= critical_bpm:
        return ZONE_CRITICAL
    if bpm >= baseline + 25:
        return ZONE_HIGH
    if bpm >= baseline + 10:
        return ZONE_RAISED
    return ZONE_CALM


def time_in_zones(samples, critical_bpm, baseline=None):
    """Sekundy v pasmach podla ODCHYLKY OD ZAKLADNE, nie podla zivej
    zataze (ta je vyhladeny stav a spatne sa neda zrekonstruovat).

    Pasma: calm < base+10, raised < base+25, high < critical, critical >=
    critical. Vysledok je slovnik {zona: sekundy}. Pouziva sa na dodatocny
    prepocet zo surovych vzoriek (napr. v testoch alebo pri importe);
    ziva relacia si pasma pocita priebezne z aktualnej zataze."""
    out = {ZONE_CALM: 0.0, ZONE_RAISED: 0.0, ZONE_HIGH: 0.0, ZONE_CRITICAL: 0.0}
    if not samples:
        return out
    base = baseline if baseline is not None else (session_baseline(samples) or min(b for _, b in samples))
    for (ts, bpm), dur in zip(samples, _durations(samples)):
        out[zone_of_bpm(bpm, base, critical_bpm)] += dur
    return out


def heart_rate_recovery(samples, recovery_s=60.0, min_prominence=15.0,
                        tolerance_s=5.0, peak_window_s=30.0, lookback_s=180.0):
    """Heart Rate Recovery: o kolko klesol tep 1 minutu po lokalnom vrchole.

    Vrati zoznam udalosti {peak_ts, peak_bpm, after_bpm, recovery} - jednu
    na kazdy vrchol, ktory:
      * je najvyssi v okne +-peak_window_s (lokalne maximum),
      * je aspon `min_prominence` BPM nad minimom predoslych `lookback_s`
        (kratky drobny zub v pokojnom tepe nie je "vrchol"),
      * ma vzorku priblizne recovery_s po sebe (tolerancia tolerance_s) -
        inak sa zotavenie neda zmerat a udalost sa vynecha.

    recovery = peak_bpm - after_bpm (zaporne = tep dalej stupal).
    Definicia: Cleveland Clinic - HRR je rozdiel tepu na vrchole a minutu po
    nom; bezne 12-23, trenovani 29+.
    """
    n = len(samples)
    events = []
    if n < 3:
        return events
    ts_list = [t for t, _ in samples]
    j0 = 0
    for i in range(n):
        ts, bpm = samples[i]
        # lokalne maximum v okne +-peak_window_s (prvy pri remize)
        is_peak = True
        k = i - 1
        while k >= 0 and ts - ts_list[k] <= peak_window_s:
            if samples[k][1] >= bpm:
                is_peak = False
                break
            k -= 1
        if not is_peak:
            continue
        k = i + 1
        while k < n and ts_list[k] - ts <= peak_window_s:
            if samples[k][1] > bpm:
                is_peak = False
                break
            k += 1
        if not is_peak:
            continue
        # prominencia voci minimu predoslych lookback_s
        while j0 < i and ts - ts_list[j0] > lookback_s:
            j0 += 1
        floor = min(b for _, b in samples[j0:i + 1])
        if bpm - floor < min_prominence:
            continue
        # vzorka ~recovery_s po vrchole
        target = ts + recovery_s
        best = None
        for m in range(i + 1, n):
            gap = ts_list[m] - target
            if gap > tolerance_s:
                break
            if abs(gap) <= tolerance_s and (best is None or abs(gap) < abs(ts_list[best] - target)):
                best = m
        if best is None:
            continue
        events.append({"peak_ts": ts, "peak_bpm": bpm, "after_bpm": samples[best][1],
                       "recovery": bpm - samples[best][1]})
    return events


def hrr_headline(events):
    """Jedno cislo pre UI: zotavenie po NAJVYSSOM vrchole relacie (tak sa
    HRR meria aj klinicky - po maximalnej zatazi). None bez udalosti."""
    if not events:
        return None
    top = max(events, key=lambda e: e["peak_bpm"])
    return int(round(top["recovery"]))


def persistence_index(samples):
    """Heart Rate Persistence Index (HRPI): najvacsie cele k take, ze tep
    bol aspon k BPM po dobu aspon k SEKUND (kumulativne, cas v sekundach
    podla rozostupov vzoriek, nie pocet vzoriek).

    Analogia h-indexu: relacia "120 BPM po 2 minuty" da k = 120, relacia
    "85 BPM po 3 hodiny" da k = 85. Jedno cislo spaja vysku aj trvanie.
    0 pre prazdne data.
    """
    if not samples:
        return 0
    pairs = sorted(zip((b for _, b in samples), _durations(samples)), reverse=True)
    cum = 0.0
    best = 0
    # prechadzame od najvyssieho tepu; cum = sekundy s tepom >= aktualny bpm
    idx = 0
    n = len(pairs)
    for k in range(int(pairs[0][0]), 0, -1):
        while idx < n and pairs[idx][0] >= k:
            cum += pairs[idx][1]
            idx += 1
        if cum >= k:
            best = k
            break
    return best


# Pod tymto casovym rozostupom (prva -> posledna relacia) nema regresny
# sklon zmysel - viz baseline_trend() nizsie.
MIN_TREND_SPAN_S = 2 * 86400.0  # 2 dni


def baseline_trend(sessions, min_span_s=MIN_TREND_SPAN_S):
    """Vyvoj pokojovej zakladne naprieC relaciami.

    Vrati {"points": [(started, baseline)], "first", "last", "delta",
    "slope_per_week", "insufficient_span"}; slope je linearna regresia
    zakladne voci casu (dni). Relacie bez baseline_bpm sa preskocia.

    Bug (opraveny tu): regresia cez body blizko seba v case davala
    nezmyselne hodnoty ako "-3009 BPM/tyzden" - dve relacie napr. 5 minut
    od seba maju takmer nulovy casovy rozptyl, cim sa aj maly rozdiel
    zakladne po vydeleni tymto rozptylom (a vynasobeni x7 na "za tyzden")
    vystreli do tisicok. Riesenie: ak je rozostup PRVEJ a POSLEDNEJ relacie
    mensi ako `min_span_s` (predvolene 2 dni), `slope_per_week` ostava 0.0
    a `insufficient_span=True` - UI ma vtedy ukazat "potrebujem viac dat",
    nie cislo. Pri >=2 dnoch je vypocet identicky ako predtym (existujuci
    test s reláciami po 1 dni naprieč tyzdnom musi dat rovnaky vysledok).
    """
    points = [(float(s.get("started", 0)), float(s["baseline_bpm"]))
              for s in sessions
              if isinstance(s, dict) and s.get("baseline_bpm")]
    points.sort()
    out = {"points": points, "first": None, "last": None, "delta": 0.0,
           "slope_per_week": 0.0, "insufficient_span": True}
    if not points:
        return out
    out["first"], out["last"] = points[0][1], points[-1][1]
    out["delta"] = points[-1][1] - points[0][1]
    span_s = points[-1][0] - points[0][0]
    out["insufficient_span"] = len(points) < 2 or span_s < min_span_s
    if not out["insufficient_span"]:
        xs = [(t - points[0][0]) / 86400.0 for t, _ in points]
        ys = [b for _, b in points]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        var = sum((x - mx) ** 2 for x in xs)
        if var > 0:
            slope_day = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
            out["slope_per_week"] = slope_day * 7.0
    return out


def count_sessions_since(sessions, since_ts):
    """Kolko relacii zacalo od `since_ts` (unix cas) a ich celkova dlzka.

    Pouziva to Dnes ("Relácie tento týždeň") - volajuci si sam vypocita
    zaciatok obdobia (napr. pondelok polnoc, viz period_start_ts), tato
    funkcia uz len filtruje a scita."""
    count, duration = 0, 0.0
    for s in sessions:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)) or started < since_ts:
            continue
        count += 1
        duration += float(s.get("duration_s") or 0.0)
    return count, duration


# --------------------------------------------------------------------------
# Co je pre TOHTO hraca bezne (graf, karty statistik, mriezka dni)
# --------------------------------------------------------------------------

def metric_series(sessions, field, n=8):
    """Poslednych `n` hodnot jedneho pola suhrnu, chronologicky.

    Na mikrograf pri cisle: "62 BPM" samo o sebe nehovori nic, "62 a za
    poslednych sedem relacii to klesalo" hovori vsetko. Relacie bez toho
    pola sa preskakuju (nie nulou - nula by krivku klamala).
    """
    ordered = sorted((s for s in sessions if isinstance(s, dict)
                      and isinstance(s.get("started"), (int, float))),
                     key=lambda s: s["started"])
    values = []
    for s in ordered:
        try:
            value = s.get(field)
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values[-n:] if n else values


def usual_range(values, lo_pct=0.25, hi_pct=0.75, min_values=4):
    """(p25, p75) - "tvoje bezne rozpatie" ako pas za grafom.

    Pod `min_values` hodnot None: kvartily z troch cisel su ozdoba, nie
    rozpatie. Zamerne percentily, nie priemer +- odchylka - jeden panicky
    vecer by rozpatie roztiahol na nezmysel.
    """
    vals = []
    for value in values or []:
        try:
            if value is not None:
                vals.append(float(value))
        except (TypeError, ValueError):
            continue
    if len(vals) < min_values:
        return None
    return _percentile(vals, lo_pct), _percentile(vals, hi_pct)


def day_activity(sessions, days=112, now=None):
    """Kalendarna mriezka: [{"date", "seconds", "count"}] za poslednych
    `days` dni vratane dneska, od najstarsieho.

    Dni BEZ relacie su v zozname tiez (s nulami) - prave diery su to, co
    na mriezke clovek cita, takze sa nesmu vynechat.
    """
    now_dt = datetime.fromtimestamp(now if now is not None else time.time())
    today = now_dt.date()
    first = today - timedelta(days=days - 1)
    cells = {first + timedelta(days=i): {"seconds": 0.0, "count": 0}
             for i in range(days)}
    for s in sessions or []:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)):
            continue
        cell = cells.get(datetime.fromtimestamp(started).date())
        if cell is None:
            continue
        cell["count"] += 1
        cell["seconds"] += float(s.get("duration_s") or 0.0)
    return [{"date": day, "seconds": cell["seconds"], "count": cell["count"]}
            for day, cell in sorted(cells.items())]


# POZN: tu bola `streaks()` - aktualna a najdlhsia seria dni po sebe.
# Vypadla zamerne, nie preto, ze by nefungovala. Seria je jedina vec v
# appke, ktora sa da PRETRHNUT, a appka ma upokojovat: najlepsia
# publikovana evidencia o seriach je nepriaznivá (bezci, ktori si seriu
# drzali, behali cez zranenia a opisovali to ako zavislost). Stranka
# Historia ukazuje namiesto toho pocet dni, v ktorych nejaka relacia
# bola - to iste "chodis na to", ale nic sa v nom neda stratit jednym
# vynechanym vecerom. Mriezka dni (`day_activity`) ostava.


# --------------------------------------------------------------------------
# Casove obdobia (Historia: Den / Tyzden / Mesiac / Rok)
# --------------------------------------------------------------------------

PERIOD_HOUR = "hour"
PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
PERIOD_YEAR = "year"
PERIODS = (PERIOD_DAY, PERIOD_WEEK, PERIOD_MONTH, PERIOD_YEAR)

# Do akych bucketov sa relacie zoskupuju v grafe PRE DANE zvolene obdobie -
# "mesiac" ukazuje denne priemery, "rok" mesacne (presne ako v zadani).
CHART_BUCKET_FOR_PERIOD = {
    PERIOD_DAY: PERIOD_HOUR,
    PERIOD_WEEK: PERIOD_DAY,
    PERIOD_MONTH: PERIOD_DAY,
    PERIOD_YEAR: PERIOD_MONTH,
}


def _period_floor(dt, period):
    if period == PERIOD_HOUR:
        return dt.replace(minute=0, second=0, microsecond=0)
    if period == PERIOD_DAY:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_WEEK:
        start = dt - timedelta(days=dt.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_MONTH:
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_YEAR:
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"neznamy period: {period}")


def period_start_ts(period, now=None):
    """Zaciatok AKTUALNEHO obdobia (napr. "tento tyzden" = pondelok 00:00)
    ako unix cas v miestnom case. `now` (unix cas) je pre testy."""
    dt = datetime.fromtimestamp(now if now is not None else time.time())
    return _period_floor(dt, period).timestamp()


PERIOD_SPAN_S = {
    PERIOD_DAY: 86400.0,
    PERIOD_WEEK: 7 * 86400.0,
    PERIOD_MONTH: 30 * 86400.0,
    PERIOD_YEAR: 365 * 86400.0,
}


def rolling_start_ts(period, now=None):
    """Zaciatok POSUVNEHO okna ("poslednych 7 dni"), nie kalendarneho
    obdobia.

    Graf trendu chce okno, kalendar mu skodi: v pondelok rano by "tento
    tyzden" (od polnoci) ukazal prazdny graf s hlaskou "V tomto období
    zatiaľ nič", hoci hrac hral cely vikend. Karta "Relácie tento týždeň"
    naopak kalendar naozaj chce - tam ma tyzden znamenat tyzden, a preto
    `period_start_ts` ostava a pouziva sa dalej.
    """
    now = float(now) if now is not None else time.time()
    return now - PERIOD_SPAN_S.get(period, 7 * 86400.0)


_BUCKET_LABEL_FMT = {
    PERIOD_HOUR: "%H:%M", PERIOD_DAY: "%d.%m", PERIOD_WEEK: "%d.%m",
    PERIOD_MONTH: "%m.%Y", PERIOD_YEAR: "%Y",
}


def aggregate_by_period(sessions, period):
    """Zoskupi relacie do bucketov podla kalendarneho obdobia (hour/day/
    week/month/year) a spriemeruje kluvove metriky v kazdom z nich.

    Vrati chronologicky zoradeny zoznam dictov {"started", "label",
    "count", "baseline", "hrr", "over_s", "peak"} - kazda metrika je
    priemer relacii v danom buckete, alebo None, ak ju ziadna relacia v
    buckete nema. Relacie bez `started` sa preskocia.
    """
    buckets = {}
    for s in sessions:
        if not isinstance(s, dict):
            continue
        started = s.get("started")
        if not isinstance(started, (int, float)):
            continue
        dt = datetime.fromtimestamp(started)
        floor = _period_floor(dt, period)
        key = floor.timestamp()
        b = buckets.get(key)
        if b is None:
            b = buckets[key] = {"label": floor.strftime(_BUCKET_LABEL_FMT[period]),
                               "count": 0, "baseline": [], "hrr": [], "over_s": [],
                               "peak": []}
        b["count"] += 1
        if s.get("baseline_bpm"):
            b["baseline"].append(float(s["baseline_bpm"]))
        if s.get("hrr_bpm") is not None:
            b["hrr"].append(float(s["hrr_bpm"]))
        if s.get("time_over_s") is not None:
            b["over_s"].append(float(s["time_over_s"]))
        if s.get("peak_stress") is not None:
            b["peak"].append(float(s["peak_stress"]))

    def avg(values):
        return sum(values) / len(values) if values else None

    return [
        {"started": key, "label": b["label"], "count": b["count"],
         "baseline": avg(b["baseline"]), "hrr": avg(b["hrr"]),
         "over_s": avg(b["over_s"]), "peak": avg(b["peak"])}
        for key, b in sorted(buckets.items())
    ]


def _period_next(dt, period):
    if period == PERIOD_HOUR:
        return dt + timedelta(hours=1)
    if period == PERIOD_DAY:
        return dt + timedelta(days=1)
    if period == PERIOD_WEEK:
        return dt + timedelta(days=7)
    if period == PERIOD_MONTH:
        return (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    if period == PERIOD_YEAR:
        return dt.replace(year=dt.year + 1)
    raise ValueError(f"neznamy period: {period}")


EMPTY_BUCKET_LIMIT = 400        # poistka proti nezmyselnemu rozsahu


def bucket_axis(buckets, period, start, end=None):
    """Doplni PRAZDNE buckety medzi `start` a `end`, aby bola os spojita.

    `aggregate_by_period` vyrobi bucket len pre obdobie, v ktorom nejaka
    relacia naozaj bola. Graf potom kreslil stredu hned vedla pondelka a
    utorok, v ktory sa nehralo, z osi zmizol - hoci prave pauza je
    informacia. Doplnene buckety maju count 0 a vsetky metriky None, cize
    sa v grafe nekreslia, ale miesto na osi zaberaju.
    """
    existujuce = {b["started"]: b for b in buckets}
    end = float(end) if end is not None else time.time()
    dt = _period_floor(datetime.fromtimestamp(start), period)
    posledny = _period_floor(datetime.fromtimestamp(end), period)
    out = []
    while dt <= posledny and len(out) < EMPTY_BUCKET_LIMIT:
        key = dt.timestamp()
        out.append(existujuce.get(key) or {
            "started": key, "label": dt.strftime(_BUCKET_LABEL_FMT[period]),
            "count": 0, "baseline": None, "hrr": None, "over_s": None,
            "peak": None})
        dt = _period_next(dt, period)
    return out


# Kym vybrany zdroj krokov posiela, ostatne sa ignoruju. Ked stichne na
# tolkoto sekund, smie ho vystriedat iny. Minuta je dost na to, aby to
# nepreskakovalo pri kazdom vypadku Wi-Fi, a malo na to, aby prepnutie
# zdroja v telefone nestalo hraca cely vecer bez detekcie pohybu.
PRELADENIE_ZDROJA_S = 60.0

# "Este som si zdroj nevybral" - odlisene od `None`, co je platny zdroj
# (UDP a hodinky, ktore meno zdroja neposielaju).
_NEURCENY = object()


class HeartStats:
    """Drzi historiu tepu a vsetko z nej odvodene.

    Trieda je cisto datova - nema Tk, nema I/O okrem ulozenia suhrnu
    relacie na konci. Vola sa VYHRADNE z GUI vlakna (z `_apply_hr_bpm`),
    takze nepotrebuje zamok.
    """

    def __init__(self, critical_bpm=110):
        self.critical_bpm = int(critical_bpm)
        self._samples = []          # [(timestamp, bpm)] za HISTORY_SECONDS
        self._long = []             # [(timestamp, bpm)] za BASELINE_SECONDS
        self.stress = 0.0
        self._raw_stress = 0.0
        # Pokojovy tep z PREDCHADZAJUCICH vecerov. Nastavuje ho appka pri
        # otvoreni relacie (`_open_hr_session`); je to vlastnost cloveka,
        # nie relacie, tak ju `reset_session` nemaze.
        self.long_baseline = None
        self.reset_session()

    # ---------- relacia ----------

    def reset_session(self):
        now = time.time()
        self.session_start = now
        self.session_min = None
        self.session_max = None
        self.session_sum = 0.0
        self.session_count = 0
        self.time_over = 0.0        # sekundy nad kritickou hranicou
        self.time_high = 0.0        # sekundy v zone high/critical
        self.triggers = 0
        self.auto_triggers = 0      # z toho kolko appka spustila sama (vysoky tep)
        self.peak_stress = 0.0
        self._last_ts = None
        self.last_bpm = None
        self.last_beat_ts = now
        # Najnizsia zakladna, aku sme v tejto relacii videli. Viz `baseline`.
        self._baseline_kotva = None
        # [(cas, prirastok krokov)] a [(cas, rychlost)] za poslednych 10 minut
        self._steps = []
        self._speed = []
        self._last_steps = None
        # Z ktoreho zdroja kroky beriem. Prvy, ktory nejake posle, vyhrava a
        # ostatne sa ignoruju - viz `note_metrics`.
        self._zdroj_krokov = _NEURCENY
        self._krok_naposledy = 0.0
        # [(cas, 0..1)] podiel casu so vstupom - plni to appka z
        # `activity.ActivityTracker`. Sluzi na odhad "kedy sa naozaj hralo".
        self._aktivita = []
        # cela relacia (pre HRR, HRPI, zakladnu relacie) - 1 vzorka/s,
        # aj 4-hodinova relacia je len ~15k dvojic
        self._all = []
        # Zataz v case, suberzne k `_all`. Do `_all` sa pridat neda - ten
        # ide do `persistence_index` aj `heart_rate_recovery`, ktore cakaju
        # dvojice (cas, bpm). Meracie okno ale chce aj "aka bola zataz
        # pred a po", a spatne sa dopocitat neda: je vyhladena
        # exponencialnym priemerom, takze zavisi od poradia, v akom
        # vzorky prichadzali.
        self._load = []
        self.zone_seconds = {ZONE_CALM: 0.0, ZONE_RAISED: 0.0,
                             ZONE_HIGH: 0.0, ZONE_CRITICAL: 0.0}
        self.trigger_offsets = []   # sekundy od zaciatku relacie
        # Hlasky s absolutnym casom a tym, ktora to bola. `trigger_offsets`
        # na meracie okna nestaci: je zaokruhleny na 0,1 s a pocita sa od
        # zapnutia senzora, nie od prvej vzorky.
        self.cues = []
        self._metric_cache = {}

    def note_trigger(self, ts=None, auto=False, category=None, cue_id=None,
                     arm="voice", source=None, delivery=None, delivered=True):
        """Zaznamena spustenu hlasku.

        `arm` je "voice" alebo "silent" - tiche kontrolne rameno pribudne
        vo faze 2, pole tu uz je, aby mali data z oboch faz rovnaky tvar.
        `source` rozlisuje, ci hlasku spustilo telo ("auto") alebo klavesa
        ("key"); klavesove spustace vo faze 3 zaniknu, dovtedy sa hodia na
        overenie, ze merania funguju.
        """
        self.triggers += 1
        if auto:
            self.auto_triggers += 1
        # `if ts` by na ts=0.0 ticho spadlo na time.time() - pri absolutnych
        # casoch je to nepravdepodobne, v testoch s vlastnymi hodinami nie.
        now = float(ts) if ts is not None else time.time()
        self.trigger_offsets.append(round(max(0.0, now - self.session_start), 1))
        self.cues.append({
            "ts": now,
            "category": category,
            "cue_id": cue_id,
            "arm": arm,
            "source": source if source is not None else ("auto" if auto else "key"),
            # "pause" / "timeout" - AKO sa to dorucilo. S `arm` sa to zlucit
            # nesmie (viz hlavicka `trigger.py`), ale zapisat sa to MUSI:
            # bez toho sa spatne neda zistit, ktore hlasky prisli na pauzu a
            # ktore az po 90 s ticho, a prah pauzy sa neda z dat overit.
            "delivery": delivery,
            # Vykreslil sa vizual naozaj? Tiche rameno ma vizual ako jediny
            # podnet - ked zlyhal, okno by meralo hlasku proti nicomu.
            # `measure` take okno zneplatni (bug B17). True/False, nie None:
            # stare zaznamy pole nemaju a `measure` ich necha platne.
            "delivered": bool(delivered),
        })

    # ---------- zber ----------

    def add(self, bpm, ts=None):
        """Prida jednu hodnotu tepu a prepocita vsetko odvodene."""
        try:
            bpm = float(bpm)
        except (TypeError, ValueError):
            return
        if not (25.0 <= bpm <= 250.0):
            return
        now = float(ts) if ts else time.time()

        # cas straveny v zone pripisujeme SPATNE za interval od poslednej
        # vzorky - inak by rychlejsie hodinky (2 Hz) nazbierali dvojnasobok
        if self._last_ts is not None:
            delta = max(0.0, min(5.0, now - self._last_ts))
            if self.last_bpm is not None and self.last_bpm > self.critical_bpm:
                self.time_over += delta
            if zone_for(self.stress) in (ZONE_HIGH, ZONE_CRITICAL):
                self.time_high += delta
            # Pasma sa pripisuju podla TEPU voci vlastnej zakladne - tou
            # istou funkciou, akou ich farbi pas v grafe (`zone_of_bpm`).
            # Predtym sa pocitali z vyhladenej zataze, ktora sa zo
            # ulozenych dat spatne zrekonstruovat neda: pas pasiem a cisla
            # pod nim by si tak nikdy presne nesadli. `time_high` ostava
            # zo zataze zamerne - to je ina otazka ("ako dlho ta to
            # tlacilo"), nie rozdelenie casu relacie.
            if self.last_bpm is not None:
                base = self.baseline
                if base is None:
                    base = min(b for _, b in self._long) if self._long else self.last_bpm
                self.zone_seconds[
                    zone_of_bpm(self.last_bpm, base, self.critical_bpm)] += delta
        self._last_ts = now

        self._samples.append((now, bpm))
        self._long.append((now, bpm))
        self._all.append((now, bpm))
        cutoff = now - HISTORY_SECONDS
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.pop(0)
        long_cutoff = now - BASELINE_SECONDS
        while self._long and self._long[0][0] < long_cutoff:
            self._long.pop(0)

        self.last_bpm = bpm
        self.last_beat_ts = now
        self.session_count += 1
        self.session_sum += bpm
        self.session_min = bpm if self.session_min is None else min(self.session_min, bpm)
        self.session_max = bpm if self.session_max is None else max(self.session_max, bpm)

        # Kroky sa pocitaju ZVLAST od tepu: sprava ich nemusi obsahovat.
        # Kotva zakladnej sa posuva LEN nadol a robi sa to tu, nie v
        # `baseline` - property so skrytym vedlajsim ucinkom je past pre
        # kazdeho, kto ju raz zavola "len na pozretie".
        if len(self._long) >= 30:
            ziva = _percentile([b for _, b in self._long], 0.20)
            if self._baseline_kotva is None or ziva < self._baseline_kotva:
                self._baseline_kotva = ziva

        self._recompute(now)
        self._load.append((now, self.stress))
        self.peak_stress = max(self.peak_stress, self.stress)

    def note_metrics(self, steps=None, speed=None, ts=None, zdroj=None):
        """Kroky a rychlost z hodiniek. Obe su volitelne.

        Drzi sa ROZDIEL krokov medzi spravami, nie ich absolutny pocet:
        hodinky posielaju kumulativny sucet za den a ten sam o sebe o pohybe
        prave teraz nehovori nic. Zaporny rozdiel (polnoc, restart appky na
        hodinkach) sa zahodi.

        `None` znamena "nevieme", nie "nula". Zamenit ich by znamenalo
        tvrdit, ze hrac sedi, vzdy ked hodinky kroky neposielaju - a prave
        na tom ma stat vyradzovanie okien.

        KROKY SA BERU LEN Z JEDNEHO ZDROJA.
        `zdroj` je meno OBS zdroja, z ktoreho sprava prisla. Appka na
        hodinkach vie pisat ten isty pocet krokov do viacerych zdrojov naraz
        (u zadavatela `Steps` aj `steps`). Rozdiel medzi dvoma pocitadlami
        nie je prejdena vzdialenost - je to ich vzajomne oneskorenie. Pri
        zaostavani o 5 krokov a styroch spravach za sekundu z toho vyslo 595
        krokov za minutu pri prahu 15, cize appka by uz nikdy nepovedala ani
        slovo.

        Prvy zdroj, ktory kroky posle, teda vyhrava a ostatne sa ticho
        preskakuju. Ked stichne na `PRELADENIE_ZDROJA_S`, prevezme to iny -
        inak by vypnuty zdroj umlcal kroky navzdy.
        """
        now = time.time() if ts is None else float(ts)
        if steps is not None:
            try:
                steps = int(steps)
            except (TypeError, ValueError):
                steps = None
        if steps is not None:
            if self._zdroj_krokov is _NEURCENY:
                self._zdroj_krokov = zdroj
            elif zdroj != self._zdroj_krokov:
                if now - self._krok_naposledy < PRELADENIE_ZDROJA_S:
                    steps = None            # duplikat z druheho pocitadla
                else:
                    # Povodny zdroj stichol. Preberie to tento, ale bez
                    # rozdielu - cudzie pocitadlo sa najprv len ukotvi.
                    self._zdroj_krokov = zdroj
                    self._last_steps = None
        if steps is not None:
            if self._last_steps is not None and steps >= self._last_steps:
                self._steps.append((now, steps - self._last_steps))
            self._last_steps = steps
            self._krok_naposledy = now
        if speed is not None:
            try:
                self._speed.append((now, float(speed)))
            except (TypeError, ValueError):
                pass
        cutoff = now - BASELINE_SECONDS
        while self._steps and self._steps[0][0] < cutoff:
            self._steps.pop(0)
        while self._speed and self._speed[0][0] < cutoff:
            self._speed.pop(0)

    def note_activity(self, aktivny, ts=None):
        """Jedno odmeranie aktivity: True/False, ci prave chodil vstup.

        Drzi sa cela relacia, nie klzave okno - krivka sa uklada do suhrnu
        a chceme ju za cely vecer. Pri sekundovom vzorkovani je to par
        desiatok tisic hodnot za dlhy vecer, cize zanedbatelne.
        """
        now = time.time() if ts is None else float(ts)
        self._aktivita.append((now, 1.0 if aktivny else 0.0))

    def activity_trace(self, points=CURVE_POINTS):
        """Krivka aktivity v rovnakom pocte bodov ako `trace()` pre tep.

        Kazdy bod je PODIEL aktivity v danom useku (0..1), nie hodnota v
        okamihu - inak by z toho bol nahodny sum jednotiek a nul namiesto
        toho, co nas zaujima: ako husto sa hralo.
        """
        if not self._aktivita:
            return []
        t0 = self._aktivita[0][0]
        t1 = self._aktivita[-1][0]
        if t1 <= t0:
            return []
        sirka = (t1 - t0) / float(points)
        sucty = [0.0] * points
        pocty = [0] * points
        for t, v in self._aktivita:
            i = min(points - 1, int((t - t0) / sirka))
            sucty[i] += v
            pocty[i] += 1
        return [round(sucty[i] / pocty[i], 3) if pocty[i] else None
                for i in range(points)]

    def steps_per_min(self, window_s=60.0, now=None):
        """Krokov za poslednu minutu, alebo None ked to nevieme.

        None znamena "nevieme", nie "nula". Ked hodinky kroky vobec
        neposielaju (`_last_steps is None`), alebo prestali posielat (posledna
        sprava starsia nez okno), je to NEZNAME - nie ze hrac stal na mieste
        (B32). Kym spravy chodia, aj nulovy prirastok je platna nula.
        """
        if self._last_steps is None:
            return None
        now = time.time() if now is None else float(now)
        if now - self._krok_naposledy > window_s:
            return None                 # kroky prestali chodit = nevieme
        v_okne = [d for t, d in self._steps if t >= now - window_s]
        if not v_okne:
            return 0.0
        return sum(v_okne) * (60.0 / window_s)

    def clear_live(self):
        """Senzor sa odpojil - krivka aj zataz idu prec, suhrn relacie ostava."""
        self._samples.clear()
        self.last_bpm = None
        self.stress = 0.0
        self._raw_stress = 0.0
        self._last_ts = None

    # ---------- odvodene hodnoty ----------

    @property
    def baseline(self):
        """Pokojova zakladna hraca. V ramci relacie sa smie uz len ZNIZOVAT.

        Kym nie je aspon 30 vzoriek, vraciame None: radsej nic, nez
        zakladnu spocitanu z 5 sekund panickeho tepu.

        PRECO KOTVA A NIE HOLY PERCENTIL
        Do 19. 9. to bol 20. percentil poslednych 10 minut, a nic viac. Znie
        to rozumne, ale ma to jeden dosledok, ktory appku rozbijal presne
        tam, kde mala byt najsilnejsia: ked tep drzi dlho hore, cele
        desatminutove okno je vysoke, zakladna sa zaň dotiahne - a
        `_recompute` pocita `over` aj `sustained` VOCI NEJ. Cim dlhsie stres
        trva, tym MENSIU zataz appka vidi.

        Odsimulovane nad tymto modulom: tep 115 BPM drzany celu hodinu pri
        critical_bpm=110 skoncil so zakladnou 114 a spickovou zatazou 21 -
        teda hlboko pod prahom 55. Nula hlasok za hodinu suvisleho stresu.
        Potvrdzuju to aj realne relacie v hr_sessions.json.

        Kotva to lieci bez toho, aby zaviedla cudzie cislo: zakladna je
        najnizsia hodnota, aku relacia videla. Ked sa hrac upokoji, klesne s
        nim; ked sa stresuje, ostane dole a zataz ma voci comu rast. Drift
        nahor zmizol, prisposobenie nadol ostalo.

        Nesie si to jedno obmedzenie a je poctive ho priznat: kto appku
        zapne az uprostred boja, ma prvu zakladnu privysoku - kym sa raz
        neupokoji. Preto sa kotva pocita z kazdej vzorky, nie raz na zaciatku.
        """
        values = [b for _, b in self._long]
        if len(values) < 30:
            return None
        ziva = _percentile(values, 0.20)
        kotva = self._baseline_kotva
        base = ziva if kotva is None else min(kotva, ziva)
        # Dlhodoba zakladna je STROP, nie nahrada: dnesny vecer smie ukazat,
        # ze je hrac pokojnejsi nez zvycajne, ale nie ze je "pokojny" na
        # 115 BPM len preto, ze tam drzi uz hodinu.
        if self.long_baseline:
            base = min(base, float(self.long_baseline))
        return base

    @property
    def zone(self):
        return zone_for(self.stress)

    @property
    def average(self):
        if not self.session_count:
            return None
        return self.session_sum / self.session_count

    def series(self, points=90):
        """Poslednych `points` hodnot pre krivku na HUD-e (stara -> nova)."""
        values = [b for _, b in self._samples]
        if len(values) <= points:
            return values
        # rovnomerne preriedenie, nie len orezanie - inak by krivka pri
        # rychlejsich hodinkach ukazovala kratsi casovy usek
        step = len(values) / float(points)
        return [values[int(i * step)] for i in range(points)]

    def trace(self, points=CURVE_POINTS):
        """Tvar CELEJ relacie (stara -> nova), preriedeny na `points`.

        `series()` je zive okno poslednych troch minut pre HUD; toto je
        cely vecer pre "stopu relacie" na stranke Dnes. Su to dve rozne
        otazky, preto dve metody.
        """
        return downsample([b for _, b in self._all], points)

    def beat_phase(self, now=None):
        """0..1 faza tepu - aby srdce na HUD-e bilo v realnom rytme."""
        if not self.last_bpm:
            return 0.0
        now = now or time.time()
        period = 60.0 / max(30.0, self.last_bpm)
        return ((now - self.last_beat_ts) % period) / period

    def _recompute(self, now):
        base = self.baseline
        if base is None:
            base = min(b for _, b in self._long) if self._long else self.last_bpm
        if not base:
            return

        headroom = max(12.0, float(self.critical_bpm) - base)
        over = (self.last_bpm - base) / headroom
        over = max(0.0, min(1.25, over))

        recent = [(t, b) for t, b in self._samples if t >= now - SLOPE_WINDOW_S]
        slope = 0.0
        if len(recent) >= 3:
            span = recent[-1][0] - recent[0][0]
            if span > 2.0:
                per_min = (recent[-1][1] - recent[0][1]) * 60.0 / span
                slope = max(0.0, min(1.0, per_min / 25.0))

        window = [(t, b) for t, b in self._samples if t >= now - SUSTAINED_WINDOW_S]
        sustained = 0.0
        if len(window) >= 5:
            above = sum(1 for _, b in window if b > base + 10.0)
            sustained = above / float(len(window))

        raw = 100.0 * min(1.0, 0.55 * over + 0.20 * slope + 0.25 * sustained)
        self._raw_stress = raw
        self.stress = self.stress + (raw - self.stress) * SMOOTHING

    # ---------- odvodene metriky celej relacie ----------

    def hrr_events(self):
        return heart_rate_recovery(self._all)

    def _cached(self, name, fn, every=30):
        """HRR/HRPI sa pytaju kazdu sekundu (stranka Dnes), ale pocitaju sa
        z celej relacie - pri 4 hodinach su to desiatky tisic vzoriek.
        Prepocitavame ich preto najviac raz za `every` novych vzoriek."""
        cache = getattr(self, "_metric_cache", None)
        if cache is None:
            cache = self._metric_cache = {}
        hit = cache.get(name)
        if hit is None or self.session_count - hit[0] >= every:
            hit = (self.session_count, fn())
            cache[name] = hit
        return hit[1]

    @property
    def hrr(self):
        """Zotavenie tepu po najvyssom vrchole relacie (BPM), None kym nie je."""
        return self._cached("hrr", lambda: hrr_headline(self.hrr_events()))

    @property
    def hrpi(self):
        return self._cached("hrpi", lambda: persistence_index(self._all))

    @property
    def session_baseline(self):
        return session_baseline(self._all)

    # ---------- suhrn ----------

    def summary(self):
        elapsed = max(0.0, time.time() - self.session_start)
        events = self.hrr_events()          # tu vzdy cerstvo, nie z cache
        base = self.session_baseline
        return {
            "started": self.session_start,
            "duration_s": round(elapsed, 1),
            "min_bpm": int(self.session_min) if self.session_min else None,
            "avg_bpm": int(round(self.average)) if self.average else None,
            "max_bpm": int(self.session_max) if self.session_max else None,
            "time_over_s": round(self.time_over, 1),
            "time_high_s": round(self.time_high, 1),
            "peak_stress": int(round(self.peak_stress)),
            "triggers": self.triggers,
            "auto_triggers": self.auto_triggers,
            "critical_bpm": self.critical_bpm,
            "samples": self.session_count,
            # nove metriky z cisteho BPM (viz hlavicka modulu)
            "baseline_bpm": int(round(base)) if base else None,
            "zone_seconds": {z: round(s, 1) for z, s in self.zone_seconds.items()},
            "hrr_bpm": hrr_headline(events),
            "hrr_events": len(events),
            "hrpi": persistence_index(self._all),
            "trigger_offsets_s": list(self.trigger_offsets),
            # Tvar relacie - 120 cisel (~0,5 kB). Bez neho sa relacia v
            # historii da uz len precitat ako riadok tabulky; s nim sa da
            # POZRIET. Pasma sa z krivky dopocitaju az pri kresleni, cez
            # `baseline_bpm` a `critical_bpm` vyssie - ukladat ich znova by
            # bolo to iste cislo dvakrat.
            "curve": [int(round(b)) for b in self.trace()],
            # Krivka aktivity vedla krivky tepu - z nej sa da spatne
            # zistit, kedy sa naozaj hralo a kedy sa sedelo v menu.
            # Prah sa z nej spocita, ked bude z coho (viz `PRAH_HRANIA`).
            "activity_curve": self.activity_trace(),
        }


# --------------------------------------------------------------------------
# Ulozenie historie relacii
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Kontext relacie
# --------------------------------------------------------------------------

# Co sa pri relacii dialo. NIE je to o pocitoch - je to na CISTENIE DAT.
#
# Rozpravanie je najhorsi konfunder v tomto merani: ked hovoris, meni sa
# dych a tep ide hore. Hlaska, ktora do toho zaznie, vyzera neucinne, hoci
# s tym nema nic spolocne. Smiech rovnako. Grind naopak drzi tep plocho
# cele hodiny.
#
# Id su ANGLICKE a NEPREKLADAJU sa - id ide do datoveho suboru a musi
# prezit zmenu jazyka rozhrania, rovnako ako kluce SFX sad a kategorie
# hlasok. Preklada sa az popisok v UI (`session.context.<id>`).
# Co sa dialo POCAS hrania.
CONTEXT_DIANIE = ("call", "laugh", "grind", "competitive", "chill")

# Co mal hrac V SEBE. Oddelene zamerne: prve su udalosti behom vecera,
# druhe je stav, v ktorom vecer zacal - a posuvaju uplne ine veci.
#
# PRECO TO VOBEC JE: kofein, alkohol ci nikotin pred hranim mozu posunut
# pokojovu zakladnu nad beznu hodnotu.
# V datach o tom nebolo NIC. Keby sa takto nazbieralo tridsat vecerov,
# rozptyl by sa nedal vysvetlit a nedal by sa ani odpocitat.
#
# Zadanie 2.1b, B2: "kazda premenna, ktora vysvetluje rozptyl, znizuje n."
# Stimulanty su pravdepodobne najvacsi vysvetlitelny zdroj rozptylu v tomto
# meraní - vacsi nez rozpravanie, kvoli ktoremu cely dialog vznikol.
# `supplement` je zamerne vseobecny, nie nazov znacky: appka ide do deviatich
# jazykov a konkretny pre-workout by inde nikomu nic nepovedal. Pre data je
# podstatne, ze islo o stimulant, nie ktory.
# `food` je tu preto, ze trávenie samo dvíha tep - jedlo tesne pred hranim
# posunie zakladnu aj bez akehokolvek stresu.
# `illness` a `exercise_before` pribudli z vyskumu 2026-09-22 ako CONFOUNDERY
# pokojovej zakladne (infekcia dvíha pokoj +10-20 bpm na dni; pohyb tesne pred
# hranim usadzuje tep 10-30 min a nastavi kotvu privysoko). `tired` odislo -
# nahradil ho jemnejsi `sleep` (3 urovne, viz normalize_sleep).
CONTEXT_TELO = ("caffeine", "supplement", "alcohol", "nicotine", "food",
                "illness", "exercise_before")

CONTEXT_IDS = CONTEXT_DIANIE + CONTEXT_TELO


def normalize_context(raw):
    """Zoznam platnych id kontextu, v pevnom poradi, bez duplikatov.

    None znamena nieco ine nez prazdny zoznam: None = hrac sa este
    nevyjadril, [] = vyslovne povedal "nic z toho". Preto sa None
    nezamiena za [].
    """
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return None
    vybrane = {c for c in raw if c in CONTEXT_IDS}
    return [c for c in CONTEXT_IDS if c in vybrane]


# Cinnost, pri ktorej relacia vznikla. Self-report v dotazniku: len hrac vie,
# ci pri PC hral alebo pracoval. NIE je to confounder, ktory by sa "odpocital"
# - je to iny DRUH vecera. Zbierame realny udaj; ci sa praca a hra lisia, sa
# rozhodne z DAT, nie dohadom (ziadne oddelene prahy, kym na to nie su cisla).
ACTIVITY_KINDS = ("play", "work")


def normalize_activity(raw):
    """'play' / 'work' / None (hrac sa nevyjadril). Ine hodnoty -> None."""
    return raw if raw in ACTIVITY_KINDS else None


# Vlastna poznamka hraca k veceru. Volny text, bez interpretacie - appka ju
# len drzi a ukaze. Strop dlzky, aby jeden zaznam nenafukol subor.
NOTE_MAX = 280


def normalize_note(raw):
    """Orezany volny text, alebo None. Prazdny/nezmyselny vstup -> None."""
    if not isinstance(raw, str):
        return None
    txt = raw.strip()
    if not txt:
        return None
    return txt[:NOTE_MAX]


# --------------------------------------------------------------------------
# SUBJEKTIVNA VRSTVA (vyskum 2026-09-22): to, co TEP NEVIDI.
# Aktivacia (tep) a valencia (dobre/zle) su dve NEZAVISLE osi. Hlavna
# evaluacna metrika je ROZCHOD merane x citene - preto sa subjektivne osi
# drzia ako ordinalne id (ako CONTEXT_IDS, prezije 9 jazykov), nie volny text.
# Vsade plati None != "nevybrate" - None = hrac sa nevyjadril.
# --------------------------------------------------------------------------

# Spanok minulu noc - nahradza binarne 'tired'. 3 urovne alebo None.
SLEEP_LEVELS = ("rested", "mid", "broken")


def normalize_sleep(raw):
    """'rested'/'mid'/'broken' alebo None. Ine hodnoty -> None."""
    return raw if raw in SLEEP_LEVELS else None


def normalize_felt_load(raw):
    """Vnimana zataz 0-10 (hracova vlastna znamka), alebo None."""
    try:
        v = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return max(0, min(10, v))


def normalize_valence(raw):
    """Valencia -2..+2 (zle .. dobre), alebo None."""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    return v if -2 <= v <= 2 else None


# Telo pocas spicky - ZAZITKOVE dlazdice, viacvyber. NIE symptomovy skrining
# (ziadna zavaznost, ziadne trvanie, ziadny kardialny termin) - ramcuje sa
# "ako to bolo v tele", nie "mal si nevolnost?". Id anglicke kvoli 9 jazykom.
BODY_PEAK_IDS = ("ok", "flow", "wired", "tense", "sick")


def normalize_body_peak(raw):
    """Zoznam platnych id v pevnom poradi, alebo None (nevyjadril sa)."""
    if raw is None or not isinstance(raw, (list, tuple, set)):
        return None
    vybrane = {c for c in raw if c in BODY_PEAK_IDS}
    return [c for c in BODY_PEAK_IDS if c in vybrane]


# Verdikt o hlaske - priama kontrola, ci cue robi spravnu vec. landed/unneeded/
# disruptive ked cue ZAZNEL; missed = "bola chvila, ked mala a mlcala". None =
# nevyjadril sa / neaplikovatelne.
CUE_VERDICTS = ("landed", "unneeded", "disruptive", "missed")


def normalize_cue_verdict(raw):
    """Jeden z CUE_VERDICTS alebo None."""
    return raw if raw in CUE_VERDICTS else None


# CONFOUNDED relacia: fyziologicky tak skreslena, ze by otravila POKOJOVU
# ZAKLADNU (menovatel vsetkeho). NEMAZE sa - ostava v historii aj v
# subjektivnej analyze, len NEVSTUPUJE do percentilovych pool-ov (zakladna/
# kriticky/prah). Rozhodnute vyskumom 2026-09-22: alkohol (dvíha pokoj aj na
# druhy den), choroba, fyzicka namaha tesne pred hranim.
CONFOUND_TAGS = ("alcohol", "illness", "exercise_before")


def je_confounded(session):
    """True, ked sa z relacie NESMIE ucit pokojova zakladna."""
    if not isinstance(session, dict):
        return True
    ctx = session.get("context") or []
    return any(t in ctx for t in CONFOUND_TAGS)


def attach_context(path, started, context, activity=None, note=None,
                   sleep=None, felt_load=None, valence=None, body_peak=None,
                   cue_verdict=None, log=None):
    """Doplni kontext k uz ulozenej relacii. Vracia True pri uspechu.

    Relacia sa uklada pri zatvoreni, dotaznik sa pyta az potom - preto sa
    zaznam dohladava podla `started`. Kazdy pripad, ked sa kontext neulozi,
    sa ZAPISE cez `log` (ak je dany): kontext je najvacsi vysvetlitelny zdroj
    rozptylu v merani a stratit ho potichu je presne to, comu sa appka
    vyhyba. Volajuci (`app.save_session_context`) navratovu hodnotu cita a
    pri False to povie hracovi (bug B16).
    """
    try:
        if not os.path.exists(path):
            if log:
                log("kontext: súbor relácií neexistuje")
            return False
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            if log:
                log("kontext: súbor relácií nie je zoznam")
            return False
        zmenene = False
        for s in data:
            if isinstance(s, dict) and s.get("started") == started:
                s["context"] = normalize_context(context)
                # Cinnost (hral/pracoval) a volna poznamka. Ukladaju sa len ked
                # ich hrac zadal: None = nevyjadril sa, nechavame stary stav.
                # Prazdna poznamka ("") je vyslovny pokyn zmazat pripadnu starsiu.
                akt = normalize_activity(activity)
                if akt is not None:
                    s["activity"] = akt
                pozn = normalize_note(note)
                if pozn is not None:
                    s["note"] = pozn
                elif isinstance(note, str):
                    s.pop("note", None)
                # Subjektivna vrstva (spanok, vnimana zataz, valencia, telo,
                # verdikt o hlaske). Uklada sa len ked hrac zadal (None = necham).
                for kluc, hodnota, norm in (
                        ("sleep", sleep, normalize_sleep),
                        ("felt_load", felt_load, normalize_felt_load),
                        ("valence", valence, normalize_valence),
                        ("body_peak", body_peak, normalize_body_peak),
                        ("cue_verdict", cue_verdict, normalize_cue_verdict)):
                    nova = norm(hodnota)
                    if nova is not None:
                        s[kluc] = nova
                zmenene = True
                break
        if not zmenene:
            # Dialóg sa otvára AŽ po úspešnom uložení relácie, takže keď sa
            # tu relácia nenájde, je to reálna strata (rotácia MAX_SESSIONS,
            # nesúhlas `started`), nie neškodný prípad krátkej relácie.
            if log:
                log("kontext: relácia sa v súbore nenašla (started=%s)" % (started,))
            return False
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        if log:
            log(f"kontext relacie sa nepodarilo ulozit: {exc}")
        return False


# Kolko relacii drzime. Bolo 60 - pri dennom hrani dva mesiace, hoci
# stranka Historia ponuka obdobie "Rok"; rocny graf tak ukazoval vysek a
# tvaril sa ako cely rok. Pri ~0,9 kB na relaciu (aj s krivkou) je 400
# relacii asi 350 kB JSON - za rok denneho hrania to vyjde.
MAX_SESSIONS = 400


def save_session(path, summary, log=None):
    """Prida suhrn relacie do JSON suboru (drzime poslednych MAX_SESSIONS).

    Relacie kratsie ako minuta alebo bez jedinej vzorky sa zahadzuju -
    zapnut a hned vypnut senzor nie je "relacia" a len by to zasumilo
    priemery v prehlade.
    """
    if not summary or summary.get("samples", 0) < 10 or summary.get("duration_s", 0) < 60:
        return False
    try:
        data = []
        if os.path.exists(path):
            citatelne = None
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    obsah = json.load(fh)
                if isinstance(obsah, list):
                    citatelne = obsah
            except Exception as exc:
                if log:
                    log(f"HR: história sa nedala prečítať: {exc}")
            if citatelne is not None:
                data = citatelne
            else:
                # EXISTUJÚCI SÚBOR JE POKAZENÝ (nečitateľný alebo nie zoznam).
                #
                # Prepísať ho novou reláciou by NAVŽDY zahodilo všetky
                # predošlé večery - a odvtedy by sa každý ďalší stratil
                # rovnako ticho (bug B15). Radšej ho odložíme bokom pod
                # `.corrupt-<čas>`, nech sa dá zachrániť, a v ukladaní
                # pokračujeme s prázdnym zoznamom.
                try:
                    os.replace(path, "%s.corrupt-%d" % (path, int(time.time())))
                    if log:
                        log("HR: pokazený súbor histórie odložený na záchranu")
                except OSError:
                    pass
        data.append(summary)
        data = data[-MAX_SESSIONS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        if log:
            log(f"HR: session log failed: {exc}")
        return False


# --------------------------------------------------------------------------
# Export do tabulky
# --------------------------------------------------------------------------

# PRECO CSV A NIE .xlsx
# Excel otvori CSV dvojklikom rovnako ako vlastny format, takze pre hraca
# je to to iste - ale appka na to nepotrebuje ziadnu kniznicu navyse, a
# teda ani nic naviac v builde (openpyxl je ~2 MB a dalsi diel, ktory sa
# moze v zabalenej appke pokazit). Dve veci to ale potrebuje, inak to
# Excel v strednej Europe otvori ako jeden stlpec:
#   * oddelovac BODKOCIARKA (v lokalizacii s desatinnou ciarkou je to on),
#   * BOM na zaciatku, inak Excel precita subor ako ANSI a zmrsi diakritiku.
CSV_SEPARATOR = ";"
CSV_COLUMNS = ("date", "start", "duration_min", "avg_bpm", "min_bpm", "max_bpm",
               "baseline_bpm", "over_min", "breathing", "peak_stress",
               "hrr_bpm", "hrpi", "calm_min", "raised_min", "high_min",
               "critical_min",
               # PRECO SA (NE)OZVALA. Bez tychto stlpcov je "0 hlasok" len
               # konstatovanie: nedalo by sa rozlisit "telo nebolo hore" od
               # "bolo, ale nie dost dlho" a od "vypadaval tep".
               "longest_above_s", "above_runs", "cancelled_dip",
               "cancelled_gap", "hold_s",
               # Co hrac o veceri povedal (kofein, alkohol, hovor...).
               # Najvacsi vysvetlitelny zdroj rozptylu v celom meraní.
               "context",
               # Cinnost (hral/pracoval), kolko % relacie bol HUD viditelny
               # (biofeedback - videny tep sa podvedome reguluje) a volna
               # poznamka hraca. Realne data k rozlisovaniu vecerov, nie dohady.
               "activity", "hud_seen", "note",
               # Subjektivna vrstva (vyskum 2026-09-22): spanok, vnimana zataz
               # 0-10, valencia, telo pocas spicky, verdikt o hlaske. Hlavna
               # evaluacia = ROZCHOD merane (tep) x citene (tieto). `confounded`
               # = ci sa relacia NEucila do zakladne (alkohol/choroba/namaha).
               "sleep", "felt_load", "valence", "body_peak", "cue_verdict",
               "confounded")


def _csv_cell(value, decimals=1):
    """Cislo s desatinnou CIARKOU (Excel v SK/CZ inak vidi text), prazdno
    pre chybajucu hodnotu."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",")
    return str(value)


def _csv_context(ctx):
    """Kontext relacie do bunky. Rozlisuje tri stavy (B20):

      None -> hrac sa nevyjadril  (prazdno)
      []   -> "nic z toho sa nedialo"  (pomlcka)
      [..] -> vymenovane polozky
    """
    if ctx is None:
        return ""
    if not ctx:
        return "-"
    return " ".join(ctx)


def _csv_hud_seen(summary):
    """Kolko % relacie bol HUD viditelny, alebo prazdno (stara relacia to
    cislo nema). Cele percento - v CSV sa cita lahsie nez zlomok."""
    frac = summary.get("hud_visible_frac")
    if frac is None:
        return ""
    try:
        return f"{round(float(frac) * 100)}%"
    except (TypeError, ValueError):
        return ""


def _csv_note(note):
    """Volna poznamka do bunky. `;` je oddelovac stlpcov a novy riadok rozbije
    riadok CSV - oboje sa nahradi, aby jedna poznamka nerozhodila tabulku."""
    if not note:
        return ""
    return str(note).replace(";", ",").replace("\n", " ").replace("\r", " ")


def session_row(summary):
    """Jedna relacia ako zoznam buniek v poradi `CSV_COLUMNS`."""
    started = summary.get("started")
    when = datetime.fromtimestamp(started) if started else None
    zones = summary.get("zone_seconds") or {}

    def minutes(seconds):
        try:
            return float(seconds or 0.0) / 60.0
        except (TypeError, ValueError):
            return 0.0

    return [
        when.strftime("%d.%m.%Y") if when else "",
        when.strftime("%H:%M") if when else "",
        _csv_cell(minutes(summary.get("duration_s"))),
        _csv_cell(summary.get("avg_bpm")),
        _csv_cell(summary.get("min_bpm")),
        _csv_cell(summary.get("max_bpm")),
        _csv_cell(summary.get("baseline_bpm")),
        _csv_cell(minutes(summary.get("time_over_s"))),
        _csv_cell(summary.get("auto_triggers", summary.get("triggers"))),
        _csv_cell(summary.get("peak_stress")),
        _csv_cell(summary.get("hrr_bpm")),
        _csv_cell(summary.get("hrpi")),
        _csv_cell(minutes(zones.get(ZONE_CALM))),
        _csv_cell(minutes(zones.get(ZONE_RAISED))),
        _csv_cell(minutes(zones.get(ZONE_HIGH))),
        _csv_cell(minutes(zones.get(ZONE_CRITICAL))),
        _csv_cell(summary.get("longest_above_s")),
        _csv_cell(summary.get("above_runs")),
        _csv_cell(summary.get("runs_cancelled_dip")),
        _csv_cell(summary.get("runs_cancelled_gap")),
        _csv_cell(summary.get("stress_hold_s")),
        # None = hráč sa nevyjadril, [] = "nič z toho" - dve rôzne veci, inde
        # ich chráni vlastný test. CSV ich zlievalo do prázdnej bunky (B20).
        _csv_context(summary.get("context")),
        # Cez normalize_activity: zaruci retazec ('play'/'work'/''), takze
        # ani cislo/nezmysel z importovanej ci rucne upravenej relacie
        # nezhodi CELY export (ako jedina bunka tu inak nesla cez sanitizer).
        normalize_activity(summary.get("activity")) or "",
        _csv_hud_seen(summary),
        _csv_note(summary.get("note")),
        # Subjektivna vrstva - vsetko cez normalizatory, aby zly import
        # nezhodil export (rovnaka poistka ako pri activity).
        normalize_sleep(summary.get("sleep")) or "",
        _csv_cell(normalize_felt_load(summary.get("felt_load"))),
        _csv_cell(normalize_valence(summary.get("valence"))),
        _csv_context(normalize_body_peak(summary.get("body_peak"))),
        normalize_cue_verdict(summary.get("cue_verdict")) or "",
        "áno" if je_confounded(summary) else "",
    ]


def export_sessions_csv(sessions, path, headers=None):
    """Zapise relacie do CSV pre Excel. Vrati pocet zapisanych riadkov.

    `headers` su prelozene nazvy stlpcov v poradi `CSV_COLUMNS`; bez nich
    sa pouziju anglicke kluce (modul neriesi preklady).
    """
    rows = sorted((s for s in sessions or [] if isinstance(s, dict)),
                  key=lambda s: float(s.get("started") or 0))
    names = list(headers) if headers else list(CSV_COLUMNS)
    lines = [CSV_SEPARATOR.join(names)]
    for summary in rows:
        lines.append(CSV_SEPARATOR.join(session_row(summary)))
    tmp = path + ".tmp"
    # utf-8-sig = UTF-8 s BOM; bez neho Excel zjedol diakritiku
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("\r\n".join(lines) + "\r\n")
    os.replace(tmp, path)
    return len(rows)


def load_sessions(path, log=None):
    # "Súbor neexistuje" = hráč ešte nič nenameral, to je v poriadku a ticho.
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if log:
            log("HR: súbor histórie nie je zoznam")
    except Exception as exc:
        # POZOR: prázdny zoznam tu znamená "NEDALO SA PREČÍTAŤ", nie "žiadne
        # relácie". Bez záznamu by História tvrdila, že si nič nenameral,
        # hoci súbor s mesiacmi dát leží vedľa (bug B15). `save_session` pri
        # najbližšej relácii pokazený súbor odloží bokom a začne čistý.
        if log:
            log(f"HR: história sa nedala prečítať: {exc}")
    return []
