"""Testy pre to, z coho sa kreslia grafy: tvar relacie, pasma, kalendarna
mriezka, serie dni a "bezne rozpatie".

Vsetko bez Tk. Kde sa da overit len kreslenie (ui_kit), test cita ZDROJ -
rovnaky pristup ako test_theme_recolor.py, lebo GUI tu nebezi.
"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_stats
import theme as theme_mod


def _read(name):
    with open(os.path.join(os.path.dirname(__file__), "..", name),
              encoding="utf-8") as fh:
        return fh.read()


def _samples(values, start=1000.0, step=1.0):
    return [(start + i * step, float(v)) for i, v in enumerate(values)]


def _session(started, **kwargs):
    base = {"started": started, "duration_s": 3600.0, "samples": 3600}
    base.update(kwargs)
    return base


# --------------------------------------------------------------------------
# downsample / trace / curve
# --------------------------------------------------------------------------

def test_downsample_prerieduje_cely_usek_nie_len_koniec():
    """Orezanim by z dvojhodinovej relacie ostala poslednych 10 minut."""
    out = hr_stats.downsample(list(range(1000)), 10)
    assert len(out) == 10
    assert out[0] == 0
    assert out[-1] >= 880, "posledny bod ma byt z konca relacie"
    assert out == sorted(out), "poradie sa nesmie zamiesat"


def test_downsample_kratky_vstup_nechava_tak():
    assert hr_stats.downsample([1, 2, 3], 10) == [1, 2, 3]
    assert hr_stats.downsample([], 10) == []


def test_trace_je_cela_relacia_a_series_je_zive_okno():
    stats = hr_stats.HeartStats(110)
    for i, bpm in enumerate([60 + (i % 40) for i in range(2000)]):
        stats.add(bpm, ts=1000.0 + i)
    trace = stats.trace()
    assert len(trace) == hr_stats.CURVE_POINTS
    # `series` drzi len HISTORY_SECONDS, `trace` cely vecer - to su dve
    # rozne otazky a nesmu vratit to iste
    assert trace[0] != stats.series(hr_stats.CURVE_POINTS)[0]


def test_summary_uklada_krivku_relacie():
    stats = hr_stats.HeartStats(110)
    for i in range(600):
        stats.add(70 + (i % 20), ts=1000.0 + i)
    summary = stats.summary()
    curve = summary["curve"]
    assert len(curve) == hr_stats.CURVE_POINTS
    assert all(isinstance(v, int) for v in curve), "krivka ma byt cela cisla"
    assert summary["baseline_bpm"] and summary["critical_bpm"], (
        "pasma krivky sa dopocitavaju z tychto dvoch - bez nich sa nakreslit neda")


def test_historia_uchova_dost_relacii_na_rocny_pohlad():
    """Stranka Historia ponuka obdobie 'Rok'. Pri 60 relaciach by rocny
    graf ukazoval dva mesiace a tvaril sa ako rok."""
    assert hr_stats.PERIOD_YEAR in hr_stats.PERIODS
    assert hr_stats.MAX_SESSIONS >= 365


# --------------------------------------------------------------------------
# pasma
# --------------------------------------------------------------------------

def test_zone_of_bpm_hranice():
    assert hr_stats.zone_of_bpm(65, 60, 110) == hr_stats.ZONE_CALM
    assert hr_stats.zone_of_bpm(70, 60, 110) == hr_stats.ZONE_RAISED
    assert hr_stats.zone_of_bpm(85, 60, 110) == hr_stats.ZONE_HIGH
    assert hr_stats.zone_of_bpm(110, 60, 110) == hr_stats.ZONE_CRITICAL


def test_time_in_zones_pocita_tou_istou_funkciou_ako_graf():
    """Pas pasiem v grafe a sucet sekund pod nim musia hovorit to iste."""
    values = [62] * 60 + [75] * 60 + [90] * 60 + [120] * 60
    zones = hr_stats.time_in_zones(_samples(values), critical_bpm=110, baseline=60)
    for bpm, zone in ((62, hr_stats.ZONE_CALM), (75, hr_stats.ZONE_RAISED),
                      (90, hr_stats.ZONE_HIGH), (120, hr_stats.ZONE_CRITICAL)):
        assert zones[hr_stats.zone_of_bpm(bpm, 60, 110)] > 0
        assert hr_stats.zone_of_bpm(bpm, 60, 110) == zone


def test_kazde_pasmo_ma_v_oboch_temach_inu_farbu():
    """Regresia: pasma kreslili success -> accent -> warn -> danger, lenze
    `accent` a `warn` su v Sumi dve takmer rovnake zlate. Styri pasma sa
    tak na jednom pruhu nedali rozlisit."""
    for kluc in (theme_mod.ZEN, theme_mod.MODERN):
        pal = theme_mod.tokens(kluc)
        farby = [theme_mod.zone_color(pal, z).lower()
                 for z in ("calm", "raised", "high", "critical")]
        assert len(set(farby)) == 4, f"tema {kluc}: pasma maju spolocnu farbu ({farby})"


def test_hud_v_hre_farbi_pasma_rovnako_ako_okno():
    """Regresia: HUD mal vlastnu dvojicu success/accent, takze po tom, co
    kazda tema dostala vlastny rad, svietil v hre zelenou aj tam, kde okno
    appky uz kreslilo modru."""
    import hud_paint
    for kluc in (theme_mod.ZEN, theme_mod.MODERN):
        pal = theme_mod.tokens(kluc)
        style = hud_paint.Style(pal)
        for zona in ("calm", "raised", "high", "critical"):
            # `Style` drzi farby ako RGB trojice, tema ako #rrggbb
            assert (hud_paint.zone_color(style, zona)
                    == hud_paint._hex(theme_mod.zone_color(pal, zona))), \
                f"tema {kluc}, pasmo {zona}"


def test_hud_style_bez_palety_nepadne():
    """Style() bez palety (testy, zaloha) musi mat pasma tiez."""
    import hud_paint
    style = hud_paint.Style()
    for zona in ("calm", "raised", "high", "critical"):
        farba = hud_paint.zone_color(style, zona)
        assert isinstance(farba, tuple) and len(farba) == 3


def test_zone_tokens_pokryvaju_vsetky_pasma():
    zony = (hr_stats.ZONE_CALM, hr_stats.ZONE_RAISED, hr_stats.ZONE_HIGH,
            hr_stats.ZONE_CRITICAL)
    assert set(theme_mod.ZONE_TOKENS) == set(zony)


# --------------------------------------------------------------------------
# bezne rozpatie, seria metrik
# --------------------------------------------------------------------------

def test_usual_range_je_kvartilovy_pas():
    lo, hi = hr_stats.usual_range([10, 20, 30, 40, 50, 60, 70, 80])
    assert lo < hi
    assert 10 < lo <= 30 and 50 <= hi < 80


def test_usual_range_mlci_pri_malo_datach():
    assert hr_stats.usual_range([60, 62, 61]) is None
    assert hr_stats.usual_range([]) is None


def test_usual_range_ignoruje_none_a_nezmysly():
    assert hr_stats.usual_range([60, None, 62, "x", 64, 66]) is not None


def test_metric_series_preskakuje_chybajuce_hodnoty():
    sessions = [_session(1000, baseline_bpm=60), _session(2000),
                _session(3000, baseline_bpm=64)]
    assert hr_stats.metric_series(sessions, "baseline_bpm") == [60.0, 64.0]


def test_metric_series_vracia_poslednych_n_chronologicky():
    sessions = [_session(1000 * i, baseline_bpm=i) for i in range(1, 11)]
    assert hr_stats.metric_series(sessions, "baseline_bpm", n=3) == [8.0, 9.0, 10.0]


# --------------------------------------------------------------------------
# mriezka dni a serie
# --------------------------------------------------------------------------

def _ts(days_ago, now):
    return (datetime.fromtimestamp(now) - timedelta(days=days_ago)).timestamp()


def test_day_activity_ma_aj_prazdne_dni():
    """Diery su to, co sa z mriezky cita - nesmu z nej vypadnut."""
    now = time.time()
    cells = hr_stats.day_activity([_session(_ts(2, now), duration_s=600.0)],
                                  days=10, now=now)
    assert len(cells) == 10
    assert cells[-1]["date"] == datetime.fromtimestamp(now).date()
    assert sum(1 for c in cells if c["seconds"] == 0) == 9
    assert [c["seconds"] for c in cells if c["seconds"]] == [600.0]


def test_day_activity_scita_viac_relacii_za_den():
    now = time.time()
    cells = hr_stats.day_activity(
        [_session(_ts(1, now), duration_s=600.0),
         _session(_ts(1, now), duration_s=900.0)], days=5, now=now)
    den = [c for c in cells if c["count"]][0]
    assert den["count"] == 2 and den["seconds"] == 1500.0


def test_day_activity_ignoruje_relacie_mimo_okna():
    now = time.time()
    cells = hr_stats.day_activity([_session(_ts(40, now))], days=7, now=now)
    assert all(c["count"] == 0 for c in cells)


def test_seria_dni_uz_v_appke_nie_je():
    """Poistka proti tichemu navratu.

    `streaks()` vypadla zamerne - je to jedina vec v appke, ktora sa da
    pretrhnut, a appka ma upokojovat. Keby ju niekto (vratane buduceho
    ja) vratil, nech to padne tu a nie az v hlave hraca, ktory si vsimne,
    ze mu appka pocita, kolko vecerov po sebe hral.
    """
    assert not hasattr(hr_stats, "streaks")


def test_pocet_dni_s_relaciou_sa_da_spocitat_z_mriezky():
    """Nahrada za seriu: kolko dni v okne malo aspon jednu relaciu.

    Diera medzi dnami na to nema vplyv - o to prave ide.
    """
    now = time.time()
    sessions = [_session(_ts(d, now)) for d in (10, 9, 8, 6, 5)]
    cells = hr_stats.day_activity(sessions, days=14, now=now)
    assert sum(1 for c in cells if c["count"]) == 5


# --------------------------------------------------------------------------
# kreslenie - co sa bez Tk da overit len zo zdroja
# --------------------------------------------------------------------------

def test_sparkline_nezahadzuje_nulu():
    """Regresia: filter bol `if v`, takze z grafu vypadla aj nula. Pri tepe
    je to jedno (0 BPM neexistuje), ale Historia sem posiela aj 'cas nad
    hranicou' - a tam je nula platna hodnota, nie chybajuci bod."""
    src = _read("ui_kit.py")
    start = src.index("class Sparkline(")
    telo = src[start:src.index("class SegmentBar(", start)]
    assert "if v is not None" in telo
    assert "(values or []) if v]" not in telo


def test_graf_historie_kresli_popisky_osi():
    """`aggregate_by_period` popisok bucketu pocita - graf ho musi pouzit,
    inak ciara visi v prazdne bez toho, kedy a kolko."""
    assert "label" in hr_stats.aggregate_by_period(
        [_session(time.time())], hr_stats.PERIOD_DAY)[0]
    app = _read("app.py")
    start = app.index("def _refresh_history_trend(")
    telo = app[start:app.index("def _refresh_history_page(", start)]
    assert "labels=labels" in telo, "graf trendu ma dostat popisky osi x"
    assert "band=band" in telo, "graf trendu ma kreslit bezne rozpatie"


def test_pasma_beru_farbu_z_jedneho_miesta():
    """Kto farbi pasma sam, skor ci neskor sa rozide s legendou."""
    ui = _read("ui_kit.py")
    for trieda in ("class ZoneBar(", "class SessionTrace("):
        start = ui.index(trieda)
        koniec = ui.index("\nclass ", start + 1)
        assert "theme_mod.zone_color(" in ui[start:koniec], f"{trieda} farbi sam"


def test_note_trigger_zapise_sposob_dorucenia():
    """`_fire_somatic_cue` posiela `delivery` z udalosti automatu; bez toho
    by sa do merania nedostal (našla revízia)."""
    import hr_stats as hs
    st = hs.HeartStats(critical_bpm=110)
    st.session_start = 1000.0
    st.note_trigger(ts=1010.0, auto=True, arm="voice", source="auto",
                    delivery="pause")
    assert st.cues[-1]["delivery"] == "pause"
    st.note_trigger(ts=1020.0, auto=False, source="hud_panel")
    assert st.cues[-1]["delivery"] is None, "klik v paneli nemá spôsob doručenia"
