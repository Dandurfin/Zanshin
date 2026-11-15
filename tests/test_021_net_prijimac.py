# -*- coding: utf-8 -*-
"""Receiver on port 4455 under load - real sockets on 127.0.0.1 (0.2.1).

Bugs from the code review that together turned the flood protection into a
way to switch heart rate reception off:

  1. the connection cap (`_MAX_LIVE_SOCKETS`) stopped the WHOLE listener
     when full, until the sensor was restarted (`break` instead of
     dropping one connection),
  2. connections had no time limit, so every silent connection held its
     place forever - even half-open ones from watches that left the Wi-Fi.

And fix 2 must not disconnect a live, just quiet watch, nor report
"disconnected" when the watch keeps writing over a new connection.

The port is taken free and only on 127.0.0.1 - the firewall does not ask
and a possibly running app on 4455 is not affected. The limits are
shortened in the tests to tenths of a second, so the test does not wait a
minute.
"""
import json
import os
import socket
import struct
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import obs_websocket  # noqa: E402

HOST = "127.0.0.1"


def _cakaj(podmienka, limit=5.0):
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        if podmienka():
            return True
        time.sleep(0.02)
    return podmienka()


def _volny_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, 0))
        return s.getsockname()[1]
    finally:
        s.close()


def _ramec(payload, opcode=0x1):
    """Frame from the client - per RFC 6455 always masked."""
    mask = os.urandom(4)
    n = len(payload)
    if n < 126:
        hlavicka = bytes([0x80 | opcode, 0x80 | n])
    elif n < 65536:
        hlavicka = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", n)
    else:
        hlavicka = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", n)
    return hlavicka + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class _Klient:
    """Minimal WebSocket client - behaving like the app on the watch."""

    def __init__(self, sock):
        self.sock = sock
        self.sock.settimeout(5.0)
        self.buf = b""

    def _citaj(self, n):
        while len(self.buf) < n:
            kus = self.sock.recv(65536)
            if not kus:
                raise ConnectionError("server spojenie zavrel")
            self.buf += kus
        von, self.buf = self.buf[:n], self.buf[n:]
        return von

    def handshake(self):
        self.sock.sendall(
            b"GET / HTTP/1.1\r\nHost: zanshin\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Sec-WebSocket-Version: 13\r\n\r\n")
        while b"\r\n\r\n" not in self.buf:
            kus = self.sock.recv(4096)
            if not kus:
                raise ConnectionError("server spojenie zavrel")
            self.buf += kus
        hlava, self.buf = self.buf.split(b"\r\n\r\n", 1)
        assert hlava.startswith(b"HTTP/1.1 101"), hlava
        opcode, hello = self.ramec()
        assert opcode == 0x1 and json.loads(hello)["op"] == 0
        return self

    def ramec(self):
        b1, b2 = self._citaj(2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._citaj(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._citaj(8))[0]
        return b1 & 0x0F, self._citaj(n)

    def posli(self, obj):
        self.sock.sendall(_ramec(json.dumps(obj).encode()))

    def identify(self):
        self.posli({"op": 1, "d": {"rpcVersion": 1}})
        _opcode, telo = self.ramec()
        assert json.loads(telo)["op"] == 2
        return self

    def tep(self, bpm, zdroj="Tep"):
        self.posli({"op": 6, "d": {
            "requestType": "SetInputSettings", "requestId": "t",
            "requestData": {"inputName": zdroj,
                            "inputSettings": {"text": str(bpm)}}}})

    def zatvoril_server(self, limit=3.0):
        """True if the server closes the connection in `limit` seconds."""
        koniec = time.monotonic() + limit
        while time.monotonic() < koniec:
            self.sock.settimeout(max(0.01, koniec - time.monotonic()))
            try:
                if not self.sock.recv(65536):
                    return True
            except socket.timeout:
                return False
            except OSError:
                return True             # a reset is a close too
        return False

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class _Prijimac:
    """A real `HeartRateMonitor` on a free port, with its own clients."""

    def __init__(self):
        self.bpm = []
        self.stavy = []
        self.klienti = []
        self.mon = heart_rate.HeartRateMonitor(
            on_bpm=lambda bpm, gen: self.bpm.append(bpm),
            on_status=lambda stav, gen: self.stavy.append(stav[0]))
        self.port = _volny_port()
        self.mon.start(HOST, self.port)
        assert _cakaj(lambda: "connecting" in self.stavy), self.stavy
        # UDP registers in its own thread - we wait for it, so that the number
        # of occupied places does not change under the test's hands
        _cakaj(lambda: self.obsadene() >= 2, limit=2.0)

    def obsadene(self):
        run = self.mon._run
        with run._lock:
            return len(run._sockets)

    def klient(self):
        for pokus in range(3):
            try:
                sock = socket.create_connection((HOST, self.port), timeout=5.0)
                break
            except ConnectionRefusedError:
                # listen() was not running yet (it is called right after the
                # UDP thread starts)
                if pokus == 2:
                    raise
                time.sleep(0.1)
        k = _Klient(sock)
        self.klienti.append(k)
        return k

    def zavri(self):
        self.mon.stop()
        for k in self.klienti:
            k.close()


@pytest.fixture
def prijimac():
    p = _Prijimac()
    yield p
    p.zavri()


# ---------------------------------------------------------------------------
# 1. a full cap must not stop all reception
# ---------------------------------------------------------------------------

def test_plny_strop_zahodi_len_nove_spojenie_a_prijem_bezi_dalej(
        prijimac, monkeypatch, caplog):
    """Before: the 16th connection -> `conn.close(); break` -> the listener
    ended and heart rate did not arrive until the sensor was restarted,
    even when places freed up. So the flood cap itself did what it was
    supposed to protect against."""
    monkeypatch.setattr(heart_rate, "_MAX_LIVE_SOCKETS", prijimac.obsadene() + 3)
    strop = heart_rate._MAX_LIVE_SOCKETS
    plni = [prijimac.klient().handshake() for _ in range(3)]
    assert _cakaj(lambda: prijimac.obsadene() == strop)

    # two extra connections: both are dropped and the listener must not
    # end meanwhile
    for _ in range(2):
        navyse = prijimac.klient()
        assert navyse.zatvoril_server(), "spojenie nad strop sa malo zahodit"

    # a place frees up...
    plni[0].close()
    assert _cakaj(lambda: prijimac.obsadene() < strop)
    # ...and the watch connects and heart rate gets through
    hodinky = prijimac.klient().handshake().identify()
    hodinky.tep(77)
    assert _cakaj(lambda: 77 in prijimac.bpm), prijimac.bpm

    # the cap is reported to the journal once per run, not on every refusal
    hlasky = [r for r in caplog.records
              if r.name == "zanshin.hr" and "strop" in r.getMessage()]
    assert len(hlasky) == 1, [r.getMessage() for r in hlasky]


def test_stop_zavrie_spojenia_hned_aj_s_casovym_limitom():
    """Sockets now have a limit (a minute of silence); stop() won't wait on it.

    Closing a socket from another thread unblocks the read immediately; if
    not, the threads of old runs would hang until the limit expired."""
    pred = set(threading.enumerate())
    p = _Prijimac()
    try:
        linked = p.klient().handshake().identify()
        v_handshake = p.klient()               # sent nothing, it is being waited for
        assert _cakaj(lambda: p.obsadene() >= 3)
        zaciatok = time.monotonic()
        p.mon.stop()
        assert linked.zatvoril_server(limit=2.0)
        assert v_handshake.zatvoril_server(limit=2.0)
        assert _cakaj(lambda: not [t for t in threading.enumerate()
                                   if t not in pred and t.is_alive()],
                      limit=3.0), "vlakna prijimaca po stop() neskoncili"
        assert time.monotonic() - zaciatok < 5.0
    finally:
        p.zavri()


# ---------------------------------------------------------------------------
# 2. time limits
# ---------------------------------------------------------------------------

def test_tiche_spojenie_uvolni_miesto_po_limite_handshake(prijimac, monkeypatch):
    """A port scanner (or anything that only opens TCP and stays silent) held
    one of the 16 places forever. Fourteen of those and the watch did not
    connect."""
    monkeypatch.setattr(obs_websocket, "HANDSHAKE_TIMEOUT_S", 0.3)
    pred = prijimac.obsadene()
    ticho = prijimac.klient()
    assert ticho.zatvoril_server(limit=3.0), "tiche spojenie malo skoncit"
    assert _cakaj(lambda: prijimac.obsadene() == pred)
    assert "client" not in prijimac.stavy, "bez handshake to nie su hodinky"


def test_mrtve_spojenie_skonci_a_odpojenie_sa_hlasi_az_za_poslednym(
        prijimac, monkeypatch):
    """Wi-Fi drop: the watch uses a NEW connection, the old one stays half-open.

    The inactivity limit now closes it - but a "client_gone" on it would,
    in the middle of live heart rate, throw away the trigger countdown and
    record a dropout that did not happen. It is reported only when the
    last client leaves.
    """
    monkeypatch.setattr(obs_websocket, "NECINNOST_S", 0.3)
    mrtve = prijimac.klient().handshake().identify()    # then not even a pong
    zive = prijimac.klient().handshake().identify()
    koniec = time.monotonic() + 1.5
    while time.monotonic() < koniec:
        zive.tep(72)
        time.sleep(0.1)
    assert mrtve.zatvoril_server(limit=2.0), "mrtve spojenie malo skoncit"
    assert prijimac.stavy.count("client") == 2
    assert "client_gone" not in prijimac.stavy, "zive hodinky este pisu"
    assert 72 in prijimac.bpm

    zive.close()
    assert _cakaj(lambda: "client_gone" in prijimac.stavy)
    time.sleep(0.2)
    assert prijimac.stavy.count("client_gone") == 1


def test_osamele_mrtve_spojenie_skonci_ako_bezne_odpojenie(prijimac, monkeypatch):
    """For the app, the inactivity limit must look exactly like a normal
    disconnect: the only client that does not answer even a ping ends with
    ONE "client_gone" (not none - the app would claim "watch connected"
    forever), the place frees up and the next watch connects normally."""
    monkeypatch.setattr(obs_websocket, "NECINNOST_S", 0.2)
    pred = prijimac.obsadene()
    mrtve = prijimac.klient().handshake().identify()    # then not even a pong
    assert mrtve.zatvoril_server(limit=3.0), "mrtve spojenie malo skoncit"
    assert _cakaj(lambda: "client_gone" in prijimac.stavy), prijimac.stavy
    assert _cakaj(lambda: prijimac.obsadene() == pred)
    time.sleep(0.2)
    assert prijimac.stavy.count("client_gone") == 1

    hodinky = prijimac.klient().handshake().identify()
    hodinky.tep(66)
    assert _cakaj(lambda: 66 in prijimac.bpm), prijimac.bpm
    assert prijimac.stavy.count("client") == 2


def _server_v_pozadi(server, zapisy, on_connected=None):
    vlakno = threading.Thread(
        target=obs_websocket.serve_connection,
        args=(server, lambda text, zdroj: zapisy.append((zdroj, text)),
              lambda: False, on_connected),
        daemon=True)
    vlakno.start()
    return vlakno


def test_zive_ale_tiche_hodinky_na_ping_odpovedia_a_ostanu(monkeypatch):
    """A pause in measuring must not mean a disconnect: after silence a ping
    goes out, every WebSocket library answers it by itself and the
    connection stays."""
    monkeypatch.setattr(obs_websocket, "NECINNOST_S", 0.2)
    server, druhy = socket.socketpair()
    zapisy = []
    vlakno = _server_v_pozadi(server, zapisy)
    try:
        k = _Klient(druhy).handshake().identify()
        pingy = 0
        koniec = time.monotonic() + 1.2
        while time.monotonic() < koniec:
            opcode, telo = k.ramec()
            if opcode == 0x9:
                pingy += 1
                k.sock.sendall(_ramec(telo, opcode=0xA))
        assert pingy >= 3, pingy
        assert vlakno.is_alive(), "zive hodinky odpojene za ticho"
        k.tep(81)
        assert _cakaj(lambda: zapisy == [("Tep", "81")]), zapisy
    finally:
        druhy.close()
        server.close()
        vlakno.join(2.0)


def test_mrtve_spojenie_dostane_ping_a_potom_skonci(monkeypatch):
    monkeypatch.setattr(obs_websocket, "NECINNOST_S", 0.2)
    server, druhy = socket.socketpair()
    vlakno = _server_v_pozadi(server, [])
    try:
        k = _Klient(druhy).handshake()
        opcode, _telo = k.ramec()
        assert opcode == 0x9, "najprv sa ma slusne opytat pingom"
        vlakno.join(2.0)
        assert not vlakno.is_alive(), "bez odpovede na ping malo skoncit"
    finally:
        druhy.close()
        server.close()


def test_handshake_ma_celkovy_limit_aj_pri_kvapkani_po_bajte(monkeypatch):
    """A limit per single `recv` would be stretched forever by a client
    sending one byte at a time - the handshake limit is overall."""
    monkeypatch.setattr(obs_websocket, "HANDSHAKE_TIMEOUT_S", 0.4)
    server, druhy = socket.socketpair()
    vysledok = []
    vlakno = threading.Thread(
        target=lambda: vysledok.append(obs_websocket.handshake(server)),
        daemon=True)
    zaciatok = time.monotonic()
    vlakno.start()
    try:
        while vlakno.is_alive() and time.monotonic() - zaciatok < 3.0:
            druhy.sendall(b"G")            # never finishes the header
            time.sleep(0.05)
        vlakno.join(0.5)
        assert vysledok == [False]
        assert time.monotonic() - zaciatok < 2.0
    finally:
        druhy.close()
        server.close()


def test_handshake_skutocneho_klienta_stale_prejde():
    server, druhy = socket.socketpair()
    try:
        vlakno = _server_v_pozadi(server, [])
        _Klient(druhy).handshake().identify()
        assert vlakno.is_alive()
    finally:
        druhy.close()
        server.close()
