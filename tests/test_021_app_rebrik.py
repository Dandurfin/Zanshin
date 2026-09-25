# -*- coding: utf-8 -*-
"""0.2.1: rebrík hlášky a „teraz nie po hláške“ rátajú len DORUČENÉ hlášky.

Review 0.2: `auto_triggers` rátal aj hlášku, ktorej obraz sa nevykreslil
(`note_trigger(delivered=False)`). Hráč z nej nič nevidel a dotazník mu
povedal „neozvala som sa“ (ponúkol len „mala / netreba“), takže sa nemal
ako sťažovať - a rebrík takú reláciu rátal ako „s hláškou a bez výhrad“
a po troch takých stúpal späť k hlasu.

Teraz:
  * relácia nesie `cues_delivered` (koľko automatických hlášok sa naozaj
    ukázalo) a rebrík ráta podľa neho; staré relácie bez neho ostávajú na
    `auto_triggers`,
  * pravidlo je rovnaké ako v dotazníku (`_ask_session_context`) a pri
    „teraz nie“ po hláške (`hr_stats.last_auto_cue_ts`),
  * tiché rameno (len obraz) JE doručená hláška - ukázalo sa.
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
    """Relácia `i` (poradie podľa `started`): 30 min, jedna hláška."""
    s = {"started": 1_789_000_000.0 + i * 3600.0, "duration_s": 1800.0,
         "auto_triggers": 1}
    s.update(kw)
    return s


# --------------------------------------------------------------------------
# Rebrík - čistá funkcia
# --------------------------------------------------------------------------

def test_nedorucena_hlaska_nepomoze_navratu():
    """Tri relácie, v ktorých sa hláška „spustila“, ale obraz zlyhal - hráč
    nič nevidel. Rebrík nesmie stúpať k hlasu z ticha."""
    zaklad = [rel(0, cue_verdict="disruptive", cues_delivered=1)]
    assert rebrik.stupen(zaklad)["stupen"] == rebrik.OBRAZ
    nic = [rel(1 + i, cues_delivered=0) for i in range(3)]
    s = rebrik.stupen(zaklad + nic)
    assert s["stupen"] == rebrik.OBRAZ
    assert s["zostava"] == rebrik.NAVRAT_RELACII, "nedorucene sa neratali"
    # dorucene ano
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
# app.py na atrape: doručenie -> súhrn relácie -> rebrík
# --------------------------------------------------------------------------

def _nic(*_a, **_k):
    return None


class _Vlakno:
    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _appka(monkeypatch, tmp_path, obrazy):
    """Skutočné `_on_cue_event` / `_fire_somatic_cue` / `_close_hr_session`.
    `obrazy` = čo vráti `overlay_manager.trigger` pri každej hláške."""
    import app as app_mod
    import app_today
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    # `_fire_somatic_cue` (vola ho `_on_cue_event`) byva v mixine app_today
    # (TodayMixin) a cita `threading` zo svojho modulu - synchronne vlakno
    # treba aj tam.
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
        return False                        # bez dotazníka a histórie

    monkeypatch.setattr(app_mod.hr_stats, "save_session", uloz)
    a._close_hr_session()
    assert len(ulozene) == 1
    return ulozene[0]


def _v_dotazniku(a):
    """To isté číslo, ktoré dostane `SessionEndDialog` (`_ask_session_context`)."""
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
    _dorucenie(a, 1400.0)                       # obraz zlyhal
    _dorucenie(a, 1800.0, arm=trigger.ARM_SILENT)
    s = _zavri(monkeypatch, a)
    assert s["auto_triggers"] == 3
    assert s["cues_delivered"] == 2 == _v_dotazniku(a)


def test_rebrik_z_ulozenych_suhrnov_nestupa_z_ticha(monkeypatch, tmp_path):
    """Celá cesta: po „rušila“ tri večery, v ktorých každá hláška zlyhala na
    obraze - rebrík ostane na obraze. Do 0.2.1 by vyliezol na hlas."""
    relacie = [rel(0, cue_verdict="disruptive", cues_delivered=1)]
    for i in range(3):
        a = _appka(monkeypatch, tmp_path, [False])
        _dorucenie(a, 1000.0)
        s = _zavri(monkeypatch, a)
        s["started"] = rel(1 + i)["started"]
        relacie.append(s)
    assert rebrik.stupen(relacie)["stupen"] == rebrik.OBRAZ


def test_tiche_rameno_je_dorucena_hlaska(monkeypatch, tmp_path):
    """Hláška len obrazom (tiché rameno) sa ukázala - relácie, v ktorých
    prišla LEN takáto hláška, rebrík ráta ako „s hláškou“ a po troch bez
    výhrad stúpa späť. Tiché rameno so zlyhaným obrazom nie (nič sa
    neukázalo ani neozvalo)."""
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
    # tiche rameno sa ukazalo - to signal je
    a = _appka(monkeypatch, tmp_path, [True])
    _dorucenie(a, 1000.0, arm=trigger.ARM_SILENT)
    a._zapis_snooze_po_hlaske(1020.0)
    assert a._snooze_po_hlaske == (20.0, 1020.0)


def test_suhrn_nesie_cues_delivered_pred_ulozenim():
    strom = strom_appky()
    fn = next(u for u in ast.walk(strom)
              if isinstance(u, ast.FunctionDef) and u.name == "_close_hr_session")
    telo = ast.unparse(fn)
    assert "summary['cues_delivered']" in telo
    assert telo.index("summary['cues_delivered']") < telo.index("hr_stats.save_session(")
