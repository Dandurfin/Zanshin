# -*- coding: utf-8 -*-
"""Nastavovanie pri stole sa neuci ako hranie (0.2.2).

Audit: uvod, parovanie a prehliadka lahko trvaju viac nez 5 minut. Prva
relacia tak bola pokoj pri stole ulozeny ako "hra" a kalibroval hranicu
vysokeho tepu aj prah zataze - ta ista chyba ako pokles 110 -> 80 z
KNOWN_ISSUES. Najmensia poctiva oprava:

  * prva ULOZENA relacia po uvode dostane `setup: True` (kratka, ktora sa
    neulozi, znacku nespotrebuje); po restarte uz nie,
  * `hr_stats.ciste_relacie` ju vynecha ako obnovenu (`recovered`) - prah,
    hranica, dlhodoba zakladna ani promocia sa z nej neucia, Historia ju
    ukazuje dalej,
  * dotaznik ma cip "Len nastavovanie appky": pri prvej relacii zapnuty od
    appky (kto pritom naozaj hral, vypne ho), pri inej ho hrac zapne sam,
  * export/import znacku prenesie.

Vsetko v tmp priecinku - %APPDATA%\\Zanshin sa nedotyka nic.
"""
import os
import random
import sys
import time
import types

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import rebrik  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402


def _nic(*_a, **_k):
    return None


# --------------------------------------------------------------------------
# Ucenie: ciste_relacie a co z nich zije
# --------------------------------------------------------------------------

def _pokoj_pri_stole(i, **navyse):
    """10 minut pokoja pri stole - presne to, co by hranicu stiahlo dole."""
    s = {"started": 1_790_000_000.0 + i * 3600.0, "duration_s": 600.0,
         "world": "play", "baseline_bpm": 62.0, "avg_bpm": 66.0,
         "max_bpm": 74.0, "samples": 300,
         "curve": [64.0 + (j % 8) for j in range(200)]}
    s.update(navyse)
    return s


def test_ciste_relacie_vynechaju_nastavovanie():
    hra = _pokoj_pri_stole(0)
    stol = _pokoj_pri_stole(1, setup=True)
    zrusene = _pokoj_pri_stole(2, setup=False)
    assert hr_stats.ciste_relacie([hra, stol, zrusene]) == [hra, zrusene]


def test_hranica_sa_z_nastavovania_neuci():
    """Tri relacie pokoja pri stole by bez znacky dali hranicu 80 namiesto
    zalohy 110 (KNOWN_ISSUES, 0.2.1). So znackou ostava zaloha."""
    bez = [_pokoj_pri_stole(i) for i in range(3)]
    so = [_pokoj_pri_stole(i, setup=True) for i in range(3)]
    assert hr_stats.dynamicky_kriticky(bez) < hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_kriticky(so) == hr_stats.KRITICKY_ZALOHA
    assert hr_stats.dynamicky_prah_zataze(
        so, baseline=62.0, critical=hr_stats.KRITICKY_ZALOHA) is None
    assert hr_stats.dlhodoba_zakladna(so) is None
    assert hr_stats.dlhodoba_zakladna(bez) == pytest.approx(62.0)


def test_historia_nastavovanie_ukazuje():
    s = _pokoj_pri_stole(0, setup=True)
    assert hr_stats.sessions_in_world([s], "play") == [s]


# --------------------------------------------------------------------------
# Dotaznik: attach_context
# --------------------------------------------------------------------------

def _ulozena(tmp_path, **navyse):
    cesta = str(tmp_path / "hr_sessions.json")
    s = dict(_pokoj_pri_stole(0, samples=300), **navyse)
    assert hr_stats.save_session(cesta, s)
    return cesta, s["started"]


def test_cip_znacku_zapne_zrusi_a_bez_odpovede_necha(tmp_path):
    cesta, started = _ulozena(tmp_path)
    assert hr_stats.attach_context(cesta, started, ["chill"], setup=True)
    s = hr_stats.load_sessions(cesta)[0]
    assert s["setup"] is True and s["context"] == ["chill"]
    # None = nemenit (napr. stare volanie bez cipu)
    assert hr_stats.attach_context(cesta, started, [])
    assert hr_stats.load_sessions(cesta)[0]["setup"] is True
    # False = hrac cip vypol, lebo naozaj hral
    assert hr_stats.attach_context(cesta, started, [], setup=False)
    assert "setup" not in hr_stats.load_sessions(cesta)[0]


# --------------------------------------------------------------------------
# Prva relacia po uvode (skutocne `_close_hr_session` / `_suhrn_relacie`)
# --------------------------------------------------------------------------

class _Root:
    def __init__(self):
        self.ulohy = {}
        self._n = 0

    def after(self, ms, fn):
        self._n += 1
        uid = "after#%d" % self._n
        self.ulohy[uid] = (ms, fn)
        return uid

    def after_cancel(self, uid):
        self.ulohy.pop(uid, None)


def _statistika(minut):
    teraz = time.time()
    st = hr_stats.HeartStats(critical_bpm=110)
    st.session_start = teraz - minut * 60.0
    for i in range(int(minut * 30)):
        st.add(70 + (i % 12), ts=st.session_start + i * 2.0)
    return st


def _appka(tmp_path, minut=15, prvy_start=True):
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root()
    a.log = _nic
    a.log_threadsafe = _nic
    a.hr_sessions_path = str(tmp_path / "hr_sessions.json")
    a.hr_events_path = str(tmp_path / "hr_events.jsonl")
    a.hr_stats = _statistika(minut)
    a.cue_trigger = trigger.CueTrigger(rng=random.Random(1))
    a.cue_trigger.open_session(silent_share=0.0)
    a._cue_log = []
    a._hr_session_open = True
    a._session_world = "play"
    a._cue_rung = rebrik.HLAS
    a._cue_style_rel = rebrik.STYL_HLAS
    a._snooze_po_hlaske = None
    a._hud_tick_t = None
    a._hud_vis_s = 0.0
    a._hud_active_s = 0.0
    a._hud_is_visible = lambda: False
    a._set_enso_armed = _nic
    a._save_measure_windows = _nic
    a._refresh_history_page = _nic
    a.dotazniky = []
    a._ask_session_context = a.dotazniky.append
    a._maybe_graduate = _nic
    a.run_hr_analysis = _nic
    a._relacia_nastavovania = prvy_start
    return a


def test_init_znacku_berie_len_z_prveho_startu():
    init = zdroj_metody("__init__")
    assert 'self._relacia_nastavovania = bool(settings["first_run"])' in init
    # skor, nez sa moze otvorit prva relacia
    assert (init.index("self._relacia_nastavovania")
            < init.index("self.start_heart_rate_monitor()"))


def test_prva_ulozena_relacia_po_uvode_je_nastavovanie(tmp_path):
    a = _appka(tmp_path)
    a._close_hr_session()
    [ulozena] = hr_stats.load_sessions(a.hr_sessions_path)
    assert ulozena["setup"] is True
    assert hr_stats.ciste_relacie([ulozena]) == []
    assert a._relacia_nastavovania is False, "len prva relacia"
    # dotaznik dostane suhrn so znackou - cip bude zapnuty
    assert a.dotazniky and a.dotazniky[0]["setup"] is True

    # dalsia relacia v tom istom behu uz je obycajna
    a.hr_stats = _statistika(15)
    a.hr_stats.session_start -= 3600.0
    a._hr_session_open = True
    a._close_hr_session()
    druha = hr_stats.load_sessions(a.hr_sessions_path)[-1]
    assert "setup" not in druha


def test_kratka_relacia_znacku_nespotrebuje(tmp_path):
    """Pod minutu (napr. sledovanie pred sparovanim hodiniek) sa neulozi -
    nastavovanie je az ta dalsia, so sparovanymi hodinkami."""
    a = _appka(tmp_path, minut=0.5)
    a._close_hr_session()
    assert hr_stats.load_sessions(a.hr_sessions_path) == []
    assert a._relacia_nastavovania is True


def test_bez_uvodu_ziadna_znacka(tmp_path):
    a = _appka(tmp_path, prvy_start=False)
    a._close_hr_session()
    [ulozena] = hr_stats.load_sessions(a.hr_sessions_path)
    assert "setup" not in ulozena


def test_kontrolny_bod_nesie_znacku(tmp_path):
    """Pad pocas nastavovania: obnovena relacia je aj tak `recovered`, ale
    znacka nesmie zmiznut - dotaznik o nej sa uz nespyta."""
    a = _appka(tmp_path)
    assert a._suhrn_relacie()["setup"] is True
    a._relacia_nastavovania = False
    assert "setup" not in a._suhrn_relacie()


def test_dotaznik_posle_cip_do_suboru(tmp_path):
    import app as app_mod
    cesta, started = _ulozena(tmp_path, setup=True)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.hr_sessions_path = cesta
    a.log_threadsafe = _nic
    a._refresh_history_page = _nic
    a.run_hr_analysis = _nic
    suhrn = {"started": started, "world": "play"}
    assert a.save_session_context(suhrn, [], setup=False) is True
    assert "setup" not in hr_stats.load_sessions(cesta)[0]
    assert a.save_session_context(suhrn, [], setup=True) is True
    assert hr_stats.load_sessions(cesta)[0]["setup"] is True


# --------------------------------------------------------------------------
# Cip v dotazniku (SessionEndDialog bez Tk)
# --------------------------------------------------------------------------

class _Tlacidlo:
    def __init__(self):
        self.farby = {}

    def configure(self, **k):
        self.farby.update(k)


def _dialog(setup):
    import theme
    import ui_dialogs
    d = ui_dialogs.SessionEndDialog.__new__(ui_dialogs.SessionEndDialog)
    d.app = types.SimpleNamespace(pal=theme.tokens(theme.DEFAULT_THEME))
    d.setup = setup
    d._setup_btn = _Tlacidlo()
    return d


def test_cip_sa_prepina_a_prefarbi():
    d = _dialog(False)
    d._paint_setup()
    assert d._setup_btn.farby["fg_color"] == "transparent"
    d._prepni_setup()
    assert d.setup is True
    assert d._setup_btn.farby["text_color"] == d.app.pal["accent"]
    d._prepni_setup()
    assert d.setup is False
    assert d._setup_btn.farby["fg_color"] == "transparent"


def test_ulozit_posle_stav_cipu():
    d = _dialog(True)
    posielane = []
    d.app.save_session_context = lambda *a, **k: posielane.append(k)
    d.summary = {"started": 1.0}
    d.vybrane, d._body_sel = set(), set()
    d.activity = d.sleep = d.felt_load = d.valence = d.cue_verdict = None
    d.note_box = None
    d.close = _nic
    d.confirm()
    assert posielane[0]["setup"] is True


def test_dotaznik_cip_kresli_a_zacina_podla_suhrnu():
    ud = zdroj_suboru("ui_dialogs.py")
    trieda = ud[ud.index("class SessionEndDialog"):ud.index("class ImportProfileDialog")]
    assert 'self.setup = bool(summary.get("setup"))' in trieda
    assert 'tr("session.context.setup")' in trieda
    assert 'tr("session.context.setup_hint")' in trieda
    assert "command=self._prepni_setup" in trieda
    assert "setup=self.setup" in trieda


def test_cip_zapnuty_appkou_povie_preco_a_ako_ho_zrusit():
    """Prva relacia po uvode ma cip zapnuty od appky. Bez vety hrac nevie
    preco - a kto pritom naozaj hral, ho Ulozenim necha (prvy vecer by sa
    do ucenia nezaratal)."""
    ud = zdroj_suboru("ui_dialogs.py")
    trieda = ud[ud.index("class SessionEndDialog"):ud.index("class ImportProfileDialog")]
    assert ('tr("session.context.setup_hint_first") if self.setup'
            in trieda), "veta podla stavu cipu pri otvoreni"
    sk = i18n.STRINGS["session.context.setup_hint_first"]["sk"]
    assert "označila sama" in sk and "odznač" in sk
    en = i18n.STRINGS["session.context.setup_hint_first"]["en"]
    assert "myself" in en and "untick" in en


def test_texty_cipu_vo_vsetkych_jazykoch():
    for kluc in ("session.context.setup", "session.context.setup_hint",
                 "session.context.setup_hint_first"):
        for jazyk in i18n.LANGUAGES:
            assert i18n.STRINGS[kluc].get(jazyk, "").strip(), (kluc, jazyk)
    assert i18n.STRINGS["session.context.setup"]["sk"] == "Len nastavovanie appky"
    assert i18n.STRINGS["session.context.setup"]["en"] == "Just setting up the app"


# --------------------------------------------------------------------------
# Export / import
# --------------------------------------------------------------------------

def test_export_a_import_znacku_prenesu(tmp_path):
    s = _pokoj_pri_stole(0, setup=True)
    cesta = data_io.write_bundle(str(tmp_path / "e.json"),
                                 data_io.build_bundle([s], []))
    sessions, windows, zahodene = data_io.parse_bundle(cesta)
    assert zahodene == 0 and windows == []
    assert sessions == [dict(s, imported=True)]
    assert sessions[0]["setup"] is True
