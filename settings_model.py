"""Datovy model slotov a globalnych nastaveni - predvolene hodnoty,
normalizacia nacitanych/importovanych dat, popisky pre UI dropdowny.

Ciste funkcie/konstanty bez UI a bez I/O (okrem tr() prekladov) - pouziva
ich app.py aj ui_dialogs.py, aby obe strany pracovali s rovnakym tvarom
dat a rovnakymi rozsahmi hodnot.
"""

import os
import uuid

import theme as theme_mod
import sfx_assets
from i18n import tr

# --------------------------------------------------------------------------
# Rezimy slotu (hlas / SFX / kombinacia) a TTS motory
# --------------------------------------------------------------------------

MODE_TTS = "tts"
MODE_SFX = "sfx"
MODE_COMBO = "combo"
MODE_ORDER = [MODE_TTS, MODE_SFX, MODE_COMBO]


def mode_labels():
    return {MODE_TTS: tr("mode.tts"), MODE_SFX: tr("mode.sfx"), MODE_COMBO: tr("mode.combo")}


def label_to_mode():
    return {v: k for k, v in mode_labels().items()}


ENGINE_EDGE = "edge"
ENGINE_SAPI = "sapi"


def engine_labels():
    return {ENGINE_EDGE: tr("engine.edge"), ENGINE_SAPI: tr("engine.sapi")}


def label_to_engine():
    return {v: k for k, v in engine_labels().items()}

# Sablona jedneho slotu - zaroven zoznam povolenych klucov v nastaveniach.
DEFAULT_SLOT = {
    "key_type": "keyboard",   # keyboard | mouse
    "key_repr": "",
    "text": "",
    "mode": MODE_TTS,         # tts | sfx | combo
    "audio_path": "",         # vlastny/nahraty subor pre SFX vrstvu
    "sfx_key": "",            # "" auto | "pack:kluc" preset | "__custom__"
    "enabled": True,
    "voice_edge": "",         # "" = pouzi globalny hlas
    "voice_sapi": "",
    "voice_path": "",         # vlastna nahravka HLASU - ak je, hraje sa
                              # namiesto TTS (viz app._speak_text). Oddelene
                              # od audio_path (to je SFX vrstva).
    "uid": "",                # stabilny identifikator slotu - pouziva sa na
                              # mena nahravok, aby sa nekrizili medzi profilmi
                              # (doplni ho normalize_slot, ak chyba).
    "cooldown": None,         # None = pouzi globalny cooldown
    "delay": 0.0,             # oneskorenie pred prehratim (s)
    "every_n": 1,             # spusti sa kazde N-te stlacenie
    "repeat": 1,              # kolkokrat zopakovat
    "repeat_gap": 0.5,        # pauza medzi opakovaniami (s)
    "jitter": 0.0,            # nahodne rozptylenie cooldownu (0.0 - 0.9)
}


def default_slots():
    """4 zakladne predvolene sloty pre nove instalacie - vzdy Kombinacia
    (Hlas+SFX), Zen SFX sada, cisté zakladne casovanie (ziadny delay,
    ziadny jitter, kazde 1. stlacenie - DEFAULT_SLOT default). Text hlasky
    sleduje aktualny jazyk UI (viz i18n slot.default.*).

    Ci je slot po onboardingu zapnuty (enabled) rozhoduje az
    DandurfApp._apply_diagnostics() podla checklistu v kroku 2 - tu su
    vsetky 4 pripravene s enabled=True (DEFAULT_SLOT default) a onboarding
    prípadne niektore vypne."""
    return [
        dict(DEFAULT_SLOT, key_type="keyboard", key_repr="c",
             text=tr("slot.default.grounding"),
             mode=MODE_COMBO, sfx_key=f"{theme_mod.ZEN}:earth_thud"),
        dict(DEFAULT_SLOT, key_type="keyboard", key_repr="r",
             text=tr("slot.default.jaw"),
             mode=MODE_COMBO, sfx_key=f"{theme_mod.ZEN}:wood_temple_block"),
        dict(DEFAULT_SLOT, key_type="mouse", key_repr="right",
             text=tr("slot.default.release"),
             mode=MODE_COMBO, sfx_key=f"{theme_mod.ZEN}:zen_singing_bowl"),
        dict(DEFAULT_SLOT, key_type="keyboard", key_repr="f",
             text=tr("slot.default.breath"),
             mode=MODE_COMBO, sfx_key=f"{theme_mod.ZEN}:soft_breath_chime"),
    ]


# Styri pevne kategorie hlasky (Tazisko, Celust, Uvolnenie, Dych). Kategoriu
# urcuje POZICIA slotu v profile (`measure.category_for_slot`, obrazok v hre,
# karta v Sprievodcovi), preto sa sloty 0-3 nedaju odstranit - vypina sa ich
# prepinacom. Sloty od indexu 4 su pozostatky "+ Pridat spustac" z 0.1:
# nemaju kategoriu ani obrazok a appka ich sama nespusta.
CUE_CATEGORY_COUNT = 4


def je_kategoria(index):
    """True pre slot, ktory nesie jednu zo styroch pevnych kategorii."""
    try:
        return 0 <= int(index) < CUE_CATEGORY_COUNT
    except (TypeError, ValueError):
        return False


def doplnit_kategorie(slots):
    """Profil kratsi nez styri kategorie doplni o chybajuce na koniec.

    Nic sa nemaze ani neprepisuje - co v profile je, ostava na svojom mieste.
    Prazdny profil dostane styri zapnute kategorie (ako novy profil). Profilu,
    ktory uz nieco ma (napr. rucne zalozeny v 0.1 s jednym slotom), sa
    chybajuce kategorie pridaju VYPNUTE: appka sa v nom nezacne ozyvat inak,
    nez bol hrac zvyknuty, a kategoriu si zapne prepinacom, ked ju chce.
    """
    slots = [normalize_slot(s) for s in (slots or []) if isinstance(s, dict)]
    if not slots:
        return [normalize_slot(s) for s in default_slots()]
    zaklad = default_slots()
    for index in range(len(slots), CUE_CATEGORY_COUNT):
        slots.append(normalize_slot(dict(zaklad[index], enabled=False)))
    return slots


# Predvolene pozicie (stred vizualu, % sirky/vysky obrazovky) pre 4 in-game
# overlay vizualy - jediny zdroj pravdy pre SomaticOverlayManager aj pre
# default_overlay_configs() nizsie.
OVERLAY_DEFAULT_POS = {
    0: (50.0, 88.0),   # Tazisko - dole v strede
    1: (50.0, 12.0),   # Celust - hore v strede
    2: (86.0, 50.0),   # Uvolnenie - vpravo v strede
    3: (50.0, 74.0),   # Dych - dole v strede, jemne nad topankami (slot 0)
}


def default_overlay_configs():
    """4 ZAPNUTE overlay konfiguracie (jedna na kazdy slot).

    Do 19. 9. boli predvolene VYPNUTE - "hrac si ich zapne a doladi". Lenze
    `app._cue_can_fire` bez zapnuteho vizualu hlasku vobec nepusti, takze
    cerstva instalacia nemala ako povedat ani slovo: hrac sparoval hodinky,
    odohral vecer, automat sa natiahol a zakazdym po 90 sekundach ticho
    vypadol. Jediny signal bol jeden riadok v zabalenom denniku.

    Vizual JE ten produkt - nie doplnok, ktory sa dokupuje. Kto ho nechce,
    vypne si ho; predvolba nesmie appku umlcat.
    """
    return [dict(enabled=True, scale=1.0, pos_x=OVERLAY_DEFAULT_POS[i][0],
                 pos_y=OVERLAY_DEFAULT_POS[i][1], color=None) for i in range(4)]


# --------------------------------------------------------------------------
# HUD (zivy panel so statistikou tepu) a vyber monitora
# --------------------------------------------------------------------------

# Na ktorom monitore sa maju kreslit vizualy aj HUD:
#   "auto"    - monitor, na ktorom je aktivne okno (= hra). Predvolba.
#   "cursor"  - monitor pod kurzorom
#   "primary" - hlavny monitor
#   "0".."3"  - konkretny index zo zoznamu display.monitors()
DEFAULT_MONITOR_TARGET = "auto"
MONITOR_TARGET_CHOICES = ("auto", "cursor", "primary")

# Predvolena poloha HUD-u: lavy dolny roh. Je to najmenej kolizne miesto
# naprie strielackami - killfeed byva vpravo hore, minimapa vlavo hore,
# stredy su rezervovane pre zameriavac a hlasky hry.
HUD_DEFAULT_POS = (13.0, 90.0)


def default_hud_config():
    """HUD je pri prvom spusteni VYPNUTY - je to nova vec a hrac si sam
    rozhodne, ci chce mat pocas hrania na obrazovke cislo svojho tepu.

    `show_triggers`/`trigger_color`: riadok 4 zakladnych funkcii pod HUD
    panelom ("Ukazat panel v hre" vo Vizualoch) - nahradza povodny
    celoappkovy "Minimalisticky rezim". Vypnute predvolene, aby sa panel
    nezmenil pre nikoho, kto uz HUD pouziva bez neho."""
    return {"enabled": False, "scale": 1.0, "opacity": 0.92,
            "pos_x": HUD_DEFAULT_POS[0], "pos_y": HUD_DEFAULT_POS[1],
            "show_triggers": False, "trigger_color": None}


def normalize_hud_config(raw):
    cfg = default_hud_config()
    if isinstance(raw, dict):
        cfg["enabled"] = bool(raw.get("enabled", False))
        cfg["scale"] = clamp_float(raw.get("scale"), 0.6, 2.0, 1.0)
        cfg["opacity"] = clamp_float(raw.get("opacity"), 0.25, 1.0, 0.92)
        cfg["pos_x"] = clamp_float(raw.get("pos_x"), 0.0, 100.0, HUD_DEFAULT_POS[0])
        cfg["pos_y"] = clamp_float(raw.get("pos_y"), 0.0, 100.0, HUD_DEFAULT_POS[1])
        cfg["show_triggers"] = bool(raw.get("show_triggers", False))
        cfg["trigger_color"] = _valid_hex(raw.get("trigger_color"))
    return cfg


def normalize_monitor_target(raw):
    value = str(raw or DEFAULT_MONITOR_TARGET)
    if value in MONITOR_TARGET_CHOICES:
        return value
    if value.isdigit() and 0 <= int(value) <= 7:
        return value
    return DEFAULT_MONITOR_TARGET


# POZN: `DEFAULT_DOJO_INTENSITY` a `normalize_dojo_intensity()` tu boli -
# hodnota 0-100 pre posuvnik "Pozadie dojo". Ovladali priehladnost
# fotopasu nad titulkovou listou (ui_shell.DojoBand), ktory bol
# odstraneny, takze uz nemaju co normalizovat. Stary kluc
# "dojo_intensity" moze v dandurf_settings.json zostat - appka ho
# jednoducho ignoruje a pri dalsom ulozeni vypadne.


# --------------------------------------------------------------------------
# Dychovy cyklus (dlzka nadychu/vydychu v sekundach)
# --------------------------------------------------------------------------

DEFAULT_BREATH_INHALE_S = 4.0
DEFAULT_BREATH_EXHALE_S = 6.0
BREATH_SECONDS_MIN, BREATH_SECONDS_MAX = 2.0, 10.0


def normalize_breath_seconds(inhale_raw, exhale_raw):
    inhale = clamp_float(inhale_raw, BREATH_SECONDS_MIN, BREATH_SECONDS_MAX,
                         DEFAULT_BREATH_INHALE_S)
    exhale = clamp_float(exhale_raw, BREATH_SECONDS_MIN, BREATH_SECONDS_MAX,
                         DEFAULT_BREATH_EXHALE_S)
    return inhale, exhale


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Vybratelne statistiky na stranke Dnes (2x2 mriezka nad spustacmi)
# --------------------------------------------------------------------------

# Poradie = poradie vo vybere "✎ upravit". Poslednych pat pribudlo v 0.2
# (widgets-history): dlzka relacie, minuty od poslednej hlasky, cas v pokoji,
# kvalita signalu a citene vs. merane z poslednej ukoncenej relacie. Predvolene
# karty ostavaju tie iste styri - nove si hrac zapne sam.
DASHBOARD_STAT_IDS = ("baseline", "hrr", "over", "breath", "avg", "max", "peak", "week",
                      "session_len", "last_cue", "calm_time", "signal",
                      "felt_vs_measured")
DEFAULT_DASHBOARD_STATS = ["baseline", "hrr", "over", "breath"]


def normalize_dashboard_stats(raw):
    """Zoznam zvolenych metrik na Dnes, v poradi ako ich hrac vybral.
    Neznamy id (napr. po buducom zmazani metriky) sa ticho zahodi;
    prazdny/rozbity vstup padne na predvoleny vyber (rovnaky ako v makete)."""
    if not isinstance(raw, list):
        return list(DEFAULT_DASHBOARD_STATS)
    out = []
    for item in raw:
        if item in DASHBOARD_STAT_IDS and item not in out:
            out.append(item)
    return out or list(DEFAULT_DASHBOARD_STATS)


# Na Dnes sa zmestia najviac 4 karty - mriezka 2x2. Nie je to kozmetika:
# stlpec kariet urcuje vysku celeho riadku Dnes, takze 5. a 6. karta
# natiahli stred (dojo) zhruba o sestinu a panel "Tep a zataz" spadol pod
# okraj okna. Odmerane pri 150 % (revizia B2): 3-4 karty 782 px, 5-6 kariet
# 911 px, 7-8 kariet 1040 px.
#
# Strop je JEDNO cislo a nic nizsie nepredpoklada, kolko metrik je v
# katalogu (DASHBOARD_STAT_IDS moze rast).
DASHBOARD_MAX_CARDS = 4


def toggle_dashboard_stat(stats, stat_id, max_cards=DASHBOARD_MAX_CARDS):
    """Novy vyber po kliknuti na metriku (riadok vo vybere alebo ✕ na karte).

    - Zvolena metrika odide - okrem POSLEDNEJ. Jedna karta ostava vzdy:
      mriezka (Tk grid) sa po poslednej karte nezmrsti a pod nadpisom by
      ostala prazdna diera.
    - Nezvolena pribudne na koniec - ale len kym je kariet menej nez
      `max_cards`.
    Ked sa nic nezmeni, vrati nezmenenu kopiu (vstup nikdy nemeni)."""
    out = list(stats)
    if stat_id in out:
        if len(out) <= 1:
            return out
        return [s for s in out if s != stat_id]
    if len(out) >= max_cards:
        return out
    return out + [stat_id]


def dashboard_stat_clickable(stats, stat_id, max_cards=DASHBOARD_MAX_CARDS):
    """Zmeni klik na tuto metriku nieco? Vyber podla toho kresli riadok:
    co nic neurobi, je bledsie a bez ruky na kurzore."""
    return toggle_dashboard_stat(stats, stat_id, max_cards) != list(stats)


def swap_dashboard_stats(stats, a, b):
    """Karta `a` potiahnuta na kartu `b`: vymenia si miesto, ostatne stoja.
    Ked jedna chyba alebo su to tie iste, vrati nezmenenu kopiu."""
    out = list(stats)
    if a == b or a not in out or b not in out:
        return out
    i, j = out.index(a), out.index(b)
    out[i], out[j] = out[j], out[i]
    return out


DEFAULT_COOLDOWN = 5.0

# Odporucane hodnoty zvuku - JEDNO miesto pre predvolby noveho profilu aj
# pre tlacidlo "Vratit odporucane" na stranke Zvuk. Hlas a motor tu
# zamerne nie su: to je volba (kto ako chce pocuvat), nie hodnota, ktoru
# sa da "pokazit" a treba ju vediet vratit.
DEFAULT_AUDIO = {
    "cooldown": DEFAULT_COOLDOWN,
    "rate": 0,
    "volume": 100,
    "balance": 50,
    "overlap": False,
}

# Kuratovany zoznam hlasov - jazyky rozhrania appky (en/sk/cs/ja) PLUS
# najpopularnejsie jazyky hracov na Steame (Steam Hardware & Software
# Survey, marec 2026 + Valve GDC'25 data): zjednodusena cinstina,
# ruština, spanielcina, portugalcina (Brazilia), nemcina, francuzstina,
# korejcina, poľstina. Kazdy jazyk ma presne 1 zensky + 1 muzsky hlas -
# rovnaka disciplina ako predtym, len sirsie pokrytie jazykov, nie viac
# hlasov na jazyk.
#
# Toto je JEDINY zdroj pravdy pre hlasy - a od 0.2 aj jediny zoznam: appka
# ho uz nestahuje z Microsoftu (predtym pri kazdom starte s Edge, len aby
# zivy katalog orezala presne na tento vyber). Meno "FALLBACK" ostalo z tych
# cias. Kazda polozka je (ShortName, meno na zobrazenie, rod "f"/"m");
# popis v comboboxe sklada `audio_engine.EdgeTTSCache.list_voices` cez tr(),
# takze slovo zena/muz je v jazyku rozhrania. Poradie = poradie zobrazenia
# (Sonia prva, je to predvoleny/"hlavny" hlas).
#
# en-GB-SoniaNeural je PREDVOLENY/HLAVNY hlas appky (DEFAULT_EDGE_VOICE
# nizsie) - vsetky ostatne su alternativy.
EDGE_FALLBACK_VOICES = [
    # --- jazyky rozhrania appky ---
    ("en-GB-SoniaNeural", "Sonia", "f"),
    ("en-GB-RyanNeural", "Ryan", "m"),
    ("en-US-AvaMultilingualNeural", "Ava", "f"),
    ("en-US-GuyNeural", "Guy", "m"),
    ("sk-SK-ViktoriaNeural", "Viktória", "f"),
    ("sk-SK-LukasNeural", "Lukáš", "m"),
    ("cs-CZ-VlastaNeural", "Vlasta", "f"),
    ("cs-CZ-AntoninNeural", "Antonín", "m"),
    ("bg-BG-KalinaNeural", "Kalina", "f"),
    ("bg-BG-BorislavNeural", "Borislav", "m"),
    ("ja-JP-NanamiNeural", "Nanami", "f"),
    ("ja-JP-KeitaNeural", "Keita", "m"),
    # --- najpopulárnejšie jazyky hráčov na Steame (2026) ---
    ("zh-CN-XiaoxiaoNeural", "Xiaoxiao", "f"),
    ("zh-CN-YunxiNeural", "Yunxi", "m"),
    ("ru-RU-SvetlanaNeural", "Svetlana", "f"),
    ("ru-RU-DmitryNeural", "Dmitry", "m"),
    ("es-ES-ElviraNeural", "Elvira", "f"),
    ("es-ES-AlvaroNeural", "Álvaro", "m"),
    ("pt-BR-FranciscaNeural", "Francisca", "f"),
    ("pt-BR-AntonioNeural", "Antônio", "m"),
    ("de-DE-KatjaNeural", "Katja", "f"),
    ("de-DE-ConradNeural", "Conrad", "m"),
    ("fr-FR-DeniseNeural", "Denise", "f"),
    ("fr-FR-HenriNeural", "Henri", "m"),
    ("ko-KR-SunHiNeural", "SunHi", "f"),
    ("ko-KR-InJoonNeural", "InJoon", "m"),
    ("pl-PL-ZofiaNeural", "Zofia", "f"),
    ("pl-PL-MarekNeural", "Marek", "m"),
]
DEFAULT_EDGE_VOICE = "en-GB-SoniaNeural"

# Hlas, ktory appka navrhne k jazyku rozhrania - pri prvom starte (jazyk
# Windowsu) aj pri prepnuti jazyka, ale len kym ma hrac predvoleny hlas.
#
# Len jazyky s inym pismom nez latinka: ich predvolene hlasky slotov
# (`slot.default.*`) su v tom pisme a anglicky hlas Sonia by ich
# pravdepodobne nevyslovil - hlaska by bola skomolena alebo ticha. Cestina
# ma predvolene hlasky anglicke a latinkove jazyky (es/de/fr/pt) Sonia
# aspon precita, tam ostava hlavny hlas appky. Vsetky styri su zenske -
# appka o sebe hovori v zenskom rode.
VOICE_HINTS = {
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "bg": "bg-BG-KalinaNeural",
}


def suggested_voice(lang, current=DEFAULT_EDGE_VOICE):
    """Navrhovany Edge hlas pre jazyk `lang`.

    Meni len predvoleny hlas (`DEFAULT_EDGE_VOICE`) - hlas, ktory si hrac
    vybral sam, ostava, ako je. Jazyk bez navrhu necha hlas tak.
    """
    if current == DEFAULT_EDGE_VOICE and lang in VOICE_HINTS:
        return VOICE_HINTS[lang]
    return current

# Hlasy, ktore znejú vyrazne prirodzenejsie - v popisku dostanu
# "najprirodzenejsi" (voice.most_natural).
EDGE_PREMIUM_HINT = ("Multilingual",)


# --------------------------------------------------------------------------
# Male pomocky na cistenie hodnot z JSON
# --------------------------------------------------------------------------

def clamp_float(value, low, high, default):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out:                      # NaN
        return default
    return max(low, min(high, out))


def clamp_int(value, low, high, default):
    try:
        out = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, out))


def optional_cooldown(value):
    if value is None or value == "":
        return None
    return clamp_float(value, 0.0, 600.0, None)


# Stare PREDVOLENE hlasove slova, ktore sa v 0.2 zmenili (kluc = text
# porovnany bez ohladu na velkost pismen a okrajove medzery). Meni sa len
# PRESNA zhoda - vlastne slovo hraca (aj "my teeth") ostava, ako ho napisal.
#   "Teeth" -> "Jaw": mimo hry znelo cudne (rozhodnutie zadavatela).
#   ja 脱力 a zh 放松 znamenaju "uvolni sa" - hlaska nikdy nehovori
#   "uvolni sa / upokoj sa" (tests/test_cue_words.py), ani zo stareho profilu.
#   Tieto dve sa menia LEN v slote, kde boli predvolene (1 = celust,
#   2 = uvolnenie ruky): 脱力 je v ja aj nazov kategorie "Release" v
#   Historii, takze ho hrac mohol do slotu 2 napisat sam - tam by 顎
#   ("celust") bolo zle slovo.
# Vola sa pri NACITANI nastaveni (`app.load_settings`), nie v `normalize_slot`:
# ta bezi aj pri kazdej prestavbe karty slotu a slovo by sa hracovi menilo
# pod rukami uprostred upravy.
_STARE_PREDVOLENE_SLOVA = {
    # text: (slot, v ktorom bol predvoleny - None = hociktory; nove slovo)
    "teeth": (None, "Jaw"),
    "脱力": (1, "顎"),
    "放松": (2, "松开"),
}


def migrate_slot_text(text, index=None):
    """Stare predvolene slovo -> nove; cokolvek ine vrati nezmenene.
    `index` = poradie slotu v profile (0 grounding, 1 jaw, 2 release,
    3 breath)."""
    if not isinstance(text, str):
        return text
    zaznam = _STARE_PREDVOLENE_SLOVA.get(text.strip().casefold())
    if zaznam is None:
        return text
    slot, nove = zaznam
    if slot is not None and slot != index:
        return text
    return nove


def normalize_slot(raw):
    """Doplni chybajuce kluce a osetri rozsahy - aj pre stare nastavenia."""
    slot = dict(DEFAULT_SLOT)
    if isinstance(raw, dict):
        slot.update({k: v for k, v in raw.items() if k in DEFAULT_SLOT})
    slot["key_type"] = "mouse" if slot.get("key_type") == "mouse" else "keyboard"
    mode = slot.get("mode")
    if mode == "audio":
        mode = MODE_SFX  # migracia zo starej schemy (Dandurf 2.0)
    slot["mode"] = mode if mode in MODE_ORDER else MODE_TTS
    slot["enabled"] = bool(slot.get("enabled", True))
    slot["key_repr"] = str(slot.get("key_repr") or "")
    slot["text"] = str(slot.get("text") or "")
    slot["audio_path"] = str(slot.get("audio_path") or "")
    slot["sfx_key"] = str(slot.get("sfx_key") or "")
    slot["voice_edge"] = str(slot.get("voice_edge") or "")
    slot["voice_sapi"] = str(slot.get("voice_sapi") or "")
    slot["voice_path"] = str(slot.get("voice_path") or "")
    # Stabilny uid: doplni sa raz a odvtedy zije v profile. Meno nahravky sa
    # z neho odvodzuje, takze dva profily s "rovnakym" slotom si neprepisu
    # subory navzajom (to bola strata dat - B1).
    slot["uid"] = str(slot.get("uid") or "") or uuid.uuid4().hex[:12]
    slot["cooldown"] = optional_cooldown(slot.get("cooldown"))
    slot["delay"] = clamp_float(slot.get("delay"), 0.0, 30.0, 0.0)
    slot["every_n"] = clamp_int(slot.get("every_n"), 1, 99, 1)
    slot["repeat"] = clamp_int(slot.get("repeat"), 1, 10, 1)
    slot["repeat_gap"] = clamp_float(slot.get("repeat_gap"), 0.05, 30.0, 0.5)
    slot["jitter"] = clamp_float(slot.get("jitter"), 0.0, 0.9, 0.0)
    return slot


# Co z hlasky ide do kodu profilu (Spustace -> Exportovat profil). Kod sa
# zdiela s inymi ludmi, takze v nom je len to, co ma pre druheho zmysel, a
# nic, co by prezradilo tento pocitac:
#   * `audio_path` a `voice_path` su ABSOLUTNE cesty k nahravkam
#     (C:\Users\<meno>\AppData\...) - kod by prezradil meno uctu vo Windows
#     a nahravka sa kodom aj tak neprenesie,
#   * `uid` je lokalny identifikator suborov nahravok (import dostane novy),
#   * `key_type`, `key_repr`, `cooldown`, `delay`, `every_n`, `repeat`,
#     `repeat_gap`, `jitter` su mrtve polia z cias klavesovych spustacov -
#     nic ich necita.
ZDIELANE_POLIA_SLOTU = ("text", "mode", "sfx_key", "enabled", "voice_edge",
                        "voice_sapi")


def slot_na_zdielanie(slot):
    """Hlaska pre kod profilu - len `ZDIELANE_POLIA_SLOTU`. Vlastny zvuk
    (`sfx_key` "__custom__") je subor na tomto PC, takze v kode padne na
    automaticky vyber."""
    if not isinstance(slot, dict):
        return {}
    out = {k: slot[k] for k in ZDIELANE_POLIA_SLOTU if k in slot}
    if out.get("sfx_key") == "__custom__":
        out["sfx_key"] = ""
    return out


def slot_zo_zdielania(raw):
    """Hlaska z cudzieho kodu profilu, alebo None.

    Berie sa len `ZDIELANE_POLIA_SLOTU` - aj zo starsich kodov, ktore este
    niesli cesty a uid. Cesty k suborom su preto VZDY prazdne (cudzia cesta
    by sa prehrala, keby na tomto PC nahodou existovala) a `normalize_slot`
    doplni cerstve uid, aby importovany profil nezdielal subory nahravok s
    inym (rec_<uid>.wav - strata dat B1)."""
    if not isinstance(raw, dict):
        return None
    slot = slot_na_zdielanie(raw)
    slot["audio_path"] = ""
    slot["voice_path"] = ""
    slot["uid"] = ""
    return normalize_slot(slot)


def normalize_overlay_config(raw, index):
    """Doplni chybajuce kluce a osetri rozsahy pre 1 polozku overlay_configs."""
    default_pos = OVERLAY_DEFAULT_POS.get(index, (50.0, 50.0))
    # `enabled` chyba -> ZAPNUTE. Chybajuci kluc znamena "stary alebo
    # neuplny zapis", nie "hrac si to vypol"; vypnute vizualy appku umlcia.
    cfg = {"enabled": True, "scale": 1.0,
           "pos_x": default_pos[0], "pos_y": default_pos[1], "color": None}
    if isinstance(raw, dict):
        cfg["enabled"] = bool(raw.get("enabled", True))
        cfg["scale"] = clamp_float(raw.get("scale"), 0.5, 2.0, 1.0)
        cfg["pos_x"] = clamp_float(raw.get("pos_x"), 0.0, 100.0, default_pos[0])
        cfg["pos_y"] = clamp_float(raw.get("pos_y"), 0.0, 100.0, default_pos[1])
        # farba piktogramu: None = pouzi akcent temy; inak overeny #rrggbb
        cfg["color"] = _valid_hex(raw.get("color"))
    return cfg


def _valid_hex(value):
    """Vrati '#rrggbb' ak je platny, inak None (= pouzi farbu temy)."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if len(v) == 7 and v[0] == "#":
        try:
            int(v[1:], 16)
            return v.lower()
        except ValueError:
            return None
    return None


def pack_label(pack):
    return tr("pack.zen") if pack == theme_mod.ZEN else tr("pack.modern")


def sfx_choice_display(sfx_key, audio_path):
    """Text zobrazeny v dropdowne SFX presetu pre dany stav slotu."""
    if sfx_key == "__custom__":
        name = os.path.basename(audio_path) if audio_path else "-"
        return tr("sfx.custom_prefix", name=name)
    if sfx_key and ":" in sfx_key:
        pack, key = sfx_key.split(":", 1)
        return f"{pack_label(pack)}: {sfx_assets.sound_label(pack, key)}"
    return tr("sfx.auto")


def sfx_dropdown_options():
    """[(display, value)] pre vsetky volby SFX presetu naprie oboma sadami."""
    options = [(tr("sfx.auto"), "")]
    for pack in (theme_mod.ZEN, theme_mod.MODERN):
        for key, label in sfx_assets.library_items(pack):
            options.append((f"{pack_label(pack)}: {label}", f"{pack}:{key}"))
    return options
