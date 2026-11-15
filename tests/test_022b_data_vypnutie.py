# -*- coding: utf-8 -*-
"""The session survives a PC shutdown, a crash and Task Manager (0.3).

Before 0.3 the session was written ONLY in `_close_hr_session`, and that was
called only by `stop_listening`, switching the sensor off and `_quit`
(WM_DELETE_WINDOW). A Windows shutdown, a crash, ending it via Task Manager
or `build.bat` thus threw away the whole evening. Guarded:

  * WM_SAVE_YOURSELF (this is how Tk on Windows reports WM_QUERYENDSESSION)
    saves the session WITHOUT the questionnaire and saves the settings;
    twice, and also during `_quit`, it is safe, and a cancelled shutdown
    starts measuring again,
  * checkpoint: the summary of the open session is written atomically to
    hr_session_open.json, a normal close deletes it,
  * at start the checkpoint is added to the history ONCE (`recovered`), not
    twice, and an implausible one is thrown away,
  * a recovered session does not enter threshold learning (`ciste_relacie`),
  * "Delete history" deletes the checkpoint too.

Everything in a tmp folder - nothing touches %APPDATA%\\Zanshin.
"""
import json
import os
import random
import sys
import time
import types

import pytest

import data_io
import hr_stats
import rebrik
import trigger
from _zdroj_appky import zdroj_metody, zdroj_suboru


def _nic(*_a, **_k):
    return None


class _Root:
    """`root.after` without Tk: a task runs only when the test lets it."""

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


def _statistika(minut=15, teraz=None):
    """A real `HeartStats` with a session that `save_session` accepts."""
    teraz = time.time() if teraz is None else teraz
    st = hr_stats.HeartStats(critical_bpm=110)
    st.session_start = teraz - minut * 60.0
    for i in range(int(minut * 30)):
        st.add(70 + (i % 12), ts=st.session_start + i * 2.0)
    return st


def _appka(tmp_path, minut=15):
    """The real `_close_hr_session`, `_suhrn_relacie` and session protection
    on `DandurfApp` without Tk. The questionnaire, promotion, analysis and
    settings are only recorded."""
    import app as app_mod
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root()
    a.denn = []
    a.log = a.denn.append
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
    a.promocie = []
    a._maybe_graduate = a.promocie.append
    a.analyzy = []
    a.run_hr_analysis = lambda: a.analyzy.append(True)
    a.nastavenia = []
    a.save_settings = lambda: a.nastavenia.append(True)
    a.listening = True
    a.hr_monitoring_enabled = True
    a.heart_rate_monitor = types.SimpleNamespace(running=True)
    a.otvorene = []
    a._open_hr_session = lambda **k: a.otvorene.append(k)
    return a


def _historia(a):
    return hr_stats.load_sessions(a.hr_sessions_path)


def _checkpoint(a):
    return hr_stats.cesta_rozpracovanej(a.hr_sessions_path)


# --------------------------------------------------------------------------
# (a) Windows shutdown
# --------------------------------------------------------------------------

def test_protokol_vypnutia_je_zaregistrovany_vedla_zatvorenia_okna():
    init = zdroj_metody("__init__")
    assert 'self.root.protocol("WM_DELETE_WINDOW", self.on_close)' in init
    assert ('self.root.protocol("WM_SAVE_YOURSELF", self._pri_vypinani_windows)'
            in init)


@pytest.mark.skipif(sys.platform != "win32", reason="WM_QUERYENDSESSION je vec Windows")
def test_tk_na_windows_hlasi_vypnutie_ako_wm_save_yourself():
    """Checks the assumption the fix stands on: Tk turns WM_QUERYENDSESSION
    into WM_SAVE_YOURSELF - even for a frameless window hidden in the tray
    (that is how the app usually is when the PC shuts down). The message is
    SENT to its own window, so nothing shuts down; the Tk loop handles it as
    in a real shutdown."""
    import ctypes
    from ctypes import wintypes
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip("Tk nie je k dispozicii: %s" % exc)
    try:
        root.overrideredirect(True)
        root.withdraw()
        root.update()
        volania = []
        root.protocol("WM_SAVE_YOURSELF", lambda: volania.append("vypnutie"))
        root.protocol("WM_DELETE_WINDOW", lambda: volania.append("zatvorenie"))
        # Own WinDLL, not `ctypes.windll.user32`: argtypes on the shared object
        # would apply to the whole test run (to other modules too).
        user32 = ctypes.WinDLL("user32")
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                        wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        WM_QUERYENDSESSION = 0x0011
        assert user32.PostMessageW(int(root.wm_frame(), 16), WM_QUERYENDSESSION, 0, 0)
        for _ in range(20):
            root.update()
            if volania:
                break
            time.sleep(0.01)
        assert volania == ["vypnutie"]
    finally:
        root.destroy()


def test_vypnutie_ulozi_relaciu_a_nastavenia_bez_dotaznika(tmp_path):
    a = _appka(tmp_path)
    a._pri_vypinani_windows()
    historia = _historia(a)
    assert len(historia) == 1
    assert historia[0]["duration_s"] >= 60
    assert a._hr_session_open is False
    assert a.nastavenia == [True]
    # Windows waits a few seconds - no questionnaire (it would be thrown away
    # with the process), no promotion or analysis in the background
    assert a.dotazniky == [] and a.promocie == [] and a.analyzy == []
    # the "Session saved" line goes to the journal anyway
    assert len(a.denn) == 1


def test_vypnutie_dvakrat_ulozi_relaciu_raz(tmp_path):
    a = _appka(tmp_path)
    a._pri_vypinani_windows()
    a._pri_vypinani_windows()
    assert len(_historia(a)) == 1
    # there is only one scheduled return after a cancelled shutdown (the old
    # one is cancelled)
    assert len(a.root.ulohy) == 1


def test_vypnutie_pocas_quit_nic_nezopakuje_ani_neotvori(tmp_path):
    """`_quit` has already closed the session (and waits for the
    questionnaire) - the shutdown saves only the settings and does not
    open the session after it."""
    a = _appka(tmp_path)
    a._close_hr_session()                 # like `_quit` -> `stop_listening`
    assert len(_historia(a)) == 1 and len(a.dotazniky) == 1
    a._quit_bezi = True
    a._zatvara_sa = True
    a._pri_vypinani_windows()
    assert len(_historia(a)) == 1
    assert a.nastavenia == [True]
    for _ms, fn in list(a.root.ulohy.values()):
        fn()
    assert a.otvorene == []


def test_zrusene_vypnutie_rozbehne_meranie_znova(tmp_path, monkeypatch):
    import app_data
    a = _appka(tmp_path)
    a._pri_vypinani_windows()
    (ms, fn), = a.root.ulohy.values()
    assert ms == app_data.VYPNUTIE_ZRUSENE_MS
    fn()
    # network untouched - receiving keeps running (like `start_listening`)
    assert a.otvorene == [{"prepoj": False, "meria": True}]


def test_zrusene_vypnutie_bez_pocuvania_nic_neotvori(tmp_path):
    a = _appka(tmp_path)
    a.listening = False
    a._pri_vypinani_windows()
    for _ms, fn in list(a.root.ulohy.values()):
        fn()
    assert a.otvorene == []


def test_vypnutie_prezije_chybu_pri_ukladani(tmp_path):
    """A failed session save must not stop the settings from being saved."""
    a = _appka(tmp_path)
    a._suhrn_relacie = lambda: (_ for _ in ()).throw(RuntimeError("pad"))
    a._pri_vypinani_windows()
    assert a.nastavenia == [True]
    assert a._vypnutie_bezi is False


# --------------------------------------------------------------------------
# (b) checkpoint
# --------------------------------------------------------------------------

def test_suhrn_relacie_nema_vedlajsie_ucinky(tmp_path):
    """The checkpoint runs in the middle of playing - it must not reset or
    add anything (otherwise closing would save different numbers)."""
    a = _appka(tmp_path)
    a._snooze_po_hlaske = (20.0, time.time() - 30.0)
    a._snooze_rel_s = 12.0
    a._hud_tick_t = time.time() - 1.0
    a._hud_active_s = 100.0
    a._hud_vis_s = 40.0
    pred = (a._snooze_po_hlaske, a._snooze_rel_s, a._hud_tick_t,
            a._hud_active_s, a._hud_vis_s, a._hr_session_open)
    s1 = a._suhrn_relacie()
    s2 = a._suhrn_relacie()
    assert (a._snooze_po_hlaske, a._snooze_rel_s, a._hud_tick_t,
            a._hud_active_s, a._hud_vis_s, a._hr_session_open) == pred
    assert s1["snooze_after_cue_s"] == 20.0 and s1["snoozed_s"] == 12.0
    assert s1["hud_visible_s"] == pytest.approx(s2["hud_visible_s"], abs=0.1)


def test_kontrolny_bod_je_to_iste_co_zatvorenie(tmp_path):
    a = _appka(tmp_path)
    assert a._zapis_rozpracovanu_relaciu() is True
    with open(_checkpoint(a), encoding="utf-8") as fh:
        bod = json.load(fh)
    a._close_hr_session()
    ulozena = _historia(a)[0]
    assert set(bod) == set(ulozena)
    for kluc in ("started", "world", "cue_rung", "stress_threshold", "samples",
                 "avg_bpm", "curve"):
        assert bod[kluc] == ulozena[kluc], kluc


def test_kontrolny_bod_sa_zapisuje_atomicky(tmp_path, monkeypatch):
    """Write via .tmp + os.replace - a crash midway keeps the old one whole."""
    a = _appka(tmp_path)
    assert a._zapis_rozpracovanu_relaciu()
    with open(_checkpoint(a), encoding="utf-8") as fh:
        povodny = fh.read()
    nahrady = []
    skutocny = os.replace

    def _replace(src, dst):
        nahrady.append((src, dst))
        raise OSError("disk je plny")

    monkeypatch.setattr(hr_stats.os, "replace", _replace)
    a.hr_stats.add(150, ts=time.time())
    assert a._zapis_rozpracovanu_relaciu() is False
    monkeypatch.setattr(hr_stats.os, "replace", skutocny)
    assert nahrady == [(_checkpoint(a) + ".tmp", _checkpoint(a))]
    with open(_checkpoint(a), encoding="utf-8") as fh:
        assert fh.read() == povodny


def test_kontrolny_bod_bez_otvorenej_alebo_s_kratkou_relaciou_nepise(tmp_path):
    a = _appka(tmp_path)
    a._hr_session_open = False
    assert a._zapis_rozpracovanu_relaciu() is False
    b = _appka(tmp_path, minut=0.5)       # under a minute - it would not be saved anyway
    assert b._zapis_rozpracovanu_relaciu() is False
    assert not os.path.exists(_checkpoint(a))


def test_normalne_zatvorenie_kontrolny_bod_zmaze(tmp_path):
    a = _appka(tmp_path)
    a._zapis_rozpracovanu_relaciu()
    assert os.path.exists(_checkpoint(a))
    a._close_hr_session()
    assert not os.path.exists(_checkpoint(a))
    assert len(_historia(a)) == 1


def test_nepodarene_ulozenie_kontrolny_bod_necha(tmp_path, monkeypatch):
    """Full disk on close: the checkpoint is the only copy - it stays."""
    import app_data
    a = _appka(tmp_path)
    a._zapis_rozpracovanu_relaciu()
    monkeypatch.setattr(app_data.hr_stats, "save_session", lambda *a_, **k: False)
    a._close_hr_session()
    assert os.path.exists(_checkpoint(a))


def test_tik_sa_planuje_dalej_a_pocas_quit_skonci(tmp_path):
    import app_data
    a = _appka(tmp_path)
    a._naplanuj_rozpracovanu_relaciu()
    (ms, fn), = a.root.ulohy.values()
    assert ms == app_data.ROZPRACOVANA_KAZDYCH_MS == 5 * 60 * 1000
    a.root.ulohy.clear()
    fn()
    assert os.path.exists(_checkpoint(a))
    assert len(a.root.ulohy) == 1          # next tick scheduled
    (_ms, fn2), = a.root.ulohy.values()
    a.root.ulohy.clear()
    a._quit_bezi = True
    fn2()
    assert a.root.ulohy == {}


def test_kontrolny_bod_sa_spusta_pri_starte_po_obnove():
    init = zdroj_metody("__init__")
    obnova = init.index("self._obnov_rozpracovanu_relaciu()")
    assert obnova < init.index("self._naplanuj_rozpracovanu_relaciu()")
    # recovery before the sensor opens a new session
    assert obnova < init.index("self.start_heart_rate_monitor()")


# --------------------------------------------------------------------------
# (b) recovery at start
# --------------------------------------------------------------------------

def _pad_s_kontrolnym_bodom(tmp_path):
    """A session with a checkpoint, then a "crash" - the close never came."""
    a = _appka(tmp_path)
    assert a._zapis_rozpracovanu_relaciu()
    return a


def test_obnova_prida_relaciu_raz_a_oznaci_ju(tmp_path):
    a = _pad_s_kontrolnym_bodom(tmp_path)
    b = _appka(tmp_path)                   # next start
    obnovena = b._obnov_rozpracovanu_relaciu()
    assert obnovena is not None and obnovena["recovered"] is True
    historia = _historia(b)
    assert len(historia) == 1 and historia[0]["recovered"] is True
    assert historia[0]["started"] == a.hr_stats.session_start
    assert not os.path.exists(_checkpoint(b))
    assert len(b.denn) == 1                # one line in the journal
    # the next start no longer recovers anything
    assert b._obnov_rozpracovanu_relaciu() is None
    assert len(_historia(b)) == 1


def test_obnova_nezdvoji_relaciu_ktora_sa_stihla_ulozit(tmp_path):
    """Crash AFTER the session save, but before the checkpoint was deleted."""
    a = _pad_s_kontrolnym_bodom(tmp_path)
    assert hr_stats.save_session(a.hr_sessions_path, a._suhrn_relacie())
    assert os.path.exists(_checkpoint(a))
    assert hr_stats.obnov_rozpracovanu(a.hr_sessions_path) is None
    assert len(_historia(a)) == 1
    assert not os.path.exists(_checkpoint(a))


@pytest.mark.parametrize("pokazit", [
    lambda s: s.update(duration_s=30.0),                      # under a minute
    lambda s: s.update(samples=3),                            # no data
    lambda s: s.update(started=None),                         # no time
    lambda s: s.update(started=12345.0),                      # year 1970
    lambda s: s.update(started=time.time() + 86400.0),        # in the future
    lambda s: s.update(duration_s=float("nan")),
])
def test_nevierohodny_kontrolny_bod_sa_zahodi(tmp_path, pokazit):
    a = _pad_s_kontrolnym_bodom(tmp_path)
    with open(_checkpoint(a), encoding="utf-8") as fh:
        bod = json.load(fh)
    pokazit(bod)
    with open(_checkpoint(a), "w", encoding="utf-8") as fh:
        json.dump(bod, fh)
    assert hr_stats.obnov_rozpracovanu(a.hr_sessions_path) is None
    assert _historia(a) == []
    assert not os.path.exists(_checkpoint(a)), "inak by sa posudzoval pri kazdom starte"


def test_necitatelny_kontrolny_bod_nezhodi_start(tmp_path):
    a = _appka(tmp_path)
    with open(_checkpoint(a), "w", encoding="utf-8") as fh:
        fh.write('{"started": 17')
    assert a._obnov_rozpracovanu_relaciu() is None
    assert a.denn == [] and _historia(a) == []


def test_obnovena_relacia_sa_neuci_prahy(tmp_path):
    """Decision for 0.3: a recovered session is in History, but thresholds,
    the critical heart rate and the long-term baseline are not learned from
    it (both the end and the questionnaire are missing)."""
    s = dict(_appka(tmp_path)._suhrn_relacie(), duration_s=1800.0,
             baseline_bpm=62)
    obnovena = dict(s, recovered=True)
    assert hr_stats.ciste_relacie([s]) == [s]
    assert hr_stats.ciste_relacie([obnovena]) == []
    # but it stays the player's own session (it is not foreign like an import)
    assert data_io.vlastne([obnovena]) == [obnovena]


def test_zmazat_historiu_zmaze_aj_kontrolny_bod(tmp_path):
    a = _pad_s_kontrolnym_bodom(tmp_path)
    plan = data_io.delete_plan(str(tmp_path))
    polozka = next(p for p in plan if p["label"] == "data.delete.open_session")
    assert polozka["exists"] and polozka["path"] == _checkpoint(a)
    assert os.path.basename(polozka["path"]) == hr_stats.ROZPRACOVANA_MENO
    data_io.delete_all(str(tmp_path))
    assert not os.path.exists(_checkpoint(a))


def test_texty_su_vo_vsetkych_jazykoch():
    import i18n
    for kluc, param in (("log.hr_session_recovered", "time"),
                        ("data.delete.open_session", None)):
        for jazyk in i18n.LANGUAGES:
            text = i18n.tr_lang(jazyk, kluc)
            assert text.strip() and text != kluc, (kluc, jazyk)
            if param:
                assert "{%s}" % param in i18n.STRINGS[kluc][jazyk], (kluc, jazyk)
    assert "Obnovila som reláciu" in i18n.tr_lang("sk", "log.hr_session_recovered")
    # English is not just copied into the other languages
    en = i18n.STRINGS["log.hr_session_recovered"]["en"]
    for jazyk in ("ja", "de", "cs", "bg"):
        assert i18n.STRINGS["log.hr_session_recovered"][jazyk] != en, jazyk


def test_gui_nastroje_zalohuju_kontrolny_bod_aj_zalohu_nastaveni():
    """gui_harness_auto and gui_screenshots run on the data next to main.py
    and at the end restore the history from before the run. At their start
    the app adds the checkpoint to the history and DELETES it - without a
    backup of it the tool would consume it and the session from the crashed
    app would vanish with the restored history."""
    import ast
    harness = ast.parse(zdroj_suboru("gui_harness_auto.py"))
    priradene = {u.targets[0].id: u.value for u in harness.body
                 if isinstance(u, ast.Assign) and isinstance(u.targets[0], ast.Name)}
    assert {"HR_SESSION_OPEN", "SETTINGS_BAK"} <= {
        e.id for e in priradene["ODLOZENE"].elts}
    assert repr(hr_stats.ROZPRACOVANA_MENO) in ast.unparse(priradene["HR_SESSION_OPEN"])
    assert "SETTINGS + '.bak'" == ast.unparse(priradene["SETTINGS_BAK"])
    foto = ast.parse(zdroj_suboru("gui_screenshots.py"))
    zalohovat = next(u.value for u in foto.body if isinstance(u, ast.Assign)
                     and getattr(u.targets[0], "id", None) == "ZALOHOVAT")
    mena = {k.value for k in ast.walk(zalohovat)
            if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert {hr_stats.ROZPRACOVANA_MENO, "dandurf_settings.json.bak"} <= mena


def test_checkpoint_je_v_gitignore():
    """Health data - the checkpoint must not end up in git."""
    import fnmatch
    vzory = [r.strip() for r in zdroj_suboru(".gitignore").splitlines()
             if r.strip() and not r.startswith("#")]
    for meno in (hr_stats.ROZPRACOVANA_MENO, hr_stats.ROZPRACOVANA_MENO + ".tmp"):
        assert any(fnmatch.fnmatch(meno, v) for v in vzory), meno
