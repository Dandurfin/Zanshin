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
import re
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


def local_ip_candidates(virtualne=None, preferovana=None, vsetky=None):
    """Zoznam IPv4 adries tohto PC, ta s najvacsou sancou prva; prazdny ak nic.

    PORADIE (0.2.2, audit 4): fyzicke adaptery pred VPN a virtualnymi
    (`virtualne_adresy`) - so zapnutou VPN ide predvolena cesta von cez
    tunel a dialog parovania ukazoval adresu, na ktoru sa hodinky nikdy
    nedostanu. Medzi rovnakymi potom adresa predvolenej cesty, potom
    domace rozsahy 192.168.* > 10.* > 172.16-31.*, potom zvysok.

    `virtualne` (mnozina IP), `preferovana` a `vsetky` sa daju vlozit
    (testy); predvolene sa pyta OS."""
    preferred = preferred_local_ip() if preferovana is None else preferovana
    if virtualne is None:
        virtualne = virtualne_adresy()
    zdroj = _all_host_ips() if vsetky is None else list(vsetky)
    if preferred and preferred not in zdroj:
        zdroj = [preferred] + zdroj
    ips = []
    for ip in zdroj:
        if _is_usable(ip) and ip not in ips:
            ips.append(ip)
    ips.sort(key=lambda ip: (1 if ip in virtualne else 0,
                             0 if ip == preferred else 1,
                             _poradie_rozsahu(ip), ip))
    return ips


def _poradie_rozsahu(ip):
    """192.168.* (domaca Wi-Fi) < 10.* < 172.16-31.* < ostatne sukromne <
    verejne. Hodinky su takmer vzdy v domacej sieti."""
    try:
        addr = ipaddress.IPv4Address(ip)
    except Exception:
        return 9
    if addr in ipaddress.IPv4Network("192.168.0.0/16"):
        return 0
    if addr in ipaddress.IPv4Network("10.0.0.0/8"):
        return 1
    if addr in ipaddress.IPv4Network("172.16.0.0/12"):
        return 2
    return 3 if addr.is_private else 4


# ---------------------------------------------------------------------------
# VPN a virtualne adaptery (0.2.2, audit 4)
# ---------------------------------------------------------------------------
#
# PRECO: hodinky (telefon) su v domacej Wi-Fi. Adresa VPN tunela, Hyper-V /
# WSL prepinaca ci VirtualBoxu je z nich nedosiahnutelna - a appka ju aj
# tak ukazovala ako "adresu tohto PC". Adapter sa posudzuje podla mena,
# popisu a typu rozhrania z Windowsu (`_adaptery_windows`). Bezne "Ethernet"
# / "Wi-Fi" / "Realtek PCIe GbE" / "Intel Wi-Fi 6" sa NEOZNACIA - slova
# kratsie nez styri znaky sa hladaju len ako cele slova.

_VIRTUALNE_SLOVA = (
    "wireguard", "wintun", "tailscale", "zerotier", "nordlynx", "openvpn",
    "hamachi", "radmin", "hyper-v", "vethernet", "virtualbox", "vmware",
    "vmnet", "loopback", "pseudo-interface", "teredo", "isatap", "npcap",
    "docker", "virtual", "proton", "mullvad", "expressvpn", "surfshark",
    "anyconnect", "fortinet", "forticlient", "globalprotect", "pangp",
    "softether", "cloudflare", "tap-windows", "tap-nordvpn", "tunnel",
)
_VIRTUALNE_CELE_SLOVA = re.compile(r"(?<![a-z0-9])(?:tap|tun|tun\d+|wg\d*|wsl|vpn|"
                                   r"vbox|utun\d*|ppp\d*|warp)(?![a-z0-9])")
# Typy rozhrania z Windowsu (IFTYPE): softverova slucka, tunel, "proprietary
# virtual" (Wintun/WireGuard, TAP, Hamachi), PPP (stare VPN).
_VIRTUALNE_TYPY = frozenset({24, 131, 53, 23})


def je_virtualny_adapter(meno="", popis="", typ=None):
    """Je adapter VPN alebo virtualny (hodinky sa nan nedostanu)? Cista
    funkcia - meno ("Ethernet 2", "vEthernet (WSL)"), popis z Windowsu
    ("TAP-Windows Adapter V9") a typ rozhrania (IFTYPE) alebo None."""
    try:
        if typ is not None and int(typ) in _VIRTUALNE_TYPY:
            return True
    except (TypeError, ValueError):
        pass
    text = f"{meno or ''} {popis or ''}".lower()
    if any(slovo in text for slovo in _VIRTUALNE_SLOVA):
        return True
    return bool(_VIRTUALNE_CELE_SLOVA.search(text))


def _adaptery_windows():
    """[(ip, meno, popis, typ)] IPv4 adries zapnutych adapterov z
    GetAdaptersAddresses (iphlpapi). Nikam sa nic neposiela - len sa pyta
    Windowsu. Mimo Windowsu alebo pri chybe []."""
    import sys
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    class _SOCKET_ADDRESS(ctypes.Structure):
        _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]

    class _UNICAST(ctypes.Structure):
        pass
    _UNICAST._fields_ = [("Length", wintypes.ULONG), ("Flags", wintypes.DWORD),
                         ("Next", ctypes.POINTER(_UNICAST)),
                         ("Address", _SOCKET_ADDRESS)]

    class _ADAPTER(ctypes.Structure):
        pass
    _ADAPTER._fields_ = [
        ("Length", wintypes.ULONG), ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(_ADAPTER)), ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.POINTER(_UNICAST)),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p), ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.ULONG), ("Flags", wintypes.ULONG),
        ("Mtu", wintypes.ULONG), ("IfType", wintypes.DWORD),
        ("OperStatus", ctypes.c_int)]

    iphlpapi = ctypes.WinDLL("iphlpapi")
    fn = iphlpapi.GetAdaptersAddresses
    fn.argtypes = [wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG)]
    fn.restype = wintypes.ULONG
    af_inet, skip = 2, 0x2 | 0x4 | 0x8          # bez anycast/multicast/DNS
    velkost = wintypes.ULONG(16 * 1024)
    for _pokus in range(3):
        buf = ctypes.create_string_buffer(velkost.value)
        vysledok = fn(af_inet, skip, None, buf, ctypes.byref(velkost))
        if vysledok == 0:
            break
        if vysledok != 111:                      # ERROR_BUFFER_OVERFLOW
            return []
    else:
        return []
    out = []
    adapter = ctypes.cast(buf, ctypes.POINTER(_ADAPTER))
    while adapter:
        a = adapter.contents
        if a.OperStatus == 1:                    # IfOperStatusUp
            adresa = a.FirstUnicastAddress
            while adresa:
                sa = adresa.contents.Address
                if sa.lpSockaddr and sa.iSockaddrLength >= 8:
                    surove = ctypes.string_at(sa.lpSockaddr, 8)
                    if surove[0] == af_inet:     # sockaddr_in.sin_family (LE)
                        ip = socket.inet_ntoa(surove[4:8])
                        out.append((ip, a.FriendlyName or "", a.Description or "",
                                    int(a.IfType)))
                adresa = adresa.contents.Next
        adapter = a.Next
    return out


def _adaptery_psutil():
    """Zaloha bez Windowsu/ctypes: len mena adapterov (bez popisu a typu)."""
    try:
        import psutil
        out = []
        for meno, adresy in psutil.net_if_addrs().items():
            for adresa in adresy:
                if adresa.family == socket.AF_INET:
                    out.append((adresa.address, meno, "", None))
        return out
    except Exception:
        return []


_CACHE_ADAPTEROV = {"cas": 0.0, "hodnota": None}
_CACHE_ADAPTEROV_S = 30.0


def adaptery(zdroj=None):
    """[(ip, meno, popis, typ, virtualny)] - IPv4 adresy s adapterom.

    Vysledok z Windowsu plati 30 s (pole IP v Nastaveniach sa pyta pri
    kazdom pismene). `zdroj()` sa da vlozit (testy). Ziadna chyba von nejde."""
    import time as _time
    if zdroj is None:
        teraz = _time.monotonic()
        if (_CACHE_ADAPTEROV["hodnota"] is not None
                and teraz - _CACHE_ADAPTEROV["cas"] < _CACHE_ADAPTEROV_S):
            return list(_CACHE_ADAPTEROV["hodnota"])
        try:
            surove = _adaptery_windows() or _adaptery_psutil()
        except Exception:
            surove = _adaptery_psutil()
    else:
        try:
            surove = list(zdroj() or ())
        except Exception:
            surove = []
    out = []
    for ip, meno, popis, typ in surove:
        out.append((ip, meno, popis, typ, je_virtualny_adapter(meno, popis, typ)))
    if zdroj is None:
        _CACHE_ADAPTEROV.update(cas=_time.monotonic(), hodnota=list(out))
    return out


def virtualne_adresy(zdroj=None):
    """Mnozina IPv4 adries, ktore patria VPN alebo virtualnemu adapteru.
    Adresa, ktoru ma aj fyzicky adapter, medzi ne nepatri."""
    zoznam = adaptery(zdroj)
    fyzicke = {z[0] for z in zoznam if not z[4]}
    return {z[0] for z in zoznam if z[4] and z[0] not in fyzicke}


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


# Kandidati na adresu vo volnom texte. Ci to naozaj adresa je, rozhodne az
# `ipaddress` - cas "12:34:56" ani verzia "0.2.2" sa tak nezamaskuju.
# Okolie strazi len dalsie cislo ("1.2.3.4.5" nie je adresa), nie samotnu
# bodku - adresa na konci vety ("... z 10.0.0.5.") sa musi zamaskovat tiez.
_IPV4_V_TEXTE = re.compile(r"(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)")
_IPV6_V_TEXTE = re.compile(
    r"(?<![0-9A-Fa-f:])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![0-9A-Fa-f:])")


def _maskuj_zhodu(zhoda):
    kus = zhoda.group(0)
    try:
        ipaddress.ip_address(kus)
    except ValueError:
        return kus
    return mask_ip(kus)


def mask_ips_in_text(text):
    """Hotovy riadok textu bez adries - pre subor logu.

    Riadky dennika ukazuju adresu cez `ip_for_screen`, cize po "Ukazat IP"
    v nich je cela. Ked taky riadok musi ist do app.log (dennik v okne uz
    nie je, viz `DandurfApp.log`), adresa tam nesmie - PRIVACY.md slubuje,
    ze app.log adresu PC neobsahuje. IPv4 ide prva, aby z "::ffff:a.b.c.d"
    neostala cast adresy."""
    if not text:
        return text
    text = _IPV4_V_TEXTE.sub(_maskuj_zhodu, str(text))
    return _IPV6_V_TEXTE.sub(_maskuj_zhodu, text)


def pairing_address(ip, port, show=False, stitok=""):
    """Hlavny riadok okna parovania "adresa   :   port". Port nie je
    citlivy (4455 ma kazdy), ostava viditelny aj pri skrytej adrese.

    `stitok` (0.2.2) ide za port - "(VPN/virtualny)", ked adresa patri
    virtualnemu adapteru. Nic o adrese neprezradi, preto aj pri skrytej."""
    riadok = f"{ip_for_screen(ip, show)}   :   {port}"
    return f"{riadok}  {stitok}" if stitok else riadok


def pairing_other_ips(ips, show=False, virtualne=(), stitok=""):
    """Riadok "dalsie adresy tohto PC" - kazda skryta rovnako ako hlavna.
    Adresa z `virtualne` dostane za seba `stitok` (0.2.2)."""
    kusy = []
    for ip in ips or ():
        kus = str(ip_for_screen(ip, show))
        if stitok and ip in (virtualne or ()):
            kus = f"{kus} {stitok}"
        kusy.append(kus)
    return ",  ".join(kusy)


def entry_mask(value, show=False):
    """Hodnota `show=` pre pole IP v Nastaveniach: "" = citatelne.

    Skryva sa len skutocna adresa. Prazdne pole a 0.0.0.0 ostavaju
    citatelne - tam nie je co prezradit a hrac musi vidiet, ze tam je
    bezpecna predvolba."""
    return "" if show or not _je_adresa(value) else ZNAK_MASKY
