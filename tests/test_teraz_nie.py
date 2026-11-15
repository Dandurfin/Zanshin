# -*- coding: utf-8 -*-
"""The "Not now" (Ctrl+Alt+Z) and sound preview - author's decisions, 24. 9.

  * "Not now" ONLY mutes the cues for the chosen time. Listening and
    measuring go on: the session stays open, heart rate is recorded, the
    questionnaire does not come. The trigger is paused with the reason
    `A_SNOOZE` (not a dropout) and is lifted when it expires or is
    cancelled. Stopping listening is a separate step.
  * The ladder signal "not now within 60 s of a cue, and then play went
    on for >= 120 s" is thereby really reachable - the whole path is here.
  * The session records how much of it "not now" was in effect
    (`snoozed_s`) - the state machine sleeps then, so afterwards neither
    the questionnaire nor the insights may explain the silence by load
    ("not once over the limit").
  * The "How it sounds" preview in Settings -> Sound follows the cue style,
    and the sentence below it says what it will really do.

Real `DandurfApp` methods on an instance without a window (`__new__`), as in
tests/test_ui_fixes.py.
"""
import ast
import os
import random
import sys
import time as _time
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import strom_appky  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def _nic(*_a, **_k):
    return None


class _Root:
    """`root.after` without Tk: the task runs only when the test lets it."""

    def __init__(self):
        self.ulohy = {}
        self._n = 0

    def after(self, ms, fn):
        self._n += 1
        uid = f"after#{self._n}"
        self.ulohy[uid] = (ms, fn)
        return uid

    def after_cancel(self, uid):
        self.ulohy.pop(uid, None)

    def spusti(self, uid):
        _ms, fn = self.ulohy.pop(uid)
        fn()


class _Hodiny:
    """`app.time` with a movable `time()`; the rest is the real module."""

    def __init__(self, t):
        self.t = float(t)

    def time(self):
        return self.t

    def __getattr__(self, meno):
        return getattr(_time, meno)


class _Bodka:
    def __init__(self):
        self.stav = []

    def set_snoozed(self, active, tip=None):
        self.stav.append((active, tip))


def _zakazane(meno):
    def volanie(*_a, **_k):
        raise AssertionError(f"„teraz nie“ nesmie volať {meno}")
    return volanie


def _appka(monkeypatch, hodiny=None):
    import app as app_mod
    import app_controls
    import app_data
    import app_session
    import app_today
    if hodiny is not None:
        monkeypatch.setattr(app_mod, "time", hodiny)
        # `_close_hr_session` lives in the app_data mixin (DataMixin) and reads
        # `time` from its own module - the clock has to go there too.
        monkeypatch.setattr(app_data, "time", hodiny)
        # "Not now" (`_start_snooze`, `_snooze_do`, `_zapocitaj_snooze`)
        # lives in the app_controls mixin (ControlsMixin) - likewise.
        monkeypatch.setattr(app_controls, "time", hodiny)
        # The cue trigger (`_tick_cue_trigger`) lives in the app_today mixin
        # (TodayMixin) - likewise.
        monkeypatch.setattr(app_today, "time", hodiny)
        # Heart-rate receiving (`_apply_hr_bpm`) lives in the app_session mixin
        # (SessionMixin) - likewise.
        monkeypatch.setattr(app_session, "time", hodiny)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root()
    a.denn = []
    a.log = a.denn.append
    a.listening = True
    a.hr_monitoring_enabled = True
    a._hr_session_open = True
    a._hr_generation = 1
    a._hr_state = "connected"
    a._hr_last_bpm = 80
    a._hr_lost = False
    a._hr_bind_retries = 0
    a._cue_armed = False
    a._snooze_job = None
    a._snooze_po_hlaske = None
    a.hr_stats = hr_stats.HeartStats(critical_bpm=110)
    a.cue_trigger = trigger.CueTrigger(
        rng=random.Random(1),
        clock=(hodiny.time if hodiny is not None else _time.time))
    a.cue_trigger.open_session(silent_share=0.0)
    a.hud = types.SimpleNamespace(set_connected=_nic)
    a.hud_config = {"enabled": False}
    a._hud_tick_t = None
    a._hud_active_s = 0.0
    a._hud_vis_s = 0.0
    a.bodka = _Bodka()
    a.sidebar = types.SimpleNamespace(state_dot=a.bodka)
    a.overlay_manager = types.SimpleNamespace(is_active=lambda i: False)
    a._hr_overlay_available = lambda: True
    a.last_global_trigger_time = 0.0
    a.cooldown_value = 0.0
    a.udalosti = []
    a._on_cue_event = a.udalosti.append
    for meno in ("_refresh_dnes_state_text", "_refresh_hud_session_text",
                 "_refresh_dnes_stats", "refresh_hr_status_label"):
        setattr(a, meno, _nic)
    for meno in ("stop_listening", "start_listening", "_close_hr_session",
                 "_ask_session_context"):
        setattr(a, meno, _zakazane(meno))
    return a


# --------------------------------------------------------------------------
# "Not now" keeps listening and measuring
# --------------------------------------------------------------------------

def test_teraz_nie_nechava_relaciu_otvorenu_a_zapisuje_tep(monkeypatch):
    a = _appka(monkeypatch)
    for bpm in (80, 81, 82):
        a._apply_hr_bpm(bpm, 1)
    pred = a.hr_stats.session_count

    a._start_snooze(30)             # the questionnaire or stop would crash here (_zakazane)

    assert a.listening is True
    assert a._hr_session_open is True
    assert a.root.ulohy[a._snooze_job][0] == 30 * 60 * 1000
    for bpm in range(83, 93):
        a._apply_hr_bpm(bpm, 1)
    assert a.hr_stats.session_count == pred + 10, "tep sa počas stíšenia nezapisuje"
    assert a.cue_trigger.state == trigger.DORMANT
    assert a.cue_trigger._suspended_by == trigger.A_SNOOZE
    assert a.denn[-1] == i18n.tr("log.snooze_started", minutes=30)


def test_pocas_teraz_nie_hlaska_nepride_ani_po_vypadku(monkeypatch):
    """Half an hour of load above the threshold with pauses - nothing arms,
    nothing is delivered. In the middle the watch drops out: the first
    sample after it comes back (`resume` without `force`, as in
    `_apply_hr_bpm`) must not lift the snooze."""
    h = _Hodiny(1_000_000.0)
    a = _appka(monkeypatch, h)
    a.activity = types.SimpleNamespace(pause_s=lambda now: 5.0)
    a._start_snooze(30)
    for i in range(29 * 60):
        if i == 300:
            a._suspend_cue_trigger(trigger.A_TEP_VYPADOL)
        a.cue_trigger.resume(h.t)
        a.cue_trigger.note_load(90.0, h.t, zona="high")
        a._tick_cue_trigger()
        assert a._cue_can_fire(h.t) is False
        h.t += 1.0
    t = a.cue_trigger
    assert (t.armed_count, t.delivered_count) == (0, 0)
    assert a.udalosti == []
    assert t._suspended_by == trigger.A_SNOOZE
    # a snooze is neither a dropout nor "the app decided to stay silent"
    assert t.zrusenych_vypadkom == 0
    assert sum(t.zadrzane.values()) == 0


def test_teraz_nie_zrusi_natiahnutie_s_dovodom_snooze(monkeypatch):
    h = _Hodiny(1_000_000.0)
    a = _appka(monkeypatch, h)
    for _ in range(200):
        if a.cue_trigger.note_load(90.0, h.t, zona="high"):
            break
        h.t += 1.0
    assert a.cue_trigger.is_armed
    a._cue_armed = True
    a._start_snooze(30)
    assert [(u["typ"], u["reason"]) for u in a.udalosti] == [
        (trigger.E_ABORT, trigger.A_SNOOZE)]
    assert a._cue_armed is False, "prstenec „natiahnuté“ musí zhasnúť"


def test_po_vyprsani_sa_hlasky_vratia(monkeypatch):
    h = _Hodiny(1_000_000.0)
    a = _appka(monkeypatch, h)
    a.activity = types.SimpleNamespace(pause_s=lambda now: 0.0)
    a._start_snooze(30)
    h.t += 30 * 60
    a.root.spusti(a._snooze_job)
    assert a._snooze_job is None and a.root.ulohy == {}
    assert a.listening is True and a._hr_session_open is True
    assert a.cue_trigger.state == trigger.IDLE
    assert a._cue_can_fire(h.t) is True
    assert a.denn[-1] == i18n.tr("log.snooze_ended")
    assert a.bodka.stav[-1][0] is False
    for _ in range(200):
        a.cue_trigger.note_load(90.0, h.t, zona="high")
        h.t += 1.0
    assert a.cue_trigger.armed_count == 1, "po stíšení sa má dať znova natiahnuť"


def test_zrusenie_skratkou_vrati_hlasky_a_necha_pocuvanie(monkeypatch):
    import app as app_mod
    a = _appka(monkeypatch)
    a._toggle_snooze_from_hotkey()
    job = a._snooze_job
    assert job is not None
    assert a.root.ulohy[job][0] == app_mod.SNOOZE_HOTKEY_MINUTES * 60 * 1000
    a._toggle_snooze_from_hotkey()          # second press = cancel
    assert a._snooze_job is None and a.root.ulohy == {}
    assert a.cue_trigger.state == trigger.IDLE
    assert a.listening is True and a._hr_session_open is True
    assert a.denn[-1] == i18n.tr("log.snooze_cancelled")


def test_kym_plati_teraz_nie_nic_ho_nezdvihne(monkeypatch):
    """`start_listening` calls `_resume_cue_trigger` - a player who pressed
    stop and start during the muting must not silently cancel it. A new
    session (`open_session`) must not drop it either."""
    a = _appka(monkeypatch)
    a._start_snooze(30)
    a._resume_cue_trigger()
    assert a.cue_trigger.state == trigger.DORMANT
    otvor = ast.unparse(_funkcia("app.py", "_open_hr_session"))
    assert otvor.index("self.cue_trigger.open_session(") < otvor.index(
        "self._suspend_cue_trigger(trigger.A_SNOOZE)")


def test_vypadok_tepu_neprepise_dovod_snooze():
    t = trigger.CueTrigger(rng=random.Random(1), clock=lambda: 1000.0)
    t.open_session(silent_share=0.0)
    t.suspend(trigger.A_SNOOZE, now=1000.0)
    t.suspend(trigger.A_TEP_VYPADOL, now=1001.0)
    t.resume(1002.0)
    assert t.state == trigger.DORMANT and t._suspended_by == trigger.A_SNOOZE
    t.resume(1003.0, force=True)
    assert t.state == trigger.IDLE
    # the other way round yes: a snooze during a dropout is the stronger reason
    t.suspend(trigger.A_TEP_VYPADOL, now=1004.0)
    t.suspend(trigger.A_SNOOZE, now=1005.0)
    t.resume(1006.0)
    assert t.state == trigger.DORMANT


def test_dnes_hovori_ze_mlci_a_meria_dalej(monkeypatch):
    """Saying "I'm waiting for the right moment" would lie during muting."""
    h = _Hodiny(_time.mktime((2026, 9, 24, 21, 15, 0, 0, 0, -1)))
    a = _appka(monkeypatch, h)
    a._start_snooze(30)
    titul, veta = a._kamae_state_text()
    assert titul == i18n.tr("kamae.snoozed")
    # 0.3: without a registered shortcut the sentence points only to the tray
    # menu (the variant with the {combo} shortcut: tests/test_022e_skratka.py)
    assert veta == i18n.tr("kamae.snoozed_sub_tray", until="21:45")
    assert a.bodka.stav[-1] == (True, i18n.tr("dock.snooze_active_tip",
                                              until="21:45"))
    a.root.spusti(a._snooze_job)
    assert a._kamae_state_text()[1] == i18n.tr("kamae.running_sub")


def test_texty_o_teraz_nie_hovoria_pravdu():
    """The centre of Today shows only when the app is listening and heart
    rate is coming in - there it may say "I keep measuring". The journal
    line and the dot apply even when you press the shortcut in a stopped
    app, so they promise only what always holds."""
    s = i18n.STRINGS
    assert "merám ďalej" in s["kamae.snoozed_sub"]["sk"]
    assert "measuring" in s["kamae.snoozed_sub"]["en"]
    # 0.3: the main switch is "sledovat" (en "watching"), not "pocuvat"
    # (listening)
    assert "Sledovanie to nezastaví" in s["log.snooze_started"]["sk"]
    assert "doesn’t stop watching" in s["log.snooze_started"]["en"]
    for kluc in ("log.snooze_started", "dock.snooze_active_tip"):
        assert "merám" not in s[kluc]["sk"], kluc
        assert "measuring" not in s[kluc]["en"], kluc
    assert "zostáva" not in s["dock.snooze_active_tip"]["sk"]
    # stopping in the bar is no longer the same as "not now"
    assert "prestanem aj merať" in s["log.hotkey_failed"]["sk"]
    assert "stop measuring" in s["log.hotkey_failed"]["en"]


# --------------------------------------------------------------------------
# Ladder: the "not now after a cue" signal is reachable
# --------------------------------------------------------------------------

def _zavri(monkeypatch, a, tmp_path):
    """Real `_close_hr_session` - the player stopped listening on their own."""
    import app as app_mod
    ulozene = []

    def uloz(path, summary, log=None):
        ulozene.append(summary)
        return False                        # without questionnaire or history

    monkeypatch.setattr(app_mod.hr_stats, "save_session", uloz)
    del a._close_hr_session                 # cancels `_zakazane`
    a._cue_log = []
    a._save_measure_windows = _nic
    a.hr_events_path = str(tmp_path / "udalosti.jsonl")
    a.hr_sessions_path = str(tmp_path / "relacie.json")
    a.log_threadsafe = _nic
    a._session_world = "play"
    a._cue_rung = rebrik.HLAS
    a._cue_style_rel = rebrik.STYL_HLAS
    a._close_hr_session()
    assert len(ulozene) == 1
    return ulozene[0]


def test_teraz_nie_po_hlaske_a_hralo_sa_dalej_posunie_rebrik(monkeypatch, tmp_path):
    h = _Hodiny(2_000_000.0)
    a = _appka(monkeypatch, h)
    a.hr_stats.note_trigger(ts=h.t, auto=True, source="auto", delivered=True)
    h.t += 20.0
    a._start_snooze(30)
    assert a._snooze_po_hlaske == (20.0, h.t)
    assert a.hr_stats.cues[-1]["snooze_after_s"] == 20.0
    h.t += 600.0                            # the session goes on
    a._apply_hr_bpm(80, 1)
    s = _zavri(monkeypatch, a, tmp_path)
    assert (s["snooze_after_cue_s"], s["snooze_then_s"]) == (20.0, 600.0)
    assert rebrik.signal_dole(s) == rebrik.D_SNOOZE
    assert rebrik.stupen([s])["stupen"] == rebrik.OBRAZ


def test_teraz_nie_a_hned_koniec_rebrik_neposunie(monkeypatch, tmp_path):
    h = _Hodiny(2_000_000.0)
    a = _appka(monkeypatch, h)
    a.hr_stats.note_trigger(ts=h.t, auto=True, source="auto", delivered=True)
    h.t += 20.0
    a._start_snooze(30)
    h.t += 60.0                             # "I'm done" - stop at once
    s = _zavri(monkeypatch, a, tmp_path)
    assert s["snooze_then_s"] == 60.0
    assert rebrik.signal_dole(s) is None


# --------------------------------------------------------------------------
# The session knows how much of it "not now" covered - and doesn't explain the
# silence otherwise
# --------------------------------------------------------------------------

def test_relacia_zapise_kolko_platilo_teraz_nie(monkeypatch, tmp_path):
    """The state machine sleeps during muting, so neither `above_runs` nor
    `longest_above_s` see that time. That is why the summary carries
    `snoozed_s`."""
    h = _Hodiny(3_000_000.0)
    a = _appka(monkeypatch, h)
    a._start_snooze(30)
    h.t += 300.0
    a._toggle_snooze_from_hotkey()          # cancelled after 5 min
    h.t += 600.0
    a._start_snooze(30)
    h.t += 120.0                            # and the session ends while muted
    s = _zavri(monkeypatch, a, tmp_path)
    assert s["snoozed_s"] == 420.0
    # the muting goes on, but outside the session nothing more is added
    h.t += 600.0
    a.root.spusti(a._snooze_job)
    assert a._snooze_rel_s == 0.0 and a._snooze_rel_od is None


def test_relacia_bez_teraz_nie_snoozed_s_nema(monkeypatch, tmp_path):
    h = _Hodiny(3_000_000.0)
    a = _appka(monkeypatch, h)
    h.t += 900.0
    assert "snoozed_s" not in _zavri(monkeypatch, a, tmp_path)


def test_nova_relacia_pocas_teraz_nie_rata_od_svojho_zaciatku():
    """A new session during muting (stop and start, switching the sensor
    on) - its `snoozed_s` counts from its opening, not from the shortcut
    press."""
    otvor = ast.unparse(_funkcia("app.py", "_open_hr_session"))
    assert "self._snooze_rel_s = 0.0" in otvor
    blok = otvor[otvor.index("self._suspend_cue_trigger(trigger.A_SNOOZE)"):]
    assert "self._snooze_rel_od = time.time()" in blok.split("self._hr_session_open")[0]


def test_dotaznik_nevysvetluje_ticho_zatazou_ked_platilo_teraz_nie():
    """After an evening in which the player pressed "not now", "The load
    never once got over the limit" could claim something the app was not
    watching at the time."""
    import ui_dialogs
    preco = ui_dialogs.SessionEndDialog._preco_ticho
    zaklad = {"above_runs": 0, "longest_above_s": 0.0, "stress_hold_s": 45.0,
              "runs_cancelled_gap": 0, "runs_cancelled_dip": 0,
              "pause_episodes": 40, "duration_s": 2400.0}
    assert preco(zaklad) == i18n.tr("session.end.none_never")
    assert preco(dict(zaklad, snoozed_s=1500.0)) == i18n.tr(
        "session.end.none_snoozed", min=25)
    assert preco(dict(zaklad, snoozed_s=12.0)) == i18n.tr(
        "session.end.none_snoozed", min=1)
    assert preco(dict(zaklad, snoozed_s="x")) == i18n.tr("session.end.none_never")
    # heart-rate dropouts are true anyway - counted outside the muting
    assert preco(dict(zaklad, snoozed_s=600.0, runs_cancelled_gap=3)) == i18n.tr(
        "session.end.none_dropouts", n=3)
    # the ladder pause takes precedence
    assert preco(dict(zaklad, snoozed_s=600.0, cue_rung="pause")) == i18n.tr(
        "session.end.none_paused")
    assert "som mlčala" in i18n.STRINGS["session.end.none_snoozed"]["sk"]


def test_postrehy_neradia_hranicu_ked_ticho_bolo_teraz_nie():
    import hr_insights
    relacie = [{"started": 1789000000.0 + i * 86400.0, "duration_s": 2400.0,
                "samples": 900, "baseline_bpm": 70, "auto_triggers": 0,
                "above_runs": 0, "longest_above_s": 0.0,
                "runs_cancelled_gap": 0, "stress_hold_s": 45.0}
               for i in range(4)]
    kluce = {i["key"] for i in hr_insights.analyze(relacie, now=1789500000.0)}
    assert "cue_never_above" in kluce
    relacie[-1]["snoozed_s"] = 900.0
    kluce = {i["key"] for i in hr_insights.analyze(relacie, now=1789500000.0)}
    assert not kluce & {"cue_far", "cue_almost", "cue_never_above", "steady"}


def test_prestavba_okna_pocas_teraz_nie_necha_bodku_jantarovu():
    """A language change builds the status dot anew - without this, during
    muting it would glow green "the app is listening"."""
    telo = ast.unparse(_funkcia("app.py", "_build_ui"))
    assert "self._refresh_snooze_indicator()" in telo


# --------------------------------------------------------------------------
# The "How it sounds" preview follows the cue style
# --------------------------------------------------------------------------

class _Vlakno:
    """A synchronous `threading.Thread` - so we can verify what was started."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _ukazka(monkeypatch, styl, slots=None, obrazky=(True,) * 4, denn=None):
    import app as app_mod
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.cue_style = styl
    a.slots = slots or [types.SimpleNamespace(index=2, enabled_value=True)]
    a.overlay_configs = [{"enabled": bool(z)} for z in obrazky]
    zaznelo, obrazok = [], []
    a._emit = lambda slot, bez_slov=False: zaznelo.append((slot.index, bez_slov))
    a.overlay_manager = types.SimpleNamespace(
        trigger=lambda i: obrazok.append(i) or True)
    a.log = (denn.append if denn is not None else _nic)
    a.preview_sound()
    return [b for _i, b in zaznelo], obrazok


def test_ukazka_hlas_ako_doteraz(monkeypatch):
    assert _ukazka(monkeypatch, "voice") == ([False], [])


def test_ukazka_zvuk_bez_slov_s_obrazkom(monkeypatch):
    assert _ukazka(monkeypatch, "sound") == ([True], [2])


def test_ukazka_obraz_nic_neprehra(monkeypatch):
    assert _ukazka(monkeypatch, "visual") == ([], [2])


def test_ukazka_bez_slov_berie_slot_s_obrazkom_ako_v_hre(monkeypatch):
    """In-game only slots with the picture enabled come up
    (`_dalsi_cue_slot`). The first enabled slot without a picture would
    show nothing after a click and in "Picture only" would not play
    anything either - the sentence below the button would lie."""
    sloty = [types.SimpleNamespace(index=0, enabled_value=True),
             types.SimpleNamespace(index=1, enabled_value=False),
             types.SimpleNamespace(index=2, enabled_value=True)]
    obrazky = (False, True, True, True)
    assert _ukazka(monkeypatch, "visual", sloty, obrazky) == ([], [2])
    assert _ukazka(monkeypatch, "sound", sloty, obrazky) == ([True], [2])
    # voice stays as before (the first enabled slot, without a picture)
    assert _ukazka(monkeypatch, "voice", sloty, obrazky) == ([False], [])


def test_ukazka_bez_jedineho_obrazka_to_povie_narovinu(monkeypatch):
    denn = []
    sloty = [types.SimpleNamespace(index=0, enabled_value=True)]
    for styl in ("visual", "sound"):
        denn.clear()
        assert _ukazka(monkeypatch, styl, sloty, (False,) * 4, denn) == ([], [])
        assert denn == [i18n.tr("log.preview_no_picture")]
    assert "neozvala" in i18n.STRINGS["log.preview_no_picture"]["sk"]


def test_veta_pod_ukazkou_ide_za_stylom():
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    veta = {}
    for styl in ("voice", "sound", "visual", None):
        a.cue_style = styl
        veta[styl] = a._preview_sub_text()
    assert veta["voice"] == veta[None] == i18n.tr("settings.preview_sub")
    assert veta["sound"] == i18n.tr("settings.preview_sub_sound")
    assert veta["visual"] == i18n.tr("settings.preview_sub_visual")
    s = i18n.STRINGS
    assert "Bez slov" in s["settings.preview_sub_sound"]["sk"]
    assert "No words" in s["settings.preview_sub_sound"]["en"]
    assert "nič nezaznie" in s["settings.preview_sub_visual"]["sk"]
    assert "only shown" in s["settings.preview_sub_visual"]["en"]


def test_zmena_stylu_prepise_vetu_pod_ukazkou(monkeypatch):
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    texty = []
    a.preview_sub_label = types.SimpleNamespace(
        configure=lambda text: texty.append(text))
    a.cue_style = "voice"
    a._cue_style_rel = "voice"
    a._session_world = "play"
    a._cue_rung = rebrik.HLAS
    a.cue_trigger = types.SimpleNamespace(voice=True)
    a._nastav_styl_hlasky("visual")
    a._nastav_styl_hlasky("voice")          # louder: the sentence right away anyway
    assert texty == [i18n.tr("settings.preview_sub_visual"),
                     i18n.tr("settings.preview_sub")]
    stranka = ast.unparse(_funkcia("app.py", "_build_zvuk_page"))
    assert "self.preview_sub_label = row.sub_label" in stranka
    assert "self._preview_sub_text()" in stranka


# --------------------------------------------------------------------------

def _funkcia(meno_suboru, meno):
    if meno_suboru == "app.py":
        # the whole app: app.py and the DandurfApp mixins in app_*.py
        strom = strom_appky()
    else:
        with open(os.path.join(KOREN, meno_suboru), encoding="utf-8") as fh:
            strom = ast.parse(fh.read())
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return uzol
    raise AssertionError(meno)
