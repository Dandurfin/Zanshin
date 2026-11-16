"""Data model of the slots and global settings - default values,
normalisation of loaded/imported data, labels for the UI dropdowns.

Pure functions/constants without UI and without I/O (apart from tr()
translations) - used by both app.py and ui_dialogs.py, so that both sides
work with the same shape of data and the same value ranges.
"""

import os
import uuid

import theme as theme_mod
import sfx_assets
from i18n import LANGUAGES, tr, tr_lang

# --------------------------------------------------------------------------
# Slot modes (voice / SFX / combination) and TTS engines
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

# Template of one slot - also the list of allowed keys in the settings.
DEFAULT_SLOT = {
    "key_type": "keyboard",   # keyboard | mouse
    "key_repr": "",
    "text": "",
    "mode": MODE_TTS,         # tts | sfx | combo
    "audio_path": "",         # own/recorded file for the SFX layer
    "sfx_key": "",            # "" auto | "pack:key" preset | "__custom__"
    "enabled": True,
    "voice_edge": "",         # "" = use the global voice
    "voice_sapi": "",
    "voice_path": "",         # own recording of the VOICE - if set, it plays
                              # instead of TTS (see app._speak_text). Separate
                              # from audio_path (that is the SFX layer).
    "uid": "",                # stable slot identifier - it is used for
                              # recording names, so they do not clash across
                              # profiles (normalize_slot adds it if missing).
    "cooldown": None,         # None = use the global cooldown
    "delay": 0.0,             # delay before playback (s)
    "every_n": 1,             # fires on every N-th press
    "repeat": 1,              # how many times to repeat
    "repeat_gap": 0.5,        # pause between repeats (s)
    "jitter": 0.0,            # random spread of the cooldown (0.0 - 0.9)
}


def default_slots():
    """4 basic default slots for new installations - always Combination
    (Voice+SFX), the Zen SFX pack, clean basic timing (no delay, no
    jitter, every 1st press - DEFAULT_SLOT default). The cue text follows
    the current UI language (see i18n slot.default.*).

    Whether a slot is enabled after onboarding is decided only by
    DandurfApp._apply_diagnostics() according to the checklist in step
    2 - here all 4 are prepared with enabled=True (DEFAULT_SLOT default)
    and onboarding may turn some of them off."""
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


# Four fixed cue categories (Grounding, Jaw, Release, Breath). The
# category is set by the slot's POSITION in the profile
# (`measure.category_for_slot`, the in-game picture, the card in the
# Guide), which is why slots 0-3 cannot be removed - they are turned off
# with the toggle. Slots from index 4 on are leftovers of "+ Add trigger"
# from 0.1: they have no category or picture, and the app does not fire
# them by itself.
CUE_CATEGORY_COUNT = 4


def je_kategoria(index):
    """True for a slot that carries one of the four fixed categories."""
    try:
        return 0 <= int(index) < CUE_CATEGORY_COUNT
    except (TypeError, ValueError):
        return False


def doplnit_kategorie(slots):
    """Appends the missing categories to a profile with fewer than four.

    Nothing is deleted or overwritten - whatever is in the profile stays
    in its place. An empty profile gets four enabled categories (like a
    new profile). A profile that already has something (e.g. created by
    hand in 0.1 with one slot) gets the missing categories added
    DISABLED: the app will not start speaking up in it differently from
    what the player was used to, and they turn a category on with the
    toggle when they want it.
    """
    slots = [normalize_slot(s) for s in (slots or []) if isinstance(s, dict)]
    if not slots:
        return [normalize_slot(s) for s in default_slots()]
    zaklad = default_slots()
    for index in range(len(slots), CUE_CATEGORY_COUNT):
        slots.append(normalize_slot(dict(zaklad[index], enabled=False)))
    return slots


# Default positions (centre of the visual, % of screen width/height) for
# the 4 in-game overlay visuals - the single source of truth for both
# SomaticOverlayManager and default_overlay_configs() below.
OVERLAY_DEFAULT_POS = {
    0: (14.0, 50.0),   # Grounding - left, middle (mirrors Release)
    1: (50.0, 12.0),   # Jaw - top centre
    2: (86.0, 50.0),   # Release - right, middle
    3: (50.0, 74.0),   # Breath - bottom centre
}

# Grounding's default position up to 0.3 (bottom centre, under the breath
# ring). Since every cue comes with the exhale ring (overlay.py), grounding
# would sit right under it, so it moved to the left middle. A config that
# still holds exactly this position was never dragged and is moved once on
# load (`move_old_grounding_position`).
OVERLAY_OLD_GROUNDING_POS = (50.0, 88.0)


def move_old_grounding_position(cfgs):
    """Moves an untouched grounding visual (slot 0) from the old default
    to the new one. Returns True if it moved it.

    Only the EXACT old default counts - a position the player dragged
    stays where they put it. Only position changes; enabled, size and
    colour stay. `cfgs` is the normalised overlay_configs list (changed in
    place). It is called once per settings file: `load_settings` asks only
    while the file has no `grounding_moved` flag, and `save_settings`
    writes it."""
    try:
        cfg = cfgs[0]
        if (float(cfg["pos_x"]), float(cfg["pos_y"])) != OVERLAY_OLD_GROUNDING_POS:
            return False
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    cfg["pos_x"], cfg["pos_y"] = OVERLAY_DEFAULT_POS[0]
    return True


def default_overlay_configs():
    """4 ENABLED overlay configurations (one for each slot).

    Until 19. 9. they were DISABLED by default - "the player will turn
    them on and fine-tune them". But `app._cue_can_fire` does not let a
    cue through at all without an enabled visual, so a fresh installation
    had no way to say a single word: the player paired the watch, played
    an evening, the state machine armed and every time, after 90 seconds,
    silently dropped out. The only signal was one line in the collapsed
    journal.

    The visual IS the product - not an add-on you buy extra. Whoever does
    not want it turns it off; the default must not silence the app.
    """
    return [dict(enabled=True, scale=1.0, pos_x=OVERLAY_DEFAULT_POS[i][0],
                 pos_y=OVERLAY_DEFAULT_POS[i][1], color=None) for i in range(4)]


# --------------------------------------------------------------------------
# HUD (live panel with heart-rate statistics) and monitor selection
# --------------------------------------------------------------------------

# Which monitor the visuals and the HUD should be drawn on:
#   "auto"    - the monitor with the active window (= the game). Default.
#   "cursor"  - the monitor under the cursor
#   "primary" - the main monitor
#   "0".."3"  - a specific index from the display.monitors() list
DEFAULT_MONITOR_TARGET = "auto"
MONITOR_TARGET_CHOICES = ("auto", "cursor", "primary")

# Default HUD position: the bottom left corner. It is the least clashing
# spot across shooters - the killfeed is usually top right, the minimap
# top left, the centres are reserved for the crosshair and the game's
# messages.
HUD_DEFAULT_POS = (13.0, 90.0)


def default_hud_config():
    """The HUD is OFF on the first start - it is a new thing and the player
    decides for themselves whether they want the number of their heart
    rate on screen while playing.

    `show_triggers`/`trigger_color`: a row of the 4 basic features under
    the HUD panel ("Show the panel in game" in Visuals) - replaces the
    original app-wide "Minimalist mode". Off by default, so the panel
    does not change for anyone who already uses the HUD without it."""
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


# NOTE: `DEFAULT_DOJO_INTENSITY` and `normalize_dojo_intensity()` were
# here - a 0-100 value for the "Dojo background" slider. They controlled
# the transparency of the photo band above the title bar
# (ui_shell.DojoBand), which was removed, so they have nothing left to
# normalise. The old key "dojo_intensity" may stay in
# dandurf_settings.json - the app simply ignores it, and it drops out on
# the next save.


# --------------------------------------------------------------------------
# Breathing cycle (inhale/exhale length in seconds)
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
# The ring at high heart rate (experiment, off by default)
# --------------------------------------------------------------------------

# While the smoothed heart rate (`HeartStats.display_bpm`) is ABOVE this
# limit, the breath ring breathes in a loop (`app_session._tick_high_hr_ring`).
# Whole BPM, set in In-game pictures on the Breath card.
DEFAULT_HIGH_HR_RING_BPM = 110
HIGH_HR_RING_BPM_MIN, HIGH_HR_RING_BPM_MAX = 80, 200


def normalize_high_hr_ring_bpm(raw):
    """The limit as a whole number in 80..200; anything that is not a
    number (text, None, true/false, NaN, infinity) -> the default 110."""
    if isinstance(raw, bool):
        return DEFAULT_HIGH_HR_RING_BPM
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_HIGH_HR_RING_BPM
    if value != value or value in (float("inf"), float("-inf")):
        return DEFAULT_HIGH_HR_RING_BPM
    return max(HIGH_HR_RING_BPM_MIN, min(HIGH_HR_RING_BPM_MAX, int(round(value))))


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Selectable statistics on the Today page (2x2 grid above the triggers)
# --------------------------------------------------------------------------

# Order = the order in the "✎ edit" picker. The last five were added in
# 0.2 (widgets-history): session length, minutes since the last cue, time
# at rest, signal quality and felt vs. measured from the last finished
# session. The default cards stay the same four - the player turns the
# new ones on themselves.
DASHBOARD_STAT_IDS = ("baseline", "hrr", "over", "breath", "avg", "max", "peak", "week",
                      "session_len", "last_cue", "calm_time", "signal",
                      "felt_vs_measured")
DEFAULT_DASHBOARD_STATS = ["baseline", "hrr", "over", "breath"]


def normalize_dashboard_stats(raw):
    """List of the chosen metrics on Today, in the order the player chose
    them. An unknown id (e.g. after a metric is deleted in the future) is
    silently dropped; empty/broken input falls back to the default
    selection (the same as in the mock-up)."""
    if not isinstance(raw, list):
        return list(DEFAULT_DASHBOARD_STATS)
    out = []
    for item in raw:
        if item in DASHBOARD_STAT_IDS and item not in out:
            out.append(item)
    return out or list(DEFAULT_DASHBOARD_STATS)


# At most 4 cards fit on Today - a 2x2 grid. This is not cosmetics: the
# card column sets the height of the whole Today row, so a 5th and 6th
# card stretched the centre (dojo) by roughly a sixth and the "Heart
# rate and load" panel fell below the edge of the window. Measured at
# 150 % (review B2): 3-4 cards 782 px, 5-6 cards 911 px, 7-8 cards
# 1040 px.
#
# The cap is ONE number and nothing below assumes how many metrics are
# in the catalogue (DASHBOARD_STAT_IDS may grow).
DASHBOARD_MAX_CARDS = 4


def toggle_dashboard_stat(stats, stat_id, max_cards=DASHBOARD_MAX_CARDS):
    """New selection after clicking a metric (picker row or ✕ on a card).

    - A chosen metric goes away - except the LAST one. One card always
      stays: the grid (Tk grid) does not shrink after the last card and
      an empty hole would be left under the heading.
    - An unchosen one is added at the end - but only while there are
      fewer cards than `max_cards`.
    When nothing changes, it returns an unchanged copy (it never changes
    the input)."""
    out = list(stats)
    if stat_id in out:
        if len(out) <= 1:
            return out
        return [s for s in out if s != stat_id]
    if len(out) >= max_cards:
        return out
    return out + [stat_id]


def dashboard_stat_clickable(stats, stat_id, max_cards=DASHBOARD_MAX_CARDS):
    """Would a click on this metric change anything? The picker draws the
    row accordingly: what does nothing is paler and has no hand cursor."""
    return toggle_dashboard_stat(stats, stat_id, max_cards) != list(stats)


def swap_dashboard_stats(stats, a, b):
    """Card `a` dragged onto card `b`: they swap places, the others stay put.
    When one is missing or they are the same, returns an unchanged copy."""
    out = list(stats)
    if a == b or a not in out or b not in out:
        return out
    i, j = out.index(a), out.index(b)
    out[i], out[j] = out[j], out[i]
    return out


DEFAULT_COOLDOWN = 5.0

# Recommended sound values - ONE place for both the defaults of a new
# profile and the "Restore recommended" button on the Sound page. The
# voice and the engine are deliberately not here: that is a choice (who
# wants to listen how), not a value that can be "broken" and needs to
# be restorable.
DEFAULT_AUDIO = {
    "cooldown": DEFAULT_COOLDOWN,
    "rate": 0,
    "volume": 100,
    "balance": 50,
    "overlap": False,
}

# Curated list of voices - the app's UI languages (en/sk/cs/ja) PLUS the
# most popular languages of players on Steam (Steam Hardware & Software
# Survey, March 2026 + Valve GDC'25 data): Simplified Chinese, Russian,
# Spanish, Portuguese (Brazil), German, French, Korean, Polish. Each
# language has exactly 1 female + 1 male voice - the same discipline as
# before, just wider language coverage, not more voices per language.
#
# This is the ONLY source of truth for voices - and since 0.2 also the
# only list: the app no longer downloads it from Microsoft (before, on
# every start with Edge, only to trim the live catalogue down to exactly
# this selection). The name "FALLBACK" is left over from those days. Each
# entry is (ShortName, display name, gender "f"/"m"); the combobox
# description is assembled by `audio_engine.EdgeTTSCache.list_voices`
# via tr(), so the word woman/man is in the UI language. Order = display
# order (Sonia first, she is the default/"main" voice).
#
# en-GB-SoniaNeural is the app's DEFAULT/MAIN voice (DEFAULT_EDGE_VOICE
# below) - all the others are alternatives.
EDGE_FALLBACK_VOICES = [
    # --- the app's UI languages ---
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
    # --- most popular languages of players on Steam (2026) ---
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

# The voice the app suggests for the language of the CUES - only while
# the player has the default voice: on the first start (Windows
# language, the cues are in it), on a new profile (its words are in the
# app language) and on a language switch only when the active profile's
# cues really are in the new language (`jazyky_hlasok`,
# `app_prefs._hlas_k_hlaskam`). Switching the language by itself does not
# translate profile texts - a Japanese voice would otherwise read the
# English "Exhale, grounded".
#
# Exactly the languages whose built-in words (`slot.default.*`) are NOT
# English. At first only those with a script other than Latin
# (ja/zh/ru/bg) - Sonia would not pronounce them at all. Since 0.3 also
# es/de/fr/pt: their words are in Spanish, German, French and Portuguese
# ("Geerdet", "Kiefer"...) and British Sonia reads them with an English
# pronunciation - so the first evening sounded foreign. The same rule
# from 0.2.1d applies (the voice follows the words, not the menu): the
# voice changes only when the speaking cues really are the built-in words
# of that language, so a language switch with English words leaves the
# voice alone. Sk/cs/en have no suggestion - their built-in words are
# English. All voices are from `EDGE_FALLBACK_VOICES` and female - the
# app refers to itself in the feminine gender.
VOICE_HINTS = {
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "bg": "bg-BG-KalinaNeural",
    "es": "es-ES-ElviraNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "pt": "pt-BR-FranciscaNeural",
}


def suggested_voice(lang, current=DEFAULT_EDGE_VOICE):
    """Suggested Edge voice for the language `lang`.

    It only changes the default voice (`DEFAULT_EDGE_VOICE`) - a voice
    the player chose themselves stays as it is. A language without a
    suggestion leaves the voice alone.
    """
    if current == DEFAULT_EDGE_VOICE and lang in VOICE_HINTS:
        return VOICE_HINTS[lang]
    return current


# Keys of the built-in words of the four categories in slot order (0
# grounding, 1 jaw, 2 release, 3 breath) - the same order as
# `default_slots`.
_KLUCE_PREDVOLENYCH_SLOV = ("slot.default.grounding", "slot.default.jaw",
                            "slot.default.release", "slot.default.breath")


def jazyky_hlasok(slots):
    """Languages in which the cues read by the shared Edge voice are written.

    This is needed for VOICE_HINTS: the UI language says nothing about
    the language of the cues - a language switch does not translate
    profile texts (for sk/cs they are English). `slots` are the profile's
    slot dicts (position = category).

    Only cues that this voice really reads count: one of the four
    categories, enabled, in voice/combination mode, with a text and
    without the slot's own voice (`voice_edge` - that one does not use
    the shared voice).

    The language is NOT GUESSED from the text: it returns the set of
    languages whose built-in words (`slot.default.*`) at the same
    positions match ALL such texts. The old built-in words of the same
    slot count too (`_STARE_PREDVOLENE_SLOVA` - the settings file and a
    profile code from before 0.3.1 are migrated, but a player may type
    an old word back, and a code from 0.3.1 keeps it). A set, because
    sk/en/cs share the English words (the old words also
    ja/zh 呼吸, es/pt Mandíbula and Respira, ru/bg Опора). The player's
    own word (even just one), mixed languages or no speaking cue -> an
    empty set and the app leaves the voice alone - better nothing than
    guessing.
    """
    texty = []
    for index, slot in enumerate(slots or []):
        if not je_kategoria(index) or not isinstance(slot, dict):
            continue
        text = str(slot.get("text") or "").strip()
        if (text and slot.get("enabled", True)
                and slot.get("mode", MODE_TTS) in (MODE_TTS, MODE_COMBO)
                and not slot.get("voice_edge")):
            texty.append((index, text.casefold()))
    if not texty:
        return set()
    return {jazyk for jazyk in LANGUAGES
            if all(text == tr_lang(jazyk, _KLUCE_PREDVOLENYCH_SLOV[index]).strip().casefold()
                   or text in _stare_slova_slotu(jazyk, index)
                   for index, text in texty)}

# Voices that sound markedly more natural - in the label they get
# "most natural" (voice.most_natural).
EDGE_PREMIUM_HINT = ("Multilingual",)


# --------------------------------------------------------------------------
# Small helpers for cleaning values from JSON
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


# Old DEFAULT voice words of the four categories - everything a new
# profile got up to 0.3, per language and slot (0 grounding, 1 jaw,
# 2 release, 3 breath). After 0.3 every cue starts with the exhale
# (`slot.default.*`, e.g. "Exhale, jaw"), so a slot that still holds an
# old default word of ITS OWN slot gets the new word of the same language
# when the settings are loaded. Only an EXACT match counts (letter case
# and surrounding spaces aside) - the player's own word (even "my teeth",
# or a default word typed into another slot) stays as they wrote it.
#   0.2-0.3: the first word of each slot (cs and bg came in 0.2).
#   0.1: "Teeth" (sk/en) - 0.2 changed it to "Jaw", outside the game it
#   sounded odd (the author's decision); ja 脱力 (jaw) and zh 放松
#   (release) - both mean "relax", and a cue never says "relax / calm
#   down" (tests/test_cue_words.py), not even from an old profile.
# Some words were the default in several languages: sk/en/cs (the same
# English words - their new words are the same too), ja/zh 呼吸, es/pt
# Mandíbula and Respira, ru/bg Опора. There the new words differ, so
# `migrate_profile_texts` reads the language from the rest of the
# profile.
# It is called when the settings are LOADED (`app.load_settings`), not
# in `normalize_slot`: that one also runs on every rebuild of the slot
# card, and the word would change under the player's hands in the middle
# of editing. And only ONCE per settings file (the `exhale_words` flag,
# written by `save_settings`): a player who types an old word back
# later ("Jaw") keeps it. The same change runs when a profile code from
# before 0.3.1 is imported (`app.import_profile_from_code`); a code from
# 0.3.1 on carries the same `exhale_words` marker and keeps its words.
_STARE_PREDVOLENE_SLOVA = {
    # language: (grounding, jaw, release, breath) - old words of each slot
    "sk": (("Grounded",), ("Jaw", "Teeth"), ("Release",), ("Breathe",)),
    "en": (("Grounded",), ("Jaw", "Teeth"), ("Release",), ("Breathe",)),
    "cs": (("Grounded",), ("Jaw",), ("Release",), ("Breathe",)),
    "ja": (("重心",), ("顎", "脱力"), ("解放",), ("呼吸",)),
    "zh": (("落地",), ("牙关",), ("松开", "放松"), ("呼吸",)),
    "ru": (("Опора",), ("Челюсть",), ("Отпусти",), ("Дыши",)),
    "es": (("Con los pies en la tierra",), ("Mandíbula",), ("Suelta",), ("Respira",)),
    "de": (("Geerdet",), ("Kiefer",), ("Loslassen",), ("Atme",)),
    "fr": (("Ancré",), ("Mâchoire",), ("Relâche",), ("Respire",)),
    "pt": (("Aterrado",), ("Mandíbula",), ("Solta",), ("Respira",)),
    "bg": (("Опора",), ("Челюст",), ("Разхлаби",), ("Дишай",)),
}

# 0.2 changed "Teeth" to "Jaw" in ANY slot, not only in the jaw slot. In
# the jaw slot it now goes straight to the new word like every old
# default; in another slot it still becomes "Jaw", exactly what 0.2-0.3
# made of it - so a profile ends up the same whether it went through
# 0.2-0.3 first or not ("Jaw" outside the jaw slot is the player's word).
_STARE_ZUBY = "teeth"


def _stare_slova_slotu(jazyk, index):
    """The old default words of slot `index` in `jazyk` (casefolded)."""
    slova = _STARE_PREDVOLENE_SLOVA.get(jazyk)
    if not slova or not je_kategoria(index):
        return set()
    return {slovo.casefold() for slovo in slova[int(index)]}


def _jazyky_stareho_slova(text, index):
    """Languages in which `text` was an old default word of slot `index`,
    in `LANGUAGES` order (empty = not an old default word of that slot)."""
    if not isinstance(text, str):
        return []
    text = text.strip().casefold()
    return [jazyk for jazyk in LANGUAGES if text in _stare_slova_slotu(jazyk, index)]


def migrate_slot_text(text, index=None, jazyky=()):
    """Old default word -> the new one; anything else is returned unchanged.

    `index` = the slot's position in the profile (0 grounding, 1 jaw,
    2 release, 3 breath). The new word is in the language in which the
    text was the old default of that slot. When that is several languages
    with different new words (ja/zh 呼吸, es/pt Mandíbula and Respira,
    ru/bg Опора), the first of them in `jazyky` wins (the most likely
    first - `migrate_profile_texts` works it out from the whole profile),
    otherwise the first in `LANGUAGES`."""
    if not isinstance(text, str):
        return text
    kandidati = _jazyky_stareho_slova(text, index)
    if kandidati:
        jazyk = next((j for j in jazyky if j in kandidati), kandidati[0])
        return tr_lang(jazyk, _KLUCE_PREDVOLENYCH_SLOV[int(index)])
    if text.strip().casefold() == _STARE_ZUBY:
        return "Jaw"
    return text


def jazyk_hlasu(voice):
    """Language of an Edge voice ("ja-JP-NanamiNeural" -> "ja"); None for a
    voice in a language the app does not have."""
    jazyk = str(voice or "").split("-", 1)[0].lower()
    return jazyk if jazyk in LANGUAGES else None


def migrate_profile_texts(slots, jazyky=()):
    """`migrate_slot_text` for every slot of one profile - `slots` (slot
    dicts, position = category) are changed in place and returned.

    A word that was the default in several languages gets the language
    that most of the profile's old default words share: a Portuguese
    profile has "Aterrado" and "Solta" next to "Mandíbula" and "Respira",
    so those two become Portuguese, not Spanish. A tie (the player has
    replaced the telling words) is decided by `jazyky` - the language of
    the voice and the app language, the most likely first - and then by
    `LANGUAGES` order.

    A slot with its OWN Edge voice (`voice_edge`) is read by that voice,
    not the shared one - so for that slot the voice's language comes
    before everything else: 呼吸 read by a Chinese voice was Chinese to the
    player, and the Japanese new word would come out garbled in it."""
    slots = slots if isinstance(slots, list) else []
    hlasy = {}
    for index, slot in enumerate(slots):
        if isinstance(slot, dict):
            for jazyk in _jazyky_stareho_slova(slot.get("text"), index):
                hlasy[jazyk] = hlasy.get(jazyk, 0) + 1
    preferovane = [j for j in jazyky if j in LANGUAGES]

    def poradie(jazyk):
        return (-hlasy[jazyk],
                preferovane.index(jazyk) if jazyk in preferovane else len(preferovane),
                LANGUAGES.index(jazyk))
    jazyky_profilu = sorted(hlasy, key=poradie)
    for index, slot in enumerate(slots):
        if isinstance(slot, dict) and "text" in slot:
            vlastny = jazyk_hlasu(slot.get("voice_edge"))
            slot["text"] = migrate_slot_text(
                slot["text"], index, ([vlastny] if vlastny else []) + jazyky_profilu)
    return slots


def normalize_slot(raw):
    """Fills in missing keys and sanitises ranges - for old settings too."""
    slot = dict(DEFAULT_SLOT)
    if isinstance(raw, dict):
        slot.update({k: v for k, v in raw.items() if k in DEFAULT_SLOT})
    slot["key_type"] = "mouse" if slot.get("key_type") == "mouse" else "keyboard"
    mode = slot.get("mode")
    if mode == "audio":
        mode = MODE_SFX  # migration from the old schema (Dandurf 2.0)
    slot["mode"] = mode if mode in MODE_ORDER else MODE_TTS
    slot["enabled"] = bool(slot.get("enabled", True))
    slot["key_repr"] = str(slot.get("key_repr") or "")
    slot["text"] = str(slot.get("text") or "")
    slot["audio_path"] = str(slot.get("audio_path") or "")
    slot["sfx_key"] = str(slot.get("sfx_key") or "")
    slot["voice_edge"] = str(slot.get("voice_edge") or "")
    slot["voice_sapi"] = str(slot.get("voice_sapi") or "")
    slot["voice_path"] = str(slot.get("voice_path") or "")
    # Stable uid: it is filled in once and lives in the profile from then
    # on. The recording name is derived from it, so two profiles with the
    # "same" slot do not overwrite each other's files (that was data loss -
    # B1).
    slot["uid"] = str(slot.get("uid") or "") or uuid.uuid4().hex[:12]
    slot["cooldown"] = optional_cooldown(slot.get("cooldown"))
    slot["delay"] = clamp_float(slot.get("delay"), 0.0, 30.0, 0.0)
    slot["every_n"] = clamp_int(slot.get("every_n"), 1, 99, 1)
    slot["repeat"] = clamp_int(slot.get("repeat"), 1, 10, 1)
    slot["repeat_gap"] = clamp_float(slot.get("repeat_gap"), 0.05, 30.0, 0.5)
    slot["jitter"] = clamp_float(slot.get("jitter"), 0.0, 0.9, 0.0)
    return slot


# What from a cue goes into the profile code (Cues -> Export
# profile). The code is shared with other people, so it contains only
# what makes sense to someone else, and nothing that would give away
# this computer:
#   * `audio_path` and `voice_path` are ABSOLUTE paths to recordings
#     (C:\Users\<meno>\AppData\...) - the code would give away the
#     Windows account name, and a recording does not travel with the
#     code anyway,
#   * `uid` is a local identifier of the recording files (an import gets
#     a new one),
#   * `key_type`, `key_repr`, `cooldown`, `delay`, `every_n`, `repeat`,
#     `repeat_gap`, `jitter` are dead fields from the days of key
#     triggers - nothing reads them.
ZDIELANE_POLIA_SLOTU = ("text", "mode", "sfx_key", "enabled", "voice_edge",
                        "voice_sapi")


def slot_na_zdielanie(slot):
    """A cue for the profile code - only `ZDIELANE_POLIA_SLOTU`. A custom
    sound (`sfx_key` "__custom__") is a file on this PC, so in the code
    it falls back to automatic selection."""
    if not isinstance(slot, dict):
        return {}
    out = {k: slot[k] for k in ZDIELANE_POLIA_SLOTU if k in slot}
    if out.get("sfx_key") == "__custom__":
        out["sfx_key"] = ""
    return out


def slot_zo_zdielania(raw):
    """A cue from someone else's profile code, or None.

    Only `ZDIELANE_POLIA_SLOTU` is taken - also from older codes that
    still carried paths and uid. File paths are therefore ALWAYS empty (a
    foreign path would play if it happened to exist on this PC) and
    `normalize_slot` fills in a fresh uid, so the imported profile does
    not share recording files with another one (rec_<uid>.wav - data
    loss B1)."""
    if not isinstance(raw, dict):
        return None
    slot = slot_na_zdielanie(raw)
    slot["audio_path"] = ""
    slot["voice_path"] = ""
    slot["uid"] = ""
    return normalize_slot(slot)


def normalize_overlay_config(raw, index):
    """Fills in missing keys, sanitises ranges for 1 overlay_configs entry."""
    default_pos = OVERLAY_DEFAULT_POS.get(index, (50.0, 50.0))
    # `enabled` missing -> ENABLED. A missing key means "an old or
    # incomplete record", not "the player turned it off"; disabled visuals
    # silence the app.
    cfg = {"enabled": True, "scale": 1.0,
           "pos_x": default_pos[0], "pos_y": default_pos[1], "color": None}
    if isinstance(raw, dict):
        cfg["enabled"] = bool(raw.get("enabled", True))
        cfg["scale"] = clamp_float(raw.get("scale"), 0.5, 2.0, 1.0)
        cfg["pos_x"] = clamp_float(raw.get("pos_x"), 0.0, 100.0, default_pos[0])
        cfg["pos_y"] = clamp_float(raw.get("pos_y"), 0.0, 100.0, default_pos[1])
        # pictogram colour: None = theme accent; otherwise a checked #rrggbb
        cfg["color"] = _valid_hex(raw.get("color"))
    return cfg


def _valid_hex(value):
    """Returns '#rrggbb' if valid, otherwise None (= use the theme colour)."""
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
    """Text shown in the SFX preset dropdown for the given slot state."""
    if sfx_key == "__custom__":
        name = os.path.basename(audio_path) if audio_path else "-"
        return tr("sfx.custom_prefix", name=name)
    if sfx_key and ":" in sfx_key:
        pack, key = sfx_key.split(":", 1)
        return f"{pack_label(pack)}: {sfx_assets.sound_label(pack, key)}"
    return tr("sfx.auto")


def sfx_dropdown_options():
    """[(display, value)] for all SFX preset choices across both packs."""
    options = [(tr("sfx.auto"), "")]
    for pack in (theme_mod.ZEN, theme_mod.MODERN):
        for key, label in sfx_assets.library_items(pack):
            options.append((f"{pack_label(pack)}: {label}", f"{pack}:{key}"))
    return options
