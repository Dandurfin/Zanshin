# -*- coding: utf-8 -*-
"""Recognising VPN and virtual adapters without false alarms (0.3 batch
4b).

Batch 4 also tagged as "(VPN/virtual)" two addresses the phone can
reach:
  * the Windows Mobile hotspot - "Microsoft Wi-Fi Direct Virtual Adapter",
    name "Local Area Connection* N" (the word "Virtual" in the description),
  * an external Hyper-V switch - the physical network card is bridged to
    "vEthernet (...)", and that holds the home address and the default
    route out.
The hotspot gets its own "(hotspot)" tag without a warning, an external
switch with the home network is treated as physical. A real VPN, WSL,
"Default Switch" and loopback stay tagged.

All adapters are made up: the names and descriptions are generic, the
addresses come from documentation ranges or are obviously made-up private
ones (192.168.250.x).
"""
import pytest

import netinfo
from _zdroj_appky import zdroj_suboru

F, H, V = netinfo.FYZICKY, netinfo.HOTSPOT, netinfo.VIRTUALNY

HOTSPOT = ("192.0.2.10", "Local Area Connection* 10",
           "Microsoft Wi-Fi Direct Virtual Adapter #2", 71)
WIFI = ("192.168.250.20", "Wi-Fi", "Generic Wireless Adapter", 71)
ETHERNET = ("192.168.250.80", "Ethernet", "Generic Gigabit Ethernet Controller", 6)
EXTERNY = ("192.168.250.77", "vEthernet (Externy prepinac)",
           "Hyper-V Virtual Ethernet Adapter", 6)
WSL = ("172.31.240.1", "vEthernet (WSL)", "Hyper-V Virtual Ethernet Adapter #2", 6)
DEFAULT_SWITCH = ("172.30.16.1", "vEthernet (Default Switch)",
                  "Hyper-V Virtual Ethernet Adapter #3", 6)
VPN = ("10.99.0.5", "Tunel", "WireGuard Tunnel", 53)
SLUCKA = ("127.0.0.1", "Loopback Pseudo-Interface 1", "Software Loopback Interface 1", 24)


def _zdroj(*adaptery):
    return lambda: list(adaptery)


# --------------------------------------------------------------------------
# druh_adaptera - one adapter
# --------------------------------------------------------------------------

@pytest.mark.parametrize("meno, popis, typ, druh", [
    (HOTSPOT[1], HOTSPOT[2], HOTSPOT[3], H),
    ("Local Area Connection* 3", "Microsoft Wi-Fi Direct Virtual Adapter", None, H),
    # fallback without a description (psutil): an asterisk and a number in the
    # name, in every language
    ("Pripojenie k miestnej sieti* 12", "", None, H),
    (WIFI[1], WIFI[2], WIFI[3], F),
    (ETHERNET[1], ETHERNET[2], ETHERNET[3], F),
    (WSL[1], WSL[2], WSL[3], V),
    (DEFAULT_SWITCH[1], DEFAULT_SWITCH[2], DEFAULT_SWITCH[3], V),
    # an external switch is virtual BY ITSELF - only `druhy_adries` judges the
    # home network (it needs the default route and the other adapters)
    (EXTERNY[1], EXTERNY[2], EXTERNY[3], V),
    (VPN[1], VPN[2], VPN[3], V),
    ("Ethernet 3", "TAP-Windows Adapter V9", None, V),
    (SLUCKA[1], SLUCKA[2], SLUCKA[3], V),
])
def test_druh_adaptera(meno, popis, typ, druh):
    assert netinfo.druh_adaptera(meno, popis, typ) == druh
    assert netinfo.je_virtualny_adapter(meno, popis, typ) is (druh == V)


def test_hviezdicka_bez_cisla_ani_s_popisom_nie_je_hotspot():
    # a name with an asterisk counts only without a description - with one,
    # the description decides
    assert netinfo.druh_adaptera("Ethernet* 2", "Generic Gigabit Ethernet Controller") == F
    assert netinfo.druh_adaptera("Siet*", "") == F


# --------------------------------------------------------------------------
# druhy_adries - the whole computer
# --------------------------------------------------------------------------

def test_hotspot_je_dosiahnutelny_a_bez_varovania():
    zdroj = _zdroj(WIFI, HOTSPOT, VPN)
    druhy = netinfo.druhy_adries(zdroj, preferovana=WIFI[0])
    assert druhy == {WIFI[0]: F, HOTSPOT[0]: H, VPN[0]: V}
    assert netinfo.virtualne_adresy(zdroj, WIFI[0]) == {VPN[0]}
    assert netinfo.hotspot_adresy(zdroj, WIFI[0]) == {HOTSPOT[0]}
    # order in the guide: the hotspot does not go to the end after the VPN
    poradie = netinfo.local_ip_candidates(
        virtualne=netinfo.virtualne_adresy(zdroj, WIFI[0]), preferovana=WIFI[0],
        vsetky=[VPN[0], HOTSPOT[0], WIFI[0]])
    assert poradie == [WIFI[0], HOTSPOT[0], VPN[0]]


def test_externy_prepinac_s_domacou_sietou_je_fyzicky():
    zdroj = _zdroj(EXTERNY, WSL, SLUCKA)
    druhy = netinfo.druhy_adries(zdroj, preferovana=EXTERNY[0])
    assert druhy[EXTERNY[0]] == F
    assert druhy[WSL[0]] == V and druhy[SLUCKA[0]] == V
    assert netinfo.virtualne_adresy(zdroj, EXTERNY[0]) == {WSL[0], SLUCKA[0]}


def test_externy_prepinac_len_ked_drzi_cestu_von():
    zdroj = _zdroj(EXTERNY, WIFI)
    # Wi-Fi holds the route out -> vEthernet is just another virtual adapter
    assert netinfo.druhy_adries(zdroj, preferovana=WIFI[0])[EXTERNY[0]] == V
    # with an injected source and no default route the OS is not asked -
    # virtual applies
    assert netinfo.druhy_adries(_zdroj(EXTERNY))[EXTERNY[0]] == V


def test_externy_prepinac_nie_ked_ma_siet_aj_fyzicky_adapter():
    zdroj = _zdroj(EXTERNY, ETHERNET)           # both in 192.168.250.0/24
    assert netinfo.druhy_adries(zdroj, preferovana=EXTERNY[0])[EXTERNY[0]] == V


@pytest.mark.parametrize("adapter", [WSL, DEFAULT_SWITCH, VPN])
def test_vnutorne_siete_a_vpn_ostavaju_oznacene_aj_s_cestou_von(adapter):
    """WSL and "Default Switch" are internal networks with NAT, a VPN is not a
    Hyper-V switch - even when they hold the default route on a private
    network."""
    druhy = netinfo.druhy_adries(_zdroj(adapter), preferovana=adapter[0])
    assert druhy[adapter[0]] == V


def test_externy_prepinac_na_verejnej_adrese_nie():
    verejny = ("203.0.113.5", EXTERNY[1], EXTERNY[2], EXTERNY[3])
    assert netinfo.druhy_adries(_zdroj(verejny), preferovana=verejny[0])[verejny[0]] == V


def test_adresa_s_fyzickym_aj_hotspotom_je_fyzicka():
    dvojita = ("192.0.2.10", "Wi-Fi", "Generic Wireless Adapter", 71)
    assert netinfo.druhy_adries(_zdroj(HOTSPOT, dvojita))["192.0.2.10"] == F


def test_pokazeny_zdroj_nic_nevyhodi():
    def zle():
        raise OSError("ziadne adaptery")
    assert netinfo.druhy_adries(zle) == {}
    assert netinfo.hotspot_adresy(zle) == set()


# --------------------------------------------------------------------------
# Tags in the pairing window
# --------------------------------------------------------------------------

def test_dalsie_adresy_nesu_svoj_stitok():
    riadok = netinfo.pairing_other_ips(
        [HOTSPOT[0], VPN[0], WIFI[0]], True, virtualne={VPN[0]}, stitok="(VPN)",
        hotspot={HOTSPOT[0]}, stitok_hotspot="(hotspot)")
    assert riadok == "192.0.2.10 (hotspot),  10.99.0.5 (VPN),  192.168.250.20"


def test_okno_parovania_ukaze_hotspot_bez_varovania():
    zdroj = zdroj_suboru("ui_dialogs.py")
    assert "self._hotspoty = self._hotspot_ips()" in zdroj
    blok = zdroj[zdroj.index("elif ip in self._hotspoty:"):]
    blok = blok[:blok.index("if len(candidates) > 1:")]
    assert 'tr("hr.ip_hotspot")' in blok and 'pal["text_dim"]' in blok
    assert "hr.ip_virtual_note" not in blok and 'pal["warn"]' not in blok
    assert "stitok_hotspot=tr(\"hr.ip_hotspot\")" in zdroj
