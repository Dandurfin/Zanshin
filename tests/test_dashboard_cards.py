# -*- coding: utf-8 -*-
"""Karty „Moje štatistiky" na Dnes (B2): strop 4 kariet, posledná karta
ostáva, výmena miest potiahnutím a výber, ktorý sa zmestí na obrazovku.

Testy bežia bez Tk: čisté funkcie zo settings_model/ui_kit a skutočné
metódy `DandurfApp` na malej atrape (rovnako ako test_hr_dropout.py).
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from settings_model import (  # noqa: E402
    DASHBOARD_MAX_CARDS, DASHBOARD_STAT_IDS, DEFAULT_DASHBOARD_STATS,
    dashboard_stat_clickable, normalize_dashboard_stats,
    swap_dashboard_stats, toggle_dashboard_stat,
)

PLNE = ["baseline", "hrr", "over", "breath"]


# --------------------------------------------------------------------------
# settings_model: vymena, strop, posledna karta
# --------------------------------------------------------------------------

def test_strop_su_styri_karty_mriezka_2x2():
    assert DASHBOARD_MAX_CARDS == 4
    assert len(DEFAULT_DASHBOARD_STATS) <= DASHBOARD_MAX_CARDS


def test_vymena_prehodi_len_dve_karty():
    assert swap_dashboard_stats(["a", "b", "c", "d"], "a", "c") == ["c", "b", "a", "d"]
    assert swap_dashboard_stats(["a", "b", "c", "d"], "d", "c") == ["a", "b", "d", "c"]


def test_vymena_bez_ciela_alebo_sama_na_seba_nic_nemeni():
    stats = ["a", "b", "c"]
    assert swap_dashboard_stats(stats, "a", "a") == stats
    assert swap_dashboard_stats(stats, "a", None) == stats
    assert swap_dashboard_stats(stats, "a", "x") == stats
    assert swap_dashboard_stats(stats, "x", "b") == stats


def test_vymena_nemeni_vstup():
    stats = ["a", "b", "c"]
    out = swap_dashboard_stats(stats, "a", "c")
    assert stats == ["a", "b", "c"] and out is not stats
    assert swap_dashboard_stats(stats, "a", "a") is not stats


def test_pridanie_ide_na_koniec_kym_je_miesto():
    assert toggle_dashboard_stat(["hrr", "over"], "avg") == ["hrr", "over", "avg"]


def test_piata_karta_sa_neprida():
    assert toggle_dashboard_stat(PLNE, "avg") == PLNE
    assert not dashboard_stat_clickable(PLNE, "avg")
    # zvolene sa daju odobrat aj pri plnej mriezke - tym sa miesto uvolni
    assert toggle_dashboard_stat(PLNE, "hrr") == ["baseline", "over", "breath"]
    assert dashboard_stat_clickable(PLNE, "hrr")


def test_posledna_karta_ostava():
    assert toggle_dashboard_stat(["hrr"], "hrr") == ["hrr"]
    assert not dashboard_stat_clickable(["hrr"], "hrr")
    # dve karty: jedna sa odobrat da
    assert toggle_dashboard_stat(["hrr", "over"], "hrr") == ["over"]


def test_toggle_nemeni_vstup():
    stats = ["hrr", "over"]
    toggle_dashboard_stat(stats, "avg")
    toggle_dashboard_stat(stats, "hrr")
    assert stats == ["hrr", "over"]


def test_strop_je_genericky_nie_viazany_na_pocet_metrik():
    """Katalog moze rast (dalsia polozka pridava nove metriky) - strop je
    jedno cislo a nepredpoklada, kolko ich je."""
    katalog = [f"m{i}" for i in range(13)]
    stats = []
    for sid in katalog:
        stats = toggle_dashboard_stat(stats, sid)
    assert stats == katalog[:DASHBOARD_MAX_CARDS]
    zvysne = [s for s in katalog if not dashboard_stat_clickable(stats, s)]
    assert zvysne == katalog[DASHBOARD_MAX_CARDS:]
    assert toggle_dashboard_stat(["a", "b"], "c", max_cards=2) == ["a", "b"]


def test_normalizacia_ostava_ako_bola():
    """Autor: semantika normalize_dashboard_stats sa nemeni (prazdne ->
    predvolene, poradie ostava, strop sa rata az v appke)."""
    assert normalize_dashboard_stats([]) == list(DEFAULT_DASHBOARD_STATS)
    assert normalize_dashboard_stats(list(DASHBOARD_STAT_IDS)) == list(DASHBOARD_STAT_IDS)


# --------------------------------------------------------------------------
# ui_kit.fit_popup: vyber sa zmesti na obrazovku
# --------------------------------------------------------------------------

def test_popup_pod_tlacidlom_ked_sa_zmesti():
    import ui_kit
    assert ui_kit.fit_popup(500, 300, 240, 400, (0, 0, 1920, 1040), 270) == (500, 300)


def test_popup_nad_tlacidlom_ked_sa_dole_nezmesti():
    import ui_kit
    x, y = ui_kit.fit_popup(500, 800, 240, 400, (0, 0, 1920, 1040), 770)
    assert (x, y) == (500, 770 - 400 - 4)


def test_popup_pritlaceny_dovnutra_obrazovky_aj_na_druhom_monitore():
    import ui_kit
    area = (1920, 0, 3840, 1040)          # monitor vpravo od primarneho
    x, _y = ui_kit.fit_popup(3700, 100, 240, 300, area, 70)
    assert x == 3840 - 240 - 8
    x, _y = ui_kit.fit_popup(1900, 100, 240, 300, area, 70)
    assert x == 1920 + 8, "na druhom monitore nesmie odskocit na prvy"


def test_popup_vyssi_nez_obrazovka_ostane_hore():
    import ui_kit
    _x, y = ui_kit.fit_popup(10, 50, 240, 2000, (0, 0, 1920, 1040), 20)
    assert y == 8


def _tlacidlo(x, y):
    return types.SimpleNamespace(
        winfo_rootx=lambda: x, winfo_rooty=lambda: y,
        winfo_width=lambda: 80, winfo_height=lambda: 20,
        winfo_screenwidth=lambda: 1920, winfo_screenheight=lambda: 1080)


def test_pracovna_plocha_je_monitor_pod_tlacidlom_bez_listy(monkeypatch):
    import display
    import ui_kit
    mons = [display.Monitor(0, 0, 1920, 1080, primary=True, work=(0, 0, 1920, 1040)),
            display.Monitor(1920, 0, 2560, 1440, work=(1920, 0, 2560, 1400))]
    monkeypatch.setattr(ui_kit.display_mod, "monitors", lambda _w=None: mons)
    assert ui_kit.work_area(_tlacidlo(2500, 300)) == (1920, 0, 4480, 1400)
    assert ui_kit.work_area(_tlacidlo(100, 300)) == (0, 0, 1920, 1040)


def test_pracovna_plocha_bez_monitora_padne_na_obrazovku(monkeypatch):
    import ui_kit
    monkeypatch.setattr(ui_kit.display_mod, "monitors", lambda _w=None: [])
    assert ui_kit.work_area(_tlacidlo(100, 300)) == (0, 0, 1920, 1080)


# --------------------------------------------------------------------------
# DandurfApp: klik vo vybere, ✕, tahanie karty
# --------------------------------------------------------------------------

def _app():
    import app as app_mod
    return app_mod


class _Card:
    def __init__(self, x, y, w=100, h=60):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.look = None
        self.looks = []

    def winfo_rootx(self):
        return self.x

    def winfo_rooty(self):
        return self.y

    def winfo_width(self):
        return self.w

    def winfo_height(self):
        return self.h

    def set_drag_look(self, role=None):
        self.look = role
        self.looks.append(role)


class _Widget:
    def __init__(self):
        self.cursor = ""

    def configure(self, **kw):
        if "cursor" in kw:
            self.cursor = kw["cursor"]


def _ev(x, y, widget=None):
    return types.SimpleNamespace(x_root=x, y_root=y, widget=widget or _Widget())


# mriezka 2x2: karty 100x60, medzera 10 px
MIESTA = {"baseline": (0, 0), "hrr": (110, 0), "over": (0, 70), "breath": (110, 70)}
STRED = {k: (x + 50, y + 30) for k, (x, y) in MIESTA.items()}
MEDZERA = (105, 30)


def _atrapa(stats=PLNE):
    app_mod = _app()
    ulozene, idle, prestavby, riadky = [], [], [], []
    a = types.SimpleNamespace(
        dashboard_stats=list(stats),
        dashboard_cards={k: _Card(*MIESTA[k]) for k in stats if k in MIESTA},
        _dashboard_drag_state=None,
        DASHBOARD_DRAG_PX=app_mod.DandurfApp.DASHBOARD_DRAG_PX,
        root=types.SimpleNamespace(after_idle=idle.append),
        _render_dashboard_picker_rows=lambda: riadky.append(1),
    )
    a.save_settings = lambda: ulozene.append(list(a.dashboard_stats))
    a._rebuild_dashboard_stats_grid = lambda: prestavby.append(list(a.dashboard_stats))
    for name in ("_dashboard_card_at", "_dashboard_drag_reset", "_dashboard_drag",
                 "_toggle_dashboard_stat"):
        setattr(a, name, types.MethodType(getattr(app_mod.DandurfApp, name), a))
    a.ulozene, a.idle, a.prestavby, a.riadky = ulozene, idle, prestavby, riadky
    return a


def _tah(a, src, body, pohyby=True):
    """Stlac na karte `src`, (volitelne pohni) a pusti na bode posledneho z `body`."""
    w = _Widget()
    x0, y0 = STRED[src]
    a._dashboard_drag(src, "press", _ev(x0, y0, w))
    if pohyby:
        for (x, y) in body:
            a._dashboard_drag(src, "move", _ev(x, y, w))
    x, y = body[-1]
    a._dashboard_drag(src, "release", _ev(x, y, w))
    return w


def test_klik_vo_vybere_pri_plnej_mriezke_nic_neurobi():
    a = _atrapa(PLNE)
    a._toggle_dashboard_stat("avg")
    assert a.dashboard_stats == PLNE
    assert a.ulozene == [] and a.prestavby == [] and a.riadky == []


def test_posledna_karta_sa_neda_odobrat():
    a = _atrapa(["hrr"])
    a._toggle_dashboard_stat("hrr")
    assert a.dashboard_stats == ["hrr"] and a.ulozene == []


def test_odobratie_uvolni_miesto_a_ulozi():
    a = _atrapa(PLNE)
    a._toggle_dashboard_stat("over")
    assert a.dashboard_stats == ["baseline", "hrr", "breath"]
    assert a.ulozene == [a.dashboard_stats] and a.prestavby and a.riadky
    a._toggle_dashboard_stat("avg")
    assert a.dashboard_stats == ["baseline", "hrr", "breath", "avg"]


def test_potiahnutie_na_inu_kartu_vymeni_miesta_a_ulozi():
    a = _atrapa()
    w = _tah(a, "baseline", [(60, 40), STRED["breath"]])
    assert a.dashboard_stats == ["breath", "hrr", "over", "baseline"]
    assert a.ulozene == [a.dashboard_stats]
    # prestavba az po udalosti - znici aj widget, ktory ju prave vybavuje
    assert a.idle == [a._rebuild_dashboard_stats_grid]
    assert w.cursor == "", "kurzor po pusteni spat"
    assert all(c.look is None for c in a.dashboard_cards.values())


def test_rozhoduje_pustenie_aj_bez_jedineho_pohybu():
    """Skutocna mys niekedy do Tk nepusti ani jeden B1-Motion."""
    a = _atrapa()
    _tah(a, "hrr", [STRED["over"]], pohyby=False)
    assert a.dashboard_stats == ["baseline", "over", "hrr", "breath"]


def test_obycajny_klik_nic_nemeni():
    a = _atrapa()
    _tah(a, "hrr", [(STRED["hrr"][0] + 3, STRED["hrr"][1] + 2)])
    assert a.dashboard_stats == PLNE and a.ulozene == [] and a.idle == []
    assert all(c.look is None for c in a.dashboard_cards.values())


def test_pustenie_do_medzery_alebo_mimo_nic_nemeni():
    a = _atrapa()
    _tah(a, "baseline", [(60, 40), MEDZERA])
    _tah(a, "baseline", [(60, 40), (900, 900)])
    _tah(a, "baseline", [(60, 40), (STRED["baseline"][0] + 20, STRED["baseline"][1])])
    assert a.dashboard_stats == PLNE and a.ulozene == [] and a.idle == []
    assert all(c.look is None for c in a.dashboard_cards.values())


def test_pohyb_len_zvyraznuje_zdroj_a_ciel():
    a = _atrapa()
    w = _Widget()
    a._dashboard_drag("baseline", "press", _ev(*STRED["baseline"], w))
    a._dashboard_drag("baseline", "move", _ev(STRED["baseline"][0] + 3, STRED["baseline"][1], w))
    assert a.dashboard_cards["baseline"].look is None, "pod prahom sa tah nezacina"
    assert w.cursor == ""
    a._dashboard_drag("baseline", "move", _ev(*STRED["hrr"], w))
    assert a.dashboard_cards["baseline"].look == "source"
    assert a.dashboard_cards["hrr"].look == "target"
    assert w.cursor == "fleur"
    a._dashboard_drag("baseline", "move", _ev(*MEDZERA, w))
    assert a.dashboard_cards["hrr"].look is None, "ciel zhasne v medzere"
    a._dashboard_drag("baseline", "move", _ev(*STRED["breath"], w))
    assert a.dashboard_cards["breath"].look == "target"
    assert a.dashboard_stats == PLNE and a.ulozene == [], "pohyb sam nic neulozi"


def test_kazde_stlacenie_zhodi_zvysky_strateneho_tahu():
    """Alt-tab uprostred tahu: pustenie nepride a okraje by ostali svietit."""
    a = _atrapa()
    w = _Widget()
    a._dashboard_drag("baseline", "press", _ev(*STRED["baseline"], w))
    a._dashboard_drag("baseline", "move", _ev(*STRED["hrr"], w))
    assert a.dashboard_cards["hrr"].look == "target"
    # ... pustenie sa stratilo; dalsie stlacenie inde
    a._dashboard_drag("over", "press", _ev(*STRED["over"]))
    assert all(c.look is None for c in a.dashboard_cards.values())
    assert w.cursor == ""


def test_cudzie_pustenie_bez_stlacenia_nic_nerobi():
    a = _atrapa()
    a._dashboard_drag("hrr", "release", _ev(*STRED["over"]))
    a._dashboard_drag("hrr", "move", _ev(*STRED["over"]))
    assert a.dashboard_stats == PLNE and a.ulozene == []


# --------------------------------------------------------------------------
# zdroj: StatCard tahanie neviaze na ⓘ ani ✕
# --------------------------------------------------------------------------

def test_statcard_tahanie_len_na_plochach_karty():
    with open(os.path.join(ROOT, "ui_kit.py"), encoding="utf-8") as fh:
        src = fh.read()
    card = src[src.index("class StatCard"):src.index("class QrReveal")]
    drag = card[card.index("if on_drag is not None:"):card.index("def set_drag_look")]
    assert "(self, body, head, self.value_label, self.tag_label)" in drag
    assert "_info_btn" not in drag and "_remove_btn" not in drag
