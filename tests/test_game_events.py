# -*- coding: utf-8 -*-
"""Príjem herných udalostí — protokol a odolnosť proti pokazenému producentovi.

Modul je zámerne oddelený od kanála tepu. 19. 9. 2026 sa ukázalo, čo spraví
zdieľanie jedného netypovaného textového kanála dvoma druhmi dát: keď appka
na hodinkách začala posielať aj kroky, parser tepu čítal počet krokov ako
BPM a vznikla 52-minútová relácia s priemerom 124 a maximom 235.
"""
import json
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import game_events  # noqa: E402


# ---------------------------------------------------------------------------
# parse_event — čo prejde a čo nie
# ---------------------------------------------------------------------------

def test_platna_udalost_prejde():
    u = game_events.parse_event('{"type": "kill", "ts": 1000.0}', now=1000.0)
    assert u["type"] == "kill"
    assert u["ts"] == 1000.0


def test_chybajuci_cas_sa_doplni_casom_prijatia():
    u = game_events.parse_event('{"type": "death"}', now=1234.0)
    assert u["ts"] == 1234.0


def test_dalsie_polia_prejdu_nedotknute():
    u = game_events.parse_event(
        '{"type": "round_end", "score": 13, "score_opponent": 9}', now=1000.0)
    assert u["score"] == 13 and u["score_opponent"] == 9


def test_neznamy_typ_sa_zahodi_nie_uhadne():
    """Z toho istého dôvodu, prečo sa nehádže tep z čísla bez menovky."""
    assert game_events.parse_event('{"type": "headshot"}') is None
    assert game_events.parse_event('{"score": 13}') is None


def test_pokazeny_riadok_neprejde():
    for riadok in ("", "   ", "toto nie je JSON", "[1,2,3]", '"kill"',
                   "null", '{"type": "kill", "ts": "nie je cislo"}'):
        assert game_events.parse_event(riadok) is None, riadok


def test_prilis_dlhy_riadok_neprejde():
    dlhy = '{"type": "kill", "x": "%s"}' % ("a" * game_events.MAX_RIADOK)
    assert game_events.parse_event(dlhy) is None


def test_stara_znacka_casu_sa_nahradi_a_povodna_ostane():
    """Most môže po výpadku poslať nazbierané udalosti naraz.

    Do bežiacej relácie už nepatria, ale zahodiť ich celé by znamenalo
    stratiť informáciu — pôvodná značka sa preto odloží.
    """
    u = game_events.parse_event('{"type": "kill", "ts": 1.0}', now=1_000_000.0)
    assert u["ts"] == 1_000_000.0
    assert u["ts_reported"] == 1.0


def test_neplatne_utf8_neprejde():
    assert game_events.parse_event(b'{"type": "kill", "x": "\xff\xfe"}') is None


# ---------------------------------------------------------------------------
# GameEventReceiver — koniec na koniec cez skutočný socket
# ---------------------------------------------------------------------------

def _volny_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _pockaj(podmienka, timeout=3.0):
    koniec = time.time() + timeout
    while time.time() < koniec:
        if podmienka():
            return True
        time.sleep(0.02)
    return False


def test_prijimac_dorucuje_udalosti():
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        assert _pockaj(lambda: r.running)
        time.sleep(0.3)                      # nech stihne bind
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b'{"type": "kill"}\n')
            s.sendall(b'{"type": "death"}\n')
            assert _pockaj(lambda: len(prijate) >= 2)
    finally:
        r.stop()
    assert [u["type"] for u in prijate] == ["kill", "death"]


def test_pokazene_riadky_nezhodia_spojenie():
    """Producent, ktorý posiela nezmysly, nesmie umlčať tie dobré."""
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        time.sleep(0.3)
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b"toto nie je JSON\n")
            s.sendall(b'{"type": "neznamy"}\n')
            s.sendall(b'{"chyba": "typ"}\n')
            s.sendall(b'{"type": "kill"}\n')   # toto prejsť MUSI
            assert _pockaj(lambda: len(prijate) >= 1)
    finally:
        r.stop()
    assert len(prijate) == 1 and prijate[0]["type"] == "kill"


def test_rozdelena_sprava_sa_poskladá():
    """TCP nezaručuje, že správa príde v jednom kuse."""
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        time.sleep(0.3)
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b'{"type": "ki')
            time.sleep(0.1)
            s.sendall(b'll", "score": 3}\n')
            assert _pockaj(lambda: len(prijate) >= 1)
    finally:
        r.stop()
    assert prijate[0]["type"] == "kill" and prijate[0]["score"] == 3


def test_pocuva_len_na_loopbacku():
    """Herné udalosti chodia z toho istého počítača.

    Tep sa počúva na všetkých sieťach, lebo chodí z hodiniek cez Wi-Fi.
    Tu na to dôvod nie je a každý port navyše otvorený do siete je riziko.
    """
    assert game_events.LOOPBACK == "127.0.0.1"
    import inspect
    telo = inspect.getsource(game_events.GameEventReceiver._serve)
    assert "LOOPBACK" in telo
    assert '"0.0.0.0"' not in telo and "ANY_INTERFACE" not in telo


def test_port_sa_nebije_s_tepom():
    import heart_rate
    assert game_events.DEFAULT_PORT != heart_rate.DEFAULT_PORT


def test_modul_je_cisto_datovy():
    """Bez Tk — rovnaké pravidlo ako trigger/measure/activity/data_io."""
    zdroj = open(os.path.join(os.path.dirname(__file__), "..",
                              "game_events.py"), encoding="utf-8").read()
    assert "import tkinter" not in zdroj
    assert "customtkinter" not in zdroj


# ---------------------------------------------------------------------------
# WebSocket — bez neho by most z Overwolfu nemal ako prísť
# ---------------------------------------------------------------------------

def _ws_ramec(payload):
    """Klientsky text frame — maskovaný, ako to vyžaduje protokol."""
    import os
    import struct
    data = payload.encode("utf-8")
    hlavicka = bytes([0x81])
    maska = os.urandom(4)
    n = len(data)
    if n < 126:
        hlavicka += bytes([0x80 | n])
    elif n < (1 << 16):
        hlavicka += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        hlavicka += bytes([0x80 | 127]) + struct.pack(">Q", n)
    zamaskovane = bytes(b ^ maska[i % 4] for i, b in enumerate(data))
    return hlavicka + maska + zamaskovane


def _ws_pripoj(port):
    """Minimálny WebSocket klient — presne to, čo spraví `overwolf.web`."""
    import base64
    import os
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    kluc = base64.b64encode(os.urandom(16)).decode()
    s.sendall(("GET / HTTP/1.1\r\n"
               "Host: 127.0.0.1\r\n"
               "Upgrade: websocket\r\n"
               "Connection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {kluc}\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n").encode())
    odpoved = b""
    while b"\r\n\r\n" not in odpoved:
        kus = s.recv(4096)
        assert kus, "server zavrel spojenie pri handshake"
        odpoved += kus
    assert b"101" in odpoved.split(b"\r\n")[0], odpoved[:80]
    return s


def test_websocket_dorucuje_rovnake_udalosti():
    """Overwolf appka je JavaScript v Chromiu a surový TCP otvoriť nevie.

    Má len `overwolf.web.createWebSocket()`. Keby príjmač rozumel iba
    surovým riadkom, testovací skript by fungoval a skutočný most by sa
    nikdy nepripojil.
    """
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        time.sleep(0.3)
        s = _ws_pripoj(port)
        try:
            s.sendall(_ws_ramec('{"type": "kill"}'))
            s.sendall(_ws_ramec('{"type": "round_end", "score": 7}'))
            assert _pockaj(lambda: len(prijate) >= 2)
        finally:
            s.close()
    finally:
        r.stop()
    assert [u["type"] for u in prijate] == ["kill", "round_end"]
    assert prijate[1]["score"] == 7


def test_websocket_znesie_viac_udalosti_v_jednom_ramci():
    """JS pošle typicky jednu udalosť na rámec, ale nemusí."""
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        time.sleep(0.3)
        s = _ws_pripoj(port)
        try:
            s.sendall(_ws_ramec('{"type": "kill"}\n{"type": "death"}\n'))
            assert _pockaj(lambda: len(prijate) >= 2)
        finally:
            s.close()
    finally:
        r.stop()
    assert [u["type"] for u in prijate] == ["kill", "death"]


def test_oba_transporty_na_tom_istom_porte():
    """Surové TCP musí prežiť pridanie WebSocketu."""
    prijate = []
    port = _volny_port()
    r = game_events.GameEventReceiver(lambda u, g: prijate.append(u))
    r.start(port)
    try:
        time.sleep(0.3)
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b'{"type": "kill"}\n')
            assert _pockaj(lambda: len(prijate) == 1)
        s = _ws_pripoj(port)
        try:
            s.sendall(_ws_ramec('{"type": "death"}'))
            assert _pockaj(lambda: len(prijate) == 2)
        finally:
            s.close()
    finally:
        r.stop()
    assert [u["type"] for u in prijate] == ["kill", "death"]
