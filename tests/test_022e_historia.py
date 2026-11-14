# -*- coding: utf-8 -*-
"""Historia citatelne (0.2.2, davka 4 auditu UX).

  * cisla vo vetach podla jazyka appky (`i18n.cislo`): desatinna ciarka v
    sk cs de fr es pt ru bg, bodka v en ja zh, skutocny minus U+2212,
  * mriezka Pravidelnost: najviac 26 tyzdnov od prvej relacie, mesiace nad
    stlpcami a dni vlavo (pondelok prvy) z i18n, nie z Windowsu,
  * zataz vsade ako "x/100", koniec osi dlhej relacie ako "2 h 18 min".

Synteticke data, bez okna.
"""
import os
import sys
import time
import types
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
import ui_kit  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

MINUS = "−"


@pytest.fixture
def sk():
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


# --------------------------------------------------------------------------
# i18n.cislo
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jazyk", ["sk", "cs", "de", "fr", "es", "pt", "ru", "bg"])
def test_desatinna_ciarka(jazyk):
    assert i18n.cislo(2.04, 1, lang=jazyk) == "2,0"
    assert i18n.cislo(-2.04, 1, sign=True, lang=jazyk) == MINUS + "2,0"
    assert i18n.cislo(1.55, 2, sign=True, lang=jazyk) == "+1,55"


@pytest.mark.parametrize("jazyk", ["en", "ja", "zh"])
def test_desatinna_bodka(jazyk):
    assert i18n.cislo(2.04, 1, lang=jazyk) == "2.0"
    assert i18n.cislo(-2.04, 1, sign=True, lang=jazyk) == MINUS + "2.0"
    assert i18n.cislo(1.5, 1, sign=True, lang=jazyk) == "+1.5"


def test_vsetky_jazyky_appky_maju_pravidlo():
    for jazyk in i18n.LANGUAGES:
        text = i18n.cislo(0.5, 1, lang=jazyk)
        assert text in ("0,5", "0.5"), jazyk


def test_nula_bez_znamienka_a_minus_nikdy_spojovnik():
    assert i18n.cislo(0.0, 1, sign=True, lang="sk") == "0,0"
    assert i18n.cislo(-0.04, 1, sign=True, lang="sk") == "0,0", "ziadne −0,0"
    assert i18n.cislo(0.04, 1, sign=True, lang="en") == "0.0", "ziadne +0.0"
    assert "-" not in i18n.cislo(-3, 0, lang="sk")
    assert i18n.cislo(-3, 0, lang="sk") == MINUS + "3"


def test_necislo_a_nekonecno():
    assert i18n.cislo(float("nan"), 1) == "—"
    assert i18n.cislo(float("inf"), 1) == "—"
    assert i18n.cislo("x", 1) == "x"
    assert i18n.cislo(None, 1) == "None"


def test_jazyk_appky_je_predvoleny(sk):
    assert i18n.cislo(1.25, 2) == "1,25"
    i18n.set_lang("en")
    assert i18n.cislo(1.25, 2) == "1.25"


def test_veta_trendu_v_slovencine(sk):
    veta = i18n.tr("history.trend_delta", first=61, last=59,
                   slope=i18n.cislo(-2.04, 1, sign=True))
    assert veta == "61 → 59 BPM, trend " + MINUS + "2,0 BPM/týždeň"


def test_sablona_trendu_nema_vlastny_format_cisla():
    for jazyk, text in i18n.STRINGS["history.trend_delta"].items():
        assert "{slope}" in text and "{slope:" not in text, jazyk


class _Label:
    def __init__(self):
        self.text = None

    def winfo_exists(self):
        return True

    def configure(self, **kw):
        self.text = kw.get("text", self.text)


class _Graf:
    def set_series(self, values, **kw):
        self.values, self.kw = list(values), kw


def _relacia(**kw):
    s = {"started": time.time() - 86400, "duration_s": 3600.0, "peak_stress": 83,
         "auto_triggers": 3, "triggers": 3, "avg_bpm": 72, "max_bpm": 131,
         "baseline_bpm": 61, "time_over_s": 125.0,
         "zone_seconds": {"calm": 1800.0, "raised": 1800.0}}
    s.update(kw)
    return s


def _trend(metric, sessions):
    D = _app()
    a = types.SimpleNamespace(
        history_trend_caption=_Label(), history_trend=_Graf(),
        history_trend_delta=_Label(), pal=theme.tokens(theme.ZEN),
        history_metric=metric, history_period=hr_stats.PERIOD_WEEK,
        _history_sessions=lambda: sessions, _world_sessions=lambda: sessions)
    for name in ("HISTORY_METRICS", "_METRIC_BUCKET_KEY", "_METRIC_BARS",
                 "_METRIC_SCALE", "_METRIC_DECIMALS"):
        setattr(a, name, getattr(D, name))
    D._refresh_history_trend(a)
    return a.history_trend_delta.text


def test_trend_pokojovej_zakladne_pise_minus_a_ciarku(sk, monkeypatch):
    monkeypatch.setattr(hr_stats, "baseline_trend",
                        lambda s: {"insufficient_span": False, "slope_per_week": -2.04})
    now = time.time()
    text = _trend("baseline", [_relacia(started=now - 4 * 86400, baseline_bpm=61),
                               _relacia(started=now - 1 * 86400, baseline_bpm=59)])
    assert text.endswith("trend " + MINUS + "2,0 BPM/týždeň"), text
    assert "-2.0" not in text


def test_trend_s_desatinami_pise_ciarku(sk):
    now = time.time()
    text = _trend("breath", [_relacia(started=now - 3 * 86400, auto_triggers=3),
                             _relacia(started=now - 1 * 86400, auto_triggers=1)])
    assert text == "3,0 → 1,0", text


def test_graf_ucinnosti_pise_cislo_podla_jazyka():
    src = zdroj_suboru("ui_kit.py")
    graf = src[src.index("class CueEffectChart"):src.index("class DayGrid")]
    assert "cislo(delta, 1, sign=True)" in graf
    assert "%+.1f" not in graf


# --------------------------------------------------------------------------
# Pravidelnost
# --------------------------------------------------------------------------

def test_mesiace_a_dni_vo_vsetkych_jazykoch():
    mesiace, dni = i18n.STRINGS["history.grid_months"], i18n.STRINGS["history.grid_weekdays"]
    assert set(mesiace) == set(dni) == set(i18n.LANGUAGES)
    for jazyk in i18n.LANGUAGES:
        assert len(mesiace[jazyk].split()) == 12, jazyk
        assert len(dni[jazyk].split()) == 7, jazyk
        assert len(set(dni[jazyk].split())) == 7, jazyk
    # pondelok prvy, nie nedela
    assert dni["sk"].split()[0] == "po" and dni["en"].split()[0] == "Mon"
    assert dni["de"].split()[0] == "Mo" and dni["ja"].split()[0] == "月"
    assert mesiace["sk"].split()[10] == "nov"
    for jazyk in ("ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg"):
        assert dni[jazyk] != dni["en"], jazyk


def test_popisok_poctu_dni_nesie_tyzdne():
    for jazyk, text in i18n.STRINGS["history.days_played"].items():
        assert "{weeks}" in text, jazyk
    assert i18n.tr_lang("sk", "history.days_played", weeks=26) == "Dní s reláciou · 26 týž."


def test_stlpce_mesiacov():
    prvy = date(2026, 8, 3)              # pondelok
    stlpce = ui_kit.DayGrid.stlpce_mesiacov(prvy, 0, 16)
    assert stlpce[0] == (0, 8), "prvy stlpec nesie svoj mesiac"
    for stlpec, mesiac in stlpce[1:]:
        dni = [prvy + timedelta(days=stlpec * 7 + r) for r in range(7)]
        assert any(d.day == 1 and d.month == mesiac for d in dni), (stlpec, mesiac)
    assert [m for _s, m in stlpce] == [8, 9, 10, 11]


def test_prvy_stlpec_bez_popisku_ked_by_sa_prekryl():
    # 27. 7. 2026 je pondelok - august zacina uz v prvom stlpci, jul by sa
    # s nim prekryl
    stlpce = ui_kit.DayGrid.stlpce_mesiacov(date(2026, 7, 27), 0, 8)
    assert stlpce[0] == (0, 8)
    assert [m for _s, m in stlpce].count(7) == 0


def _relacia_pred(dni, now):
    return {"started": now - dni * 86400.0, "duration_s": 3600.0}


def test_rytmus_od_prvej_relacie_najviac_26_tyzdnov():
    D = _app()
    a = types.SimpleNamespace(RYTMUS_MIN_TYZDNOV=D.RYTMUS_MIN_TYZDNOV,
                              RYTMUS_MAX_TYZDNOV=D.RYTMUS_MAX_TYZDNOV)
    now = time.mktime((2026, 11, 14, 20, 0, 0, 0, 0, -1))
    assert D._rytmus_tyzdne(a, [], now=now) == 8
    assert D._rytmus_tyzdne(a, [_relacia_pred(10, now)], now=now) == 8
    tyzdne = D._rytmus_tyzdne(a, [_relacia_pred(70, now)], now=now)
    assert 10 <= tyzdne <= 12
    assert D._rytmus_tyzdne(a, [_relacia_pred(400, now)], now=now) == 26
    assert D._rytmus_tyzdne(a, [{"started": "zle"}, None], now=now) == 8
    assert D.RYTMUS_MAX_TYZDNOV == 26


def test_mriezka_dostane_mesiace_dni_a_najviac_pol_roka(sk):
    D = _app()
    zaznam = {}

    class _Mriezka:
        def winfo_exists(self):
            return True

        def set_days(self, days, legend=("", ""), months=(), weekdays=()):
            zaznam.update(days=days, months=months, weekdays=weekdays)

    a = types.SimpleNamespace(
        history_daygrid=_Mriezka(), history_days_label=_Label(),
        history_days_value=_Label(), RYTMUS_MIN_TYZDNOV=D.RYTMUS_MIN_TYZDNOV,
        RYTMUS_MAX_TYZDNOV=D.RYTMUS_MAX_TYZDNOV)
    a._rytmus_tyzdne = lambda s, now=None: D._rytmus_tyzdne(a, s, now=now)
    now = time.time()
    sessions = [_relacia_pred(d, now) for d in (2, 9, 300)]
    D._refresh_history_rhythm(a, sessions)
    assert len(zaznam["months"]) == 12 and zaznam["months"][0] == "jan"
    assert len(zaznam["weekdays"]) == 7 and zaznam["weekdays"][0] == "po"
    assert len(zaznam["days"]) <= 26 * 7
    assert zaznam["days"][0]["date"].weekday() == 0, "prvy stlpec je pondelok"
    assert a.history_days_label.text == "DNÍ S RELÁCIOU · 26 TÝŽ."
    assert a.history_days_value.text == "2"


# --------------------------------------------------------------------------
# Zataz "x/100" a dlzky
# --------------------------------------------------------------------------

def test_zataz_ako_x_zo_100():
    D = _app()
    assert D._fmt_zataz(83) == "83/100"
    assert D._fmt_zataz(83.6) == "84/100"
    assert D._fmt_zataz(None) == "—"
    assert D._fmt_zataz("zle", "-") == "-"


def test_tabulka_aj_detail_pisu_zataz_rovnako():
    assert '"peak": self._fmt_zataz(session.get("peak_stress"), "—")' in \
        zdroj_metody("_history_detail_values")
    assert 'self._fmt_zataz(s.get("peak_stress"), "-")' in zdroj_suboru("app_history.py")
    assert '"peak_stress", 0)} %' not in zdroj_suboru("app_history.py")


def test_os_stopy_relacie_od_hodiny_ako_dlzka(sk):
    T = ui_kit.SessionTrace
    assert T.os_popisky(600) == ("0:00", "10:00")
    assert T.os_popisky(3599) == ("0:00", "59:59")
    assert T.os_popisky(3600) == ("0 min", "1 h 00 min")
    assert T.os_popisky(8282) == ("0 min", "2 h 18 min")


def test_dlzka_text(sk):
    assert ui_kit.dlzka_text(45 * 60) == "45 min"
    assert ui_kit.dlzka_text(7380) == "2 h 03 min"
    assert ui_kit.dlzka_text("zle") == "—"
