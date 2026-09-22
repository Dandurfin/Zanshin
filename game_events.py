# -*- coding: utf-8 -*-
"""Prijem udalosti z hry. Appka hru NECITA - dostane, co jej niekto posle.

PRECO ZVLAST A NIE CEZ KANAL TEPU
19. 9. 2026 sa ukazalo, co spravi zdielanie jedneho netypovaneho textoveho
kanala dvoma druhmi dat: ked appka na hodinkach zacala posielat aj kroky,
parser tepu zacal citat pocet krokov ako BPM. Vysledkom bola 52-minutova
relacia s priemerom 124 a maximom 235, ktora vyzerala ako telo. Herne data
preto chodia vlastnym portom a s VYSLOVNYM typom v kazdej sprave.

PRECO TO NEPORUSUJE SLUB "APPKA HRU NECITA"
Neporusuje, lebo appka naozaj necita. Tento modul otvori lokalny socket a
caka. Kto don posle udalosti, je uz mimo Zanshinu - napriklad samostatna
Overwolf appka, ktora ma na herne udalosti vlastne sankcionovane API. Ten
most moze byt v inom repozitari a pod inou licenciou; jadro tym ostava bez
proprietarnych zavislosti. Je to ten isty vzor, akym uz chodi tep z hodiniek
(`obs_websocket.py` predstiera OBS a hodinky don posielaju).

PROTOKOL
Newline-delimited JSON cez TCP, jedna udalost na riadok, kodovanie UTF-8:

    {"type": "kill",       "ts": 1789820012.4}
    {"type": "death",      "ts": 1789820044.1}
    {"type": "round_end",  "score": 13, "score_opponent": 9}
    {"type": "match_end",  "won": true}
    {"type": "game_info",  "game": "The Finals"}

Kluce su ANGLICKE zamerne: je to verejne rozhranie, ktore budu implementovat
cudzi ludia (most pre Overwolf, pre herny log, pre Riot API). Komentare v
kode ostavaju po slovensky, protokol nie.

`ts` je volitelny; ked chyba, pouzije sa cas prijatia. Neznamy `type` sa
ZAHODI, nie uhadne - z toho isteho dovodu, preco sa nehada tep z cisla bez
menovky.

DVA TRANSPORTY NA JEDNOM PORTE
Povodne to bolo len surove TCP. Lenze Overwolf appka je JavaScript v
Chromium prostredi a surovy TCP socket otvorit NEVIE - ma len
`overwolf.web.createWebSocket()` (klient na localhost) a
`overwolf.web.createServer()`. Prijimac, ktory vie len surove riadky, by teda
skutocny most nikdy neoslovil, hoci testovaci skript funguje.

Port preto rozozna oboje podla prvych bajtov:
  - zacina `GET ` -> WebSocket handshake (`obs_websocket`), potom sa citaju
    ramce; jeden ramec smie niest jednu udalost aj viac riadkov naraz
  - cokolvek ine -> surove riadky oddelene `\n`

Protokol je v oboch pripadoch ten isty. Surove TCP ostava preto, lebo sa
nan da poslat udalost jednym `printf` z ktorehokolvek jazyka a testuje
sa to bez kniznice.
"""

import json
import socket
import threading
import time

import logging_setup
import obs_websocket

log = logging_setup.get_logger("game")

# Vlastny port, hned vedla tepu (4455). Zmena tu, nie na troch miestach.
DEFAULT_PORT = 4456

# LEN LOOPBACK, na rozdiel od tepu.
#
# Tep chodi z INEHO zariadenia (hodinky cez Wi-Fi), takze sa pocuva na
# vsetkych sietach. Herne udalosti pochadzaju z procesu na tom istom
# pocitaci, takze nie je dovod vystavovat ich sieti - a kazdy port navyse
# otvoreny do siete je zbytocne riziko.
LOOPBACK = "127.0.0.1"

# Najdlhsi riadok, ktory sa este spracuje. Bez stropu by jeden pokazeny
# producent (chybajuci newline v cykle) nafukoval buffer donekonecna.
MAX_RIADOK = 8192

# Ako daleko od "teraz" smie lezat `ts` v sprave. Most moze posielat
# nazbierane udalosti po vypadku a tie uz do beziacej relacie nepatria.
MAX_ODCHYLKA_S = 30.0

# Typy, ktorym rozumieme. Co tu nie je, sa zahodi.
TYPY = frozenset({
    "kill", "death", "assist",
    "round_start", "round_end",
    "match_start", "match_end",
    "game_info",
})


class _Run:
    """Jeden beh prijimaca. Generacia zahodi spravy z uz zastaveneho vlakna -
    rovnaky vzor ako `heart_rate._Run`."""

    def __init__(self, generation):
        self.generation = generation
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sockets = set()
        self.prijatych = 0
        self.zahodenych = 0
        self.log_left = 12          # kolko surovych riadkov este zapisat

    def add(self, sock):
        with self._lock:
            if self.stop_event.is_set():
                return False
            self._sockets.add(sock)
            return True

    def discard(self, sock):
        with self._lock:
            self._sockets.discard(sock)

    def stop(self):
        self.stop_event.set()
        with self._lock:
            sockety, self._sockets = list(self._sockets), set()
        for s in sockety:
            try:
                s.close()
            except Exception:
                pass


def parse_event(riadok, now=None):
    """Jeden riadok -> udalost, alebo None ked sa jej neda verit.

    Vracia None a NEHADA. Producent, ktory posle nezmysel, nema dostat
    polovicne prijatu udalost - to by bola tichá chyba v datach.
    """
    now = time.time() if now is None else float(now)
    if isinstance(riadok, bytes):
        try:
            riadok = riadok.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
    riadok = (riadok or "").strip()
    if not riadok or len(riadok) > MAX_RIADOK:
        return None
    try:
        obj = json.loads(riadok)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    typ = obj.get("type")
    if typ not in TYPY:
        return None

    udalost = dict(obj)
    ts = obj.get("ts")
    if ts is None:
        udalost["ts"] = now
    else:
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            return None
        # Stara alebo buduca znacka casu je podozriva - nechame cas prijatia
        # a povodnu hodnotu si odlozime, nech sa to da spatne dohladat.
        if abs(now - ts) > MAX_ODCHYLKA_S:
            udalost["ts"] = now
            udalost["ts_reported"] = ts
        else:
            udalost["ts"] = ts
    return udalost


class GameEventReceiver:
    """Pocuva na lokalnom porte a hlasi prijate udalosti.

    `on_event(udalost, generation)` sa vola z vlakna prijimaca, nie z Tk -
    volajuci si to musi preniest sam (appka ma na to `ui_call`).
    """

    def __init__(self, on_event, on_status=None):
        self.on_event = on_event
        self.on_status = on_status
        self._run = None
        self._generation = 0

    @property
    def running(self):
        return self._run is not None

    def start(self, port=DEFAULT_PORT):
        """Spusti novy beh a vrati cislo jeho generacie."""
        self.stop()
        self._generation += 1
        run = _Run(self._generation)
        self._run = run
        threading.Thread(target=self._serve, args=(int(port), run),
                         daemon=True).start()
        return run.generation

    def stop(self):
        run, self._run = self._run, None
        if run is not None:
            run.stop()

    # ---------- vnutro ----------

    def _notify(self, callback, *args):
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:
            log.exception("callback herných udalostí zlyhal")

    def _serve(self, port, run):
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((LOOPBACK, port))
            listener.listen(4)
            listener.settimeout(0.5)
        except OSError as exc:
            self._notify(self.on_status, ("error", str(exc)), run.generation)
            return
        if not run.add(listener):
            listener.close()
            return
        self._notify(self.on_status, ("listening", port), run.generation)
        log.info("herné udalosti: počúvam na %s:%d", LOOPBACK, port)

        while not run.stop_event.is_set():
            try:
                conn, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not run.add(conn):
                conn.close()
                break
            threading.Thread(target=self._obsluz, args=(conn, run),
                             daemon=True).start()
        run.discard(listener)
        try:
            listener.close()
        except Exception:
            pass

    def _je_websocket(self, conn, run):
        """Nakukne na prve bajty BEZ toho, aby ich zjedol.

        `obs_websocket.handshake` si cele HTTP hlavicky precita sam, takze
        sa pred nim nesmie zo socketu nic odobrat - preto `MSG_PEEK`.
        """
        koniec = time.time() + 3.0
        while time.time() < koniec and not run.stop_event.is_set():
            try:
                zaciatok = conn.recv(4, socket.MSG_PEEK)
            except socket.timeout:
                continue
            except OSError:
                return False
            if not zaciatok:
                return False
            if len(zaciatok) < 4:
                continue            # este nedoslo dost bajtov na rozhodnutie
            return zaciatok == b"GET "
        return False

    def _citaj_websocket(self, conn, run):
        """Ramce po handshake. Jeden ramec = jedna alebo viac udalosti."""
        if not obs_websocket.handshake(conn):
            log.warning("herné udalosti: WebSocket handshake zlyhal")
            return
        log.info("herné udalosti: pripojené cez WebSocket")
        conn.settimeout(None)       # ramce sa citaju blokujuco, nie po kusoch
        while not run.stop_event.is_set():
            try:
                opcode, payload = obs_websocket.read_frame(conn)
            except OSError:
                break
            if opcode is None or opcode == 0x8:          # zatvorene
                break
            if opcode == 0x9:                            # ping -> pong
                try:
                    obs_websocket.send_frame(conn, payload, opcode=0xA)
                except OSError:
                    break
                continue
            if opcode not in (0x1, 0x2):                 # text / binary
                continue
            # JS posle typicky jednu udalost na ramec (`ws.send(JSON...)`),
            # ale niekto moze poslat aj viac riadkov naraz - zvladneme oboje.
            for riadok in (payload or b"").split(b"\n"):
                if riadok.strip():
                    self._spracuj(riadok, run)

    def _obsluz(self, conn, run):
        """Jedno spojenie. Rozozna transport a potom cita, kym sa nezavrie."""
        self._notify(self.on_status, ("connected", None), run.generation)
        try:
            conn.settimeout(1.0)
            if self._je_websocket(conn, run):
                self._citaj_websocket(conn, run)
            else:
                self._citaj_riadky(conn, run)
        finally:
            run.discard(conn)
            try:
                conn.close()
            except Exception:
                pass
            self._notify(self.on_status, ("disconnected", None), run.generation)

    def _citaj_riadky(self, conn, run):
        """Surove TCP: udalosti oddelene newline."""
        buffer = b""
        while not run.stop_event.is_set():
            try:
                kus = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not kus:
                break
            buffer += kus
            # Prilis dlhy riadok bez newline = pokazeny producent.
            # Zahodime buffer, nie spojenie: dalsi riadok moze byt dobry.
            if len(buffer) > MAX_RIADOK * 4:
                run.zahodenych += 1
                log.warning("herné udalosti: riadok bez konca, zahadzujem buffer")
                buffer = b""
                continue
            while b"\n" in buffer:
                riadok, buffer = buffer.split(b"\n", 1)
                self._spracuj(riadok, run)

    def _spracuj(self, riadok, run):
        if run.log_left > 0:
            run.log_left -= 1
            try:
                ukazka = riadok.decode("utf-8", errors="replace")[:200]
            except Exception:
                ukazka = repr(riadok[:120])
            log.info("z hry prišlo: %r", ukazka)
        udalost = parse_event(riadok)
        if udalost is None:
            run.zahodenych += 1
            return
        run.prijatych += 1
        self._notify(self.on_event, udalost, run.generation)


# --------------------------------------------------------------------------
# Samostatny beh: `python game_events.py --pocuvaj`
# --------------------------------------------------------------------------
#
# Aby sa dal protokol vyskusat bez appky - user spusti toto v jednom okne a
# `probe_herne_udalosti.py` v druhom. Je to zaroven najrychlejsi sposob, ako
# si cudzi clovek overi, ze jeho most posiela spravne riadky.

def _main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="Počúva herné udalosti a vypisuje ich.")
    parser.add_argument("--pocuvaj", action="store_true", help="spusti prijímač")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if not args.pocuvaj:
        parser.print_help()
        return 0

    def na_udalost(udalost, _gen):
        cas = time.strftime("%H:%M:%S", time.localtime(udalost["ts"]))
        zvysok = {k: v for k, v in udalost.items() if k not in ("type", "ts")}
        print("%s  %-12s %s" % (cas, udalost["type"], zvysok or ""))

    def na_stav(stav, _gen):
        print("[%s] %s" % stav if stav[1] is not None else "[%s]" % stav[0])

    prijimac = GameEventReceiver(na_udalost, na_stav)
    prijimac.start(args.port)
    print("Ctrl+C ukončí.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        prijimac.stop()
        print("koniec")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
