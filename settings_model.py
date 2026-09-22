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

DASHBOARD_STAT_IDS = ("baseline", "hrr", "over", "breath", "avg", "max", "peak", "week")
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
# Toto je JEDINY zdroj pravdy pre hlasy: sluzi zaroven ako
#   1) zaloha, ked sa nepodari stiahnut zoznam (bez internetu),
#   2) filter na ziveho stiahnuty katalog (inak by tam bolo pre kazdy
#      jazyk 20-30 hlasov - presne to, co appka nepotrebuje),
#   3) poradie zobrazenia (Sonia prva, je to predvoleny/"hlavny" hlas).
#
# en-GB-SoniaNeural je PREDVOLENY/HLAVNY hlas appky (DEFAULT_EDGE_VOICE
# nizsie) - vsetky ostatne su alternativy.
EDGE_FALLBACK_VOICES = [
    # --- jazyky rozhrania appky ---
    ("en-GB-SoniaNeural", "en-GB · Sonia (žena, hlavný hlas appky)"),
    ("en-GB-RyanNeural", "en-GB · Ryan (muž)"),
    ("en-US-AvaMultilingualNeural", "en-US · Ava (žena, najprirodzenejšia)"),
    ("en-US-GuyNeural", "en-US · Guy (muž)"),
    ("sk-SK-ViktoriaNeural", "sk-SK · Viktória (žena)"),
    ("sk-SK-LukasNeural", "sk-SK · Lukáš (muž)"),
    ("cs-CZ-VlastaNeural", "cs-CZ · Vlasta (žena)"),
    ("cs-CZ-AntoninNeural", "cs-CZ · Antonín (muž)"),
    ("ja-JP-NanamiNeural", "ja-JP · Nanami (žena, prirodzená)"),
    ("ja-JP-KeitaNeural", "ja-JP · Keita (muž)"),
    # --- najpopulárnejšie jazyky hráčov na Steame (2026) ---
    ("zh-CN-XiaoxiaoNeural", "zh-CN · Xiaoxiao (žena)"),
    ("zh-CN-YunxiNeural", "zh-CN · Yunxi (muž)"),
    ("ru-RU-SvetlanaNeural", "ru-RU · Svetlana (žena)"),
    ("ru-RU-DmitryNeural", "ru-RU · Dmitry (muž)"),
    ("es-ES-ElviraNeural", "es-ES · Elvira (žena)"),
    ("es-ES-AlvaroNeural", "es-ES · Álvaro (muž)"),
    ("pt-BR-FranciscaNeural", "pt-BR · Francisca (žena)"),
    ("pt-BR-AntonioNeural", "pt-BR · Antônio (muž)"),
    ("de-DE-KatjaNeural", "de-DE · Katja (žena)"),
    ("de-DE-ConradNeural", "de-DE · Conrad (muž)"),
    ("fr-FR-DeniseNeural", "fr-FR · Denise (žena)"),
    ("fr-FR-HenriNeural", "fr-FR · Henri (muž)"),
    ("ko-KR-SunHiNeural", "ko-KR · SunHi (žena)"),
    ("ko-KR-InJoonNeural", "ko-KR · InJoon (muž)"),
    ("pl-PL-ZofiaNeural", "pl-PL · Zofia (žena)"),
    ("pl-PL-MarekNeural", "pl-PL · Marek (muž)"),
]
DEFAULT_EDGE_VOICE = "en-GB-SoniaNeural"

# Ked je rozhranie prepnute na japoncinu, hodi sa aj prirodzeny japonsky
# hlas ako navrhovana volba (Nanami je jeden z najprirodzenejsich Edge
# hlasov pre ja-JP).
JAPANESE_VOICE_HINT = "ja-JP-NanamiNeural"

# Hlasy, ktore znejú vyrazne prirodzenejsie - vytiahneme ich navrch a
# v popisku im odstranime "Multilingual" z nazvu (napr. "Ava" mesto
# "AvaMultilingual").
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
