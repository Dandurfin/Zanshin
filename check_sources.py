#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Overi, ci URL zdrojov (studii) v Sprievodcovi este ziju.

Preco to je samostatny skript
-----------------------------
Odkazy na studie starnu - casopis presunie clanok, DOI sa zmeni, stranka
zhasne. Mrtvy odkaz v casti "veda za appkou" podkopava presne to, co ma
budovat: doveryhodnost. Tento skript prejde vsetky URL z guide_content.py,
skusi ich otvorit a nahlasi, ktore uz nevedu na 200 OK.

NEBEZI automaticky pri builde (potrebuje siet, a build ma byt offline). Spusti
ho rucne raz za cas, alebo pred vydanim:

    python check_sources.py

Navratovy kod 0 = vsetky odkazy ziju, 1 = aspon jeden je mrtvy/presmerovany
inam. Timeout na odkaz je 8 s; ked nemas siet, skript to povie a skonci
neutralne (nie ako chyba v odkazoch). Offline = ziaden server neodpovedal
a VSETKY odkazy zlyhali uz na sieti (DNS, nedosiahnutelna siet, timeout) -
vtedy sa neskontrolovalo nic a zoznam "mrtvych" by bol vymysleny.
"""

import errno
import socket
import sys
import urllib.error
import urllib.request

sys.path.insert(0, ".")

try:
    from guide_content import PHILOSOPHY_SOURCES
except Exception as exc:  # pragma: no cover
    print(f"Nepodarilo sa nacitat PHILOSOPHY_SOURCES z guide_content.py: {exc}")
    sys.exit(2)

import i18n

TIMEOUT = 8
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 Zanshin-link-check")
HEADERS = {"User-Agent": UA,
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

# HTTP 403 od Cloudflare/WAF NIE JE mrtvy odkaz - server len odmieta roboty
# (ACM, WHOOP, sportspsychology.org: v prehliadaci sa otvoria, skript
# dostane "challenge"). Mrtva stranka vracia 404/410 alebo DNS zlyha.
# Takéto odkazy hlasime zvlast ("blokuje roboty - over rucne") a nepocitame
# ich ako chybu, inak by skript padal na kazdom vedeckom vydavatelstve.
BOT_BLOCKED = "bot-blocked"


# Chyby, pri ktorych poziadavka k serveru vobec nedosla - nie su odpovedou
# servera, takze samy o sebe nehovoria, ci odkaz zije. Do 0.2.1 skript poznal
# len linuxovy text "Name or service not known"; na Windows bez internetu
# (getaddrinfo -> WinError 11001) preto hlasil KAZDY odkaz ako mrtvy.
# Winsock kody: 11001 WSAHOST_NOT_FOUND ("getaddrinfo failed"), 11002
# WSATRY_AGAIN, 10051 WSAENETUNREACH, 10065 WSAEHOSTUNREACH.
_WIN_NET_ERRORS = {11001, 11002, 10051, 10065}
_NET_ERRNOS = {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN}
_NET_TEXTS = ("getaddrinfo failed", "name or service not known",
              "temporary failure in name resolution",
              "nodename nor servname", "no address associated", "timed out")


class NetworkError(ConnectionError):
    """Poziadavka nedosla k serveru (DNS, smerovanie, timeout)."""


def is_network_error(exc):
    """True, ak `exc` (aj zabalena v URLError) znamena "k serveru som sa
    nedostal", nie "server odpovedal chybou"."""
    if isinstance(exc, urllib.error.URLError) and not isinstance(
            exc, urllib.error.HTTPError):
        exc = exc.reason
    # socket.timeout je od Pythonu 3.10 len iny nazov pre TimeoutError
    if isinstance(exc, (socket.gaierror, socket.timeout, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        if getattr(exc, "winerror", None) in _WIN_NET_ERRORS:
            return True
        if exc.errno in _WIN_NET_ERRORS or exc.errno in _NET_ERRNOS:
            return True
    text = str(exc).lower()
    return any(t in text for t in _NET_TEXTS)


def check(url):
    """Vrati (ok, kod_alebo_chyba). HEAD najprv (setri prenos), pri 405/501
    skusi GET - niektore servery HEAD odmietaju, hoci stranka existuje.
    Pri 403 vrati (True, BOT_BLOCKED) - stranka zije, ale robota nepusti.

    Ked sa uz HEAD k serveru nedostane (`is_network_error`), vyhodi
    NetworkError: o odkaze to nic nehovori, rozhodne az `main` podla toho,
    ci odpovedal aspon jeden iny server."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return True, resp.status
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 405, 501) and method == "HEAD":
                continue                      # skus GET
            if exc.code in (403, 429, 503):
                return True, BOT_BLOCKED
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            reason = getattr(exc, "reason", exc)
            # GET ide len po HTTP odpovedi na HEAD - server je teda
            # dosiahnutelny a zlyhanie GET je vlastnost odkazu.
            if method == "HEAD" and is_network_error(exc):
                raise NetworkError(str(reason)) from exc
            return False, str(reason)
    return False, "HEAD aj GET zlyhali"


def main():
    print(f"Kontrolujem {len(PHILOSOPHY_SOURCES)} zdrojov...\n")
    i18n.set_lang("en")   # popisky v anglictine pre citatelny vystup
    dead = []
    blocked = []
    unreachable = []      # (key, url, chyba) - k serveru sa nedoslo
    # Kolko odkazov nepadlo uz na sieti: server odpovedal HTTP kodom, alebo
    # sa ozval a zlyhalo to inak (SSL, odmietnute spojenie) - siet teda ide.
    answered = 0
    for key, url in PHILOSOPHY_SOURCES:
        label = i18n.tr(key)
        try:
            ok, info = check(url)
        except NetworkError as exc:
            # Este nevieme, ci je mrtvy odkaz alebo cela siet - rozhodne sa
            # az na konci, preto ine oznacenie nez PAD.
            unreachable.append((key, url, str(exc)))
            print(f"  NET [{exc}]  {label}")
            print(f"        {url}")
            continue
        answered += 1
        mark = "OK " if ok else "PAD"
        if info == BOT_BLOCKED:
            mark = "OK?"
            blocked.append((key, url))
        print(f"  {mark} [{info}]  {label}")
        print(f"        {url}")
        if not ok:
            dead.append((key, url, info))

    if unreachable and not answered:
        # Ani jeden server neodpovedal a vsetko padlo na sieti: nie si
        # online. Hlasit to ako mrtve odkazy by bola nepravda.
        print("\n  !!  Nie si online - ani jeden odkaz sa nedal otvorit "
              "(sietova chyba), nic som neskontroloval.")
        print("Spusti znova, ked budes online.")
        sys.exit(0)
    # Aspon jeden server odpovedal, siet teda ide - odkaz, ku ktoremu sa
    # nedalo dostat (neexistujuca domena, timeout), je naozaj nedostupny.
    dead.extend(unreachable)

    print()
    if blocked:
        print(f"Blokuju roboty (403/challenge), stranka existuje - over raz rucne v prehliadaci: {len(blocked)}")
        for key, url in blocked:
            print(f"  ? {key}  {url}")
        print()
    if dead:
        print(f"{'!' * 60}")
        print(f"MRTVE ALEBO NEDOSTUPNE ODKAZY: {len(dead)}")
        for key, url, info in dead:
            print(f"  ✗ {key} [{info}]  {url}")
        print("Najdi aktualnu nahradu a oprav PHILOSOPHY_SOURCES v guide_content.py.")
        print(f"{'!' * 60}")
        sys.exit(1)
    else:
        print("Vsetky odkazy ziju.")
        sys.exit(0)


if __name__ == "__main__":
    main()
