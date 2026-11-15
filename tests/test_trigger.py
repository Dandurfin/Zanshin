# -*- coding: utf-8 -*-
"""Cue state machine — arming, postponing to a pause, the silent arm.

The clock is faked, so the tests wait for nothing in real time and the
90-second dwell is simulated instantly.

Most of the tests below exist because exactly those cases were marked by
the adversarial design review as places where the measurement would
silently break: merging `arm` and `delivery`, a missing return from
cooldown, a dip tolerance that would turn "continuously above 55" into
"not once below 45".
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trigger  # noqa: E402


class Hodiny:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def posun(self, o):
        self.t += o


def spusti(silent_share=0.0, rng_seed=1, **params):
    """State machine with a fixed generator, so the arm is predictable."""
    h = Hodiny()
    t = trigger.CueTrigger(params=params, rng=random.Random(rng_seed), clock=h)
    t.open_session(silent_share=silent_share)
    return t, h


def natiahni(t, h, stress=80.0, krok=1.0, zona="high"):
    """Hold load above the threshold until it arms. Returns the arming event.

    `zona` is the heart-rate band for the gate (0.2): "high" = known and
    not critical, load is steady — the gate lets it through. Without a band
    (None) the cue would not go at all."""
    for _ in range(200):
        ev = t.note_load(stress, h.t, zona=zona)
        if ev:
            return ev
        h.posun(krok)
    raise AssertionError("nenatiahlo sa")


# --------------------------------------------------------------------------
# Arming
# --------------------------------------------------------------------------

def test_spicka_nenatiahne():
    """A jump after a headshot is not stress. Two minutes at 120 is."""
    t, h = spusti()
    for _ in range(10):                 # 10 s of high load
        assert t.note_load(95.0, h.t) is None
        h.posun(1.0)
    assert t.state == trigger.RISING
    assert not t.is_armed


def test_zotrvanie_nad_prahom_natiahne():
    t, h = spusti()
    ev = natiahni(t, h)
    assert ev["typ"] == trigger.E_ARMED
    assert t.is_armed


def test_kratky_prepad_natiahnutie_nezrusi():
    """`stress` is smoothed by an exponential average and oscillates at the
    threshold. Three seconds below the threshold must not knock it down."""
    t, h = spusti()
    for _ in range(40):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(3):                  # a short dip
        t.note_load(40.0, h.t)
        h.posun(1.0)
    for _ in range(60):
        ev = t.note_load(80.0, h.t)
        if ev:
            break
        h.posun(1.0)
    assert t.is_armed


def test_dlhy_prepad_natiahnutie_zrusi():
    # The tolerance is set explicitly here. Before, the test relied on the
    # default value and failed the moment it changed from 5 s to 20 s — even
    # though nothing changed in the behaviour it checks.
    t, h = spusti(dip_grace_s=5.0)
    for _ in range(40):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(10):                 # a dip longer than the tolerance
        t.note_load(40.0, h.t)
        h.posun(1.0)
    assert t.state == trigger.IDLE
    assert t._above_since is None


def test_cas_pod_prahom_sa_do_zotrvania_nepocita():
    """A guard against a bug found by the design review: "continuously above
    55" must not degenerate into "not once below 45".

    Load oscillating just below the threshold must not arm, however long
    it runs.
    """
    t, h = spusti()
    for _ in range(300):
        assert t.note_load(50.0, h.t) is None    # below the threshold of 55
        h.posun(1.0)
    assert not t.is_armed


# --------------------------------------------------------------------------
# Postponing to a pause
# --------------------------------------------------------------------------

def test_pauza_dorucí_hlasku():
    t, h = spusti()
    natiahni(t, h)
    assert t.tick(pause_s=0.0, now=h.t) is None      # playing, not delivered
    h.posun(5.0)
    ev = t.tick(pause_s=3.0, now=h.t)
    assert ev["typ"] == trigger.E_DELIVER
    assert ev["delivery"] == trigger.D_PAUSE
    assert ev["hlas"] is True


def _drz(t, h, sekund, stress=80.0, zona="high", pause_s=0.0, krok=1.0):
    """HR samples and ticks while waiting, as in the app. Returns events."""
    udalosti = []
    for _ in range(int(sekund / krok)):
        h.posun(krok)
        t.note_load(stress, h.t, zona=zona)
        ev = t.tick(pause_s=pause_s, now=h.t)
        if ev:
            udalosti.append(ev)
    return udalosti


def test_ked_pauza_nepride_ide_tichy_vizual():
    """0.2: the silent picture after max_wait_s stays — but only when the gate
    lets it through (band known and not critical, load not rising).
    Otherwise the arming is cancelled."""
    t, h = spusti()
    natiahni(t, h)
    ev = _drz(t, h, 91.0)[0]                         # max_wait_s has passed
    assert ev["typ"] == trigger.E_DELIVER
    assert ev["delivery"] == trigger.D_TIMEOUT
    assert ev["hlas"] is False                       # no voice
    assert ev["arm"] == trigger.ARM_VOICE            # but the arm is the voice arm!

    t, h = spusti()
    natiahni(t, h, zona="critical")
    ev = _drz(t, h, 91.0, zona="critical")[0]        # over the heart-rate limit
    assert ev["typ"] == trigger.E_ABORT, "obrázok nesmie ísť nad hranicou"
    assert ev["reason"] == trigger.A_BEZ_PAUZY

    t, h = spusti()
    natiahni(t, h)
    udalosti = []
    for i in range(91):                              # load still rising
        h.posun(1.0)
        t.note_load(80.0 + i, h.t, zona="high")
        ev = t.tick(pause_s=0.0, now=h.t)
        if ev:
            udalosti.append(ev)
    assert [e["typ"] for e in udalosti] == [trigger.E_ABORT]
    assert udalosti[0]["reason"] == trigger.A_BEZ_PAUZY


def test_timeout_nie_je_tiche_rameno():
    """The most important test in the file.

    When the pause does not come, the cue goes silently — but it is NOT the
    control arm. If both were recorded as arm="silent", measure.summarize()
    would compare two different things: one group had a pause, the other
    did not, and the difference between the arms would measure exactly
    that.

    And without a pause the voice does not sound even in the voice arm —
    ever.
    """
    t, h = spusti(silent_share=0.0)                  # never draw silence
    natiahni(t, h)
    udalosti = _drz(t, h, 91.0)
    assert len(udalosti) == 1
    ev = udalosti[0]
    assert ev["hlas"] is False                       # did not sound
    assert ev["arm"] == trigger.ARM_VOICE            # but belongs to the voice arm
    assert ev["delivery"] == trigger.D_TIMEOUT       # and the reason is recorded


def test_odchod_od_pc_nie_je_pauza():
    t, h = spusti()
    natiahni(t, h)
    ev = t.tick(pause_s=200.0, now=h.t)
    assert ev["typ"] == trigger.E_ABORT
    assert ev["reason"] == trigger.A_ODISIEL


def test_neznama_pauza_nedoruci_hned_ale_ani_necaka_navzdy():
    """pause_s() returns None when the system does not report idle.

    That must not pretend to be "there is a pause" (it would be delivered
    at once), nor "there is never a pause". max_wait_s is let run out and
    then the same applies as without a pause: a silent picture via the
    gate, voice never.
    """
    t, h = spusti()
    natiahni(t, h)
    assert t.tick(pause_s=None, now=h.t) is None
    udalosti = _drz(t, h, 91.0, pause_s=None)
    assert len(udalosti) == 1
    ev = udalosti[0]
    assert ev["delivery"] == trigger.D_TIMEOUT
    assert ev["hlas"] is False
    assert t.pause_episodes == 0, "neznáma pauza nie je pauza"

    # ... and above the high heart-rate limit not even a picture
    t, h = spusti()
    natiahni(t, h, zona="critical")
    udalosti = _drz(t, h, 91.0, zona="critical", pause_s=None)
    assert [e["typ"] for e in udalosti] == [trigger.E_ABORT]


def test_ked_sa_nesmie_natiahnutie_sa_nespali():
    """can_fire=False (cooldown, visual off) does not cancel the arming —
    it keeps waiting."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=5.0, now=h.t, can_fire=False) is None
    assert t.is_armed
    ev = t.tick(pause_s=5.0, now=h.t, can_fire=True)
    assert ev["typ"] == trigger.E_DELIVER


# --------------------------------------------------------------------------
# Cooldown
# --------------------------------------------------------------------------

def test_po_hlaske_sa_da_natiahnut_znova():
    """The design review found a version in which the transition from
    cooldown back did not exist — after the first cue the session would
    never trigger anything again."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=3.0, now=h.t)["typ"] == trigger.E_DELIVER
    assert t.state == trigger.COOLDOWN

    h.posun(300.0)                                   # more than min_gap_s
    t.tick(pause_s=0.0, now=h.t)
    assert t.state == trigger.IDLE
    natiahni(t, h)
    assert t.is_armed


def test_odstup_je_dlhsi_nez_refrakterna_zona():
    """min_gap_s must be greater than measure.REFRACTORY_AFTER_S (180 s).

    Otherwise two cues invalidate each other's measurement windows and a
    month of measuring is worthless.
    """
    import measure
    assert trigger.default_params()["min_gap_s"] > measure.REFRACTORY_AFTER_S


# --------------------------------------------------------------------------
# Silent arm
# --------------------------------------------------------------------------

def test_rameno_sa_losuje_uz_pri_natiahnuti():
    """So it can be recorded even when the cue ends up not delivered."""
    t, h = spusti(silent_share=1.0)
    ev = natiahni(t, h)
    assert ev["arm"] == trigger.ARM_SILENT


def test_tiche_rameno_nezaznie_ale_dorucí_sa():
    t, h = spusti(silent_share=1.0)
    natiahni(t, h)
    h.posun(5.0)
    ev = t.tick(pause_s=3.0, now=h.t)
    assert ev["typ"] == trigger.E_DELIVER            # the window is recorded
    assert ev["delivery"] == trigger.D_PAUSE         # the pause really came
    assert ev["hlas"] is False                       # it just does not sound


def test_podiel_ticha_klesne_po_kalibracii():
    assert trigger.silent_share_for(0) == 0.25
    assert trigger.silent_share_for(14) == 0.25
    assert trigger.silent_share_for(15) == 0.10
    assert trigger.silent_share_for(400) == 0.10


def test_podiel_ticha_nikdy_nie_je_nula():
    """Without a control arm, "it works" always comes out, even if the app
    stayed silent — heart rate comes back down on its own too."""
    for n in (0, 15, 100, 10000):
        assert trigger.silent_share_for(n) > 0


def test_losovanie_nezavisi_od_modulového_random():
    """`app.fire_slot` uses random.uniform for jitter. If the state machine
    drew from the module's generator, any random.seed() elsewhere in the
    app would shift the arm too and the control group would stop being
    random."""
    vysledky = []
    for _ in range(2):
        random.seed(12345)
        t, h = spusti(silent_share=0.5, rng_seed=7)
        vysledky.append(natiahni(t, h)["arm"])
    assert vysledky[0] == vysledky[1]


# --------------------------------------------------------------------------
# Interruptions
# --------------------------------------------------------------------------

def test_snooze_zrusi_natiahnutie():
    t, h = spusti()
    natiahni(t, h)
    ev = t.suspend(trigger.A_SNOOZE, now=h.t)
    assert ev["reason"] == trigger.A_SNOOZE
    assert t.state == trigger.DORMANT
    assert t.tick(pause_s=5.0, now=h.t) is None      # during snooze not even a visual


def test_vypadok_tepu_zrusi_natiahnutie_a_pocita_sa_odznova():
    t, h = spusti()
    natiahni(t, h)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(now=h.t)
    assert t.state == trigger.IDLE
    for _ in range(10):                              # 10 s is not enough
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert not t.is_armed                            # 90 s counts from scratch


def test_koniec_relacie_v_stave_cakania_sa_zapise():
    """How often this happens can be used to tune max_wait_s."""
    t, h = spusti()
    natiahni(t, h)
    h.posun(30.0)
    ev = t.close_session(now=h.t)
    assert ev["reason"] == trigger.A_KONIEC_RELACIE
    assert ev["waited_s"] == 30.0


# --------------------------------------------------------------------------
# Developer overlay — parameters only between sessions (§3.3)
# --------------------------------------------------------------------------

def _zdroj(meno):
    # utf-8-sig, not utf-8: app.py has a BOM at the start and `ast.parse`
    # fails on it with "invalid non-printable character U+FEFF".
    cesta = os.path.join(os.path.dirname(__file__), "..", meno)
    return open(cesta, encoding="utf-8-sig").read()


def _telo(meno_suboru, meno_funkcie):
    """Function body as code, WITHOUT the docstring and comments.

    Searching for a substring in the raw source is a trap: the docstring
    often explains why something is NOT USED, and the test fails on that.
    That is why the AST is read and the docstring is thrown away.
    """
    import ast
    if meno_suboru == "app.py":
        # the whole app: app.py and the DandurfApp mixins in app_*.py
        from _zdroj_appky import strom_appky
        strom = strom_appky()
    else:
        strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno_funkcie:
            telo = uzol.body
            if (telo and isinstance(telo[0], ast.Expr)
                    and isinstance(telo[0].value, ast.Constant)
                    and isinstance(telo[0].value.value, str)):
                telo = telo[1:]
            return "\n".join(ast.unparse(p) for p in telo)
    raise AssertionError(f"{meno_funkcie} sa v {meno_suboru} nenašla")


def _telo_metody(meno_suboru, trieda, metoda):
    """Body of a method of a SPECIFIC class.

    `_telo` takes the first function of the given name in the file — and
    that is a trap: when `_StateDot.set_live` was added to `ui_shell.py`,
    the enso test started reading someone else's method and failed. The
    name alone is not enough.
    """
    import ast
    strom = ast.parse(_zdroj(meno_suboru))
    for uzol in ast.walk(strom):
        if not (isinstance(uzol, ast.ClassDef) and uzol.name == trieda):
            continue
        for pod in uzol.body:
            if isinstance(pod, ast.FunctionDef) and pod.name == metoda:
                telo = pod.body
                if (telo and isinstance(telo[0], ast.Expr)
                        and isinstance(telo[0].value, ast.Constant)
                        and isinstance(telo[0].value.value, str)):
                    telo = telo[1:]
                return chr(10).join(ast.unparse(x) for x in telo)
        raise AssertionError(f"{trieda}.{metoda} sa nenašla")
    raise AssertionError(f"trieda {trieda} sa v {meno_suboru} nenašla")


def test_nove_prahy_sa_beru_az_pri_novej_relacii():
    """Changing thresholds mid-session means measuring a moving target.

    Windows from the first half of the evening and from the second could
    not be compared and nobody could tell afterwards which was which. That
    is why `_dev_params` are read in `start_heart_rate_monitor`, not on
    save in the dialog.
    """
    # The logic sits in `_open_hr_session`; `start_heart_rate_monitor` is now
    # just "open the session + start the socket". BOTH halves of the chain
    # are guarded, otherwise the delegation could be silently removed.
    assert "_open_hr_session" in _telo("app.py", "start_heart_rate_monitor")
    assert "_dev_params" in _telo("app.py", "_open_hr_session"), \
        "start_heart_rate_monitor musí brať prahy z vývojárskej vrstvy"


def test_dialog_ladenia_zamkne_polia_pocas_relacie():
    """It is not a recommendation in the text — the fields really lock."""
    src = _zdroj("ui_dialogs.py")
    blok = src[src.index("class DevLayerDialog"):]
    blok = blok[:blok.index("\nclass ", 5)]
    assert "_hr_session_open" in blok, "dialóg sa musí pýtať, či relácia beží"
    assert 'state="disabled"' in blok, "polia sa počas relácie musia zamknúť"


def test_vynutena_hlaska_nejde_do_merania():
    """`dev_force_cue` bypasses the state machine on purpose.

    A forced cue is not a measurement — if it were recorded into windows,
    it would burn the refractory zone around a real cue and pollute the
    data exactly while tuning, i.e. when it is clicked most often.
    """
    telo = _telo("app.py", "dev_force_cue")
    assert "note_trigger" not in telo, "vynútená hláška sa nesmie zapísať do relácie"
    assert "cue_trigger" not in telo, "vynútená hláška nesmie ísť cez automat"


def test_pocitadla_sedia():
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    t.tick(pause_s=3.0, now=h.t)
    s = t.snapshot()
    assert s["armed_count"] == 1 and s["delivered_count"] == 1


# --------------------------------------------------------------------------
# Hourly cap (spec §2)
# --------------------------------------------------------------------------

def _doruc(t, h):
    """Runs the whole cycle up to delivery. Returns the event or None."""
    for _ in range(400):
        ev = t.note_load(80.0, h.t, zona="high")
        h.posun(1.0)
        if ev and ev["typ"] == trigger.E_ARMED:
            h.posun(5.0)
            return t.tick(pause_s=3.0, now=h.t)
    return None


def test_strop_zastavi_po_piatich_za_hodinu():
    """`min_gap_s` alone is not enough — a 240 s gap allows up to 15 cues/hour.

    A simulation measured 6.9 per hour on a tense evening, i.e. above the
    spec.
    """
    t, h = spusti()
    for i in range(5):
        ev = _doruc(t, h)
        assert ev is not None and ev["typ"] == trigger.E_DELIVER, f"{i + 1}. hláška"
    # the sixth must not even arm
    for _ in range(600):
        assert t.note_load(80.0, h.t) is None, "šiesta hláška prekročila strop"
        h.posun(1.0)
    assert t.delivered_count == 5


def test_strop_pusti_dalsiu_ked_najstarsia_vyprsi():
    """The window is sliding — an hour after the first cue a slot frees up."""
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    prva = t._delivered_at[0]
    # move to just past an hour after the first
    h.t = prva + trigger.HOUR_S + 1.0
    ev = _doruc(t, h)
    assert ev is not None and ev["typ"] == trigger.E_DELIVER
    assert t.delivered_count == 6


def test_strop_sa_neda_obist_restartom_relacie():
    """Switching the sensor off and on must not reset the cap.

    "Five per hour" is about the player, not the session — and the player
    would restart exactly when the app annoys them, i.e. they would get
    more, not fewer.
    """
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    t.close_session(now=h.t)
    t.open_session(silent_share=0.0)
    for _ in range(600):
        assert t.note_load(80.0, h.t) is None, "reštart relácie obišiel strop"
        h.posun(1.0)


def test_strop_sa_da_vypnut_nulou():
    """The developer overlay must be able to switch off the cap — without it
    nothing that needs many cues in a short time can be tuned."""
    t, h = spusti(max_per_hour=0)
    for i in range(8):
        ev = _doruc(t, h)
        assert ev is not None, f"{i + 1}. hláška pri vypnutom strope"
    assert t.delivered_count == 8


def test_vycerpany_strop_nenatiahne_prstenec():
    """Arming and not delivering would mean the ring on the enso is lit and
    nothing comes. With the cap used up it therefore does not arm at all."""
    t, h = spusti()
    for _ in range(5):
        assert _doruc(t, h) is not None
    for _ in range(600):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.is_armed is False
    assert t.armed_count == 5, "natiahlo sa viackrát, než sa doručilo"


# --------------------------------------------------------------------------
# The "armed" ring on the enso
# --------------------------------------------------------------------------

def test_prstenec_sa_zhadzuje_na_kazdej_ceste_von_z_natiahnutia():
    """A forgotten path = a ring that is lit forever.

    It is the quietest possible failure: the state machine is fine, the
    measurement is fine, only the mark lies. Nothing in the app catches it
    - `CueTrigger` does not know about the UI and the UI has no way to find
    out that an event got lost somewhere.

    Four paths lead out of the ARMED state and each must drop the ring.
    """
    cesty = {
        "_on_cue_event": "dorucenie aj zrusenie",
        "_suspend_cue_trigger": "snooze a vypadok tepu",
        "_close_hr_session": "koniec relacie",
    }
    for meno, preco in cesty.items():
        telo = _telo("app.py", meno)
        assert "_set_enso_armed" in telo, f"{meno} ({preco}) nezhadzuje prstenec"

    # The fourth path is in the widget: when listening stops, the arming no
    # longer holds and `set_live(False)` must drop it itself. If only the app
    # did it, after switching listening off and on the ring would light at
    # once.
    telo = _telo_metody("ui_shell.py", "_EnsoButton", "set_live")
    assert "_armed" in telo, "set_live(False) musí zahodiť natiahnutie"


def test_ikona_hodiniek_zapina_a_nikdy_nevypina():
    """Spec §1.10. Before, the icon only opened the dialog — over a switched
    off sensor, so the player followed the panel and the app received
    nothing.

    And above all: it must not switch off. An icon that switches on one
    time and off another is unreadable for a single pictogram without a
    label.
    """
    telo = _telo("app.py", "open_watch_pairing")
    assert "_enable_hr_monitoring" in telo, "ikona hodiniek nezapína senzor"

    zapnutie = _telo("app.py", "_enable_hr_monitoring")
    assert "hr_monitoring_enabled = True" in zapnutie
    assert "= False" not in zapnutie, "cez ikonu sa nesmie dať vypnúť"
    assert "stop_heart_rate_monitor" not in zapnutie


def test_zapnutie_senzora_nezahodi_beziacu_relaciu():
    """`start_heart_rate_monitor` calls `hr_stats.reset_session()`. Calling
    it on a running session would throw away a whole evening of collected
    data just because the player opened the pairing panel."""
    telo = _telo("app.py", "_enable_hr_monitoring")
    assert "if self.hr_monitoring_enabled:" in telo and "return False" in telo, \
        "_enable_hr_monitoring sa musí vrátiť skôr, keď senzor už beží"


def test_enso_sleduje_temu_nie_stav():
    """PREMIUM REDESIGN (2026-09, decision "by theme"): the enso has a colour
    by THEME (style.accent - gold in Sumi, blue in Aizome), NOT by state.
    The state (listening/not) is carried by the MOVEMENT of the breathing
    bar + the dot in the panel (_StateDot). render_enso therefore MUST NOT
    reach for the state colours (success/danger) - those belong to the dot
    and the bar - and MUST use accent.
    """
    import ast
    strom = ast.parse(_zdroj("hud_paint.py"))
    telo = None
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == "render_enso":
            telo = ast.unparse(uzol)
            break
    assert telo is not None, "render_enso sa nenasla"
    najdene = {f"style.{u.attr}" for u in ast.walk(ast.parse(telo))
               if isinstance(u, ast.Attribute)
               and isinstance(u.value, ast.Name) and u.value.id == "style"}
    stavove = {"style.success", "style.danger"}
    assert not (najdene & stavove), (
        "render_enso siaha na STAVOVE farby (patria bodke/pasu): "
        + repr(sorted(najdene & stavove)))
    assert "style.accent" in najdene, "enso ma mat farbu TEMY (style.accent)"

# --------------------------------------------------------------------------
# Today header — state instead of numbers
# --------------------------------------------------------------------------

def test_pas_a_prstenec_citaju_ten_isty_priznak():
    """One source of truth, not two.

    The first version had the ring from the argument of `_set_enso_armed`
    and the bar text derived the state again from `cue_trigger.is_armed`.
    In the app it happened to match, in the preview it no longer did - the
    bar said "Listening" while the ring was lit. They always drift apart,
    just not right away.
    """
    zapis = _telo("app.py", "_set_enso_armed")
    assert "_cue_armed = armed" in zapis, \
        "_set_enso_armed musí byť jediné miesto, kde sa príznak zapisuje"
    assert "_refresh_kamae_state_text" in zapis, \
        "text pásu sa musí meniť spolu s prstencom"

    citanie = _telo("app.py", "_kamae_state_text")
    assert "_cue_armed" in citanie
    assert "is_armed" not in citanie, \
        "text pásu si stav nesmie odvodzovať znova z automatu"


def test_pas_ma_tri_stavy():
    """Stopped / listening / armed. The third is the whole point of the
    change: "armed" could until now only be read from the ring, and that
    is 68 px.

    "Stopped" has had two wordings since then — the app can start by
    itself when a game starts, but only with automatic profile switching
    on. The choice between them lives in `_kamae_zastavene`, which is why
    both bodies are read: the state must exist, not necessarily on one
    line.
    """
    telo = _telo("app.py", "_kamae_state_text") + _telo("app.py", "_kamae_zastavene")
    for kluc in ("kamae.stopped", "kamae.running", "kamae.armed"):
        assert kluc in telo, f"chýba stav {kluc}"


def test_veta_o_starte_pri_hre_plati_len_ked_je_zapnuty():
    """The app starts by itself only with `auto_profile_enabled`.

    One sentence for both states would lie in the second one — and the
    comment in `app.py` about the fourth state of the bar says exactly what
    such a sentence does: the player goes to play thinking the app is
    running, and waits the whole evening for a cue that has nowhere to come
    from.
    """
    telo = _telo("app.py", "_kamae_zastavene")
    assert "auto_profile_enabled" in telo
    assert "kamae.stopped_sub_auto" in telo and "kamae.stopped_sub" in telo
    # and that promise must really be covered by the code that does the start
    assert "start_listening" in _telo("app.py", "_handle_game_found")


def test_pas_neukazuje_odpocet():
    """Measuring the player's own state before their eyes is exactly what the
    app must not do. The sentence says it is waiting — a number does not
    belong there."""
    telo = _telo("app.py", "_kamae_state_text")
    for zakazane in ("max_wait_s", "_armed_at", "time.time()", "waited"):
        assert zakazane not in telo, f"do textu pásu sa dostal odpočet: {zakazane}"


def test_riadok_o_poslednej_hlaske_sa_skryva():
    """While nothing has happened in the session, the line is not shown. An
    empty line with a zero would be a counter, and the app should show
    state, not a score."""
    telo = _telo("app.py", "_refresh_last_cue")
    # Since the centre was rebuilt onto a Canvas the line is not a widget — it
    # is hidden by `_dnes_lastcue_text` being empty (`_paint_dnes_canvas` then
    # does not draw it).
    assert "_dnes_lastcue_text" in telo, "bez hlášky sa riadok musí schovať"
    assert "if not cues" in telo or "not cues" in telo


def test_riadok_o_hlaske_sa_nepakuje_do_scrollable_frame():
    """`CTkScrollableFrame` is a composite widget — `dnes_body` is the inner
    frame on the canvas, but what gets packed into `wrap` is its outer
    wrapper, so `pack(before=...)` on it fails with TclError "isn't
    packed" — and it failed silently.

    After the rebuild the line sits in the middle column and needs no
    anchor. The test stays as a guard so that path does not come back."""
    telo = _telo("app.py", "_refresh_last_cue")
    assert "before=self.dnes_body" not in telo
    assert "dnes_body" not in telo


# --------------------------------------------------------------------------
# Pausing: what heart rate may lift and what not
# --------------------------------------------------------------------------

def test_tep_nezdvihne_snooze():
    """The worst bug the review found.

    `resume()` is called from `_apply_hr_bpm`, i.e. EVERY SECOND. While it
    did not know why the state machine was paused, the first heartbeat a
    second later cancelled "not now". Measured: during a 30-minute snooze
    it armed 10 times and an inflated `natiahnuti` was written into every
    measurement window of the session.
    """
    t, h = spusti()
    t.suspend(trigger.A_SNOOZE, now=h.t)
    for _ in range(1800):                       # half an hour of heart-rate samples
        t.resume(h.t)                           # exactly like _apply_hr_bpm
        assert t.note_load(80.0, h.t) is None, "tep zdvihol snooze"
        h.posun(1.0)
    assert t.state == trigger.DORMANT
    assert t.armed_count == 0, f"natiahlo sa {t.armed_count}x počas snooze"


def test_vedome_zdvihnutie_snooze_funguje():
    t, h = spusti()
    t.suspend(trigger.A_SNOOZE, now=h.t)
    t.resume(h.t, force=True)
    assert t.state == trigger.IDLE
    natiahni(t, h)
    assert t.is_armed


def test_vypadok_tepu_zdvihne_prva_vzorka():
    """This one `resume()` without `force` MUST lift — it is exactly the case
    it was written for."""
    t, h = spusti()
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(h.t)
    assert t.state == trigger.IDLE


def test_pozastavenie_nezmaze_odstup_medzi_hlaskami():
    """The second half of the same bug.

    `_cooldown_until` is read ONLY in the COOLDOWN state. When pausing went
    straight to IDLE, one heart-rate dropout erased four minutes of gap —
    and that gap must be greater than `measure.REFRACTORY_AFTER_S`,
    otherwise two cues invalidate each other's measurement windows.
    """
    t, h = spusti()
    natiahni(t, h)
    h.posun(5.0)
    assert t.tick(pause_s=3.0, now=h.t)["typ"] == trigger.E_DELIVER
    assert t.state == trigger.COOLDOWN

    h.posun(10.0)                                # still deep in the gap
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    t.resume(h.t)
    assert t.state == trigger.COOLDOWN, "odstup sa stratil pri výpadku tepu"

    # and after the gap has passed it continues normally
    h.posun(trigger.default_params()["min_gap_s"] + 1.0)
    t.tick(pause_s=0.0, now=h.t)
    assert t.state == trigger.IDLE


def test_appka_zdvihne_spustac_na_vsetkych_troch_cestach():
    """Three paths lead out of snooze and `start_listening` is only called
    conditionally — with snooze started in a non-listening state the
    trigger would stay paused forever."""
    for meno in ("_cancel_snooze", "start_listening"):
        assert "_resume_cue_trigger" in _telo("app.py", meno), meno
    # snooze expiry is a nested function in _start_snooze
    assert "_resume_cue_trigger" in _telo("app.py", "_start_snooze")


def test_zmena_ip_uprostred_relacie_nezahodi_vecer():
    """`start_heart_rate_monitor` calls `hr_stats.reset_session()`, which
    deletes both `cues` and `_all`. Without a proper close the measurement
    windows would have nothing to be built from — and the only way here
    with an open session is changing the IP/port in the middle of the
    evening."""
    assert "_open_hr_session" in _telo("app.py", "start_heart_rate_monitor")
    telo = _telo("app.py", "_open_hr_session")
    assert "_close_hr_session" in telo
    assert telo.index("_close_hr_session") < telo.index("reset_session"), \
        "zatvoriť sa musí PRED vynulovaním"


def test_tiche_rameno_sa_neda_vypnut_nedopatrenim():
    """The tuning dialog was prefilled from `cue_trigger.silent_share`, which
    is 0.0 before the first session. Whoever opened it and pressed Save
    without touching that field switched off the control arm for the whole
    app run — silently."""
    telo = _telo("app.py", "_silent_share_for_next_session")
    assert "if not podiel" in telo, "nula sa musí brať ako nedopatrenie"
    assert "silent_share_for" in telo


def test_riadok_o_hlaske_sa_obnovuje_aj_bez_tepu():
    """All the other paths to `_refresh_dnes_stats` hang on incoming heart
    rate. After a watch dropout the "X min ago" number would freeze and lie
    forever."""
    assert "_refresh_last_cue" in _telo("app.py", "_tick_session")


def test_prestavba_okna_zosuladi_prstenec():
    """A rebuild (language change) builds the ensō anew with `_armed=False`,
    while `self._cue_armed` keeps holding the state. `set_live` does not
    save it — it drops that flag only on a True → False transition."""
    telo = _telo("app.py", "_apply_listening_visuals")
    assert "set_armed" in telo and "_cue_armed" in telo


# --------------------------------------------------------------------------
# Window rebuild: the mark to the centre, the switch into the bar
# --------------------------------------------------------------------------

def test_znacka_sa_stavia_na_stranke_nie_v_paneli():
    """Since 2.1 it sits in the centre of the page. In the panel it had 68 px
    and the "armed" ring at that size 1.4 px. Since the centre was rebuilt
    onto a Canvas it is `_EnsoHero` (a drawing, not a widget) - so the
    enso floats on the dojo without a box."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "_EnsoHero" in telo, "značka sa musí stavať na stránke Dnes"
    assert "ENSO_SIZE" in telo

    import app as app_mod
    assert app_mod.DandurfApp.ENSO_SIZE >= 120


def test_stred_dnes_je_canvas_bez_boxu():
    """The enso + text must float on the dojo, not sit on a dark square.

    A CTk widget cannot be transparent over a photo (`fg_color="transparent"`
    inherits the parent's solid colour), so any frame/label over the dojo
    stayed as a box. That is why the centre is drawn on a `tk.Canvas`
    (`create_image` for the transparent enso, `create_text` for text). The
    test guards that the box does not come back."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "tk.Canvas" in telo and "dnes_canvas" in telo, \
        "stred Dnes sa má kresliť na Canvas"
    # An opaque frame in the background colour must NEVER come back into the
    # centre - that was exactly the "square".
    assert 'ctk.CTkFrame(stred, fg_color=pal["bg"])' not in telo, \
        "nepriehľadný box v strede je späť"
    # the enso and the dojo are both IMAGES on the Canvas (create_image in the
    # layout); in the paint loop they are only swapped via itemconfigure (no
    # flicker).
    layout = _telo("app.py", "_layout_dnes_items")
    assert "create_image" in layout, "enso aj dojo sú obrázky na Canvase"
    paint = _telo("app.py", "_paint_dnes_canvas")
    assert "itemconfigure" in paint, "snímky sa vymieňajú v mieste (proti blikaniu)"
    text = _telo("app.py", "_canvas_text")
    assert "create_text" in text, "text sa kreslí bez pozadia (create_text)"


def test_sidebar_uz_znacku_nestavia():
    src = _zdroj("ui_shell.py")
    i = src.index("class Sidebar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_EnsoButton(" not in telo, "Sidebar už značku nestavia"


def test_alias_sidebar_enso_ostava():
    """`guided_tour.py` and both harnesses look up the mark as
    `app.sidebar.enso` and look it up BY NAME — on a rename they would fail
    SILENTLY (the tour bubble would just stop pointing at anything)."""
    telo = _telo("app.py", "_build_ui")
    assert "self.sidebar.enso = self.enso" in telo


def test_spinac_je_v_pase_a_nie_na_znacke():
    """The mark stopped being a hidden button. The control has its own
    visible element and NOW ONLY it toggles — a click elsewhere in the bar
    does nothing."""
    src = _zdroj("ui_kit.py")
    i = src.index("class KamaeBar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "BTN_X" in telo and "_v_spinaci" in telo
    assert "def _clicked" in telo
    # a click outside the switch must not toggle
    j = telo.index("def _clicked")
    klik = telo[j:telo.index("def ", j + 10)]
    assert "_v_spinaci" in klik, "prepína aj klik mimo spínača"


def test_znacka_sa_dokresluje_na_pozadi():
    """At 150 px the whole set costs 283 ms — and it would be paid on every
    start and every theme change, against a budget of ~673 ms per theme."""
    src = _zdroj("ui_shell.py")
    i = src.index("class _EnsoButton")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_build_step" in telo and "_build_queue" in telo
    assert "BIG_PX" in telo, "veľká značka sa má kresliť s nižším prevzorkovaním"
    # both chains must be cancelled
    j = telo.index("def destroy")
    znic = telo[j:telo.index("def ", j + 10)]
    assert "_cancel_build" in znic and "_after_id" in znic


def test_pozadie_ma_vsetko_v_jednom_module():
    """Whoever changes the photo changes `background.py` and nothing else.
    The centre photo is built by `_build_dojo_photo` (dojo/dimmed → PIL →
    ImageTk for the Canvas)."""
    telo = _telo("app.py", "_build_dojo_photo")
    assert "background.load" in telo
    assert ".jpg" not in telo and ".png" not in telo


def test_stav_sa_da_precitat_aj_mimo_stranky_dnes():
    """Both the mark and the breathing bar are children of the Today page.
    Without the indicator in the side panel, on History, In-game, Sound and
    Settings there would be nothing in the window that says whether the
    app is listening — that is a loss of capability, not a change of look.
    """
    src = _zdroj("ui_shell.py")
    assert "class _StateDot" in src
    i = src.index("class Sidebar")
    telo = src[i:src.index("\nclass ", i + 1)]
    assert "_StateDot(" in telo, "kontrolka musí byť v bočnom paneli"

    # and it must toggle together with the state
    assert "state_dot" in _telo("app.py", "_apply_listening_visuals")


def test_kontrolka_nie_je_druhe_tlacidlo():
    """There is one switch and it is in the breathing bar. Two places where
    the app can be started is exactly what the rebuild avoided."""
    telo = _telo_metody("ui_shell.py", "_StateDot", "__init__")
    assert "on_toggle" not in telo and "Button-1" not in telo


def test_stav_je_vyplneny_uz_pri_stavbe():
    """Otherwise the text is written only from `_apply_listening_visuals` and
    `_set_enso_armed`, and neither runs while the window is built - after
    a fresh start the mark stood above an empty spot. It shows in
    logs/gui_screenshots/01_dnes.png."""
    telo = _telo("app.py", "_build_dnes_page")
    assert "_refresh_dnes_state_text" in telo


def test_pozadie_sa_nekresli_1_5x_vacsie():
    """DPI: `winfo_*` on the Canvas are already PHYSICAL pixels. That is why
    the dojo is built 1:1 at (w, h) and the enso and fonts are scaled by
    `get_widget_scaling` (logical × scale = physical), so they are not
    small at 150 %. Before, the photo was drawn 1.5× bigger via
    `CTkImage(size=)` and got cropped."""
    telo = _telo("app.py", "_paint_dnes_canvas")
    assert "get_widget_scaling" in telo
    assert "mierka" in telo


# --------------------------------------------------------------------------
# Why the evening ended with zero cues
#
# The first real evening (The Finals, 36 min) ended with zero cues, even
# though peak load was 87 at a threshold of 55. The session summary could
# not tell whether the "continuously 90 s" rule was too strict, or whether
# heart-rate dropouts were breaking the continuity counter. These four
# numbers tell them apart without storing the curve.
# --------------------------------------------------------------------------

def test_najdlhsi_usek_nad_prahom_sa_meria():
    """When it does not arm, it must be visible how close it came."""
    t, h = spusti(stress_hold_s=90.0, dip_grace_s=5.0)
    for _ in range(40):                      # 40 s above the threshold, then down
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(20):                      # a long dip cancels the stretch
        t.note_load(10.0, h.t)
        h.posun(1.0)
    assert t.armed_count == 0
    assert 38.0 <= t.najdlhsi_nad_s <= 40.0, t.najdlhsi_nad_s
    assert t.behov_nad == 1
    assert t.zrusenych_prepadom == 1
    assert t.zrusenych_vypadkom == 0


def test_vypadok_tepu_sa_odlisi_od_prepadu():
    """Same zero cues, a completely different cause — and a different fix."""
    t, h = spusti(stress_hold_s=90.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_TEP_VYPADOL, h.t)
    assert t.zrusenych_vypadkom == 1
    assert t.zrusenych_prepadom == 0
    assert 28.0 <= t.najdlhsi_nad_s <= 30.0, t.najdlhsi_nad_s


def test_kratky_prepad_beh_nerozbije():
    """The `dip_grace_s` tolerance must not count a new run - otherwise the
    numbers would claim a fragmentation that did not happen."""
    t, h = spusti(stress_hold_s=90.0, dip_grace_s=5.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    for _ in range(3):                       # a short dip, within tolerance
        t.note_load(10.0, h.t)
        h.posun(1.0)
    for _ in range(30):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.behov_nad == 1, t.behov_nad
    assert t.zrusenych_prepadom == 0
    # One stretch (more than either of the two 30 s pieces), but without the
    # three seconds of the dip: since 0.2.1 time below the threshold does not
    # count towards the stretch. Before, this said `>= 60` and passed only
    # because the wall clock (62 s) also counted the dip.
    assert 58.0 <= t.najdlhsi_nad_s <= 60.0, t.najdlhsi_nad_s


def test_pocitadla_sa_novou_relaciou_vynuluju():
    t, h = spusti(stress_hold_s=90.0)
    for _ in range(20):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    assert t.behov_nad == 1
    t.open_session(silent_share=0.0)
    assert t.najdlhsi_nad_s == 0.0
    assert t.behov_nad == 0
    assert t.zrusenych_prepadom == 0
    assert t.zrusenych_vypadkom == 0


def test_uspesne_natiahnutie_najdlhsi_usek_zaznamena():
    """Even when the cue goes off, the stretch length must be recorded -
    otherwise the longest stretch would come out as zero exactly on the
    evenings when the app worked."""
    t, h = spusti(stress_hold_s=90.0)
    natiahni(t, h, stress=80.0)
    assert t.armed_count == 1
    assert t.najdlhsi_nad_s >= 89.0, t.najdlhsi_nad_s


# --------------------------------------------------------------------------
# The "why didn't I speak up" sentence must hit the right cause
#
# Three very different things look the same from the player's point of
# view (silence) and have very different fixes. Mixing them up would send
# them to fix something else.
# --------------------------------------------------------------------------

def _preco(**summary):
    import ui_dialogs
    return ui_dialogs.SessionEndDialog._preco_ticho(summary)


def test_preco_ticho_stare_relacie_nic_netvrdia():
    """A session saved before this change lacks those numbers - stay silent."""
    assert _preco(duration_s=1800) == ""


def test_preco_ticho_telo_nebolo_hore():
    veta = _preco(above_runs=0, runs_cancelled_gap=0, runs_cancelled_dip=0)
    # 0.3: load has a "prah" (threshold), "hranica" is only heart rate in BPM
    assert veta and "prah" in veta.lower(), veta


def test_preco_ticho_bolo_hore_ale_kratko():
    veta = _preco(above_runs=6, runs_cancelled_gap=0, runs_cancelled_dip=6,
                  longest_above_s=42.0, stress_hold_s=90.0)
    assert "42" in veta and "90" in veta, veta


def test_preco_ticho_vypadky_maju_prednost():
    """With dropouts the "longest stretch" is untrustworthy - it is chopped
    up by gaps in the data, not by physiology. That is why they are asked
    first."""
    veta = _preco(above_runs=9, runs_cancelled_gap=7, runs_cancelled_dip=2,
                  longest_above_s=11.0, stress_hold_s=90.0)
    assert "7" in veta, veta
    assert "11" not in veta, "pri vypadkoch sa dlzka useku tvrdit nema: " + veta


def test_kolova_hra_sa_natiahne_az_po_uprave():
    """Why `stress_hold_s` went from 90 to 45 and the tolerance from 5 to 20.

    The pattern of a round-based shooter: the body goes up, you die,
    respawn, the body drops for a while, next round. Exactly this happened
    on the evening that ended with zero cues — and exactly this the app
    must catch after the change.
    """
    def odohraj(**params):
        t, h = spusti(**params)
        for _ in range(3):                   # three rounds
            for _ in range(50):              # 50 s in combat
                if t.note_load(80.0, h.t):
                    return True
                h.posun(1.0)
            for _ in range(12):              # 12 s of respawn and calm
                if t.note_load(20.0, h.t):
                    return True
                h.posun(1.0)
        return False

    # Since 19. 9. it is not a CONTINUOUS stretch that counts, but how much
    # time was above the threshold in the last `OKNO_NASOBOK * stress_hold_s`
    # seconds. That is why this pattern arms even with the old parameters —
    # and that is the whole point of the change: the evening that ended with
    # zero cues had 13 runs above the threshold and the longest was 44.1 s
    # against the required 45.0. One second of one run was missing, while
    # there was plenty of time above the threshold.
    assert odohraj(stress_hold_s=90.0, dip_grace_s=5.0), (
        "kumulatívne okno musí zachytiť aj kolový vzorec s krátkou toleranciou")
    assert odohraj(stress_hold_s=45.0, dip_grace_s=20.0), (
        "s dnešnými parametrami tobôž")


def test_pokojny_vecer_sa_nenatiahne_ani_kumulativne():
    """Guard for the previous: cumulative window must not arm on just anything.

    If a few seconds above the threshold over a long time were enough, the
    app would speak up even during calm play — that is exactly the
    opposite that makes it annoying.
    """
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    for _ in range(40):
        for _ in range(5):                   # a short 5 s spike above the threshold
            assert not t.note_load(60.0, h.t)
            h.posun(1.0)
        for _ in range(55):                  # 55 s of calm
            assert not t.note_load(20.0, h.t)
            h.posun(1.0)


def test_vypadok_spojenia_sa_nerata_ako_cas_nad_prahom():
    """A gap in the data is not load.

    Without a per-step cap, one 20-minute connection dropout would add 20
    minutes "above the threshold" to the window and the app would speak up
    right after the return — based on time nobody measured.
    """
    t, h = spusti(stress_threshold=55.0, stress_hold_s=45.0)
    assert not t.note_load(80.0, h.t)
    h.posun(1200.0)                          # 20 minutes of silence from the sensor
    assert not t.note_load(80.0, h.t), "výpadok sa nesmie počítať ako držanie"


def test_zapnutie_pocuvania_otvori_novu_relaciu():
    """Point 1 of the spec from 18. 9.

    The session was tied to the SENSOR, not to listening — it was opened
    only in `start_heart_rate_monitor`. Since `stop_listening` closes it
    properly, after the first stop/start cycle no session was open and
    nothing was measured. In the CSV from 18. 9. this shows as four short
    sessions instead of one — they came about only from app restarts.
    """
    telo = _telo("app.py", "start_listening")
    assert "_hr_session_open" in telo, "start_listening sa musí pýtať na reláciu"
    assert "_open_hr_session" in telo, "a otvoriť novú, keď žiadna nebeží"


def test_zapnutie_pocuvania_nerestartuje_siet_zbytocne():
    """A socket restart = a short watch disconnect, and it is exactly short
    dropouts that break the continuity counting (points 2 and 5). When
    reception is already running, only the session may be opened."""
    telo = _telo("app.py", "start_listening")
    assert "heart_rate_monitor.running" in telo, \
        "start_listening sa musí spýtať, či príjem už beží"
    assert "prepoj=False" in telo, \
        "pri bežiacom príjme sa stav pripojenia nesmie zhodiť na 'connecting'"


# ---------------------------------------------------------------------------
# "How often I speak up" - one control that moves four thresholds at once
# ---------------------------------------------------------------------------

def test_citlivost_bezne_je_presne_vychodiskove_nastavenie():
    """"Bezne" must not be its own table of numbers.

    If it kept its own values, `default_params()` and "bezne" would drift
    apart one day and nobody would know which of them are the numbers from
    the spec.
    """
    assert trigger.params_for(trigger.CITLIVOST_BEZNE) == trigger.default_params()


def test_citlivost_vracia_cely_slovnik_nie_len_rozdiel():
    """Switching back to "bezne" must return ALL the numbers.

    If `params_for` returned only the difference and the caller
    `update`-d it into the running parameters, then after the path "viac"
    -> "bezne" the old threshold 48 would stay in them and the choice
    would lie.
    """
    for citlivost in trigger.CITLIVOSTI:
        assert set(trigger.params_for(citlivost)) == set(trigger.default_params())


def test_citlivost_naozaj_meni_frekvenciu_spravnym_smerom():
    menej = trigger.params_for(trigger.CITLIVOST_MENEJ)
    bezne = trigger.params_for(trigger.CITLIVOST_BEZNE)
    viac = trigger.params_for(trigger.CITLIVOST_VIAC)
    # lower threshold and shorter hold = speaks up sooner
    assert menej["stress_threshold"] > bezne["stress_threshold"] > viac["stress_threshold"]
    assert menej["stress_hold_s"] > bezne["stress_hold_s"] > viac["stress_hold_s"]
    # shorter gap and higher cap = speaks up more often
    assert menej["min_gap_s"] > bezne["min_gap_s"] > viac["min_gap_s"]
    assert menej["max_per_hour"] < bezne["max_per_hour"] < viac["max_per_hour"]


def test_ziadna_citlivost_nepodlezie_refrakternu_zonu():
    """HARD LIMIT. The gap must stay above `measure.REFRACTORY_AFTER_S`.

    If it dropped below it, the second cue would land in the measurement
    window of the first, both windows would be invalidated and nothing
    would be left of the evening to evaluate. It is the only reason why
    "viac" does not go even higher.
    """
    import measure
    for citlivost in trigger.CITLIVOSTI:
        odstup = trigger.params_for(citlivost)["min_gap_s"]
        assert odstup > measure.REFRACTORY_AFTER_S, citlivost
    assert trigger.MIN_GAP_FLOOR_S > measure.REFRACTORY_AFTER_S


def test_nezmyselna_citlivost_padne_na_bezne():
    """Broken/old settings.json must not leave the app without thresholds."""
    for nezmysel in ("stredne", "", None, 3):
        assert trigger.params_for(nezmysel) == trigger.default_params()


def test_vyvojarska_vrstva_nepodlezie_refrakternu_zonu():
    """The hard safety net applies to the developer overlay too.

    It is a tool for tuning thresholds, not for bypassing the limit that
    protects the measurement. A typo in a field (24 instead of 240) would
    not spoil one evening, but a whole week of data — and in the data it
    would look like "the cue did not work", not like a settings error.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp.apply_dev_params)
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "MIN_GAP_FLOOR_S" in telo, "vyvojarska vrstva poistku obchadza"


def test_vypnutie_vsetkych_hlasok_appku_umlci():
    """Whoever switched off all four wanted silence — and got breathing.

    `_dalsi_cue_slot` returned `CUE_SLOT_INDEX` (the breathing circle) as a
    fallback, so switching off all toggles did not silence the app.
    Switching off is the player's decision and the state machine must not
    get around it.
    """
    import inspect
    import app as app_mod
    telo = inspect.getsource(app_mod.DandurfApp._dalsi_cue_slot)
    telo = telo[telo.index('"""', telo.index('"""') + 3):]
    assert "return self.CUE_SLOT_INDEX" not in telo, "zaloha sa vratila"
    assert "return None" in telo

    doruc = inspect.getsource(app_mod.DandurfApp._fire_somatic_cue)
    assert "if index is None:" in doruc, "dorucenie None neoseruje"


# --------------------------------------------------------------------------
# A heart-rate dropout throws away the collected time above the threshold (B4)
# --------------------------------------------------------------------------

def test_vypadok_tepu_zahodi_nazbierany_cas_nad_prahom():
    """B4: `suspend` reset `_above_since`, but left `_nad_okno`.

    The guard against a gap in `note_load` triggers only when
    `_above_since` is not None — and that is exactly what suspend reset.
    Without clearing the window, after a 12–40 s dropout the old collected
    load would survive and the first sample after the return would arm a
    cue on time nobody measured.
    """
    t, h = spusti(stress_threshold=50.0, stress_hold_s=30.0)
    # ~29 s just under hold=30 → it does not arm yet, but the window is full
    for _ in range(29):
        assert t.note_load(80.0, h.t) is None
        h.posun(1.0)

    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)   # the app calls this on a dropout
    h.posun(15.0)                               # 15 s without heart rate
    t.resume(now=h.t)                           # heart rate returns

    ev = t.note_load(80.0, h.t)                 # first sample after the return
    assert ev is None, "natiahlo sa z času spred výpadku (B4)"


def test_po_vypadku_sa_da_natiahnut_odznova():
    """The guard must not silence the app — after the return it can arm
    normally, just from scratch (from zero), not from the old time."""
    t, h = spusti(stress_threshold=50.0, stress_hold_s=30.0)
    for _ in range(10):
        t.note_load(80.0, h.t)
        h.posun(1.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=h.t)
    h.posun(20.0)
    t.resume(now=h.t)
    ev = natiahni(t, h, stress=80.0)            # hold the load → it must arm
    assert ev is not None
