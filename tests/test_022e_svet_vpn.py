# -*- coding: utf-8 -*-
"""Svet pocas relacie a VPN/virtualne adaptery (0.2.2, davka 4).

* Prepnutie Hra <-> Praca pocas sledovania meni len pohlad: relacia aj jej
  pripomienky ostavaju vo svete, v ktorom zacala; dennik to povie raz.
* Adresa PC pre hodinky: fyzicky adapter pred VPN/virtualnym, virtualne
  nesu stitok a pod adresou je veta. Bezne "Ethernet"/"Wi-Fi" nie su
  virtualne. Len vymyslene adaptery a dokumentacne adresy (192.0.2.x...)."""
import pytest

import app as app_mod
import netinfo
import rebrik
from i18n import tr

# --------------------------------------------------------------------------
# Svet relacie
# --------------------------------------------------------------------------


def _appka(svet="work", svet_relacie="play", otvorena=True):
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.cue_style = rebrik.STYL_HLAS
    a.world = svet
    a._session_world = svet_relacie
    a._hr_session_open = otvorena
    return a


def test_hlas_pocas_relacie_ide_za_svetom_relacie():
    # hra zacala v Hre, hrac sa pozrel na Pracu - pripomienky stale hovoria
    assert _appka("work", "play")._hlasky_hovoria() is True
    # zacala v Praci, prepol na Hru - stale len obrazom
    assert _appka("play", "work")._hlasky_hovoria() is False
    # bez relacie plati zobrazeny svet
    assert _appka("work", "play", otvorena=False)._hlasky_hovoria() is False
    assert _appka("play", "work", otvorena=False)._hlasky_hovoria() is True


def _na_prepnutie(otvorena=True, svet_relacie="play"):
    a = _appka("play", svet_relacie, otvorena)
    a.denn = []
    a.log = a.denn.append
    a.theme_key = "sumi"
    for meno in ("on_theme_switch", "save_settings", "_sync_world_switches",
                 "_refresh_history_page", "_refresh_dnes_stats", "run_hr_analysis",
                 "schedule_pregenerate", "_sync_world_nazvy"):
        setattr(a, meno, lambda *_x, **_k: None)
    return a


def test_prepnutie_sveta_pocas_relacie_povie_jeden_riadok():
    a = _na_prepnutie()
    a.set_world("work")
    assert a.world == "work" and a._session_world == "play"
    assert a.denn == [tr("log.world_switch_session", world=tr("world.play"),
                         new=tr("world.work"))]
    # spat do sveta relacie: nic nove sa nehovori
    a.set_world("play")
    assert len(a.denn) == 1


def test_prepnutie_bez_relacie_nic_nehovori():
    a = _na_prepnutie(otvorena=False)
    a.set_world("work")
    assert a.denn == []


def test_relacia_peceti_svet_pri_otvoreni():
    from _zdroj_appky import zdroj_metody
    assert "self._session_world = self.world" in zdroj_metody("_open_hr_session")
    assert 'summary["world"] = getattr(self, "_session_world"' in zdroj_metody(
        "_suhrn_relacie")


# --------------------------------------------------------------------------
# VPN a virtualne adaptery
# --------------------------------------------------------------------------

@pytest.mark.parametrize("meno, popis, typ", [
    ("Ethernet 2", "TAP-Windows Adapter V9", 6),
    ("OpenVPN Data Channel Offload", "OpenVPN Data Channel Offload", 6),
    ("WireGuard tunel", "WireGuard Tunnel", 53),
    ("Tailscale", "Tailscale Tunnel", 53),
    ("ZeroTier One [8056c2e21c000001]", "ZeroTier Virtual Port", 6),
    ("NordLynx", "NordLynx Tunnel", 53),
    ("Hamachi", "LogMeIn Hamachi Virtual Ethernet Adapter", 6),
    ("Radmin VPN", "Famatech Radmin VPN Ethernet Adapter", 6),
    ("vEthernet (Default Switch)", "Hyper-V Virtual Ethernet Adapter", 6),
    ("vEthernet (WSL)", "Hyper-V Virtual Ethernet Adapter #2", 6),
    ("Ethernet 3", "VirtualBox Host-Only Ethernet Adapter", 6),
    ("VMware Network Adapter VMnet8", "VMware Virtual Ethernet Adapter for VMnet8", 6),
    ("Loopback Pseudo-Interface 1", "Software Loopback Interface 1", 24),
    ("Neznamy", "", 131),
    ("Lokalne pripojenie", "Wintun Userspace Tunnel", None),
    ("wg0", "", None),
    ("tun0", "", None),
    ("ProtonVPN", "", None),
])
def test_virtualne_adaptery(meno, popis, typ):
    assert netinfo.je_virtualny_adapter(meno, popis, typ) is True


@pytest.mark.parametrize("meno, popis, typ", [
    ("Ethernet", "Realtek PCIe GbE Family Controller", 6),
    ("Wi-Fi", "Intel(R) Wi-Fi 6E AX211 160MHz", 71),
    ("Wi-Fi 2", "Killer(R) Wi-Fi 6 AX1650i 160MHz Wireless Network Adapter (201NGW)", 71),
    ("Ethernet", "Intel(R) Ethernet Connection (17) I219-LM", 6),
    ("Ethernet 4", "Remote NDIS Compatible Device", 6),
    ("Conexión de red Bluetooth", "Bluetooth Device (Personal Area Network)", 6),
    ("Ethernet", "", None),
    ("Wi-Fi", "", None),
    ("", "", None),
])
def test_bezne_adaptery_nie_su_virtualne(meno, popis, typ):
    assert netinfo.je_virtualny_adapter(meno, popis, typ) is False


def test_fyzicka_adresa_ide_pred_vpn_aj_ked_vpn_drzi_cestu_von():
    vpn, wifi, docker = "10.8.0.6", "192.168.1.23", "172.17.0.1"
    poradie = netinfo.local_ip_candidates(
        virtualne={vpn, docker}, preferovana=vpn, vsetky=[docker, vpn, wifi, "127.0.0.1"])
    assert poradie == [wifi, vpn, docker]


def test_domaca_wifi_pred_inymi_rozsahmi():
    poradie = netinfo.local_ip_candidates(
        virtualne=set(), preferovana="",
        vsetky=["172.20.1.5", "10.0.0.7", "192.168.0.10", "198.51.100.3", "169.254.3.3"])
    assert poradie == ["192.168.0.10", "10.0.0.7", "172.20.1.5", "198.51.100.3"]


def test_virtualne_adresy_z_vlozeneho_zdroja():
    zdroj = lambda: [("192.0.2.10", "Ethernet", "Realtek PCIe GbE Family Controller", 6),
                     ("198.51.100.7", "Tailscale", "Tailscale Tunnel", 53),
                     ("203.0.113.4", "vEthernet (WSL)", "Hyper-V Virtual Ethernet Adapter", 6)]
    assert netinfo.virtualne_adresy(zdroj) == {"198.51.100.7", "203.0.113.4"}
    # adresa, ktoru ma aj fyzicky adapter, sa neoznaci
    dvojita = lambda: [("192.0.2.10", "Ethernet", "", 6), ("192.0.2.10", "Tailscale", "", 53)]
    assert netinfo.virtualne_adresy(dvojita) == set()
    # chyba zdroja = ziadne virtualne, ziadna vynimka
    def zle():
        raise OSError("iphlpapi nejde")
    assert netinfo.virtualne_adresy(zle) == set()


def test_stitok_v_okne_parovania_neprezradi_adresu():
    stitok = tr("hr.ip_virtual")
    assert netinfo.pairing_address("198.51.100.7", 4455, show=False, stitok=stitok) == (
        f"{netinfo.MASKA_IPV4}   :   4455  {stitok}")
    assert netinfo.pairing_address("192.0.2.10", 4455, show=True) == "192.0.2.10   :   4455"
    riadok = netinfo.pairing_other_ips(["192.0.2.10", "198.51.100.7"], show=True,
                                       virtualne={"198.51.100.7"}, stitok=stitok)
    assert riadok == f"192.0.2.10,  198.51.100.7 {stitok}"


class _Label:
    def __init__(self, text):
        self.text = text

    def cget(self, _k):
        return self.text

    def configure(self, **k):
        self.text = k.get("text", self.text)


def test_pole_ip_v_nastaveniach_upozorni_na_virtualnu_adresu():
    a = app_mod.DandurfApp.__new__(app_mod.DandurfApp)
    a.hr_ip_hint_label = _Label(tr("settings.hr_ip_hint"))
    assert a._hr_ip_virtual_hint("198.51.100.7", virtualne={"198.51.100.7"}) is True
    assert a.hr_ip_hint_label.text == (tr("settings.hr_ip_hint") + "\n"
                                       + tr("settings.hr_ip_virtual_note"))
    assert a._hr_ip_virtual_hint("0.0.0.0", virtualne={"198.51.100.7"}) is False
    assert a.hr_ip_hint_label.text == tr("settings.hr_ip_hint")


def test_okno_parovania_ukaze_vetu_pod_virtualnou_adresou():
    from _zdroj_appky import zdroj_suboru
    zdroj = zdroj_suboru("ui_dialogs.py")
    assert "self._virtualne = self._virtual_ips()" in zdroj
    assert 'tr("hr.ip_virtual_note")' in zdroj
    # Stitok hlavnej adresy je od skeptika UX vlastny riadok pod adresou, nie
    # koniec riadku mono 20 (tam sa orezal a vytlacil "Ukazat IP") - spravanie
    # stazi tests/test_022e_ux_skeptik.py.
    assert "self.ip_virtual_label = ctk.CTkLabel(" in zdroj
    assert 'net_in, text=tr("hr.ip_virtual")' in zdroj
