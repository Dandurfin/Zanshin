# -*- coding: utf-8 -*-
"""Cislo tepu na obrazovke je vyhladene, meranie nie (0.2.2).

Appka na hodinkach vie do jedneho zdroja pisat dva rady tepu (5-10 BPM od
seba, ~2 spravy za sekundu). Obrazovka ukazovala poslednu surovu hodnotu,
takze cislo v tej istej sekunde skakalo hore-dole.

Strazi sa:
  * HUD, Dnes a stitok pri prepinaci ukazuju `HeartStats.display_bpm` -
    median vzoriek za poslednych `ZOBRAZ_OKNO_S` sekund, vzdy aspon tej
    poslednej,
  * do merania ide KAZDA vzorka ako doteraz (`add`, suhrn relacie, pasmo,
    `_hr_last_bpm` pre rozhodovanie),
  * okno sa vynuluje pri vypadku a zastaveni (`clear_live`) aj pri novej
    relacii (`reset_session`) - tam, kde sa nuluje `_hr_last_bpm`.

Vsetky rady su umele - ziadne skutocne namerane data.
"""
import os
import sys
import time
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import theme  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

T0 = 1_700_000_000.0
# Umele hodnoty dvoch radov (7 BPM od seba) - vymyslene, nie namerane.
HORE, DOLE = 97, 90


def _nic(*_a, **_k):
    return None


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _dva_rady(st, t=T0, n=10, hore=HORE, dole=DOLE):
    """Umely rad: kazdu sekundu hodnota z vyssieho radu a o 0,5 s z nizsieho."""
    for _ in range(n):
        st.add(hore, ts=t)
        st.add(dole, ts=t + 0.5)
        t += 1.0
    return t


# --------------------------------------------------------------------------
# HeartStats.display_bpm
# --------------------------------------------------------------------------

def test_okno_je_tri_sekundy_a_ohranicene():
    assert hr_stats.ZOBRAZ_OKNO_S == 3.0
    st = hr_stats.HeartStats()
    for i in range(500):
        st.add(80, ts=T0 + i * 0.01)
    assert len(st._zobraz) <= hr_stats.ZOBRAZ_MAX_VZORIEK


def test_bez_tepu_nic_a_prva_vzorka_hned():
    st = hr_stats.HeartStats()
    assert st.display_bpm is None
    st.add(73, ts=T0)
    assert st.display_bpm == 73, "aspon posledna vzorka, ziadne cakanie"


def test_dva_rady_nerozskacu_cislo():
    st = hr_stats.HeartStats()
    t = _dva_rady(st)
    zobrazene = set()
    for _ in range(6):
        st.add(HORE, ts=t)
        zobrazene.add(st.display_bpm)
        st.add(DOLE, ts=t + 0.5)
        zobrazene.add(st.display_bpm)
        t += 1.0
    # surova hodnota skace HORE <-> DOLE, cislo drzi medzi radmi
    assert st.last_bpm == DOLE
    assert all(DOLE < z < HORE for z in zobrazene), zobrazene
    assert max(zobrazene) - min(zobrazene) <= 2, zobrazene


def test_median_zahodi_jednu_ujdenu_hodnotu():
    st = hr_stats.HeartStats()
    for i, bpm in enumerate((80, 81, 80, 81, 80)):
        st.add(bpm, ts=T0 + i)
    st.add(140, ts=T0 + 5)             # jedna spicka
    assert st.last_bpm == 140
    assert st.display_bpm in (80, 81)


def test_starsie_nez_okno_sa_nepocita():
    st = hr_stats.HeartStats()
    for i in range(5):
        st.add(70, ts=T0 + i)
    # po medzere dlhsej nez okno plati len nova hodnota
    st.add(95, ts=T0 + 4 + hr_stats.ZOBRAZ_OKNO_S + 0.1)
    assert st.display_bpm == 95
    # okno sa meria od poslednej vzorky, nie od hodin - cislo neodplava
    assert st.display_bpm == 95


def test_hodiny_posunute_dozadu_neberu_vzorky_z_buducnosti():
    st = hr_stats.HeartStats()
    st.add(80, ts=T0 + 10)
    st.add(80, ts=T0 + 11)
    st.add(120, ts=T0 + 5)             # hodiny PC skocili dozadu
    assert st.display_bpm == 120


def test_cislo_ide_s_tepom_do_par_sekund():
    """Vyhladenie nesmie skryt skutocny nastup tepu."""
    st = hr_stats.HeartStats()
    t = T0
    for _ in range(10):
        st.add(70, ts=t)
        t += 1.0
    for _ in range(3):
        st.add(100, ts=t)
        t += 1.0
    assert st.display_bpm == 100


def test_vypadok_a_nova_relacia_okno_vynuluju():
    st = hr_stats.HeartStats()
    t = _dva_rady(st)
    st.clear_live()                    # vypadok / vypnutie senzora
    assert st.display_bpm is None
    st.add(90, ts=t)                   # v tom istom okne 3 s - stare nie
    assert st.display_bpm == 90
    _dva_rady(st, t + 1.0)
    st.reset_session()                 # nova relacia (`_open_hr_session`)
    assert st.display_bpm is None
    st.add(66, ts=t + 12.0)
    assert st.display_bpm == 66


def test_meranie_dostava_kazdu_vzorku():
    """Surove vzorky ostavaju vsade, kde sa meria - vyhladene je len cislo."""
    st = hr_stats.HeartStats(critical_bpm=110)
    hodnoty = []
    t = T0
    for i in range(40):
        for bpm in (HORE + i % 3, DOLE - 2 - i % 2):
            st.add(bpm, ts=t)
            hodnoty.append((t, float(bpm)))
            t += 0.5
    assert st._all == hodnoty
    assert st.session_count == len(hodnoty)
    assert st.session_max == max(b for _, b in hodnoty)
    assert st.session_min == min(b for _, b in hodnoty)
    assert st.average == pytest.approx(sum(b for _, b in hodnoty) / len(hodnoty))
    assert st.last_bpm == hodnoty[-1][1]
    # pasmo stale z medianu 5 SUROVYCH vzoriek, nie z cisla na obrazovke
    posledne = sorted(b for _, b in hodnoty[-hr_stats.ZONE_MEDIAN_SAMPLES:])
    base = st._zakladna_bez_odhadu()
    assert base is not None
    assert st.zone == hr_stats.zone_of_bpm(posledne[2], base, st.critical_bpm)


# --------------------------------------------------------------------------
# Appka: kam ide surova vzorka a co sa ukazuje
# --------------------------------------------------------------------------

class _Stats:
    """Atrapa `hr_stats`, ktora si pamata, co do merania prislo."""

    def __init__(self):
        self.prijate = []
        self.last_bpm = None

    def add(self, bpm, ts=None):
        self.prijate.append(bpm)
        self.last_bpm = bpm


def _prijem(stats):
    return types.SimpleNamespace(
        _hr_generation=3, _hr_state="connecting", _hr_bind_retries=0,
        _hr_last_bpm=None, hr_stats=stats, _hr_lost=False,
        _hr_session_open=False,
        hud=types.SimpleNamespace(set_connected=_nic),
        _refresh_hud_session_text=_nic, _refresh_dnes_stats=_nic,
        refresh_hr_status_label=_nic, _refresh_kamae_state_text=_nic)


def test_apply_hr_bpm_posiela_do_merania_kazdu_surovu_vzorku():
    stats = _Stats()
    a = _prijem(stats)
    rad = [HORE, DOLE, HORE + 1, DOLE - 2, HORE - 1, DOLE + 1]
    for bpm in rad:
        _app()._apply_hr_bpm(a, bpm, 3)
        # rozhodovanie (vypadok, kontrolka, vstup bez pauzy) ide zo suroveho
        assert a._hr_last_bpm == bpm
    assert stats.prijate == rad


def test_rozhodovanie_cita_surovy_tep_nie_vyhladeny():
    """`_hr_last_bpm` zostava posledna surova vzorka a cita sa len ako
    "tep chodi / nechodi" - vyhladene cislo tam nema co robit."""
    telo = zdroj_metody("_apply_hr_bpm")
    assert "self._hr_last_bpm = bpm" in telo
    assert "self.hr_stats.add(bpm)" in telo
    assert "display_bpm" not in telo
    for metoda in ("_zaznamenaj_vypadok", "_tick_nonstop_input"):
        assert "display_bpm" not in zdroj_metody(metoda), metoda


def _stitok_atrapa(st, **navyse):
    a = types.SimpleNamespace(
        _hr_generation=5, _hr_state="connected", _hr_last_bpm=None,
        hr_critical_bpm=110, pal=theme.tokens(theme.DEFAULT_THEME),
        hr_stats=st)
    a.__dict__.update(navyse)
    return a


def test_stitok_pri_prepinaci_ukazuje_vyhladene_cislo():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    a = _stitok_atrapa(st, _hr_last_bpm=DOLE)
    text, _farba = _app()._hr_status_display(a)
    assert text == f"❤️ {st.display_bpm} BPM"
    assert st.display_bpm != DOLE


def test_stitok_farbu_berie_z_vyhladeneho_cisla():
    """Surova 107 by bola pod hranicou 110, vyhladene 112 je nad nou -
    farba sa riadi tym, co hrac vidi."""
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4, hore=117, dole=107)
    assert st.display_bpm == 112
    a = _stitok_atrapa(st, _hr_last_bpm=107)
    assert _app()._hr_status_display(a)[1] == theme.zone_color(a.pal, "critical")


def test_stitok_bez_tepu_neukaze_cislo_ani_po_vypadku():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    st.clear_live()
    a = _stitok_atrapa(st, _hr_state="linked", _hr_last_bpm=None)
    assert "BPM" not in _app()._hr_status_display(a)[0]


class _Widget:
    def __init__(self, mapped=True):
        self.kw, self.mapped = {}, mapped

    def configure(self, **kw):
        self.kw.update(kw)

    def set_value(self, *_a, **_k):
        pass

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


def test_dnes_ukazuje_vyhladene_cislo():
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
    a = types.SimpleNamespace(
        hr_stats=st, _hr_state="connected", _hr_lost=False,
        pal=theme.tokens(theme.MODERN), hr_critical_bpm=110,
        dnes_bpm=_Widget(), dnes_spark=_Widget(), dnes_load=_Widget(),
        dnes_zone=_Widget(), hr_panel=_Widget(),
        dnes_empty=_Widget(mapped=False), dnes_live=_Widget(),
        _refresh_session_trace=_nic, _refresh_zone_panel=_nic,
        _refresh_dashboard_stats=_nic, _refresh_last_cue=_nic,
        _stop_dnes_hero=_nic, _start_dnes_hero=_nic)
    _app()._refresh_dnes_stats(a)
    assert getattr(a, "_dnes_refresh_fails", 0) == 0
    assert a.dnes_bpm.kw["text"] == str(st.display_bpm)
    assert st.display_bpm != int(st.last_bpm)


def test_hud_kresli_vyhladene_cislo(monkeypatch):
    import hud as hud_mod
    st = hr_stats.HeartStats()
    _dva_rady(st, n=4)
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
    assert zachytene["bpm"] == st.display_bpm
    assert zachytene["bpm"] != st.last_bpm
    # krivka ostava surova - dva rady v nej ostanu vidiet
    assert HORE in zachytene["history"] and DOLE in zachytene["history"]
