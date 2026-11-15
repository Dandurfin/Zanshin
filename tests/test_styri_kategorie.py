# -*- coding: utf-8 -*-
"""Cues have four fixed categories (0.2).

Grounding, Jaw, Release, Breath - each with its own visual in game.
The „+ Pridat spustac“ (+ Add trigger) button is gone: the fifth and any
further slot had neither a visual nor a category, `_dalsi_cue_slot`
skipped it and it never sounded on its own, even though the log promised
the player the opposite.

These tests guard:
  * that neither the button nor its texts came back,
  * that old settings with more than four slots load without a crash and
    nothing gets lost from them,
  * that a new profile (even a profile without slots) gets all four
    categories,
  * that an automatic cue increments the counter in the journal header
    (`session.summary`) - only when it was really shown and not in the
    silent control arm.
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_appky  # noqa: E402


# --------------------------------------------------------------------------
# The button is gone
# --------------------------------------------------------------------------

def test_tlacidlo_pridat_spustac_je_prec():
    src = zdroj_appky()
    assert "def add_slot(self" not in src
    assert 'tr("slots.add")' not in src
    assert "log.slot_added" not in src
    for kluc in ("slots.add", "log.slot_added", "slot.new_text_default"):
        assert kluc not in i18n.STRINGS, kluc


# --------------------------------------------------------------------------
# Loading old settings
# --------------------------------------------------------------------------

@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` lives in the app_prefs mixin (PrefsMixin) and reads
    # SETTINGS_PATH from its own module - it has to be redirected there.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah):
        with open(cesta, "w", encoding="utf-8") as fh:
            json.dump(obsah, fh)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def test_stare_nastavenia_so_siestimi_slotmi_sa_nacitaju(nastavenia):
    sloty = [{"text": f"hlaska {i}", "mode": "tts"} for i in range(6)]
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "profiles": [{"name": "Moj", "slots": sloty}],
                    "active_profile": "Moj"})
    nacitane = d["profiles"][0]["slots"]
    assert [s["text"] for s in nacitane] == [f"hlaska {i}" for i in range(6)], \
        "z nastaveni sa nesmie nic stratit"
    assert len(d["overlay_configs"]) == 4


def test_profil_bez_slotov_dostane_styri_kategorie(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "profiles": [{"name": "Prazdny", "slots": []}],
                    "active_profile": "Prazdny"})
    assert len(d["profiles"][0]["slots"]) == 4


def test_piaty_slot_appka_sama_nespusti_ale_nespadne():
    """Slot 4+ has no visual (`overlay_configs` always has 4 items) - the
    rotation skips it, without an exception."""
    import app as app_mod
    a = types.SimpleNamespace(
        slots=[types.SimpleNamespace(index=i, enabled_value=True) for i in range(6)],
        overlay_configs=[{"enabled": True} for _ in range(4)])
    videne = {app_mod.DandurfApp._dalsi_cue_slot(a) for _ in range(20)}
    assert videne == {0, 1, 2, 3}


def test_novy_profil_ma_styri_kategorie():
    import app as app_mod
    a = types.SimpleNamespace(
        profiles=[{"name": "Default", "slots": []}], active_profile_name="Default",
        _sync_active_profile_slots=lambda: None, rebuild_slots=lambda s: None,
        refresh_profile_switch=lambda: None, save_settings=lambda: None,
        # since 0.2.1 a new profile starts cue preparation like switching a
        # profile does (test_021b_pregen_profil_a_hra.py)
        schedule_pregenerate=lambda *_: None,
        # since 0.2.1d a new profile may get a voice for its words
        # (test_021d_hlas_podla_hlasok.py) - it plays no role here
        _hlas_k_hlaskam=lambda slots: False,
        log=lambda *x: None)
    app_mod.DandurfApp.create_profile(a, "Novy")
    novy = next(p for p in a.profiles if p["name"] == "Novy")
    assert len(novy["slots"]) == 4
    assert a.active_profile_name == "Novy"


# --------------------------------------------------------------------------
# The session counter in the journal header
# --------------------------------------------------------------------------

class _Vlakno:
    """Synchronous `threading.Thread` - so we can check what was started."""

    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        self._t(*self._a, **self._k)


def _hlaska(monkeypatch, arm, vykreslene=True):
    import app as app_mod
    import app_today
    monkeypatch.setattr(app_mod, "threading", types.SimpleNamespace(Thread=_Vlakno))
    # `_fire_somatic_cue` lives in the app_today mixin (TodayMixin) and reads
    # `threading` from its own module - the synchronous thread is needed
    # there too.
    monkeypatch.setattr(app_today, "threading", types.SimpleNamespace(Thread=_Vlakno))
    obnovene = []
    slot = types.SimpleNamespace(index=1, text_value="Jaw")
    a = types.SimpleNamespace(
        _cue_rung=rebrik.HLAS, _cue_style_rel=rebrik.STYL_HLAS, slots=[slot],
        overlay_manager=types.SimpleNamespace(trigger=lambda i: vykreslene),
        hr_stats=hr_stats.HeartStats(), last_global_trigger_time=0.0,
        log=lambda *x: None, _refresh_hud_session_text=lambda: None,
        _refresh_dnes_stats=lambda: None, _dalsi_cue_slot=lambda: 1,
        _slot_zaznie=lambda s, bez_slov=False: True,
        _emit=lambda s, bez_slov=False: None,
        session_counts={0: 0, 1: 0, 2: 0, 3: 0},
        update_session_label=lambda: obnovene.append(True))
    ev = {"typ": trigger.E_DELIVER, "ts": 1200.0, "arm": arm,
          "delivery": "pause", "hlas": arm == trigger.ARM_VOICE,
          "load": 61.0, "load_peak": 74.0, "zone_at": "high"}
    app_mod.DandurfApp._fire_somatic_cue(a, ev)
    return a, obnovene


def test_automaticka_hlaska_zvysi_pocitadlo_relacie(monkeypatch):
    import app as app_mod
    a, obnovene = _hlaska(monkeypatch, trigger.ARM_VOICE)
    assert a.session_counts == {0: 0, 1: 1, 2: 0, 3: 0}
    assert obnovene, "riadok v denniku sa musi hned prekreslit"
    povodny = i18n._lang["code"]
    i18n.set_lang("en")
    try:
        assert "Jaw 1×" in app_mod.DandurfApp._session_text(a)
    finally:
        i18n.set_lang(povodny)


def test_tiche_kontrolne_rameno_sa_nerata(monkeypatch):
    a, obnovene = _hlaska(monkeypatch, trigger.ARM_SILENT)
    assert a.session_counts == {0: 0, 1: 0, 2: 0, 3: 0}
    assert not obnovene


def test_nevykreslena_hlaska_sa_nerata(monkeypatch):
    a, _ = _hlaska(monkeypatch, trigger.ARM_VOICE, vykreslene=False)
    assert a.session_counts == {0: 0, 1: 0, 2: 0, 3: 0}
