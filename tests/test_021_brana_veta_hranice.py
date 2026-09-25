# -*- coding: utf-8 -*-
"""Veta o hranici vysokeho tepu v nastaveniach (0.2.1, zaverecna brana).

`hr_stats.dynamicky_kriticky` sa od 0.2.1 uci len z relacii dlhych aspon
5 minut (`je_dost_dlha`). `app._kriticky_popis` ale dalej ratal KAZDU cistu
hernu relaciu - po troch kratkych relaciach (parovanie hodiniek) nastavenia
tvrdili "spocitane z 3 tvojich hernych relacii", kym v skutocnosti platila
zaloha 110. Presne ten druh vety, ktory SOUL.md povazuje za chybu.

To iste pravidlo musi platit aj pre `_prah_z_relacii` v `_open_hr_session`
(pocet do vety o prahu zataze): `float(duration_s)` priamo tam pri
pokazenom cisle vyhodil vynimku a `except` zahodil aj dlhodobu zakladnu.

Bez Tk - skutocne metody `DandurfApp` na malej atrape (ako test_worlds.py).
"""
import math
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats  # noqa: E402
import i18n  # noqa: E402


def _app():
    import app as app_mod
    return app_mod.DandurfApp


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _relacia(minut, **kw):
    """Cista herna relacia s plynulou krivkou (kadencia 1 s, najviac
    `CURVE_POINTS` bodov) - `je_podozriva` ju necha tak."""
    trvanie = minut * 60.0
    bodov = min(hr_stats.CURVE_POINTS, int(trvanie))
    s = {"started": 1.7e9, "duration_s": trvanie, "baseline_bpm": 70.0,
         "max_bpm": 95.0, "world": "play",
         "curve": [round(75 + 15 * math.sin(i / 7.0), 1) for i in range(bodov)]}
    s.update(kw)
    return s


def _popis(relacie):
    a = types.SimpleNamespace(hr_critical_bpm=110, ALGORITMUS_SVET="play",
                              _history_sessions=lambda: relacie)
    return _app()._kriticky_popis(a)


def test_tri_kratke_relacie_netvrdia_vypocitanu_hranicu(sk):
    """Tri 4-minutove relacie maju spolu 720 bodov krivky (nad
    `KRITICKY_MIN_BODOV`), no hranica sa z nich neuci - veta to musi vediet."""
    kratke = [_relacia(4) for _ in range(3)]
    assert sum(len(r["curve"]) for r in kratke) >= hr_stats.KRITICKY_MIN_BODOV
    assert hr_stats.dynamicky_kriticky(kratke) == hr_stats.KRITICKY_ZALOHA
    assert _popis(kratke) == i18n.tr("settings.hr_critical_learning",
                                     bpm=110, treba=3)


def test_kratke_relacie_sa_nerataju_do_troch_potrebnych(sk):
    dve_dlhe = [_relacia(20) for _ in range(2)]
    kratke = [_relacia(3) for _ in range(3)]
    assert hr_stats.dynamicky_kriticky(dve_dlhe + kratke) == hr_stats.KRITICKY_ZALOHA
    assert _popis(dve_dlhe + kratke) == i18n.tr("settings.hr_critical_learning",
                                                bpm=110, treba=1)


def test_tri_dlhe_relacie_vetu_prepnu_na_vypocitanu(sk):
    """Predpoklad testov vyssie: s tromi relaciami po 5 minut sa veta naozaj
    prepne - inak by nemerali nic."""
    dlhe = [_relacia(5) for _ in range(3)]
    assert hr_stats.dynamicky_kriticky(dlhe) != hr_stats.KRITICKY_ZALOHA
    assert _popis(dlhe + [_relacia(2)]) == i18n.tr(
        "settings.hr_critical_computed", bpm=110, n=3)


class _Stop(Exception):
    pass


def _otvor(historia):
    """Spusti skutocny `_open_hr_session` po cast s ucenim hranic. Atrapa
    `hud.configure` ho zastavi hned za blokom try/except, ktory nas zaujima."""
    def _stop(**_kw):
        raise _Stop()
    a = types.SimpleNamespace(
        hr_critical_bpm=110, ALGORITMUS_SVET="play", world="play",
        hr_stats=types.SimpleNamespace(long_baseline=None, critical_bpm=110),
        hud=types.SimpleNamespace(configure=_stop),
        _history_sessions=lambda: historia, _prah_z_relacii=0)
    with pytest.raises(_Stop):
        _app()._open_hr_session(a, prepoj=False)
    return a


def test_pocet_do_vety_o_prahu_rata_tym_istym_pravidlom():
    """Pokazene `duration_s` (text, nekonecno) sa neuci a ani nezhodi vypocet:
    pocet sedi s `je_dost_dlha` a dlhodoba zakladna prezije."""
    historia = [_relacia(20) for _ in range(3)]
    historia += [_relacia(20, duration_s="dlho"),
                 _relacia(20, duration_s=float("inf")),
                 _relacia(4)]
    a = _otvor(historia)
    assert a.hr_stats.long_baseline is not None, "zakladna sa nesmie zahodit"
    assert a._prah_z_relacii == 3
    assert a._prah_z_dat is not None
    assert a.hr_critical_bpm != int(hr_stats.KRITICKY_ZALOHA)
