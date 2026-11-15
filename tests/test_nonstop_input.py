# -*- coding: utf-8 -*-
"""Input without a single pause: a quiet line on Today, once per session.

It happened to the author: the controller gyroscope ("Motion Always On")
reported input to Windows every ~16 ms, `GetLastInputInfo` was never idle
and the app found no pause in which to speak up - until he turned the gyro
off. The app cannot know this for sure, so only a quiet line on Today (not
in the game).

The tests run without Tk: `NonstopInputWatch` is pure, the app method is
called on a small dummy.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import activity  # noqa: E402
import i18n      # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

T0 = 1_700_000_000.0
MIN20 = 20 * 60


def _bez_pauzy(watch, od, sekund, watching=True, pause_s=0.0, krok=0.25):
    """Steps time by 0.25 s (like `_tick_activity`), returns the end time."""
    t = od
    koniec = od + sekund
    ukaz = False
    while t < koniec:
        t += krok
        ukaz = watch.update(t, pause_s, watching)
    return t, ukaz


# --------------------------------------------------------------------------
# NonstopInputWatch
# --------------------------------------------------------------------------

def test_dvadsat_minut_bez_pauzy_ukaze_riadok_nie_skor():
    w = activity.NonstopInputWatch()
    assert w.after_s == MIN20
    w.update(T0, 0.0, True)
    t, ukaz = _bez_pauzy(w, T0, MIN20 - 5)
    assert not ukaz
    t, ukaz = _bez_pauzy(w, t, 10)
    assert ukaz and w.active and w.shown


def test_pauza_riadok_skryje_a_v_relacii_sa_uz_neukaze():
    w = activity.NonstopInputWatch()
    w.update(T0, 0.0, True)
    t, ukaz = _bez_pauzy(w, T0, MIN20 + 1)
    assert ukaz
    assert w.update(t + 0.25, 2.6, True) is False    # a 2.6 s pause came
    t, ukaz = _bez_pauzy(w, t + 0.25, 2 * MIN20)
    assert not ukaz, "raz za relaciu"
    w.reset()                                          # new session
    w.update(t, 0.0, True)
    t, ukaz = _bez_pauzy(w, t, MIN20 + 1)
    assert ukaz


def test_kratka_pauza_pod_prahom_cas_nevynuluje():
    w = activity.NonstopInputWatch()
    w.update(T0, 0.0, True)
    t, _ = _bez_pauzy(w, T0, MIN20 - 60)
    w.update(t + 0.25, 1.5, True)                      # 1.5 s < 2.5 s
    t, ukaz = _bez_pauzy(w, t + 0.25, 70)
    assert ukaz


def test_pauza_sa_meria_prahom_spustaca():
    w = activity.NonstopInputWatch()
    w.update(T0, 0.0, True)
    t, _ = _bez_pauzy(w, T0, MIN20 - 60)
    w.update(t + 0.25, 3.0, True, pause_needed_s=4.0)   # 3 s < 4 s threshold
    t, ukaz = _bez_pauzy(w, t + 0.25, 70)
    assert ukaz


def test_bez_tepu_cas_nerastie_ale_ani_sa_nenuluje():
    """A heart-rate dropout (the player may not be at the PC) stops the time. A
    short dropout in the middle of the evening must not reset it, though -
    dropouts are frequent."""
    w = activity.NonstopInputWatch()
    w.update(T0, 0.0, True)
    t, _ = _bez_pauzy(w, T0, MIN20 - 60)
    t, ukaz = _bez_pauzy(w, t, 3600, watching=False)
    assert not ukaz, "bez tepu sa nerata"
    t, ukaz = _bez_pauzy(w, t, 70)
    assert ukaz, "vypadok cas nevynuloval"


def test_nezname_idle_sa_nerata():
    w = activity.NonstopInputWatch()
    w.update(T0, None, True)
    t, ukaz = _bez_pauzy(w, T0, 2 * MIN20, pause_s=None)
    assert not ukaz


def test_uspaty_pc_neprida_minuty_jednym_tikom():
    w = activity.NonstopInputWatch()
    w.update(T0, 0.0, True)
    assert w.update(T0 + 3 * MIN20, 0.0, True) is False


# --------------------------------------------------------------------------
# app: the line only on Today, only when listening and the heart rate is coming
# --------------------------------------------------------------------------

def _app():
    import app as app_mod
    return app_mod


def _atrapa(**navyse):
    kresby = []
    a = types.SimpleNamespace(
        listening=True, _hr_session_open=True, _hr_state="connected",
        _hr_last_bpm=84, _hr_lost=False,
        cue_trigger=types.SimpleNamespace(params={"pause_s": 2.5}),
        activity=types.SimpleNamespace(pause_s=lambda now=None: 0.0),
        _nonstop_input=activity.NonstopInputWatch(),
        _dnes_nonstop_text="",
        _refresh_dnes_backdrop=lambda _e=None, force=False: kresby.append(force),
        kresby=kresby)
    a.__dict__.update(navyse)
    return a


def _tikaj(a, od, sekund):
    tick = _app().DandurfApp._tick_nonstop_input
    t = od
    while t < od + sekund:
        t += 0.25
        tick(a, now=t)
    return t


def test_appka_po_20_min_ukaze_riadok_na_dnes_a_prekresli():
    app_mod = _app()
    a = _atrapa()
    t = _tikaj(a, T0, MIN20 - 5)
    assert a._dnes_nonstop_text == "" and a.kresby == []
    _tikaj(a, t, 10)
    assert a._dnes_nonstop_text == app_mod.tr("dnes.nonstop_input", min=20)
    assert len(a.kresby) == 1, "prekresli sa raz, pri zmene - nie 4x za sekundu"


def test_appka_po_pauze_riadok_zhodi():
    a = _atrapa()
    t = _tikaj(a, T0, MIN20 + 1)
    assert a._dnes_nonstop_text
    a.activity = types.SimpleNamespace(pause_s=lambda now=None: 3.0)
    _tikaj(a, t, 1)
    assert a._dnes_nonstop_text == ""


def test_appka_bez_tepu_ani_bez_pocuvania_nerata():
    for navyse in ({"_hr_lost": True}, {"_hr_last_bpm": None},
                   {"_hr_state": "linked"}, {"_hr_session_open": False},
                   {"listening": False}):
        a = _atrapa(**navyse)
        _tikaj(a, T0, MIN20 + 60)
        assert a._dnes_nonstop_text == "", navyse


def test_appka_ked_prestane_pocuvat_riadok_zmizne():
    a = _atrapa()
    t = _tikaj(a, T0, MIN20 + 1)
    assert a._dnes_nonstop_text
    a.listening = False
    _tikaj(a, t, 1)
    assert a._dnes_nonstop_text == ""


def _src(nazov):
    with open(os.path.join(ROOT, nazov), encoding="utf-8") as fh:
        return fh.read()


def test_zapojenie_v_appke():
    tick = zdroj_metody("_tick_activity")
    assert "self._tick_nonstop_input()" in tick
    otvor = zdroj_metody("_open_hr_session")
    assert "self._nonstop_input.reset()" in otvor, "raz za RELACIU"
    kresli = zdroj_metody("_paint_dnes_canvas")
    assert "_dnes_nonstop_text" in kresli


def test_riadok_nie_je_v_hre():
    """Today only: the HUD and the in-game visuals know nothing about it."""
    for nazov in ("hud.py", "hud_paint.py", "overlay.py"):
        src = _src(nazov)
        assert "nonstop" not in src and "_dnes_nonstop_text" not in src, nazov


# --------------------------------------------------------------------------
# texts
# --------------------------------------------------------------------------

def test_texty_maju_vsetkych_jedenast_jazykov_a_min():
    for kluc in ("dnes.nonstop_input", "hr.trouble_pad"):
        zaznam = i18n.STRINGS[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        # language phase 0.2: its own translation in every language
        for jazyk in i18n.LANGUAGES:
            if jazyk not in ("sk", "en"):
                assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk)
    for jazyk in i18n.LANGUAGES:
        assert "{min}" in i18n.STRINGS["dnes.nonstop_input"][jazyk], jazyk


def test_texty_su_opatrne_a_radia_to_iste():
    riadok = i18n.STRINGS["dnes.nonstop_input"]
    # the app speaks of itself in the feminine; "mozno" (maybe), not a verdict
    assert "nezachytila" in riadok["sk"] and "možno" in riadok["sk"]
    assert "may be" in riadok["en"]
    assert "gyro" in riadok["sk"] and "mŕtvej zóny" in riadok["sk"]
    assert "gyro" in riadok["en"] and "deadzone" in riadok["en"]
    tip = i18n.STRINGS["hr.trouble_pad"]
    assert "Gyro" in tip["sk"] and "vypni" in tip["sk"] and "mŕtvu zónu" in tip["sk"]
    assert "Turn off its gyro" in tip["en"] and "deadzone" in tip["en"]


def test_tip_je_v_navode_k_parovaniu():
    src = _src("ui_dialogs.py")
    parovanie = src[src.index("class WatchPairingDialog"):]
    assert 'tr("hr.trouble_pad")' in parovanie
