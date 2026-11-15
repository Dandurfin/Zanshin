"""Addresses of this PC on the local network - for pairing the watch.

Why a separate module
---------------------
The player has to type the IP of this computer into the phone. A machine
with Wi-Fi + Ethernet + VPN (+ Hyper-V/WSL virtual adapters) has several
IPs, though, and "the right one" is the one the phone is on (the app on it
sends the heart rate from the watch) - the app cannot guess that. So:

  * `preferred_local_ip()` - the address through which the OS would send a
    packet out (typically Wi-Fi/Ethernet with the default route). Nothing
    is sent anywhere: a UDP socket only gets "connected" (which for UDP
    only means choosing the source address) and its own address is read.
  * `local_ip_candidates()` - ALL IPv4 addresses of the machine except
    loopback and APIPA (169.254.x.x - "I did not get DHCP", the phone is
    never there), the preferred one first, then the private ranges
    (192.168 / 10 / 172.16-31), then the rest. The UI shows the first one
    big and the others as "or".

No module of the app listens on a specific hard-coded IP - the server
listens on 0.0.0.0 (all networks), this is just a hint for a human.

Hidden IP (0.2)
---------------
The PC's IP address is NOT shown on screen by itself. A streamer often has
the app window right on the stream and a tester sends screenshots - the
local address has no business being there. The pairing window, the IP
field in Settings and the lines in the app journal therefore show it
masked (`mask_ip`) until the player reveals it with the "Show IP" button.
Revealing lasts only until the app restarts: `app.show_ip` is in memory
only and is not written into the settings.
"""

import ipaddress
import re
import socket

# "Listen on all networks" - it is not an address of this PC, so it is
# not hidden (the tip "leave 0.0.0.0 in the settings" needs to show it).
ANY = "0.0.0.0"
MASKA_IPV4 = "•••.•••.•••.•••"
MASKA = "•••"
# The character CTkEntry uses to draw a hidden field (as with a password).
ZNAK_MASKY = "•"


def _is_usable(ip):
    try:
        addr = ipaddress.IPv4Address(ip)
    except Exception:
        return False
    return not (addr.is_loopback or addr.is_link_local or addr.is_unspecified
                or addr.is_multicast)


def preferred_local_ip():
    """IPv4 the OS would use for outgoing connections; None if impossible."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))     # UDP connect = no packet
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
    """IPv4 addresses of this PC, the likeliest first; empty if none.

    ORDER (0.3, audit 4): physical adapters before VPN and virtual ones
    (`virtualne_adresy`) - with a VPN on, the default route goes out
    through the tunnel and the pairing dialog showed an address the phone
    can never reach. Among equals then the default-route address, then the
    home ranges 192.168.* > 10.* > 172.16-31.*, then the rest.

    `virtualne` (a set of IPs), `preferovana` and `vsetky` can be injected
    (tests); by default the OS is asked."""
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
    """192.168.* (home Wi-Fi) < 10.* < 172.16-31.* < other private < public.
    The phone is almost always on the home network."""
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
# VPN and virtual adapters (0.3, audit 4)
# ---------------------------------------------------------------------------
#
# WHY: the phone (the app that sends the heart rate from the watch) is on
# the home Wi-Fi. The address of a VPN tunnel, a Hyper-V / WSL switch or
# VirtualBox cannot be reached from it - and the app still showed it as
# "the address of this PC". An adapter is judged by the name, description
# and interface type from Windows (`_adaptery_windows`). The usual
# "Ethernet" / "Wi-Fi" / "Realtek PCIe GbE" / "Intel Wi-Fi 6" are NOT
# flagged - words shorter than four characters are only matched as whole
# words.

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
# Interface types from Windows (IFTYPE): software loopback, tunnel,
# "proprietary virtual" (Wintun/WireGuard, TAP, Hamachi), PPP (old VPNs).
_VIRTUALNE_TYPY = frozenset({24, 131, 53, 23})


# Kind of address (0.3 batch 4b). A hotspot is NOT virtual in the sense the
# player cares about: the Windows Mobile hotspot runs on the "Microsoft
# Wi-Fi Direct Virtual Adapter" (name "Local Area Connection* 10" and
# similar) and a phone connected to that hotspot can reach its address.
# The word "Virtual" in the description used to flag it "(VPN/virtual)",
# warning included.
FYZICKY, HOTSPOT, VIRTUALNY = "fyzicky", "hotspot", "virtualny"

_HOTSPOT_POPIS = re.compile(r"wi-?fi direct")
# "Local Area Connection* 10" - Windows gives the asterisk and a number to
# Wi-Fi Direct adapters in every language. Applies only when the
# description is missing (the psutil fallback).
_HOTSPOT_MENO = re.compile(r"\*\s*\d+\s*$")


def druh_adaptera(meno="", popis="", typ=None):
    """FYZICKY / HOTSPOT / VIRTUALNY for one adapter. A pure function - the
    name ("Ethernet 2", "vEthernet (WSL)"), the description from Windows
    ("TAP-Windows Adapter V9") and the interface type (IFTYPE) or None.

    The hotspot is judged FIRST: its description contains the word
    "Virtual". An external Hyper-V switch stays VIRTUALNY here - whether it
    holds the home network only `druhy_adries` knows (it needs the default
    route and the other adapters)."""
    text = f"{meno or ''} {popis or ''}".lower()
    if _HOTSPOT_POPIS.search(text) or (
            not (popis or "").strip() and _HOTSPOT_MENO.search(meno or "")):
        return HOTSPOT
    try:
        if typ is not None and int(typ) in _VIRTUALNE_TYPY:
            return VIRTUALNY
    except (TypeError, ValueError):
        pass
    if any(slovo in text for slovo in _VIRTUALNE_SLOVA):
        return VIRTUALNY
    return VIRTUALNY if _VIRTUALNE_CELE_SLOVA.search(text) else FYZICKY


def je_virtualny_adapter(meno="", popis="", typ=None):
    """Is the adapter a VPN or virtual (the phone cannot reach it)? A hotspot
    is not (`druh_adaptera`)."""
    return druh_adaptera(meno, popis, typ) == VIRTUALNY


def _je_externy_prepinac(meno="", popis=""):
    """A Hyper-V switch adapter ("vEthernet (...)") that MAY be external - i.e.
    bridged to the physical network card. WSL and "Default Switch" are
    always internal networks with NAT (the phone cannot reach them), Docker
    too."""
    text = f"{meno or ''} {popis or ''}".lower()
    if "vethernet" not in text and "hyper-v virtual ethernet" not in text:
        return False
    return not any(slovo in text for slovo in ("wsl", "default switch", "docker"))


_LAN_ROZSAHY = (ipaddress.IPv4Network("10.0.0.0/8"),
                ipaddress.IPv4Network("172.16.0.0/12"),
                ipaddress.IPv4Network("192.168.0.0/16"))


def _lan_siet(ip):
    """The home network of an address (/24 - the app does not read the Windows
    adapter mask), but only for private LAN ranges. Otherwise None."""
    try:
        addr = ipaddress.IPv4Address(ip)
    except Exception:
        return None
    if not any(addr in rozsah for rozsah in _LAN_ROZSAHY):
        return None
    return ipaddress.IPv4Network(f"{addr}/24", strict=False)


def _adaptery_windows():
    """[(ip, meno, popis, typ)] of the IPv4 addresses of enabled adapters from
    GetAdaptersAddresses (iphlpapi). Nothing is sent anywhere - Windows is
    only asked. Outside Windows or on an error []."""
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
    af_inet, skip = 2, 0x2 | 0x4 | 0x8          # no anycast/multicast/DNS
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
    """Fallback without Windows/ctypes: just names (no description or type)."""
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
    """[(ip, meno, popis, typ, virtualny)] - IPv4 addresses with their adapter.

    The result from Windows is valid for 30 s (the IP field in Settings asks
    on every letter). `zdroj()` can be injected (tests). No error gets out."""
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


def druhy_adries(zdroj=None, preferovana=None):
    """{ip: FYZICKY / HOTSPOT / VIRTUALNY} for the IPv4 addresses of this PC.

    An address that a physical adapter also has is physical; one that a
    hotspot has (and no physical adapter) is a hotspot.

    EXTERNAL HYPER-V SWITCH (0.3 batch 4b): when the player makes an
    external switch in Hyper-V, Windows bridges the physical network card
    to "vEthernet (...)" and the home address and the default route out are
    then held by that vEthernet - the physical card has no address. The
    phone can reach it, so such an address is taken as physical when: it
    belongs to a Hyper-V switch (not WSL nor "Default Switch"), it holds the
    default route (`preferovana`, otherwise the OS is asked), it is in a
    private LAN range and no physical adapter has an address in the same
    network. A VPN that holds the route out is not overridden - it is not a
    Hyper-V switch.

    With an injected `zdroj` (tests) the OS is not asked for the default
    route - without `preferovana` the external switch then does not apply."""
    zoznam = adaptery(zdroj)
    if preferovana is None and zdroj is None:
        preferovana = preferred_local_ip()
    podla_ip = {}
    for ip, meno, popis, typ, _virtualny in zoznam:
        podla_ip.setdefault(ip, []).append((meno, popis, druh_adaptera(meno, popis, typ)))
    out = {}
    for ip, zaznamy in podla_ip.items():
        druhy = {z[2] for z in zaznamy}
        out[ip] = (FYZICKY if FYZICKY in druhy
                   else HOTSPOT if HOTSPOT in druhy else VIRTUALNY)
    siet = _lan_siet(preferovana) if preferovana else None
    if siet is not None and out.get(preferovana) == VIRTUALNY and all(
            _je_externy_prepinac(meno, popis) for meno, popis, _d in podla_ip[preferovana]):
        fyzicka_v_sieti = any(druh == FYZICKY and _lan_siet(ip) == siet
                              for ip, druh in out.items())
        if not fyzicka_v_sieti:
            out[preferovana] = FYZICKY
    return out


def virtualne_adresy(zdroj=None, preferovana=None):
    """Set of IPv4 addresses that belong to a VPN or virtual adapter
    (`druhy_adries`). An address that a physical adapter also has, a
    hotspot or an external Hyper-V switch with the home network are not
    among them."""
    return {ip for ip, druh in druhy_adries(zdroj, preferovana).items()
            if druh == VIRTUALNY}


def hotspot_adresy(zdroj=None, preferovana=None):
    """Set of IPv4 addresses of the Windows Mobile hotspot (Wi-Fi Direct). A
    phone connected to the hotspot can reach them - they get the label
    "(hotspot)", not a warning."""
    return {ip for ip, druh in druhy_adries(zdroj, preferovana).items()
            if druh == HOTSPOT}


# ---------------------------------------------------------------------------
# Hidden IP - what may be shown on screen
# ---------------------------------------------------------------------------

def _je_adresa(ip):
    """A real address that has to be hidden - not empty, not 0.0.0.0."""
    return ip is not None and str(ip).strip() not in ("", ANY)


def mask_ip(ip):
    """The IP address as it is shown until the player reveals it.

    "", None and "0.0.0.0" are returned unchanged: 0.0.0.0 is not the PC's
    address, only "listen everywhere", and the tip "leave 0.0.0.0" needs to
    see it. IPv4 -> dots in the shape of the address (the player sees there
    is an address there), anything else (IPv6, a name) -> just •••, so that
    the mask does not give away even the length.
    """
    if not _je_adresa(ip):
        return ip
    try:
        ipaddress.IPv4Address(str(ip).strip())
    except ValueError:
        return MASKA
    return MASKA_IPV4


def ip_for_screen(ip, show=False):
    """Address for window and journal: full only if the player revealed it."""
    return ip if show else mask_ip(ip)


# Address candidates in free text. Whether it really is an address only
# `ipaddress` decides - so neither the time "12:34:56" nor the version
# "0.2.1" get masked. The context guards only against a further number
# ("1.2.3.4.5" is not an address), not against a dot on its own - an
# address at the end of a sentence ("... z 10.0.0.5.") must be masked too.
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
    """A finished line of text without addresses - for the log file.

    Journal lines show the address through `ip_for_screen`, so after
    "Show IP" it is in them in full. When such a line has to go to app.log
    (the in-window journal is no longer there, see `DandurfApp.log`), the
    address must not go there - PRIVACY.md promises that app.log does not
    contain the PC's address. IPv4 goes first, so that no part of the
    address is left of "::ffff:a.b.c.d"."""
    if not text:
        return text
    text = _IPV4_V_TEXTE.sub(_maskuj_zhodu, str(text))
    return _IPV6_V_TEXTE.sub(_maskuj_zhodu, text)


def pairing_address(ip, port, show=False, stitok=""):
    """The main line of the pairing window "address   :   port". The port is
    not sensitive (everyone has 4455), it stays visible even with a hidden
    address.

    `stitok` (0.3) goes after the port - "(VPN/virtual)" when the address
    belongs to a virtual adapter. It gives nothing away about the address,
    so it is shown even when hidden."""
    riadok = f"{ip_for_screen(ip, show)}   :   {port}"
    return f"{riadok}  {stitok}" if stitok else riadok


def pairing_other_ips(ips, show=False, virtualne=(), stitok="",
                      hotspot=(), stitok_hotspot=""):
    """The line "other addresses of this PC" - each hidden the same way as the
    main one. An address from `virtualne` gets `stitok` after it (0.3), an
    address from `hotspot` gets `stitok_hotspot` (0.3 batch 4b)."""
    kusy = []
    for ip in ips or ():
        kus = str(ip_for_screen(ip, show))
        if stitok and ip in (virtualne or ()):
            kus = f"{kus} {stitok}"
        elif stitok_hotspot and ip in (hotspot or ()):
            kus = f"{kus} {stitok_hotspot}"
        kusy.append(kus)
    return ",  ".join(kusy)


def entry_mask(value, show=False):
    """The `show=` value for the IP field in Settings: "" = readable.

    Only a real address is hidden. An empty field and 0.0.0.0 stay readable
    - there is nothing to give away and the player has to see that the safe
    default is there."""
    return "" if show or not _je_adresa(value) else ZNAK_MASKY
