# -*- coding: utf-8 -*-
"""Pat novych kariet na Dnes a Historia ako cely obraz (0.2, widgets-history).

Karty: dlzka relacie, minuty od poslednej hlasky, cas v pokoji, kvalita
signalu, citene vs. merane z poslednej ukoncenej relacie. Historia: graf
aj pre dlzku, pokoj, signal a pocet hlasok; detail relacie so vsetkymi
hodnotami; stlpec pokrytia signalu v CSV.

Bez Tk: ciste funkcie z hr_stats/settings_model a skutocne metody
`DandurfApp` na malej atrape (rovnako ako test_dashboard_cards.py).
"""
import os
import sys
import time
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import theme  # noqa: E402
from settings_model import (  # noqa: E402
    DASHBOARD_MAX_CARDS, DASHBOARD_STAT_IDS, DEFAULT_DASHBOARD_STATS,
    normalize_dashboard_stats, toggle_dashboard_stat,
)

NOVE = ("session_len", "last_cue", "calm_time", "signal", "felt_vs_measured")
NOVE_V_HISTORII = ("session_len", "calm_time", "signal", "breath")


@pytest.fixture
def sk():
    """Texty v slovencine; povodny jazyk sa po teste vrati."""
    povodny = i18n._lang["code"]
    i18n.set_lang("sk")
    yield
    i18n.set_lang(povodny)


def _app():
    import app as app_mod
    return app_mod.DandurfApp


# --------------------------------------------------------------------------
# id a normalizacia
# --------------------------------------------------------------------------

def test_nove_karty_su_v_katalogu_a_predvolene_ostavaju():
    for sid in NOVE:
        assert sid in DASHBOARD_STAT_IDS
    assert DEFAULT_DASHBOARD_STATS == ["baseline", "hrr", "over", "breath"]
    assert len(set(DASHBOARD_STAT_IDS)) == len(DASHBOARD_STAT_IDS)


def test_normalizacia_drzi_nove_id_a_poradie():
    assert normalize_dashboard_stats(["signal", "felt_vs_measured", "hrr"]) == \
        ["signal", "felt_vs_measured", "hrr"]
    assert normalize_dashboard_stats(["signal", "signal", "nic"]) == ["signal"]


def test_strop_styroch_kariet_plati_aj_pre_nove():
    stats = []
    for sid in NOVE:
        stats = toggle_dashboard_stat(stats, sid)
    assert stats == list(NOVE[:DASHBOARD_MAX_CARDS])


def test_katalog_vyberu_ma_kazde_id_raz_a_farbu_z_palety():
    D = _app()
    a = types.SimpleNamespace()
    katalog = D._dashboard_stat_catalog(a)
    assert [k for k, _t, _c in katalog] == list(DASHBOARD_STAT_IDS)
    pal = theme.tokens(theme.ZEN)
    assert all(c in pal for _k, _t, c in katalog)


# --------------------------------------------------------------------------
# i18n
# --------------------------------------------------------------------------

def _ma_vsetky_jazyky(kluc):
    return set(i18n.STRINGS.get(kluc, {})) == set(i18n.LANGUAGES)


def test_kazda_nova_karta_ma_vsetky_texty_vo_vsetkych_jazykoch():
    chyba = [f"metric.{sid}.{cast}" for sid in NOVE
             for cast in ("tag", "title", "short", "more")
             if not _ma_vsetky_jazyky(f"metric.{sid}.{cast}")]
    chyba += [f"dashboard.unit.{sid}" for sid in NOVE
              if not _ma_vsetky_jazyky(f"dashboard.unit.{sid}")]
    chyba += [k for k in ("dashboard.fmt.min", "dashboard.fmt.h_min", "dashboard.fmt.pct")
              if not _ma_vsetky_jazyky(k)]
    assert not chyba, chyba


def test_vysvetlenie_hovori_aj_co_karta_nemeria(sk):
    """Kazda `more` veta ma povedat hranicu metriky, nielen co meria."""
    from i18n import tr
    nie = ("nie ", "nie je", "neznamená", "nezaráta", "nemusia")
    for sid in NOVE:
        text = tr(f"metric.{sid}.more")
        assert any(n in text for n in nie), sid


def test_felt_vs_measured_nehovori_kto_ma_pravdu(sk):
    from i18n import tr
    more = tr("metric.felt_vs_measured.more")
    assert "ani jedno nie je" in more
    assert "vydelená desiatimi" in more, "musi povedat, co je merane cislo"
    # aj kratka veta (viditelna bez rozbalenia) povie, ze merane je spicka
    assert "špičky" in tr("metric.felt_vs_measured.short")


# --------------------------------------------------------------------------
# hr_stats: hodnoty jednej ulozenej relacie
# --------------------------------------------------------------------------

def _relacia(**kw):
    s = {"started": 1_700_000_000.0, "duration_s": 3600.0, "peak_stress": 83,
         "auto_triggers": 3, "triggers": 5, "avg_bpm": 72, "max_bpm": 131,
         "time_over_s": 125.0, "hrr_bpm": 22, "hrpi": 104,
         "zone_seconds": {"calm": 1800.0, "raised": 900.0, "high": 600.0,
                          "critical": 192.0}}
    s.update(kw)
    return s


def test_cas_v_pokoji_z_pasiem_alebo_none():
    assert hr_stats.cas_v_pokoji_s(_relacia()) == 1800.0
    assert hr_stats.cas_v_pokoji_s(_relacia(zone_seconds={})) is None
    assert hr_stats.cas_v_pokoji_s(_relacia(zone_seconds=None)) is None
    assert hr_stats.cas_v_pokoji_s(
        _relacia(zone_seconds={"calm": "x", "raised": 1})) is None
    # pasma su, pokoj nula: to je vypoved, nie "nevieme"
    assert hr_stats.cas_v_pokoji_s(
        _relacia(zone_seconds={"calm": 0.0, "raised": 60.0})) == 0.0


def test_hlasky_su_tie_co_appka_poslala_sama():
    assert hr_stats.hlasky_relacie(_relacia()) == 3
    stara = _relacia()
    del stara["auto_triggers"]
    assert hr_stats.hlasky_relacie(stara) == 5
    assert hr_stats.hlasky_relacie({"started": 1}) is None
    assert hr_stats.hlasky_relacie(_relacia(auto_triggers="?")) is None


@pytest.mark.parametrize("peak,cakam", [
    (83, 8), (45, 5), (44, 4), (0, 0), (100, 10), (5, 1), (4.9, 0),
    (None, None), ("x", None), (float("nan"), None), (-3, None), (250, 10)])
def test_namerana_zataz_na_skale_0_10(peak, cakam):
    assert hr_stats.namerana_zataz_0_10({"peak_stress": peak}) == cakam


def test_citene_a_merane():
    assert hr_stats.citene_a_merane(_relacia(felt_load=6)) == (6, 8)
    # preskoceny dotaznik -> nie je co porovnat
    assert hr_stats.citene_a_merane(_relacia()) is None
    assert hr_stats.citene_a_merane(_relacia(felt_load=None)) is None
    # spicka chyba -> citene ostava, merane "nevieme"
    assert hr_stats.citene_a_merane(_relacia(felt_load=3, peak_stress=None)) == (3, None)
    assert hr_stats.citene_a_merane(None) is None


def test_posledna_relacia_podla_casu_nie_poradia():
    a, b, c = _relacia(started=100.0), _relacia(started=300.0), _relacia(started=200.0)
    assert hr_stats.posledna_relacia([a, b, c]) is b
    assert hr_stats.posledna_relacia([a, "junk", None, {"started": "x"}]) is a
    assert hr_stats.posledna_relacia([]) is None


def test_posledna_relacia_preskoci_importovanu():
    """Zlucany cudzi export (`imported`) nie je "tvoja posledna relacia" -
    aj keby bol novsi, karta ma ukazat tvoje cisla, alebo "—"."""
    moja = _relacia(started=100.0, felt_load=4)
    cudzia = _relacia(started=500.0, felt_load=9, imported=True)
    assert hr_stats.posledna_relacia([moja, cudzia]) is moja
    assert hr_stats.posledna_relacia([cudzia]) is None


# --------------------------------------------------------------------------
# hr_stats: buckety grafu
# --------------------------------------------------------------------------

def test_bucket_spriemeruje_nove_metriky_na_relaciu():
    den = time.mktime((2026, 9, 10, 20, 0, 0, 0, 0, -1))
    sessions = [
        _relacia(started=den, duration_s=3600.0, auto_triggers=2),
        _relacia(started=den + 3600, duration_s=1800.0, auto_triggers=1,
                 zone_seconds={"calm": 600.0, "raised": 1200.0}),
    ]
    b = hr_stats.aggregate_by_period(sessions, hr_stats.PERIOD_DAY)
    assert len(b) == 1
    b = b[0]
    assert b["duration_s"] == pytest.approx(2700.0)
    assert b["calm_s"] == pytest.approx(1200.0)
    assert b["cues"] == pytest.approx(1.5)
    # pokrytie: (3492/3600 + 1800/1800) / 2
    assert b["coverage"] == pytest.approx((3492 / 3600.0 + 1.0) / 2)
    for kluc in hr_stats.BUCKET_METRICS:
        assert kluc in b


def test_bucket_bez_dat_nove_metriky_none_nie_nula():
    den = time.mktime((2026, 9, 10, 20, 0, 0, 0, 0, -1))
    stara = {"started": den, "baseline_bpm": 60}
    b = hr_stats.aggregate_by_period([stara], hr_stats.PERIOD_DAY)[0]
    assert b["duration_s"] is None and b["calm_s"] is None
    assert b["coverage"] is None and b["cues"] is None
    os_ = hr_stats.bucket_axis([], hr_stats.PERIOD_DAY, den, den + 2 * 86400)
    assert len(os_) == 3
    assert all(set(hr_stats.BUCKET_METRICS) <= set(x) for x in os_)
    assert all(x[k] is None for x in os_ for k in hr_stats.BUCKET_METRICS)


# --------------------------------------------------------------------------
# HeartStats: zive hodnoty
# --------------------------------------------------------------------------

def test_posledna_hlaska_len_automaticka_a_dorucena():
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.last_auto_cue_ts() is None
    st.note_trigger(ts=1000.0, auto=True, source="auto")
    st.note_trigger(ts=1100.0, auto=False, source="key")          # klavesa / Test
    assert st.last_auto_cue_ts() == 1000.0
    st.note_trigger(ts=1200.0, auto=True, source="auto", delivered=False)
    assert st.last_auto_cue_ts() == 1000.0, "nevykreslena hlaska sa nerata"
    st.note_trigger(ts=1300.0, auto=True, source="auto", arm="silent")
    assert st.last_auto_cue_ts() == 1300.0, "tiche rameno ma vizual - rata sa"
    st.reset_session()
    assert st.last_auto_cue_ts() is None


def test_cas_v_pokoji_zivo():
    st = hr_stats.HeartStats(critical_bpm=110)
    assert st.calm_seconds() is None, "bez tepu nevieme"
    st.long_baseline = 60.0
    t0 = 1_000_000.0
    for i in range(20):
        st.add(62, ts=t0 + i)
    assert st.calm_seconds() == pytest.approx(19.0)
    for i in range(20, 30):
        st.add(80, ts=t0 + i)                  # +20 nad pokojom = zvysena
    assert st.calm_seconds() == pytest.approx(20.0)


def test_cas_v_pokoji_prvy_vecer_kym_nie_je_zakladna():
    st = hr_stats.HeartStats(critical_bpm=110)
    t0 = 1_000_000.0
    for i in range(5):
        st.add(62, ts=t0 + i)
    assert st._zony_cakaju, "predpoklad: sekundy cakaju na zakladnu"
    assert st.calm_seconds() is None


# --------------------------------------------------------------------------
# DandurfApp._dashboard_stat_value pre nove karty
# --------------------------------------------------------------------------

def _atrapa(otvorena=True, sessions=()):
    D = _app()
    a = types.SimpleNamespace(
        hr_stats=hr_stats.HeartStats(critical_bpm=110),
        _hr_session_open=otvorena,
        # Karty na Dnes ukazuju len aktualny svet (B3-worlds); relacie
        # bez stitku patria Hre.
        world="play",
        _history_cached=lambda: list(sessions),
        _fmt_dlzka=D._fmt_dlzka, _fmt_pokrytie=D._fmt_pokrytie,
        _fmt_citene_merane=D._fmt_citene_merane,
    )
    a.hodnota = lambda sid: D._dashboard_stat_value(a, sid)[0]
    a.jednotka = lambda sid: D._dashboard_stat_value(a, sid)[1]
    return a


def test_dlzka_relacie(sk):
    a = _atrapa()
    a.hr_stats.session_start = time.time() - 3900
    assert a.hodnota("session_len") == "1 h 05 min"
    a.hr_stats.session_start = time.time() - 45 * 60 - 20
    assert a.hodnota("session_len") == "45 min"
    assert a.jednotka("session_len") == i18n.tr("dashboard.unit.session_len")
    assert _atrapa(otvorena=False).hodnota("session_len") == "—"


def test_od_poslednej_hlasky(sk):
    a = _atrapa()
    assert a.hodnota("last_cue") == "—"
    a.hr_stats.note_trigger(ts=time.time() - 125, auto=True, source="auto")
    assert a.hodnota("last_cue") == "2 min"
    a.hr_stats.note_trigger(ts=time.time() - 5, auto=False, source="key")
    assert a.hodnota("last_cue") == "2 min", "Test/klavesa sa nerata"
    a._hr_session_open = False
    assert a.hodnota("last_cue") == "—"


def test_cas_v_pokoji_karta(sk):
    a = _atrapa()
    assert a.hodnota("calm_time") == "—"
    a.hr_stats.long_baseline = 60.0
    t0 = time.time() - 200
    for i in range(0, 200, 2):
        a.hr_stats.add(62, ts=t0 + i)
    assert a.hodnota("calm_time") == "3 min"          # 198 s


def test_signal_karta(sk):
    a = _atrapa()
    assert a.hodnota("signal") == "—", "bez tepu nevieme"
    st = a.hr_stats
    st.long_baseline = 60.0
    now = time.time()
    t0 = now - 120
    for i in range(0, 60):
        st.add(62, ts=t0 + i)
    st.note_dropout(od=t0 + 59)
    st.clear_live()
    for i in range(90, 121):
        st.add(62, ts=t0 + i)
    text = a.hodnota("signal")
    pokrytie = st.signal_coverage
    assert text == f"{round(pokrytie * 100)} % · 1×"
    assert pokrytie < 0.9
    st.dropouts = 0
    assert a.hodnota("signal") == f"{round(pokrytie * 100)} %"
    a._hr_session_open = False
    assert a.hodnota("signal") == "—", "po zatvoreni by pokrytie ticho klesalo"


def test_signal_prvu_minutu_pomlcka(sk):
    a = _atrapa()
    a.hr_stats.long_baseline = 60.0
    t0 = time.time() - 20
    for i in range(20):
        a.hr_stats.add(62, ts=t0 + i)
    assert a.hodnota("signal") == "—"


def test_citene_vs_merane_karta(sk):
    stara = _relacia(started=100.0, felt_load=2)
    posledna = _relacia(started=200.0, felt_load=6, peak_stress=83)
    assert _atrapa(sessions=[posledna, stara]).hodnota("felt_vs_measured") == "6 · 8"
    preskoceny = _relacia(started=300.0)
    assert _atrapa(sessions=[stara, preskoceny]).hodnota("felt_vs_measured") == "—", \
        "posledna relacia bez dotaznika -> pomlcka, nie starsia relacia"
    assert _atrapa(sessions=[]).hodnota("felt_vs_measured") == "—"
    bez_spicky = _relacia(started=300.0, felt_load=0, peak_stress=None)
    assert _atrapa(sessions=[bez_spicky]).hodnota("felt_vs_measured") == "0 · —"


def test_citene_vs_merane_pokazena_historia_nezhodi_kartu(sk):
    a = _atrapa()

    def zle():
        raise OSError("disk")
    a._history_cached = zle
    assert a.hodnota("felt_vs_measured") == "—"


# --------------------------------------------------------------------------
# Historia: metriky grafu
# --------------------------------------------------------------------------

def test_historia_ma_nove_metriky_a_kazda_je_zapojena():
    D = _app()
    kluce = [k for k, _t, _c in D.HISTORY_METRICS]
    for k in NOVE_V_HISTORII:
        assert k in kluce
    assert len(set(kluce)) == len(kluce)
    pal = theme.tokens(theme.ZEN)
    for k, title_key, color in D.HISTORY_METRICS:
        assert D._METRIC_BUCKET_KEY[k] in hr_stats.BUCKET_METRICS, k
        info = D._METRIC_INFO_KEY[k]
        for kluc in (title_key, f"metric.{info}.short", f"metric.{info}.more",
                     f"history.unit.{k}"):
            assert _ma_vsetky_jazyky(kluc), kluc
        assert color in pal, color


def test_stlpce_a_ciary():
    D = _app()
    assert {"session_len", "calm_time", "breath", "over", "peak"} <= D._METRIC_BARS
    assert "signal" not in D._METRIC_BARS, "signal zije pri 95-100 %, stlpec by ho schoval"
    assert "baseline" not in D._METRIC_BARS and "hrr" not in D._METRIC_BARS
    assert D._METRIC_SCALE["session_len"] == pytest.approx(1 / 60.0)
    assert D._METRIC_SCALE["calm_time"] == pytest.approx(1 / 60.0)
    assert D._METRIC_SCALE["signal"] == 100.0


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


@pytest.mark.parametrize("metric,cakam,bars,decimals", [
    ("session_len", [60.0, 30.0], True, 0),
    ("calm_time", [30.0, 10.0], True, 0),
    ("signal", [97.0, 100.0], False, 0),
    ("breath", [3.0, 1.0], True, 1),
])
def test_graf_historie_kresli_nove_metriky(sk, metric, cakam, bars, decimals):
    D = _app()
    now = time.time()
    sessions = [
        _relacia(started=now - 3 * 86400, duration_s=3600.0, auto_triggers=3,
                 zone_seconds={"calm": 1800.0, "raised": 1692.0}),
        _relacia(started=now - 1 * 86400, duration_s=1800.0, auto_triggers=1,
                 zone_seconds={"calm": 600.0, "raised": 1200.0}),
    ]
    a = types.SimpleNamespace(
        history_trend_caption=_Label(), history_trend=_Graf(),
        history_trend_delta=_Label(), pal=theme.tokens(theme.ZEN),
        history_metric=metric, history_period=hr_stats.PERIOD_WEEK,
        _history_sessions=lambda: sessions,
        # Graf cita len relacie aktualneho sveta (B3-worlds).
        _world_sessions=lambda: sessions)
    for name in ("HISTORY_METRICS", "_METRIC_BUCKET_KEY", "_METRIC_BARS",
                 "_METRIC_SCALE", "_METRIC_DECIMALS"):
        setattr(a, name, getattr(D, name))
    D._refresh_history_trend(a)
    hodnoty = [v for v in a.history_trend.values if v is not None]
    assert hodnoty == pytest.approx(cakam)
    assert a.history_trend.kw["bars"] is bars
    assert a.history_trend.kw["decimals"] == decimals
    assert i18n.tr(f"history.unit.{metric}") in a.history_trend_caption.text
    assert "→" in a.history_trend_delta.text


# --------------------------------------------------------------------------
# Historia: detail relacie ukazuje vsetko
# --------------------------------------------------------------------------

def test_detail_ma_vsetky_hodnoty_relacie():
    D = _app()
    kluce = [k for k, _l, _c in D.HISTORY_DETAIL_CELLS]
    assert kluce == ["duration", "avg", "max", "calm", "over", "breath",
                     "peak", "hrr", "hrpi", "signal", "felt"]
    pal = theme.tokens(theme.ZEN)
    for _k, label_key, color in D.HISTORY_DETAIL_CELLS:
        assert _ma_vsetky_jazyky(label_key), label_key
        assert color in pal


def _detail(session):
    D = _app()
    a = types.SimpleNamespace(
        _fmt_dlzka=D._fmt_dlzka, _fmt_pokrytie=D._fmt_pokrytie,
        _fmt_citene_merane=D._fmt_citene_merane, _fmt_minutes=D._fmt_minutes)
    return D._history_detail_values(a, session)


def test_detail_hodnoty(sk):
    v = _detail(_relacia(duration_s=3900.0, felt_load=6))
    assert v == {
        "duration": "1 h 05 min", "avg": "72", "max": "131", "calm": "30 min",
        "over": "2:05", "breath": "3", "peak": "83", "hrr": "+22",
        "hrpi": "104", "signal": "90 %", "felt": "6 · 8",
    }
    assert set(v) == {k for k, _l, _c in _app().HISTORY_DETAIL_CELLS}


def test_detail_stara_relacia_pomlcky_nie_nuly(sk):
    v = _detail({"started": 1_700_000_000.0})
    for kluc in ("duration", "avg", "max", "calm", "over", "breath", "peak",
                 "hrr", "hrpi", "signal", "felt"):
        assert v[kluc] == "—", kluc
    # nula je vypoved, nie "nevieme"
    v = _detail(_relacia(time_over_s=0.0, auto_triggers=0))
    assert v["over"] == "0:00" and v["breath"] == "0"


# --------------------------------------------------------------------------
# CSV: stlpec pokrytia signalu
# --------------------------------------------------------------------------

STARE_STLPCE = (
    "date", "start", "duration_min", "avg_bpm", "min_bpm", "max_bpm",
    "baseline_bpm", "over_min", "breathing", "peak_stress", "hrr_bpm", "hrpi",
    "calm_min", "raised_min", "high_min", "critical_min", "longest_above_s",
    "above_runs", "cancelled_dip", "cancelled_gap", "hold_s", "context",
    "activity", "hud_seen", "note", "sleep", "felt_load", "valence",
    "body_peak", "cue_verdict", "confounded")


# words-and-fixes (0.2): za `signal` pribudli styri stlpce, zase na konci.
NOVE_STLPCE = ("world", "dropouts", "blind_s", "pause_episodes")
I_SIGNAL = len(STARE_STLPCE)


def test_csv_ma_stlpec_signal_a_nove_na_konci_a_stare_stoja():
    assert hr_stats.CSV_COLUMNS[:I_SIGNAL] == STARE_STLPCE
    assert hr_stats.CSV_COLUMNS[I_SIGNAL] == "signal"
    assert hr_stats.CSV_COLUMNS[I_SIGNAL + 1:] == NOVE_STLPCE
    for kluc in hr_stats.CSV_COLUMNS:
        assert _ma_vsetky_jazyky(f"history.export_col.{kluc}"), kluc


def test_csv_bunka_signalu():
    riadok = hr_stats.session_row(_relacia())
    assert len(riadok) == len(hr_stats.CSV_COLUMNS)
    assert riadok[I_SIGNAL] == "97%"                  # 3492 / 3600
    assert hr_stats.session_row({"started": 1_700_000_000})[I_SIGNAL] == ""


def test_csv_export_zapise_signal(tmp_path):
    cesta = str(tmp_path / "r.csv")
    hr_stats.export_sessions_csv([_relacia()], cesta)
    with open(cesta, encoding="utf-8-sig", newline="") as fh:
        riadky = [r for r in fh.read().split("\r\n") if r]
    assert riadky[0].split(";")[I_SIGNAL] == "signal"
    assert riadky[1].split(";")[I_SIGNAL] == "97%"


def _bunky(relacia):
    return dict(zip(hr_stats.CSV_COLUMNS, hr_stats.session_row(relacia)))


def test_csv_svet_je_ten_isty_ako_v_historii():
    """`session_world`: dotaznik > svet zo startu > Hra (aj stara relacia)."""
    assert _bunky(_relacia(world="work"))["world"] == "work"
    assert _bunky(_relacia(world="work", activity="play"))["world"] == "play"
    assert _bunky(_relacia())["world"] == "play"
    assert _bunky({"started": 1_700_000_000})["world"] == "play"
    assert _bunky(_relacia(world="nezmysel"))["world"] == "play"


def test_csv_vypadky_slepy_cas_a_pauzy():
    b = _bunky(_relacia(dropouts=2, blind_s=42.8, pause_episodes=17))
    assert (b["dropouts"], b["blind_s"], b["pause_episodes"]) == ("2", "42,8", "17")
    # nula je vypoved
    b = _bunky(_relacia(dropouts=0, blind_s=0.0, pause_episodes=0))
    assert (b["dropouts"], b["blind_s"], b["pause_episodes"]) == ("0", "0,0", "0")
    # stara relacia ich nema, pokazeny import nezhodi export
    b = _bunky({"started": 1_700_000_000})
    assert (b["dropouts"], b["blind_s"], b["pause_episodes"]) == ("", "", "")
    b = _bunky(_relacia(dropouts="x;y", blind_s=-3, pause_episodes=None))
    assert (b["dropouts"], b["blind_s"], b["pause_episodes"]) == ("", "", "")


def test_csv_hlasky_su_to_iste_cislo_ako_detail():
    """Jedno cislo na relaciu vsade (`hlasky_relacie`)."""
    assert _bunky(_relacia())["breathing"] == "3"      # auto, nie `triggers` 5
    stara = _relacia()
    del stara["auto_triggers"]
    assert _bunky(stara)["breathing"] == "5"
    assert _bunky(_relacia(auto_triggers="?"))["breathing"] == ""


def test_csv_nove_stlpce_maju_hlavicku_sk_en(sk):
    assert i18n.tr("history.export_col.world") == "svet"
    assert i18n.tr("history.export_col.dropouts") == "výpadky tepu"
    assert i18n.tr("history.export_col.blind_s") == "bez signálu (s)"
    assert i18n.tr("history.export_col.pause_episodes") == "pauzy vo vstupe"
    for kluc in NOVE_STLPCE:
        assert i18n.STRINGS[f"history.export_col.{kluc}"]["en"]


def test_tabulka_historie_ukazuje_to_iste_cislo_hlasok():
    """Stlpec „Hlášky" v tabulke rata ako detail, graf aj CSV - nie stare
    `triggers` (to ratalo aj klavesu a tlacidlo „Test")."""
    import ast
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        strom = ast.parse(fh.read())
    funkcia = next(f for f in ast.walk(strom)
                   if isinstance(f, ast.FunctionDef)
                   and f.name == "_refresh_history_page")
    zdroj = ast.unparse(funkcia)
    assert "hr_stats.hlasky_relacie(s)" in zdroj
    assert "'triggers'" not in zdroj and '"triggers"' not in zdroj
