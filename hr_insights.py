"""Analyza historie relacii tepu - jemne odporucania, nie diagnozy.

Co to robi
----------
Prejde ulozene suhrny relacii (hr_sessions.json) a hlada vzory NAPRIEC
relaciami, ktore z jednej relacie vidiet nie je:

  * pokojova zakladna stupa/klesa tyzden po tyzdni,
  * zotavenie tepu (HRR) sa zlepsuje/zhorsuje,
  * kedy v relacii prichadza vacsina spusteni dychania (prva hodina vs.
    az po dvoch hodinach),
  * cas nad hranicou rastie.

Kazdy vysledok je (kluc do i18n, parametre, ton). Texty su formulovane ako
"co vidime a co by si mohol skusit" - nikdy "si zdravy/chory". Modul je
cisto datovy: ziadny Tk, ziadna siet, ziadne I/O okrem save/load JSON,
takze sa da spustit v pozadi (threading) aj testovat priamo.

Prahy su zamerne konzervativne (aspon 3 relacie, rozdiel aspon 4 BPM),
aby appka nehlasila "trend" z dvoch nahodnych vecerov.
"""

import json
import os
import time

import hr_stats

MIN_SESSIONS = 3
BASELINE_DELTA_BPM = 4.0       # od kolkych BPM je zmena zakladne "trend"
HRR_DELTA_BPM = 4.0
WEEK_S = 7 * 86400.0
EARLY_SHARE = 0.66             # podiel spusteni v prvej hodine = "skoro"
LATE_SHARE = 0.5               # podiel spusteni po 2 h = "neskoro"
LONG_SESSION_S = 90 * 60.0
VERY_LONG_SESSION_S = 150 * 60.0

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
    early = late = total = 0
    for s in valid:
        offsets = s.get("trigger_offsets_s") or []
        dur = float(s.get("duration_s", 0))
        if dur < LONG_SESSION_S:
            continue
        for off in offsets:
            try:
                off = float(off)
            except (TypeError, ValueError):
                continue
            total += 1
            if off <= 3600.0:
                early += 1
            if dur >= VERY_LONG_SESSION_S and off >= 7200.0:
                late += 1
    if total >= 4:
        if early / total >= EARLY_SHARE:
            insights.append(_insight("triggers_early", TONE_INFO,
                                     share=int(round(100.0 * early / total))))
        elif late / total >= LATE_SHARE:
            insights.append(_insight("triggers_late", TONE_WATCH,
                                     share=int(round(100.0 * late / total))))
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
        elif hlasok == 0 and behov == 0:
            # Telo sa ani raz nedostalo nad prah - politika nepomoze,
            # hranica tepu je na hraca nastavena privysoko.
            insights.append(_insight("cue_never_above", TONE_INFO,
                                     n=len(posledne)))
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

def save_insights(path, insights, log=None):
    try:
        payload = {"computed_at": time.time(), "insights": list(insights or [])}
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
    return {"computed_at": None, "insights": []}
