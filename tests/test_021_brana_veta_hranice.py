# -*- coding: utf-8 -*-
"""The sentence about the high heart rate limit in settings (0.2.1,
final gate).

Since 0.2.1 `hr_stats.dynamicky_kriticky` learns only from sessions at least
5 minutes long (`je_dost_dlha`). But `app._kriticky_popis` still counted
EVERY clean play session - after three short sessions (pairing the watch)
settings claimed "computed from 3 of your play sessions", while in fact the
fallback of 110 applied. Exactly the kind of sentence SOUL.md considers a
bug.

The same rule must also apply to `_prah_z_relacii` in `_open_hr_session`
(the count for the sentence about the load threshold): `float(duration_s)`
right there raised an exception on a broken number, and the `except` threw
away the long-term baseline too.

Without Tk - the real `DandurfApp` methods on a small dummy (like
test_worlds.py).
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
    """A clean play session with a smooth curve (1 s cadence, at most
    `CURVE_POINTS` points) - `je_podozriva` leaves it alone."""
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
    """Three 4-minute sessions have 720 curve points together (above
    `KRITICKY_MIN_BODOV`), but the limit does not learn from them - the
    sentence has to know that."""
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
    """Premise of the tests above: with three 5-minute sessions the sentence
    really does switch - otherwise they would measure nothing."""
    dlhe = [_relacia(5) for _ in range(3)]
    assert hr_stats.dynamicky_kriticky(dlhe) != hr_stats.KRITICKY_ZALOHA
    assert _popis(dlhe + [_relacia(2)]) == i18n.tr(
        "settings.hr_critical_computed", bpm=110, n=3)


class _Stop(Exception):
    pass


def _otvor(historia):
    """Runs the real `_open_hr_session` up to the part that learns the
    limits. The `hud.configure` dummy stops it right after the try/except
    block we care about."""
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
    """A broken `duration_s` (text, infinity) is not learned from and does
    not break the computation: the count matches `je_dost_dlha` and the
    long-term baseline survives."""
    historia = [_relacia(20) for _ in range(3)]
    historia += [_relacia(20, duration_s="dlho"),
                 _relacia(20, duration_s=float("inf")),
                 _relacia(4)]
    a = _otvor(historia)
    assert a.hr_stats.long_baseline is not None, "zakladna sa nesmie zahodit"
    assert a._prah_z_relacii == 3
    assert a._prah_z_dat is not None
    assert a.hr_critical_bpm != int(hr_stats.KRITICKY_ZALOHA)
