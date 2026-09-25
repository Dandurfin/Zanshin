# -*- coding: utf-8 -*-
"""Výpadok tepu: vidno ho ticho a zapíše sa (C3).

Tep, ktorý appka počula, prestane chodiť (12 s ticha alebo hodinky pustia
spojenie). Doteraz to vyzeralo presne ako „hodinky ešte nikdy neprišli":
Dnes zhodila živý blok aj stopu relácie a ukázala „Spáruj hodinky", a nikde
sa nezapísalo, ako často a ako dlho bola appka slepá. Po návrate tepu navyše
pár sekúnd tvrdila „Pokoj", hoci tep bol hore — záťaž sa rozbiehala od nuly.

Testy bežia bez Tk: skutočné metódy `DandurfApp` sa volajú na malej atrape.
"""
import ast
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
from _zdroj_appky import uzol_metody  # noqa: E402

T0 = 1_700_000_000.0
KROK = 2.8                      # skutočná kadencia hodiniek (C1)


def _nic(*_a, **_k):
    return None


def _nakrm(st, bpm, n, t):
    for _ in range(n):
        st.add(bpm, ts=t)
        t += KROK
    return t


def _po_kalibracii(critical=110):
    st = hr_stats.HeartStats(critical_bpm=critical)
    t = _nakrm(st, 70, 60, T0)
    assert not st.is_calibrating
    return st, t


# --------------------------------------------------------------------------
# HeartStats: settling, dropouts, blind_s
# --------------------------------------------------------------------------

def test_settling_len_prve_styri_vzorky_po_navrate():
    st = hr_stats.HeartStats(critical_bpm=110)
    t = T0
    # počas kalibrácie je to kalibrácia, nie „usádzanie"
    for _ in range(10):
        st.add(70, ts=t)
        t += KROK
        assert st.is_calibrating and not st.is_settling
    t = _nakrm(st, 70, 50, t)
    assert not st.is_calibrating and not st.is_settling   # ustálený stav

    st.note_dropout()
    st.clear_live()
    assert not st.is_settling, "bez vzorky nie je čo usádzať (je to výpadok)"
    t += 30.0
    stavy = []
    for _ in range(6):
        st.add(72, ts=t)
        t += KROK
        stavy.append(st.is_settling)
    assert stavy == [True, True, True, True, False, False]


def test_po_navrate_sa_nikdy_neukaze_falosny_pokoj():
    """Tep drží hore pred výpadkom aj po ňom. Kým `is_settling`, pásmo sa
    nečíta; potom už nesmie vyjsť „Pokoj" (záťaž smie chvíľu podstreliť do
    „Zvýšená" — chyba smerom k tichu)."""
    st, t = _po_kalibracii()
    t = _nakrm(st, 125, 60, t)
    assert st.zone in (hr_stats.ZONE_HIGH, hr_stats.ZONE_CRITICAL)
    st.note_dropout()
    st.clear_live()
    t += 40.0
    for _ in range(12):
        st.add(125, ts=t)
        t += KROK
        if not st.is_settling:
            assert st.zone != hr_stats.ZONE_CALM, round(st.stress, 1)


def test_suhrn_ma_pocet_vypadkov_a_slepy_cas():
    st, t = _po_kalibracii()
    posledna = t - KROK
    st.note_dropout()
    st.clear_live()
    navrat = posledna + 42.8
    st.add(71, ts=navrat)
    s = st.summary()
    assert s["dropouts"] == 1
    assert s["blind_s"] == pytest.approx(42.8, abs=0.1)
    # jednotlivé čísla, nie krivka
    assert isinstance(s["dropouts"], int) and isinstance(s["blind_s"], float)


def test_ten_isty_vypadok_sa_nerata_dvakrat():
    """`disconnected` po 12 s a `client_gone` po zatvorení TCP môžu prísť
    obe — stále je to jeden výpadok."""
    st, t = _po_kalibracii()
    st.note_dropout()
    st.note_dropout()
    st.clear_live()
    st.add(70, ts=t + 20.0)
    assert st.summary()["dropouts"] == 1


def test_suhrn_pocas_vypadku_zarata_otvoreny_interval():
    """Relácia sa zatvára naslepo (hráč vypne senzor počas výpadku): slepý čas
    sa počíta až po teraz, nie až po návrat, ktorý nepríde."""
    st = hr_stats.HeartStats(critical_bpm=110)
    teraz = time.time()
    t = teraz - 300.0
    while t < teraz - 60.0:
        st.add(70, ts=t)
        t += KROK
    posledna = st.last_beat_ts
    st.note_dropout()
    st.clear_live()
    s = st.summary()
    assert s["dropouts"] == 1
    assert s["blind_s"] == pytest.approx(time.time() - posledna, abs=1.0)
    assert s["blind_s"] >= 59.0


def test_bez_vypadku_su_nuly_a_nova_relacia_ich_zahodi():
    st, t = _po_kalibracii()
    s = st.summary()
    assert s["dropouts"] == 0 and s["blind_s"] == 0.0
    st.note_dropout()
    st.reset_session()
    s = st.summary()
    assert s["dropouts"] == 0 and s["blind_s"] == 0.0


# --------------------------------------------------------------------------
# App: _hr_lost žije len od výpadku po prvú vzorku
# --------------------------------------------------------------------------

class _SpyStats(hr_stats.HeartStats):
    """HeartStats, ktorý si zapisuje poradie `note_dropout` / `clear_live`."""

    def __init__(self, *a, **k):
        self.volania = []
        super().__init__(*a, **k)

    def note_dropout(self, od=None):
        self.volania.append("note_dropout")
        return super().note_dropout(od=od)

    def clear_live(self):
        self.volania.append("clear_live")
        return super().clear_live()


def _app():
    import app as app_mod
    return app_mod


def _atrapa(stats=None, **navyse):
    app_mod = _app()
    denn = []
    a = types.SimpleNamespace(
        _hr_generation=1, _hr_state="connected", _hr_last_bpm=None,
        _hr_lost=False, _hr_lost_od=None, _hr_over_since=None,
        _hr_client_linked=True, _hr_bind_retries=0, _hr_session_open=False,
        hr_stats=stats if stats is not None else _SpyStats(critical_bpm=110),
        hud=types.SimpleNamespace(set_connected=_nic),
        log=denn.append, denn=denn,
        _suspend_cue_trigger=_nic, _cancel_no_client_check=_nic,
        refresh_hr_status_label=_nic, _refresh_dnes_stats=_nic,
        _refresh_kamae_state_text=_nic, _refresh_hud_session_text=_nic,
    )
    a.__dict__.update(navyse)
    # pomocníci sú tiež metódy appky - volajú sa cez atrapu
    a._zaznamenaj_vypadok = lambda kind: app_mod.DandurfApp._zaznamenaj_vypadok(a, kind)
    a._tep_je_spat = lambda: app_mod.DandurfApp._tep_je_spat(a)
    return a


def _vzorka(a, bpm):
    _app().DandurfApp._apply_hr_bpm(a, bpm, 1)


def _stav(a, kind, payload=None):
    _app().DandurfApp._apply_hr_status(a, (kind, payload), 1)


@pytest.mark.parametrize("kind", ["disconnected", "client_gone"])
def test_vypadok_sa_zapise_pred_clear_live(kind):
    a = _atrapa()
    a.hr_stats.add(80, ts=time.time() - 30.0)
    a._hr_last_bpm = 80
    _stav(a, kind)
    assert a._hr_lost is True
    assert a.hr_stats.dropouts == 1
    assert a.hr_stats.volania == ["note_dropout", "clear_live"], (
        "po clear_live uz hr_stats nevie, kedy prisla posledna vzorka")
    assert a._hr_lost_od == pytest.approx(time.time() - 30.0, abs=1.0)


def test_vypadok_pred_prvou_vzorkou_nie_je_vypadok():
    a = _atrapa()
    _stav(a, "disconnected")
    assert a._hr_lost is False
    assert a.hr_stats.dropouts == 0


def test_druha_udalost_toho_isteho_vypadku_sa_nerata():
    a = _atrapa()
    a.hr_stats.add(80, ts=time.time() - 20.0)
    a._hr_last_bpm = 80
    _stav(a, "disconnected")
    _stav(a, "client_gone")
    assert a._hr_lost is True
    assert a.hr_stats.dropouts == 1


def test_prva_vzorka_vypadok_ukonci_jednym_riadkom():
    app_mod = _app()
    a = _atrapa()
    a.hr_stats.add(80, ts=time.time() - 30.0)
    a._hr_last_bpm = 80
    _stav(a, "disconnected")
    a.denn.clear()
    _vzorka(a, 82)
    assert a._hr_lost is False and a._hr_lost_od is None
    assert a.denn == [app_mod.tr("log.hr_back", s=30)], a.denn
    _vzorka(a, 83)
    assert len(a.denn) == 1, "riadok patri len prvej vzorke po vypadku"
    s = a.hr_stats.summary()
    assert s["dropouts"] == 1
    assert s["blind_s"] == pytest.approx(30.0, abs=1.0)


@pytest.mark.parametrize("kind", ["error", "busy"])
def test_chyba_a_obsadeny_port_vypadok_zhodia(kind):
    a = _atrapa(_hr_lost=True, _hr_lost_od=123.0,
                hr_monitoring_enabled=True, hr_enabled_var=None,
                save_settings=_nic, _close_hr_session=_nic,
                HR_BIND_RETRIES=3, HR_BIND_RETRY_MS=10,
                _retry_hr_bind=_nic,
                root=types.SimpleNamespace(after=lambda *_a: None))
    _stav(a, kind, "x")
    assert a._hr_lost is False and a._hr_lost_od is None


def test_vypnutie_senzora_vypadok_zhodi_a_suhrn_ho_zarata():
    """Hráč vypne senzor počas výpadku: príznak ide preč, ale relácia sa
    zatvára s výpadkom, ktorý ešte trval."""
    app_mod = _app()
    st = _SpyStats(critical_bpm=110)
    st.add(80, ts=time.time() - 45.0)
    st.note_dropout()
    st.clear_live()
    suhrny = []
    a = _atrapa(stats=st, _hr_lost=True, _hr_lost_od=st.last_beat_ts,
                heart_rate_monitor=types.SimpleNamespace(stop=_nic),
                _close_hr_session=lambda: suhrny.append(st.summary()))
    app_mod.DandurfApp.stop_heart_rate_monitor(a)
    assert a._hr_lost is False and a._hr_lost_od is None
    assert suhrny and suhrny[0]["blind_s"] >= 44.0


def _telo(metoda):
    # metoda DandurfApp - aj ked byva v mixine v app_*.py
    return uzol_metody(metoda)


def test_nova_relacia_zhodi_vypadok_vzdy_nie_len_pri_prepojeni():
    """`start_listening` počas výpadku otvára reláciu s `prepoj=False`.
    Príznak nesmie prejsť do novej relácie (a `reset_session` prepíše čas,
    od ktorého by sa rátal riadok „tep je späť")."""
    fn = _telo("_open_hr_session")
    priamo = [
        ciel.attr
        for prikaz in fn.body if isinstance(prikaz, ast.Assign)
        for ciel in prikaz.targets
        if isinstance(ciel, ast.Attribute) and isinstance(ciel.value, ast.Name)
        and ciel.value.id == "self"
    ]
    assert "_hr_lost" in priamo and "_hr_lost_od" in priamo, (
        "_hr_lost sa musi zhodit na urovni funkcie, nie vnutri `if prepoj:`")


# --------------------------------------------------------------------------
# Pás / Dnes / kontrolka / HUD
# --------------------------------------------------------------------------

def test_pas_pri_vypadku_ma_vlastnu_vetu():
    app_mod = _app()
    a = types.SimpleNamespace(listening=True, hr_monitoring_enabled=True,
                              _hr_state="linked", _hr_last_bpm=None,
                              _cue_armed=False, _hr_lost=True,
                              _kamae_zastavene=lambda: ("stop", ""))
    titul, veta = app_mod.DandurfApp._kamae_state_text(a)
    assert titul == app_mod.tr("kamae.no_hr"), "nadpis 'Cakam na tep' plati aj tu"
    assert veta == app_mod.tr("kamae.lost_sub")
    a._hr_lost = False
    assert app_mod.DandurfApp._kamae_state_text(a)[1] == app_mod.tr("kamae.no_hr_sub")


class _Widget:
    def __init__(self, mapped=False):
        self.kw = {}
        self.mapped = mapped
        self.hodnota = None
        self.pasmo = None
        self.seria = None
        self.vpravo = None

    def configure(self, **kw):
        self.kw.update(kw)

    def set_value(self, v, zone=None):
        self.hodnota = v
        self.pasmo = zone

    def set_series(self, values, **_k):
        self.seria = list(values)

    def set_right(self, text):
        self.vpravo = text

    def winfo_ismapped(self):
        return self.mapped

    def pack(self, **_k):
        self.mapped = True

    def pack_forget(self):
        self.mapped = False


def _dnes(stats, hr_state, lost):
    import theme as theme_mod
    app_mod = _app()
    stopa, hero = [], []
    a = types.SimpleNamespace(
        hr_stats=stats, _hr_state=hr_state, _hr_lost=lost,
        pal=theme_mod.tokens(theme_mod.MODERN), hr_critical_bpm=110,
        dnes_bpm=_Widget(), dnes_spark=_Widget(), dnes_load=_Widget(),
        dnes_zone=_Widget(), hr_panel=_Widget(),
        dnes_empty=_Widget(mapped=False), dnes_live=_Widget(mapped=True),
        _refresh_session_trace=stopa.append, _refresh_zone_panel=_nic,
        _refresh_dashboard_stats=_nic, _refresh_last_cue=_nic,
        _stop_dnes_hero=lambda: hero.append("stop"),
        _start_dnes_hero=lambda: hero.append("start"))
    app_mod.DandurfApp._refresh_dnes_stats(a)
    assert getattr(a, "_dnes_refresh_fails", 0) == 0
    return a, stopa, hero


def test_dnes_pocas_vypadku_necha_zivy_blok_bez_falosneho_pokoja():
    st, _t = _po_kalibracii()
    st.note_dropout()
    st.clear_live()
    assert st.zone == hr_stats.ZONE_CALM     # samo o sebe by klamalo...
    a, stopa, hero = _dnes(st, "linked", lost=True)
    assert a.dnes_bpm.kw["text"] == "--"
    assert a.dnes_zone.kw["text"] == "—", "...preto ho Dnes nesmie citat"
    assert a.dnes_load.hodnota == 0
    assert a.hr_panel.vpravo == _app().tr("dnes.hr_lost")
    assert a.dnes_live.mapped and not a.dnes_empty.mapped, \
        "uprostred vecera ziadne 'Sparuj hodinky'"
    assert stopa == [True], "stopa relacie ostava"
    assert "start" not in hero


def test_dnes_pred_prvou_vzorkou_ukaze_parovanie():
    st = hr_stats.HeartStats(critical_bpm=110)
    a, stopa, hero = _dnes(st, "connecting", lost=False)
    assert a.hr_panel.vpravo == _app().tr("dnes.hr_waiting")
    assert a.dnes_empty.mapped and not a.dnes_live.mapped
    assert stopa == [False] and hero == ["start"]


def test_dnes_po_navrate_pise_tri_bodky_nie_pokoj():
    st, t = _po_kalibracii()
    st.note_dropout()
    st.clear_live()
    st.add(125, ts=t + 30.0)
    # Od C2 je `zone` tep voci pokoju, takze tu uz nepise falosny pokoj -
    # zataz sa ale rozbieha od nuly, tak usadzanie ma prednost dalej.
    assert st.is_settling and st.stress < 25
    a, stopa, _hero = _dnes(st, "connected", lost=False)
    assert a.dnes_zone.kw["text"] == "…"
    assert a.dnes_load.hodnota == 0
    assert a.dnes_load.pasmo is None, "usadzanie nefarbi pruh pasmom"
    assert a.hr_panel.vpravo == _app().tr("dnes.hr_connected")
    assert stopa == [True]


def test_kontrolka_po_navrate_neutralna():
    app_mod = _app()
    st, t = _po_kalibracii()
    st.note_dropout()
    st.clear_live()
    st.add(125, ts=t + 30.0)
    a = types.SimpleNamespace(hr_monitoring_enabled=True, hr_stats=st,
                              WATCH_ZONE_HOLD_S=1.5)
    _spojene, _caka, pasmo, _faza = app_mod.DandurfApp._watch_pulse_state(a)
    assert pasmo == "neutral"


def test_hud_po_navrate_ide_cestou_kalibracie(monkeypatch):
    import hud as hud_mod
    st, t = _po_kalibracii()
    st.note_dropout()
    st.clear_live()
    st.add(125, ts=t + 30.0)
    zachytene = {}

    def render(style, **kw):
        zachytene.update(kw)
        return object()

    monkeypatch.setattr(hud_mod.hud_paint, "render_hud", render)
    h = hud_mod.StatsHud(None, st, style=None)
    h.labels = {"calibrating": "kalibrujem…", "calm": "Pokoj"}
    h.set_connected(True)
    h.surface = types.SimpleNamespace(draw=_nic, show=_nic)
    h._last_reposition = time.time()
    h._draw()
    assert zachytene["calibrating"] is True
    assert zachytene["labels"]["calibrating"] == "…"
    assert h.labels["calibrating"] == "kalibrujem…", "povodne popisky ostavaju"


@pytest.fixture
def style():
    if not hud_paint.PIL_AVAILABLE:
        pytest.skip("pillow nie je nainstalovany")
    import theme as theme_mod
    return hud_paint.Style(theme_mod.tokens(theme_mod.MODERN))


def _texty(monkeypatch):
    napisane = []
    povodny = hud_paint.Painter.text

    def zapis(self, x, y, text, *args, **kwargs):
        napisane.append(text)
        return povodny(self, x, y, text, *args, **kwargs)

    monkeypatch.setattr(hud_paint.Painter, "text", zapis)
    return napisane


def test_hud_naslepo_netvrdi_pokoj(style, monkeypatch):
    """Po `clear_live` je záťaž 0.0, čiže `zone` = pokoj. HUD bez spojenia to
    nesmie prečítať."""
    napisane = _texty(monkeypatch)
    hud_paint.render_hud(style, bpm=None, stress=0.0, history=[],
                         threshold=110, connected=False, ss=2,
                         labels={"calm": "X_CALM", "waiting": "X_WAIT"})
    assert "X_WAIT" in napisane and "--" in napisane
    assert "X_CALM" not in napisane


def test_hud_po_navrate_tri_bodky_a_prazdny_pruh(style, monkeypatch):
    napisane = _texty(monkeypatch)
    labels = {"calm": "X_CALM", "calibrating": "…"}
    hore = hud_paint.render_hud(style, bpm=125, stress=10.0,
                                history=[120, 125], threshold=110,
                                labels=labels, calibrating=True, ss=2)
    assert "..." in napisane and "X_CALM" not in napisane
    dole = hud_paint.render_hud(style, bpm=125, stress=90.0,
                                history=[120, 125], threshold=110,
                                labels=labels, calibrating=True, ss=2)
    assert hore.tobytes() == dole.tobytes(), "zataz sa nesmie citat ani omylom"


# --------------------------------------------------------------------------
# Texty
# --------------------------------------------------------------------------

def test_nove_kluce_maju_vsetkych_jedenast_jazykov():
    for kluc in ("dnes.hr_lost", "kamae.lost_sub", "log.hr_back"):
        zaznam = i18n.STRINGS[kluc]
        assert set(zaznam) == set(i18n.LANGUAGES), kluc
        assert all(str(v).strip() for v in zaznam.values()), kluc
    for jazyk in i18n.LANGUAGES:
        assert "{s}" in i18n.STRINGS["log.hr_back"][jazyk], jazyk


def test_rada_pri_vypadku_je_vsade_ta_ista_a_pravdiva():
    """Tep ide hodinky → telefón (Bluetooth) → Wi‑Fi → počítač. Koniec
    relácie radil „hodinky bližšie k počítaču", postreh hovoril o telefóne."""
    koniec = i18n.STRINGS["session.end.none_dropouts"]
    postreh = i18n.STRINGS["insight.cue_dropouts"]
    for jazyk, retaz in (("sk", "Tep ide z hodiniek do telefónu cez Bluetooth "
                                "a z telefónu cez Wi‑Fi do počítača"),
                         ("en", "It goes from the watch to the phone over "
                                "Bluetooth, and from the phone to the PC over Wi‑Fi")):
        assert retaz in koniec[jazyk], jazyk
        assert retaz in postreh[jazyk], jazyk
    assert "bližšie k počítaču" not in koniec["sk"]
    assert "closer to the PC" not in koniec["en"]
    for kluc in ("session.end.none_dropouts", "insight.cue_dropouts"):
        for jazyk in i18n.LANGUAGES:
            assert "{n}" in i18n.STRINGS[kluc][jazyk], (kluc, jazyk)


def test_cakam_na_tep_hovori_tu_istu_retaz():
    """„Z hodiniek zatiaľ nič nechodí" radilo „nech sú hodinky na tej istej
    Wi‑Fi" - hodinky ale idú cez telefón (Bluetooth) a až telefón je na
    Wi‑Fi. Starý preklad nesmie prežiť v žiadnom jazyku: starý o Bluetooth
    nehovoril, nový (jazyková fáza 0.2) áno - v každom jazyku."""
    zaznam = i18n.STRINGS["kamae.no_hr_sub"]
    assert "pri telefóne (Bluetooth)" in zaznam["sk"]
    assert "telefón na tej istej Wi‑Fi ako počítač" in zaznam["sk"]
    assert "near the phone (Bluetooth)" in zaznam["en"]
    assert "the phone is on the same Wi‑Fi as the PC" in zaznam["en"]
    for jazyk in i18n.LANGUAGES:
        if jazyk not in ("sk", "en"):
            assert zaznam[jazyk] != zaznam["en"], jazyk
            assert _retaz_cez_telefon(zaznam[jazyk]), jazyk


def _retaz_cez_telefon(text):
    """Veta hovorí o Bluetooth (hodinky -> telefón) aj o Wi‑Fi (telefón ->
    počítač). Nemčina hovorí WLAN, čínština 蓝牙."""
    return (("Bluetooth" in text or "蓝牙" in text)
            and ("Wi‑Fi" in text or "WLAN" in text))


def test_ticho_bez_prekrocenia_nehodnoti_telo():
    zaznam = i18n.STRINGS["session.end.none_never"]
    assert "telo" not in zaznam["sk"] and "body" not in zaznam["en"]
    assert "hranic" in zaznam["sk"] and "threshold" in zaznam["en"]


def test_zmenene_vety_nenechali_stary_preklad():
    """Stará veta („hodinky bližšie k PC", „telo bolo v pohode") nesmie prežiť
    v žiadnom jazyku. Jazyková fáza 0.2 ich preložila z nového SK: každý
    jazyk má vlastný text a veta o výpadku hovorí celú reťaz cez telefón."""
    for kluc in ("session.end.none_never", "session.end.none_dropouts",
                 "insight.cue_dropouts"):
        zaznam = i18n.STRINGS[kluc]
        for jazyk in i18n.LANGUAGES:
            if jazyk in ("sk", "en"):
                continue
            assert zaznam[jazyk] != zaznam["en"], (kluc, jazyk)
            if kluc != "session.end.none_never":
                assert _retaz_cez_telefon(zaznam[jazyk]), (kluc, jazyk)


def test_postreh_o_vypadkoch_netvrdi_malo_hlasok():
    """`hr_insights` pusti postreh o výpadkoch podľa priemeru zrušených
    počítaní, bez ohľadu na to, koľko hlášok v tie večery padlo. Veta teda
    nesmie tvrdiť „preto je hlášok málo" ako fakt - len že ich môže byť
    menej."""
    postreh = i18n.STRINGS["insight.cue_dropouts"]
    assert "hlášok málo" not in postreh["sk"]
    assert "few cues" not in postreh["en"]
    assert "môže byť hlášok menej" in postreh["sk"]
    assert "may be fewer cues" in postreh["en"]
    # „a to sa začalo" sa dalo čítať ako „a to (konkrétne)…" - počítanie
    # je v oboch vetách pomenované
    for kluc in ("insight.cue_dropouts", "session.end.none_dropouts"):
        assert "a počítanie sa zakaždým začalo odznova" in i18n.STRINGS[kluc]["sk"], kluc
