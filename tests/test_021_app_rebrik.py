# -*- coding: utf-8 -*-
"""0.2.1: the cue ladder and "not now after a cue" count only DELIVERED cues.

Review 0.2: `auto_triggers` also counted a cue whose picture was not drawn
(`note_trigger(delivered=False)`). The player saw nothing of it and the
questionnaire told them "I did not speak up" (it only offered "yes, it should
have / wasn't needed"), so they had no way to complain - and the ladder
counted such a session as "with a cue and no objections" and after three of
those climbed back up to voice.

Now:
  * a session carries `cues_delivered` (how many automatic cues were really
    shown) and the ladder counts by it; old sessions without it stay on
    `auto_triggers`,
  * the rule is the same as in the questionnaire (`_ask_session_context`)
    and for "not now" after a cue (`hr_stats.last_auto_cue_ts`),
  * the silent arm (picture only) IS a delivered cue - it was shown.
"""
import ast
import os
import random
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import strom_appky  # noqa: E402

KOREN = os.path.join(os.path.dirname(__file__), "..")


def rel(i, **kw):
    """Session `i` (ordered by `started`): 30 min, one cue."""
    s = {"started": 1_789_000_000.0 + i * 3600.0, "duration_s": 1800.0,
         "auto_triggers": 1}
    s.update(kw)
    return s


# --------------------------------------------------------------------------
# Ladder - pure function
# --------------------------------------------------------------------------

def test_nedorucena_hlaska_nepomoze_navratu():
    """Three sessions in which the cue "fired" but the picture failed - the
    player saw nothing. The ladder must not climb to voice out of silence."""
    zaklad = [rel(0, cue_verdict="disruptive", cues_delivered=1)]
    assert rebrik.stupen(zaklad)["stupen"] == rebrik.OBRAZ
    nic = [rel(1 + i, cues_delivered=0) for i in range(3)]
    s = rebrik.stupen(zaklad + nic)
    assert s["stupen"] == rebrik.OBRAZ
    assert s["zostava"] == rebrik.NAVRAT_RELACII, "nedorucene sa neratali"
    # delivered ones do count
    s = rebrik.stupen(zaklad + [rel(4 + i, cues_delivered=1) for i in range(3)])
    assert (s["stupen"], s["dovod"]) == (rebrik.HLAS, rebrik.D_NAVRAT)


def test_verdikt_pri_nedorucenej_hlaske_nic_neposunie():
    s = rebrik.stupen([rel(0, cue_verdict="disruptive", cues_delivered=0)])
    assert s["stupen"] == rebrik.HLAS


def test_stare_relacie_ostavaju_na_auto_triggers():
    zaklad = [rel(0, cue_verdict="disruptive")]
    s = rebrik.stupen(zaklad + [rel(1 + i) for i in range(3)])
    assert s["stupen"] == rebrik.HLAS
    assert rebrik._hlasok({"auto_triggers": 2}) == 2
    assert rebrik._hlasok({"auto_triggers": 2, "cues_delivered": 0}) == 0


def test_pokazene_cislo_nezhodi_rebrik():
    for zle in ("?", None, [], {}):
        assert rebrik._hlasok({"cues_delivered": zle, "auto_triggers": 1}) == 1
    for zle in (float("nan"), float("inf"), -3):
        assert rebrik._hlasok({"cues_delivered": zle}) == 0
    s = rebrik.stupen([rel(0, cues_delivered=float("nan"),
                           cue_verdict="disruptive")])
    assert s["stupen"] == rebrik.HLAS


# --------------------------------------------------------------------------
# app.py on a dummy: delivery -> session summary -> ladder
# --------------------------------------------------------------------------

def _nic(*_a, **_k):
    return None


class _Vlakno:
    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _appka(monkeypatch, tmp_path, obrazy):
    """The real `_on_cue_event` / `_fire_somatic_cue` / `_close_hr_session`.
    `obrazy` = what `overlay_manager.trigger` returns for each cue."""
    import app as app_mod
    import app_today
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    # `_fire_somatic_cue` (called by `_on_cue_event`) lives in the app_today
    # mixin (TodayMixin) and reads `threading` from its own module - a
    # synchronous thread is needed there too.
    monkeypatch.setattr(app_today, "threading", types.SimpleNamespace(Thread=_Vlakno))
    obrazy = list(obrazy)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.log = _nic
    a.log_threadsafe = _nic
    a._hr_session_open = True
    a.hr_stats = hr_stats.HeartStats(critical_bpm=110)
    a.cue_trigger = trigger.CueTrigger(rng=random.Random(1), clock=lambda: 0.0)
    a.cue_trigger.open_session(silent_share=0.0)
    a._cue_log = []
    a._cue_rung = rebrik.HLAS
    a._cue_style_rel = rebrik.STYL_HLAS
    a._session_world = "play"
    a.slots = [types.SimpleNamespace(index=1, text_value="Jaw")]
    a._dalsi_cue_slot = lambda: 1
    a.overlay_manager = types.SimpleNamespace(trigger=lambda i: obrazy.pop(0))
    a._slot_zaznie = lambda s, bez_slov=False: True
    a._emit = lambda s, bez_slov=False: None
    a.session_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    a.update_session_label = _nic
    for meno in ("_refresh_hud_session_text", "_refresh_dnes_stats",
                 "_refresh_kamae_state_text", "_save_measure_windows"):
        setattr(a, meno, _nic)
    a.last_global_trigger_time = 0.0
    a._snooze_po_hlaske = None
    a._hud_tick_t = None
    a._hud_vis_s = 0.0
    a._hud_active_s = 0.0
    a.hr_events_path = str(tmp_path / "udalosti.jsonl")
    a.hr_sessions_path = str(tmp_path / "relacie.json")
    return a


def _dorucenie(a, ts, arm=trigger.ARM_VOICE):
    a._on_cue_event({"typ": trigger.E_DELIVER, "ts": ts, "arm": arm,
                     "delivery": "pause", "hlas": arm == trigger.ARM_VOICE,
                     "load": 61.0, "load_peak": 74.0, "zone_at": "high"})


def _zavri(monkeypatch, a):
    import app as app_mod
    ulozene = []

    def uloz(path, summary, log=None):
        ulozene.append(summary)
        return False                        # no questionnaire, no history

    monkeypatch.setattr(app_mod.hr_stats, "save_session", uloz)
    a._close_hr_session()
    assert len(ulozene) == 1
    return ulozene[0]


def _v_dotazniku(a):
    """The same number that `SessionEndDialog` gets (`_ask_session_context`)."""
    return sum(1 for c in a._cue_log
               if c.get("typ") == trigger.E_DELIVER and c.get("delivered"))


def test_zlyhany_obraz_sa_v_relacii_nerata_ako_hlaska(monkeypatch, tmp_path):
    a = _appka(monkeypatch, tmp_path, [False])
    _dorucenie(a, 1000.0)
    s = _zavri(monkeypatch, a)
    assert s["auto_triggers"] == 1, "zaznam o spusteni ostava (meranie)"
    assert s["cues_delivered"] == 0 == _v_dotazniku(a)
    assert rebrik._hlasok(s) == 0


def test_dorucene_aj_tiche_rameno_sa_rataju(monkeypatch, tmp_path):
    a = _appka(monkeypatch, tmp_path, [True, False, True])
    _dorucenie(a, 1000.0)
    _dorucenie(a, 1400.0)                       # picture failed
    _dorucenie(a, 1800.0, arm=trigger.ARM_SILENT)
    s = _zavri(monkeypatch, a)
    assert s["auto_triggers"] == 3
    assert s["cues_delivered"] == 2 == _v_dotazniku(a)


def test_rebrik_z_ulozenych_suhrnov_nestupa_z_ticha(monkeypatch, tmp_path):
    """The whole path: after an "it disrupted" verdict, three evenings in which
    every cue failed on the picture - the ladder stays on the picture rung.
    Before 0.2.1 it would have climbed to voice."""
    relacie = [rel(0, cue_verdict="disruptive", cues_delivered=1)]
    for i in range(3):
        a = _appka(monkeypatch, tmp_path, [False])
        _dorucenie(a, 1000.0)
        s = _zavri(monkeypatch, a)
        s["started"] = rel(1 + i)["started"]
        relacie.append(s)
    assert rebrik.stupen(relacie)["stupen"] == rebrik.OBRAZ


def test_tiche_rameno_je_dorucena_hlaska(monkeypatch, tmp_path):
    """A picture-only cue (silent arm) was shown - sessions in which ONLY such
    a cue came are counted by the ladder as "with a cue", and after three
    without objections it climbs back. A silent arm with a failed picture is
    not (nothing was shown and nothing spoke up)."""
    def relacie(obraz):
        out = [rel(0, cue_verdict="agitated", cues_delivered=1)]
        for i in range(3):
            a = _appka(monkeypatch, tmp_path, [obraz])
            _dorucenie(a, 1000.0, arm=trigger.ARM_SILENT)
            s = _zavri(monkeypatch, a)
            assert s["auto_triggers"] == 1
            assert s["cues_delivered"] == int(obraz) == _v_dotazniku(a)
            s["started"] = rel(1 + i)["started"]
            out.append(s)
        return out

    assert rebrik.stupen(relacie(True))["stupen"] == rebrik.HLAS
    assert rebrik.stupen(relacie(False))["stupen"] == rebrik.OBRAZ


def test_teraz_nie_po_nedorucenej_hlaske_nie_je_signal(monkeypatch, tmp_path):
    a = _appka(monkeypatch, tmp_path, [False])
    _dorucenie(a, 1000.0)
    a._zapis_snooze_po_hlaske(1020.0)
    assert a._snooze_po_hlaske is None
    # the silent arm was shown - that is a signal
    a = _appka(monkeypatch, tmp_path, [True])
    _dorucenie(a, 1000.0, arm=trigger.ARM_SILENT)
    a._zapis_snooze_po_hlaske(1020.0)
    assert a._snooze_po_hlaske == (20.0, 1020.0)


def test_suhrn_nesie_cues_delivered_pred_ulozenim():
    strom = strom_appky()

    def _telo(meno):
        return ast.unparse(next(u for u in ast.walk(strom)
                                if isinstance(u, ast.FunctionDef) and u.name == meno))
    # The summary is built by `_suhrn_relacie` (0.3 - the same summary also
    # goes into the checkpoint); `_close_hr_session` has it assembled before
    # saving.
    assert "summary['cues_delivered']" in _telo("_suhrn_relacie")
    zatvor = _telo("_close_hr_session")
    assert zatvor.index("self._suhrn_relacie()") < zatvor.index("hr_stats.save_session(")
