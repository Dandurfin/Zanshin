"""Meracie okna okolo hlasky - co sa dialo s telom pred nou a po nej.

PRECO TO EXISTUJE
-----------------
Bez merania sa neda povedat, ci hlaska nieco robi. A meria sa to zle
velmi lahko: hlaska sa spusta prave vtedy, ked je tep hore, a tep sa
vracia dole aj sam od seba. Ked sa teda porovna "pred" a "po" bez
kontroly, vyjde "funguje" vzdy - aj keby appka mlcala. Preto sa kazde
okno zapisuje s ramenom (`arm`), aby sa tiche rameno dalo porovnat s
hlasnym. Tiche rameno je uz ZIVE (losuje ho `trigger.CueTrigger`): cast
natiahnuti sa zamerne nedoruci hlasom, len vizualom, a meria sa rovnako -
inak by "funguje" vyslo vzdy.

TVAR OKNA
---------
    -60 s          0        +10 s              +70 s        +180 s
      |----pre----|hlaska|--mrtvy cas--|----post----|--trvacnost--|

Mrtvy cas +10 s je tam preto, aby sa do "po" nedostal este dobiehajuci
stav z momentu hlasky - aspon jeden cely dychovy cyklus.

CO OKNO ZNEPLATNI
-----------------
  * refraktérna zona - ak v rozsahu -60/+180 s zaznela ina hlaska,
    nedá sa povedat, ktora z nich co sposobila
  * diera v datach - senzor vypadol; `HeartStats.clear_live()` vycisti
    len zivu krivku, `_all` rastie dalej, takze diera NIE JE nicim
    oznacena a da sa najst jedine z rozdielov casovych znaciek
  * skratene okno - hlaska padla skor nez 60 s od zaciatku relacie,
    alebo relacia skoncila skor nez uplynulo +180 s

Neplatne okno sa ZAPISE, nezahodi - s dovodom v `reasons`. Prve vecery
bude dolezitejsie vidiet, kolko okien padlo a preco, nez mat cisty
subor. Filtruje sa az pri analyze (`valid=True`).

Modul je cisto datovy: ziadny Tk, ziadne I/O okrem ulozenia na konci,
rovnako ako `hr_stats.py`. Vsetky vypocty su ciste funkcie nad
`[(timestamp, hodnota)]`, takze sa daju testovat bez displeja.
"""

import json
import os

# --------------------------------------------------------------------------
# Rozmery okna (sekundy). Vychodiskove hodnoty su z literatury, nie z tela
# konkretneho hraca - prve vecery sa budu ladit, preto su na jednom mieste.
# --------------------------------------------------------------------------

PRE_S = 60.0                 # -60 .. 0
DEAD_S = 10.0                # 0 .. +10   mrtvy cas (jeden dychovy cyklus)
POST_S = 70.0                # +10 .. +70
DURABILITY_S = 180.0         # +70 .. +180 (volitelne)

REFRACTORY_BEFORE_S = 60.0
REFRACTORY_AFTER_S = 180.0

# Dlhsia diera medzi vzorkami = vypadok senzora. ROVNAKE CISLO ako
# `trigger.DIERA_S` (= `heart_rate.HeartRateMonitor.STALE_AFTER_S`, 12 s) -
# test to strazi. Neimportuje sa: `trigger` importuje `measure`.
#
# Predtym tu bolo 5 s (ako `hr_stats.MAX_SAMPLE_GAP_S`, co je ale strop
# KREDITU za jednu medzeru, nie hranica vypadku). Hodinky od 20. 9. posielaju
# tep po ~2,9 s a jeden strateny paket je medzera ~5,6 s - takze skoro kazde
# meracie okno dostalo `diera_v_datach`, hoci appka ani spustac to za vypadok
# nepovazuju a HUD celu dobu ukazoval tep.
MAX_GAP_S = 12.0

# Pod tolko milisekund od posledneho vstupu povazujeme hraca za aktivneho.
ACTIVE_IDLE_MS = 1000

# Kategorie hlasok. Su to tie iste styri somaticke vizualy, ktore appka
# kresli do hry (`hud_paint.render_slot_icon`) a ktore zodpovedaju slotom
# 0-3. Mena su anglicke a NEPREKLADAJU sa - id kategorie ide do datoveho
# suboru a musi prezit zmenu jazyka rozhrania, rovnako ako kluce SFX sad.
CATEGORIES = ("grounding", "jaw", "release", "breath")


def next_slot(available, last=None):
    """Ktory slot ma zaznniet teraz. Vracia index alebo None.

    PRECO STRIEDANIE
    ----------------
    Do 18. 9. hrala appka VZDY jeden pevny slot (dychovy). Ma to jednu
    silnu vlastnost - vsetky meracie okna su z jednej kategorie, takze sa
    daju porovnavat bez dalsej premennej - a jednu fatalnu: rovnaka veta
    stokrat za vecer prestane fungovat. Habituacia je presne to, proti
    comu cela appka stoji.

    PRECO KOLO-DOKOLA A NIE NAHODA
    ------------------------------
    Nahodny vyber by tu istu kategoriu obcas zopakoval trikrat po sebe a
    inu by za vecer nepustil vobec. Striedanie v kruhu drzi kategorie
    ROVNOMERNE zastupene, co je zaroven to, co potrebuje analyza: kazda
    ma podobny pocet okien.

    CO TO STOJI
    -----------
    Okna uz nie su z jednej kategorie, takze do odhadu ucinku pribudne
    rozptyl medzi kategoriami. Nie je to ale strata: kategoria sa do okna
    zapisuje (`category_for_slot`), takze faza 8 bude mat data na to, aby
    ich rozdelila - a zbiera ich od DNES, nie az odvtedy, co sa faza 8
    otvori.

    `available` su indexy ZAPNUTYCH slotov. Ked je zapnuty jediny, vrati sa
    on - opakovaniu sa vtedy vyhnut neda.
    """
    zoznam = sorted({int(i) for i in (available or [])})
    if not zoznam:
        return None
    if last is None or int(last) not in zoznam:
        return zoznam[0]
    kde = zoznam.index(int(last))
    return zoznam[(kde + 1) % len(zoznam)]


def category_for_slot(index):
    """Kategoria pre slot 0-3, alebo None pre cokolvek ine."""
    try:
        index = int(index)
    except (TypeError, ValueError):
        return None
    return CATEGORIES[index] if 0 <= index < len(CATEGORIES) else None


# Dovody, preco okno nie je platne.
# Podiel casu so vstupom z klavesnice/mysi, pod ktorym okno neplati.
#
# `pre_activity` a `post_activity` sa zapisovali od zaciatku, ale na platnost
# okna nemali vplyv - a to bola diera. Ked hrac vstane a odide si po kavu,
# tep mu stupne CHODZOU, nie hrou: appka to vidi ako zataz, ozve sa, a po
# navrate a sadnuti si tep klesne. Take okno vyzera ako ucinna hlaska,
# pritom nemeria nic ine nez to, ze si clovek sadol.
#
# 0,25 je zamerne nizko: mikropauza pri stole podiel takmer nezmeni (okna su
# 60 s pred a 180 s po), kym odchod od PC ho zrazi k nule.
MIN_AKTIVITA = 0.25

R_NEAKTIVNY = "nebol_pri_klavesnici"
R_REFRACTORY = "refraktern_zona"
R_GAP = "diera_v_datach"
R_PRE_SHORT = "skratene_pred"
R_POST_SHORT = "skratene_po"
R_NO_DATA = "ziadne_data"
# Vizuál sa nevykreslil (jediný podnet tichého ramena). Okno by meralo
# hlášku proti ničomu, tak ho vylúčime (bug B17).
R_NEDORUCENE = "nedorucene"


# --------------------------------------------------------------------------
# Ciste vypocty nad [(timestamp, hodnota)]
# --------------------------------------------------------------------------

def slice_span(series, t0, t1):
    """Vzorky s casom v <t0, t1) - zaciatok patri dnu, koniec uz nie.

    Polootvorene zamerne, z dvoch dovodov:

      * vzorka presne v momente hlasky nepatri ani do "pred", ani do "po" -
        je to okamih zasahu. Pri pred-okne <-60, 0> by inak natiekla dnu a
        priemer by tahala prave tym cislom, ktore hlasku vyvolalo,
      * po-okno konci tam, kde zacina trvacnost (+70 s). Pri uzavretych
        intervaloch by sa vzorka na hranici zapocitala dvakrat.

    Predpoklada rastuce casy.
    """
    return [(ts, v) for ts, v in series if t0 <= ts < t1]


def mean_in(series, t0, t1):
    """Priemer hodnot v intervale, alebo None ked tam nic nie je."""
    values = [v for _, v in slice_span(series, t0, t1)]
    if not values:
        return None
    return sum(values) / float(len(values))


def gaps(series, t0, t1):
    """(diera na zaciatku, najvacsia diera vnutri, diera na konci).

    Tieto tri veci sa rozlisuju zamerne, lebo znamenaju nieco ine:

      * diera na ZACIATKU pred-okna = relacia zacala az v jeho priebehu,
        cize okno je SKRATENE (hlaska padla skor nez 60 s od zapnutia),
      * diera na KONCI po-okna = relacia skoncila skor, tiez skratene,
      * diera VNUTRI = senzor vypadol; `clear_live()` ju nicim neoznaci,
        takze sa da najst jedine tu.

    Keby sa vsetky tri scitali do jedneho cisla, skratene okno by sa
    hlasilo ako vypadok senzora a v prvych vecerov by sa nedalo rozlisit,
    ci je chyba v hodinkach alebo len v tom, ze relacia bola kratka.
    """
    inside = slice_span(series, t0, t1)
    if not inside:
        return (t1 - t0, 0.0, 0.0)
    inner = 0.0
    for i in range(len(inside) - 1):
        inner = max(inner, inside[i + 1][0] - inside[i][0])
    return (inside[0][0] - t0, inner, t1 - inside[-1][0])


def active_share(activity, t0, t1, active_idle_ms=ACTIVE_IDLE_MS):
    """Podiel vzoriek v intervale, v ktorych bol hrac aktivny (0.0-1.0).

    Je to zamerne hrube: "ako vela toho v tom okne robil", nie co robil.
    `activity` je [(timestamp, idle_ms)] z `activity.ActivityTracker`.
    """
    inside = slice_span(activity, t0, t1)
    if not inside:
        return None
    active = sum(1 for _, idle in inside if idle is not None and idle < active_idle_ms)
    return active / float(len(inside))


def refractory_conflict(ts, other_ts,
                        before=REFRACTORY_BEFORE_S, after=REFRACTORY_AFTER_S):
    """Zaznela v refraktérnej zone tejto hlasky ina hlaska?

    `other_ts` su casy VSETKYCH hlasok relacie vratane tejto - vlastny
    cas sa preskakuje porovnanim na rovnost, takze volajuci nemusi nic
    filtrovat.
    """
    for other in other_ts:
        if other == ts:
            continue
        if ts - before <= other <= ts + after:
            return True
    return False


# --------------------------------------------------------------------------
# Zostavenie okna
# --------------------------------------------------------------------------

def build_window(cue, samples, all_cue_ts, activity=None,
                 session_started=None, game=None):
    """Jedno meracie okno okolo jednej hlasky.

    `cue` je zaznam z `HeartStats.cues`: {ts, category, cue_id, arm, source}.
    `samples` je [(timestamp, bpm)], `activity` je [(timestamp, idle_ms)].
    Vracia vzdy dict - aj ked je okno neplatne, aby sa dalo spocitat,
    kolko okien a preco vypadlo.
    """
    ts = float(cue["ts"])
    reasons = []

    pre_a, pre_b = ts - PRE_S, ts
    post_a, post_b = ts + DEAD_S, ts + POST_S
    dur_a, dur_b = ts + POST_S, ts + DURABILITY_S

    pre_bpm = mean_in(samples, pre_a, pre_b)
    post_bpm = mean_in(samples, post_a, post_b)
    dur_bpm = mean_in(samples, dur_a, dur_b)

    if pre_bpm is None and post_bpm is None:
        reasons.append(R_NO_DATA)
    else:
        # Trvacnost (+70..+180) je volitelna, jej diery okno nezneplatnuju.
        pre_start, pre_inner, pre_end = gaps(samples, pre_a, pre_b)
        post_start, post_inner, post_end = gaps(samples, post_a, post_b)

        if pre_bpm is None or pre_start > MAX_GAP_S:
            reasons.append(R_PRE_SHORT)      # relacia zacala az v pred-okne
        if post_bpm is None or post_end > MAX_GAP_S:
            reasons.append(R_POST_SHORT)     # relacia skoncila v po-okne
        # R_GAP = senzor vypadol UPROSTRED, teda diera obklopena datami.
        # Prazdna strana nie je diera, ale SKRATENE okno (uz oznacene vyssie).
        # Bez tejto podmienky dostalo prazdne po-okno okrem spravneho
        # `skratene_po` aj nepravdivy `diera_v_datach`: `gaps()` vracia pri
        # prazdnom okne (cely_rozsah, 0, 0), cize `post_start` = cely rozsah.
        # Pri ladeni to tvrdilo, ze vypadli hodinky, hoci hrac len dohral (B5).
        diery = []
        if pre_bpm is not None:
            diery += [pre_inner, pre_end]
        if post_bpm is not None:
            diery += [post_start, post_inner]
        if diery and max(diery) > MAX_GAP_S:
            reasons.append(R_GAP)            # senzor vypadol uprostred

    if refractory_conflict(ts, all_cue_ts):
        reasons.append(R_REFRACTORY)

    # Vizuál sa nevykreslil? `is False`, nie `not`: staré záznamy pole
    # `delivered` nemajú (None = nevieme) a tie sa nesmú spätne zneplatniť —
    # rovnaké pravidlo ako pri aktivite.
    if cue.get("delivered") is False:
        reasons.append(R_NEDORUCENE)

    # Bol hrac vobec pri pocitaci? Nizka aktivita PRED hlaskou znamena, ze
    # zvyseny tep nepochadzal z hrania; nizka aktivita PO nej znamena, ze
    # pokles nemeria ucinok hlasky, ale to, ze sa clovek vratil a sadol si.
    # Okno sa nezahadzuje - zapise sa s dovodom a vypadne z ucinnosti.
    pre_act = active_share(activity or [], pre_a, pre_b)
    post_act = active_share(activity or [], post_a, post_b)
    # `None` znamena "nevieme" (stara relacia, alebo sa aktivita nesledovala),
    # nie "bol prec". Neznalost nesmie zneplatnit okno - inak by sa spatne
    # zahodila cela historia, ktora este aktivitu nezapisovala.
    if ((pre_act is not None and pre_act < MIN_AKTIVITA)
            or (post_act is not None and post_act < MIN_AKTIVITA)):
        reasons.append(R_NEAKTIVNY)

    window = {
        "ts": round(ts, 1),
        "arm": cue.get("arm", "voice"),
        "source": cue.get("source", "auto"),
        "category": cue.get("category"),
        "cue_id": cue.get("cue_id"),
        # ROZNE veci: `arm` je vylosovane rameno (voice/silent), `delivery`
        # je sposob dorucenia (pause/timeout). Zlucit sa nesmu, ale oboje
        # musi byt v okne - inak sa prah pauzy z nameraneho neda overit.
        "delivery": cue.get("delivery"),
        "pre_bpm": _round(pre_bpm),
        "post_bpm": _round(post_bpm),
        "durability_bpm": _round(dur_bpm),
        "pre_load": _round(mean_in(cue.get("load_series") or [], pre_a, pre_b)),
        "post_load": _round(mean_in(cue.get("load_series") or [], post_a, post_b)),
        "pre_activity": _round(pre_act, 3),
        "post_activity": _round(post_act, 3),
        "valid": not reasons,
        "reasons": reasons,
    }
    # ZAZNAM O DORUCENI (0.2, rebrik + brana): stupen rebrika, ci naozaj
    # nieco zaznelo, zataz pri doruceni a jej vrchol od natiahnutia, pasmo
    # tepu a za kolko sekund po hlaske prislo "teraz nie". Len ked ich
    # zaznam hlasky ma - starsie zaznamy ich nemaju a okno sa postavi aj tak.
    for kluc in ("rung", "audible", "load_at", "load_peak", "zone_at",
                 "snooze_after_s"):
        if cue.get(kluc) is not None:
            window[kluc] = cue[kluc]
    if session_started is not None:
        window["session_started"] = round(float(session_started), 1)
        window["offset_s"] = round(ts - float(session_started), 1)
    if game:
        window["game"] = game
    return window


def _round(value, decimals=1):
    return None if value is None else round(float(value), decimals)


def build_windows(cues, samples, load=None, activity=None,
                  session_started=None, game=None):
    """Meracie okna pre vsetky hlasky jednej relacie.

    Vola sa raz, pri zatvoreni relacie - vtedy uz je `samples` kompletny
    a netreba nic casovat. Zaroven to znamena, ze okno poslednej hlasky
    moze byt skratene, ak relacia skoncila skor nez +70 s; take okno sa
    zapise s dovodom, nezahodi.
    """
    cues = sorted(cues, key=lambda c: float(c["ts"]))
    all_ts = [float(c["ts"]) for c in cues]
    out = []
    for cue in cues:
        enriched = dict(cue)
        enriched["load_series"] = load or []
        window = build_window(enriched, samples, all_ts, activity=activity,
                              session_started=session_started, game=game)
        out.append(window)
    return out


# --------------------------------------------------------------------------
# Ulozenie
# --------------------------------------------------------------------------

# Pri strope 5 hlasok za hodinu a troch hodinach hrania denne je to
# ~15 okien denne, cize rok denneho hrania. Jedno okno je ~300 B JSON,
# 5000 okien teda ~1,5 MB.
MAX_WINDOWS = 5000


def load_windows(path):
    """Ulozene okna, alebo prazdny zoznam. Nikdy nevyhodi vynimku."""
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [w for w in data if isinstance(w, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def save_windows(path, windows, log=None):
    """Prida okna do JSON suboru (drzime poslednych MAX_WINDOWS).

    Zapisuje sa cez `.tmp` + `os.replace`, rovnako ako
    `hr_stats.save_session` - pad appky uprostred zapisu tak nemoze
    nechat na disku polovicny subor.

    Pri necitatelnom existujucom subore sa RADSEJ NEZAPISE nic, nez aby
    sa prepisal prazdnym zoznamom: zle prečitany subor nie je dovod
    zahodit vsetko, co sa dovtedy nameralo.
    """
    if not windows:
        return False
    try:
        data = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if not isinstance(loaded, list):
                raise ValueError("hr_windows.json nie je zoznam")
            data = loaded
        data.extend(windows)
        data = data[-MAX_WINDOWS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        if log:
            log(f"measure: zapis okien zlyhal: {exc}")
        return False


# --------------------------------------------------------------------------
# Prehlad (pouzije az faza 4, ale patri k datam, nie k UI)
# --------------------------------------------------------------------------

# Kritické hodnoty Studentovho t pre obojstranny 95% interval, df = n-1.
# Tabulka a nie `scipy`: `measure.py` je cisto datovy modul a ma sa dat
# importovat bez tazkych zavislosti (zadanie 2.1b, B2: "bez scipy").
# Nad 30 stupnov volnosti je rozdiel oproti 1,96 uz pod 4 %.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
    14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
    20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

# Pod tolkoto oknami sa cislo NEUKAZUJE. Nie je to vkus: pri troch oknach
# je interval siroky ako cely rozsah a graf by tvrdil nieco, co v datach
# nie je. Radsej "potrebujem viac" nez presvedcivo vyzerajuci sum.
MIN_OKIEN = 5


def _interval95(hodnoty):
    """(priemer, polsirka 95% intervalu). Polsirka je None, ked sa neda."""
    n = len(hodnoty)
    if n == 0:
        return None, None
    priemer = sum(hodnoty) / float(n)
    if n < 2:
        return priemer, None
    odchylka = (sum((h - priemer) ** 2 for h in hodnoty) / float(n - 1)) ** 0.5
    if odchylka == 0.0:
        return priemer, 0.0
    t = _T95.get(n - 1, 1.96)
    return priemer, t * odchylka / (n ** 0.5)


def _ma_branu(window):
    """Vzniklo okno uz s branou hlasky (0.2)? Znacku nesu `params`."""
    params = window.get("params")
    return isinstance(params, dict) and bool(params.get("brana"))


def by_category(windows, only_valid=True, arm="voice"):
    """Ucinnost podla KATEGORIE hlasky, nie podla ramena.

    Odkedy sa kategorie striedaju (`next_slot`), da sa pytat aj "ktora z
    nich zabera". Toto je vstup pre fazu 8 - a zatial hlavne pre graf v
    appke, aby hrac videl, na com je.

    Pocita sa len z HLASNEHO ramena: tiche okna su referencia pre to, ci
    hlaska funguje VOBEC, nie pre porovnanie kategorii medzi sebou.
    Miesat ich by znamenalo porovnavat kategoriu s tichom.

    Vracia {kategoria: {"n", "delta_bpm", "ci95", "dost_dat"}}.
    `delta_bpm` je posun po hlaske: zaporne cislo = tep klesol.
    `ci95` je POLSIRKA intervalu, alebo None pri jedinom okne.
    `dost_dat` hovori, ci sa to smie ukazat ako cislo.

    ZAMERNE NEROBI ZAVER. Nevracia "najlepsiu kategoriu" ani poradie -
    to by z prekryvajucich sa intervalov spravilo rebricek, ktory data
    neunesu.

    CO SA RATA (0.2, rebrik + brana): len hlasky dorucene NA PAUZE (tichy
    obrazok po `max_wait_s` nie je hlasna hlaska), ktore naozaj ZAZNELI
    (`audible` False = stupen "obraz", styl bez zvuku, slot bez zvuku;
    chybajuce pole = starsie okno, vtedy hlasne rameno na pauze zaznelo),
    a nie z PRACE (tam je hlaska len obrazom). A ked uz existuje okno s
    branou (`params.brana`), rataju sa LEN take - hlaska od 0.2 chodi az
    ked zataz nestupa, takze starsie okna by merali nieco ine.
    """
    okna = [w for w in windows or ()
            # CUDZIE DATA SA DO UCINNOSTI NERATAJU.
            #
            # `data_io.clean_window` oznacuje importovane zaznamy `imported:
            # True` a hlavicka toho modulu to vyslovne slubuje - lenze necital
            # to tu nikto. Kto si naimportoval zalohu od kamarata, videl vo
            # svojom grafe ucinnosti jeho telo zmiesane so svojim a nemal ako
            # to zistit.
            if isinstance(w, dict) and not w.get("imported")]
    if any(_ma_branu(w) for w in okna):
        okna = [w for w in okna if _ma_branu(w)]
    podla = {}
    for w in okna:
        if only_valid and not w.get("valid"):
            continue
        if arm is not None and w.get("arm") != arm:
            continue
        if w.get("delivery") != "pause":
            continue
        if w.get("world") == "work":
            continue
        if arm == "voice" and w.get("audible") is False:
            continue
        pre, post = w.get("pre_bpm"), w.get("post_bpm")
        if pre is None or post is None:
            continue
        kat = w.get("category")
        if kat is None:
            continue
        podla.setdefault(kat, []).append(post - pre)

    out = {}
    for kat, hodnoty in podla.items():
        priemer, polsirka = _interval95(hodnoty)
        out[kat] = {
            "n": len(hodnoty),
            "delta_bpm": round(priemer, 2),
            "ci95": None if polsirka is None else round(polsirka, 2),
            "dost_dat": len(hodnoty) >= MIN_OKIEN,
        }
    return out


def summarize(windows, only_valid=True):
    """Kolko okien je na ktorom ramene a aky je v nich priemerny posun BPM.

    Zamerne NEROBI ziadny zaver - vracia cisla. Rozhodnut, ci je rozdiel
    nieco viac nez sum, sa da az pri dostatocnom pocte okien (zadanie
    hovori o 30 na rameno) a s intervalom spolahlivosti.
    """
    out = {}
    for w in windows:
        # Cudzie okna sem nepatria - viz `by_category`.
        if w.get("imported"):
            continue
        if only_valid and not w.get("valid"):
            continue
        pre, post = w.get("pre_bpm"), w.get("post_bpm")
        if pre is None or post is None:
            continue
        bucket = out.setdefault(w.get("arm", "voice"), {"n": 0, "delta_sum": 0.0})
        bucket["n"] += 1
        bucket["delta_sum"] += post - pre
    for bucket in out.values():
        bucket["delta_bpm"] = round(bucket["delta_sum"] / bucket["n"], 2)
        del bucket["delta_sum"]
    return out
