"""Minimalny server protokolu obs-websocket v5 - len tolko, kolko treba,
aby si appka na hodinkach myslela, ze sa rozprava s OBS.

Preco to vobec existuje: "HeartRateOnStream for OBS" tep NIKAM neposiela.
Sprava sa ako klient, ktory sa pripoji k OBS a zapisuje tep do textoveho
zdroja poziadavkou `SetInputSettings`. Zachytena komunikacia z realnych
hodiniek vyzera takto:

    ->  {"op":0,"d":{"obsWebSocketVersion":"5.5.0","rpcVersion":1}}
    <-  {"op":1,"d":{"rpcVersion":1,"eventSubscriptions":132}}
    ->  {"op":2,"d":{"negotiatedRpcVersion":1}}
    <-  {"op":6,"d":{"requestType":"GetSceneList",...}}
    <-  {"op":6,"d":{"requestType":"SetInputSettings","requestData":
         {"inputName":"Tep","inputSettings":{"text":"63","read_from_file":false}}}}

Posledny riadok je cely nas zaujem - v `inputSettings.text` je BPM.

Predstierame teda OBS s jedinou scenou a NIEKOLKYMI textovymi zdrojmi. Nazvy
su zamerne konstantne (nie prelozene) - hrac si zdroj v telefone vyberie raz a
jeho volba musi platit aj po prepnuti jazyka appky.

PRECO VIAC ZDROJOV A PRECO SA MENO ZDROJA POSIELA DALEJ
Premiova verzia appky na hodinkach vie posielat aj kroky a rychlost, lenze
kazdu metriku pise do SAMOSTATNEHO textoveho zdroja - a do kazdeho posle len
hole cislo. Na drote potom vidno striedavo "86" a "1045" bez akejkolvek
menovky. 19. 9. 2026 to takto realne chodilo a jediny dovod, preco z toho
nevznikla dalsia pokazena relacia, bol ten, ze 1045 je mimo vierohodneho
rozsahu tepu. Rano, pri 140 nachodenych krokoch, by uz appka citala 140 BPM.

Jedina informacia, ktora tie cisla rozlisuje, je `inputName` v poziadavke.
Preto sa `on_text` vola s menom zdroja a preto tu zdroje su tri: aby si ich
hrac v telefone mal odkial vybrat.

Ziadna externa kniznica - WebSocket handshake aj ramce su par riadkov stdlib.
"""

import base64
import hashlib
import json
import struct

import logging_setup

log = logging_setup.get_logger("obs")

# Konstanta z RFC 6455 - pripaja sa ku klucu klienta pred zahashovanim.
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

# Predstierana scena a textovy zdroj, ktore uvidi hrac v telefone.
SCENE_NAME = "Zanshin"
SCENE_UUID = "7a6e5d4c-3b2a-4190-8f7e-6d5c4b3a2910"
INPUT_NAME = "Tep"
INPUT_UUID = "1f2e3d4c-5b6a-4798-9807-1a2b3c4d5e6f"
INPUT_KIND = "text_gdiplus_v3"

# Zdroje, ktore hrac uvidi v telefone. Tep je povinny, zvysok je bonus pre
# premiovu verziu appky na hodinkach. Mena su naschval jednoduche a bez
# diakritiky - hrac ich vidi v cudzej appke, ktora slovencinu nepozna.
ZDROJE = (
    (INPUT_NAME, INPUT_UUID),
    ("Kroky", "2f3e4d5c-6b7a-4891-9018-2b3c4d5e6f70"),
    ("Rychlost", "3f4e5d6c-7b8a-4902-9129-3c4d5e6f7081"),
)


# --------------------------------------------------------------------------
# WebSocket vrstva
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
    """Dokonci HTTP upgrade na WebSocket. True ak sa to podarilo."""
    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = conn.recv(4096)
        if not chunk:
            return False
        raw += chunk
        if len(raw) > 65536:              # nikto rozumny neposle vacsiu hlavicku
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
        # Vyberieme LEN subprotokol, ktory vieme citat - JSON. Doteraz sa
        # echoval PRVY ponuknuty; ked klient ponukol "obswebsocket.msgpack,
        # obswebsocket.json", dohodli sme sa na msgpacku a klient potom
        # posielal binarne ramce, ktore parser (len JSON) nevie precitat -
        # "pripojene, ticho" bez jedinej chyby (B31). Ak JSON neponukol,
        # nevyberieme nic a nechame to na klienta.
        ponuka = [p.strip() for p in requested.split(",")]
        vybrany = next((p for p in ponuka if "json" in p.lower()), None)
        if vybrany:
            response += f"Sec-WebSocket-Protocol: {vybrany}\r\n"
    conn.sendall((response + "\r\n").encode())
    return True


def read_frame(conn):
    """(opcode, payload) alebo (None, None) ked spojenie skoncilo."""
    try:
        first, second = _recv_exact(conn, 2)
    except (ConnectionError, OSError):
        return None, None
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(conn, 8))[0]
    if length > 1 << 20:                  # 1 MB je uz zjavne nezmysel
        return None, None
    mask = _recv_exact(conn, 4) if masked else None
    payload = _recv_exact(conn, length) if length else b""
    if mask:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
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

# Opkody, ktore sa smu ticho ignorovat, lebo na ne odpoved nepatri.
# Cokolvek ine sa zapise do dennika - viz vetva `op 8` nizsie.
_TICHE_OP = frozenset((0, 2, 5, 7, 9))


def _odbav(data, on_text, vlastne, nepoznane, zapis_ok=True):
    """Jedna poziadavka (samostatna aj z davky) -> telo odpovede.

    Vydelene z `serve_connection` prave preto, aby davka (`op 8`) chodila
    ROVNAKOU cestou ako samostatna poziadavka a nemohla sa rozist.

    `zapis_ok=False` znamena, ze klient sa este NEIDENTIFIKOVAL (op 1). Vtedy
    sa citania odbavia normalne, ale ZAPIS tepu sa odmietne: bez toho by
    hocico v LAN, co dokonci WS handshake, mohlo poslat lubovolne "BPM" a
    zapisalo by sa ako realny tep (bug B6).
    """
    request_type = data.get("requestType", "")
    request_data = data.get("requestData")
    if not isinstance(request_data, dict):
        request_data = {}
    meno = request_data.get("inputName")
    if isinstance(meno, str) and meno:
        vlastne.add(meno)              # nech ho GetInputList uz pozna
    if request_type == "SetInputSettings":
        zdroj, text = _extract_write(request_data, vlastne)
        if text is not None and zapis_ok:
            on_text(text, zdroj)
        elif text is not None and "_zapis_pred_identify" not in nepoznane:
            nepoznane.add("_zapis_pred_identify")
            log.warning("OBS: zápis tepu pred Identify odmietnutý")
    elif request_type not in _ZNAME and request_type not in nepoznane:
        # NEZNAMA POZIADAVKA DO DENNIKA, kazdy druh raz za spojenie.
        #
        # Prazdna odpoved je pre niektore appky rovnako zla ako ziadna:
        # cakaju na konkretne pole, nedockaju sa a po 10 sekundach hlasia
        # "timeout". Bez tohto zapisu sa neda zistit, na com.
        nepoznane.add(request_type)
        log.info("OBS: neznama poziadavka %r - odpovedam prazdnym objektom",
                 request_type)
    return {
        "requestType": request_type,
        "requestId": data.get("requestId"),
        "requestStatus": {"result": True, "code": 100},
        "responseData": _response_data(request_type, vlastne, request_data),
    }


# Poziadavky, na ktore vieme odpovedat zmysluplne. Cokolvek mimo tohto
# zoznamu dostane prazdny objekt a zapise sa do dennika.
_ZNAME = frozenset((
    "GetVersion", "GetCurrentProgramScene", "GetSceneList", "GetInputList",
    "GetInputKindList", "GetSceneItemList", "GetInputSettings",
    "GetInputDefaultSettings", "GetStudioModeEnabled", "SetInputSettings",
    "CreateInput", "CreateSceneItem",
))


def _uuid_pre(meno):
    """Stabilne UUID odvodene od mena zdroja.

    Realny OBS ho ma z vlastnej databazy, my ho nemame kde vziat - ale klient
    ho casto posle spat v dalsej poziadavke a musi sediet. Odvodenie z mena
    zaruci, ze to iste meno dostane to iste UUID aj po restarte appky.
    """
    h = hashlib.md5(meno.encode("utf-8")).hexdigest()
    return "%s-%s-4%s-8%s-%s" % (h[0:8], h[8:12], h[13:16], h[17:20], h[20:32])


def _zoznam_zdrojov(extra=()):
    """Nase tri zdroje plus tie, ktore si klient v tomto spojeni vypytal."""
    zoznam = [(meno, uuid) for meno, uuid in ZDROJE]
    mena = set(meno for meno, _ in zoznam)
    for meno in sorted(extra):
        if meno and meno not in mena:
            zoznam.append((meno, _uuid_pre(meno)))
            mena.add(meno)
    return zoznam


def _response_data(request_type, extra=(), request_data=None):
    """Vierohodne odpovede predstieraneho OBS. Ak niektoru vynechame alebo
    posleme prazdnu, klient spojenie zavrie a zacne sa znova pripajat."""
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
        # Klient si smie zdroj vyrobit. Realny OBS vrati jeho UUID a cislo
        # polozky v scene; bez oboch niektore appky cakaju na odpoved do
        # vyprsania limitu a potom hlasia, ze prijimac neexistuje.
        meno = (request_data or {}).get("inputName") or ""
        mapa = dict(zoznam)
        uuid = mapa.get(meno) or _uuid_pre(meno)
        mena = [m for m, _ in zoznam]
        index = mena.index(meno) if meno in mapa else len(zoznam)
        return {"inputUuid": uuid, "sceneItemId": index + 1}
    return {}


def _meno_z_uuid(uuid, extra=()):
    """Meno zdroja podla `inputUuid`, alebo None.

    obs-websocket v5 dovoluje adresovat zdroj aj cez `inputUuid` namiesto
    mena. UUID sme rozdavali sami (fixne v `ZDROJE`, klientom vyrobene cez
    `_uuid_pre`), takze ich vieme zmapovat spat na meno. Bez toho by write
    adresovany cez UUID nemal meno, `metrika_zdroja(None)` by vratila None a
    hole cislo z krokov by sa citalo ako tep (B7).
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
    """Jeden zapis do textoveho zdroja: `(meno zdroja, text)`.

    Meno je tu rovnako dolezite ako text. Appka na hodinkach pise kazdu
    metriku do ineho zdroja a posiela HOLE CISLO - `86` a `1045` sa bez mena
    zdroja nedaju rozlisit a tep by sa cital z poctu krokov. Ked klient
    adresuje zdroj cez `inputUuid` namiesto mena, meno dohladame (B7).
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
    """Odbavi jedno spojenie klienta obs-websocket.

    `on_text(text, meno_zdroja)` sa zavola pri kazdom zapise do textoveho
    zdroja. Meno moze byt `None`, ked ho klient neposlal.
    `on_connected()` hned po uspesnom handshake - vdaka tomu vie UI
    rozlisit "este sa nikto nepripojil" od "hodinky su pripojene, ale
    neposielaju tep", co su uplne ine problemy.
    `should_stop()` sa pyta medzi ramcami, ci uz mame skoncit."""
    if not handshake(conn):
        return
    if on_connected is not None:
        on_connected()

    # Hello BEZ objektu "authentication" = server nechce heslo. Hrac tak
    # nemusi v telefone nic dalsie vyplnat.
    send_frame(conn, json.dumps({
        "op": 0, "d": {"obsWebSocketVersion": "5.5.0", "rpcVersion": 1}}).encode())

    # Zdroje, ktore si klient v tomto spojeni vypytal alebo vyrobil, a druhy
    # poziadaviek, na ktore sme uz upozornili - aby dennik nezaplavil klient,
    # ktory sa pyta na to iste dvakrat za sekundu.
    vlastne = set()
    nepoznane = set()
    # Klient sa musí najprv identifikovať (op 1), než príjmeme zápis tepu.
    # Skutočné hodinky to robia (protokol to vyžaduje); toto len zavrie dvere
    # pred čímkoľvek v LAN, čo by chcelo zapísať tep bez identifikácie (B6).
    identified = False

    while not should_stop():
        opcode, payload = read_frame(conn)
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
            # BEZ TEJTO VETVY KLIENT CAKAL DO VYPRSANIA LIMITU.
            #
            # Appka na hodinkach, ktora posiela viac metrik, ich zvykne
            # poslat NARAZ ako davku. Davka doteraz prepadla cez cely
            # if/elif retazec: ziadna odpoved, ziadny zapis do dennika - a
            # klient po desiatich sekundach hlasil, ze prijimac neexistuje.
            # Ani zapis o neznamej poziadavke to nechytil, lebo ten je
            # vnutri vetvy `op == 6`, kam sa davka nikdy nedostala.
            requests = data.get("requests")
            vysledky = [_odbav(r, on_text, vlastne, nepoznane,
                               zapis_ok=identified)
                        for r in (requests if isinstance(requests, list) else [])
                        if isinstance(r, dict)]
            send_frame(conn, json.dumps({
                "op": 9, "d": {"requestId": data.get("requestId"),
                               "results": vysledky}}).encode())
        elif op not in _TICHE_OP and op not in nepoznane:
            # Vsetko ostatne aspon do dennika - prave ticho okolo `op 8`
            # stalo tri dni hladania.
            nepoznane.add(op)
            log.info("OBS: neznamy op %r - neodpovedam", op)
