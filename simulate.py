"""Simulates an evening of play and tells what the trigger would do.

WHY IT CAN BE SIMULATED HERE
----------------------------
For the question "does Windows see the gamepad?" simulation did not work -
synthetic input would answer on behalf of the operating system and the
result would mean nothing. Here it is the other way round: we ask what OUR
own state machine does with a known input. That is exactly what simulation
is for.

Nothing is recomputed here. The evening goes through `hr_stats.HeartStats`,
`activity.ActivityTracker`, `trigger.CueTrigger` and `measure` - i.e.
through the same objects that run in the app, in the same call order as
`_apply_hr_bpm` and `_tick_activity`. Only two things are slipped in: the
clock and `idle_fn`. If idle were computed here, it would completely miss
the part that matters most - `pause_s()` and the fact that a pause starts
at the moment of the LAST input, not at the moment the app noticed it.

WHAT IT WILL AND WILL NOT TELL YOU
----------------------------------
IT WILL TELL: how many times it would arm, how many cues would sound, how
many would fall into the silent branch, how many measurement windows would
be valid and why the others would not. Those are properties of the
MECHANISM, and those can be verified.

IT WILL NOT TELL: whether your real load ever exceeds 55 and holds for 90
seconds. That is a property of the BODY, and for that you need an evening
with the watch. The simulation can show that the mechanism is fine; it
cannot show that the thresholds fit you. The "telo" (body) row in the
output is therefore only a check that the synthetic evening gives the
state machine anything to bite into at all - it is not a claim about the
player.

THE WEAKEST POINT of this model is the distribution of breaks in the input
- and that happens to be exactly what the dispute is about (the 2.5 s
threshold). So the number that comes out depends on the assumption that is
about to be measured. That is why it is a parameter and why `--sweep` is
here: not to give an answer, but to show how much depends on that
assumption.

USAGE
-----
    python simulate.py                   # 5 evenings of 3 h each
    python simulate.py --sedeni 1 --podrobne
    python simulate.py --sweep           # a table across pause thresholds
"""

import argparse
import bisect
import random
import statistics

import activity
import hr_stats
import measure
import trigger

# Activity has the same cadence as in the app: `_tick_activity` runs 4x a
# second (activity.POLL_S).
#
# Heart rate does NOT. The simulation sends a sample exactly once a second,
# without loss - an ideally dense cadence. Real watches, according to the
# data, send ~0.9 to ~2.9 s per sample (since 20. 9. ~2.9 s, in OBS heart
# rate alternates with steps), with a tail of gaps just over 5 s (a lost
# packet). That tail is not here - which is why this simulation never
# showed that the trigger erased the accumulated time on every gap over
# 5 s (fixed via `trigger.DIERA_S`). Its numbers apply to a dense watch.
TEP_S = 1.0

# The evening does not start at time 0. `HeartStats.add` has `now = float(ts)
# if ts else time.time()`, so ts=0.0 would silently fall back to the real time
# and the whole simulation would fall apart. A zero absolute time never happens
# in the app, so here it is worked around, not fixed - but it is written down
# so nobody goes looking for it.
T0 = 1_700_000_000.0


# --------------------------------------------------------------------------
# Synthetic evening
# --------------------------------------------------------------------------

def bloky(rng, hodin):
    """Evening split into intense/calm stretches: [(od, do, vypaty, uroven)].

    The split is made ONCE and is used for both heart rate and input. The
    first attempt generated them in two independent passes and the result
    was nonsense: intense heart rate fell on calm input, so the state
    machine armed at a moment when the player had long stopped doing
    anything, and "waiting for a pause" came out at 0.3 s. That would
    measure the model's lack of correlation, not the trigger.
    """
    koniec = hodin * 3600.0
    out = []
    t = 0.0
    vypaty = False
    while t < koniec:
        dlzka = rng.uniform(150, 420) if vypaty else rng.uniform(60, 240)
        do = min(koniec, t + dlzka)
        out.append((t, do, vypaty, rng.uniform(16, 34) if vypaty
                    else rng.uniform(0, 6)))
        t = do
        vypaty = not vypaty
    return out


def _blok_v(bl, t):
    for od, do, vypaty, uroven in bl:
        if od <= t < do:
            return vypaty, uroven
    return bl[-1][2], bl[-1][3]


def vecer(rng, hodin=3.0, pokoj=62.0, naklonenie=1.0):
    """Returns (tep, vstupy).

    `tep` is [(cas, bpm)] per second, `vstupy` are the times when the
    player pressed something. From them idle is then computed the same way
    Windows computes it: "how many ms since the last input".

    It is not about faithful physiology, it is about having the situations
    the state machine reacts to: long holds up high, short peaks, breaks of
    various lengths. `naklonenie` scales how high the load goes - 0.5 is a
    calm evening, 2.0 a hard competitive session.
    """
    bl = bloky(rng, hodin)
    koniec = hodin * 3600.0
    tep, vstupy = [], []

    t = 0.0
    while t < koniec:
        vypaty, uroven = _blok_v(bl, t)
        bpm = pokoj + uroven * (naklonenie if vypaty else 1.0) + rng.gauss(0, 2.5)
        if vypaty and rng.random() < 0.02:
            bpm += rng.uniform(10, 25)          # peak after a fight
        tep.append((T0 + t, max(45.0, min(190.0, bpm))))
        t += TEP_S

    t = 0.0
    while t < koniec:
        vstupy.append(T0 + t)
        t += medzera(rng, _blok_v(bl, t)[0])

    return tep, vstupy


def medzera(rng, vypaty):
    """How long until the next press.

    THIS IS THE ASSUMPTION. The whole number "how many cues get delivered
    in a pause" falls out of it, so it cannot be relied on as a
    measurement. It is an estimate of what playing looks like: in action
    almost continuous, between rounds and in menus sparse.
    """
    r = rng.random()
    if vypaty:
        if r < 0.90:
            return rng.uniform(0.05, 0.4)       # action
        if r < 0.99:
            return rng.uniform(1.0, 4.0)        # reload, moving
        return rng.uniform(5.0, 15.0)           # end of round
    if r < 0.60:
        return rng.uniform(0.1, 1.0)            # menu, chat
    if r < 0.90:
        return rng.uniform(2.0, 10.0)           # waiting
    if r < 0.98:
        return rng.uniform(20.0, 90.0)          # stepped away
    return rng.uniform(120.0, 400.0)            # break


class Hodiny:
    """A stand-in clock. An object, not a closure, so the time can be moved
    from outside and all three (`HeartStats`, `ActivityTracker`,
    `CueTrigger`) see the same one."""

    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


# --------------------------------------------------------------------------
# Running it through the real modules
# --------------------------------------------------------------------------

def odsimuluj(tep, vstupy, params=None, silent_share=0.10, seed=1):
    """Returns (okna, udalosti, telo). The call order copies the app."""
    hodiny = Hodiny()

    def idle_ms():
        """Same as what GetLastInputInfo returns: ms since the last input."""
        i = bisect.bisect_right(vstupy, hodiny.t)
        if i == 0:
            return None
        return (hodiny.t - vstupy[i - 1]) * 1000.0

    stats = hr_stats.HeartStats(critical_bpm=110)
    stats.session_start = T0
    sled = activity.ActivityTracker(idle_fn=idle_ms, clock=hodiny)
    aut = trigger.CueTrigger(params=params, rng=random.Random(seed),
                             clock=hodiny)
    aut.open_session(silent_share=silent_share)

    udalosti = []
    telo = {"nad_prahom_s": 0.0, "peak": 0.0, "behy": []}
    prah = aut.params["stress_threshold"]
    beh_od = None

    i_tep = 0
    t = T0
    koniec = tep[-1][0]

    while t <= koniec:
        hodiny.t = t

        # ---- heart rate: `_apply_hr_bpm`, once a second ----
        while i_tep < len(tep) and tep[i_tep][0] <= t:
            ts, bpm = tep[i_tep]
            hodiny.t = ts
            stats.add(bpm, ts=ts)
            ev = aut.note_load(stats.stress, ts,
                               calibrating=stats.is_calibrating,
                               zona=stats.known_zone)   # gate, like the app
            if ev:
                udalosti.append(ev)
            # diagnostics of the synthetic body, not of the app
            if stats.stress >= prah:
                telo["nad_prahom_s"] += TEP_S
                if beh_od is None:
                    beh_od = ts
            elif beh_od is not None:
                telo["behy"].append(ts - beh_od)
                beh_od = None
            telo["peak"] = max(telo["peak"], stats.stress)
            i_tep += 1

        # ---- activity: `_tick_activity`, 4x a second ----
        hodiny.t = t
        sled.poll(now=t)
        ev = aut.tick(pause_s=sled.pause_s(now=t), now=t, can_fire=True)
        if ev:
            udalosti.append(ev)
            if ev["typ"] == trigger.E_DELIVER:
                # the same as what `_fire_somatic_cue` does
                stats.note_trigger(ts=ev["ts"], auto=True,
                                   category=measure.category_for_slot(
                                       measure.CATEGORIES.index("breath")),
                                   cue_id="slot3", arm=ev["arm"],
                                   source="auto")
        t += activity.POLL_S

    if beh_od is not None:
        telo["behy"].append(koniec - beh_od)
    zaver = aut.close_session(now=koniec)
    if zaver:
        udalosti.append(zaver)

    okna = measure.build_windows(stats.cues, stats._all, load=stats._load,
                                 activity=sled.samples,
                                 session_started=T0, game="simulacia")
    return okna, udalosti, telo


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def zhrn(okna, udalosti, telo):
    doruceni = [e for e in udalosti if e["typ"] == trigger.E_DELIVER]
    zruseni = [e for e in udalosti if e["typ"] == trigger.E_ABORT]
    cakanie = [e["waited_s"] for e in doruceni]
    dovody, preco_zrusene = {}, {}
    for w in okna:
        for d in w.get("reasons") or []:
            dovody[d] = dovody.get(d, 0) + 1
    for e in zruseni:
        preco_zrusene[e["reason"]] = preco_zrusene.get(e["reason"], 0) + 1
    dlhe = [b for b in telo["behy"] if b >= 90.0]
    return {
        "natiahnuti": sum(1 for e in udalosti if e["typ"] == trigger.E_ARMED),
        "doruceni": len(doruceni),
        "pauzou": sum(1 for e in doruceni if e["delivery"] == trigger.D_PAUSE),
        "timeoutom": sum(1 for e in doruceni if e["delivery"] == trigger.D_TIMEOUT),
        "hlasne": sum(1 for e in doruceni if e["hlas"]),
        "ticho": sum(1 for e in doruceni if not e["hlas"]),
        "rameno_silent": sum(1 for e in doruceni if e["arm"] == trigger.ARM_SILENT),
        "zrusene": len(zruseni), "preco_zrusene": preco_zrusene,
        "okien": len(okna),
        "platnych": sum(1 for w in okna if w.get("valid")),
        "dovody": dovody,
        "cakanie": cakanie,
        "median_cakania": statistics.median(cakanie) if cakanie else 0.0,
        "nad_prahom_min": telo["nad_prahom_s"] / 60.0,
        "peak": telo["peak"],
        "behov_90": len(dlhe),
    }


def jeden_vecer(args, seed):
    rng = random.Random(seed)
    tep, vstupy = vecer(rng, hodin=args.hodin, naklonenie=args.naklonenie)
    params = {}
    if args.pauza is not None:
        params["pause_s"] = args.pauza
    if args.prah is not None:
        params["stress_threshold"] = args.prah
    if args.drzanie is not None:
        params["stress_hold_s"] = args.drzanie
    if args.cakanie is not None:
        params["max_wait_s"] = args.cakanie
    okna, udalosti, telo = odsimuluj(tep, vstupy, params=params or None,
                                     silent_share=args.ticho, seed=seed)
    s = zhrn(okna, udalosti, telo)
    s["_okna"] = okna
    s["_udalosti"] = udalosti
    return s


def priemer(sucty, kluc):
    return sum(s[kluc] for s in sucty) / float(len(sucty))


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Odsimuluje vecer hrania cez skutocne moduly appky.")
    ap.add_argument("--hodin", type=float, default=3.0)
    ap.add_argument("--sedeni", type=int, default=5, help="kolko vecerov")
    ap.add_argument("--naklonenie", type=float, default=1.0,
                    help="0.5 pokojny vecer, 2.0 tvrda kompetitivna session")
    ap.add_argument("--pauza", type=float, default=None, help="prah pauzy v s")
    ap.add_argument("--prah", type=float, default=None, help="prah zataze 0-100")
    ap.add_argument("--drzanie", type=float, default=None,
                    help="ako dlho musi zataz drzat hore (s)")
    ap.add_argument("--cakanie", type=float, default=None,
                    help="najdlhsie cakanie na pauzu (s)")
    ap.add_argument("--ticho", type=float, default=0.10,
                    help="podiel tichého kontrolneho ramena")
    ap.add_argument("--podrobne", action="store_true",
                    help="vypise kazdu udalost")
    ap.add_argument("--sweep", action="store_true",
                    help="tabulka naprie prahmi pauzy")
    args = ap.parse_args()

    if args.sweep:
        sweep(args)
        return

    p = dict(trigger.default_params())
    print(f"{args.sedeni} vecerov po {args.hodin:g} h, naklonenie "
          f"{args.naklonenie:g}")
    print(f"prah zataze {args.prah or p['stress_threshold']:g}, drzanie "
          f"{args.drzanie or p['stress_hold_s']:g} s, prah pauzy "
          f"{args.pauza or p['pause_s']:g} s, tiche rameno "
          f"{args.ticho * 100:.0f} %")
    print("=" * 74)

    sucty = [jeden_vecer(args, seed) for seed in range(args.sedeni)]

    print(f"{'':>7} {'natiah':>7} {'doruc':>6} {'pauzou':>7} {'timeout':>8} "
          f"{'hlasne':>7} {'ticho':>6} {'zrus':>5} {'okna':>10}")
    for i, s in enumerate(sucty):
        print(f"vecer {i + 1:<2}{s['natiahnuti']:>7} {s['doruceni']:>6} "
              f"{s['pauzou']:>7} {s['timeoutom']:>8} {s['hlasne']:>7} "
              f"{s['ticho']:>6} {s['zrusene']:>5} "
              f"{s['platnych']:>4}/{s['okien']:<5}")
    print("-" * 74)
    print(f"{'priemer':<7}{priemer(sucty, 'natiahnuti'):>7.1f} "
          f"{priemer(sucty, 'doruceni'):>6.1f} {priemer(sucty, 'pauzou'):>7.1f} "
          f"{priemer(sucty, 'timeoutom'):>8.1f} {priemer(sucty, 'hlasne'):>7.1f} "
          f"{priemer(sucty, 'ticho'):>6.1f} {priemer(sucty, 'zrusene'):>5.1f} "
          f"{priemer(sucty, 'platnych'):>4.1f}/{priemer(sucty, 'okien'):<5.1f}")

    vsetky_cakania = [c for s in sucty for c in s["cakanie"]]
    if vsetky_cakania:
        strop = args.cakanie if args.cakanie is not None else p["max_wait_s"]
        print(f"\ncakanie na pauzu: median {statistics.median(vsetky_cakania):.1f} s, "
              f"najdlhsie {max(vsetky_cakania):.1f} s (strop {strop:g} s)")

    dovody = {}
    for s in sucty:
        for d, n in s["dovody"].items():
            dovody[d] = dovody.get(d, 0) + n
    if dovody:
        print("\npreco okno nie je platne:")
        for d, n in sorted(dovody.items(), key=lambda kv: -kv[1]):
            print(f"  {d:<20} {n}")

    zrusene = {}
    for s in sucty:
        for d, n in s["preco_zrusene"].items():
            zrusene[d] = zrusene.get(d, 0) + n
    if zrusene:
        print("\npreco sa natiahnutie zrusilo:")
        for d, n in sorted(zrusene.items(), key=lambda kv: -kv[1]):
            print(f"  {d:<20} {n}")

    print(f"\ntelo (synteticke, NIE tvrdenie o hracovi): nad prahom "
          f"{priemer(sucty, 'nad_prahom_min'):.0f} min z {args.hodin * 60:.0f}, "
          f"z toho {priemer(sucty, 'behov_90'):.1f} usekov dlhsich nez 90 s, "
          f"spicka zataze {priemer(sucty, 'peak'):.0f}")

    na_vecer = priemer(sucty, "platnych")
    if na_vecer > 0:
        tichych = na_vecer * args.ticho
        print(f"\nPri {na_vecer:.1f} platnych oknach na vecer a {args.ticho * 100:.0f} % "
              f"tichom rameni pribudne {tichych:.2f} tichého okna za vecer.")
        print(f"Na 30 tichych okien (minimum zo zadania §2) to je "
              f"{30 / tichych:.0f} vecerov, na ~130 (sila 80 % pri d = 0,35) "
              f"{130 / tichych:.0f}.")

    if args.podrobne:
        print("\nudalosti prveho vecera:")
        for e in sucty[0]["_udalosti"]:
            cas = (e["ts"] - T0) / 60.0
            if e["typ"] == trigger.E_ARMED:
                print(f"  {cas:6.1f} min  NATIAHNUTE   rameno {e['arm']}, "
                      f"zataz {e['load']:.0f}")
            elif e["typ"] == trigger.E_DELIVER:
                print(f"  {cas:6.1f} min  DORUCENE     {e['delivery']}, "
                      f"rameno {e['arm']}, cakalo {e['waited_s']:.1f} s, "
                      f"hlas {'ano' if e['hlas'] else 'nie'}")
            else:
                print(f"  {cas:6.1f} min  ZRUSENE      {e['reason']}, "
                      f"po {e['waited_s']:.1f} s")


def sweep(args):
    print(f"Ako velmi na prahu pauzy zalezi. {args.sedeni} vecerov po "
          f"{args.hodin:g} h, naklonenie {args.naklonenie:g}.")
    print("Pozor: rozdelenie medzier vo vstupe je PREDPOKLAD tohto skriptu,")
    print("nie meranie. Tabulka ukazuje citlivost, nie spravnu hodnotu.")
    print("=" * 74)
    print(f"{'prah pauzy':>11} {'natiah':>8} {'doruc':>7} {'pauzou':>8} "
          f"{'timeout':>8} {'median cakania':>16}")
    print("-" * 74)
    for prah in (1.0, 2.5, 5.0, 10.0, 20.0, 45.0):
        args.pauza = prah
        sucty = [jeden_vecer(args, seed) for seed in range(args.sedeni)]
        cakania = [c for s in sucty for c in s["cakanie"]]
        med = statistics.median(cakania) if cakania else 0.0
        print(f"{prah:>10.1f}s {priemer(sucty, 'natiahnuti'):>8.1f} "
              f"{priemer(sucty, 'doruceni'):>7.1f} "
              f"{priemer(sucty, 'pauzou'):>8.1f} "
              f"{priemer(sucty, 'timeoutom'):>8.1f} {med:>14.1f} s")
    print()
    print("Stlpec 'pauzou' vs 'timeout' je ten podstatny: timeout znamena, ze")
    print("sa na prestavku cakalo 90 s, neprisla, a hlaska sla ticho. Cim viac")
    print("timeoutov, tym menej hlasnych okien - a tym dlhsie meranie.")


if __name__ == "__main__":
    main()
