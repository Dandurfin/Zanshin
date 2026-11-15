"""Cue ladder - the app quiets down by itself when a cue gets in the way (0.2).

    voice  ->  picture  ->  pause

Every session runs on one rung. It is set when the session OPENS from the
saved sessions of the same world and does not change after that (like the
session world, B3-worlds).

The TOP (the loudest allowed rung) is set by the player and the world, not
by the ladder:
  * WORK is picture only - the author's decision from B3-worlds. The
    world is not recomputed here; the caller sends the one B3 sealed at
    opening.
  * the style the player chose (the `cue_style` setting; a question in
    onboarding, the "Ako sa ozyvam" (How I speak up) row in Settings ->
    Sound): "visual" = picture only; "sound" = the voice rung with the words
    muted (the slot plays its sound and shows the picture, neither TTS nor
    the player's own recording is heard); "voice" or a missing key = voice.
    The answer "neviem" (Not sure) in onboarding = voice.
The ladder only goes BELOW the top, never above it.

DOWN, by one rung per session, when:
  * the questionnaire after a session with a cue says "rusila" (it
    disrupted) or "rozhodila ma" (it wound me up),
  * or the player pressed "not now" (Ctrl+Alt+Z) within
    `SNOOZE_PO_HLASKE_S` after a delivered cue - BUT only when the session
    still ran on after it for at least `SNOOZE_POTOM_S` and the verdict of
    that session is not "sadla" (it landed). The author is not sure that
    by that shortcut he does not mean "I'm done"; cues come right
    at the end of rounds, which is also when people stop. So it only
    counts when playing went on.
    Since 24. 9. "not now" does NOT CLOSE the session - it only silences
    the cues and measuring goes on (`app._start_snooze`), so
    `snooze_then_s` is the real time the session still ran after it, and
    the signal can really show up.
UP slowly: by a rung after `NAVRAT_RELACII` sessions with a cue and no
signal. Cue = DELIVERED (the picture really showed, see `_hlasok`); an
undelivered one counts neither towards going back up nor as a session with
a cue for the verdict.
PAUSE lasts `PAUZA_RELACII` sessions of at least `PAUZA_MIN_TRVANIE_S` (or
ends with the verdict "ano, mala" (yes, it should have)) and then the
picture is tried.

Sound as a separate rung is deliberately not here (review stress-cue):
whoever wants sound without words has the "sound" style or the "Zvuk"
(Sound) slot mode. Nor is "voice is worse than picture" measured - there
is no data for that yet.

A pure module (no Tk, no I/O), just like `trigger.py`.
"""

HLAS = "voice"
OBRAZ = "visual"
PAUZA = "pause"
STUPNE = (HLAS, OBRAZ, PAUZA)

# The cue style the player chose (settings key `cue_style`).
STYL_HLAS = "voice"
STYL_ZVUK = "sound"
STYL_OBRAZ = "visual"
STYLY = (STYL_HLAS, STYL_ZVUK, STYL_OBRAZ)

# Strings from `hr_stats` (world, verdicts). Not an import: the module
# stays standalone.
SVET_PRACA = "work"
DOLE_VERDIKTY = ("disruptive", "agitated")
VERDIKT_SADLA = "landed"
VERDIKT_MALA = "missed"

SNOOZE_PO_HLASKE_S = 60.0
SNOOZE_POTOM_S = 120.0
NAVRAT_RELACII = 3
PAUZA_RELACII = 3
PAUZA_MIN_TRVANIE_S = 300.0

# Why the ladder is where it is (`stupen()["dovod"]`).
D_RUSILA = "disruptive"
D_ROZHODILA = "agitated"
D_SNOOZE = "snooze"
D_NAVRAT = "climb"
D_ZNOVA = "retry"
D_MALA = "missed"
# These can stand below the top (and have a sentence in History). `climb`
# cannot: with three rungs going back up always leads all the way to the
# top.
DOVODY_POD_VRCHOLOM = (D_RUSILA, D_ROZHODILA, D_SNOOZE, D_ZNOVA, D_MALA)


def normalize_cue_style(raw):
    """One of `STYLY`; a missing or nonsensical style = voice."""
    return raw if raw in STYLY else STYL_HLAS


def je_tichsi(novy, stary):
    """Is style `novy` quieter than `stary`? `STYLY` go from the loudest."""
    return (STYLY.index(normalize_cue_style(novy))
            > STYLY.index(normalize_cue_style(stary)))


def vrchol(svet, styl):
    """The loudest rung the ladder may reach in this world."""
    if svet == SVET_PRACA:
        return OBRAZ
    if normalize_cue_style(styl) == STYL_OBRAZ:
        return OBRAZ
    return HLAS


def _cislo(hodnota):
    try:
        return float(hodnota)
    except (TypeError, ValueError):
        return None


def _hlasok(session):
    """How many cues the player actually GOT in a session (picture drawn).

    ONLY A DELIVERED CUE COUNTS. `auto_triggers` also counts a cue whose
    picture failed (`note_trigger(delivered=False)`) - the player saw nothing
    of it and the questionnaire told them "I did not speak up", so they had no
    way to complain. The ladder would count such a session as "with a cue and
    no objections" and climb towards the voice out of silence. `cues_delivered`
    (since 0.2.1, `_close_hr_session`) has the same rule as the questionnaire
    and "not now" after a cue (`hr_stats.last_auto_cue_ts`): the silent arm
    counts - the picture showed. Older sessions do not have it and keep
    `auto_triggers`."""
    pocet = _cislo(session.get("cues_delivered"))
    if pocet is None:
        pocet = _cislo(session.get("auto_triggers"))
    try:
        return max(0, int(pocet or 0))
    except (ValueError, OverflowError):
        # NaN / infinity from a hand-edited file - the ladder must not crash.
        return 0


def signal_dole(session):
    """Why the ladder goes one rung lower after this session - or None.

    The verdict takes priority over snooze: it is the player's direct word.
    Per session it is always at most one rung."""
    if not isinstance(session, dict):
        return None
    verdikt = session.get("cue_verdict")
    if _hlasok(session) > 0 and verdikt in DOLE_VERDIKTY:
        return verdikt
    if verdikt == VERDIKT_SADLA:
        # "Sadla" (it landed) and right after "not now" = more "I'm done"
        # than "it got in the way".
        return None
    po = _cislo(session.get("snooze_after_cue_s"))
    potom = _cislo(session.get("snooze_then_s"))
    if (po is not None and 0.0 <= po <= SNOOZE_PO_HLASKE_S
            and potom is not None and potom >= SNOOZE_POTOM_S):
        return D_SNOOZE
    return None


def stupen(sessions, svet="play", styl=STYL_HLAS):
    """Which rung the next session in this world will run on.

    `sessions` are the saved sessions of ONE world (the caller filters them
    through `hr_stats.sessions_in_world`). Imported ones (someone else's
    body) do not count.

    Returns {"stupen", "vrchol", "dovod", "started", "zostava"}: `dovod` and
    `started` say which session moved the ladder last (or None), `zostava`
    how many sessions are left until the next attempt at a louder rung (0
    at the top).
    """
    vrch_meno = vrchol(svet, styl)
    vrch = STUPNE.index(vrch_meno)
    obraz, pauza = STUPNE.index(OBRAZ), STUPNE.index(PAUZA)
    rel = sorted((s for s in sessions or ()
                  if isinstance(s, dict) and not s.get("imported")),
                 key=lambda s: _cislo(s.get("started")) or 0.0)

    st = vrch
    # THE START FROM THE STAMP OF THE OLDEST HELD SESSION. The history gets
    # trimmed after `hr_stats.MAX_SESSIONS` - without this, old records
    # dropping out would silently bring the voice back. The stamp applies only
    # when it was below its OWN top: whoever had the "picture" style and
    # switched to voice should not stay on the picture.
    if rel and rel[0].get("cue_rung") in STUPNE:
        jej = STUPNE.index(rel[0]["cue_rung"])
        if jej > STUPNE.index(vrchol(svet, rel[0].get("cue_style"))):
            st = max(vrch, jej)

    ciste = 0
    v_pauze = 0
    dovod, kedy = None, None
    for s in rel:
        zacala = s.get("started")
        if st == pauza:
            if (_cislo(s.get("duration_s")) or 0.0) >= PAUZA_MIN_TRVANIE_S:
                v_pauze += 1
            if s.get("cue_verdict") == VERDIKT_MALA:
                st, v_pauze, ciste = obraz, 0, 0
                dovod, kedy = D_MALA, zacala
            elif v_pauze >= PAUZA_RELACII:
                st, v_pauze, ciste = obraz, 0, 0
                dovod, kedy = D_ZNOVA, zacala
            continue
        dole = signal_dole(s)
        if dole:
            st = min(pauza, st + 1)
            ciste = 0
            dovod, kedy = dole, zacala
        elif _hlasok(s) > 0:
            ciste += 1
            if ciste >= NAVRAT_RELACII and st > vrch:
                st, ciste = st - 1, 0
                dovod, kedy = D_NAVRAT, zacala
        # Never above the top (the style may have got quieter in the meantime).
        st = max(st, vrch)

    if st == pauza:
        zostava = PAUZA_RELACII - v_pauze
    elif st > vrch:
        zostava = NAVRAT_RELACII - ciste
    else:
        zostava = 0
    return {"stupen": STUPNE[st], "vrchol": vrch_meno, "dovod": dovod,
            "started": kedy, "zostava": zostava}
