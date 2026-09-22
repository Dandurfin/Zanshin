# -*- coding: utf-8 -*-
"""Falosny producent herných udalostí - test `game_events.py` bez hry.

PRECO EXISTUJE
Celá herná časť sa dá postaviť a otestovať BEZ Overwolfu, bez ich
schvaľovania a bez toho, aby sme vedeli, či sú naše hry vôbec podporované.
Keď je protokol hotový a overený proti tomuto skriptu, Overwolf sa stane už
len ďalším producentom - rovnako ako herný log alebo Riot API.

Je to zároveň referenčná implementácia pre kohokoľvek, kto by chcel napísať
most pre inú hru: stačí posielať tieto riadky na ten port.

POUZITIE
    python probe_herne_udalosti.py            # zápas na 2 minúty
    python probe_herne_udalosti.py --rychlo   # to isté za 20 sekúnd
    python probe_herne_udalosti.py --nezmysly # aj pokazené riadky
"""

import argparse
import json
import random
import socket
import sys
import time

import game_events


def posli(sock, **udalost):
    riadok = json.dumps(udalost, ensure_ascii=False) + "\n"
    sock.sendall(riadok.encode("utf-8"))
    print("  ->", riadok.strip())


def zapas(sock, tempo=1.0, nezmysly=False):
    """Jeden krátky zápas: začiatok, pár killov a smrtí, koniec kola."""
    posli(sock, type="game_info", game="The Finals")
    time.sleep(0.5 * tempo)
    posli(sock, type="match_start")

    skore, skore_sup = 0, 0
    for kolo in range(1, 4):
        posli(sock, type="round_start")
        time.sleep(1.0 * tempo)
        for _ in range(random.randint(2, 5)):
            if random.random() < 0.65:
                skore += 1
                posli(sock, type="kill")
            else:
                skore_sup += 1
                posli(sock, type="death")
            time.sleep(random.uniform(0.6, 2.0) * tempo)

        if nezmysly:
            # Presne to, co ma prijimac prezit bez mihnutia oka.
            print("  -> (pokazene riadky)")
            sock.sendall(b"toto nie je JSON\n")
            sock.sendall(b'{"type": "neznamy_typ"}\n')
            sock.sendall(b'{"chyba": "typ"}\n')
            sock.sendall(b'{"type": "kill", "ts": "nie je cislo"}\n')
            sock.sendall(b'{"type": "kill", "ts": 1}\n')   # rok 1970

        posli(sock, type="round_end", score=skore, score_opponent=skore_sup)
        time.sleep(1.0 * tempo)

    posli(sock, type="match_end", won=skore > skore_sup)


def main(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=game_events.DEFAULT_PORT)
    p.add_argument("--rychlo", action="store_true", help="zrýchlené tempo")
    p.add_argument("--nezmysly", action="store_true",
                   help="posielať aj pokazené riadky")
    a = p.parse_args(argv)

    tempo = 0.15 if a.rychlo else 1.0
    print("pripájam sa na %s:%d ..." % (game_events.LOOPBACK, a.port))
    try:
        sock = socket.create_connection((game_events.LOOPBACK, a.port), timeout=3)
    except OSError as exc:
        print("nepodarilo sa pripojiť: %s" % exc)
        # Zanshin sám prijímač herných udalostí NESPÚŠŤA (modul zatiaľ nie je
        # napojený — viz B30). Musí bežať samostatne:
        print("beží prijímač? spusti `python game_events.py --pocuvaj`")
        return 1
    with sock:
        zapas(sock, tempo=tempo, nezmysly=a.nezmysly)
    print("hotovo")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
