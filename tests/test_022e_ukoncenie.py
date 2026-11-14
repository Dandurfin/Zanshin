# -*- coding: utf-8 -*-
"""Druhe "Ukoncit" nad dotaznikom a casovac pokusov o vazbu (0.2.2, davka 4).

* Druhe "Ukoncit" (lista) pocas otvoreneho dotaznika: ked sa hrac dotkol
  aspon jednej odpovede, ulozia sa (ako "Ulozit") a appka skonci; ked nie,
  dotaznik sa zavrie ako "Preskocit". Jeden riadok do dennika.
* `_hr_retry_job` (pokus po obsadenom porte) sa rusi pri vypnuti senzora,
  novom behu (iny port), chybe vazby aj ukonceni a nikdy nebezia dva."""
import types

import app as app_mod
import app_session
import ui_dialogs
from i18n import tr
from _zdroj_appky import zdroj_metody

import test_022b_instance_port as port


class _Dotaznik:
    def __init__(self, vyplneny, zlyha=False):
        self.vyplneny, self.zlyha = vyplneny, zlyha
        self.volane = []

    def bolo_vyplnene(self):
        return self.vyplneny

    def confirm(self):
        self.volane.append("confirm")
        if self.zlyha:
            raise OSError("disk")

    def close(self):
        self.volane.append("close")


def _appka(dotaznik):
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a._quit_bezi = True
    a._dotaznik_pri_zatvarani = dotaznik
    a.denn = []
    a.log = a.denn.append
    return a


def test_vyplneny_dotaznik_sa_pri_druhom_ukonceni_ulozi():
    d = _Dotaznik(vyplneny=True)
    a = _appka(d)
    a._quit()
    assert d.volane == ["confirm"]
    assert a.denn == [tr("log.quit_questionnaire_saved")]
    assert a._quit_bezi is True, "ukoncenie dokonci prvy `_quit`"


def test_prazdny_dotaznik_sa_zavrie_ako_preskocit():
    d = _Dotaznik(vyplneny=False)
    a = _appka(d)
    a._quit()
    assert d.volane == ["close"]
    assert a.denn == [tr("log.quit_questionnaire_skipped")]


def test_zlyhane_ulozenie_dotaznik_aj_tak_zavrie():
    d = _Dotaznik(vyplneny=True, zlyha=True)
    _appka(d)._quit()
    assert d.volane == ["confirm", "close"], "prvy `_quit` na dotaznik caka"


def test_atrapa_bez_stavu_sa_bere_ako_prazdna():
    d = types.SimpleNamespace(volane=[])
    d.close = lambda: d.volane.append("close")
    _appka(d)._quit()
    assert d.volane == ["close"]


class _Text:
    def __init__(self, text=""):
        self.text = text

    def get(self, *_a):
        return self.text


def _dotaznik(**k):
    d = ui_dialogs.SessionEndDialog.__new__(ui_dialogs.SessionEndDialog)
    d.vybrane, d._body_sel = set(), set()
    d.activity = d.sleep = d.felt_load = d.valence = d.cue_verdict = None
    d.summary = {"setup": False}
    d.setup = False
    d.note_box = _Text()
    d.__dict__.update(k)
    return d


def test_bolo_vyplnene_vidi_kazdu_odpoved():
    assert _dotaznik().bolo_vyplnene() is False
    assert _dotaznik(felt_load=6).bolo_vyplnene() is True
    assert _dotaznik(vybrane={"tilt"}).bolo_vyplnene() is True
    assert _dotaznik(cue_verdict="helped").bolo_vyplnene() is True
    assert _dotaznik(note_box=_Text("  dlhy den  \n")).bolo_vyplnene() is True
    assert _dotaznik(note_box=_Text("   \n")).bolo_vyplnene() is False
    # cip "len nastavovanie" predvyplneny appkou nie je odpoved - az klik
    assert _dotaznik(summary={"setup": True}, setup=True).bolo_vyplnene() is False
    assert _dotaznik(summary={"setup": True}, setup=False).bolo_vyplnene() is True


# --------------------------------------------------------------------------
# _hr_retry_job
# --------------------------------------------------------------------------

def test_zrusenie_pokusu_je_bezpecne():
    zrusene = []
    a = types.SimpleNamespace(_hr_retry_job="job-1",
                              root=types.SimpleNamespace(after_cancel=zrusene.append))
    assert app_session._zrus_pokus_o_vazbu(a) is True
    assert zrusene == ["job-1"] and a._hr_retry_job is None
    assert app_session._zrus_pokus_o_vazbu(a) is False
    assert zrusene == ["job-1"], "after_cancel(None) Tk odmietne - nevola sa"

    def zle(_j):
        raise RuntimeError("okno zaniklo")
    a = types.SimpleNamespace(_hr_retry_job="job-2",
                              root=types.SimpleNamespace(after_cancel=zle))
    assert app_session._zrus_pokus_o_vazbu(a) is True and a._hr_retry_job is None


class _Root:
    def __init__(self):
        self.ulohy, self.zrusene, self._n = {}, [], 0

    def after(self, ms, fn):
        self._n += 1
        self.ulohy["j%d" % self._n] = (ms, fn)
        return "j%d" % self._n

    def after_cancel(self, job):
        self.zrusene.append(job)
        self.ulohy.pop(job, None)


def test_obsadeny_port_nikdy_nenaplanuje_dva_pokusy():
    root = _Root()
    a = port._atrapa(root=root)
    port._stav(a, "busy", 4455)
    prvy = a._hr_retry_job
    assert list(root.ulohy) == [prvy]
    # dalsie "busy" skor, nez stary pokus dobehol (napr. dve spravy z vlakna)
    port._stav(a, "busy", 4455)
    assert root.zrusene == [prvy]
    assert list(root.ulohy) == [a._hr_retry_job] and a._hr_retry_job != prvy


def test_chyba_vazby_zrusi_cakajuci_pokus():
    root = _Root()
    a = port._atrapa(root=root)
    port._stav(a, "busy", 4455)
    port._stav(a, "error", "WinError 10049")
    assert root.ulohy == {} and a._hr_retry_job is None
    assert a.hr_monitoring_enabled is False


def test_vypnutie_senzora_zrusi_pokus():
    root = _Root()
    a = port._atrapa(root=root)
    port._stav(a, "busy", 4455)
    for meno, hodnota in (("heart_rate_monitor", types.SimpleNamespace(stop=lambda: None)),
                          ("_cancel_no_client_check", lambda: None),
                          ("hud", types.SimpleNamespace(set_connected=lambda _v: None)),
                          ("hr_stats", types.SimpleNamespace(clear_live=lambda: None))):
        setattr(a, meno, hodnota)
    port._D().stop_heart_rate_monitor(a)
    assert root.ulohy == {} and a._hr_retry_job is None and a._hr_bind_retries == 0


def test_zmena_portu_aj_ukoncenie_rusia_pokus():
    assert "_zrus_pokus_o_vazbu(self)" in zdroj_metody("start_heart_rate_monitor")
    assert "start_heart_rate_monitor()" in zdroj_metody("on_hr_config_change")
    quit_ = zdroj_metody("_quit")
    assert '"_hr_retry_job"' in quit_ and "after_cancel(job)" in quit_
    # `_open_hr_session` pokus uz nezahadzuje bez zrusenia
    assert "self._hr_retry_job = None" not in zdroj_metody("_open_hr_session")
