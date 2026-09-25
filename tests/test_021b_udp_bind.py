# -*- coding: utf-8 -*-
"""UDP na porte tepu sa neotvorilo - uz nie potichu (0.2.1, BUG 3).

`heart_rate._udp_loop` pri zlyhani vazby (port drzi iny program, chyba
pristupu) doteraz skoncil holym `return`: ziadny riadok v denniku, ziadny
stav. Hrac s appkou, ktora posiela len UDP/OSC (iPhone), tak pozeral na
"Pripaja sa..." a nemal ako zistit preco.

Strazi sa:
  * zlyhanie sa nahlasi (vlastny druh "udp_busy"/"udp_error") - RAZ za beh,
  * TCP (appky pre OBS) pritom prijima dalej a tep z neho chodi,
  * appka z toho spravi jeden riadok v denniku a text pri prepinaci, ale
    NEzhodi prijem ani relaciu (nie je to "busy"/"error" padnuteho TCP).

Skutocne sockety len na 127.0.0.1 a na volnom porte - firewall sa nepyta a
pripadnej bezucej appke na 4455 sa nic nestane.
"""
import errno
import json
import os
import socket
import struct
import sys
import threading
import time
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import theme  # noqa: E402
from i18n import tr  # noqa: E402

HOST = "127.0.0.1"
UDP_DRUHY = ("udp_busy", "udp_error")


def _cakaj(podmienka, limit=5.0):
    koniec = time.monotonic() + limit
    while time.monotonic() < koniec:
        if podmienka():
            return True
        time.sleep(0.02)
    return podmienka()


def _obsad_udp_port():
    """UDP socket, ktory drzi port volny pre TCP - presne ta situacia, ked
    port tepu drzi len iny UDP program (TCP a UDP su dva rozne priestory)."""
    for _ in range(20):
        blokator = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        blokator.bind((HOST, 0))
        port = blokator.getsockname()[1]
        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            tcp.bind((HOST, port))
            return blokator, port
        except OSError:
            blokator.close()
        finally:
            tcp.close()
    pytest.skip("nenasiel sa port volny pre TCP a zaroven drzany cez UDP")


def _volny_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((HOST, 0))
        return s.getsockname()[1]
    finally:
        s.close()


# ---------------------------------------------------------------------------
# minimalny klient obs-websocket - tak, ako sa sprava appka na hodinkach
# ---------------------------------------------------------------------------

def _ramec(payload):
    """Textovy ramec od klienta - podla RFC 6455 vzdy maskovany."""
    mask = os.urandom(4)
    n = len(payload)
    if n < 126:
        hlavicka = bytes([0x81, 0x80 | n])
    else:
        hlavicka = bytes([0x81, 0x80 | 126]) + struct.pack(">H", n)
    return hlavicka + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class _Klient:
    def __init__(self, port):
        for pokus in range(3):
            try:
                self.sock = socket.create_connection((HOST, port), timeout=5.0)
                break
            except ConnectionRefusedError:
                # listen() este nebezal (vola sa tesne po starte UDP vlakna)
                if pokus == 2:
                    raise
                time.sleep(0.1)
        self.buf = b""

    def _citaj(self, n):
        while len(self.buf) < n:
            kus = self.sock.recv(65536)
            if not kus:
                raise ConnectionError("server spojenie zavrel")
            self.buf += kus
        von, self.buf = self.buf[:n], self.buf[n:]
        return von

    def ramec(self):
        _b1, b2 = self._citaj(2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._citaj(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._citaj(8))[0]
        return json.loads(self._citaj(n))

    def posli(self, obj):
        self.sock.sendall(_ramec(json.dumps(obj).encode()))

    def pripoj_a_posli_tep(self, bpm):
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
        assert self.ramec()["op"] == 0                      # Hello
        self.posli({"op": 1, "d": {"rpcVersion": 1}})
        assert self.ramec()["op"] == 2                      # Identified
        self.posli({"op": 6, "d": {
            "requestType": "SetInputSettings", "requestId": "t",
            "requestData": {"inputName": "Tep",
                            "inputSettings": {"text": str(bpm)}}}})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class _SpyLog:
    """Nahrada `heart_rate.log` - zapisuje si varovania do suboru logu."""

    def __init__(self):
        self.varovania = []

    def warning(self, fmt, *args):
        self.varovania.append(fmt % args)

    def info(self, *_a, **_k):
        pass

    def exception(self, *_a, **_k):
        pass


class _Prijimac:
    def __init__(self):
        self.bpm = []
        self.stavy = []             # (druh, payload, generacia)
        self._lock = threading.Lock()
        self.klienti = []
        self.mon = heart_rate.HeartRateMonitor(
            on_bpm=lambda bpm, gen: self.bpm.append(bpm),
            on_status=self._stav)

    def _stav(self, stav, gen):
        with self._lock:
            self.stavy.append((stav[0], stav[1], gen))

    def druhy(self, gen=None):
        with self._lock:
            return [d for d, _p, g in self.stavy if gen is None or g == gen]

    def udp(self, gen=None):
        with self._lock:
            return [(d, p) for d, p, g in self.stavy
                    if d in UDP_DRUHY and (gen is None or g == gen)]

    def klient(self, port):
        k = _Klient(port)
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


@pytest.fixture
def spy_log(monkeypatch):
    # `_udp_loop` byva v heart_rate - modulovy `log` sa podstrkuje tam
    spy = _SpyLog()
    monkeypatch.setattr(heart_rate, "log", spy)
    return spy


# ---------------------------------------------------------------------------
# 1. prijimac: obsadeny UDP port sa nahlasi raz, TCP bezi dalej
# ---------------------------------------------------------------------------

def test_obsadeny_udp_port_sa_nahlasi_raz_a_tcp_prijima_dalej(prijimac, spy_log):
    blokator, port = _obsad_udp_port()
    try:
        gen = prijimac.mon.start(HOST, port)
        assert _cakaj(lambda: prijimac.udp(gen)), prijimac.stavy
        assert prijimac.udp(gen) == [("udp_busy", port)]

        # TCP zije: hodinky sa pripoja cez obs-websocket a tep prejde
        k = prijimac.klient(port)
        k.pripoj_a_posli_tep(77)
        assert _cakaj(lambda: 77 in prijimac.bpm), prijimac.stavy
        assert "client" in prijimac.druhy(gen)

        # ...a UDP sa za ten cas nenahlasilo znova (ziadny spam z vlakna)
        time.sleep(3 * heart_rate.HeartRateMonitor.TICK_TIMEOUT_S)
        assert prijimac.udp(gen) == [("udp_busy", port)], prijimac.stavy
        # zlyhanie UDP nie je padnuty TCP - appka by inak zhodila cely prijem
        assert "busy" not in prijimac.druhy() and "error" not in prijimac.druhy()
        assert prijimac.mon.running
    finally:
        blokator.close()

    # do suboru logu jeden riadok - s portom, bez adresy PC
    assert len(spy_log.varovania) == 1, spy_log.varovania
    assert str(port) in spy_log.varovania[0]
    assert HOST not in spy_log.varovania[0]


def test_kazdy_start_hlasi_raz_nie_viac(prijimac, spy_log):
    """"Raz za beh": restart senzora (zmena portu, dalsi pokus po obsadenom
    TCP) je novy beh a smie to povedat znova - ale zase len raz."""
    blokator, port = _obsad_udp_port()
    try:
        prva = prijimac.mon.start(HOST, port)
        assert _cakaj(lambda: prijimac.udp(prva))
        druha = prijimac.mon.start(HOST, port)
        assert druha != prva
        assert _cakaj(lambda: prijimac.udp(druha))
        time.sleep(2 * heart_rate.HeartRateMonitor.TICK_TIMEOUT_S)
        assert prijimac.udp(prva) == [("udp_busy", port)]
        assert prijimac.udp(druha) == [("udp_busy", port)]
    finally:
        blokator.close()
    assert len(spy_log.varovania) == 2, spy_log.varovania


def test_ina_chyba_udp_sa_nahlasi_s_dovodom_a_tcp_prijima(prijimac, spy_log):
    """Nie kazde zlyhanie je obsadeny port (napr. WSAEACCES pri porte, ktory
    si rezervoval Windows). Hrac ma vidiet dovod, TCP ide dalej."""
    port = _volny_port()
    povodny = prijimac.mon._bind

    def _bind(kind, host, p):
        if kind == socket.SOCK_DGRAM:
            raise PermissionError(errno.EACCES, "pristup zamietnuty")
        return povodny(kind, host, p)

    prijimac.mon._bind = _bind
    gen = prijimac.mon.start(HOST, port)
    assert _cakaj(lambda: prijimac.udp(gen)), prijimac.stavy
    [(druh, payload)] = prijimac.udp(gen)
    assert druh == "udp_error"
    assert payload[0] == port and "pristup zamietnuty" in payload[1]

    k = prijimac.klient(port)
    k.pripoj_a_posli_tep(81)
    assert _cakaj(lambda: 81 in prijimac.bpm), prijimac.stavy
    assert prijimac.udp(gen) == [(druh, payload)]


def test_volny_udp_port_nic_nehlasi(prijimac, spy_log):
    """Bez chyby ticho - riadok patri len skutocnemu zlyhaniu."""
    port = _volny_port()
    gen = prijimac.mon.start(HOST, port)
    assert _cakaj(lambda: "connecting" in prijimac.druhy(gen))
    run = prijimac.mon._run
    # UDP sa registruje vo vlastnom vlakne - listener + UDP = 2 sockety
    assert _cakaj(lambda: len(run._sockets) >= 2, limit=2.0)
    assert prijimac.udp() == []
    assert spy_log.varovania == []


# ---------------------------------------------------------------------------
# 2. appka: riadok v denniku a text pri prepinaci, prijem ani relacia nepadaju
# ---------------------------------------------------------------------------

def _nic(*_a, **_k):
    return None


def _app():
    import app as app_mod
    return app_mod.DandurfApp


def _atrapa(**navyse):
    denn = []
    zatvorene = []
    a = types.SimpleNamespace(
        _hr_generation=5, _hr_state="connecting", _hr_last_bpm=None,
        _hr_client_linked=False, _hr_session_open=True,
        hr_monitoring_enabled=True, hr_critical_bpm=110,
        pal=theme.tokens(theme.DEFAULT_THEME),
        log=denn.append, denn=denn, zatvorene=zatvorene,
        _close_hr_session=lambda: zatvorene.append(True),
        save_settings=_nic, refresh_hr_status_label=_nic,
        _refresh_dnes_stats=_nic, _refresh_kamae_state_text=_nic,
    )
    a.__dict__.update(navyse)
    return a


def _stav(a, kind, payload, gen=5):
    _app()._apply_hr_status(a, (kind, payload), gen)


def _stitok(a):
    return _app()._hr_status_display(a)[0]


def test_appka_zapise_obsadeny_udp_raz_a_prijem_nezhodi():
    a = _atrapa()
    _stav(a, "udp_busy", 4455)
    _stav(a, "udp_busy", 4455)          # ta ista sprava znova - uz nie
    assert a.denn == [tr("log.hr_udp_busy", port=4455)], a.denn
    # nic z toho, co robi "busy"/"error" padnuteho TCP
    assert a._hr_state == "connecting"
    assert a._hr_generation == 5
    assert a.hr_monitoring_enabled is True
    assert a.zatvorene == [], "relacia sa kvoli UDP zatvarat nesmie"


def test_appka_zapise_inu_chybu_udp_s_dovodom():
    a = _atrapa()
    _stav(a, "udp_error", (4455, "[WinError 10013] zakazane"))
    assert a.denn == [tr("log.hr_udp_error", port=4455,
                         err="[WinError 10013] zakazane")]
    assert "10013" in a.denn[0]
    assert a._hr_state == "connecting" and a.zatvorene == []


def test_sprava_zo_stareho_behu_sa_zahodi():
    a = _atrapa()
    _stav(a, "udp_busy", 4455, gen=4)
    assert a.denn == []
    assert _stitok(a) == tr("settings.hr_status_connecting")


def test_stitok_pri_prepinaci_hovori_len_tcp_kym_sa_nikto_nepripojil():
    a = _atrapa()
    assert _stitok(a) == tr("settings.hr_status_connecting")
    _stav(a, "udp_busy", 4455)
    assert _stitok(a) == tr("settings.hr_status_udp_off")
    a._hr_state = "no_client"
    assert _stitok(a) == tr("settings.hr_status_udp_off")
    # hodinky drzia TCP spojenie - UDP nikomu nechyba, plati skutocny stav
    a._hr_state = "linked"
    assert _stitok(a) == tr("settings.hr_status_waiting")
    a._hr_state, a._hr_last_bpm = "connected", 72
    assert "72" in _stitok(a)


def test_novy_beh_priznak_zahodi_sam():
    """Restart senzora ma novu generaciu - stary priznak na stitku neostane
    a nova sprava sa do dennika zapise znova (raz za beh)."""
    a = _atrapa()
    _stav(a, "udp_busy", 4455)
    a._hr_generation = 6
    assert _stitok(a) == tr("settings.hr_status_connecting")
    _stav(a, "udp_busy", 4455, gen=6)
    assert len(a.denn) == 2
    assert _stitok(a) == tr("settings.hr_status_udp_off")
    # vypnuty senzor (generacia 0) nic o UDP netvrdi
    a._hr_generation, a._hr_state = 0, "disconnected"
    assert _stitok(a) == tr("settings.hr_status_disconnected")


def test_texty_maju_vsetky_jazyky():
    import i18n
    for kluc in ("log.hr_udp_busy", "log.hr_udp_error",
                 "settings.hr_status_udp_off"):
        for jazyk in i18n.LANGUAGES:
            assert i18n.tr_lang(jazyk, kluc).strip(), (kluc, jazyk)
        assert i18n.tr_lang("sk", kluc) != i18n.tr_lang("en", kluc)
    # riadok hovori aj to, co funguje dalej - nie len, co nejde
    assert "TCP" in i18n.tr_lang("sk", "log.hr_udp_busy")
    assert "TCP" in i18n.tr_lang("en", "log.hr_udp_error")
