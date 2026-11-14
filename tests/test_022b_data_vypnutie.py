# -*- coding: utf-8 -*-
"""Relacia prezije vypnutie PC, pad aj Spravcu uloh (0.2.2).

Do 0.2.2 sa relacia zapisala LEN v `_close_hr_session` a ten volal len
`stop_listening`, vypnutie senzora a `_quit` (WM_DELETE_WINDOW). Vypnutie
Windows, pad, ukoncenie cez Spravcu uloh alebo `build.bat` tak zahodili cely
vecer. Strazi sa:

  * WM_SAVE_YOURSELF (Tk tak na Windows hlasi WM_QUERYENDSESSION) ulozi
    relaciu BEZ dotaznika a ulozi nastavenia; dvakrat aj pocas `_quit` je to
    bezpecne a zrusene vypnutie meranie znova rozbehne,
  * kontrolny bod: suhrn otvorenej relacie sa atomicky zapisuje do
    hr_session_open.json, normalne zatvorenie ho zmaze,
  * pri starte sa kontrolny bod prida do historie RAZ (`recovered`), nie
    dvakrat, a nevierohodny sa zahodi,
  * obnovena relacia nevstupuje do ucenia prahov (`ciste_relacie`),
  * "Zmazat historiu" zmaze aj kontrolny bod.

Vsetko v tmp priecinku - %APPDATA%\\Zanshin sa nedotyka nic.
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
    """`root.after` bez Tk: uloha sa spusti, az ked ju test pusti."""

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
    """Skutocny `HeartStats` s relaciou, ktoru `save_session` prijme."""
    teraz = time.time() if teraz is None else teraz
    st = hr_stats.HeartStats(critical_bpm=110)
    st.session_start = teraz - minut * 60.0
    for i in range(int(minut * 30)):
        st.add(70 + (i % 12), ts=st.session_start + i * 2.0)
    return st


def _appka(tmp_path, minut=15):
    """Skutocne `_close_hr_session`, `_suhrn_relacie` a ochrana relacie na
    `DandurfApp` bez Tk. Dotaznik, promocia, analyza a nastavenia sa len
    zaznamenaju."""
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
# (a) vypnutie Windows
# --------------------------------------------------------------------------

def test_protokol_vypnutia_je_zaregistrovany_vedla_zatvorenia_okna():
    init = zdroj_metody("__init__")
    assert 'self.root.protocol("WM_DELETE_WINDOW", self.on_close)' in init
    assert ('self.root.protocol("WM_SAVE_YOURSELF", self._pri_vypinani_windows)'
            in init)


@pytest.mark.skipif(sys.platform != "win32", reason="WM_QUERYENDSESSION je vec Windows")
def test_tk_na_windows_hlasi_vypnutie_ako_wm_save_yourself():
    """Overenie predpokladu, na ktorom oprava stoji: Tk z WM_QUERYENDSESSION
    spravi WM_SAVE_YOURSELF - aj pri bezramovom okne schovanom v liste (tak
    appka byva pri vypinani PC). Sprava sa POSIELA vlastnemu oknu, takze sa
    nic nevypina; spracuje ju slucka Tk ako pri skutocnom vypnuti."""
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
        # Vlastny WinDLL, nie `ctypes.windll.user32`: argtypes na zdielanom
        # objekte by platili pre cely beh testov (aj pre ine moduly).
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
    # Windows caka par sekund - ziadny dotaznik (zahodil by sa s procesom),
    # promocia ani analyza v pozadi
    assert a.dotazniky == [] and a.promocie == [] and a.analyzy == []
    # riadok "Relacia ulozena" do dennika ide aj tak
    assert len(a.denn) == 1


def test_vypnutie_dvakrat_ulozi_relaciu_raz(tmp_path):
    a = _appka(tmp_path)
    a._pri_vypinani_windows()
    a._pri_vypinani_windows()
    assert len(_historia(a)) == 1
    # naplanovany navrat po zrusenom vypnuti je len jeden (stary sa zrusi)
    assert len(a.root.ulohy) == 1


def test_vypnutie_pocas_quit_nic_nezopakuje_ani_neotvori(tmp_path):
    """`_quit` relaciu uz zavrel (a caka na dotaznik) - vypnutie ulozi len
    nastavenia a relaciu po nom neotvori."""
    a = _appka(tmp_path)
    a._close_hr_session()                 # ako `_quit` -> `stop_listening`
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
    # siete sa nedotyka - prijem bezi dalej (ako `start_listening`)
    assert a.otvorene == [{"prepoj": False, "meria": True}]


def test_zrusene_vypnutie_bez_pocuvania_nic_neotvori(tmp_path):
    a = _appka(tmp_path)
    a.listening = False
    a._pri_vypinani_windows()
    for _ms, fn in list(a.root.ulohy.values()):
        fn()
    assert a.otvorene == []


def test_vypnutie_prezije_chybu_pri_ukladani(tmp_path):
    """Pad ukladania relacie nesmie zastavit ulozenie nastaveni."""
    a = _appka(tmp_path)
    a._suhrn_relacie = lambda: (_ for _ in ()).throw(RuntimeError("pad"))
    a._pri_vypinani_windows()
    assert a.nastavenia == [True]
    assert a._vypnutie_bezi is False


# --------------------------------------------------------------------------
# (b) kontrolny bod
# --------------------------------------------------------------------------

def test_suhrn_relacie_nema_vedlajsie_ucinky(tmp_path):
    """Kontrolny bod bezi uprostred hrania - nesmie nic vynulovat ani
    pripocitat (inak by zatvorenie ulozilo ine cisla)."""
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
    """Zapis ide cez .tmp + os.replace - pad uprostred necha stary bod cely."""
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
    b = _appka(tmp_path, minut=0.5)       # pod minutu - neulozila by sa ani tak
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
    """Plny disk pri zatvoreni: kontrolny bod je jedina kopia - ostava."""
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
    assert len(a.root.ulohy) == 1          # dalsi tik naplanovany
    (_ms, fn2), = a.root.ulohy.values()
    a.root.ulohy.clear()
    a._quit_bezi = True
    fn2()
    assert a.root.ulohy == {}


def test_kontrolny_bod_sa_spusta_pri_starte_po_obnove():
    init = zdroj_metody("__init__")
    obnova = init.index("self._obnov_rozpracovanu_relaciu()")
    assert obnova < init.index("self._naplanuj_rozpracovanu_relaciu()")
    # obnova skor, nez senzor otvori novu relaciu
    assert obnova < init.index("self.start_heart_rate_monitor()")


# --------------------------------------------------------------------------
# (b) obnova pri starte
# --------------------------------------------------------------------------

def _pad_s_kontrolnym_bodom(tmp_path):
    """Relacia s kontrolnym bodom a potom "pad" - zatvorenie neprislo."""
    a = _appka(tmp_path)
    assert a._zapis_rozpracovanu_relaciu()
    return a


def test_obnova_prida_relaciu_raz_a_oznaci_ju(tmp_path):
    a = _pad_s_kontrolnym_bodom(tmp_path)
    b = _appka(tmp_path)                   # dalsi start
    obnovena = b._obnov_rozpracovanu_relaciu()
    assert obnovena is not None and obnovena["recovered"] is True
    historia = _historia(b)
    assert len(historia) == 1 and historia[0]["recovered"] is True
    assert historia[0]["started"] == a.hr_stats.session_start
    assert not os.path.exists(_checkpoint(b))
    assert len(b.denn) == 1                # jeden riadok v denniku
    # dalsi start uz nic neobnovi
    assert b._obnov_rozpracovanu_relaciu() is None
    assert len(_historia(b)) == 1


def test_obnova_nezdvoji_relaciu_ktora_sa_stihla_ulozit(tmp_path):
    """Pad AZ po ulozeni relacie, ale pred zmazanim kontrolneho bodu."""
    a = _pad_s_kontrolnym_bodom(tmp_path)
    assert hr_stats.save_session(a.hr_sessions_path, a._suhrn_relacie())
    assert os.path.exists(_checkpoint(a))
    assert hr_stats.obnov_rozpracovanu(a.hr_sessions_path) is None
    assert len(_historia(a)) == 1
    assert not os.path.exists(_checkpoint(a))


@pytest.mark.parametrize("pokazit", [
    lambda s: s.update(duration_s=30.0),                      # pod minutu
    lambda s: s.update(samples=3),                            # bez dat
    lambda s: s.update(started=None),                         # bez casu
    lambda s: s.update(started=12345.0),                      # rok 1970
    lambda s: s.update(started=time.time() + 86400.0),        # v buducnosti
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
    """Rozhodnutie 0.2.2: obnovena relacia je v Historii, ale prahy, kriticky
    tep ani dlhodoba zakladna sa z nej neucia (chyba koniec aj dotaznik)."""
    s = dict(_appka(tmp_path)._suhrn_relacie(), duration_s=1800.0,
             baseline_bpm=62)
    obnovena = dict(s, recovered=True)
    assert hr_stats.ciste_relacie([s]) == [s]
    assert hr_stats.ciste_relacie([obnovena]) == []
    # ale vlastna relacia hraca to ostava (nie je cudzia ako import)
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
    # anglictina nie je len skopirovana do inych jazykov
    en = i18n.STRINGS["log.hr_session_recovered"]["en"]
    for jazyk in ("ja", "de", "cs", "bg"):
        assert i18n.STRINGS["log.hr_session_recovered"][jazyk] != en, jazyk


def test_gui_nastroje_zalohuju_kontrolny_bod_aj_zalohu_nastaveni():
    """gui_harness_auto a gui_screenshots bezia nad datami vedla main.py a na
    konci vracaju historiu spred behu. Appka pri ich starte kontrolny bod
    prida do historie a ZMAZE - bez jeho zalohy by ho nastroj spotreboval a
    relacia z padnutej appky by zmizla s vratenou historiou."""
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
    """Zdravotne data - kontrolny bod nesmie skoncit v gite."""
    import fnmatch
    vzory = [r.strip() for r in zdroj_suboru(".gitignore").splitlines()
             if r.strip() and not r.startswith("#")]
    for meno in (hr_stats.ROZPRACOVANA_MENO, hr_stats.ROZPRACOVANA_MENO + ".tmp"):
        assert any(fnmatch.fnmatch(meno, v) for v in vzory), meno
