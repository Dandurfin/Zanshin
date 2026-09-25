# -*- coding: utf-8 -*-
"""Stropy na to, co si klient na porte 4455 voli sam (0.2.1).

Port je v LAN bez hesla (zamerne - hrac v telefone nic nevyplna). O to viac
nesmie platit, ze hocico v LAN urci, kolko pamate, CPU a riadkov denniku
appka minie:

  * mena zdrojov (`inputName`) sa pamatali bez limitu a kazda odpoved na
    GetInputList/GetSceneItemList ich posielala vsetky,
  * odmaskovanie ramca islo po bajte v Pythone, pri ramcoch do 1 MB,
  * klientom zvoleny `requestType` isiel do denniku cely (`%r`),
  * prvych 40 surovych sprav z hodiniek islo do denniku pri kazdom behu.
"""
import logging
import os
import socket
import struct
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heart_rate  # noqa: E402
import obs_websocket  # noqa: E402


def _odmaskuj_po_bajte(payload, mask):
    """Povodna (pomala) implementacia - referencia spravnosti."""
    return bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def _ramec(payload, opcode=0x1, mask=None):
    mask = mask or os.urandom(4)
    n = len(payload)
    if n < 126:
        hlavicka = bytes([0x80 | opcode, 0x80 | n])
    elif n < 65536:
        hlavicka = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", n)
    else:
        hlavicka = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", n)
    return hlavicka + mask + _odmaskuj_po_bajte(payload, mask)


def _precitaj(data, timeout=5.0):
    """`read_frame` nad skutocnym socketom; data posiela druhe vlakno, lebo
    64 kB sa do bufferu socketu nemusi zmestit naraz."""
    server, druhy = socket.socketpair()
    server.settimeout(timeout)
    posielac = threading.Thread(target=lambda: _posli_ticho(druhy, data),
                                daemon=True)
    posielac.start()
    try:
        return obs_websocket.read_frame(server)
    finally:
        druhy.close()
        server.close()


def _posli_ticho(sock, data):
    try:
        sock.sendall(data)
    except OSError:
        pass                    # server ramec odmietol a zavrel - to je v poriadku


# ---------------------------------------------------------------------------
# odmaskovanie ramca
# ---------------------------------------------------------------------------

def test_rychle_odmaskovanie_dava_to_iste_co_povodne():
    for mask in (b"\x00\x00\x00\x00", b"\xff\xff\xff\xff", b"\x12\x34\x56\x78",
                 os.urandom(4)):
        for n in list(range(0, 20)) + [125, 126, 1000, 65535, 65536]:
            payload = os.urandom(n)
            assert (obs_websocket._odmaskuj(payload, mask)
                    == _odmaskuj_po_bajte(payload, mask)), (mask, n)


def test_odmaskovanie_zachova_uvodne_nuly():
    """Cez cele cislo by sa uvodne nulove bajty lahko stratili."""
    mask = b"\x01\x02\x03\x04"
    payload = b"\x01\x02\x03\x04" * 3 + b"AB"      # prve bajty vyjdu nulove
    von = obs_websocket._odmaskuj(payload, mask)
    assert len(von) == len(payload)
    assert von == _odmaskuj_po_bajte(payload, mask)
    assert von.startswith(b"\x00" * 12)


def test_read_frame_vsetky_tri_kodovania_dlzky():
    for n in (5, 300, obs_websocket._MAX_RAMEC):   # 7-bit, 16-bit, 64-bit dlzka
        payload = os.urandom(n)
        assert _precitaj(_ramec(payload)) == (0x1, payload), n


def test_ramec_nad_strop_sa_odmietne():
    """Skutocne spravy maju stovky bajtov; 1 MB strop bol len miesto na DoS."""
    assert obs_websocket._MAX_RAMEC <= 64 * 1024
    velky = os.urandom(obs_websocket._MAX_RAMEC + 1)
    assert _precitaj(_ramec(velky)) == (None, None)


def test_ticho_medzi_ramcami_nie_je_koniec_spojenia():
    server, druhy = socket.socketpair()
    try:
        server.settimeout(0.1)
        assert obs_websocket.read_frame(server) == (obs_websocket.TICHO, None)
        # a spojenie je stale v poriadku - dalsi ramec sa precita cely
        druhy.sendall(_ramec(b"ahoj"))
        server.settimeout(5.0)
        assert obs_websocket.read_frame(server) == (0x1, b"ahoj")
    finally:
        druhy.close()
        server.close()


def test_limit_uprostred_ramca_ukonci_spojenie_bez_vynimky():
    """Doteraz by vynimka z polovice ramca vyletela az do `heart_rate`."""
    server, druhy = socket.socketpair()
    try:
        druhy.sendall(_ramec(b"x" * 50)[:10])        # hlavicka + kus tela
        server.settimeout(0.2)
        assert obs_websocket.read_frame(server) == (None, None)
    finally:
        druhy.close()
        server.close()


# ---------------------------------------------------------------------------
# mena zdrojov
# ---------------------------------------------------------------------------

def _poziadavka(typ, meno=None, text=None):
    d = {"requestType": typ, "requestId": "x"}
    if meno is not None:
        d["requestData"] = {"inputName": meno}
        if text is not None:
            d["requestData"]["inputSettings"] = {"text": text}
    return d


def test_mena_zdrojov_od_klienta_maju_strop():
    vlastne, nepoznane = set(), set()
    for i in range(500):
        obs_websocket._odbav(_poziadavka("GetInputSettings", "zdroj%d" % i),
                             lambda t, z: None, vlastne, nepoznane)
    assert len(vlastne) == obs_websocket._MAX_VLASTNYCH
    strop = len(obs_websocket.ZDROJE) + obs_websocket._MAX_VLASTNYCH
    for typ, kluc in (("GetInputList", "inputs"),
                      ("GetSceneItemList", "sceneItems")):
        d = obs_websocket._odbav(_poziadavka(typ), lambda t, z: None,
                                 vlastne, nepoznane)
        assert len(d["responseData"][kluc]) <= strop, typ


def test_prve_mena_sa_stale_pamataju():
    """Strop nesmie rozbit to, kvoli comu sa mena pamataju."""
    vlastne = set()
    obs_websocket._odbav(_poziadavka("CreateInput", "speed"),
                         lambda t, z: None, vlastne, set())
    mena = [i["inputName"] for i in obs_websocket._odbav(
        _poziadavka("GetInputList"), lambda t, z: None, vlastne, set())
        ["responseData"]["inputs"]]
    assert "speed" in mena


def test_zapis_s_nezapamatanym_menom_ide_dalej():
    """Co sa do zoznamu nezmesti, sa len nezapamata - tep ide dalej aj s
    menom zdroja, bez ktoreho by sa kroky citali ako tep."""
    vlastne = set("plne%d" % i for i in range(obs_websocket._MAX_VLASTNYCH))
    zapisy = []
    obs_websocket._odbav(_poziadavka("SetInputSettings", "Tep navyse", "70"),
                         lambda t, z: zapisy.append((z, t)), vlastne, set())
    assert zapisy == [("Tep navyse", "70")]
    assert "Tep navyse" not in vlastne


def test_prilis_dlhe_meno_sa_nezapamata():
    vlastne = set()
    dlhe = "a" * (obs_websocket._MAX_DLZKA_MENA + 1)
    obs_websocket._odbav(_poziadavka("GetInputSettings", dlhe),
                         lambda t, z: None, vlastne, set())
    assert not vlastne


def test_beh_si_nepamata_neobmedzene_vela_mien_zdrojov():
    """`note_source` rozhoduje len "jeden, alebo viac" - viac nez dve mena
    netreba. Doteraz rastla mnozina do restartu senzora s kazdym menom."""
    r = heart_rate._Run(1)
    assert r.note_source("Tep") is True
    assert r.note_source("Tep") is True
    for i in range(1000):
        assert r.note_source("zdroj%d" % i) is False
    assert len(r.zdroje) == 2


# ---------------------------------------------------------------------------
# dennik
# ---------------------------------------------------------------------------

def _riadky(caplog, logger):
    return [r.getMessage() for r in caplog.records if r.name == logger]


def test_neznama_poziadavka_ide_do_denniku_skratena(caplog):
    caplog.set_level(logging.INFO, logger="zanshin")
    obrovska = "X" * (1 << 20)
    obs_websocket._odbav(_poziadavka(obrovska), lambda t, z: None, set(), set())
    riadky = _riadky(caplog, "zanshin.obs")
    assert len(riadky) == 1
    assert len(riadky[0]) < 200, len(riadky[0])


def test_kratka_neznama_poziadavka_sa_zapise_ako_doteraz(caplog):
    caplog.set_level(logging.INFO, logger="zanshin")
    obs_websocket._odbav(_poziadavka("GetHotkeyList"), lambda t, z: None,
                         set(), set())
    assert any("'GetHotkeyList'" in r for r in _riadky(caplog, "zanshin.obs"))


def test_stale_nove_nezname_poziadavky_dennik_nezaplavia(caplog):
    caplog.set_level(logging.INFO, logger="zanshin")
    nepoznane = set()
    for i in range(200):
        obs_websocket._odbav(_poziadavka("Divna%d" % i), lambda t, z: None,
                             set(), nepoznane)
    riadky = _riadky(caplog, "zanshin.obs")
    assert 1 <= len(riadky) <= obs_websocket._MAX_NEPOZNANYCH
    assert len(nepoznane) <= obs_websocket._MAX_NEPOZNANYCH


def test_skratenie_pre_dennik():
    assert obs_websocket._do_dennika("GetFoo") == repr("GetFoo")
    assert obs_websocket._do_dennika(7) == "7"
    assert len(obs_websocket._do_dennika("y" * 10 ** 6)) <= 90


def test_surovych_sprav_z_hodiniek_ide_do_denniku_len_par(caplog):
    """Je to na zistenie, co hodinky pri parovani posielaju - nie zaznam
    tepu. 40 surovych hodnot pri kazdom spusteni bolo privela."""
    caplog.set_level(logging.INFO, logger="zanshin")
    mon = heart_rate.HeartRateMonitor(on_bpm=lambda bpm, gen: None)
    run = heart_rate._Run(1)
    for _ in range(50):
        mon._emit(b"72", run, "Tep")
    riadky = [r for r in _riadky(caplog, "zanshin.hr")
              if "z hodiniek prislo" in r]
    assert 1 <= len(riadky) <= 5, len(riadky)


def test_meno_zdroja_v_denniku_je_skratene(caplog):
    caplog.set_level(logging.INFO, logger="zanshin")
    mon = heart_rate.HeartRateMonitor(on_bpm=lambda bpm, gen: None)
    mon._emit(b"72", heart_rate._Run(1), "T" * 100000)
    riadky = [r for r in _riadky(caplog, "zanshin.hr")
              if "z hodiniek prislo" in r]
    assert riadky and len(riadky[0]) < 400
