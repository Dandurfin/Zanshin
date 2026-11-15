# -*- coding: utf-8 -*-
"""Chyby prirodzeneho hlasu (0.2.2, davka 4): "skontroluj internet" len ked
naozaj nejde spojenie; odmietnutie Microsoftom (HTTP 401/403/429, odmietnuty
handshake) ma inu radu a ostatne vseobecnu vetu. Dennik povie, ako to skusit
znova, a v Nastaveniach -> Zvuk je "Skusit znova" - pocas sledovania sa na
siet aj tak nejde. Ziadna siet, vlastne triedy vynimiek."""
import socket
import threading
import types

import pytest

import app as app_mod
import app_audio
import audio_engine
from audio_engine import (EDGE_CHYBA_INA, EDGE_CHYBA_ODMIETNUTE, EDGE_CHYBA_OFFLINE,
                          druh_chyby_edge)
from i18n import tr

import test_021b_pregen_len_co_zaznie as pregen


class WSServerHandshakeError(Exception):
    def __init__(self, status):
        super().__init__(f"Invalid response status {status}")
        self.status = status


class ClientResponseError(Exception):
    def __init__(self, status):
        super().__init__(f"{status}")
        self.status = status


class ClientConnectorError(OSError):
    pass


class NoAudioReceived(Exception):
    pass


@pytest.mark.parametrize("exc, druh", [
    (WSServerHandshakeError(403), EDGE_CHYBA_ODMIETNUTE),
    (WSServerHandshakeError(503), EDGE_CHYBA_ODMIETNUTE),
    (ClientResponseError(401), EDGE_CHYBA_ODMIETNUTE),
    (ClientResponseError(429), EDGE_CHYBA_ODMIETNUTE),
    (ClientConnectorError("Cannot connect to host"), EDGE_CHYBA_OFFLINE),
    (socket.gaierror(11001, "getaddrinfo failed"), EDGE_CHYBA_OFFLINE),
    (TimeoutError(), EDGE_CHYBA_OFFLINE),
    (ConnectionResetError(), EDGE_CHYBA_OFFLINE),
    (ClientResponseError(500), EDGE_CHYBA_INA),
    (NoAudioReceived("No audio was received"), EDGE_CHYBA_INA),
    (RuntimeError("prazdny vystup"), EDGE_CHYBA_INA),
    (OSError(28, "No space left on device"), EDGE_CHYBA_INA),
    (None, EDGE_CHYBA_INA),
])
def test_druh_chyby(exc, druh):
    assert druh_chyby_edge(exc) == druh


def test_druh_hlada_aj_v_priciname():
    try:
        try:
            raise ConnectionRefusedError()
        except ConnectionRefusedError as vnutri:
            raise RuntimeError("edge-tts zlyhal") from vnutri
    except RuntimeError as exc:
        assert druh_chyby_edge(exc) == EDGE_CHYBA_OFFLINE


def test_hlavna_chyba_ma_prednost_odmietnutie():
    o, r, i = ((EDGE_CHYBA_OFFLINE, "o"), (EDGE_CHYBA_ODMIETNUTE, "r"), (EDGE_CHYBA_INA, "i"))
    assert app_audio.hlavna_chyba_edge([o, i, r]) == r
    assert app_audio.hlavna_chyba_edge([i, o]) == o
    assert app_audio.hlavna_chyba_edge([i]) == i
    assert app_audio.hlavna_chyba_edge([]) == (EDGE_CHYBA_INA, None), "bez info nie internet"


def test_cache_si_pamata_chybu_za_kazde_vlakno(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_engine, "TTS_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)

    class _Odmietne:
        def __init__(self, *a, **k):
            pass

        async def save(self, _tmp):
            raise WSServerHandshakeError(403)
    monkeypatch.setattr(audio_engine, "edge_tts",
                        types.SimpleNamespace(Communicate=_Odmietne), raising=False)
    cache = audio_engine.EdgeTTSCache(log=lambda *_a: None)
    assert cache.ensure("Nadychni sa", "sk-SK-ViktoriaNeural", 0) is None
    druh, exc = cache.posledna_chyba()
    assert druh == EDGE_CHYBA_ODMIETNUTE and isinstance(exc, WSServerHandshakeError)
    ine = []
    t = threading.Thread(target=lambda: ine.append(cache.posledna_chyba()))
    t.start()
    t.join()
    assert ine == [None], "ine vlakno chybu tohto nevidi"


class _Tlacidlo:
    def __init__(self):
        self.zabalene = ""

    def winfo_manager(self):
        return self.zabalene

    def pack(self, **_k):
        self.zabalene = "pack"

    def pack_forget(self):
        self.zabalene = ""


def _atrapa(monkeypatch, pocuva=False):
    a = pregen._atrapa(monkeypatch, pregen._tri(), pocuva=pocuva)
    a.denn = []
    a.log = a.denn.append
    a.edge_retry_btn = _Tlacidlo()
    a.edge_status_label = None
    D = app_mod.DandurfApp
    for meno in ("_edge_priprava_zlyhala", "_ukaz_skusit_hlas_znova", "skus_hlas_znova"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    return a


def _zlyha(a, chyba):
    a.edge_cache.ensure = lambda text, voice, rate, abort=None: None
    a.edge_cache.posledna_chyba = lambda: chyba
    a.pregenerate()
    pregen._dobehni(a)
    for fn in list(a.ui):
        fn()


def test_odmietnutie_povie_skus_neskor_alebo_windows(monkeypatch):
    a = _atrapa(monkeypatch)
    _zlyha(a, (EDGE_CHYBA_ODMIETNUTE, WSServerHandshakeError(403)))
    assert a.stavy[-1] == tr("edge.partial_refused", ok=0, total=3)
    assert a.edge_retry_btn.zabalene == "pack"
    # stranka, ktoru hrac naozaj vidi: Nastavenia → Zvuk (0.2.2 davka 4b)
    assert a.denn == [tr("log.edge_failed_refused",
                         page=tr("nav.nastavenia") + " → " + tr("nav.nastavenia_tabs.zvuk"),
                         retry=tr("common.retry"), cmd=tr("common.prepare_voices"))]
    assert "internet" not in a.stavy[-1]


def test_vypadok_siete_povie_internet_a_dennik_raz(monkeypatch):
    a = _atrapa(monkeypatch)
    _zlyha(a, (EDGE_CHYBA_OFFLINE, TimeoutError()))
    assert a.stavy[-1] == tr("edge.partial", ok=0, total=3)
    assert a.denn == [tr("log.edge_failed_offline",
                         page=tr("nav.nastavenia") + " → " + tr("nav.nastavenia_tabs.zvuk"),
                         retry=tr("common.retry"), cmd=tr("common.prepare_voices"))]
    a.ui.clear()
    _zlyha(a, (EDGE_CHYBA_OFFLINE, TimeoutError()))
    assert len(a.denn) == 1, "ta ista chyba dennik nezaplni"


def test_ina_chyba_vseobecna_veta_bez_cesty(monkeypatch):
    a = _atrapa(monkeypatch)
    _zlyha(a, (EDGE_CHYBA_INA, OSError("zapis zlyhal: 'C:\\Users\\hrac\\audio\\x.mp3'")))
    assert a.stavy[-1] == tr("edge.partial_other", ok=0, total=3)
    assert "hrac" not in a.denn[-1] and "x.mp3" in a.denn[-1]


def test_atrapa_bez_info_nehovori_o_internete(monkeypatch):
    a = _atrapa(monkeypatch)
    a.edge_cache.ensure = lambda text, voice, rate, abort=None: None
    a.pregenerate()
    pregen._dobehni(a)
    for fn in list(a.ui):
        fn()
    assert a.stavy[-1] == tr("edge.partial_other", ok=0, total=3)


def test_skusit_znova_je_ta_ista_priprava_ako_ctrl_k(monkeypatch):
    a = _atrapa(monkeypatch)
    volania = []
    a.pregenerate = lambda force=False: volania.append(force)
    a.edge_retry_btn.zabalene = "pack"
    a.skus_hlas_znova()
    assert volania == [True] and a.edge_retry_btn.zabalene == ""


def test_skusit_znova_pocas_sledovania_na_siet_nejde(monkeypatch):
    a = _atrapa(monkeypatch, pocuva=True)
    a.skus_hlas_znova()
    assert a.vlakna == [] and a.posielane == []
    assert a.stavy[-1] == tr("edge.after_game")


def test_kazdy_iny_stav_tlacidlo_schova_a_je_pod_zdrojom_hlasu():
    from _zdroj_appky import zdroj_metody
    assert "self._ukaz_skusit_hlas_znova(False)" in zdroj_metody("set_edge_status")
    stranka = zdroj_metody("_build_zvuk_page")
    assert "self.edge_retry_btn = ui_kit.button(" in stranka
    assert 'tr("common.retry"), command=self.skus_hlas_znova' in stranka
