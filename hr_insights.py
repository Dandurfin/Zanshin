"""Analyza historie relacii tepu - jemne odporucania, nie diagnozy.

Co to robi
----------
Prejde ulozene suhrny relacii (hr_sessions.json) a hlada vzory NAPRIEC
relaciami, ktore z jednej relacie vidiet nie je:

  * pokojova zakladna stupa/klesa tyzden po tyzdni,
  * zotavenie tepu (HRR) sa zlepsuje/zhorsuje,
  * kedy v relacii chodia spustenia dychania hustejsie (prva hodina vs.
    az po dvoch hodinach),
  * cas nad hranicou rastie.

Kazdy vysledok je (kluc do i18n, parametre, ton). Texty su formulovane ako
"co vidime a co by si mohol skusit" - nikdy "si zdravy/chory". Modul je
cisto datovy: ziadny Tk, ziadna siet, ziadne I/O okrem save/load JSON,
takze sa da spustit v pozadi (threading) aj testovat priamo.

Prahy su zamerne konzervativne (aspon 3 relacie, rozdiel aspon 4 BPM,
spustenia aspon 2x hustejsie a nie nahodou), aby appka nehlasila "trend"
z dvoch nahodnych vecerov.
"""

import json
import math
import os
import time

import hr_stats

MIN_SESSIONS = 3
BASELINE_DELTA_BPM = 4.0       # od kolkych BPM je zmena zakladne "trend"
HRR_DELTA_BPM = 4.0
WEEK_S = 7 * 86400.0
LONG_SESSION_S = 90 * 60.0
VERY_LONG_SESSION_S = 150 * 60.0

# Kedy prichadzaju spustenia (postreh 3). Porovnava sa HUSTOTA - kolko
# spusteni pride na cas relacie v okne - nie ich podiel. (Cas relacie, nie
# cas hrania: `duration_s` bezi od zapnutia senzora, aj cez menu a AFK.)
# Podiel sa myli uz na rovnomernych spusteniach: v 90-min relacii je prva hodina dve tretiny
# casu, takze aj uplne rovnomerne spustenia davaju ~67 % "v prvej hodine"
# a stary prah 66 % hlasil vzor, ktory tam nebol. V 4-5 h relaciach to
# iste robilo "po dvoch hodinach" (prah 50 %) - a to s tonom "watch".
EARLY_WINDOW_S = 3600.0        # "v prvej hodine"
LATE_FROM_S = 7200.0           # "az po dvoch hodinach"
RATE_RATIO = 2.0               # okno musi byt aspon 2x hustejsie nez zvysok
MIN_TRIGGERS = 6               # menej spusteni v porovnani = vecer, nie vzor
# Ako velmi moze byt nepomer nahoda. Pri par spusteniach je aj 2x nahoda:
# simulacia rovnomernych spusteni (3-5 relacii po 90-300 min, 1-3 za
# hodinu, s odstupom a stropom z trigger.py) dala so samotnym "2x a aspon
# 6 spusteni" hlasku v 4-18 % pripadov, s touto poistkou okolo 2 % (aj ked
# su napate vecery kratsie alebo dlhsie nez pokojne - viz ocakavanie po
# relaciach v analyze()).
# Cena: z troch 90-min relacii sa skutocny rozbeh ukaze malokedy (po
# prvej hodine je v nich len pol hodiny na porovnanie) - postreh pride
# az s dalsimi relaciami. Radsej ticho nez plany poplach.
CHANCE_P = 0.05

# Kolko POSLEDNYCH relacii sa pyta pri odporucaniach o tichu. Tri su
# minimum, z ktoreho sa da povedat "deje sa to opakovane" a nie "mal si
# jeden pokojny vecer".
TICHYCH_RELACII = 3
# Ked je najdlhsi usek nad prahom aspon takouto castou potrebneho drzania,
# je to "tesne vedla" - vtedy ma zmysel radit zmenu politiky. Ked je to
# hlboko pod, problem je inde (prah, hranica tepu) a rada by mylila.
TESNE_VEDLA = 0.5
# Od kolkych zruseni vypadkom na relaciu sa to uz neda zvalit na nahodu.
VYPADKOV_VELA = 3.0

TONE_INFO = "info"
TONE_GOOD = "good"
TONE_WATCH = "watch"


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _zadrzanych(sessions):
    """Kolko natiahnuti appka v tychto relaciach SAMA zrusila
    (`cues_withheld`, 0.2 stress-gate). Stare relacie ho nemaju - 0;
    pokazena hodnota sa nerata."""
    spolu = 0.0
    for s in sessions:
        zadrzane = s.get("cues_withheld")
        if not isinstance(zadrzane, dict):
            continue
        for v in zadrzane.values():
            try:
                spolu += float(v or 0)
            except (TypeError, ValueError):
                pass
    return spolu


def _cislo_or_0(hodnota):
    """Cislo zo suhrnu relacie; chybajuce alebo pokazene = 0."""
    try:
        return float(hodnota or 0)
    except (TypeError, ValueError):
        return 0.0


def _valid(sessions):
    out = []
    for s in sessions or []:
        if not isinstance(s, dict):
            continue
        # Importovana relacia je cudzie telo. Postreh "tvoj pokojovy tep
        # rastie" postaveny na nej by bol tvrdenie o niekom inom.
        if s.get("imported"):
            continue
        # Pokazena relacia (kroky citane ako tep) tu doteraz prechadzala a
        # vyrobila neexistujuce varovanie aj hlasku "zotavenie +50 BPM" z
        # poctu krokov (B8). Ten isty filter ako pri kalibracii.
        if hr_stats.je_podozriva(s):
            continue
        try:
            if float(s.get("duration_s", 0)) < 60 or int(s.get("samples", 0)) < 10:
                continue
        except (TypeError, ValueError):
            continue
        out.append(s)
    out.sort(key=lambda s: float(s.get("started", 0)))
    return out


def _insight(key, tone=TONE_INFO, **params):
    return {"key": key, "tone": tone, "params": params}


def _binom_tail(k, n, p):
    """P(X >= k) pre X ~ Bin(n, p). V logaritmoch, aby to nepretieklo ani
    pri tisickach spusteni za roky hrania (math.comb * float by padol)."""
    lp, lq = math.log(p), math.log1p(-p)
    ln_n = math.lgamma(n + 1)
    return sum(math.exp(ln_n - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * lp + (n - i) * lq)
               for i in range(k, n + 1))


def _denser(inside, outside, t_inside, t_outside):
    """Chodia spustenia v okne ZRETELNE hustejsie nez mimo neho?

    `inside`/`outside` su pocty spusteni, `t_inside`/`t_outside` kolko by
    ich v okne a mimo neho bolo, keby v kazdej relacii chodili rovnomerne
    (sucet podielov okna cez spustenia). Platit musi oboje:
      * v okne je ich aspon RATE_RATIO-krat viac oproti ocakavaniu nez mimo
        neho - aby to bol rozdiel, ktory stoji za vetu;
      * pri rovnomernom rozlozeni by taky nepomer vznikol nahodou nanajvys
        s pravdepodobnostou CHANCE_P. Binomicky chvost s priemernym podielom
        je pri roznych dlzkach relacii opatrnejsi nez presny (Hoeffding
        1956), takze chyba ide smerom k tichu.
    """
    n = inside + outside
    if n < MIN_TRIGGERS or t_inside <= 0 or t_outside <= 0:
        return False
    # inside/t_inside >= RATE_RATIO * outside/t_outside, bez delenia nulou
    if inside * t_outside < RATE_RATIO * outside * t_inside:
        return False
    p = t_inside / (t_inside + t_outside)
    if not 0.0 < p < 1.0:       # pokazene trvanie (inf/nan) - radsej ticho
        return False
    return _binom_tail(inside, n, p) <= CHANCE_P


def _split_recent(sessions, now, field):
    """Relacie s danym polom: posledny tyzden vs. tyzden pred nim. Ak by
    v niektorom tyzdni boli menej nez 2, spadne na 'posledne 3 vs.
    predosle 3' - stale porovnavame porovnatelne kusy."""
    with_field = [s for s in sessions if s.get(field) is not None]
    recent = [s for s in with_field if now - float(s.get("started", 0)) <= WEEK_S]
    previous = [s for s in with_field
                if WEEK_S < now - float(s.get("started", 0)) <= 2 * WEEK_S]
    if len(recent) >= 2 and len(previous) >= 2:
        return recent, previous, "week"
    if len(with_field) >= 6:
        return with_field[-3:], with_field[-6:-3], "sessions"
    return None, None, None


def analyze(sessions, now=None):
    """Vrati zoznam insightov pre danu historiu (moze byt prazdny)."""
    now = float(now) if now else time.time()
    valid = _valid(sessions)
    insights = []
    if len(valid) < MIN_SESSIONS:
        insights.append(_insight("need_more", TONE_INFO, n=len(valid), need=MIN_SESSIONS))
        return insights

    flagged = False

    # 1. pokojova zakladna - stupa alebo klesa
    recent, previous, basis = _split_recent(valid, now, "baseline_bpm")
    if recent:
        diff = _mean(s["baseline_bpm"] for s in recent) - _mean(s["baseline_bpm"] for s in previous)
        if diff >= BASELINE_DELTA_BPM:
            insights.append(_insight("resting_up", TONE_WATCH, delta=int(round(diff))))
            flagged = True
        elif diff <= -BASELINE_DELTA_BPM:
            insights.append(_insight("resting_down", TONE_GOOD, delta=int(round(-diff))))

    # 2. zotavenie tepu (HRR)
    recent, previous, basis = _split_recent(valid, now, "hrr_bpm")
    if recent:
        diff = _mean(s["hrr_bpm"] for s in recent) - _mean(s["hrr_bpm"] for s in previous)
        if diff >= HRR_DELTA_BPM:
            insights.append(_insight("hrr_up", TONE_GOOD, delta=int(round(diff))))
        elif diff <= -HRR_DELTA_BPM:
            insights.append(_insight("hrr_down", TONE_WATCH, delta=int(round(-diff))))
            flagged = True

    # 3. kedy prichadzaju spustenia dychania
    #
    # "Skoro" = prva hodina proti zvysku, v relaciach od 90 min. "Neskoro" =
    # po dvoch hodinach proti prvym dvom, len v relaciach od 150 min - len
    # tam je po dvoch hodinach aspon pol hodiny na porovnanie.
    #
    # Ocakavanie sa pocita PO RELACIACH, nie zo suctu casov: kazde spustenie
    # prinesie podiel okna vo SVOJEJ relacii. So suctom casov by napata
    # 90-min relacia vedla pokojnych 5-h relacii vyzerala ako "prva hodina
    # je hustejsia", hoci v ziadnej relacii nebola (Simpsonov paradox).
    early = after_early = 0
    t_early = t_after_early = 0.0
    late = before_late = 0
    t_late = t_before_late = 0.0
    for s in valid:
        offsets = s.get("trigger_offsets_s") or []
        dur = float(s.get("duration_s", 0))
        # nan/inf: preskocit len tuto relaciu, nie umlcat postreh navzdy
        if not math.isfinite(dur) or dur < LONG_SESSION_S:
            continue
        very_long = dur >= VERY_LONG_SESSION_S
        p_early = EARLY_WINDOW_S / dur
        p_late = (dur - LATE_FROM_S) / dur
        for off in offsets:
            try:
                off = float(off)
            except (TypeError, ValueError):
                continue
            t_early += p_early
            t_after_early += 1.0 - p_early
            if very_long:
                t_late += p_late
                t_before_late += 1.0 - p_late
            if off <= EARLY_WINDOW_S:
                early += 1
            else:
                after_early += 1
            if very_long:
                if off >= LATE_FROM_S:
                    late += 1
                else:
                    before_late += 1
    # {share} ostava obycajny podiel spusteni v okne - veta "X % spusteni
    # prislo v prvej hodine" je doslova pravdiva; to, ze je to VIAC, nez
    # by zodpovedalo casu, overil _denser.
    if _denser(early, after_early, t_early, t_after_early):
        insights.append(_insight("triggers_early", TONE_INFO,
                                 share=int(round(100.0 * early / (early + after_early)))))
    elif _denser(late, before_late, t_late, t_before_late):
        insights.append(_insight("triggers_late", TONE_WATCH,
                                 share=int(round(100.0 * late / (late + before_late)))))
        flagged = True

    # 4. cas nad hranicou rastie (podiel relacie)
    def over_share(s):
        dur = float(s.get("duration_s", 0)) or 1.0
        return float(s.get("time_over_s", 0)) / dur
    if len(valid) >= 6:
        recent_share = _mean(over_share(s) for s in valid[-3:])
        previous_share = _mean(over_share(s) for s in valid[-6:-3])
        recent_abs = _mean(float(s.get("time_over_s", 0)) for s in valid[-3:])
        if previous_share is not None and recent_abs >= 300 \
                and recent_share >= 1.5 * max(previous_share, 0.02):
            insights.append(_insight("over_up", TONE_WATCH,
                                     minutes=int(round(recent_abs / 60.0))))
            flagged = True

    # 5. PRECO APPKA MLCI
    #
    # Toto su jedine odporucania, ktore hovoria hracovi, CO MA UROBIT - a
    # preto stoja na tvrdych cislach zo spustaca (`longest_above_s`,
    # `above_runs`, `runs_cancelled_gap`), nie na dojme z tepu.
    #
    # Poradie NIE JE lubovolne. Vypadky sa pytaju ako prve: pri nich je
    # "najdlhsi usek" rozsekany dierami v datach, takze rada "ozvi sa
    # castejsie" by poslala hraca ladit prah namiesto hodiniek.
    posledne = [s for s in valid if s.get("above_runs") is not None][-TICHYCH_RELACII:]
    if len(posledne) >= TICHYCH_RELACII:
        hlasok = sum(int(s.get("auto_triggers") or 0) for s in posledne)
        vypadkov = _mean(float(s.get("runs_cancelled_gap") or 0) for s in posledne)
        behov = sum(int(s.get("above_runs") or 0) for s in posledne)

        if vypadkov >= VYPADKOV_VELA:
            insights.append(_insight("cue_dropouts", TONE_WATCH,
                                     n=int(round(vypadkov))))
            flagged = True
        elif hlasok == 0 and any(s.get("cue_rung") == "pause" for s in posledne):
            # 0.2 (rebrik hlasky): appka mala hlasky sama vypnute - "nemala
            # som sa preco ozvat", "len na chvilu" ani "nic som si nevsimla"
            # by nebola pravda. Preco, povie veta v Historii a dotaznik.
            flagged = True
        elif hlasok == 0 and any(_cislo_or_0(s.get("snoozed_s")) > 0
                                 for s in posledne):
            # 24. 9.: "teraz nie" relaciu uz nezatvara. Kym platilo, automat
            # spal a `above_runs` ani `longest_above_s` ten cas nevidia -
            # "nedostala sa nad hranicu" / "len na chvilu" by vysvetlovali
            # ticho, ktore si hrac vybral sam. Co sa stalo, povie dotaznik.
            flagged = True
        elif hlasok == 0 and behov == 0:
            # Telo sa ani raz nedostalo nad prah - politika nepomoze,
            # hranica tepu je na hraca nastavena privysoko.
            insights.append(_insight("cue_never_above", TONE_INFO,
                                     n=len(posledne)))
            flagged = True
        elif hlasok == 0 and _zadrzanych(posledne) > 0:
            # 0.2 (stress-gate): spustac sa natiahol, ale appka sama mlcala
            # (brana, odstup). Zataz teda hore vydrzala a "len na chvilu" /
            # "tesne" by klamalo. Radsej ziadna rada (ani "nic som si
            # nevsimla") - co sa stalo, povie dotaznik po relacii.
            flagged = True
        elif hlasok == 0 and behov > 0:
            najdlhsi = max(float(s.get("longest_above_s") or 0) for s in posledne)
            treba = max(float(s.get("stress_hold_s") or 0) for s in posledne)
            if treba and najdlhsi >= TESNE_VEDLA * treba:
                insights.append(_insight("cue_almost", TONE_INFO,
                                         sec=int(round(najdlhsi)),
                                         need=int(round(treba))))
            else:
                insights.append(_insight("cue_far", TONE_INFO,
                                         sec=int(round(najdlhsi)),
                                         need=int(round(treba))))
            flagged = True

    if not flagged and len(insights) == 0:
        insights.append(_insight("steady", TONE_GOOD, n=len(valid)))
    return insights


# --------------------------------------------------------------------------
# Ulozenie vysledku (aby sa nemusel pocitat pri kazdom otvoreni stranky)
# --------------------------------------------------------------------------

def save_insights(path, insights, log=None, world=None):
    """`world` = svet, z ktoreho relacii sa postrehy ratali (B3-worlds).

    Bez neho by sa po prepnuti sveta pri starte ukazali postrehy druheho
    sveta - appka ich preto pri nezhode zahodi a prepocita (viz app.py)."""
    try:
        payload = {"computed_at": time.time(), "insights": list(insights or [])}
        if world is not None:
            payload["world"] = world
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        if log:
            log(f"HR insights: save failed: {exc}")
        return False


def load_insights(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("insights"), list):
            return data
    except Exception:
        pass
    return {"computed_at": None, "insights": [], "world": None}
