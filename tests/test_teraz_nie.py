# -*- coding: utf-8 -*-
"""„Teraz nie“ (Ctrl+Alt+Z) a ukážka zvuku - rozhodnutia zadávateľa 24. 9.

  * „Teraz nie“ LEN stíši hlášky na zvolený čas. Počúva a meria sa ďalej:
    relácia ostáva otvorená, tep sa zapisuje, dotazník nepríde. Spúšťač je
    pozastavený s dôvodom `A_SNOOZE` (nie výpadok) a zdvihne sa po
    vypršaní alebo zrušení. Zastaviť počúvanie je samostatný krok.
  * Signál rebríka „teraz nie do 60 s po hláške a potom sa ešte hralo
    >= 120 s“ je tým naozaj dosiahnuteľný - celá cesta je tu.
  * Relácia si zapíše, koľko z nej platilo „teraz nie“ (`snoozed_s`) -
    automat vtedy spí, takže dotazník ani postrehy potom ticho nesmú
    vysvetľovať záťažou („ani raz nad hranicou“).
  * Ukážka „Ako to znie“ v Nastaveniach -> Zvuk ide za štýlom hlášky a veta
    pod ňou hovorí, čo naozaj urobí.

Skutočné metódy `DandurfApp` na inštancii bez okna (`__new__`), ako v
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
    """`root.after` bez Tk: úloha sa spustí, až keď ju test pustí."""

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
    """`app.time` s posúvateľným `time()`; zvyšok je skutočný modul."""

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
        # `_close_hr_session` byva v mixine app_data (DataMixin) a cita
        # `time` zo svojho modulu - hodiny musia ist aj tam.
        monkeypatch.setattr(app_data, "time", hodiny)
        # "Teraz nie" (`_start_snooze`, `_snooze_do`, `_zapocitaj_snooze`)
        # byva v mixine app_controls (ControlsMixin) - rovnako.
        monkeypatch.setattr(app_controls, "time", hodiny)
        # Spustac hlasky (`_tick_cue_trigger`) byva v mixine app_today
        # (TodayMixin) - rovnako.
        monkeypatch.setattr(app_today, "time", hodiny)
        # Prijem tepu (`_apply_hr_bpm`) byva v mixine app_session
        # (SessionMixin) - rovnako.
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
# „Teraz nie“ počúva a meria ďalej
# --------------------------------------------------------------------------

def test_teraz_nie_nechava_relaciu_otvorenu_a_zapisuje_tep(monkeypatch):
    a = _appka(monkeypatch)
    for bpm in (80, 81, 82):
        a._apply_hr_bpm(bpm, 1)
    pred = a.hr_stats.session_count

    a._start_snooze(30)             # dotazník ani stop by tu spadli (_zakazane)

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
    """Pol hodiny záťaže nad prahom s pauzami - nič sa nenatiahne, nič sa
    nedoručí. Uprostred vypadnú hodinky: prvá vzorka po návrate (`resume`
    bez `force`, ako v `_apply_hr_bpm`) snooze zdvihnúť nesmie."""
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
    # snooze nie je výpadok ani „appka sa rozhodla mlčať“
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
    a._toggle_snooze_from_hotkey()          # druhé stlačenie = zrušiť
    assert a._snooze_job is None and a.root.ulohy == {}
    assert a.cue_trigger.state == trigger.IDLE
    assert a.listening is True and a._hr_session_open is True
    assert a.denn[-1] == i18n.tr("log.snooze_cancelled")


def test_kym_plati_teraz_nie_nic_ho_nezdvihne(monkeypatch):
    """`start_listening` volá `_resume_cue_trigger` - hráč, ktorý počas
    stíšenia dal stop a start, ho nesmie ticho zrušiť. Nová relácia
    (`open_session`) ho tiež nesmie zhodiť."""
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
    # opačne áno: snooze počas výpadku je silnejší dôvod
    t.suspend(trigger.A_TEP_VYPADOL, now=1004.0)
    t.suspend(trigger.A_SNOOZE, now=1005.0)
    t.resume(1006.0)
    assert t.state == trigger.DORMANT


def test_dnes_hovori_ze_mlci_a_meria_dalej(monkeypatch):
    """„Čakám na správnu chvíľu“ by počas stíšenia klamalo."""
    h = _Hodiny(_time.mktime((2026, 9, 24, 21, 15, 0, 0, 0, -1)))
    a = _appka(monkeypatch, h)
    a._start_snooze(30)
    titul, veta = a._kamae_state_text()
    assert titul == i18n.tr("kamae.snoozed")
    assert veta == i18n.tr("kamae.snoozed_sub", until="21:45")
    assert a.bodka.stav[-1] == (True, i18n.tr("dock.snooze_active_tip",
                                              until="21:45"))
    a.root.spusti(a._snooze_job)
    assert a._kamae_state_text()[1] == i18n.tr("kamae.running_sub")


def test_texty_o_teraz_nie_hovoria_pravdu():
    """Stred Dnes sa ukáže len keď appka počúva a tep chodí - tam smie
    povedať „merám ďalej“. Riadok v denníku a bodka platia aj keď skratku
    stlačíš v zastavenej appke, tak sľubujú len to, čo platí vždy."""
    s = i18n.STRINGS
    assert "merám ďalej" in s["kamae.snoozed_sub"]["sk"]
    assert "measuring" in s["kamae.snoozed_sub"]["en"]
    assert "Počúvanie to nezastaví" in s["log.snooze_started"]["sk"]
    assert "doesn’t stop listening" in s["log.snooze_started"]["en"]
    for kluc in ("log.snooze_started", "dock.snooze_active_tip"):
        assert "merám" not in s[kluc]["sk"], kluc
        assert "measuring" not in s[kluc]["en"], kluc
    assert "zostáva" not in s["dock.snooze_active_tip"]["sk"]
    # zastavenie v páse už nie je to isté ako „teraz nie“
    assert "prestanem aj merať" in s["log.hotkey_failed"]["sk"]
    assert "stop measuring" in s["log.hotkey_failed"]["en"]


# --------------------------------------------------------------------------
# Rebrík: signál „teraz nie po hláške“ je dosiahnuteľný
# --------------------------------------------------------------------------

def _zavri(monkeypatch, a, tmp_path):
    """Skutočné `_close_hr_session` - hráč sám zastavil počúvanie."""
    import app as app_mod
    ulozene = []

    def uloz(path, summary, log=None):
        ulozene.append(summary)
        return False                        # bez dotazníka a histórie

    monkeypatch.setattr(app_mod.hr_stats, "save_session", uloz)
    del a._close_hr_session                 # zruší `_zakazane`
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
    h.t += 600.0                            # relácia beží ďalej
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
    h.t += 60.0                             # „končím“ - hneď stop
    s = _zavri(monkeypatch, a, tmp_path)
    assert s["snooze_then_s"] == 60.0
    assert rebrik.signal_dole(s) is None


# --------------------------------------------------------------------------
# Relácia vie, koľko z nej platilo „teraz nie“ - a ticho nevysvetľuje inak
# --------------------------------------------------------------------------

def test_relacia_zapise_kolko_platilo_teraz_nie(monkeypatch, tmp_path):
    """Automat počas stíšenia spí, takže `above_runs` ani `longest_above_s`
    ten čas nevidia. Súhrn preto nesie `snoozed_s`."""
    h = _Hodiny(3_000_000.0)
    a = _appka(monkeypatch, h)
    a._start_snooze(30)
    h.t += 300.0
    a._toggle_snooze_from_hotkey()          # zrušené po 5 min
    h.t += 600.0
    a._start_snooze(30)
    h.t += 120.0                            # a relácia skončí počas stíšenia
    s = _zavri(monkeypatch, a, tmp_path)
    assert s["snoozed_s"] == 420.0
    # stíšenie beží ďalej, ale mimo relácie sa už nič nepripočíta
    h.t += 600.0
    a.root.spusti(a._snooze_job)
    assert a._snooze_rel_s == 0.0 and a._snooze_rel_od is None


def test_relacia_bez_teraz_nie_snoozed_s_nema(monkeypatch, tmp_path):
    h = _Hodiny(3_000_000.0)
    a = _appka(monkeypatch, h)
    h.t += 900.0
    assert "snoozed_s" not in _zavri(monkeypatch, a, tmp_path)


def test_nova_relacia_pocas_teraz_nie_rata_od_svojho_zaciatku():
    """Nová relácia počas stíšenia (stop a štart, zapnutie senzora) - jej
    `snoozed_s` sa ráta od jej otvorenia, nie od stlačenia skratky."""
    otvor = ast.unparse(_funkcia("app.py", "_open_hr_session"))
    assert "self._snooze_rel_s = 0.0" in otvor
    blok = otvor[otvor.index("self._suspend_cue_trigger(trigger.A_SNOOZE)"):]
    assert "self._snooze_rel_od = time.time()" in blok.split("self._hr_session_open")[0]


def test_dotaznik_nevysvetluje_ticho_zatazou_ked_platilo_teraz_nie():
    """„Záťaž sa ani raz nedostala nad hranicu“ by po večere, v ktorom hráč
    stlačil „teraz nie“, mohlo tvrdiť niečo, čo appka vtedy nesledovala."""
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
    # výpadky tepu sú pravda aj tak - mimo stíšenia sa rátali
    assert preco(dict(zaklad, snoozed_s=600.0, runs_cancelled_gap=3)) == i18n.tr(
        "session.end.none_dropouts", n=3)
    # pauza rebríka má prednosť
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
    """Zmena jazyka postaví bodku stavu nanovo - bez tohto by počas
    stíšenia svietila zelenou „appka počúva“."""
    telo = ast.unparse(_funkcia("app.py", "_build_ui"))
    assert "self._refresh_snooze_indicator()" in telo


# --------------------------------------------------------------------------
# Ukážka „Ako to znie“ ide za štýlom hlášky
# --------------------------------------------------------------------------

class _Vlakno:
    """Synchronné `threading.Thread` - aby sa dalo overiť, čo sa spustilo."""

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
    """V hre prídu len sloty so zapnutým obrázkom (`_dalsi_cue_slot`).
    Prvý zapnutý slot bez obrázka by po kliku neukázal nič a v „len
    obrázok“ ani nič neprehral - veta pod tlačidlom by klamala."""
    sloty = [types.SimpleNamespace(index=0, enabled_value=True),
             types.SimpleNamespace(index=1, enabled_value=False),
             types.SimpleNamespace(index=2, enabled_value=True)]
    obrazky = (False, True, True, True)
    assert _ukazka(monkeypatch, "visual", sloty, obrazky) == ([], [2])
    assert _ukazka(monkeypatch, "sound", sloty, obrazky) == ([True], [2])
    # hlas ostáva ako doteraz (prvý zapnutý slot, bez obrázka)
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
    a._nastav_styl_hlasky("voice")          # hlasnejsí: veta aj tak hneď
    assert texty == [i18n.tr("settings.preview_sub_visual"),
                     i18n.tr("settings.preview_sub")]
    stranka = ast.unparse(_funkcia("app.py", "_build_zvuk_page"))
    assert "self.preview_sub_label = row.sub_label" in stranka
    assert "self._preview_sub_text()" in stranka


# --------------------------------------------------------------------------

def _funkcia(meno_suboru, meno):
    if meno_suboru == "app.py":
        # cela appka: app.py aj mixiny DandurfApp v app_*.py
        strom = strom_appky()
    else:
        with open(os.path.join(KOREN, meno_suboru), encoding="utf-8") as fh:
            strom = ast.parse(fh.read())
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return uzol
    raise AssertionError(meno)
