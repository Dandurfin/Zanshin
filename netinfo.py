"""Adresy tohto PC v lokalnej sieti - pre parovanie hodiniek.

Preco samostatny modul
----------------------
Hrac musi do telefonu prepisat IP tohto pocitaca. Stroj s Wi-Fi + Ethernet
+ VPN (+ Hyper-V/WSL virtualne adaptery) ma ale IP viacero a "ta spravna"
je ta, na ktorej su hodinky/telefon - to appka nevie uhadnut. Preto:

  * `preferred_local_ip()` - adresa, cez ktoru by OS poslal paket von
    (typicky Wi-Fi/Ethernet s default route). Nikam sa nic neposiela: UDP
    socket sa len "pripoji" (co pri UDP znamena iba vyber zdrojovej adresy)
    a precita sa jeho vlastna adresa.
  * `local_ip_candidates()` - VSETKY IPv4 adresy stroja bez loopbacku a
    APIPA (169.254.x.x - "nedostal som DHCP", tam hodinky nikdy nie su),
    preferovana prva, potom sukromne rozsahy (192.168 / 10 / 172.16-31),
    potom zvysok. UI ukaze prvu velkym a ostatne ako "alebo".

Ziadny modul appky nepocuva na konkretnej IP natvrdo - server pocuva na
0.0.0.0 (vsetky siete), toto je len napoveda pre cloveka.
"""

import ipaddress
import socket


def _is_usable(ip):
    try:
        addr = ipaddress.IPv4Address(ip)
    except Exception:
        return False
    return not (addr.is_loopback or addr.is_link_local or addr.is_unspecified
                or addr.is_multicast)


def preferred_local_ip():
    """IPv4, ktoru by OS pouzil pre odchadzajuce spojenie; None ak sa neda."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))     # UDP connect = ziadny paket
        ip = sock.getsockname()[0]
        return ip if _is_usable(ip) else None
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _all_host_ips():
    ips = []
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def local_ip_candidates():
    """Zoznam IPv4 adries tohto PC, preferovana prva; prazdny ak nic."""
    preferred = preferred_local_ip()
    others = [ip for ip in _all_host_ips() if _is_usable(ip) and ip != preferred]
    others.sort(key=lambda ip: (0 if ipaddress.IPv4Address(ip).is_private else 1, ip))
    out = ([preferred] if preferred else []) + others
    return out
