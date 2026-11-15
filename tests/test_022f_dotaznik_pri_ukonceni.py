# -*- coding: utf-8 -*-
"""Dotaznik po relacii pri kazdom ukonceni a vypnuti Windows (0.2.2 davka 4b).

Do davky 4 ulozilo dotknute odpovede len druhe "Ukoncit" pocas dotaznika
zatvarania (`_dotaznik_pri_zatvarani`). Dotaznik otvoreny beznym Stop, ktory
este visel, ked hrac ukoncil appku z listy alebo sa vypinal Windows
(WM_SAVE_YOURSELF), zanikol s `root.destroy()` aj s odpovedami.

Pravidlo zadavatela teraz plati pri KAZDOM ukonceni: dotknute odpovede sa
ulozia ako "Ulozit", nedotknuty dotaznik sa zavrie ako "Preskocit", do
dennika ide jeden riadok. Okno s chybou ulozenia sa pri tom neotvara.
Vsetky data su vymyslene.
"""
import types

import app as app_mod
import app_data
import hr_stats
import ui_dialogs
import ui_kit
from i18n import tr
from _zdroj_appky import zdroj_metody


class _Top:
    def __init__(self, zije=True):
        self.zije = zije

    def winfo_exists(self):
        return self.zije


class _Dotaznik:
    """Atrapa SessionEndDialog: zaznamenava, co s nou appka spravila."""

    def __init__(self, poradie, vyplneny, ok=True, zije=True, meno="dotaznik"):
        self.poradie, self.vyplneny, self.ok = poradie, vyplneny, ok
        self.meno = meno
        self.top = _Top(zije)

    def bolo_vyplnene(self):
        return self.vyplneny

    def confirm(self):
        self.poradie.append(self.meno + ":ulozit")
        self.top.zije = False
        return self.ok

    def close(self):
        self.poradie.append(self.meno + ":preskocit")
        self.top.zije = False


class _Root:
    def __init__(self, poradie):
        self.poradie = poradie

    def after(self, _ms, _fn):
        return "job"

    def after_cancel(self, _job):
        pass

    def destroy(self):
        self.poradie.append("destroy")


def _appka(poradie):
    """DandurfApp bez Tk: kroky ukoncenia sa len zapisu do `poradie`."""
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.root = _Root(poradie)
    a.denn = []
    a.log = a.denn.append
    a.stop_listening = lambda: poradie.append("stop_listening")
    a._close_hr_session = lambda **_k: poradie.append("close_hr_session")
    nic = types.SimpleNamespace(stop=lambda: None, stop_all=lambda: None)
    a.hud = a.overlay_manager = a.gamepad = a.heart_rate_monitor = a.worker = nic
    a.stop_snooze_hotkey = lambda: None
    a.game_watcher = None
    a.tray_icon = None
    a.save_settings = lambda: poradie.append("save_settings")
    return a


def test_prve_ukoncenie_ulozi_dotknuty_dotaznik_z_bezneho_stop():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, vyplneny=True)]
    a._quit()
    # dotaznik sa dokonci PRED zastavenim (novy dotaznik sa neotvori nad nim)
    assert poradie[:2] == ["dotaznik:ulozit", "stop_listening"], poradie
    assert poradie[-1] == "destroy"
    assert a.denn == [tr("log.quit_questionnaire_saved")]
    assert a._otvorene_dotazniky == []


def test_prve_ukoncenie_zavrie_nedotknuty_dotaznik_ako_preskocit():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, vyplneny=False)]
    a._quit()
    assert poradie[0] == "dotaznik:preskocit", poradie
    assert a.denn == [tr("log.quit_questionnaire_skipped")]


def test_zavrety_dotaznik_sa_preskoci_a_bez_dotaznika_nic_navyse():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, vyplneny=True, zije=False)]
    a._quit()
    assert poradie[0] == "stop_listening", poradie
    assert a.denn == []
    # appka bez jedineho dotaznika (atribut ani nevznikol)
    poradie2 = []
    b = _appka(poradie2)
    b._quit()
    assert poradie2[0] == "stop_listening" and b.denn == []


def test_dva_otvorene_dotazniky_kazdy_jeden_riadok():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, True, meno="a"),
                             _Dotaznik(poradie, False, meno="b")]
    assert a._dokonci_otvorene_dotazniky() == 2
    assert poradie == ["a:ulozit", "b:preskocit"]
    assert a.denn == [tr("log.quit_questionnaire_saved"),
                      tr("log.quit_questionnaire_skipped")]


def test_neuspesne_ulozenie_da_do_dennika_chybu_nie_ulozene():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, vyplneny=True, ok=False)]
    a._dokonci_otvorene_dotazniky()
    assert a.denn == [tr("session.context.save_failed")]
    assert a._dotaznik_bez_okna_chyby is False


def test_vypnutie_windows_ulozi_dotaznik_pred_relaciou():
    poradie = []
    a = _appka(poradie)
    a._otvorene_dotazniky = [_Dotaznik(poradie, vyplneny=True)]
    a._pri_vypinani_windows()
    assert poradie[:3] == ["dotaznik:ulozit", "close_hr_session", "save_settings"], poradie
    assert a.denn == [tr("log.quit_questionnaire_saved")]


def test_vypnutie_windows_zavrie_aj_dotaznik_na_ktory_caka_quit():
    """`_quit` caka vo `wait_window` na dotaznik zatvarania; ten je tiez
    v `_otvorene_dotazniky`, takze ho vypnutie Windows dokonci tiez."""
    poradie = []
    a = _appka(poradie)
    d = _Dotaznik(poradie, vyplneny=False)
    a._quit_bezi = True
    a._dotaznik_pri_zatvarani = d
    a._otvorene_dotazniky = [d]
    a._pri_vypinani_windows()
    assert poradie[0] == "dotaznik:preskocit"
    assert a.denn == [tr("log.quit_questionnaire_skipped")]


def test_pri_ukonceni_sa_okno_s_chybou_neotvori(monkeypatch):
    okna = []
    monkeypatch.setattr(ui_kit, "notify", lambda *a, **k: okna.append(a))
    monkeypatch.setattr(hr_stats, "attach_context", lambda *a, **k: False)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.hr_sessions_path = "nikde.json"
    a.log_threadsafe = lambda _m: None
    a.root = a.pal = None
    a._dotaznik_bez_okna_chyby = True
    assert a.save_session_context({"started": 1.0}, []) is False
    assert okna == []
    # bezne "Ulozit" mimo ukoncenia okno s chybou ukaze ako doteraz
    a._dotaznik_bez_okna_chyby = False
    assert a.save_session_context({"started": 1.0}, []) is False
    assert len(okna) == 1


def test_confirm_vrati_vysledok_ulozenia():
    d = ui_dialogs.SessionEndDialog.__new__(ui_dialogs.SessionEndDialog)
    d.vybrane, d._body_sel = {"tilt"}, set()
    d.activity = d.sleep = d.felt_load = d.valence = d.cue_verdict = None
    d.summary, d.setup, d.note_box = {"started": 1.0}, False, None
    zavrete = []
    d.close = lambda: zavrete.append(True)
    for vysledok in (True, False):
        d.app = types.SimpleNamespace(save_session_context=lambda *a, _v=vysledok, **k: _v)
        assert d.confirm() is vysledok
    assert zavrete == [True, True]


def test_kazdy_otvoreny_dotaznik_si_appka_zapamata(monkeypatch):
    vytvorene = []

    class _Falosny:
        def __init__(self, app, summary, cues=0, silent=0):
            self.top = _Top()
            vytvorene.append(self)

    monkeypatch.setattr(app_data, "SessionEndDialog", _Falosny)
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a._cue_log = []
    a._zatvara_sa = False
    a._ask_session_context({"started": 1.0})
    a._ask_session_context({"started": 2.0})
    assert a._otvorene_dotazniky == vytvorene and len(vytvorene) == 2
    # pri beznom Stop sa na dotaznik neceka a `_dotaznik_pri_zatvarani` ostava prazdny
    assert getattr(a, "_dotaznik_pri_zatvarani", None) is None
    # zavrete okno z dlhsieho behu sa pri dalsom dotazniku zahodi
    vytvorene[0].top.zije = False
    a._ask_session_context({"started": 3.0})
    assert a._otvorene_dotazniky == vytvorene[1:]


def test_druhe_ukoncenie_pouziva_to_iste_pravidlo():
    kod = zdroj_metody("_quit")
    assert "self._dokonci_dotaznik(dotaznik)" in kod
    assert kod.index("self._dokonci_otvorene_dotazniky()") < kod.index(
        'krok("stop_listening"')
    vypnutie = zdroj_metody("_pri_vypinani_windows")
    assert vypnutie.index("self._dokonci_otvorene_dotazniky()") < vypnutie.index(
        "self._close_hr_session(pri_vypnuti=True)")
