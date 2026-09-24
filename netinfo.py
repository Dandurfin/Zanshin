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

Skryta IP (0.2)
---------------
IP adresa PC sa na obrazovke NEUKAZE sama. Streamer ma okno appky casto
priamo na streame a tester posiela screenshoty - lokalna adresa tam nema co
robit. Okno parovania, pole IP v Nastaveniach aj riadky v denniku appky ju
preto ukazuju zamaskovanu (`mask_ip`), kym si ju hrac neodkryje tlacidlom
"Ukazat IP". Odkrytie plati len do restartu appky: `app.show_ip` je len v
pamati a do nastaveni sa nezapisuje.
"""

import ipaddress
import socket

# "Pocuvaj na vsetkych sietach" - nie je to adresa tohto PC, takze sa
# neskryva (rada "v nastaveniach nechaj 0.0.0.0" ju potrebuje ukazat).
ANY = "0.0.0.0"
MASKA_IPV4 = "•••.•••.•••.•••"
MASKA = "•••"
# Znak, ktorym CTkEntry kresli skryte pole (ako pri hesle).
ZNAK_MASKY = "•"


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


# ---------------------------------------------------------------------------
# Skryta IP - co sa smie ukazat na obrazovke
# ---------------------------------------------------------------------------

def _je_adresa(ip):
    """Skutocna adresa, ktoru treba skryt - nie prazdno ani 0.0.0.0."""
    return ip is not None and str(ip).strip() not in ("", ANY)


def mask_ip(ip):
    """IP adresa tak, ako sa ukaze, kym si ju hrac neodkryje.

    "", None a "0.0.0.0" sa vracaju bez zmeny: 0.0.0.0 nie je adresa PC,
    len "pocuvaj vsade", a rada "nechaj 0.0.0.0" ju potrebuje vidiet.
    IPv4 -> bodky v tvare adresy (hrac vidi, ze tam adresa je), cokolvek
    ine (IPv6, meno) -> len •••, aby maska neprezradila ani dlzku.
    """
    if not _je_adresa(ip):
        return ip
    try:
        ipaddress.IPv4Address(str(ip).strip())
    except ValueError:
        return MASKA
    return MASKA_IPV4


def ip_for_screen(ip, show=False):
    """Adresa pre okno aj dennik: cela len ked si ju hrac odkryl."""
    return ip if show else mask_ip(ip)


def pairing_address(ip, port, show=False):
    """Hlavny riadok okna parovania "adresa   :   port". Port nie je
    citlivy (4455 ma kazdy), ostava viditelny aj pri skrytej adrese."""
    return f"{ip_for_screen(ip, show)}   :   {port}"


def pairing_other_ips(ips, show=False):
    """Riadok "dalsie adresy tohto PC" - kazda skryta rovnako ako hlavna."""
    return ",  ".join(str(ip_for_screen(ip, show)) for ip in (ips or ()))


def entry_mask(value, show=False):
    """Hodnota `show=` pre pole IP v Nastaveniach: "" = citatelne.

    Skryva sa len skutocna adresa. Prazdne pole a 0.0.0.0 ostavaju
    citatelne - tam nie je co prezradit a hrac musi vidiet, ze tam je
    bezpecna predvolba."""
    return "" if show or not _je_adresa(value) else ZNAK_MASKY
