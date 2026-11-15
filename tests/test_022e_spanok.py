# -*- coding: utf-8 -*-
"""PC sleep splits the session (0.3, batch 4).

A session across sleep/hibernation lasted as long as 14 hours and the
sleeping heart rate got into the resting baseline. A gap between session
ticks above `MEDZERA_SPANKU_S` while watching = the session is closed at the
LAST TICK before the gap (the normal saving path) and a new one starts after
it. A clock going backwards is not a gap.
Injected clock, no waiting."""
import math
import time

import app_session
import hr_stats
from i18n import tr
from _zdroj_appky import zdroj_metody

import test_022b_data_vypnutie as vypnutie


def test_medzera_spanku_je_len_dlhy_skok_dopredu():
    assert app_session.MEDZERA_SPANKU_S == 120.0
    assert app_session.je_medzera_spanku(1000.0, 1121.0)
    assert not app_session.je_medzera_spanku(1000.0, 1120.0)
    assert not app_session.je_medzera_spanku(1000.0, 1000.25)
    # a clock going backwards (time sync) is not sleep
    assert not app_session.je_medzera_spanku(5000.0, 1000.0)
    for zle in (None, "x", math.nan):
        assert not app_session.je_medzera_spanku(zle, 2000.0)
        assert not app_session.je_medzera_spanku(1000.0, zle)


def _appka(tmp_path, minut=15):
    a = vypnutie._appka(tmp_path, minut=minut)

    def otvor(**k):
        a.otvorene.append(k)
        a._hr_session_open = True
    a._open_hr_session = otvor
    return a


def test_spanok_rozdeli_relaciu_k_poslednemu_tiku(tmp_path):
    a = _appka(tmp_path, minut=15)
    zaciatok = a.hr_stats.session_start
    posledny = zaciatok + 10 * 60.0
    a._posledny_tik_relacie = posledny
    po_prebudeni = posledny + 9 * 3600.0
    assert a._hlidaj_medzeru_relacie(teraz=po_prebudeni) is True
    historia = hr_stats.load_sessions(a.hr_sessions_path)
    assert len(historia) == 1
    assert historia[0]["duration_s"] == 600.0, "relacia konci poslednym tikom, nie po spanku"
    assert a.dotazniky == [], "po prebudeni ziadny dotaznik - hrac pri tom nebol"
    assert a.otvorene == [{"prepoj": False, "meria": True}], "nova relacia po spanku"
    assert a.denn[-1] == tr("log.session_split_sleep", min=540)
    assert a._posledny_tik_relacie == po_prebudeni


def test_bez_sledovania_alebo_bez_prijmu_sa_nova_neotvori(tmp_path):
    a = _appka(tmp_path)
    a._posledny_tik_relacie = a.hr_stats.session_start + 300.0
    a.heart_rate_monitor.running = False
    a._hlidaj_medzeru_relacie(teraz=a._posledny_tik_relacie + 600.0)
    assert a.otvorene == []
    assert a.denn[-1] == tr("log.session_split_sleep_end", min=10)
    assert len(hr_stats.load_sessions(a.hr_sessions_path)) == 1


def test_kratka_medzera_ani_hodiny_dozadu_nic_nerozdelia(tmp_path):
    a = _appka(tmp_path)
    t = a.hr_stats.session_start + 300.0
    a._posledny_tik_relacie = t
    assert a._hlidaj_medzeru_relacie(teraz=t + 0.25) is False
    assert a._hlidaj_medzeru_relacie(teraz=t + 60.0) is False
    # the clock jumped an hour backwards: the starting point just moves
    assert a._hlidaj_medzeru_relacie(teraz=t - 3600.0) is False
    assert a._posledny_tik_relacie == t - 3600.0
    assert a._hlidaj_medzeru_relacie(teraz=t - 3590.0) is False
    assert a._hr_session_open and a.otvorene == [] and a.denn == []
    assert hr_stats.load_sessions(a.hr_sessions_path) == []


def test_mimo_sledovania_sa_medzera_neráta(tmp_path):
    a = _appka(tmp_path)
    a.listening = False
    t = a.hr_stats.session_start + 300.0
    a._posledny_tik_relacie = t
    assert a._hlidaj_medzeru_relacie(teraz=t + 7200.0) is False
    assert a._hr_session_open and a.denn == []
    assert a._posledny_tik_relacie == t + 7200.0, "cas sa posuva vzdy"


def test_kratka_relacia_pred_spankom_sa_neulozi(tmp_path):
    """Normal saving: a sub-minute session isn't written even after sleep."""
    a = _appka(tmp_path, minut=15)
    a._posledny_tik_relacie = a.hr_stats.session_start + 30.0
    a._hlidaj_medzeru_relacie(teraz=a._posledny_tik_relacie + 3600.0)
    assert hr_stats.load_sessions(a.hr_sessions_path) == []


def test_suhrn_sa_uzavrie_k_zadanemu_koncu():
    st = vypnutie._statistika(minut=20, teraz=time.time())
    koniec = st.session_start + 300.0
    s = st.summary(koniec=koniec)
    assert s["duration_s"] == 300.0
    assert st.summary()["duration_s"] >= 1199.0


def test_tik_aj_vzorka_tepu_hlidaju_medzeru():
    assert "self._hlidaj_medzeru_relacie()" in zdroj_metody("_tick_activity")
    bpm = zdroj_metody("_apply_hr_bpm")
    # a sample after waking belongs to the new session - check BEFORE writing
    assert bpm.index("_hlidaj_medzeru_relacie") < bpm.index("self._hr_last_bpm = bpm")
    # opening a session sets the starting point for measuring the gap
    assert "self._posledny_tik_relacie = self._hud_tick_t" in zdroj_metody("_open_hr_session")
