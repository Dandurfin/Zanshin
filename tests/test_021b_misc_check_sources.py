# -*- coding: utf-8 -*-
"""check_sources.py without internet on Windows (review 0.2.1, bug 6).

The script recognised "no network" only by the Linux text "Name or service
not known". On Windows without internet getaddrinfo reports `[Errno 11001]
getaddrinfo failed` (or WinError 11002 / 10051 / 10065, or a timeout), so
the script declared EVERY link dead and exited with code 1. Now: when no
server answered and everything failed on the network, it says "you are not
online, I checked nothing" and exits neutrally (0). When at least one
server answered, a network error on another link really is an unreachable
link (e.g. a dead domain).

urlopen is always replaced in the tests - the test sends not a single byte
anywhere.
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
    """OSError the way Windows produces it (both winerror and errno). On
    another system only errno - so that the test runs there too."""
    if sys.platform == "win32":
        return OSError(None, text, None, kod)
    return OSError(kod, text)


class _Odpoved:
    """Stand-in for the urlopen response - the server answered 200."""
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def _jazyk_naspat(monkeypatch):
    # main() switches i18n to English - after the test we restore the
    # original language
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
    # what really comes from urlopen on Windows without internet
    urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed")),
    urllib.error.URLError(socket.gaierror(11002, "getaddrinfo failed")),
    urllib.error.URLError(_win_chyba(11001, "No such host is known")),
    urllib.error.URLError(_win_chyba(11002, "Temporary DNS failure")),
    urllib.error.URLError(_win_chyba(10051, "A socket operation was attempted "
                                            "to an unreachable network")),
    urllib.error.URLError(_win_chyba(10065, "A socket operation was attempted "
                                            "to an unreachable host")),
    # unwrapped (an error while reading the response)
    _win_chyba(10051, "unreachable network"),
    # the Linux text the script knew until now still applies
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
    """A network without internet (e.g. Wi-Fi without a connection) - every
    link times out. Wrapped and unwrapped, as urllib really sends it."""
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
    """The fix must not hide a really dead link: when the other servers
    answer, a nonexistent domain (getaddrinfo) is a link error."""
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
    """Server answered (if with an error) - network works, links are dead."""
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
    """HEAD got 405 (the server answered), GET then times out - the server is
    reachable, so it is a link failure, not a network error."""
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
    # the server is reachable, it just refuses / answered with an error
    (ConnectionRefusedError(10061, "refused"), False),
    (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), False),
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), False),
    (ValueError("unknown url type"), False),
])
def test_is_network_error(chyba, sietova):
    assert cs.is_network_error(chyba) is sietova
