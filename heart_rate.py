"""Receiving the heart rate (BPM) from a Wear OS watch over the local Wi-Fi.

It listens in TWO ways AT ONCE on the same port, because the watch apps
fall into two camps:

  TCP  - the obs-websocket v5 protocol (see obs_websocket.py). This is how
         "HeartRateOnStream for OBS" behaves: it connects to us as if we
         were OBS and writes the heart rate into a "text source". This is
         verified on a real watch - 872 updates in 14 minutes, once a second.
  UDP  - a plain datagram with a number (or JSON). This is how several
         simpler apps send. OSC (the binary protocol of apps for VRChat)
         is received on the same port too - it is the ONLY way to send
         the heart rate from an iPhone/Apple Watch to a local address
         without the cloud, see `_parse_osc`.

Whatever comes first counts - the heart-rate indicator is shared.

Two things here are deliberately done differently from what one would expect:

1) `stop()` NEVER waits for the threads (no join). Callbacks get from them
   into the GUI through `root.after`, and that blocks when called from
   another thread - if the GUI thread in `stop()` waited for a thread that
   is itself waiting for the GUI thread, the app would freeze for the whole
   timeout. The threads are daemons and stop() closes the sockets under
   their hands, so they end immediately.

2) Every run gets its own generation number, which is sent back in the
   callbacks. The receiver (DandurfApp) can thus throw away updates that
   arrive late from an old run that has been stopped in the meantime -
   otherwise the indicator would freeze at "125 BPM" even after the sensor
   is switched off.
"""

import errno
import json
import math
import re
import socket
import struct
import threading
import time
from collections import deque

import logging_setup
import obs_websocket

log = logging_setup.get_logger("hr")

# Cap on simultaneous sockets (listener + UDP + clients). Without it anyone
# on the LAN could open any number of TCP connections and inflate threads
# (DoS). When the cap is full only the NEW connection is dropped and
# receiving goes on (see `_serve`); idle and dead connections free their
# place on their own (time limits in `obs_websocket`). Against someone on
# the LAN who actively holds connections the cap does not help - the port
# is without a password on purpose, see README.
_MAX_LIVE_SOCKETS = 16

# Physiologically possible heart-rate range. Besides the BPM itself, quite
# different numbers can be caught on the network (timestamps, packet IDs,
# noise from another device on the same port) - so anything outside this
# range is NOT a heart rate and we drop it right here, so that nonsense
# like "9999 BPM" never reaches the indicator or the biofeedback trigger.
MIN_PLAUSIBLE_BPM = 25
MAX_PLAUSIBLE_BPM = 250

# "" = listen on all network interfaces (0.0.0.0). This is the only value
# that works on every PC regardless of which IP the router has just
# assigned to it - that is why it is the default.
ANY_INTERFACE = "0.0.0.0"

# Default obs-websocket v5 port - exactly the one the apps for OBS have
# pre-filled, so the player does not have to change anything.
DEFAULT_PORT = 4455

# Socket errors that are NOT a reason to stop receiving:
#   WSAEMSGSIZE (10040)   - the datagram was bigger than the buffer; the
#                           socket stays fully working, we just lose that
#                           one packet
#   WSAECONNRESET (10054) - ICMP "port unreachable" from a previous receiver
_RECOVERABLE_ERRNOS = {errno.EMSGSIZE, errno.ECONNRESET, 10040, 10054}

# Errors that mean "this PC does not have this address" - typically when
# the player types the IP of the watch into the field instead of the IP of
# their PC, or the router assigned a different address than the saved one.
_NO_SUCH_ADDRESS_ERRNOS = {errno.EADDRNOTAVAIL, 10049}

# Someone is already listening on the port - a second copy of Zanshin, or
# OBS is running, which also has 4455 as its default. This is not a
# "broken network" but a specific thing the player can fix - that is why
# it has its own state and its own message.
_PORT_BUSY_ERRNOS = {errno.EADDRINUSE, 10048}


def _err_no(exc):
    return getattr(exc, "winerror", None) or getattr(exc, "errno", None)


# TWO DIFFERENT HEART RATES IN ONE SOURCE (0.3).
#
# Measured at the author's: the watch app wrote two heart-rate streams
# interleaved into ONE source ("Tep") - in the same second a value from
# the higher stream and right after from the lower one, one stream
# 5-10 BPM below the other; at a calm heart rate they merged. For the
# measurement this is one heart rate jumping up and down, and the player
# will not find out on their own. So the app recognises it and says so
# (`DvaRadyTepu`, `_Run.note_bpm`) - it does not touch the measurement,
# the fix is in the settings of the watch app.
#
# The pattern is looked for in the last DVA_TEPY_OKNO_S seconds of ONE
# source and ALL four things must hold at once - each one cuts off a
# different false alarm. The numbers are verified on synthetic streams
# (tests/test_022_dva_tepy.py) and in a simulation: neither a noisy stream
# at 1-3 Hz, nor duplicates, nor one-off spikes, nor batches after a stuck
# Wi-Fi raised an alarm, two streams 5-10 BPM apart did - at 1 Hz within
# ~15 s, with pairs of messages every 2-4 s within ~35 s.
DVA_TEPY_OKNO_S = 60.0
# 1) MORE MESSAGES THAN ONE SENSOR CAN MANAGE: at least 30 % of the gaps
#    between messages are shorter than 0.65 s. The sensor changes ~1x per
#    second, so one stream has such gaps only now and then (Wi-Fi jitter);
#    two streams have them on every reading (at the author's the median
#    gap was 0.51 s).
DVA_TEPY_BLIZKO_S = 0.65
DVA_TEPY_MIN_PODIEL_BLIZKYCH = 0.30
# 2) ZIGZAG: the value jumps away from the previous one by at least 4 BPM
#    and right away comes back by at least 4 BPM the opposite way, and at
#    least one of those two gaps is short (above). There must be at least
#    8 such spots - one spike makes at most two. Below 4 BPM is normal
#    sensor noise.
DVA_TEPY_SKOK_BPM = 4
DVA_TEPY_MIN_CIKCAKOV = 8
# 3) NOT ONE BATCH: the zigzags are spread over at least 10 s. After a
#    stuck Wi-Fi a heap of old messages of one stream arrives at once -
#    that must not be enough.
DVA_TEPY_MIN_ROZPATIE_S = 10.0
# 4) EVERY OTHER VALUE BELONGS TOGETHER: neighbouring samples differ in
#    total at least 2x more than samples one apart. With two streams every
#    step jumps by the difference between the streams, one apart it is the
#    same stream; with one stream (even a noisy one, even with duplicates)
#    it is the other way round or the same. This is the main safeguard
#    against noise - without it a very noisy stream at 2 Hz in the
#    simulation sometimes produced an alarm.
DVA_TEPY_POMER = 2.0
# Below this many samples in the window the ratio (4) is just chance.
DVA_TEPY_MIN_VZORIEK = 16
# Memory: the client picks the source names, so at most this many sources
# per run and in each at most this many samples (60 s even at ~4 messages
# per second).
DVA_TEPY_MAX_ZDROJOV = 4
DVA_TEPY_MAX_VZORIEK = 256
# Source name for the journal and app.log, shortened, like the raw message in
# `_emit`.
MENO_ZDROJA_MAX = 80


def dva_rady_v_okne(vzorky):
    """True when [(cas, bpm)] (old -> new) has two interleaved HR streams.

    Pure rules 1-4 above, no state - tested directly.
    """
    n = len(vzorky)
    if n < max(3, DVA_TEPY_MIN_VZORIEK):
        return False
    blizko = [vzorky[i + 1][0] - vzorky[i][0] < DVA_TEPY_BLIZKO_S
              for i in range(n - 1)]
    if sum(blizko) < DVA_TEPY_MIN_PODIEL_BLIZKYCH * (n - 1):
        return False
    cikcaky = []
    susedne = ob_jednu = 0.0
    for i in range(n - 2):
        a, b, c = vzorky[i][1], vzorky[i + 1][1], vzorky[i + 2][1]
        susedne += abs(b - a)
        ob_jednu += abs(c - a)
        tam, spat = b - a, c - b
        if (abs(tam) >= DVA_TEPY_SKOK_BPM and abs(spat) >= DVA_TEPY_SKOK_BPM
                and (tam > 0) != (spat > 0) and (blizko[i] or blizko[i + 1])):
            cikcaky.append(vzorky[i + 1][0])
    if len(cikcaky) < DVA_TEPY_MIN_CIKCAKOV:
        return False
    if cikcaky[-1] - cikcaky[0] < DVA_TEPY_MIN_ROZPATIE_S:
        return False
    return susedne >= DVA_TEPY_POMER * ob_jednu


class DvaRadyTepu:
    """Sliding heart-rate window from ONE source for `dva_rady_v_okne`.

    Not thread-safe by itself - `_Run.note_bpm` calls it under the run lock.
    """

    def __init__(self):
        self._vzorky = deque(maxlen=DVA_TEPY_MAX_VZORIEK)

    def pridaj(self, bpm, cas):
        """Adds a sample; returns True when the window now has two streams."""
        self._vzorky.append((float(cas), float(bpm)))
        hranica = float(cas) - DVA_TEPY_OKNO_S
        while self._vzorky and self._vzorky[0][0] < hranica:
            self._vzorky.popleft()
        return dva_rady_v_okne(list(self._vzorky))


def meno_zdroja_do_dennika(zdroj):
    """Source name for a journal line: without line breaks (the client picks
    it itself and a new line would create a fake entry in the journal) and
    shortened."""
    return " ".join(str(zdroj).split())[:MENO_ZDROJA_MAX]


class _Run:
    """State of one receiver run (one generation). Keeps all open sockets,
    so that `stop()` can close them immediately."""

    def __init__(self, generation):
        self.generation = generation
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sockets = set()
        self.last_data = None
        self.stale_reported = False
        # How many raw messages to still write to the journal - to find out
        # what the watch really sends during pairing.
        #
        # 40 -> 5 IN 0.2.1. Every line carries the source name
        # ("[Kroky] '1045'"), so even an alternating pattern (heart rate once,
        # something else once) is visible from five messages. 40 raw
        # heart-rate values on every receiver start was half a minute more
        # health data in the journal than debugging the pairing needs.
        self.log_left = 5
        # Names of the sources that have already sent something in this run.
        # This decides whether a heart rate may be guessed from a bare number
        # from an UNKNOWN source (see `parse_metrics`). `None` is an entry
        # too - it is the UDP channel. No more than two are remembered (see
        # `note_source`).
        self.zdroje = set()
        # The connection cap is reported to the journal once per run, not on every
        # refusal.
        self.plno_hlasene = False
        # How many obs-websocket clients hold a connection after the handshake
        # right now - "client_gone" is reported only when the LAST one leaves
        # (see `_websocket_client`).
        self.klienti = 0
        # Two heart-rate streams in one source: a window for each source
        # separately and a flag that it has already been reported in this run
        # (ONCE per run, see `note_bpm`).
        self.dva_tepy = {}
        self.dva_tepy_hlasene = False

    def client_linked(self):
        with self._lock:
            self.klienti += 1

    def client_left(self):
        """Returns True if the last connected client has just left."""
        with self._lock:
            self.klienti -= 1
            return self.klienti <= 0

    def add(self, sock):
        with self._lock:
            if self.stop_event.is_set():
                return False
            if len(self._sockets) >= _MAX_LIVE_SOCKETS:
                return False        # connection cap - safeguard against LAN DoS
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
        """Notes the source; True if it is so far the only one in this run.

        The answer only depends on whether there are AT LEAST TWO sources -
        so there is no need to remember more names. Until now every name
        the client sent was added, until the sensor restarted: constantly
        new names from the LAN = memory without a cap (the client picks the
        name)."""
        with self._lock:
            if len(self.zdroje) < 2:
                self.zdroje.add(zdroj)
            return len(self.zdroje) <= 1

    def mark_data(self):
        with self._lock:
            self.last_data = time.monotonic()
            self.stale_reported = False

    def note_bpm(self, zdroj, bpm, cas=None):
        """Heart rate from a named source into the `DvaRadyTepu` window.
        Returns True EXACTLY ONCE per run - when the two-stream pattern first
        shows up in some source.

        The key is only the source name, not the connection: two
        connections writing into the same source break the measurement just
        the same. Without a name (UDP/OSC, a client without a source name)
        nothing is looked for - the message would have nothing to name.
        """
        if zdroj is None or bpm is None:
            return False
        cas = time.monotonic() if cas is None else cas
        with self._lock:
            if self.dva_tepy_hlasene:
                return False
            okno = self.dva_tepy.get(zdroj)
            if okno is None:
                if len(self.dva_tepy) >= DVA_TEPY_MAX_ZDROJOV:
                    return False
                okno = self.dva_tepy[zdroj] = DvaRadyTepu()
            if not okno.pridaj(bpm, cas):
                return False
            self.dva_tepy_hlasene = True
            self.dva_tepy.clear()           # no longer needed, the memory is freed
            return True


class HeartRateMonitor:
    """Heart-rate receiver.

    `on_bpm(bpm, generation)` is called on every received valid value,
    `on_status((kind, payload), generation)` on a change of the connection
    state - kind is "connecting" | "disconnected" | "error" | "busy" |
    "bound_any" | "client" | "client_gone" | "udp_busy" | "udp_error" |
    "two_series". "udp_busy"/"udp_error" mean "UDP did not open, TCP keeps
    running" - the run does not end. "two_series" (payload = source name
    for the journal) comes at most once per run: two different heart-rate
    streams are arriving into one source. Both callbacks come from a
    background thread, the caller has to reschedule them into the GUI
    thread itself (see DandurfApp.ui_call) and should throw away those
    whose `generation` is no longer current."""

    TICK_TIMEOUT_S = 0.5
    # After this many seconds without a sample "disconnected" is reported.
    #
    # 3 -> 12 AFTER THE TEST EVENING OF 18. 9.
    # This number is not only about the indicator in the window.
    # `app._apply_hr_status` on "disconnected" calls
    # `_suspend_cue_trigger(A_TEP_VYPADOL)` and that, in `trigger.suspend()`,
    # throws away all the collected time above the threshold (back then the
    # CONTINUOUS stretch, since 19. 9. also the cumulative window), so every
    # such dropout starts the 45-second countdown over.
    #
    # At three seconds ordinary home Wi-Fi jitter was enough for that: the
    # watch sent on average every ~1.5 s (1405 samples in 2136 s from the
    # session of 17. 9.), so 3 s is just twice the average gap - one lost
    # packet and the countdown is gone. In the CSV from 18. 9. this shows as
    # the 18:22 session (12.2 min, 0.3 min above the limit) with ZERO cues.
    #
    # The cadence changes, though: since 20. 9. the heart rate comes every
    # ~2.9 s (in OBS it alternates with steps), so one lost packet is already
    # a ~5.6 s gap. That is why the trigger has the same dropout limit too -
    # `trigger.DIERA_S` is the same number as this one (a test guards it).
    # When one changes, the other has to change too.
    #
    # The asymmetry is clear: a false "disconnected" kills the feature, slow
    # detection of a real disconnect only means that the window shows the
    # last heart rate for 12 seconds. So longer is better.
    #
    # A longer dropout is STILL caught correctly and `resume()` starts the
    # countdown over - that is intended, not a bug: after half a minute
    # without data we really do not know whether the body stayed elevated.
    STALE_AFTER_S = 12.0
    # A buffer big enough even for chatty JSON from the watch (RR intervals,
    # device ID, timestamp). A smaller buffer on Windows would not cause
    # truncation, but straight away a WSAEMSGSIZE exception.
    RECV_BUFFER_BYTES = 4096

    def __init__(self, on_bpm, on_status=None, on_metrics=None):
        self.on_bpm = on_bpm
        self.on_status = on_status
        # Optional: steps and speed from the same message. When nobody sets
        # it, the app behaves exactly as before.
        self.on_metrics = on_metrics
        self._run = None
        self._generation = 0

    def start(self, host, port):
        """Starts a new receiver run and returns its generation number."""
        self.stop()
        self._generation += 1
        run = _Run(self._generation)
        self._run = run
        threading.Thread(target=self._serve, args=(host, int(port), run),
                         daemon=True).start()
        return run.generation

    @property
    def running(self):
        """Is receiving running right now? It lets the caller avoid a needless
        restart.

        A socket restart means a short disconnect of the watch - and short
        dropouts are exactly what breaks the continuity counting in
        `trigger.py`. Whoever only wants a NEW MEASUREMENT SESSION has no
        reason to touch the network.
        """
        return self._run is not None

    def stop(self):
        """Stops the running receiver immediately (without blocking).

        It deliberately does NOT wait for the threads to finish - see note
        1) in the module header. Closing the sockets unblocks each of them
        on its own."""
        run, self._run = self._run, None
        if run is not None:
            run.shutdown()

    # ---------- background threads ----------

    def _notify(self, func, payload, run):
        if func is None or run.stop_event.is_set():
            return
        try:
            func(payload, run.generation)
        except Exception:
            # An error in processing a sample
            # (on_bpm/on_data/on_status/on_connected) would otherwise silently
            # kill EVERY following sample and the heart rate would "freeze"
            # without a single trace. We log it ONCE (further ones are not
            # printed), so that it does not flood the log from the reading
            # thread.
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
        """Received message: heart rate the old way, steps/speed the new way.

        `zdroj` is the name of the OBS source the watch app wrote into. With
        UDP there is none - there the metrics are still recognised from the
        labels in the text.

        Steps come SEPARATELY from the heart rate on purpose. The message
        does not have to contain them (the basic version of the watch app
        does not send them) and then it must not pretend the player is
        sitting - "we do not know" and "zero steps" are two different
        things.
        """
        metriky = parse_metrics(data, zdroj, run.note_source(zdroj))
        # RAW MESSAGE TO THE JOURNAL, the first few from every run.
        #
        # Without it there is no way to find out WHAT the watch sends - and
        # that is exactly the question movement detection stands on. A limited
        # number is written: a permanent record of every message would turn the
        # journal into a firehose (a sample every ~0.9 to ~2.9 s = roughly 1200
        # to 4000 lines per hour, see `trigger.MAX_KROK_S`).
        if run.log_left > 0:
            run.log_left -= 1
            try:
                ukazka = data.decode("utf-8", errors="replace")[:200]
            except Exception:
                ukazka = repr(data[:120])
            # the client picks the source name - only its start to the journal
            log.info("z hodiniek prislo [%s]: %r -> %s",
                     (zdroj or "bez mena")[:80], ukazka, metriky)
        self._emit_bpm(metriky["bpm"], run)
        # Two heart-rate streams in one source: once per run a line to app.log
        # and a state for the app. The heart rate goes out above unchanged -
        # this does not fix the measurement.
        if run.note_bpm(zdroj, metriky["bpm"]):
            meno = meno_zdroja_do_dennika(zdroj)
            log.info("HR: do zdroja [%s] chodia dva rozne rady tepu", meno)
            self._notify(self.on_status, ("two_series", meno), run)
        if self.on_metrics is not None and (metriky["steps"] is not None
                                            or metriky["speed"] is not None):
            # THE SOURCE NAME GOES ALONG WITH THE VALUES. Without it `hr_stats`
            # would have no way to recognise that the same step count is coming
            # from two sources at once - and from their mutual delay it would
            # count steps that never happened.
            self._notify(self.on_metrics, dict(metriky, zdroj=zdroj), run)

    def _serve(self, host, port, run):
        """Main thread of the run: opens TCP (obs-websocket) and UDP, then
        accepts connections. TCP is mandatory - that is the path the apps
        for OBS use; UDP is a bonus and its failure does not bring the run
        down."""
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
                if run.stop_event.is_set():
                    break
                # FULL: only THIS new connection is dropped, receiving goes on.
                #
                # Until now there was a `break` here, so the cap that was meant
                # to protect against a flood of connections itself stopped ALL
                # receiving until the sensor restarted - even when places freed
                # up in the meantime. `run.add` returns False also while
                # stopping; `stop_event` above tells these apart.
                if not run.plno_hlasene:
                    run.plno_hlasene = True
                    log.warning("HR: strop %d spojeni, nove spojenie odmietnute "
                                "(dalsie sa uz nevypisu)", _MAX_LIVE_SOCKETS)
                continue
            threading.Thread(target=self._websocket_client, args=(conn, run),
                             daemon=True).start()
        run.discard(listener)
        try:
            listener.close()
        except Exception:
            pass

    def _websocket_client(self, conn, run):
        """One connected obs-websocket client (the watch app)."""
        linked = False
        try:
            # THE TIME LIMITS ARE SET BY `serve_connection` (handshake 10 s,
            # then a ping after a minute of silence). Until now there was
            # `settimeout(None)` here: a connection that sent nothing held one
            # place under `_MAX_LIVE_SOCKETS` forever. A dead connection now
            # ends like any other disconnect (`finally` below). stop() closes
            # the socket right away and that unblocks the read on its own, it
            # does not wait for the limit.

            def on_connected():
                nonlocal linked
                linked = True
                run.client_linked()
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
            # "client_gone" ONLY WHEN THE LAST CLIENT LEAVES.
            #
            # After a Wi-Fi dropout the phone connects with a NEW connection
            # and the old one hangs half-open on our side. Before there was an
            # idle limit it hung forever and reported nothing; now the limit
            # closes it within two minutes - and if that reported
            # "client_gone", the app would, in the middle of a live heart rate
            # from the new connection, throw away the trigger countdown and
            # record a dropout that did not happen. A heart rate that really
            # stopped coming is reported anyway by `_stale_watchdog` after
            # STALE_AFTER_S.
            if linked and run.client_left():
                self._notify(self.on_status, ("client_gone", None), run)

    def _udp_loop(self, host, port, run):
        """Fallback for apps that send plain UDP datagrams."""
        # AN ALREADY STOPPED RUN DOES NOT TAKE THE PORT. `_serve` starts this
        # thread only after `_notify("connecting")`, which waits for the GUI
        # from a foreign thread - and in the meantime the run may be stopped
        # and a new one already opening the same port. If the old run grabbed
        # the port (and let go right away), the new one would get "the port is
        # held by another program", although only Zanshin itself held it for a
        # moment.
        if run.stop_event.is_set():
            return
        try:
            sock, _ = self._bind(socket.SOCK_DGRAM, host, port)
        except OSError as exc:
            if run.stop_event.is_set():
                return      # a stopped run reports nothing, not even to app.log
            # UDP is a bonus - its failure does NOT bring the run down, TCP
            # (apps for OBS) keeps running. But no longer silently: until now
            # there was a bare `return` here, so a player with an app that
            # sends only UDP/OSC (e.g. from an iPhone) stared at
            # "Pripaja sa..." (Connecting...) without a single trace of why.
            # Hence its own kinds "udp_busy"/"udp_error" - not "busy"/"error",
            # the app would take those as a failed TCP and bring all
            # receiving down.
            # Reported ONCE per run: binding is tried only here in one run.
            # Only the port and the error go into the file - the PC address
            # does not go into app.log (guarded by tests/test_ip_skryta.py).
            log.warning("HR/UDP: port %d sa nepodarilo otvorit (%s), "
                        "prijem ide len cez TCP", port, exc)
            if _err_no(exc) in _PORT_BUSY_ERRNOS:
                self._notify(self.on_status, ("udp_busy", port), run)
            else:
                self._notify(self.on_status, ("udp_error", (port, str(exc))), run)
            return
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
                        # packet too big / ICMP from a previous receiver -
                        # the socket is fine, we just drop this packet
                        continue
                    break
                try:
                    self._emit(data, run)
                except Exception:
                    # A broken/malicious packet (e.g. OSC float inf/nan) must
                    # not PERMANENTLY kill UDP heart-rate receiving - just as
                    # the TCP client (`_websocket_client`) already does for its
                    # branch.
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
        """When the heart rate stops coming, the indicator must go back to
        "Odpojene" (Disconnected) - regardless of which of the two channels
        it came through."""
        while not run.stop_event.wait(self.TICK_TIMEOUT_S):
            last = run.last_data
            if last is None or run.stale_reported:
                continue
            if time.monotonic() - last > self.STALE_AFTER_S:
                run.stale_reported = True
                self._notify(self.on_status, ("disconnected", None), run)

    # ---------- opening sockets ----------

    def _bind(self, kind, host, port):
        """Returns (socket, pouzila_sa_zaloha). If this PC does not have the
        given address, it does not end with an error but starts listening on
        all interfaces - otherwise it would be enough for the player to mistype
        one number and the feature would silently stop working for them."""
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
        """WATCH OUT for the difference between Windows and Linux: on Windows
        SO_REUSEADDR would allow TWO processes to listen on the same port
        at the same time - only one of them would then get the connections
        and the second copy of the app would silently get nothing (and the
        player would just stare at "Pripaja sa..." (Connecting...)).
        SO_EXCLUSIVEADDRUSE instead fails honestly with "port is in use",
        which we can tell the player.

        On Linux SO_REUSEADDR is safe and common for a listening socket (it
        does not allow two live listeners), so it stays there."""
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            sock.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        elif kind == socket.SOCK_STREAM:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def _plausible(bpm):
    """None for whatever cannot be a human heart rate (see MIN/MAX above)."""
    if bpm is None:
        return None
    return bpm if MIN_PLAUSIBLE_BPM <= bpm <= MAX_PLAUSIBLE_BPM else None


# --------------------------------------------------------------------------
# OSC - the third format that arrives over UDP
# --------------------------------------------------------------------------
#
# WHY THIS IS HERE: on iPhone/Apple Watch there is NO app that would speak
# obs-websocket. Everything that can read the Apple Watch (Pulsoid, Stromno,
# HypeRate, Heartwitch) sends the heart rate to the CLOUD and gives back a
# link for the browser - it never connects to this PC. The only way to send
# the heart rate from an iPhone to a LOCAL address without the cloud is OSC
# (apps for VRChat, e.g. PulseOSC). On Android HeartOSC can do the same.
#
# OSC is binary, not text, so it would not get through the text branch below:
#   message = address ("/avatar/parameters/HR") + type tag string (",i")
#             + arguments, all null-terminated and padded to a multiple
#             of 4 bytes, numbers big-endian
#   bundle  = "#bundle\0" + 8 bytes of timestamp + [length][message]...
#
# We DELIBERATELY do not look at the address: every app names it
# differently and the player can rewrite it. We take the first number that
# looks like a human heart rate - and that at the same time filters out the
# normalised 0..1 values those apps send next to the real BPM (0.36 is not
# a heart rate, 72 is).

def _osc_string(data, pos):
    """(string, position of the next field). OSC strings are null-terminated
    and padded with zeros to a multiple of four bytes."""
    end = data.find(b"\0", pos)
    if end < 0:
        return None, len(data)
    return data[pos:end], (end + 4) & ~3


def _parse_osc(data):
    """BPM from an OSC message or bundle; None if it is not OSC."""
    if data.startswith(b"#bundle\0"):
        pos = 16                      # header + timestamp
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
                return None           # inf/nan in an OSC float is not a heart rate
        else:
            return None               # we do not skip strings/blobs, we stop
        pos += 4
        bpm = _plausible(int(round(value)))
        if bpm is not None:
            return bpm
    return None


# TWO searches, not one alternation.
#
# `re.search` returns the LEFTMOST match, not the first matching branch. With
# the text "Tep: 73  Kroky: 1832" the pattern `(\d+)\s*kroky` caught
# "73  Kroky" - i.e. it read the heart rate as the step count - because it
# started earlier than "Kroky: 1832". A label before the number is less
# ambiguous, so it is tried first.
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
    """The first number that one of the patterns finds - in the order given."""
    for vzor in vzory:
        m = vzor.search(text)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", "."))
        except (TypeError, ValueError, AttributeError):
            continue
    return None


# SOURCE NAMES we can classify. The player names them themselves in the
# watch app, so there cannot be exact strings here.
#
# WORD BOUNDARIES ARE NECESSARY HERE, not cosmetics. Originally the key was
# searched for as a plain substring and `hr` has two characters: a source
# named "Threshold" or "HRV" was therefore classified as HEART RATE. It is
# exactly the same mistake as the Slovak "tep" inside the English
# "s-tep-s" - already the third time in this file.
#
# Longer keys are prefixes (`krok\w*` catches "kroky" and "Denne kroky"),
# short ones have a boundary on both sides (`hr\b` does not catch
# "Threshold"). The order matters: steps are tried FIRST.
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

# A purely numeric message - "86", "4,2", " 1045 ". We take nothing else as
# a metric value: if we pulled the first number out of any text, we would
# go right back to the bug that made the heart rate get read from the step
# count.
_HOLE_CISLO = re.compile(r"^[\s]*([-+]?\d+(?:[.,]\d+)?)[\s]*$")

# THE STEP COUNT HAS ITS OWN PATTERN, because it tolerates a thousands
# separator.
#
# The watch formats the number for the overlay by locale and sends "1,085"
# or "1 085" into the source. The shared pattern above took the comma as a
# decimal one and read 1 out of 1085 steps. Telling them apart at string
# level is impossible ("4,2" is a valid speed), but at METRIC level it is
# possible: a step is always a whole number, so for steps the separator is
# always the thousands one and never decimal.
_HOLY_POCET = re.compile(
    r"^[\s]*([-+]?\d{1,3}(?:[ .,\u00a0]\d{3})+|[-+]?\d+)[\s]*$")

# Steps are cumulative for the day, speed ranges from walking to running.
# Values outside that are a transfer error, not data - and wrong data is
# worse than none, because the app uses it to judge whether the player was
# sitting at the keyboard.
MAX_KROKOV = 200000
MAX_RYCHLOST_KMH = 50.0


def metrika_zdroja(meno):
    """`"bpm"` / `"steps"` / `"speed"` by OBS source name, otherwise `None`.

    `None` means "I do not know" and NOT "heart rate". A message from an
    unnamed source goes the old way through the labels in the text - where
    it went until now.
    """
    if not meno:
        return None
    n = meno.strip()
    for metrika, vzor in _ZDROJE_METRIK:
        if vzor.search(n):
            return metrika
    return None


def _hodnota_holeho_cisla(data, ako_pocet=False):
    """A number from a purely numeric message, otherwise None.

    `ako_pocet=True` is for steps: it allows a thousands separator and always
    returns a whole number. For heart rate and speed the comma stays decimal.
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
    """Everything one message can yield: heart rate, steps, speed.

    `zdroj` is the name of the OBS source the watch app has just written into.
    When we know it, it strictly decides what the message means - and a step
    source can NEVER produce a heart rate, even if the step count happened to
    fit into the human heart-rate range (in the morning after 140 steps
    exactly that was a risk).

    `jediny_zdroj` says whether someone else has also written into this run.
    We can only classify the names we know, and the player names them
    themselves - so `Cadence`, `Calories` or the Japanese \u6b69\u6570 are
    unknown to us. With a SINGLE source an unknown name is still heart rate,
    whatever it is called (the default source name in OBS is "Text 1" and
    many people do not rename it). As soon as AT LEAST TWO different sources
    write, the client is clearly splitting the metrics by source - and then
    a heart rate MUST NOT be guessed from a bare number from an unrecognised
    source any more. Otherwise the original bug would come back for everyone
    who named their step source differently than we expect.

    The premium version of the watch app can also send steps and speed into
    the same text. The app used to throw them away - yet they are the only
    DIRECT movement signal we have. Without it walking cannot be told apart
    from gaming load: in both cases only the heart rate goes up.

    A missing item is None, not zero. "We do not know" and "zero steps" are
    two different things, and mixing them up would mean claiming the player
    is sitting whenever the watch does not send steps.
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
        # AN UNKNOWN SOURCE AMONG SEVERAL: a bare number is not a heart rate.
        #
        # A label in the text ("Tep: 86") gets through here too - only a bare
        # number is suppressed, i.e. exactly the case where we have no way of
        # knowing what it is, and where it used to be guessed.
        if not jediny_zdroj and _hodnota_holeho_cisla(data) is not None:
            vysledok["bpm"] = None
        return vysledok

    # The source is named: if there was no label in the text, the whole body
    # of the message is the value of exactly this metric.
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

    # AND ABOVE ALL: no heart rate may come out of a step or speed source.
    # That is the whole reason the source name is carried all the way here.
    if metrika != "bpm":
        vysledok["bpm"] = None
    return vysledok


def _parse_bpm(data):
    # OSC goes first: it is binary and the text branch below would pull a
    # random number out of it from the bytes of the address
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

    # A NAMED NUMBER TAKES PRIORITY OVER "THE FIRST NUMBER IN THE TEXT".
    #
    # The premium version of the watch app can also send steps and speed into
    # the same text. Until now simply the first number was taken, which with
    # a text like "1832 krokov | 73 bpm" means reading the steps as the heart
    # rate. `_plausible` would reject them and return None, so the heart rate
    # would NOT ARRIVE AT ALL - and in the app it would look like a watch
    # dropout, not like a misread text.
    #
    # So first we look for a number that has a heart-rate label next to it,
    # and only when there is none do we reach for the first plausible number.
    menovka = re.search(
        # WORD BOUNDARIES ARE NECESSARY HERE, not cosmetics: the Slovak "tep"
        # is inside the English "S-tep-s". Without `\b` the pattern caught
        # "Steps" and read 183 as the heart rate out of "Steps: 1832".
        # `(?!\d)` in turn stops "1832" from yielding its first three digits.
        r"(?:\bbpm\b|\bhr\b|\bheart[\s_-]*rate\b|\btep\b|\bpuls\b)"
        r"[\s:=-]{0,3}(\d{1,3})(?!\d)"
        r"|(\d{1,3})(?!\d)\s*(?:\bbpm\b|\btep\b)",
        text, re.IGNORECASE)
    if menovka:
        cislo = menovka.group(1) or menovka.group(2)
        hodnota = _plausible(int(cislo))
        if hodnota is not None:
            return hodnota

    # Without a label: the first number that is a plausible heart rate at all.
    # Steps (thousands) and speed (0-20) are skipped that way on their own.
    for m in re.finditer(r"\d+", text):
        hodnota = _plausible(int(m.group()))
        if hodnota is not None:
            return hodnota
    return None
