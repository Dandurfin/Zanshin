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
neutralne (nie ako chyba v odkazoch).
"""

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


def check(url):
    """Vrati (ok, kod_alebo_chyba). HEAD najprv (setri prenos), pri 405/501
    skusi GET - niektore servery HEAD odmietaju, hoci stranka existuje.
    Pri 403 vrati (True, BOT_BLOCKED) - stranka zije, ale robota nepusti."""
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
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            # rozliš "nie je siet" od "odkaz je mrtvy"
            if isinstance(reason, OSError) and "Name or service" in str(reason):
                raise ConnectionError("no-network")
            return False, str(reason)
        except ConnectionError:
            raise
        except Exception as exc:
            return False, str(exc)
    return False, "HEAD aj GET zlyhali"


def main():
    print(f"Kontrolujem {len(PHILOSOPHY_SOURCES)} zdrojov...\n")
    i18n.set_lang("en")   # popisky v anglictine pre citatelny vystup
    dead = []
    blocked = []
    no_net = False
    for key, url in PHILOSOPHY_SOURCES:
        label = i18n.tr(key)
        try:
            ok, info = check(url)
        except ConnectionError:
            no_net = True
            print("  !!  Nie je siet - kontrolu neviem dokoncit.")
            break
        mark = "OK " if ok else "PAD"
        if info == BOT_BLOCKED:
            mark = "OK?"
            blocked.append((key, url))
        print(f"  {mark} [{info}]  {label}")
        print(f"        {url}")
        if not ok:
            dead.append((key, url, info))

    if no_net:
        print("\nSpusti znova, ked budes online.")
        sys.exit(0)

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
