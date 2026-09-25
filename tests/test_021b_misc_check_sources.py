# -*- coding: utf-8 -*-
"""check_sources.py bez internetu na Windows (review 0.2.1, bug 6).

Skript rozoznaval "nie je siet" len podla linuxoveho textu "Name or service
not known". Na Windows bez internetu hlasi getaddrinfo `[Errno 11001]
getaddrinfo failed` (pripadne WinError 11002 / 10051 / 10065 alebo timeout),
takze skript vyhlasil KAZDY odkaz za mrtvy a skoncil kodom 1. Teraz: ked
ziaden server neodpovedal a vsetko padlo na sieti, povie "nie si online, nic
som neskontroloval" a skonci neutralne (0). Ked aspon jeden server odpovedal,
sietova chyba pri inom odkaze je naozaj nedostupny odkaz (napr. mrtva domena).

urlopen je v testoch vzdy nahradeny - test nikam nesiela ani bajt.
"""
import os
import socket
import sys
import urllib.error

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import check_sources as cs  # noqa: E402
import i18n  # noqa: E402


def _win_chyba(kod, text):
    """OSError tak, ako ho vyrobi Windows (winerror aj errno). Na inom
    systeme len errno - aby test bezal aj tam."""
    if sys.platform == "win32":
        return OSError(None, text, None, kod)
    return OSError(kod, text)


class _Odpoved:
    """Nahrada odpovede urlopen - server odpovedal 200."""
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def _jazyk_naspat(monkeypatch):
    # main() prepina i18n na anglictinu - po teste vratime povodny jazyk
    monkeypatch.setitem(i18n._lang, "code", i18n._lang["code"])


def _spusti(monkeypatch, capsys, urlopen):
    monkeypatch.setattr(cs.urllib.request, "urlopen", urlopen)
    with pytest.raises(SystemExit) as koniec:
        cs.main()
    return koniec.value.code, capsys.readouterr().out


def _vzdy(chyba):
    def urlopen(req, timeout=None):
        raise chyba
    return urlopen


@pytest.mark.parametrize("chyba", [
    # to, co naozaj pride z urlopen na Windows bez internetu
    urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed")),
    urllib.error.URLError(socket.gaierror(11002, "getaddrinfo failed")),
    urllib.error.URLError(_win_chyba(11001, "No such host is known")),
    urllib.error.URLError(_win_chyba(11002, "Temporary DNS failure")),
    urllib.error.URLError(_win_chyba(10051, "A socket operation was attempted "
                                            "to an unreachable network")),
    urllib.error.URLError(_win_chyba(10065, "A socket operation was attempted "
                                            "to an unreachable host")),
    # nezabalene (chyba pocas citania odpovede)
    _win_chyba(10051, "unreachable network"),
    # linuxovy text, ktory skript poznal doteraz, stale plati
    urllib.error.URLError(socket.gaierror(-2, "Name or service not known")),
], ids=["gai11001", "gai11002", "win11001", "win11002", "win10051",
        "win10065", "raw10051", "linux"])
def test_bez_siete_hlasi_offline_nie_mrtve_odkazy(monkeypatch, capsys, chyba):
    kod, vystup = _spusti(monkeypatch, capsys, _vzdy(chyba))
    assert kod == 0, vystup
    assert "Nie si online" in vystup
    assert "nic som neskontroloval" in vystup
    assert "MRTVE" not in vystup
    assert "PAD" not in vystup


def test_timeout_na_vsetkych_odkazoch_je_offline(monkeypatch, capsys):
    """Sieť bez internetu (napr. Wi-Fi bez pripojenia) - kazdy odkaz
    vyprsi. Zabalene aj nezabalene, ako to urllib naozaj posiela."""
    chyby = iter([urllib.error.URLError(TimeoutError("timed out")),
                  socket.timeout("timed out"),
                  urllib.error.URLError(_win_chyba(10060, "connection timed out"))])

    def urlopen(req, timeout=None):
        raise next(chyby)
    kod, vystup = _spusti(monkeypatch, capsys, urlopen)
    assert kod == 0, vystup
    assert "Nie si online" in vystup
    assert "MRTVE" not in vystup


def test_online_mrtva_domena_je_stale_mrtvy_odkaz(monkeypatch, capsys):
    """Oprava nesmie skryt skutocne mrtvy odkaz: ked ostatne servery
    odpovedaju, neexistujuca domena (getaddrinfo) je chyba odkazu."""
    mrtva = cs.PHILOSOPHY_SOURCES[1][1]

    def urlopen(req, timeout=None):
        if req.full_url == mrtva:
            raise urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))
        return _Odpoved()
    kod, vystup = _spusti(monkeypatch, capsys, urlopen)
    assert kod == 1, vystup
    assert "Nie si online" not in vystup
    assert "MRTVE ALEBO NEDOSTUPNE ODKAZY: 1" in vystup
    assert cs.PHILOSOPHY_SOURCES[1][0] in vystup


def test_http_404_nie_je_offline(monkeypatch, capsys):
    """Server odpovedal (hoci chybou) - siet ide, odkazy su mrtve."""
    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    kod, vystup = _spusti(monkeypatch, capsys, urlopen)
    assert kod == 1, vystup
    assert "Nie si online" not in vystup
    assert "MRTVE ALEBO NEDOSTUPNE ODKAZY: %d" % len(cs.PHILOSOPHY_SOURCES) in vystup


def test_vsetko_zije(monkeypatch, capsys):
    kod, vystup = _spusti(monkeypatch, capsys, lambda req, timeout=None: _Odpoved())
    assert kod == 0
    assert "Vsetky odkazy ziju." in vystup


def test_get_po_head_odpovedi_nie_je_offline(monkeypatch):
    """HEAD dostal 405 (server odpovedal), GET potom vyprsi - server je
    dosiahnutelny, takze je to zlyhanie odkazu, nie chyba siete."""
    def urlopen(req, timeout=None):
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 405, "Method", {}, None)
        raise urllib.error.URLError(TimeoutError("timed out"))
    monkeypatch.setattr(cs.urllib.request, "urlopen", urlopen)
    ok, info = cs.check("https://example.invalid/")
    assert ok is False
    assert "timed out" in info


@pytest.mark.parametrize("chyba, sietova", [
    (socket.gaierror(11001, "getaddrinfo failed"), True),
    (_win_chyba(11002, "x"), True),
    (_win_chyba(10051, "x"), True),
    (_win_chyba(10065, "x"), True),
    (TimeoutError("timed out"), True),
    (urllib.error.URLError("timed out"), True),
    # server je dosiahnutelny, len odmieta / odpovedal chybou
    (ConnectionRefusedError(10061, "refused"), False),
    (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), False),
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), False),
    (ValueError("unknown url type"), False),
])
def test_is_network_error(chyba, sietova):
    assert cs.is_network_error(chyba) is sietova
