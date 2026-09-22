"""Prijem srdcoveho tepu (BPM) z Wear OS hodiniek cez lokalnu Wi-Fi siet.

Pocuva NARAZ dvoma sposobmi na tom istom porte, pretoze appky na hodinkach
sa delia na dva tabory:

  TCP  - protokol obs-websocket v5 (viz obs_websocket.py). Takto sa sprava
         "HeartRateOnStream for OBS": pripoji sa k nam ako keby sme boli
         OBS a zapisuje tep do "textoveho zdroja". Toto je overene na
         realnych hodinkach - 872 aktualizacii za 14 minut, raz za sekundu.
  UDP  - obycajny datagram s cislom (pripadne JSON). Takto posiela viacero
         jednoduchsich appiek. Na tom istom porte sa prijima aj OSC
         (binarny protokol appiek pre VRChat) - je to JEDINA cesta, akou
         sa da tep poslat z iPhonu/Apple Watch na lokalnu adresu bez
         cloudu, viz `_parse_osc`.

Co pride skor, to plati - indikator tepu je spolocny.

Dve veci, ktore su tu urobene zamerne inak, nez by clovek cakal:

1) `stop()` NIKDY necaka na vlakna (ziadny join). Callbacky sa z nich
   dostavaju do GUI cez `root.after`, a to je pri volani z ineho vlakna
   blokujuce - keby GUI vlakno v `stop()` cakalo na vlakno, ktore samo caka
   na GUI vlakno, appka zamrzne na cely timeout. Vlakna su daemon a stop()
   im pod rukami zavrie sockety, takze skoncia okamzite.

2) Kazdy beh dostane vlastne cislo generacie, ktore sa posiela spat v
   callbackoch. Prijimatel (DandurfApp) tak vie zahodit aktualizacie, ktore
   uz doleteli od stareho, medzitym zastaveneho behu - inak by indikator
   zamrzol na "125 BPM" aj po vypnuti senzora.
"""

import errno
import json
import math
import re
import socket
import struct
import threading
import time

import logging_setup
import obs_websocket

log = logging_setup.get_logger("hr")

# Strop sucasnych socketov (listener + UDP + klienti). Bez neho by hocikto
# z LAN mohol otvorit lubovolne vela TCP spojeni a nafukovat vlakna (DoS).
_MAX_LIVE_SOCKETS = 16

# Fyziologicky mozny rozsah tepu. Na sieti sa okrem samotneho BPM daju
# chytit aj uplne ine cisla (timestampy, ID paketu, sum z ineho zariadenia
# na tom istom porte) - cokolvek mimo tohto rozsahu preto NIE je tep a
# zahadzujeme to uz tu, aby sa nezmysel ako "9999 BPM" nikdy nedostal ani
# na indikator, ani do biofeedback triggera.
MIN_PLAUSIBLE_BPM = 25
MAX_PLAUSIBLE_BPM = 250

# "" = pocuvaj na vsetkych sietovych rozhraniach (0.0.0.0). Toto je jedina
# hodnota, ktora funguje na kazdom PC bez ohladu na to, aku IP mu prave
# pridelil router - preto je predvolena.
ANY_INTERFACE = "0.0.0.0"

# Predvoleny port obs-websocket v5 - presne ten, ktory maju appky pre OBS
# predvyplneny, takze hrac nemusi menit nic.
DEFAULT_PORT = 4455

# Chyby socketu, ktore NIE su dovod ukoncit prijem:
#   WSAEMSGSIZE (10040)   - datagram bol vacsi nez buffer; socket zostava
#                           plne funkcny, len o ten jeden paket prideme
#   WSAECONNRESET (10054) - ICMP "port unreachable" od predosleho prijemcu
_RECOVERABLE_ERRNOS = {errno.EMSGSIZE, errno.ECONNRESET, 10040, 10054}

# Chyby, ktore znamenaju "tuto adresu toto PC nema" - typicky ked hrac do
# policka napise IP hodiniek namiesto IP svojho PC, alebo mu router pridelil
# inu adresu, nez ma ulozenu.
_NO_SUCH_ADDRESS_ERRNOS = {errno.EADDRNOTAVAIL, 10049}

# Port uz niekto pocuva - druha kopia Zanshinu, alebo bezi OBS, ktore ma
# 4455 tiez ako predvoleny. Toto nie je "rozbita siet", ale konkretna vec,
# ktoru vie hrac opravit - preto ma vlastny stav a vlastnu hlasku.
_PORT_BUSY_ERRNOS = {errno.EADDRINUSE, 10048}


def _err_no(exc):
    return getattr(exc, "winerror", None) or getattr(exc, "errno", None)


class _Run:
    """Stav jedneho behu prijimaca (jednej generacie). Drzi si vsetky
    otvorene sockety, aby ich `stop()` vedel okamzite zavriet."""

    def __init__(self, generation):
        self.generation = generation
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sockets = set()
        self.last_data = None
        self.stale_reported = False
        # Kolko surovych sprav este zapisat do denniku.
        #
        # 12 bolo primalo: pri dvoch spravach za sekundu je to sest sekund
        # prevadzky, z ktorych sa striedavy vzor (raz tep, raz nieco ine)
        # precitat neda. 40 pokryje asi pol minuty, co uz staci, a firehose
        # z toho nebude - je to raz za spustenie prijmu.
        self.log_left = 40
        # Mena zdrojov, ktore v tomto behu uz nieco poslali. Podla toho sa
        # rozhoduje, ci sa smie z holeho cisla z NEZNAMEHO zdroja hadat tep
        # (viz `parse_metrics`). `None` je tiez zaznam - je to UDP kanal.
        self.zdroje = set()

    def add(self, sock):
        with self._lock:
            if self.stop_event.is_set():
                return False
            if len(self._sockets) >= _MAX_LIVE_SOCKETS:
                return False        # strop spojeni - poistka proti LAN DoS
            self._sockets.add(sock)
            return True

    def discard(self, sock):
        with self._lock:
            self._sockets.discard(sock)

    def shutdown(self):
        self.stop_event.set()
        with self._lock:
            sockets, self._sockets = self._sockets, set()
        for sock in sockets:
            try:
                sock.close()
            except Exception:
                pass

    def note_source(self, zdroj):
        """Zaznamena zdroj a vrati True, ak je v tomto behu zatial jediny."""
        with self._lock:
            self.zdroje.add(zdroj)
            return len(self.zdroje) <= 1

    def mark_data(self):
        with self._lock:
            self.last_data = time.monotonic()
            self.stale_reported = False


class HeartRateMonitor:
    """Prijimac tepu.

    `on_bpm(bpm, generation)` sa vola pri kazdej prijatej platnej hodnote,
    `on_status((kind, payload), generation)` pri zmene stavu pripojenia -
    kind je "connecting" | "disconnected" | "error" | "bound_any".
    Oba callbacky pridu z pozadoveho vlakna, volajuci si ich musi sam
    preplanovat do GUI vlakna (viz DandurfApp.ui_call) a mal by zahodit
    tie, ktorych `generation` uz nie je aktualna."""

    TICK_TIMEOUT_S = 0.5
    # Po tolkoto sekundach bez vzorky sa hlasi "odpojene".
    #
    # 3 -> 12 PO TESTOVANOM VECERI 18. 9.
    # Toto cislo nie je len o indikatore v okne. `app._apply_hr_status`
    # na "disconnected" vola `_suspend_cue_trigger(A_TEP_VYPADOL)` a ten v
    # `trigger.suspend()` VYNULUJE `_above_since`. Kedze natiahnutie
    # vyzaduje SUVISLE `stress_hold_s` (45 s), kazdy taky vypadok zacal
    # 45-sekundovy odpocet odznova.
    #
    # Pri troch sekundach na to stacil bezny jitter domacej Wi-Fi: hodinky
    # posielaju v priemere kazdych ~1,5 s (1405 vzoriek za 2136 s z relacie
    # 17. 9.), takze 3 s su len dvojnasobok priemernej medzery - jeden
    # strateny paket a odpocet je prec. V CSV z 18. 9. to vidno ako relaciu
    # 18:22 (12,2 min, 0,3 min nad hranicou) s NULOU hlasok.
    #
    # Nesymetria je jasna: falosne "odpojene" zabije funkciu, pomale
    # rozpoznanie skutocneho odpojenia znamena len to, ze okno 12 sekund
    # ukazuje posledny tep. Preto radsej dlhsie.
    #
    # Dlhsi vypadok sa STALE zachyti spravne a `resume()` odpocet spusti
    # odznova - to je zamer, nie chyba: po pol minute bez dat uz naozaj
    # nevieme, ci telo ostalo hore.
    STALE_AFTER_S = 12.0
    # Dost velky buffer aj na ukecany JSON z hodiniek (RR intervaly, ID
    # zariadenia, casova znacka). Mensi buffer by na Windows nespôsobil
    # orezanie, ale rovno vynimku WSAEMSGSIZE.
    RECV_BUFFER_BYTES = 4096

    def __init__(self, on_bpm, on_status=None, on_metrics=None):
        self.on_bpm = on_bpm
        self.on_status = on_status
        # Volitelne: kroky a rychlost z tej istej spravy. Ked ho nikto
        # nenastavi, appka sa sprava presne ako predtym.
        self.on_metrics = on_metrics
        self._run = None
        self._generation = 0

    def start(self, host, port):
        """Spusti novy beh prijimaca a vrati cislo jeho generacie."""
        self.stop()
        self._generation += 1
        run = _Run(self._generation)
        self._run = run
        threading.Thread(target=self._serve, args=(host, int(port), run),
                         daemon=True).start()
        return run.generation

    @property
    def running(self):
        """Bezi prave prijem? Volajuci sa tym vyhne zbytocnemu restartu.

        Restart socketu znamena kratke odpojenie hodiniek - a prave kratke
        vypadky su to, co rozbija pocitanie suvislosti v `trigger.py`.
        Kto chce len NOVU MERACIU RELACIU, nema dovod sahat na siet.
        """
        return self._run is not None

    def stop(self):
        """Okamzite (neblokujuco) ukonci bezuci prijem.

        Zamerne sa NEcaka na dobehnutie vlakien - viz poznamka 1) v hlavicke
        modulu. Zatvorenim socketov sa kazde z nich odblokuje samo."""
        run, self._run = self._run, None
        if run is not None:
            run.shutdown()

    # ---------- pozadove vlakna ----------

    def _notify(self, func, payload, run):
        if func is None or run.stop_event.is_set():
            return
        try:
            func(payload, run.generation)
        except Exception:
            # Chyba v spracovani vzorky (on_bpm/on_data/on_status/on_connected)
            # by inak ticho zhodila KAZDU dalsiu vzorku a tep by "zamrzol" bez
            # jedinej stopy. Zalogujeme RAZ (dalsie sa uz nevypisu), nech to
            # z citaceho vlakna nezaplavi log.
            if not getattr(self, "_notify_warned", False):
                self._notify_warned = True
                log.exception("HR: spracovanie vzorky zlyhalo "
                              "(dalsie vyskyty sa uz nevypisu)")

    def _emit_bpm(self, bpm, run):
        if bpm is None:
            return
        run.mark_data()
        self._notify(self.on_bpm, bpm, run)

    def _emit(self, data, run, zdroj=None):
        """Jedna prijata sprava: tep von starou cestou, kroky a rychlost novou.

        `zdroj` je meno OBS zdroja, do ktoreho appka na hodinkach zapisala.
        Pri UDP ziadne nie je - tam sa metriky nadalej poznavaju z menoviek
        v texte.

        Kroky chodia ZVLAST od tepu zamerne. Sprava ich nemusi obsahovat
        (zakladna verzia appky na hodinkach ich neposiela) a vtedy sa nesmie
        tvarit, ze hrac sedi - "nevieme" a "nula krokov" su dve rozne veci.
        """
        metriky = parse_metrics(data, zdroj, run.note_source(zdroj))
        # SUROVA SPRAVA DO DENNIKA, prvych par kusov z kazdeho behu.
        #
        # Bez toho sa neda zistit, CO hodinky posielaju - a to je prave
        # otazka, na ktorej stoji detekcia pohybu. Zapisuje sa obmedzeny
        # pocet: trvaly zapis kazdej spravy by z denniku spravil firehose
        # (vzorka kazdych 1,5 s = 2400 riadkov za hodinu).
        if run.log_left > 0:
            run.log_left -= 1
            try:
                ukazka = data.decode("utf-8", errors="replace")[:200]
            except Exception:
                ukazka = repr(data[:120])
            log.info("z hodiniek prislo [%s]: %r -> %s",
                     zdroj or "bez mena", ukazka, metriky)
        self._emit_bpm(metriky["bpm"], run)
        if self.on_metrics is not None and (metriky["steps"] is not None
                                            or metriky["speed"] is not None):
            # MENO ZDROJA IDE SPOLU S HODNOTAMI. Bez neho by `hr_stats`
            # nemalo ako rozoznat, ze ten isty pocet krokov chodi z dvoch
            # zdrojov naraz - a z ich vzajomneho oneskorenia by pocitalo
            # kroky, ktore sa nestali.
            self._notify(self.on_metrics, dict(metriky, zdroj=zdroj), run)

    def _serve(self, host, port, run):
        """Hlavne vlakno behu: otvori TCP (obs-websocket) a UDP, potom
        prijima spojenia. TCP je povinne - to je cesta, ktorou chodia
        appky pre OBS; UDP je bonus a jeho zlyhanie beh nezhodi."""
        try:
            listener, used_fallback = self._bind(socket.SOCK_STREAM, host, port)
        except OSError as exc:
            kind = "busy" if _err_no(exc) in _PORT_BUSY_ERRNOS else "error"
            self._notify(self.on_status, (kind, port if kind == "busy" else str(exc)), run)
            return
        if not run.add(listener):
            listener.close()
            return

        if used_fallback:
            self._notify(self.on_status, ("bound_any", host), run)
        self._notify(self.on_status, ("connecting", None), run)

        bind_host = "" if used_fallback else host
        threading.Thread(target=self._udp_loop, args=(bind_host, port, run),
                         daemon=True).start()
        threading.Thread(target=self._stale_watchdog, args=(run,),
                         daemon=True).start()

        listener.listen(4)
        listener.settimeout(self.TICK_TIMEOUT_S)
        while not run.stop_event.is_set():
            try:
                conn, _addr = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not run.add(conn):
                conn.close()
                break
            threading.Thread(target=self._websocket_client, args=(conn, run),
                             daemon=True).start()
        run.discard(listener)
        try:
            listener.close()
        except Exception:
            pass

    def _websocket_client(self, conn, run):
        """Jeden pripojeny klient obs-websocket (appka na hodinkach)."""
        linked = False
        try:
            conn.settimeout(None)   # stop() socket zavrie, timeout netreba

            def on_connected():
                nonlocal linked
                linked = True
                self._notify(self.on_status, ("client", None), run)

            obs_websocket.serve_connection(
                conn,
                on_text=lambda text, zdroj=None: self._emit(
                    text.encode(), run, zdroj),
                should_stop=run.stop_event.is_set,
                on_connected=on_connected)
        except Exception:
            pass
        finally:
            run.discard(conn)
            try:
                conn.close()
            except Exception:
                pass
            if linked:
                self._notify(self.on_status, ("client_gone", None), run)

    def _udp_loop(self, host, port, run):
        """Zaloha pre appky, ktore posielaju obycajne UDP datagramy."""
        try:
            sock, _ = self._bind(socket.SOCK_DGRAM, host, port)
        except OSError:
            return              # UDP je bonus, jeho zlyhanie beh nezhodi
        if not run.add(sock):
            sock.close()
            return
        sock.settimeout(self.TICK_TIMEOUT_S)
        try:
            while not run.stop_event.is_set():
                try:
                    data, _addr = sock.recvfrom(self.RECV_BUFFER_BYTES)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if run.stop_event.is_set():
                        break
                    if _err_no(exc) in _RECOVERABLE_ERRNOS:
                        # prilis velky paket / ICMP od predosleho prijemcu -
                        # socket je v poriadku, len tento paket zahodime
                        continue
                    break
                try:
                    self._emit(data, run)
                except Exception:
                    # Pokazeny/skodlivy paket (napr. OSC float inf/nan) nesmie
                    # NATRVALO zhodit UDP prijem tepu - rovnako, ako to pre
                    # svoju vetvu uz robi TCP klient (`_websocket_client`).
                    if not getattr(self, "_udp_warned", False):
                        self._udp_warned = True
                        log.exception("HR/UDP: spracovanie paketu zlyhalo "
                                      "(dalsie sa uz nevypisu)")
        finally:
            run.discard(sock)
            try:
                sock.close()
            except Exception:
                pass

    def _stale_watchdog(self, run):
        """Ked tep prestane chodit, indikator sa musi vratit na "Odpojene" -
        bez ohladu na to, ktorym z dvoch kanalov chodil."""
        while not run.stop_event.wait(self.TICK_TIMEOUT_S):
            last = run.last_data
            if last is None or run.stale_reported:
                continue
            if time.monotonic() - last > self.STALE_AFTER_S:
                run.stale_reported = True
                self._notify(self.on_status, ("disconnected", None), run)

    # ---------- otvaranie socketov ----------

    def _bind(self, kind, host, port):
        """Vrati (socket, pouzila_sa_zaloha). Ak zadanu adresu toto PC nema,
        neskonci chybou, ale zacne pocuvat na vsetkych rozhraniach - inak by
        hracovi stacilo zle prepisat jedno cislo a funkcia by mu tichom
        prestala fungovat."""
        target = (host or "").strip()
        try:
            return self._bind_to(kind, target, port), False
        except OSError as exc:
            if target in ("", ANY_INTERFACE) or _err_no(exc) not in _NO_SUCH_ADDRESS_ERRNOS:
                raise
        return self._bind_to(kind, "", port), True

    def _bind_to(self, kind, host, port):
        sock = socket.socket(socket.AF_INET, kind)
        try:
            self._set_exclusive(sock, kind)
            sock.bind(("" if host == ANY_INTERFACE else host, port))
        except OSError:
            try:
                sock.close()
            except Exception:
                pass
            raise
        return sock

    @staticmethod
    def _set_exclusive(sock, kind):
        """POZOR na rozdiel medzi Windows a Linuxom: na Windows by
        SO_REUSEADDR dovolil DVOM procesom pocuvat na tom istom porte
        sucasne - spojenia by potom dostal len jeden z nich a druha kopia
        appky by tichom nedostala nic (a hrac by len pozeral na "Pripaja
        sa..."). SO_EXCLUSIVEADDRUSE namiesto toho poctivo zlyha s "port je
        obsadeny", co vieme hracovi povedat.

        Na Linuxe je SO_REUSEADDR pre pocuvaci socket bezpecny a bezny
        (dva zive listenery nedovoli), takze tam ostava."""
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            sock.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        elif kind == socket.SOCK_STREAM:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def _plausible(bpm):
    """None pre vsetko, co nemoze byt ludsky tep (viz MIN/MAX vyssie)."""
    if bpm is None:
        return None
    return bpm if MIN_PLAUSIBLE_BPM <= bpm <= MAX_PLAUSIBLE_BPM else None


# --------------------------------------------------------------------------
# OSC - treti format, ktory po UDP prichadza
# --------------------------------------------------------------------------
#
# PRECO TO TU JE: na iPhone/Apple Watch NEEXISTUJE appka, ktora by hovorila
# obs-websocket. Vsetko, co vie citat Apple Watch (Pulsoid, Stromno,
# HypeRate, Heartwitch), posiela tep do CLOUDU a vracia odkaz do
# prehliadaca - k tomuto PC sa nepripoji nikdy. Jedina cesta, ktorou sa z
# iPhonu da tep poslat na LOKALNU adresu bez cloudu, je OSC (appky pre
# VRChat, napr. PulseOSC). Na Androide to iste vie HeartOSC.
#
# OSC je binarny, nie text, takze cez textovu vetvu nizsie by nepresiel:
#   sprava = adresa ("/avatar/parameters/HR") + typovy retazec (",i")
#            + argumenty, vsetko null-ukoncene a doplnene na nasobok 4
#            bajtov, cisla big-endian
#   balik  = "#bundle\0" + 8 bajtov casovej znacky + [dlzka][sprava]...
#
# Adresu ZAMERNE neskumame: kazda appka si ju pomenuje inak a hrac si ju
# vie prepisat. Berieme prve cislo, ktore vyzera ako ludsky tep - a prave
# to zaroven odfiltruje normalizovane hodnoty 0..1, ktore tie appky
# posielaju vedla skutocneho BPM (0.36 nie je tep, 72 ano).

def _osc_string(data, pos):
    """(retazec, pozicia dalsieho pola). OSC retazce su null-ukoncene a
    doplnene nulami na nasobok styroch bajtov."""
    end = data.find(b"\0", pos)
    if end < 0:
        return None, len(data)
    return data[pos:end], (end + 4) & ~3


def _parse_osc(data):
    """BPM z OSC spravy alebo balika; None, ak to OSC nie je."""
    if data.startswith(b"#bundle\0"):
        pos = 16                      # hlavicka + casova znacka
        while pos + 4 <= len(data):
            size = int.from_bytes(data[pos:pos + 4], "big")
            pos += 4
            if size <= 0 or pos + size > len(data):
                break
            bpm = _parse_osc(data[pos:pos + size])
            if bpm is not None:
                return bpm
            pos += size
        return None
    if not data.startswith(b"/"):
        return None
    _address, pos = _osc_string(data, 0)
    tags, pos = _osc_string(data, pos)
    if not tags or not tags.startswith(b","):
        return None
    for tag in tags[1:]:
        if tag == ord("i") and pos + 4 <= len(data):
            value = int.from_bytes(data[pos:pos + 4], "big", signed=True)
        elif tag == ord("f") and pos + 4 <= len(data):
            value = struct.unpack(">f", data[pos:pos + 4])[0]
            if not math.isfinite(value):
                return None           # inf/nan v OSC float nie je tep
        else:
            return None               # retazce/bloby nepreskakujeme, koncime
        pos += 4
        bpm = _plausible(int(round(value)))
        if bpm is not None:
            return bpm
    return None


# DVE hladania, nie jedna alternacia.
#
# `re.search` vracia NAJLAVEJSI vyskyt, nie prvu vyhovujucu vetvu. Pri texte
# "Tep: 73  Kroky: 1832" sa vzor `(\d+)\s*kroky` chytil na "73  Kroky" -
# teda precital tep ako pocet krokov - lebo zacinal skor nez "Kroky: 1832".
# Menovka pred cislom je jednoznacnejsia, tak sa skusa prva.
_KROKY_PRED = re.compile(
    r"(?:\bsteps?\b|\bkrok(?:y|ov)?\b|\bstep[\s_-]*count\b)[\s:=-]{0,3}(\d{1,6})",
    re.IGNORECASE)
_KROKY_ZA = re.compile(
    r"(\d{1,6})\s*(?:\bsteps?\b|\bkrok(?:y|ov)?\b)", re.IGNORECASE)

_RYCHLOST_PRED = re.compile(
    r"(?:\bspeed\b|\brychlost\b|\bpace\b)[\s:=-]{0,3}(\d+(?:[.,]\d+)?)",
    re.IGNORECASE)
_RYCHLOST_ZA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:km/?h|m/?s|kmh)", re.IGNORECASE)


def _cislo(text, *vzory):
    """Prve cislo, ktore najde niektory zo vzorov - v poradi, v akom prisli."""
    for vzor in vzory:
        m = vzor.search(text)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", "."))
        except (TypeError, ValueError, AttributeError):
            continue
    return None


# MENA ZDROJOV, ktore vieme zaradit. Hrac si ich v appke na hodinkach
# pomenuje sam, takze tu nemozu byt presne retazce.
#
# HRANICE SLOV SU TU NUTNE, nie kozmetika. Povodne sa kluc hladal ako
# obycajny podretazec a `hr` ma dva znaky: zdroj menom "Threshold" aj "HRV"
# sa tym padom zaradil ako TEP. Je to presne ten isty omyl ako slovenske
# "tep" vnutri anglickeho "s-tep-s" - uz tretikrat v tomto subore.
#
# Dlhsie kluce su predpony (`krok\w*` chyti "kroky" aj "Denne kroky"),
# kratke maju hranicu z oboch stran (`hr\b` nechyti "Threshold").
# Poradie ma vyznam: kroky sa skusaju PRVE.
_ZDROJE_METRIK = (
    ("steps", re.compile(
        r"\b(krok\w*|steps?\b|step[\s_-]*count|schritt\w*|pasos?\b|pas\b"
        r"|\u6b69\u6570|\u6b69\u884c)", re.IGNORECASE)),
    ("speed", re.compile(
        r"\b(rychl\w*|r\u00fdchl\w*|speed\b|pace\b|tempo\b|km/?h\b"
        r"|geschwindigkeit|velocidad)", re.IGNORECASE)),
    ("bpm", re.compile(
        r"\b(tep\w*|bpm\b|hr\b|heart[\s_-]*rate|heart\b|puls\w*|pulse\b"
        r"|srdc\w*|herzfrequenz|\u5fc3\u62cd)", re.IGNORECASE)),
)

# Cisto ciselna sprava - "86", "4,2", " 1045 ". Nic ine za hodnotu metriky
# neberieme: keby sme z lubovolneho textu vytiahli prve cislo, vratili by sme
# sa presne k chybe, kvoli ktorej sa tep cital z poctu krokov.
_HOLE_CISLO = re.compile(r"^[\s]*([-+]?\d+(?:[.,]\d+)?)[\s]*$")

# POCET KROKOV MA VLASTNY VZOR, lebo znesie oddelovac tisicov.
#
# Hodinky formatuju cislo pre overlay podla locale a do zdroja posielaju
# "1,085" alebo "1 085". Spolocny vzor vyssie bral ciarku ako desatinnu
# a z 1085 krokov citaral 1. Rozlisit to na urovni retazca sa neda ("4,2" je
# platna rychlost), zato na urovni METRIKY ano: krok je vzdy cele cislo,
# takze pri krokoch je oddelovac vzdy tisicovy a nikdy desatinny.
_HOLY_POCET = re.compile(
    r"^[\s]*([-+]?\d{1,3}(?:[ .,\u00a0]\d{3})+|[-+]?\d+)[\s]*$")

# Kroky su kumulativne za den, rychlost je chodza az beh. Hodnoty mimo
# toho su chyba prenosu, nie udaj - a chybny udaj je horsi nez ziadny,
# lebo z neho appka usudzuje, ci hrac sedel pri klavesnici.
MAX_KROKOV = 200000
MAX_RYCHLOST_KMH = 50.0


def metrika_zdroja(meno):
    """`"bpm"` / `"steps"` / `"speed"` podla mena OBS zdroja, inak `None`.

    `None` znamena "neviem" a NIE "tep". Sprava z nepomenovaneho zdroja ide
    starou cestou cez menovky v texte - tam, kde bola doteraz.
    """
    if not meno:
        return None
    n = meno.strip()
    for metrika, vzor in _ZDROJE_METRIK:
        if vzor.search(n):
            return metrika
    return None


def _hodnota_holeho_cisla(data, ako_pocet=False):
    """Cislo z cisto ciselnej spravy, inak None.

    `ako_pocet=True` je pre kroky: pripusti oddelovac tisicov a vzdy vrati
    cele cislo. Pre tep a rychlost ostava ciarka desatinna.
    """
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return None
    if ako_pocet:
        m = _HOLY_POCET.match(text)
        if m is None:
            return None
        cistene = re.sub(r"[ .,\u00a0]", "", m.group(1))
        try:
            return float(cistene)
        except ValueError:
            return None
    m = _HOLE_CISLO.match(text)
    if m is None:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_metrics(data, zdroj=None, jediny_zdroj=True):
    """Vsetko, co sa z jednej spravy da vytiahnut: tep, kroky, rychlost.

    `zdroj` je meno OBS zdroja, do ktoreho appka na hodinkach prave zapisala.
    Ked ho pozname, ostro urcuje, co sprava znamena - a zdroj krokov uz NIKDY
    nemoze vydat tep, aj keby sa pocet krokov nahodou zmestil do rozsahu
    ludskeho tepu (rano po 140 krokoch presne to hrozilo).

    `jediny_zdroj` hovori, ci do tohto behu zapisal uz aj niekto iny.
    Zaradit vieme len mena, ktore pozname, a hrac si ich pomenuva sam - takze
    `Cadence`, `Calories` ci japonske \u6b69\u6570 su pre nas neznama. Pri
    JEDINOM zdroji je neznamy nazov nadalej tep, nech sa vola akokolvek
    (predvolene meno zdroja v OBS je "Text 1" a vela ludi ho nepremenuje).
    Len co pisu ASPON DVA rozne zdroje, klient zjavne rozdeluje metriky podla
    zdrojov - a vtedy sa z holeho cisla z nepoznaneho zdroja tep uz hadat
    NESMIE. Inak by sa povodna chyba vratila kazdemu, kto si zdroj krokov
    pomenoval inak nez my cakame.

    Premiova verzia appky na hodinkach vie poslat do toho isteho textu aj
    kroky a rychlost. Appka ich doteraz zahadzovala - pritom su to jediny
    PRIAMY signal pohybu, ktory mame. Bez neho sa chodza od hernej zataze
    odlisit neda: v oboch pripadoch len stupne tep.

    Chybajuca polozka je None, nie nula. "Nevieme" a "nula krokov" su dve
    rozne veci a zamenit ich by znamenalo tvrdit, ze hrac sedi, vzdy ked
    hodinky kroky neposielaju.
    """
    bpm = _parse_bpm(data)
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return {"bpm": bpm, "steps": None, "speed": None}

    kroky = rychlost = None
    obj = None
    if text.lstrip().startswith("{"):
        try:
            obj = json.loads(text)
        except Exception:
            obj = None
    if isinstance(obj, dict):
        for kluc in ("steps", "stepCount", "step_count", "kroky"):
            if kluc in obj:
                try:
                    kroky = int(float(obj[kluc]))
                except (TypeError, ValueError, OverflowError):
                    pass
                break
        for kluc in ("speed", "pace", "rychlost", "kmh"):
            if kluc in obj:
                try:
                    rychlost = float(obj[kluc])
                except (TypeError, ValueError):
                    pass
                break
    if kroky is None:
        c = _cislo(text, _KROKY_PRED, _KROKY_ZA)
        kroky = int(c) if c is not None else None
    if rychlost is None:
        rychlost = _cislo(text, _RYCHLOST_PRED, _RYCHLOST_ZA)

    vysledok = {"bpm": bpm, "steps": kroky, "speed": rychlost}
    metrika = metrika_zdroja(zdroj)
    if metrika is None:
        # NEZNAMY ZDROJ MEDZI VIACERYMI: holé číslo nie je tep.
        #
        # Menovka v texte ("Tep: 86") prejde aj tadialto - potlaca sa len
        # holé číslo, teda presne ten pripad, kde nemame ako vediet, co to
        # je, a kde sa doteraz hadalo.
        if not jediny_zdroj and _hodnota_holeho_cisla(data) is not None:
            vysledok["bpm"] = None
        return vysledok

    # Zdroj je pomenovany: ak v texte nebola menovka, cele telo spravy je
    # hodnotou prave tejto metriky.
    if vysledok[metrika] is None:
        c = _hodnota_holeho_cisla(data, ako_pocet=(metrika == "steps"))
        if c is not None:
            if metrika == "bpm":
                vysledok["bpm"] = _plausible(int(c))
            elif metrika == "steps":
                if 0 <= c <= MAX_KROKOV:
                    vysledok["steps"] = int(c)
            elif 0 <= c <= MAX_RYCHLOST_KMH:
                vysledok["speed"] = c

    # A HLAVNE: zo zdroja krokov ani rychlosti nesmie vypadnut tep. Toto je
    # cely dovod, preco sa meno zdroja vobec prenasa az sem.
    if metrika != "bpm":
        vysledok["bpm"] = None
    return vysledok


def _parse_bpm(data):
    # OSC ide prvy: je binarny a textova vetva nizsie by z neho vytiahla
    # nahodne cislo z bajtov adresy
    bpm = _parse_osc(data)
    if bpm is not None:
        return bpm
    try:
        text = data.decode("utf-8", errors="ignore").strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return _plausible(int(float(text)))
    except (ValueError, OverflowError):
        pass
    try:
        obj = json.loads(text)
    except Exception:
        obj = None
    if isinstance(obj, dict):
        for key in ("bpm", "heartRate", "heart_rate", "hr", "value"):
            if key in obj:
                try:
                    return _plausible(int(float(obj[key])))
                except (TypeError, ValueError, OverflowError):
                    pass

    # POMENOVANE CISLO MA PREDNOST PRED "PRVYM CISLOM V TEXTE".
    #
    # Prémiová verzia appky na hodinkach vie do toho isteho textu poslat aj
    # kroky a rychlost. Doteraz sa bralo proste prve cislo, co pri texte typu
    # "1832 krokov | 73 bpm" znamena precitat kroky ako tep. `_plausible` by
    # ich sice odmietol a vratil None, takze by tep NEPRISIEL VOBEC - a v
    # appke by to vyzeralo ako vypadok hodiniek, nie ako zle precitany text.
    #
    # Preto sa najprv hlada cislo, ktore ma pri sebe menovku tepu, a az ked
    # ziadne nie je, siahne sa po prvom pravdepodobnom cisle.
    menovka = re.search(
        # HRANICE SLOV SU TU NUTNE, nie kozmetika: slovenske "tep" je
        # vnutri anglickeho "S-tep-s". Bez `\b` sa vzor chytil na "Steps"
        # a z "Steps: 1832" precital 183 ako tep.
        # `(?!\d)` zasa brani tomu, aby sa z "1832" vzali prve tri cislice.
        r"(?:\bbpm\b|\bhr\b|\bheart[\s_-]*rate\b|\btep\b|\bpuls\b)"
        r"[\s:=-]{0,3}(\d{1,3})(?!\d)"
        r"|(\d{1,3})(?!\d)\s*(?:\bbpm\b|\btep\b)",
        text, re.IGNORECASE)
    if menovka:
        cislo = menovka.group(1) or menovka.group(2)
        hodnota = _plausible(int(cislo))
        if hodnota is not None:
            return hodnota

    # Bez menovky: prve cislo, ktore je vobec pravdepodobny tep. Kroky
    # (tisice) a rychlost (0-20) sa tak preskocia samy.
    for m in re.finditer(r"\d+", text):
        hodnota = _plausible(int(m.group()))
        if hodnota is not None:
            return hodnota
    return None
