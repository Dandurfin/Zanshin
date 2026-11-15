# -*- coding: utf-8 -*-
"""Data hraca (0.2.2, davka 4): zmazanie jednej relacie v Historii, "Zmazat
historiu" s exportom vopred a vypnute pocas sledovania, relacia, ktoru sa
nepodarilo ulozit (hr_session_pending.json), priecinok s datami a strop
historie pri importe. Len syntetické data v tmp priecinku."""
import json
import os
import time
import types

import app as app_mod
import app_data
import data_io
import hr_stats
import measure
from i18n import tr
from _zdroj_appky import zdroj_metody, zdroj_suboru

import test_022b_data_vypnutie as vypnutie


def _relacia(started, minut=20, **k):
    s = {"started": float(started), "duration_s": minut * 60.0, "samples": minut * 30,
         "avg_bpm": 80, "max_bpm": 101, "min_bpm": 64, "peak_stress": 40}
    s.update(k)
    return s


def _zapis(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def _citaj(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _stub(tmp_path):
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = vypnutie._Root()
    a.pal = {}
    a.denn = []
    a.log = a.denn.append
    a.log_threadsafe = a.denn.append
    a.hr_sessions_path = str(tmp_path / "hr_sessions.json")
    a.hr_windows_path = str(tmp_path / "hr_windows.json")
    a._hr_session_open = False
    a.poznamky = []
    a._data_note = a.poznamky.append
    a.prekreslene = []
    a._refresh_history_page = lambda: a.prekreslene.append(True)
    a.analyzy = []
    a.run_hr_analysis = lambda *_a: a.analyzy.append(True)
    return a


# --------------------------------------------------------------------------
# Zmazat tuto relaciu (detail v Historii)
# --------------------------------------------------------------------------

def test_delete_session_zmaze_len_jednu_relaciu(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    _zapis(cesta, [_relacia(1.8e9), _relacia(1.8e9 + 86400), _relacia(1.8e9 + 2 * 86400)])
    assert hr_stats.delete_session(cesta, 1.8e9 + 86400) is True
    assert [s["started"] for s in _citaj(cesta)] == [1.8e9, 1.8e9 + 2 * 86400]
    assert hr_stats.delete_session(cesta, 1.7e9) is False, "neexistujuca"


def test_necitatelna_historia_sa_pri_mazani_neprepise(tmp_path):
    cesta = str(tmp_path / "hr_sessions.json")
    with open(cesta, "w", encoding="utf-8") as fh:
        fh.write("{pokazene")
    assert hr_stats.delete_session(cesta, 1.8e9, log=lambda *_a: None) is False
    with open(cesta, encoding="utf-8") as fh:
        assert fh.read() == "{pokazene"


def test_zmazanie_relacie_s_potvrdenim_okna_aj_postrehy(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    ciel = _relacia(1.8e9 + 3600, minut=14 * 60)
    _zapis(a.hr_sessions_path, [_relacia(1.8e9), ciel])
    _zapis(a.hr_windows_path, [{"session_started": ciel["started"], "ts": 1.0},
                               {"session_started": 1.8e9, "ts": 2.0}])
    otazky = []

    def confirm(owner, pal, title, text, ok_label, cancel_label, danger=False):
        otazky.append((title, text, ok_label, cancel_label, danger))
        return True
    monkeypatch.setattr(app_data.ui_kit, "confirm", confirm)
    assert a.delete_history_session(dict(ciel)) is True
    (titul, text, ok, zrusit, danger), = otazky
    # datum v jazyku appky (0.2.2 davka 4b) - ten isty ako tabulka v Historii
    kedy = app_data.ui_kit.datum_text(ciel["started"], cas=True)
    assert titul == tr("history.delete_session.title")
    assert text == tr("history.delete_session.body", date=kedy,
                      duration=a._fmt_dlzka(ciel["duration_s"]))
    assert ok == tr("history.delete_session.btn") and zrusit == tr("common.cancel")
    assert danger is True
    assert [s["started"] for s in _citaj(a.hr_sessions_path)] == [1.8e9]
    assert measure.load_windows(a.hr_windows_path) == [{"session_started": 1.8e9, "ts": 2.0}]
    assert a.analyzy == [True], "postrehy sa prepocitaju ako tlacidlom Prepocitat"
    assert a.prekreslene and a.history_detail_index is None
    assert a.denn[-1] == tr("log.session_deleted", date=kedy)


def test_zrusene_potvrdenie_nic_nezmaze(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    _zapis(a.hr_sessions_path, [_relacia(1.8e9)])
    monkeypatch.setattr(app_data.ui_kit, "confirm", lambda *x, **k: False)
    assert a.delete_history_session(_relacia(1.8e9)) is False
    assert len(_citaj(a.hr_sessions_path)) == 1 and a.analyzy == []


def test_prave_nahravanu_relaciu_zmazat_neponukne(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    a._hr_session_open = True
    a.hr_stats = types.SimpleNamespace(session_start=1.8e9)
    otazky = []
    monkeypatch.setattr(app_data.ui_kit, "confirm", lambda *x, **k: otazky.append(x))
    assert a.delete_history_session(_relacia(1.8e9)) is False
    assert otazky == []


def test_tlacidlo_je_v_detaile_a_nahravanu_vypne():
    zdroj = zdroj_suboru("app_history.py")
    assert 'tr("history.delete_session.btn"), kind="danger"' in zdroj
    detail = zdroj_metody("_refresh_history_detail")
    assert "self._je_nahravana_relacia(session)" in detail
    assert '"disabled"' in detail


# --------------------------------------------------------------------------
# Zmazat historiu: najprv export, pocas sledovania nie
# --------------------------------------------------------------------------

def _mazanie(tmp_path, monkeypatch, volby):
    a = _stub(tmp_path)
    monkeypatch.setattr(app_data, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app_data, "legacy_data_dirs", lambda: [])
    a.exporty = []
    a.export_all_json = lambda: a.exporty.append(True)
    otazky = []

    def choose(owner, pal, title, text, choices, cancel=None, default=None):
        otazky.append((choices, cancel, default))
        return volby.pop(0)
    monkeypatch.setattr(app_data.ui_kit, "choose", choose)
    zmazane = []
    monkeypatch.setattr(app_data.data_io, "delete_all",
                        lambda *x, **k: zmazane.append(True) or 4)
    return a, otazky, zmazane


def test_najprv_export_potom_sa_otazka_vrati(tmp_path, monkeypatch):
    a, otazky, zmazane = _mazanie(tmp_path, monkeypatch, ["export", "delete"])
    a.delete_history()
    assert a.exporty == [True] and zmazane == [True]
    assert len(otazky) == 2
    volby, zrusit, predvolena = otazky[0]
    assert [v[0] for v in volby] == ["delete", "export", "cancel"]
    assert volby[0] == ("delete", tr("data.delete.btn"), "danger")
    assert volby[1][1] == tr("data.delete.export_first")
    assert zrusit == "cancel" and predvolena == "cancel", "fokus a Enter na Zrusit"
    assert a.poznamky[-1] == tr("data.delete.done", n=4)


def test_zrusit_nic_nezmaze(tmp_path, monkeypatch):
    a, _otazky, zmazane = _mazanie(tmp_path, monkeypatch, ["cancel"])
    a.delete_history()
    assert zmazane == [] and a.exporty == []


def test_pocas_sledovania_sa_historia_nezmaze(tmp_path, monkeypatch):
    a, otazky, zmazane = _mazanie(tmp_path, monkeypatch, ["delete"])
    a._hr_session_open = True
    a.delete_history()
    assert otazky == [] and zmazane == []
    assert a.poznamky == [tr("data.delete.stop_first")]


class _Widget:
    def __init__(self):
        self.stav, self.text, self.zabaleny = "normal", "", ""
        self.master = object()

    def configure(self, **k):
        self.stav = k.get("state", self.stav)
        self.text = k.get("text", self.text)

    def winfo_manager(self):
        return self.zabaleny

    def pack(self, **_k):
        self.zabaleny = "pack"

    def pack_forget(self):
        self.zabaleny = ""


def test_tlacidlo_zmazat_je_pocas_relacie_vypnute_s_dovodom(tmp_path):
    a = _stub(tmp_path)
    a.data_delete_btn, a.data_delete_reason = _Widget(), _Widget()
    a._hr_session_open = True
    a._refresh_data_delete_state()
    assert a.data_delete_btn.stav == "disabled"
    assert a.data_delete_reason.text == tr("data.delete.stop_first")
    assert a.data_delete_reason.zabaleny == "pack"
    a._hr_session_open = False
    a._refresh_data_delete_state()
    assert a.data_delete_btn.stav == "normal" and a.data_delete_reason.zabaleny == ""


def test_otvorenie_a_zatvorenie_relacie_obnovi_tlacidlo():
    assert "_refresh_data_delete_state" in zdroj_metody("_open_hr_session")
    assert '_ak_vies(self, "_refresh_data_delete_state")' in zdroj_metody("_close_hr_session")


def test_mazanie_zmaze_aj_neulozene_relacie():
    assert ("data.delete.pending_session", hr_stats.CAKAJUCA_MENO) in data_io.MAZATELNE


# --------------------------------------------------------------------------
# Priecinok s datami a strop historie pri importe
# --------------------------------------------------------------------------

def test_otvorit_priecinok_s_datami(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    otvorene = []
    monkeypatch.setattr(app_data.os, "startfile", otvorene.append, raising=False)
    a.open_data_folder()
    assert otvorene == [app_data.DATA_DIR] and a.poznamky == []

    def zle(_p):
        raise OSError("explorer nejde")
    monkeypatch.setattr(app_data.os, "startfile", zle, raising=False)
    a.open_data_folder()
    assert a.poznamky == [tr("data.open_folder.failed")]
    assert "data.open_folder.btn" in zdroj_metody("_build_data_panel")


def test_import_povie_kolko_relacii_odrezal_strop(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    moje = [_relacia(1.80e9 + i * 86400) for i in range(3)]
    _zapis(a.hr_sessions_path, moje)
    cudzie = [_relacia(1.81e9 + i * 86400) for i in range(3)]
    monkeypatch.setattr(app_data.hr_stats, "MAX_SESSIONS", 4)
    a._history_cache = (0.0, None)
    a._zapis_import(cudzie, [], False)
    assert len(_citaj(a.hr_sessions_path)) == 4
    sprava = a.poznamky[-1]
    assert tr("data.import.limit", max=4, n=2) in sprava
    assert tr("data.import.backup_where") in sprava


def test_vysledok_importu_rata_vypadnute():
    moje = [_relacia(1.80e9 + i) for i in range(3)]
    cudzie = [_relacia(1.81e9 + i) for i in range(2)]
    info = {}
    relacie, _o, n, _no = data_io.vysledok_importu(moje, [], cudzie, [], False,
                                                   max_s=4, info=info)
    assert len(relacie) == 4 and n == 2
    assert info == {"vypadlo": 1, "vypadlo_vlastnych": 1}
    info = {}
    data_io.vysledok_importu(moje, [], cudzie, [], False, max_s=10, info=info)
    assert info["vypadlo"] == 0


# --------------------------------------------------------------------------
# Relacia, ktoru sa nepodarilo ulozit
# --------------------------------------------------------------------------

def test_chyba_zapisu_relaciu_odlozi_povie_a_ukaze_oznam(tmp_path, monkeypatch):
    a = vypnutie._appka(tmp_path)
    a.pal = {}
    oznamy = []
    monkeypatch.setattr(app_data.ui_kit, "notify",
                        lambda *x, **k: oznamy.append((x, k)))

    def plny_disk(path, summary, log=None):
        log("HR: session log failed: [Errno 28] No space left on device: "
            "'C:\\\\Users\\\\hrac\\\\AppData\\\\Roaming\\\\Zanshin\\\\hr_sessions.json'")
        return False
    monkeypatch.setattr(app_data.hr_stats, "save_session", plny_disk)
    a._close_hr_session()
    cakajuce = hr_stats.nacitaj_cakajuce(a.hr_sessions_path)
    assert len(cakajuce) == 1 and cakajuce[0]["duration_s"] >= 899
    riadok = a.denn[-1]
    assert riadok.startswith(tr("log.hr_session_save_failed", err="X").split("(")[0])
    assert "hrac" not in riadok and "hr_sessions.json" in riadok, "bez cesty s menom uctu"
    assert a.dotazniky == [], "neulozena relacia dotaznik neotvori"
    # oznam v okne appky (nie systemovy), az ked sa slucka dostane k slovu
    (_ms, ukaz), = a.root.ulohy.values()
    ukaz()
    (args, kwargs), = oznamy
    assert args[2] == tr("session.save_failed.title") and args[3] == riadok


def test_pri_ukonceni_bez_oznamu(tmp_path, monkeypatch):
    a = vypnutie._appka(tmp_path)
    a._zatvara_sa = True
    monkeypatch.setattr(app_data.hr_stats, "save_session", lambda *x, **k: False)
    a._close_hr_session()
    assert hr_stats.nacitaj_cakajuce(a.hr_sessions_path)
    assert a.root.ulohy == {}, "pri ukoncovani by okno zablokovalo koniec"


def test_kratka_relacia_bez_tepu_povie_preco_sa_neulozila(tmp_path):
    a = _stub(tmp_path)
    a._kratka_relacia_bez_tepu({"duration_s": 1800, "samples": 3})
    assert a.denn == [tr("log.hr_session_no_data")]
    a._kratka_relacia_bez_tepu({"duration_s": 20, "samples": 3})
    assert len(a.denn) == 1, "pod minutu nie je relacia - nic sa nehovori"


def test_dalsi_start_doplni_cakajucu_raz_a_subor_zmaze(tmp_path):
    a = _stub(tmp_path)
    teraz = time.time()
    s = _relacia(teraz - 7200)
    assert hr_stats.zapis_cakajucu(a.hr_sessions_path, s)
    assert hr_stats.zapis_cakajucu(a.hr_sessions_path, dict(s)), "ta ista sa neodlozi dvakrat"
    assert len(hr_stats.nacitaj_cakajuce(a.hr_sessions_path)) == 1
    doplnene = a._dopln_cakajuce_relacie()
    assert len(doplnene) == 1
    historia = _citaj(a.hr_sessions_path)
    assert len(historia) == 1 and historia[0]["recovered"] is True, "z obnovenej sa neuci"
    assert not os.path.exists(hr_stats.cesta_cakajucej(a.hr_sessions_path))
    kedy = app_data.ui_kit.datum_text(s["started"], cas=True)
    assert a.denn == [tr("log.hr_session_pending_saved", time=kedy)]
    # uz v historii (napr. aj z kontrolneho bodu): neduplikuje sa
    hr_stats.zapis_cakajucu(a.hr_sessions_path, dict(s))
    assert a._dopln_cakajuce_relacie() == []
    assert len(_citaj(a.hr_sessions_path)) == 1
    assert not os.path.exists(hr_stats.cesta_cakajucej(a.hr_sessions_path))


def test_cakajuca_sa_zmaze_az_po_uspesnom_zapise(tmp_path, monkeypatch):
    a = _stub(tmp_path)
    hr_stats.zapis_cakajucu(a.hr_sessions_path, _relacia(time.time() - 7200))
    monkeypatch.setattr(hr_stats, "save_session", lambda *x, **k: False)
    assert a._dopln_cakajuce_relacie() == []
    assert len(hr_stats.nacitaj_cakajuce(a.hr_sessions_path)) == 1


def test_start_doplni_cakajuce_pred_kontrolnym_bodom():
    obnova = zdroj_metody("_obnov_rozpracovanu_relaciu")
    assert obnova.index('"_dopln_cakajuce_relacie"') < obnova.index("obnov_rozpracovanu(")
    assert hr_stats.cesta_cakajucej("x/hr_sessions.json").endswith(
        os.path.join("x", "hr_session_pending.json"))


def test_cesty_v_chybe_sa_skryju():
    assert app_data.bez_ciest(
        "[Errno 13] Permission denied: 'C:\\Users\\hrac\\AppData\\hr_sessions.json'") == (
        "[Errno 13] Permission denied: 'hr_sessions.json'")
