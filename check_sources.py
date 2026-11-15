#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks whether the source (study) URLs in the Guide are still alive.

Why this is a separate script
-----------------------------
Links to studies age - a journal moves an article, a DOI changes, a page goes
dark. A dead link in the "science behind the app" part undermines exactly what
it is meant to build: credibility. This script goes through all URLs from
guide_content.py, tries to open them and reports which ones no longer lead to
200 OK.

It does NOT run automatically during the build (it needs the network, and the
build is meant to be offline). Run it by hand once in a while, or before a
release:

    python check_sources.py

Exit code 0 = all links are alive, 1 = at least one is dead/redirected
elsewhere. The timeout per link is 8 s; when you have no network, the script
says so and ends neutrally (not as an error in the links). Offline = no server
answered and ALL links already failed on the network (DNS, unreachable network,
timeout) - then nothing was checked and the list of "dead" ones would be made
up.
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

# HTTP 403 from Cloudflare/WAF IS NOT a dead link - the server only refuses
# robots (ACM, WHOOP, sportspsychology.org: they open in a browser, the script
# gets a "challenge"). A dead page returns 404/410 or DNS fails. We report such
# links separately ("blocks robots - check by hand") and do not count them as
# an error, otherwise the script would fail on every scientific publisher.
BOT_BLOCKED = "bot-blocked"


# Errors where the request never reached the server - they are not an answer
# from the server, so on their own they do not say whether the link is alive.
# Until 0.2.1 the script only knew the Linux text "Name or service not known";
# on Windows without internet (getaddrinfo -> WinError 11001) it therefore
# reported EVERY link as dead.
# Winsock codes: 11001 WSAHOST_NOT_FOUND ("getaddrinfo failed"), 11002
# WSATRY_AGAIN, 10051 WSAENETUNREACH, 10065 WSAEHOSTUNREACH.
_WIN_NET_ERRORS = {11001, 11002, 10051, 10065}
_NET_ERRNOS = {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN}
_NET_TEXTS = ("getaddrinfo failed", "name or service not known",
              "temporary failure in name resolution",
              "nodename nor servname", "no address associated", "timed out")


class NetworkError(ConnectionError):
    """The request did not reach the server (DNS, routing, timeout)."""


def is_network_error(exc):
    """True if `exc` (also wrapped in URLError) means "I could not reach the
    server", not "the server answered with an error"."""
    if isinstance(exc, urllib.error.URLError) and not isinstance(
            exc, urllib.error.HTTPError):
        exc = exc.reason
    # since Python 3.10 socket.timeout is just another name for TimeoutError
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
    """Returns (ok, code_or_error). HEAD first (saves transfer), on 405/501
    tries GET - some servers refuse HEAD although the page exists. On 403
    returns (True, BOT_BLOCKED) - the page is alive, but does not let the robot
    in.

    When HEAD already cannot reach the server (`is_network_error`), it raises
    NetworkError: that says nothing about the link, `main` decides later based
    on whether at least one other server answered."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return True, resp.status
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 405, 501) and method == "HEAD":
                continue                      # try GET
            if exc.code in (403, 429, 503):
                return True, BOT_BLOCKED
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            reason = getattr(exc, "reason", exc)
            # GET only runs after an HTTP answer to HEAD - so the server is
            # reachable and a GET failure is a property of the link.
            if method == "HEAD" and is_network_error(exc):
                raise NetworkError(str(reason)) from exc
            return False, str(reason)
    return False, "HEAD aj GET zlyhali"


def main():
    print(f"Kontrolujem {len(PHILOSOPHY_SOURCES)} zdrojov...\n")
    i18n.set_lang("en")   # English labels for readable output
    dead = []
    blocked = []
    unreachable = []      # (key, url, error) - the server was not reached
    # How many links did not already fail on the network: the server answered
    # with an HTTP code, or it responded and failed otherwise (SSL, refused
    # connection) - so the network works.
    answered = 0
    for key, url in PHILOSOPHY_SOURCES:
        label = i18n.tr(key)
        try:
            ok, info = check(url)
        except NetworkError as exc:
            # We do not know yet whether it is a dead link or the whole
            # network - it is decided only at the end, hence a different mark
            # than PAD.
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
        # Not a single server answered and everything failed on the network:
        # you are not online. Reporting it as dead links would be untrue.
        print("\n  !!  Nie si online - ani jeden odkaz sa nedal otvorit "
              "(sietova chyba), nic som neskontroloval.")
        print("Spusti znova, ked budes online.")
        sys.exit(0)
    # At least one server answered, so the network works - a link that could
    # not be reached (non-existent domain, timeout) really is unavailable.
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
