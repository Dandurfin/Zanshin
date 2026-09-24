# -*- coding: utf-8 -*-
"""Jeden význam slov pásma všade (C2).

Do 0.2 znamenalo „Vysoká" dve veci na tej istej stránke Dnes: živé slovo pri
záťaži bralo pevné pásma záťaže (25/50/75), panel „Kde si dnes bol", stopa
relácie a História brali tep voči pokoju (`hr_stats.zone_of_bpm`). Pri
pokoji 76 a hranici 109 dáva stabilných 95 BPM záťaž okolo 57 — HUD písal
„Vysoká", panel pod tým ten istý moment rátal ako „zvýšenú".

Teraz sa pásmo počíta raz (`HeartStats.zone`, tep voči pokoju) a HUD, Dnes aj
kontrolka tepu ho len kreslia. Číslo záťaže, dĺžka pruhu, spúšťač ani
`time_high_s` sa nemenia.
"""
import os
import sys
import time
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats   # noqa: E402
import hud_paint  # noqa: E402
import i18n       # noqa: E402

KROK = 1.5


def _nakrm(st, hodnoty, t=1000.0):
    for bpm in hodnoty:
        st.add(bpm, ts=t)
        t += KROK
    return t


def _vecer_z_testovania(bpm=95, n=160):
    """Pokoj z predošlých večerov 76, nameraná hranica 109 (príklad z testovania)."""
    st = hr_stats.HeartStats(critical_bpm=109)
    st.long_baseline = 76.0
    t = _nakrm(st, [bpm] * n)
    assert not st.is_calibrating and not st.is_settling
    return st, t


def _nic(*_a, **_k):
    return None


# --------------------------------------------------------------------------
# HeartStats.zone
# --------------------------------------------------------------------------

def test_95_bpm_pri_pokoji_76_a_hranici_109_je_zvysena():
    st, _t = _vecer_z_testovania()
    assert st._zakladna_bez_odhadu() == 76.0
    assert st.zone == hr_stats.ZONE_RAISED
    # staré pásma záťaže by tu hovorili „Vysoká" - práve to bol rozpor
    assert hr_stats.zone_for(st.stress) == hr_stats.ZONE_HIGH


def test_zataz_pri_95_bpm_sa_nezmenila():
    """Regresia: vzorec záťaže zostáva (headroom, váhy, strop základne)."""
    st, _t = _vecer_z_testovania()
    assert 55.0 <= st.stress <= 63.0, round(st.stress, 1)
    # aj s bežným šumom hodiniek (±3 BPM) okolo toho istého čísla
    st = hr_stats.HeartStats(critical_bpm=109)
    st.long_baseline = 76.0
    sum_ = [0, 2, -1, 3, -2, 1, -3, 2, 0, -1]
    t, zataze = 1000.0, []
    for i in range(160):
        st.add(95 + sum_[i % len(sum_)], ts=t)
        t += KROK
        if i >= 100:
            zataze.append(st.stress)
            assert st.zone == hr_stats.ZONE_RAISED
    zataze.sort()
    assert 55.0 <= zataze[len(zataze) // 2] <= 63.0


@pytest.mark.parametrize("bpm, pasmo", [
    (85, hr_stats.ZONE_CALM),        # pokoj + 9
    (86, hr_stats.ZONE_RAISED),      # pokoj + 10
    (100, hr_stats.ZONE_RAISED),
    (101, hr_stats.ZONE_HIGH),       # pokoj + 25
    (108, hr_stats.ZONE_HIGH),
    (109, hr_stats.ZONE_CRITICAL),   # nameraná hranica
])
def test_hranice_pasiem_su_pokoj_plus_10_plus_25_a_namerana_hranica(bpm, pasmo):
    st, _t = _vecer_z_testovania(bpm=bpm, n=60)
    assert st.zone == pasmo


def test_jedna_spicka_pasmo_neprehodi():
    """Medián posledných vzoriek: jedna vzorka mimo slovo ani farbu
    nepreklopí, tep, ktorý tam drží, áno."""
    st, t = _vecer_z_testovania(n=60)
    vidim = []
    for _ in range(3):
        st.add(130, ts=t)
        t += KROK
        vidim.append(st.zone)
    assert vidim == [hr_stats.ZONE_RAISED, hr_stats.ZONE_RAISED,
                     hr_stats.ZONE_CRITICAL]


def test_pasmo_rata_voci_tej_istej_zakladni_ako_zataz():
    """Po dlhom výpadku `baseline` nie je, záťaž beží voči kotve večera -
    pásmo tiež, nie voči niečomu inému."""
    st = hr_stats.HeartStats(critical_bpm=110)
    t = _nakrm(st, [62] * 200)
    st.clear_live()
    t += hr_stats.BASELINE_SECONDS + 100
    _nakrm(st, [80, 81, 79, 80, 80, 80], t)
    assert st.baseline is None
    zaklad = st._zakladna_bez_odhadu()
    assert zaklad == 62
    assert st.zone == hr_stats.zone_of_bpm(80, zaklad, 110) == hr_stats.ZONE_RAISED


def test_bez_tepu_pasmo_netvrdi_nic_ine_nez_predtym():
    st, _t = _vecer_z_testovania()
    st.clear_live()
    assert st.zone == hr_stats.ZONE_CALM   # volajúci to bez spojenia nečítajú
    assert hr_stats.HeartStats(110).zone == hr_stats.ZONE_CALM


def test_time_high_ostava_na_pevnych_pasmach_zataze():
    """`time_high_s` je uložená metrika - nesmie sa potichu prepnúť na nové
    slovo pásma, inak by staré a nové relácie neboli porovnateľné."""
    st, t = _vecer_z_testovania()
    assert st.zone == hr_stats.ZONE_RAISED
    pred = st.time_high
    _nakrm(st, [95] * 20, t)
    assert st.zone == hr_stats.ZONE_RAISED
    assert st.stress >= 50
    assert st.time_high == pytest.approx(pred + 20 * KROK, abs=0.01)


# --------------------------------------------------------------------------
# HUD, Dnes a kontrolka čítajú to isté pásmo
# --------------------------------------------------------------------------

class _Widget:
    def __init__(self, mapped=True):
        self.kw, self.mapped = {}, mapped
        self.hodnota = self.pasmo = None

    def configure(self, **kw):
        self.kw.update(kw)

    def set_value(self, v, zone=None):
        self.hodnota, self.pasmo = v, zone

    def set_series(self, *_a, **_k):
        pass

    def set_right(self, *_a):
        pass

    def winfo_ismapped(self):
        return self.mapped

    def pack(self, **_k):
        self.mapped = True

    def pack_forget(self):
        self.mapped = False


def _dnes(st):
    import app as app_mod
    import theme as theme_mod
    a = types.SimpleNamespace(
        hr_stats=st, _hr_state="connected", _hr_lost=False,
        pal=theme_mod.tokens(theme_mod.MODERN), hr_critical_bpm=st.critical_bpm,
        dnes_bpm=_Widget(), dnes_spark=_Widget(), dnes_load=_Widget(),
        dnes_zone=_Widget(), hr_panel=_Widget(),
        dnes_empty=_Widget(mapped=False), dnes_live=_Widget(),
        _refresh_session_trace=_nic, _refresh_zone_panel=_nic,
        _refresh_dashboard_stats=_nic, _refresh_last_cue=_nic,
        _stop_dnes_hero=_nic, _start_dnes_hero=_nic)
    app_mod.DandurfApp._refresh_dnes_stats(a)
    assert getattr(a, "_dnes_refresh_fails", 0) == 0
    return a


def _kontrolka(st):
    import app as app_mod
    a = types.SimpleNamespace(hr_monitoring_enabled=True, hr_stats=st,
                              WATCH_ZONE_HOLD_S=1.5)
    return app_mod.DandurfApp._watch_pulse_state(a)[2]


def _hud_kwargs(st, monkeypatch):
    import hud as hud_mod
    zachytene = {}

    def render(style, **kw):
        zachytene.update(kw)
        return object()

    monkeypatch.setattr(hud_mod.hud_paint, "render_hud", render)
    h = hud_mod.StatsHud(None, st, style=None)
    h.set_connected(True)
    h.surface = types.SimpleNamespace(draw=_nic, show=_nic)
    h._last_reposition = time.time()
    h._draw()
    return zachytene


def test_hud_dnes_a_kontrolka_maju_to_iste_pasmo(monkeypatch):
    import app as app_mod
    st, _t = _vecer_z_testovania()
    pasmo = st.zone
    assert pasmo == hr_stats.ZONE_RAISED

    a = _dnes(st)
    assert a.dnes_zone.kw["text"] == app_mod.tr(f"hud.zone.{pasmo}")
    assert a.dnes_load.pasmo == pasmo, "pruh na Dnes má farbu toho istého pásma"
    assert a.dnes_load.hodnota == pytest.approx(st.stress), "dĺžka je záťaž"

    assert _kontrolka(st) == pasmo

    kw = _hud_kwargs(st, monkeypatch)
    assert kw["zone"] == pasmo
    assert kw["stress"] == pytest.approx(st.stress)
    assert kw["calibrating"] is False


def test_kalibracia_a_usadzanie_maju_dalej_prednost():
    st = hr_stats.HeartStats(critical_bpm=109)
    st.long_baseline = 76.0
    _nakrm(st, [95] * 10)
    assert st.is_calibrating and st.zone == hr_stats.ZONE_RAISED
    assert _kontrolka(st) == "neutral"
    a = _dnes(st)
    assert a.dnes_zone.kw["text"] == i18n.tr("hud.calibrating")
    assert a.dnes_load.pasmo is None and a.dnes_load.hodnota == 0


# --------------------------------------------------------------------------
# Kreslenie: žiadne vlastné hranice pásiem v pruhoch
# --------------------------------------------------------------------------

@pytest.fixture
def style():
    if not hud_paint.PIL_AVAILABLE:
        pytest.skip("pillow nie je nainstalovany")
    import theme as theme_mod
    return hud_paint.Style(theme_mod.tokens(theme_mod.MODERN))


def _zaznam(monkeypatch):
    texty, dieliky = [], []
    text0, rect0 = hud_paint.Painter.text, hud_paint.Painter.rect

    def text(self, x, y, t, *a, **k):
        texty.append(t)
        return text0(self, x, y, t, *a, **k)

    def rect(self, *a, **k):
        if k.get("alpha") == 0.92:          # plný dielik pruhu záťaže
            dieliky.append(k.get("color"))
        return rect0(self, *a, **k)

    monkeypatch.setattr(hud_paint.Painter, "text", text)
    monkeypatch.setattr(hud_paint.Painter, "rect", rect)
    return texty, dieliky


LABELS = {"load": "ZÁŤAŽ", "calm": "Pokoj", "raised": "Zvýšená",
          "high": "Vysoká", "critical": "Špička", "calibrating": "kalibrujem…"}


def _hud(style, **kw):
    zaklad = dict(bpm=95, stress=57.0, history=[90 + i % 8 for i in range(90)],
                  threshold=109, baseline=76, labels=LABELS, ss=2)
    zaklad.update(kw)
    return hud_paint.render_hud(style, **zaklad)


def test_hud_pise_pasmo_zo_statistiky_nie_zo_zataze(style, monkeypatch):
    texty, dieliky = _zaznam(monkeypatch)
    _hud(style, zone="raised")
    assert "ZVÝŠENÁ" in texty and "VYSOKÁ" not in texty
    # 57 % = 11 dielikov z 20, všetky vo farbe aktuálneho pásma
    assert len(dieliky) == 11
    assert set(dieliky) == {hud_paint.zone_color(style, "raised")}


def test_staticky_nahlad_bez_pasma_ide_na_zalohu(style, monkeypatch):
    texty, dieliky = _zaznam(monkeypatch)
    _hud(style)
    assert "VYSOKÁ" in texty
    assert set(dieliky) == {hud_paint.zone_color(style, "high")}


def test_hud_pocas_kalibracie_pasmo_necita(style):
    assert (_hud(style, zone="critical", calibrating=True).tobytes()
            == _hud(style, zone="calm", calibrating=True, stress=5.0).tobytes())


def test_segmentbar_farbi_plne_dieliky_farbou_pasma():
    import theme as theme_mod
    import ui_kit
    pal = theme_mod.tokens(theme_mod.MODERN)
    nakreslene = []
    platno = types.SimpleNamespace(
        delete=_nic,
        create_rectangle=lambda *a, **k: nakreslene.append(k["fill"]))
    bar = types.SimpleNamespace(pal=pal, canvas=platno, SEGMENTS=20,
                                _value=57.0, _zone="raised",
                                _canvas_size=lambda: (200, 8, 1.0))
    ui_kit.SegmentBar._redraw(bar)
    plne = nakreslene[:11]
    assert set(plne) == {theme_mod.zone_color(pal, "raised")}
    assert set(nakreslene[11:]) == {pal["switch_off"]}


def _zdroj(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def test_ziadny_kresliaci_kod_nema_vlastne_hranice_pasiem():
    hp = _zdroj("hud_paint.py")
    assert "_ZONE_ORDER" not in hp and "def zone_for(" not in hp
    ui = _zdroj("ui_kit.py")
    start = ui.index("class SegmentBar(")
    telo = ui[start:ui.index("\nclass ", start + 1)]
    assert "0.35" not in telo and "share" not in telo
    app = _zdroj("app.py")
    start = app.index("def _watch_pulse_state(")
    telo = app[start:app.index("\n    def ", start + 1)]
    assert "stats.zone" in telo and "zone_for" not in telo


# --------------------------------------------------------------------------
# Texty
# --------------------------------------------------------------------------

# Kúsky starých prekladov (_tr7 spred C2). Stará veta sľubovala „ako veľmi
# ťa hra zaťažuje" - nesmie prežiť v žiadnom jazyku. Kým jazyková fáza
# nepreloží nový text, idú ostatné jazyky anglicky; test to ale nepribíja
# na angličtinu, aby nový preklad nemusel meniť aj tento test.
STARE_VETY_ZATAZE = (
    "ゲームに押されている", "游戏此刻给你多大压力", "игра давит на тебя",
    "te está exigiendo el juego", "dich das Spiel gerade fordert",
    "le jeu te pousse", "o jogo te está a exigir",
    "拍と拍の間隔が必要", "HRV 需要心跳间隔", "нужны интервалы между ударами",
    "intervalos latido a latido", "Schlag-zu-Schlag-Intervalle",
    "intervalles entre battements", "intervalos batimento a batimento",
)


def test_text_zataze_je_poctivy():
    kratky = i18n.STRINGS["metric.load.short"]
    viac = i18n.STRINGS["metric.load.more"]
    for zaznam in (kratky, viac):
        assert set(zaznam) == set(i18n.LANGUAGES)
        for jazyk in i18n.LANGUAGES:
            assert zaznam[jazyk].strip(), jazyk
            for stara in STARE_VETY_ZATAZE:
                assert stara not in zaznam[jazyk], (jazyk, stara)
    assert "hra práve zaťažuje" not in kratky["sk"]
    assert "game is pushing you" not in kratky["en"]

    sk, en = viac["sk"], viac["en"]
    # voči čomu: pokoj z pokojnejších večerov, nie len z dnešného
    assert "pokojnejších večerov" in sk and "calmer evenings" in en
    # hranice pásiem slovami
    for kus in ("od 10 BPM nad pokojom", "od 25 BPM", "hranice vysokého tepu"):
        assert kus in sk, kus
    for kus in ("10 BPM above your calm", "at 25 BPM", "high heart-rate limit"):
        assert kus in en, kus
    # „Vysoká" NIE JE „appka čaká na pauzu": najprv počíta, či to vydrží
    assert "najprv počíta, či tam chvíľu vydrží, a až potom čaká na pauzu" in sk
    assert "first counts whether it holds there for a while, and only then waits for a pause" in en
    assert "začne čakať na pauzu" not in sk
    assert "starts waiting for a pause" not in en
    # Od stress-gate (0.2) najvyššie pásmo hlášku ZASTAVÍ - „o hláške slovo
    # nerozhoduje“ by klamalo. Hlášku slovo nespúšťa, ale „Špička“ ju umlčí
    # (do 0.2 sa pásmo volalo „Kritická“ - znelo to ako diagnóza).
    assert "nerozhoduje" not in sk and "does not decide" not in en
    assert "Kým slovo ukazuje „Špička“, appka mlčí." in sk
    assert "While the word says “Peak”, the app stays quiet." in en
    assert "v ktorej už záťaž nestúpa" in sk
    assert "in which the load is no longer climbing" in en
