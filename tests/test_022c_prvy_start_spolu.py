# -*- coding: utf-8 -*-
"""Prvy start ako celok (0.2.2, zaverecna brana davky 2).

Tri casti davky 2 sa na prvom starte stretnu v jednom vecere:

  * navod na parovanie (z uvodu) zapne prijem tepu hned po otvoreni okna,
  * sledovanie zacne az po priprave hlasu (najviac `PRVY_START_MAX_S`),
    teda casto UPROSTRED parovania - `start_listening` otvori relaciu
    s `prepoj=False` nad uz pripojenym telefonom,
  * prva relacia nesie znacku nastavovania (`setup`) aj v kontrolnom bode.

Testy tu strazia styky medzi nimi, nie casti samotne (tie maju vlastne
subory test_022c_*). Bez Tk, vsetko v tmp priecinku.
"""
import json
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats  # noqa: E402


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _nic(*_a, **_k):
    return None


class _Stop(Exception):
    pass


def _otvor(prepoj):
    """Skutocny `_open_hr_session` po ucenie prahov (ako
    test_021_brana_veta_hranice). Atrapa `hud.configure` ho zastavi hned za
    nim - stav spojenia je vtedy uz nastaveny."""
    def _stop(**_kw):
        raise _Stop()
    a = types.SimpleNamespace(
        _hr_state="connected", _hr_client_linked=True, _hr_last_bpm=78,
        hr_critical_bpm=110, ALGORITMUS_SVET="play", world="play",
        hr_stats=types.SimpleNamespace(critical_bpm=110, long_baseline=None),
        hud=types.SimpleNamespace(configure=_stop),
        _history_sessions=lambda: [], _prah_z_relacii=0)
    with pytest.raises(_Stop):
        _app()._open_hr_session(a, prepoj=prepoj)
    return a


def test_nova_relacia_bez_prepojenia_necha_telefon_pripojeny():
    """Sledovanie zacne uprostred parovania: siete sa nedotyka, telefon
    spojenie drzi - priznak spojenia musi prezit."""
    a = _otvor(prepoj=False)
    assert a._hr_client_linked is True
    assert a._hr_state == "connected"
    assert a._hr_last_bpm is None


def test_restart_prijmu_priznak_zhodi():
    a = _otvor(prepoj=True)
    assert a._hr_client_linked is False
    assert a._hr_state == "connecting"


def test_vypadok_tepu_po_novej_relacii_hovori_pripojene():
    """Hodinky na chvilu prestanu posielat (`disconnected`) po tom, co
    sledovanie zacalo nad pripojenym telefonom: stav je "linked" (navod:
    "telefon pripojeny - cakam na tep"), nie "odpojene / cakam na telefon"."""
    a = _otvor(prepoj=False)
    a.__dict__.update(
        _hr_generation=1, _hr_lost=False, _hr_lost_od=None,
        _hr_over_since=None, _hr_session_open=True,
        hr_stats=hr_stats.HeartStats(critical_bpm=110),
        hud=types.SimpleNamespace(set_connected=_nic),
        log=_nic, _suspend_cue_trigger=_nic, _cancel_no_client_check=_nic,
        refresh_hr_status_label=_nic, _refresh_dnes_stats=_nic,
        _refresh_kamae_state_text=_nic, _refresh_hud_session_text=_nic)
    a._zaznamenaj_vypadok = lambda kind: _app()._zaznamenaj_vypadok(a, kind)
    _app()._apply_hr_status(a, ("disconnected", None), 1)
    assert a._hr_state == "linked"


def test_obnoveny_kontrolny_bod_nastavovania_znacku_drzi(tmp_path):
    """Pad uprostred prvej relacie: kontrolny bod (`_suhrn_relacie` so
    `setup`) sa po starte prida do historie ako `recovered` - a znacka
    nastavovania v nej ostane (dotaznik sa uz nespyta)."""
    cesta = str(tmp_path / "hr_sessions.json")
    teraz = time.time()
    suhrn = {"started": teraz - 900.0, "duration_s": 600.0, "samples": 300,
             "world": "play", "avg_bpm": 66.0, "setup": True}
    assert hr_stats.zapis_rozpracovanu(cesta, suhrn)
    with open(hr_stats.cesta_rozpracovanej(cesta), encoding="utf-8") as fh:
        assert json.load(fh)["setup"] is True
    obnovena = hr_stats.obnov_rozpracovanu(cesta, now=teraz)
    assert obnovena is not None
    [ulozena] = hr_stats.load_sessions(cesta)
    assert ulozena["recovered"] is True and ulozena["setup"] is True
    assert hr_stats.ciste_relacie([ulozena]) == []
    assert not os.path.exists(hr_stats.cesta_rozpracovanej(cesta))
