"""Minimal obs-websocket v5 protocol server - only as much as it takes for
the smartwatch app to think it is talking to OBS.

Why this exists at all: "HeartRateOnStream for OBS" does not send the heart
rate ANYWHERE. It behaves as a client that connects to OBS and writes the
heart rate into a text source with a `SetInputSettings` request. Captured
traffic from a real watch looks like this:

    ->  {"op":0,"d":{"obsWebSocketVersion":"5.5.0","rpcVersion":1}}
    <-  {"op":1,"d":{"rpcVersion":1,"eventSubscriptions":132}}
    ->  {"op":2,"d":{"negotiatedRpcVersion":1}}
    <-  {"op":6,"d":{"requestType":"GetSceneList",...}}
    <-  {"op":6,"d":{"requestType":"SetInputSettings","requestData":
         {"inputName":"Tep","inputSettings":{"text":"63","read_from_file":false}}}}

The last line is all we care about - `inputSettings.text` holds the BPM.

So we pretend to be an OBS with a single scene and SEVERAL text sources. The
names are deliberately constant (not translated) - the player picks the
source on the phone once, and that choice must still hold after the app
language is switched.

WHY SEVERAL SOURCES AND WHY THE SOURCE NAME IS PASSED ON
The premium version of the watch app can also send steps and speed, but it
writes each metric to a SEPARATE text source - and sends only a bare number
to each one. On the wire you then see "86" and "1045" alternating without
any label. On 19. 9. 2026 this really happened, and the only reason it did
not produce another broken session was that 1045 is outside the plausible
heart-rate range. In the morning, at 140 steps walked, the app would already
have read 140 BPM.

The only information that tells those numbers apart is `inputName` in the
request. That is why `on_text` is called with the source name, and why there
are three sources here: so the player has something to choose from on the
phone.

No external library - the WebSocket handshake and the frames are a few lines
of stdlib.
"""

import base64
import hashlib
import json
import socket
import struct
import time

import logging_setup

log = logging_setup.get_logger("obs")

# Constant from RFC 6455 - appended to the client's key before hashing.
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

# The pretend scene and text source the player sees on the phone.
SCENE_NAME = "Zanshin"
SCENE_UUID = "7a6e5d4c-3b2a-4190-8f7e-6d5c4b3a2910"
INPUT_NAME = "Tep"
INPUT_UUID = "1f2e3d4c-5b6a-4798-9807-1a2b3c4d5e6f"
INPUT_KIND = "text_gdiplus_v3"

# Sources the player sees on the phone. Heart rate is required, the rest is a
# bonus for the premium version of the watch app. The names are deliberately
# simple and without diacritics - the player sees them in someone else's app
# that does not know Slovak.
ZDROJE = (
    (INPUT_NAME, INPUT_UUID),
    ("Kroky", "2f3e4d5c-6b7a-4891-9018-2b3c4d5e6f70"),
    ("Rychlost", "3f4e5d6c-7b8a-4902-9129-3c4d5e6f7081"),
)

# CONNECTION TIMEOUTS (0.2.1).
#
# Until now there were none. Anyone who opened a TCP connection and sent
# nothing held one of the 16 slots (`heart_rate._MAX_LIVE_SOCKETS`) forever -
# a port scanner, or a phone that left the Wi-Fi without saying goodbye (the
# connection on our side then hangs half-open and no packet will ever close
# it). Fourteen of those and the real phone (the app that sends the heart
# rate from the watch) could no longer connect.
#
# Handshake: a real client sends the HTTP upgrade right after connecting.
# 10 s is the TOTAL limit (not per `recv`); even slow Wi-Fi manages it with
# room to spare.
HANDSHAKE_TIMEOUT_S = 10.0
# After the handshake: the phone app writes every ~1 to ~3 s. Only after
# NECINNOST_S of complete silence do we send a ping - per RFC 6455 every
# WebSocket library answers it ON ITS OWN, so a live but quiet phone (the
# watch with measuring paused) does NOT LOSE the connection. Only
# when nothing arrives for another NECINNOST_S is the connection dead, and it
# is closed like any other disconnect. So a dead connection disappears within
# 2 minutes at the latest.
#
# Why not shorter: a false "phone disconnected" (and with it a discarded
# countdown in the trigger) is worse than a minute of waiting for a slot to
# free up. The heart rate reports an outage on its own after 12 s anyway
# (`HeartRateMonitor.STALE_AFTER_S`); this limit only serves to clean up the
# socket, not to detect an outage.
NECINNOST_S = 60.0

# The largest frame we accept. Real messages are hundreds of bytes (a heart
# rate write ~150 B, a batch of several requests a few kB) - 64 kB is over a
# hundred times a heart rate write, leaves even a batch more than tenfold
# headroom, and it is the same cap as for the HTTP header in `handshake`.
# Until now it was 1 MB: a megabyte of memory and CPU for every inflated
# frame from anyone on the LAN, while no real message comes anywhere near it.
_MAX_RAMEC = 64 * 1024

# No frame started: the socket timeout expired between frames. It is NOT the
# end of the connection - see `NECINNOST_S`. A valid opcode is 0..15, so it
# cannot be mistaken for one.
TICHO = -1


# --------------------------------------------------------------------------
# WebSocket layer
# --------------------------------------------------------------------------

def _recv_exact(conn, count):
    buf = b""
    while len(buf) < count:
        chunk = conn.recv(count - len(buf))
        if not chunk:
            raise ConnectionError("spojenie zatvorene")
        buf += chunk
    return buf


def handshake(conn):
    """Completes the HTTP upgrade to WebSocket. True if it succeeded.

    The whole handshake must fit within HANDSHAKE_TIMEOUT_S - before every
    `recv` the limit is cut by the time already spent, otherwise a client
    sending one byte at a time could stretch it out forever."""
    koniec = time.monotonic() + HANDSHAKE_TIMEOUT_S
    raw = b""
    while b"\r\n\r\n" not in raw:
        zostava = koniec - time.monotonic()
        if zostava <= 0:
            return False
        try:
            conn.settimeout(zostava)
            chunk = conn.recv(4096)
        except OSError:                   # including a timeout
            return False
        if not chunk:
            return False
        raw += chunk
        if len(raw) > 65536:              # no sane client sends a bigger header
            return False

    headers = {}
    for line in raw.decode("utf-8", "ignore").split("\r\n")[1:]:
        if ": " in line:
            name, value = line.split(": ", 1)
            headers[name.lower()] = value

    key = headers.get("sec-websocket-key")
    if not key or "websocket" not in headers.get("upgrade", "").lower():
        return False

    accept = base64.b64encode(
        hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
    response = ("HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n")
    requested = headers.get("sec-websocket-protocol")
    if requested:
        # We pick ONLY the subprotocol we can read - JSON. Until now the
        # FIRST one offered was echoed; when the client offered
        # "obswebsocket.msgpack, obswebsocket.json", we agreed on msgpack
        # and the client then sent binary frames that the parser (JSON only)
        # cannot read - "connected, silence" without a single error (B31).
        # If it did not offer JSON, we pick nothing and leave it to the client.
        ponuka = [p.strip() for p in requested.split(",")]
        vybrany = next((p for p in ponuka if "json" in p.lower()), None)
        if vybrany:
            response += f"Sec-WebSocket-Protocol: {vybrany}\r\n"
    conn.sendall((response + "\r\n").encode())
    return True


def _odmaskuj(payload, mask):
    """XOR with the repeated 4-byte mask (RFC 6455, 5.3) all at once, via one
    integer. Until now it was done byte by byte in Python: with the old 1 MB
    cap that was ~40 ms of CPU (and the GIL, which the GUI thread also needs)
    for EVERY frame, so anything on the LAN sending frame after frame kept
    the app busy. Via an integer it is over 10x faster, and on top of that
    the cap is 16x lower."""
    n = len(payload)
    if not n:
        return b""
    kluc = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(payload, "big")
            ^ int.from_bytes(kluc, "big")).to_bytes(n, "big")


def read_frame(conn):
    """(opcode, payload), or (None, None) when the connection has ended.

    `(TICHO, None)` when the socket timeout expired between frames and not a
    single byte arrived - the connection may be alive, just quiet (see
    `NECINNOST_S`). That is why the first byte is read separately: if the
    timeout expired after one of the two header bytes, that one byte would be
    lost and the rest of the connection would be read shifted.
    """
    try:
        first = _recv_exact(conn, 1)[0]
    except socket.timeout:
        return TICHO, None
    except (ConnectionError, OSError):
        return None, None
    try:
        second = _recv_exact(conn, 1)[0]
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", _recv_exact(conn, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _recv_exact(conn, 8))[0]
        if length > _MAX_RAMEC:
            return None, None
        mask = _recv_exact(conn, 4) if masked else None
        payload = _recv_exact(conn, length) if length else b""
    except (ConnectionError, OSError):
        # Including a timeout IN THE MIDDLE of a frame: a sane client does
        # not get stuck halfway through a frame for a minute, so the
        # connection ends.
        return None, None
    if mask:
        payload = _odmaskuj(payload, mask)
    return opcode, payload


def send_frame(conn, payload, opcode=_OP_TEXT):
    header = bytes([0x80 | opcode])
    size = len(payload)
    if size < 126:
        header += bytes([size])
    elif size < 65536:
        header += bytes([126]) + struct.pack(">H", size)
    else:
        header += bytes([127]) + struct.pack(">Q", size)
    conn.sendall(header + payload)


# --------------------------------------------------------------------------
# obs-websocket v5
# --------------------------------------------------------------------------

# Opcodes that may be silently ignored, because no reply belongs to them.
# Anything else is written to the journal - see the `op 8` branch below.
_TICHE_OP = frozenset((0, 2, 5, 7, 9))

# CAPS ON WHAT THE CLIENT CAN CHOOSE IN ONE CONNECTION (0.2.1).
#
# Every `inputName` from a request was added to the list of sources without a
# limit, and every reply to GetInputList/GetSceneItemList sent the whole list
# - so a client sending ever new names inflated both the memory and every
# following reply. The real app writes to a few sources (heart rate, steps,
# speed, sometimes the same one twice); 32 names leave room even for a player
# who names them themselves. Nobody gives a name longer than 256 characters in
# OBS. Whatever does not fit is just NOT REMEMBERED: a write with such a name
# goes on normally, the name just does not appear in the list of sources.
_MAX_VLASTNYCH = 32
_MAX_DLZKA_MENA = 256
# At most this many unknown kinds of requests and opcodes are written to the
# journal per connection, and only the first 80 characters of each. The client
# chooses `requestType` - until now it could write a megabyte into the journal
# with one frame and flood it with ever new kinds (the journal rotates at 1 MB,
# so it would push out everything useful).
_MAX_NEPOZNANYCH = 16
_MAX_ZNAKOV_DO_DENNIKA = 80


def _do_dennika(hodnota):
    """Client-chosen value shortened for the journal (`%s`, not `%r`)."""
    if isinstance(hodnota, str):
        # no need to repr a whole megabyte, one char past the cut is enough
        hodnota = hodnota[:_MAX_ZNAKOV_DO_DENNIKA + 1]
    text = repr(hodnota)
    if len(text) > _MAX_ZNAKOV_DO_DENNIKA:
        return text[:_MAX_ZNAKOV_DO_DENNIKA] + "..."
    return text


def _odbav(data, on_text, vlastne, nepoznane, zapis_ok=True):
    """One request (standalone or from a batch) -> the reply body.

    Split out of `serve_connection` precisely so that a batch (`op 8`) goes
    the SAME way as a standalone request and the two cannot drift apart.

    `zapis_ok=False` means the client has NOT IDENTIFIED itself yet (op 1).
    Then reads are handled normally, but a heart rate WRITE is refused:
    without that, anything on the LAN that completes the WS handshake could
    send an arbitrary "BPM" and it would be recorded as a real heart rate
    (bug B6).
    """
    request_type = data.get("requestType", "")
    request_data = data.get("requestData")
    if not isinstance(request_data, dict):
        request_data = {}
    meno = request_data.get("inputName")
    if (isinstance(meno, str) and meno and len(meno) <= _MAX_DLZKA_MENA
            and len(vlastne) < _MAX_VLASTNYCH):
        vlastne.add(meno)              # so GetInputList knows it from now on
    if request_type == "SetInputSettings":
        zdroj, text = _extract_write(request_data, vlastne)
        if text is not None and zapis_ok:
            on_text(text, zdroj)
        elif text is not None and "_zapis_pred_identify" not in nepoznane:
            nepoznane.add("_zapis_pred_identify")
            log.warning("OBS: zápis tepu pred Identify odmietnutý")
    elif (request_type not in _ZNAME and request_type not in nepoznane
          and len(nepoznane) < _MAX_NEPOZNANYCH):
        # UNKNOWN REQUEST INTO THE JOURNAL, each kind once per connection.
        #
        # An empty reply is as bad as none for some apps: they wait for a
        # specific field, never get it and after 10 seconds report
        # "timeout". Without this entry there is no way to find out on what.
        nepoznane.add(request_type)
        log.info("OBS: neznama poziadavka %s - odpovedam prazdnym objektom",
                 _do_dennika(request_type))
    return {
        "requestType": request_type,
        "requestId": data.get("requestId"),
        "requestStatus": {"result": True, "code": 100},
        "responseData": _response_data(request_type, vlastne, request_data),
    }


# Requests we can answer meaningfully. Anything outside this list gets an
# empty object and is written to the journal.
_ZNAME = frozenset((
    "GetVersion", "GetCurrentProgramScene", "GetSceneList", "GetInputList",
    "GetInputKindList", "GetSceneItemList", "GetInputSettings",
    "GetInputDefaultSettings", "GetStudioModeEnabled", "SetInputSettings",
    "CreateInput", "CreateSceneItem",
))


def _uuid_pre(meno):
    """A stable UUID derived from the source name.

    Real OBS has it from its own database, we have nowhere to take it from -
    but the client often sends it back in the next request and it has to
    match. Deriving it from the name guarantees that the same name gets the
    same UUID even after the app restarts.
    """
    h = hashlib.md5(meno.encode("utf-8")).hexdigest()
    return "%s-%s-4%s-8%s-%s" % (h[0:8], h[8:12], h[13:16], h[17:20], h[20:32])


def _zoznam_zdrojov(extra=()):
    """Our three sources plus those the client asked for in this connection."""
    zoznam = [(meno, uuid) for meno, uuid in ZDROJE]
    mena = set(meno for meno, _ in zoznam)
    for meno in sorted(extra):
        if meno and meno not in mena:
            zoznam.append((meno, _uuid_pre(meno)))
            mena.add(meno)
    return zoznam


def _response_data(request_type, extra=(), request_data=None):
    """Plausible replies of the pretend OBS. If we leave one out or send it
    empty, the client closes the connection and starts reconnecting."""
    zoznam = _zoznam_zdrojov(extra)
    if request_type == "GetVersion":
        return {"obsVersion": "30.2.3", "obsWebSocketVersion": "5.5.0",
                "rpcVersion": 1, "availableRequests": [],
                "supportedImageFormats": ["png"], "platform": "windows",
                "platformDescription": "Windows"}
    if request_type == "GetCurrentProgramScene":
        return {"currentProgramSceneName": SCENE_NAME,
                "currentProgramSceneUuid": SCENE_UUID,
                "sceneName": SCENE_NAME, "sceneUuid": SCENE_UUID}
    if request_type == "GetSceneList":
        return {"currentProgramSceneName": SCENE_NAME,
                "currentProgramSceneUuid": SCENE_UUID,
                "currentPreviewSceneName": None, "currentPreviewSceneUuid": None,
                "scenes": [{"sceneName": SCENE_NAME, "sceneUuid": SCENE_UUID,
                            "sceneIndex": 0}]}
    if request_type == "GetInputList":
        return {"inputs": [{"inputName": meno, "inputUuid": uuid,
                            "inputKind": INPUT_KIND,
                            "unversionedInputKind": "text_gdiplus"}
                           for meno, uuid in zoznam]}
    if request_type == "GetInputKindList":
        return {"inputKinds": [INPUT_KIND, "text_gdiplus", "text_ft2_source_v2"]}
    if request_type == "GetSceneItemList":
        return {"sceneItems": [{
            "sceneItemId": i + 1, "sceneItemIndex": i,
            "sourceName": meno, "sourceUuid": uuid,
            "sourceType": "OBS_SOURCE_TYPE_INPUT", "inputKind": INPUT_KIND,
            "isGroup": None, "sceneItemEnabled": True, "sceneItemLocked": False,
            "sceneItemBlendMode": "OBS_BLEND_NORMAL",
            "sceneItemTransform": {
                "positionX": 0, "positionY": 60 * i, "width": 200, "height": 50,
                "sourceWidth": 200, "sourceHeight": 50, "scaleX": 1, "scaleY": 1,
                "rotation": 0, "alignment": 5, "boundsType": "OBS_BOUNDS_NONE",
                "boundsAlignment": 0, "boundsWidth": 0, "boundsHeight": 0,
                "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0}}
            for i, (meno, uuid) in enumerate(zoznam)]}
    if request_type == "GetInputSettings":
        return {"inputKind": INPUT_KIND, "inputSettings": {"text": ""}}
    if request_type == "GetInputDefaultSettings":
        return {"defaultInputSettings": {"text": ""}}
    if request_type == "GetStudioModeEnabled":
        return {"studioModeEnabled": False}
    if request_type in ("CreateInput", "CreateSceneItem"):
        # The client may create a source. Real OBS returns its UUID and the
        # item number in the scene; without both, some apps wait for the reply
        # until the timeout and then report that the receiver does not exist.
        meno = (request_data or {}).get("inputName") or ""
        mapa = dict(zoznam)
        uuid = mapa.get(meno) or _uuid_pre(meno)
        mena = [m for m, _ in zoznam]
        index = mena.index(meno) if meno in mapa else len(zoznam)
        return {"inputUuid": uuid, "sceneItemId": index + 1}
    return {}


def _meno_z_uuid(uuid, extra=()):
    """Source name for an `inputUuid`, or None.

    obs-websocket v5 also allows addressing a source by `inputUuid` instead of
    the name. We handed out the UUIDs ourselves (fixed in `ZDROJE`, the ones
    created by the client via `_uuid_pre`), so we can map them back to a
    name. Without that, a write addressed by UUID would have no name,
    `metrika_zdroja(None)` would return None and a bare number from the steps
    would be read as heart rate (B7).
    """
    if not uuid:
        return None
    for meno, u in ZDROJE:
        if u == uuid:
            return meno
    for meno in extra:
        if meno and _uuid_pre(meno) == uuid:
            return meno
    return None


def _extract_write(request_data, vlastne=()):
    """One write into a text source: `(source name, text)`.

    The name matters here as much as the text. The watch app writes each
    metric into a different source and sends a BARE NUMBER - `86` and `1045`
    cannot be told apart without the source name, and the heart rate would be
    read from the step count. When the client addresses the source by
    `inputUuid` instead of the name, we look the name up (B7).
    """
    if not isinstance(request_data, dict):
        return None, None
    settings = request_data.get("inputSettings")
    if not isinstance(settings, dict):
        return None, None
    value = settings.get("text")
    if not isinstance(value, str):
        return None, None
    meno = request_data.get("inputName")
    if not isinstance(meno, str) or not meno:
        meno = _meno_z_uuid(request_data.get("inputUuid"), vlastne)
    return meno, value


def serve_connection(conn, on_text, should_stop, on_connected=None):
    """Handles one obs-websocket client connection.

    `on_text(text, meno_zdroja)` is called on every write into a text
    source. The name can be `None` when the client did not send it.
    `on_connected()` right after a successful handshake - thanks to that
    the UI can tell "nobody has connected yet" from "the phone is
    connected, but the heart rate is not coming", which are completely
    different problems.
    `should_stop()` is asked between frames whether we should stop yet.

    It sets the socket timeouts itself (see `HANDSHAKE_TIMEOUT_S` and
    `NECINNOST_S`); the receiver's `stop()` closes the socket right away
    anyway, which unblocks the read immediately, not only after the limit."""
    if not handshake(conn):
        return
    conn.settimeout(NECINNOST_S)
    if on_connected is not None:
        on_connected()

    # Hello WITHOUT the "authentication" object = the server wants no password.
    # So the player does not have to fill in anything else on the phone.
    send_frame(conn, json.dumps({
        "op": 0, "d": {"obsWebSocketVersion": "5.5.0", "rpcVersion": 1}}).encode())

    # Sources the client asked for or created in this connection, and the kinds
    # of requests we have already warned about - so that the journal is not
    # flooded by a client that asks for the same thing twice a second.
    vlastne = set()
    nepoznane = set()
    # The client must identify itself first (op 1) before we accept a heart rate
    # write. The real phone app does this (the protocol requires it); this only
    # shuts the door on anything on the LAN that would want to write a heart rate
    # without identifying (B6).
    identified = False
    # After the first silence we sent a ping and wait for anything (pong, heart
    # rate...).
    ping_poslany = False

    while not should_stop():
        opcode, payload = read_frame(conn)
        if opcode == TICHO:
            if ping_poslany or should_stop():
                return                  # nothing even to the ping - the connection is dead
            ping_poslany = True
            send_frame(conn, b"", opcode=_OP_PING)
            continue
        ping_poslany = False
        if opcode is None or opcode == _OP_CLOSE:
            return
        if opcode == _OP_PING:
            send_frame(conn, payload, opcode=_OP_PONG)
            continue
        if opcode not in (_OP_TEXT, _OP_BINARY):
            continue

        try:
            message = json.loads(payload.decode("utf-8", "ignore"))
        except Exception:
            continue
        if not isinstance(message, dict):
            continue

        op = message.get("op")
        data = message.get("d") if isinstance(message.get("d"), dict) else {}

        if op == 1:                                   # Identify
            identified = True
            send_frame(conn, json.dumps({
                "op": 2, "d": {"negotiatedRpcVersion": 1}}).encode())
        elif op == 6:                                 # Request
            send_frame(conn, json.dumps({
                "op": 7, "d": _odbav(data, on_text, vlastne, nepoznane,
                                     zapis_ok=identified),
            }).encode())
        elif op == 8:                                 # RequestBatch
            # WITHOUT THIS BRANCH THE CLIENT WAITED UNTIL THE TIMEOUT.
            #
            # A watch app that sends several metrics tends to send them
            # AT ONCE as a batch. Until now the batch fell through the whole
            # if/elif chain: no reply, no journal entry - and after ten
            # seconds the client reported that the receiver does not exist.
            # Not even the unknown-request entry caught it, because that one
            # is inside the `op == 6` branch, which the batch never reached.
            requests = data.get("requests")
            vysledky = [_odbav(r, on_text, vlastne, nepoznane,
                               zapis_ok=identified)
                        for r in (requests if isinstance(requests, list) else [])
                        if isinstance(r, dict)]
            send_frame(conn, json.dumps({
                "op": 9, "d": {"requestId": data.get("requestId"),
                               "results": vysledky}}).encode())
        elif op not in _TICHE_OP and op not in nepoznane:
            # Everything else at least into the journal - exactly the silence
            # around `op 8` cost three days of searching.
            if len(nepoznane) < _MAX_NEPOZNANYCH:
                nepoznane.add(op)
                log.info("OBS: neznamy op %s - neodpovedam", _do_dennika(op))
