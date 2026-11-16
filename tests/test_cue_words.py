# -*- coding: utf-8 -*-
"""Words the app says and shows IN GAME (0.2, words-and-fixes).

Decisions these tests guard:
  * a cue never says "uvoľni sa" (relax) or "upokoj sa" (calm down) - in
    none of the 11 languages. A command about a STATE under load can
    backfire (Wegner 1997); the app says one word about the body. Applies
    to everything that gets into the game: the slot's voice word
    (`slot.default.*`), the caption under the picture (`overlay.caption.*`)
    and what the HUD draws in the game language (`hud.*`, the time inside
    its session line `dashboard.fmt.*`); that the code translates nothing
    else in the game language is read from the code. The forbidden phrases
    are command-shaped ("stay calm", "bleib ruhig", "се отпусни", "放轻松")
    or stems no in-game text uses, so today's state LABELS stay allowed: the
    HUD zone "Calm" / "Ruhig" / "Klid" / "Покой" / "平静", or "above your own
    calm" in the "How it came about" text. In the cue itself (voice word,
    caption) such a state word is not allowed even alone - "Exhale, calm"
    or a caption "CALMA" commands the state too. Text and phrases are
    compared after NFKC, casefolding, one kind of dash and apostrophe, no
    invisible characters and one space for any run of whitespace - a
    no-break space, a non-breaking hyphen, a zero-width mark or "´" for an
    apostrophe does not hide a command.
  * the voice word "Teeth" is "Jaw" (ja 顎), zh 放松 ("uvoľni sa") is 松开
    ("povoľ", loosen), ru caption РАЗОЖМИ ЧЕЛЮСТЬ (not РАССЛАБЬ), ja
    captions in the soft -て form instead of a bare command (落とせ /
    ゆるめろ).
  * an existing profile with the old default word gets the new word when
    the settings are loaded; the player's own word stays as they wrote it.
  * after 0.3 every cue starts with the EXHALE (the author's idea): "Exhale,
    grounded" / "Exhale, jaw" / "Exhale, release", the breath slot says
    "Long exhale". Sk and cs keep the English words; the other languages
    say the exhale first and then the same body word as up to 0.3, short
    enough for about a second and a half. Every old default word (0.2-0.3
    and the 0.1 ones) of a slot becomes the new word of the same slot in
    the same language - also where several languages shared it (ja/zh
    呼吸, es/pt Mandíbula and Respira, ru/bg Опора).
  * no dead in-game text waits in the catalogue: `overlay.visual.jaw_label`
    ("RELAX JAW", never shown, outside the reach of the forbidden-word
    check) is gone, and every `overlay.*` key is read by the app's code.
"""
import ast
import glob
import json
import os
import re
import sys
import types
import unicodedata

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import i18n_cs_bg  # noqa: E402
import settings_model  # noqa: E402
from _zdroj_appky import KOREN, zdroj_suboru  # noqa: E402

# Keys that get INTO THE GAME, by prefix: the cue itself - the slot's voice
# word and the caption under the picture (`_PREFIXY_POKYNU`) - and what the
# HUD draws in the game language: its labels and session line (`hud.*`) and
# the time inside that line (`dashboard.fmt.*`, built by `ui_kit.cas_text`
# with the game translator). `hud.*` also holds the HUD's settings texts in
# the app window; they are checked too - should a phrase ever hit their
# prose, narrow the phrase, not the scope. That the code translates no other
# key in the game language is read from the code
# (`test_texty_hry_maju_predponu_v_hre`). Not read from the code: an
# app-language `tr()` text put into the HUD, and the slot's voice word
# (from `settings_model`) - their keys are covered only by these prefixes.
_PREFIXY_POKYNU = ("slot.default.", "overlay.caption.")
_PREFIXY_V_HRE = _PREFIXY_POKYNU + ("hud.", "dashboard.fmt.")

# Forbidden phrases ("uvoľni sa" / "upokoj sa"), compared after
# `_normalizuj`. The UNION of all languages is checked in every language -
# while a translation is missing, the slot has English text and that must
# not say "relax" either.
# 脱力 is literally "release (of strength)" - that is why it disappeared
# from the jaw voice word; 力を抜いて says the same.
# A command, not a state label: the union is also checked in the HUD zone
# label (Calm, Calma, Ruhig, Klid, Pokoj, Покой, 平静) and in the "How it
# came about" text ("above your own calm", "nad svým klidem", "offen
# gelassen", stress / estrés / ストレス / стресса as a topic). That is why
# there is no bare calm, calma, ruhig, klid, gelassen, stress, 平静 or
# ストレス, nor uvoľni / relâch / ゆるめ (approved captions: UVOĽNI ČEĽUSŤ,
# RELÂCHE TON POIDS, 顎をゆるめて) - in a cue itself such a state word is
# caught by `_STAV_V_POKYNE`. A word or stem is here when it hits none of
# the texts this file checks, even if the catalogue uses it elsewhere as an
# adjective, a topic or a description (chill, tranquilo, спокойно, паник;
# "ganz ruhig" on the felt-load scale, "sa po vypätí upokojuješ" in the onboarding) -
# if such a text ever gets into the game, the test fails and someone
# decides. Where a command shape is enough, only the command shape is here
# ("zachovej chladnou hlavu", not about.body's "udržet chladnou hlavu" or
# "keep a cool head"; "спокойнее!", not ob.step1.body's "закончить игру
# спокойнее").
# Still substrings, not word starts: "kľud" has to catch "ukľudni sa",
# "relax" "zrelaxuj", "entspann" "Muskelentspannung".
ZAKAZANE = {
    "sk": ("uvoľni sa", "uvolni sa", "sa uvoľni", "sa uvolni", "uvoľnite sa",
           "uvolnite sa", "upokoj", "relax", "kľud", "klud", "zachovaj pokoj",
           "zachovajte pokoj", "buď pokojn", "bud pokojn", "buďte pokojn",
           "budte pokojn", "ostaň pokojn", "ostan pokojn", "ostaňte pokojn",
           "ostante pokojn", "ostaň v pokoji", "ostan v pokoji", "ostaňte v pokoji",
           "ostante v pokoji", "len pokoj", "hlavne pokoj", "zachovaj chladnú hlavu",
           "zachovajte chladnú hlavu", "nestresuj", "žiadny stres", "ziadny stres",
           "nepanik", "žiadna panika", "ziadna panika", "nerob paniku",
           "nebuď nervózn", "nebud nervozn", "nebuďte nervózn", "nebudte nervozn"),
    "en": ("relax", "calm down", "stay calm", "keep calm", "remain calm", "be calm",
           "calm your", "calm it down", "chill", "take it easy", "unwind",
           "loosen up", "lighten up", "ease up", "settle down", "simmer down",
           "cool down", "cool it", "cool off", "stay cool", "keep cool",
           "keep your cool", "compose yourself", "stay composed",
           "be at ease", "destress", "de-stress", "no stress", "don't stress",
           "dont stress", "do not stress", "no panic", "don't panic", "dont panic",
           "do not panic", "freak out", "don't get nervous", "dont get nervous",
           "do not get nervous", "don't tense", "dont tense"),
    "ja": ("リラックス", "落ち着", "落ちつ", "おちつ", "脱力", "力を抜", "力抜", "ちからをぬ",
           "力まな", "楽にし", "らくにし", "気楽に", "きらくに", "気を楽に", "くつろ",
           "寛いで", "ゆったりして","焦らな", "焦るな", "焦らず", "あせらな", "あせるな",
           "あせらず", "慌てな", "慌てるな", "慌てず", "あわてな", "あわてるな", "あわてず",
           "パニックにならな", "パニックになるな", "緊張しな", "緊張するな", "緊張をほぐ",
           "イライラしな", "動揺しな", "熱くならな", "平常心", "穏やかに", "おだやかに"),
    "zh": ("放松", "放鬆", "冷静", "冷靜", "放轻松", "放輕鬆", "轻松点", "輕鬆點",
           "轻松一点", "輕鬆一點", "轻松些", "輕鬆些", "轻松一下", "輕鬆一下", "淡定",
           "镇定", "鎮定", "镇静", "鎮靜", "平静下来", "平靜下來", "静下心", "靜下心",
           "沉住气", "沉住氣", "放宽心", "放寬心", "别紧张", "別緊張", "不要紧张",
           "不要緊張", "别慌", "別慌", "不要慌", "莫慌", "别急", "別急", "不要急", "着急",
           "著急", "别激动", "別激動", "别焦虑", "別焦慮", "松弛", "鬆弛", "减压", "減壓",
           "解压", "解壓"),
    "ru": ("расслаб", "успокой", "спокойно", "спокойств", "спокойнее!", "поспокойнее",
           "будь спокоен", "будь спокойн", "будьте спокойн", "оставайся спокойн",
           "оставайтесь спокойн", "сохраняй хладнокрови", "сохраняйте хладнокрови",
           "не нервнич", "не волнуй", "не психуй", "не дёргай", "не дергай",
           "не суетис", "не горячис", "не кипятис", "без нервов", "паник",
           "не напрягайся", "не напрягайтесь", "не стрессуй", "остынь", "угомон"),
    "es": ("relaj", "reláj", "cálm", "calmate", "calmese", "calmense", "calmaos",
           "¡calma", "calma!", "calma !", "calma, calma", "con calma", "ten calma",
           "mantén la calma", "manten la calma", "mantenga la calma",
           "mantente calmad", "quédate calmad", "quedate calmad", "estate calmad",
           "tranquilo", "tranquila", "¡tranqui", "tranqui!", "tranquilíz",
           "tranquiliz", "tranquilíc", "tranquilic", "serénate", "serenate",
           "sosiég", "sosieg", "suéltate", "sueltate", "no te estres", "no se estres",
           "desestrés", "desestres", "sin estrés", "sin estres", "no te agobies",
           "no te pongas nervios", "no te alteres", "no entres en pánico",
           "no entres en panico", "sin pánico", "sin panico"),
    "de": ("entspann", "beruhig", "bleib ruhig", "bleiben sie ruhig",
           "ruhig bleiben", "sei ruhig", "seien sie ruhig", "ganz ruhig", "ruhig!",
           "ruhig, ruhig", "werde ruhig", "werd ruhig", "ruhig blut", "nur die ruhe",
           "ruhe bewahren", "bewahr die ruhe", "bewahre die ruhe",
           "bewahren sie die ruhe", "immer mit der ruhe", "komm zur ruhe",
           "bleib gelassen", "bleiben sie gelassen", "sei gelassen",
           "gelassen bleiben", "komm runter", "komm mal runter", "kommen sie runter",
           "runterkommen", "reg dich ab", "reg dich nicht auf", "nicht aufregen",
           "keine aufregung", "keine panik", "keine hektik", "kein stress",
           "keinen stress", "stress dich nicht", "nicht stressen", "bleib locker",
           "locker bleiben", "immer locker", "mach dich locker", "nimm's locker",
           "nimm es locker", "bleib cool", "cool bleiben", "nicht nervös werden",
           "sei nicht nervös", "werd nicht nervös", "werde nicht nervös"),
    "fr": ("détends", "détendez", "detends", "detendez", "décontract", "decontract",
           "calme-toi", "calmez-vous", "calme toi", "calmez vous", "on se calme",
           "calme!", "calme !", "sois calme", "soyez calme", "reste calme",
           "restez calme", "du calme", "garde ton calme", "gardez votre calme",
           "garde ton sang", "gardez votre sang", "reste détendu", "restez détendu",
           "reste detendu", "restez detendu", "sois détendu", "soyez détendu",
           "sois detendu", "soyez detendu", "reste zen", "restez zen", "sois zen",
           "soyez zen", "reste cool", "restez cool", "reste serein", "restez serein",
           "relâche-toi", "relache-toi", "relâche toi", "relache toi",
           "relâchez-vous", "relachez-vous", "relâchez vous", "relachez vous",
           "apaise-toi", "apaisez-vous", "apaise toi", "apaisez vous", "tranquille",
           "tranquillis", "t'énerve pas", "t'enerve pas", "énervez pas",
           "enervez pas", "pas de panique", "panique pas", "paniquez pas",
           "pas de stress", "stresse pas", "stressez pas"),
    "pt": ("relaxa", "acalm", "calma!", "calma aí", "calma ai", "com calma",
           "tenha calma", "tem calma", "mantenha a calma", "mantém a calma",
           "mantem a calma", "mantenha-se calm", "mantém-te calm", "mantem-te calm",
           "fica calm", "fique calm", "fica seren", "fique seren", "fica frio",
           "fique frio", "sosseg", "descontrai", "não se estress", "nao se estress",
           "não te stress", "nao te stress", "sem stress", "sem estresse",
           "não fique nervos", "nao fique nervos", "não fica nervos",
           "nao fica nervos", "se apavor", "te apavor", "não entre em pânico",
           "nao entre em panico", "sem pânico", "sem panico"),
    "cs": ("uvolni se", "se uvolni", "uvolněte se", "uvolnete se", "se uvolněte",
           "se uvolnete", "uklidn", "uklidňuj", "zklidn", "zklidňuj", "klídek",
           "klidek", "jen klid", "klid!", "klid, klid", "zachovej klid",
           "zachovejte klid", "buď v klidu", "bud v klidu", "buďte v klidu",
           "budte v klidu", "zůstaň v klidu", "zustan v klidu", "zůstaňte v klidu",
           "zustante v klidu", "buď klidn", "bud klidn", "buďte klidn", "budte klidn",
           "zůstaň klidn", "zustan klidn", "zůstaňte klidn", "zustante klidn",
           "zachovej chladnou hlavu", "zachovejte chladnou hlavu", "žádný stres",
           "zadny stres", "žádná panika", "zadna panika"),
    "bg": ("отпусни се", "се отпусни", "отпуснете се", "се отпуснете",
           "разпусни се", "се разпусни", "разпуснете се", "успокой се", "релакс",
           "бъди спокоен", "бъди спокойн", "бъдете спокойн", "остани спокоен",
           "остани спокойн", "останете спокойн", "бъди отпуснат", "не се стресирай",
           "не стресирай", "без стрес", "не се напрягай", "не се вълнувай",
           "не се нервирай", "охлади се", "разтовари се"),
}

# One form of the characters a command could hide behind: the common
# dashes as "-" (U+2011 "calme\u2011toi"), the common apostrophes as "'" -
# also the acute accent, backtick and prime typed in their place ("Don´t"
# on a keyboard where ´ is a dead key). Invisible characters go
# (`_bez_neviditelnych`): every format character (soft hyphen, zero-width
# space, direction marks) and the invisible ones that are not format
# characters - the grapheme joiner, variation selectors and the Hangul
# filler (U+3164, the usual "invisible name" in games). NFKC turns a
# no-break or thin space into a space and fullwidth "Ｒｅｌａｘ" into "Relax".
_ROVNAKE_ZNAKY = {
    **dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2043\u2212"), "-"),
    **dict.fromkeys(map(ord, "\u2018\u2019\u201b\u02bc\u02bb\u02b9\u00b4`\u2032"), "'"),
}
_NEVIDITELNE_NAVYSE = frozenset(
    ["\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u3164", "\uffa0",
     *map(chr, range(0x180B, 0x1810)), *map(chr, range(0xFE00, 0xFE10)),
     *map(chr, range(0xE0100, 0xE01F0))])


def _bez_neviditelnych(text):
    return "".join(z for z in text if unicodedata.category(z) != "Cf"
                   and z not in _NEVIDITELNE_NAVYSE)


_MEDZERY = re.compile(r"\s+")


def _normalizuj(text):
    """The characters above (also before NFKC, which would split "´" into
    a space and a combining accent), NFKC, casefold (and NFKC again, so
    the result does not change when normalised twice), any run of
    whitespace as one space - for the text and the phrases alike."""
    t = _bez_neviditelnych(str(text).translate(_ROVNAKE_ZNAKY))
    t = _bez_neviditelnych(unicodedata.normalize("NFKC", t).translate(_ROVNAKE_ZNAKY))
    return _MEDZERY.sub(" ", unicodedata.normalize("NFKC", t.casefold()))


_VSETKY_ZAKAZANE = tuple(dict.fromkeys(_normalizuj(slovo) for slova in ZAKAZANE.values()
                                       for slovo in slova))


def _zakazane(text):
    t = _normalizuj(text)
    return [slovo for slovo in _VSETKY_ZAKAZANE if slovo in t]


# A cue that only NAMES the state commands it all the same: "Exhale, calm"
# in the app's own "<exhale>, <word>" shape, or a caption alone ("CALMA",
# "KLID", "GELASSEN"). Most of these words are state labels elsewhere (the
# HUD zone "Calm" / "Ruhig" / "Klid" / "Покой", "above your own calm"), so
# they cannot be in ZAKAZANE (a few are there too: chill, tranquilo,
# спокойно): they are checked as whole words, with their feminine, plural
# and comparative forms, and only in the cue itself - the slot's voice word
# and the caption under the picture (`_PREFIXY_POKYNU`), not the HUD. A
# state word about a body part ("Klidný dech", "Ruhig atmen") is caught on
# purpose: the cue names the body or a movement, not how it should feel.
# Not here: "locker" (de "Kiefer locker lassen" is the approved "Kiefer
# lockern" - loose muscles, not a mood) and "ゆったり" ("ゆったり吐いて" =
# "breathe out slowly"). ja/zh write no spaces between words, so there it
# is a substring.
_STAV_V_POKYNE = frozenset(_normalizuj(slovo) for slovo in (
    # en
    "calm", "calmly", "calmer", "calmness", "chill", "easy", "zen", "serene",
    # es / pt
    "calma", "calmo", "calmos", "calmas", "calmado", "calmada", "calmados",
    "calmadas", "calmamente", "calmadamente", "tranquilo", "tranquila",
    "tranquilos", "tranquilas", "tranquilamente", "sereno", "serena",
    "serenos", "serenas", "serenamente",
    # fr
    "calme", "calmes", "calmement", "tranquille", "tranquilles",
    "tranquillement", "serein", "sereine", "sereins", "sereines",
    "sereinement", "détendu", "détendue", "détendus", "détendues", "detendu",
    "detendue", "detendus", "detendues",
    # de
    "ruhig", "ruhige", "ruhiger", "ruhiges", "ruhigen", "ruhe", "gelassen",
    "gelassene", "gelassener",
    # cs / sk
    "klid", "klidně", "klidne", "klidněji", "klidneji", "klidný", "klidny",
    "klidná", "klidna", "klidní", "klidni", "klidné", "klidnější", "klidnejsi",
    "kľud", "klud", "pokoj", "pokojne", "pokojnejšie", "pokojnejsie", "pokojný",
    "pokojny", "pokojná", "pokojna", "pokojní", "pokojni", "pokojné",
    "pokojnejší", "pokojnejsi",
    # ru / bg
    "спокойно", "спокойствие", "спокоен", "спокойна", "спокойни", "спокойны",
    "спокойный", "спокойная", "спокойное", "спокойные", "спокойным",
    "спокойной", "спокойнее", "спокойней", "покой"))
_STAV_V_POKYNE_CJK = tuple(_normalizuj(slovo) for slovo in (
    "平静", "平靜", "安静", "安靜", "轻松", "輕鬆", "穏やか", "平常心"))
_SLOVO = re.compile(r"\w+")


def _stav_v_pokyne(text):
    t = _normalizuj(text)
    return sorted({s for s in _SLOVO.findall(t) if s in _STAV_V_POKYNE}
                  | {s for s in _STAV_V_POKYNE_CJK if s in t})


# Helpers the game translator is handed to, which build their own keys with
# it: helper name -> the start of those keys (it has to be in
# `_PREFIXY_V_HRE`). `ui_kit.cas_text` -> `dlzka_text` writes the time in
# the HUD session line ("1 h 15 min"). The scan does not read a helper's
# code, so each helper here is called with a translator that writes down
# the keys it asks for (`test_cas_v_hre_sklada_len_svoje_kluce`) - a new
# helper needs such a check too.
_POMOCNICI_HRY = {"cas_text": "dashboard.fmt."}


def _je_preklad_hry(uzol, mena):
    """`self._game_text`, or a local name for it (`g = self._game_text`)."""
    return ((isinstance(uzol, ast.Attribute) and uzol.attr == "_game_text")
            or (isinstance(uzol, ast.Name) and uzol.id in mena))


def _meno_volania(uzol):
    """`ui_kit.cas_text` / `cas_text` -> "cas_text"."""
    if isinstance(uzol, ast.Attribute):
        return uzol.attr
    return uzol.id if isinstance(uzol, ast.Name) else ast.unparse(uzol)


def _kluce_argumentu(kluc):
    """(whole keys, fixed starts) of a key argument: a text, a choice of two
    texts ("hud.waiting" if c else "hud.calibrating") or a built key
    (f"hud.zone.{zone}" -> the start "hud.zone."). None: it cannot be read."""
    if _je_text(kluc):
        return {kluc.value}, set()
    if (isinstance(kluc, ast.IfExp) and _je_text(kluc.body)
            and _je_text(kluc.orelse)):
        return {kluc.body.value, kluc.orelse.value}, set()
    zaciatok = _zaciatok_skladaneho_kluca(kluc) if kluc is not None else None
    return (set(), {zaciatok}) if zaciatok else None


def _texty_hry_v_kode():
    """What the app's code translates in the GAME language, read via ast:
    (whole keys, fixed starts of built keys, helpers the translator is
    handed to, places the scan cannot read - with the reason).

    The game translator is `self._game_text` (app_hud.py) or a local name
    for it (`g = self._game_text`). It may be called - its key, the first
    argument or `key=`, is a text, a choice of two texts or a built key
    with a fixed start - or handed to a helper as an argument
    (`ui_kit.cas_text(..., preklad=self._game_text)`); then only the
    helper's name is noted and `_POMOCNICI_HRY` says which keys it builds.
    Reported instead: a key the scan cannot read (in a variable), the
    translator stored, returned or taken through getattr
    (`self.hud.preklad = g`, `return self._game_text` - the scan would lose
    track of it), and a direct `tr_lang(...game_lang...)` call outside
    `_game_text` (a second road into the game)."""
    kluce, zaciatky, pomocnici, nejasne = set(), set(), set(), set()
    zabaleny = ("(nebaľ preklad hry: volaj self._game_text priamo, alebo "
                "g = self._game_text)")
    for meno in _subory_produkcie():
        zdroj = zdroj_suboru(meno)
        if "_game_text" not in zdroj and "game_lang" not in zdroj:
            continue
        strom = ast.parse(zdroj)
        sledovane = set()           # uses of the translator the scan follows
        for fn in ast.walk(strom):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            mena = set()
            for u in ast.walk(fn):
                if (isinstance(u, ast.Assign) and _je_preklad_hry(u.value, ())
                        and all(isinstance(c, ast.Name) for c in u.targets)):
                    mena |= {c.id for c in u.targets}
                    sledovane.add(id(u.value))
            for u in ast.walk(fn):
                if not isinstance(u, ast.Call):
                    continue
                miesto = f"{meno}:{u.lineno}"
                if _je_preklad_hry(u.func, mena):
                    sledovane.add(id(u.func))
                    kluc = (u.args[0] if u.args else
                            next((k.value for k in u.keywords if k.arg == "key"), None))
                    najdene = _kluce_argumentu(kluc)
                    if najdene:
                        kluce |= najdene[0]
                        zaciatky |= najdene[1]
                    else:
                        nejasne.add(f"{miesto}: kľúč textu do hry sa nedá prečítať - "
                                    "napíš ho ako text alebo f\"hud.x.{...}\" " + zabaleny)
                for argument in (*u.args, *(k.value for k in u.keywords)):
                    if _je_preklad_hry(argument, mena):
                        sledovane.add(id(argument))
                        pomocnici.add(_meno_volania(u.func))
                if (_meno_volania(u.func) == "tr_lang" and u.args
                        and "game_lang" in ast.unparse(u.args[0])
                        and fn.name != "_game_text"):
                    nejasne.add(f"{miesto}: tr_lang v jazyku hry mimo _game_text - "
                                "text do hry má ísť cez self._game_text")
            nejasne.update(
                f"{meno}:{u.lineno}: preklad hry `{u.id}` sa ukladá alebo vracia - test "
                "nevie, čo sa s ním preloží " + zabaleny
                for u in ast.walk(fn)
                if isinstance(u, ast.Name) and isinstance(u.ctx, ast.Load)
                and u.id in mena and id(u) not in sledovane)
        nejasne.update(
            f"{meno}:{u.lineno}: preklad hry sa ukladá, vracia alebo berie cez getattr - "
            "test nevie, čo sa s ním preloží " + zabaleny
            for u in ast.walk(strom)
            if (isinstance(u, ast.Attribute) and u.attr == "_game_text"
                and id(u) not in sledovane)
            or (_je_text(u) and u.value == "_game_text"))
    return kluce, zaciatky, pomocnici, sorted(nejasne)


def _kluce_v_hre():
    return sorted(k for k in i18n.STRINGS if k.startswith(_PREFIXY_V_HRE))


def test_texty_hry_maju_predponu_v_hre():
    """Every key the code translates in the game language - and every key a
    helper builds with the game translator - starts with `_PREFIXY_V_HRE`,
    so the word checks below read it. Safeguard against an empty scan: the
    HUD labels, the session line, the captions and the time are found."""
    kluce, zaciatky, pomocnici, nejasne = _texty_hry_v_kode()
    assert not nejasne, "\n  ".join(["text do hry, ktorý test nevie prečítať:", *nejasne])
    nezname = sorted(pomocnici - set(_POMOCNICI_HRY))
    assert not nezname, (
        f"preklad hry dostáva pomocník {nezname}: dopíš ho do _POMOCNICI_HRY so "
        "začiatkom kľúčov, ktoré skladá (ten musí byť v _PREFIXY_V_HRE), a over ho "
        "ako test_cas_v_hre_sklada_len_svoje_kluce")
    starty = kluce | zaciatky | {_POMOCNICI_HRY[p] for p in pomocnici}
    mimo = sorted(k for k in starty if not k.startswith(_PREFIXY_V_HRE))
    assert not mimo, (f"texty do hry mimo _PREFIXY_V_HRE (kontrola slov ich nečíta): {mimo}"
                      " - dopíš ich začiatok do _PREFIXY_V_HRE")
    zname = ("hud.load", "hud.zone.calm", "hud.waiting", "hud.calibrating",
             "hud.session.triggers", "hud.session.over", "overlay.caption.jaw")
    nenajdene = [z for z in zname if not any(z.startswith(s) for s in starty)]
    assert not nenajdene, (
        f"tieto texty do hry sken v kóde nenašiel: {nenajdene} - ak si ich z hry "
        "odstránil naschvál, oprav zoznam `zname`; ak sa premenoval _game_text, "
        "oprav _je_preklad_hry")
    assert "cas_text" in pomocnici, (
        "čas v riadku HUD nejde cez ui_kit.cas_text s prekladom hry - ak ide cez "
        "iného pomocníka, dopíš ho do _POMOCNICI_HRY a oprav túto kontrolu")
    chybaju = sorted(k for k in kluce if k not in i18n.STRINGS)
    assert not chybaju, f"kód prekladá do hry kľúče, ktoré v i18n nie sú: {chybaju}"
    prazdne = sorted(z for z in zaciatky if not any(k.startswith(z) for k in i18n.STRINGS))
    assert not prazdne, f"kód skladá do hry kľúče, ku ktorým v i18n nič nie je: {prazdne}"


def test_cas_v_hre_sklada_len_svoje_kluce():
    """`_POMOCNICI_HRY` is not read from the helper's code - so the helper is
    called with a translator that writes down every key it asks for, from
    under a minute to days (the HUD shows the time from one hour on)."""
    import ui_kit
    pytane = []

    def preklad(kluc, **kwargs):
        pytane.append(kluc)
        return i18n.tr_lang("en", kluc, **kwargs)

    for sekundy in (0, 59, 3599, 3600, 4500, 86_400, 10 ** 7):
        ui_kit.cas_text(sekundy, preklad=preklad)
    assert pytane, "cas_text sa na nijaký text nepýtal - zmenil sa?"
    zaciatok = _POMOCNICI_HRY["cas_text"]
    zle = sorted({k for k in pytane if not k.startswith(zaciatok)})
    assert not zle, f"cas_text skladá do hry aj kľúče mimo {zaciatok}: {zle}"


def test_kontrola_nieco_kontroluje():
    """Safeguard against an empty test: all four slots, five captions and
    the HUD zones are there and the list really catches the old wording and
    the commands found later - but not the approved words, nor a state
    label, nor the app's own prose that only describes."""
    kluce = _kluce_v_hre()
    for kat in ("grounding", "jaw", "release", "breath"):
        assert f"slot.default.{kat}" in kluce
    for cap in ("grounding", "jaw", "release", "inhale", "exhale"):
        assert f"overlay.caption.{cap}" in kluce
    for zona in ("calm", "raised", "high", "critical"):
        assert f"hud.zone.{zona}" in kluce
    for stare_znenie in ("放松", "РАССЛАБЬ ЧЕЛЮСТЬ", "脱力", "Relax", "Calm down",
                         "Upokoj sa", "Uvoľni sa", "Entspann dich", "Cálmate",
                         "Relájate",
                         "Détends-toi", "Relaxa", "リラックスして", "УСПОКОЙСЯ",
                         # en
                         "Stay calm", "Keep calm", "Chill out", "Take it easy",
                         "Unwind", "Loosen up", "Settle down", "Cool down",
                         "Don't stress", "Don’t panic", "Be calm", "Chill", "Chillax",
                         "Keep your cool", "Calm your mind", "Ease up", "No panic",
                         "Don't tense up", "Simmer down",
                         # de
                         "Bleib ruhig", "Ganz ruhig", "Bleib gelassen", "Komm runter",
                         "Keine Panik", "Kein Stress", "Nur die Ruhe", "Ruhig, ruhig",
                         "Werde ruhig", "Reg dich ab", "Nicht aufregen", "Bleib cool",
                         "Nimm’s locker", "Keine Hektik", "Komm zur Ruhe",
                         # fr
                         "Reste calme", "Du calme", "Reste détendu", "Reste zen",
                         "Relâche-toi", "Reste tranquille", "Pas de panique",
                         "Décontracte-toi", "Decontracte toi", "On se calme", "Sois calme",
                         "Tranquille", "Reste serein", "Garde ton sang-froid",
                         "Ne t’énerve pas",
                         # es
                         "¡Calma!", "¡Tranquilo!", "Relájese", "Cálmese", "Sosiégate",
                         "Mantén la calma", "Tómatelo con calma", "Sin pánico",
                         "Desestrésate", "Tranquilo", "Tranquila", "¡Tranqui!",
                         "No te agobies", "Mantente calmado", "Serénate",
                         # pt
                         "Acalme-se", "Calma!", "Fica calmo", "Fique tranquilo",
                         "Sossega", "Descontrai", "Vai com calma", "Sem pânico",
                         "Desestressa", "Calma aí", "Sem estresse", "Não fique nervoso",
                         "Fica frio", "Não se apavore",
                         # ru
                         "Спокойно!", "Не нервничай", "Не волнуйся", "Без паники",
                         "Остынь", "Угомонись", "Сохраняй спокойствие", "Спокойно",
                         "Спокойствие", "Спокойнее!", "Будьте спокойны",
                         "Оставайся спокойным", "Оставайтесь спокойными", "Не психуй",
                         "Не дёргайся", "Сохраняй хладнокровие",
                         # bg
                         "Се отпусни", "Отпуснете се", "Разпусни се",
                         "Не се паникьосвай", "Запази спокойствие", "Бъдете спокойни",
                         "Остани спокоен", "Останете спокойни", "Не се вълнувай",
                         "Без стрес", "Не изпадай в паника",
                         # sk
                         "Teraz sa uvoľni", "Uvoľnite sa", "Kľud", "Ukľudni sa",
                         "Zachovaj pokoj", "Nestresuj", "Buďte pokojný", "Budte pokojny",
                         "Zostaňte pokojný", "Ostaň pokojný", "Zostaň v pokoji", "Klud",
                         "Kludne", "Žiadny stres", "Nebuď nervózny",
                         # cs
                         "Teď se uklidni", "Uvolněte se", "Zachovej klid",
                         "Buď v klidu", "Klid!", "Nepanikař", "Zůstaň v klidu",
                         "Zustan v klidu", "Zklidni se", "Zklidněte se", "Uklidni mysl",
                         "Klídek", "Buďte klidní", "Žádná panika",
                         "Zachovej chladnou hlavu",
                         # ja
                         "力を抜いて", "楽にして", "気楽に", "焦らないで", "慌てないで",
                         "緊張しないで", "穏やかに", "パニックにならないで", "慌てずに",
                         "焦らずに", "落ちついて", "くつろいで", "力まないで", "気を楽に",
                         # zh
                         "放轻松", "放輕鬆", "淡定", "别紧张", "別緊張", "镇定", "别慌",
                         "轻松点", "松弛", "减压", "解压", "别着急", "不要着急", "別著急",
                         "平静下来", "平靜下來", "沉住气", "别激动", "静下心来", "莫慌",
                         # hidden behind other characters (`_normalizuj`)
                         "calme\u2011toi", "uvoľni\u00a0sa", "Stay\u202fcalm",
                         "calm\u2009down", "uvoľni  sa", "Ｒｅｌａｘ", "re\u00adlax",
                         "Calme\u202f!", "Don\u00b4t panic", "Don`t panic",
                         "Don\u2032t panic", "re\u200elax", "re\u3164lax",
                         "re\u180blax", "re\ufe0flax"):
        assert _zakazane(stare_znenie), stare_znenie
    for dobre_znenie in ("UVOĽNI ČEĽUSŤ", "UNCLENCH YOUR JAW", "松开",
                         "РАЗОЖМИ ЧЕЛЮСТЬ", "RELÂCHE TON POIDS", "Loslassen",
                         "Solta", "顎をゆるめて", "Exhale, release",
                         "Expire, relâche", "Ausatmen, loslassen",
                         "Издишай, разхлаби", "Long exhale",
                         "Exhale, grounded", "Exhale, jaw", "RELÂCHE TA PRISE",
                         "UVOLNI ČELIST", "ОТПУСНИ ЧЕЛЮСТТА", "LOOSEN YOUR GRIP",
                         "AFLOJA LA MANDÍBULA", "KIEFER LOCKERN", "握りをゆるめて",
                         # a state label, not a command
                         "Calm", "Calma", "Calme", "Calmo", "Ruhig", "Klid", "Pokoj",
                         "Покой", "平静", "平靜", "above your own calm",
                         "nad svým klidem", "nad svojím pokojom", "über deiner Ruhe",
                         "offen gelassen", "losgelassen", "stress", "estrés",
                         "ストレス", "стресса", "压力",
                         # the app's own prose: a description, not a command
                         "udržet chladnou hlavu", "udržať chladnú hlavu",
                         "keep a cool head", "закончить игру спокойнее"):
        assert not _zakazane(dobre_znenie), dobre_znenie


def test_v_hre_nikdy_uvolni_sa_ani_upokoj_sa():
    zle = []
    for kluc in _kluce_v_hre():
        for jazyk in i18n.LANGUAGES:
            text = i18n.tr_lang(jazyk, kluc)
            najdene = _zakazane(text)
            if najdene:
                zle.append(f"{kluc}[{jazyk}] = {text!r} ({', '.join(najdene)})")
    assert not zle, "v hre nesmie zaznieť „uvoľni sa / upokoj sa“:\n  " + "\n  ".join(zle)


def test_pokyn_v_hre_nemenuje_stav():
    """The slot's voice word and the caption name the body, not the state -
    not even as a bare word (`_STAV_V_POKYNE`). Safeguard first: the check
    catches the shapes it is for and lets the approved words through."""
    for zle_znenie in ("Exhale, calm", "EXHALE, CALM", "Exhale, easy", "Ausatmen, ruhig",
                       "Ausatmen, gelassen", "Exhala, calma", "Expire, calme",
                       "Expira, calmo", "Выдох, спокойно", "Издишай, спокойно",
                       "呼气，平静", "呼气，轻松", "CALMA", "KLID", "Klid.", "GELASSEN",
                       "СПОКОЙНО", "Покой", "CHILL", "ZEN", "Expire calmement",
                       "Exhala calmamente", "Dýchej klidněji", "Dýchaj pokojnejšie",
                       "Выдох, спокойней", "kl\u200eid"):
        assert _stav_v_pokyne(zle_znenie), zle_znenie
    for dobre_znenie in ("KIEFER LOCKERN", "GRIFF LOCKERN", "Exhale, grounded",
                         "UNCLENCH YOUR JAW", "Expire, relâche", "息を吐いて、解放",
                         "呼气，松开", "Издишай, разхлаби"):
        assert not _stav_v_pokyne(dobre_znenie), dobre_znenie
    pokyny = sorted(k for k in i18n.STRINGS if k.startswith(_PREFIXY_POKYNU))
    assert len(pokyny) >= 9                 # 4 slots, 5 captions
    zle = []
    for kluc in pokyny:
        for jazyk in i18n.LANGUAGES:
            text = i18n.tr_lang(jazyk, kluc)
            najdene = _stav_v_pokyne(text)
            if najdene:
                zle.append(f"{kluc}[{jazyk}] = {text!r} ({', '.join(najdene)})")
    assert not zle, ("pokyn v hre menuje stav, nie časť tela ani pohyb:\n  "
                     + "\n  ".join(zle))


def test_hlasove_slovo_celuste_je_jaw():
    zaznam = i18n.STRINGS["slot.default.jaw"]
    assert zaznam["sk"] == "Exhale, jaw" and zaznam["en"] == "Exhale, jaw"
    assert zaznam["ja"].endswith("顎")
    assert not any("teeth" in slovo.casefold() for slovo in zaznam.values())


def test_zh_uvolnenie_je_povol():
    assert i18n.STRINGS["slot.default.release"]["zh"].endswith("松开")
    # 0.3: the slot 2 category is "grip & gaze" (UX audit), not just a squeeze
    assert i18n.STRINGS["cue.category.release"]["zh"] == "手与视线"


def test_ru_popisok_celuste_je_razozmi():
    assert i18n.STRINGS["overlay.caption.jaw"]["ru"] == "РАЗОЖМИ ЧЕЛЮСТЬ"


def test_ja_popisky_su_v_makkom_tvare():
    """-て (a request), not the bare command 落とせ / ゆるめろ."""
    for kluc in (k for k in _kluce_v_hre() if k.startswith("overlay.caption.")):
        text = i18n.STRINGS[kluc]["ja"]
        assert text.endswith("て"), (kluc, text)
        assert not text.endswith(("ろ", "せ")), (kluc, text)


@pytest.mark.parametrize("jazyk", ["sk", "en", "cs"])
def test_novy_profil_hovori_jaw(jazyk):
    povodny = i18n._lang["code"]
    try:
        i18n.set_lang(jazyk)
        sloty = settings_model.default_slots()
    finally:
        i18n.set_lang(povodny)
    assert sloty[1]["text"] == "Exhale, jaw"


# --------------------------------------------------------------------------
# No dead in-game text in the catalogue (after 0.3)
# --------------------------------------------------------------------------

# The old label under the jaw picture: "RELAX JAW", ru РАССЛАБЬ, zh 放松,
# es RELAJA, de ENTSPANNEN, pt RELAXE (its cs/bg text was the same as
# today's caption). Nothing ever showed it (the caption the player
# sees is `overlay.caption.jaw`), so the forbidden-word check above, which
# reads only the keys that get into the game (`_kluce_v_hre`), did not read
# it either - a relax command waiting for the first line of code that would
# use it.
_STARY_POPISOK_CELUSTE = "overlay.visual.jaw_label"

# The `overlay.*` keys the code BUILDS, and for exactly which names. The
# name of the category above a slot, f"overlay.slot.{index}": slots 0-3
# (app.py and ui_dialogs.py go through range(4), the slot card asks
# `je_kategoria`); a slot from index 4 on has no category, nor a name. A new
# family the code starts to build has to be added here, with its names.
_RODINY_OVERLAY = {
    "overlay.slot.": tuple(str(i) for i in range(settings_model.CUE_CATEGORY_COUNT)),
}

# The start of a key: what a built key begins with up to its first `%` / `{`.
_ZACIATOK_KLUCA = re.compile(r"overlay\.[A-Za-z0-9_.]*")


def _subory_produkcie():
    """The app's code: every *.py in the project root except the catalogue
    itself and the GUI harnesses (gui_*.py) - those drive the windows the
    way a test does, and a key only they read is never seen by the player."""
    mena = (os.path.basename(p) for p in glob.glob(os.path.join(KOREN, "*.py")))
    return sorted(m for m in mena
                  if m not in ("i18n.py", "i18n_cs_bg.py") and not m.startswith("gui_"))


def _je_text(uzol):
    return isinstance(uzol, ast.Constant) and isinstance(uzol.value, str)


def _zaciatok_skladaneho_kluca(uzol):
    """The fixed start of a key the code builds, or None: f"overlay.slot.{i}",
    "overlay.slot.%d" % i, "overlay.slot." + x and "overlay.slot.{}".format(i)
    all give "overlay.slot." (the same for a HUD key, f"hud.zone.{z}")."""
    if (isinstance(uzol, ast.JoinedStr) and len(uzol.values) > 1
            and _je_text(uzol.values[0])):
        return uzol.values[0].value
    if (isinstance(uzol, ast.BinOp) and isinstance(uzol.op, (ast.Mod, ast.Add))
            and _je_text(uzol.left)):
        return uzol.left.value.split("%")[0]
    if (isinstance(uzol, ast.Call) and isinstance(uzol.func, ast.Attribute)
            and uzol.func.attr == "format" and _je_text(uzol.func.value)):
        return uzol.func.value.value.split("{")[0]
    return None


def _kluce_overlay_v_kode():
    """(whole keys, families) of `overlay.*` in the app's code.

    A whole key is a string that is exactly "overlay.x.y". A family is the
    fixed start of a key the code builds - f"overlay.slot.{index}" (the only
    one in 0.3), "overlay.slot.%d" % i, "overlay.slot." + x and
    "overlay.slot.{}".format(i) all give "overlay.slot.". Read via ast, so a
    key mentioned in a comment or inside a docstring sentence does not count
    as read. Families: {start: ["file:line", ...]}."""
    cele, rodiny = set(), {}
    for meno in _subory_produkcie():
        for uzol in ast.walk(ast.parse(zdroj_suboru(meno))):
            zaciatok = None
            if _je_text(uzol):
                cele.add(uzol.value)
            else:
                zaciatok = _zaciatok_skladaneho_kluca(uzol)
            if zaciatok and _ZACIATOK_KLUCA.fullmatch(zaciatok):
                rodiny.setdefault(zaciatok, []).append(f"{meno}:{uzol.lineno}")
    return cele, rodiny


def _katalog_overlay():
    """`overlay.*` keys from i18n.py and from both cs/bg dicts."""
    return {k for k in (*i18n.STRINGS, *i18n_cs_bg.CS, *i18n_cs_bg.BG)
            if k.startswith("overlay.")}


def test_stary_popisok_celuste_nie_je_v_katalogu():
    """Neither in i18n.py nor in the Czech or Bulgarian dict - the merge in
    i18n.py takes cs/bg only for a key i18n.py has, so a leftover there
    would just wait for the key to come back."""
    kde = [meno for meno, slovnik in (("i18n.py", i18n.STRINGS),
                                      ("i18n_cs_bg.CS", i18n_cs_bg.CS),
                                      ("i18n_cs_bg.BG", i18n_cs_bg.BG))
           if _STARY_POPISOK_CELUSTE in slovnik]
    assert not kde, f"{_STARY_POPISOK_CELUSTE} je znova v: {', '.join(kde)}"


def test_kazdy_text_obrazka_appka_naozaj_cita():
    """Every `overlay.*` key (the in-game picture and its settings) is read
    by the app's code, word for word or through a family in
    `_RODINY_OVERLAY`. A text nobody reads is checked by nobody either -
    that is how "RELAX JAW" outlived the caption the player really sees."""
    cele, rodiny = _kluce_overlay_v_kode()
    # safeguard against a vacuous pass: the scan really finds whole keys and
    # the slot family
    assert {"overlay.caption.jaw", "overlay.test", "overlay.monitor.auto"} <= cele
    assert "overlay.slot." in rodiny
    assert set(rodiny) == set(_RODINY_OVERLAY), (
        "kod sklada kluce overlay.*, ktore _RODINY_OVERLAY nepozna (alebo uz nesklada):\n  "
        + "\n  ".join(f"{z}  ({', '.join(miesta)})" for z, miesta in sorted(rodiny.items())))
    clenovia = {zaciatok + meno for zaciatok, mena in _RODINY_OVERLAY.items()
                for meno in mena}
    chybaju = sorted(clenovia - set(i18n.STRINGS))
    assert not chybaju, f"kod sklada kluce, ktore v i18n nie su: {chybaju}"
    nikto_necita = sorted(k for k in _katalog_overlay()
                          if k not in cele and k not in clenovia)
    assert not nikto_necita, ("texty obrazka, ktore appka necita (zmaz ich, alebo ich "
                              "pouzi):\n  " + "\n  ".join(nikto_necita))


# --------------------------------------------------------------------------
# The exhale first (after 0.3)
# --------------------------------------------------------------------------

_KATEGORIE = ("grounding", "jaw", "release", "breath")

# The new words, written out by hand: this table IS the decision - a change
# to a word has to be made here too, on purpose.
NOVE_SLOVA = {
    "sk": ("Exhale, grounded", "Exhale, jaw", "Exhale, release", "Long exhale"),
    "en": ("Exhale, grounded", "Exhale, jaw", "Exhale, release", "Long exhale"),
    "cs": ("Exhale, grounded", "Exhale, jaw", "Exhale, release", "Long exhale"),
    "ja": ("息を吐いて、重心", "息を吐いて、顎", "息を吐いて、解放", "息を長く吐いて"),
    "zh": ("呼气，落地", "呼气，牙关", "呼气，松开", "长长地呼气"),
    "ru": ("Выдох, опора", "Выдох, челюсть", "Выдох, отпусти", "Долгий выдох"),
    "es": ("Exhala, pies en la tierra", "Exhala, mandíbula", "Exhala, suelta",
           "Exhala largo"),
    "de": ("Ausatmen, geerdet", "Ausatmen, Kiefer", "Ausatmen, loslassen",
           "Lang ausatmen"),
    "fr": ("Expire, ancré", "Expire, mâchoire", "Expire, relâche", "Expire longuement"),
    "pt": ("Expira, aterrado", "Expira, mandíbula", "Expira, solta", "Expiração longa"),
    "bg": ("Издишай, опора", "Издишай, челюст", "Издишай, разхлаби", "Издишай дълго"),
}

# The default words up to 0.3 (0.2-0.3 first, then the 0.1 ones that 0.2
# had already replaced), per language and slot - also written out by hand,
# independently of `settings_model._STARE_PREDVOLENE_SLOVA`.
STARE_SLOVA = {
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

# How each language says the exhale (casefolded): (how grounding, jaw and
# release start, what the breath slot contains).
VYDYCH = {
    "sk": ("exhale", "exhale"), "en": ("exhale", "exhale"),
    "cs": ("exhale", "exhale"), "ja": ("息を吐いて", "吐いて"),
    "zh": ("呼气", "呼气"), "ru": ("выдох", "выдох"), "es": ("exhala", "exhala"),
    "de": ("ausatmen", "ausatmen"), "fr": ("expire", "expire"),
    "pt": ("expira", "expira"), "bg": ("издишай", "издишай"),
}


def _nove(jazyk, index):
    return i18n.tr_lang(jazyk, f"slot.default.{_KATEGORIE[index]}")


def _stare_slova():
    """(language, slot, old word) for every old default word."""
    return [(jazyk, index, slovo) for jazyk, sloty in sorted(STARE_SLOVA.items())
            for index, slova in enumerate(sloty) for slovo in slova]


def test_tabulky_pokryvaju_vsetky_jazyky():
    assert set(NOVE_SLOVA) == set(STARE_SLOVA) == set(VYDYCH) == set(i18n.LANGUAGES)


@pytest.mark.parametrize("jazyk", sorted(NOVE_SLOVA))
def test_nove_slova_kazdeho_jazyka(jazyk):
    assert tuple(_nove(jazyk, i) for i in range(4)) == NOVE_SLOVA[jazyk]


def test_sk_a_cs_hovoria_anglicke_slova():
    """Deliberately the same English words as en - also after the change."""
    for jazyk in ("sk", "cs"):
        assert NOVE_SLOVA[jazyk] == NOVE_SLOVA["en"]


@pytest.mark.parametrize("jazyk", sorted(NOVE_SLOVA))
def test_najprv_vydych_potom_to_iste_telo(jazyk):
    """Grounding, jaw and release start with the exhale and keep the body
    word of 0.3; the breath slot is about the long exhale. The one
    shortening: es "Con los pies en la tierra" -> "pies en la tierra",
    otherwise it would not fit into a second and a half."""
    zaciatok, v_dychu = VYDYCH[jazyk]
    for index in range(3):
        slovo = _nove(jazyk, index).casefold()
        assert slovo.startswith(zaciatok), (jazyk, index, slovo)
        telo = STARE_SLOVA[jazyk][index][0].casefold()
        if (jazyk, index) == ("es", 0):
            telo = "pies en la tierra"
        assert telo in slovo[len(zaciatok):], (jazyk, index, slovo)
    assert v_dychu in _nove(jazyk, 3).casefold(), jazyk


@pytest.mark.parametrize("jazyk", sorted(NOVE_SLOVA))
def test_nove_slova_su_kratke(jazyk):
    """About a second and a half when spoken: no longer than the longest
    word up to 0.3 (es "Con los pies en la tierra", 25 characters); ja/zh
    at most 8 characters."""
    limit = 8 if jazyk in ("ja", "zh") else 25
    for index in range(4):
        assert len(_nove(jazyk, index)) <= limit, (jazyk, index)


def test_ja_hlasove_slova_su_v_makkom_tvare():
    """The exhale as a request (吐いて), not the bare command 吐け."""
    for index in range(4):
        slovo = _nove("ja", index)
        assert "吐いて" in slovo and "吐け" not in slovo, slovo


def test_nove_slova_nie_su_stare():
    """Otherwise the migration would change them again on every load."""
    stare = {slovo.casefold() for _, _, slovo in _stare_slova()}
    for jazyk in NOVE_SLOVA:
        for index in range(4):
            assert _nove(jazyk, index).casefold() not in stare


@pytest.mark.parametrize("jazyk", sorted(NOVE_SLOVA))
def test_nove_slova_bez_zakazanych(jazyk):
    for index in range(4):
        assert not _zakazane(_nove(jazyk, index)), (jazyk, index)


# --------------------------------------------------------------------------
# Migration of the old default word
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stare, index, nove", [
    ("Teeth", 1, "Exhale, jaw"), ("teeth", 1, "Exhale, jaw"),
    ("TEETH", 1, "Exhale, jaw"), ("  Teeth ", 1, "Exhale, jaw"),
    # outside the jaw slot exactly what 0.2-0.3 made of it
    ("Teeth", 3, "Jaw"), ("Teeth", None, "Jaw"),
    ("脱力", 1, "息を吐いて、顎"), ("放松", 2, "呼气，松开"),
    ("Grounded", 0, "Exhale, grounded"), (" breathe ", 3, "Long exhale"),
    ("Jaw", 1, "Exhale, jaw"), ("Release", 2, "Exhale, release"),
])
def test_stare_predvolene_slovo_sa_zmeni(stare, index, nove):
    assert settings_model.migrate_slot_text(stare, index) == nove


@pytest.mark.parametrize("jazyk, index, stare", _stare_slova())
def test_kazde_stare_slovo_dostane_nove_slovo_svojho_jazyka(jazyk, index, stare):
    """Every old default word of every language (sk/cs English too) -> the
    new word of the same slot in the same language. Alone (a word shared by
    several languages decides the language given first)..."""
    nove = NOVE_SLOVA[jazyk][index]
    assert settings_model.migrate_slot_text(stare, index, (jazyk,)) == nove
    assert settings_model.migrate_slot_text(f"  {stare.upper()} ", index, (jazyk,)) == nove


@pytest.mark.parametrize("jazyk", sorted(STARE_SLOVA))
@pytest.mark.parametrize("vek", [0, -1])
def test_cely_stary_profil_dostane_slova_svojho_jazyka(jazyk, vek):
    """...and in a whole profile with no hint at all: the other words tell
    the language (a Portuguese profile has "Aterrado" next to "Mandíbula").
    `vek` 0 = the 0.2-0.3 words, -1 = the oldest ones (0.1)."""
    sloty = [settings_model.normalize_slot({"text": slova[vek]})
             for slova in STARE_SLOVA[jazyk]]
    settings_model.migrate_profile_texts(sloty)
    assert tuple(s["text"] for s in sloty) == NOVE_SLOVA[jazyk]


@pytest.mark.parametrize("slova, jazyky, nove", [
    # nothing in the profile tells - the voice / app language decides
    ((None, None, None, "呼吸"), ("zh",), "长长地呼气"),
    ((None, None, None, "呼吸"), ("ja",), "息を長く吐いて"),
    ((None, "Mandíbula", None, None), ("pt", "es"), "Expira, mandíbula"),
    ((None, "Mandíbula", None, None), ("es", "pt"), "Exhala, mandíbula"),
    (("Опора", None, None, None), ("bg",), "Издишай, опора"),
    (("Опора", None, None, None), ("ru",), "Выдох, опора"),
    # a language that is not among the candidates does not get in the way
    ((None, None, None, "呼吸"), ("en", None, "zh"), "长长地呼气"),
    # no hint at all: the first in LANGUAGES order
    ((None, None, None, "呼吸"), (), "息を長く吐いて"),
    # the profile beats the hint: "Дишай" is Bulgarian only
    (("Опора", None, None, "Дишай"), ("ru",), "Издишай, опора"),
    (("Aterrado", None, None, "Respira"), ("es",), "Expiração longa"),
])
def test_spolocne_slovo_rozhodne_profil_potom_hlas(slova, jazyky, nove):
    sloty = [settings_model.normalize_slot({"text": t or "Moje slovo"}) for t in slova]
    settings_model.migrate_profile_texts(sloty, jazyky)
    zmenene = [s["text"] for s in sloty if s["text"] != "Moje slovo"]
    assert nove in zmenene


@pytest.mark.parametrize("vlastny_hlas, nove", [
    ("zh-CN-YunxiNeural", "长长地呼气"),
    ("ja-JP-KeitaNeural", "息を長く吐いて"),
    # a voice in a language that is not a candidate does not get in the way
    ("en-US-GuyNeural", "息を長く吐いて"),
    ("ko-KR-InJoonNeural", "息を長く吐いて"),
])
def test_vlastny_hlas_slotu_rozhodne_spolocne_slovo(vlastny_hlas, nove):
    """A slot with its own voice is read by that voice: 呼吸 read by a
    Chinese voice gets the Chinese word, even in a profile and with a
    shared voice that would say Japanese."""
    sloty = [settings_model.normalize_slot({"text": "Moje slovo"}) for _ in range(3)]
    sloty.append(settings_model.normalize_slot({"text": "呼吸", "voice_edge": vlastny_hlas}))
    settings_model.migrate_profile_texts(sloty, ("ja", "ja"))
    assert sloty[3]["text"] == nove
    # the slot's own voice decides only its own slot
    sloty = [settings_model.normalize_slot({"text": "Opora"}) for _ in range(4)]
    sloty[0]["text"] = "Опора"
    sloty[3].update(text="呼吸", voice_edge="zh-CN-YunxiNeural")
    settings_model.migrate_profile_texts(sloty, ("bg",))
    assert (sloty[0]["text"], sloty[3]["text"]) == ("Издишай, опора", "长长地呼气")


@pytest.mark.parametrize("vlastne", [
    "my teeth", "Teeth!", "Zuby", "", "Release", "Breathe", "Grounded",
    "Jaw!", "Exhale", "Exhale, jaw", "Exhale, teeth", "呼吸", "Опора",
    "Respira", "Con los pies", "Long exhale",
])
def test_vlastne_slovo_hraca_ostava(vlastne):
    """In the jaw slot: the player's own words, the new words and default
    words of OTHER slots stay as they are."""
    assert settings_model.migrate_slot_text(vlastne, 1) == vlastne


@pytest.mark.parametrize("jazyk, index, stare",
                         [x for x in _stare_slova() if x[2] != "Teeth"])
def test_stare_slovo_v_cudzom_slote_ostava(jazyk, index, stare):
    """A default word typed into another slot (or a slot from index 4 on,
    which has no category) is the player's word. ("Teeth" has the 0.2 rule,
    see `test_stare_predvolene_slovo_sa_zmeni`.)"""
    for iny in (0, 1, 2, 3, 4, 7, None):
        if iny != index:
            assert settings_model.migrate_slot_text(stare, iny, (jazyk,)) == stare, (stare, iny)
    sloty = [settings_model.normalize_slot({"text": "Moje slovo"}) for _ in range(6)]
    for iny in (0, 1, 2, 3, 4, 5):
        if iny != index:
            sloty[iny]["text"] = stare
    settings_model.migrate_profile_texts(sloty, (jazyk,))
    assert [s["text"] for i, s in enumerate(sloty) if i != index] == [stare] * 5


def test_nove_slova_sa_uz_nemenia():
    for jazyk in NOVE_SLOVA:
        sloty = [settings_model.normalize_slot({"text": t}) for t in NOVE_SLOVA[jazyk]]
        settings_model.migrate_profile_texts(sloty, (jazyk,))
        assert tuple(s["text"] for s in sloty) == NOVE_SLOVA[jazyk]


def test_migracia_profilu_znesie_aj_nezmysel():
    assert settings_model.migrate_profile_texts(None) == []
    sloty = [{"text": "Grounded"}, "nezmysel", {"mode": "tts"}, {"text": 3}]
    settings_model.migrate_profile_texts(sloty)
    assert sloty == [{"text": "Exhale, grounded"}, "nezmysel", {"mode": "tts"},
                     {"text": 3}]


def test_jazyk_hlasu():
    assert settings_model.jazyk_hlasu("pt-BR-FranciscaNeural") == "pt"
    assert settings_model.jazyk_hlasu("zh-CN-XiaoxiaoNeural") == "zh"
    assert settings_model.jazyk_hlasu("en-GB-SoniaNeural") == "en"
    assert settings_model.jazyk_hlasu("ko-KR-SunHiNeural") is None
    assert settings_model.jazyk_hlasu("") is None
    assert settings_model.jazyk_hlasu(None) is None


# --------------------------------------------------------------------------
# jazyky_hlasok with the new words
# --------------------------------------------------------------------------

def _profil(slova):
    return [settings_model.normalize_slot({"text": t}) for t in slova]


@pytest.mark.parametrize("jazyk", sorted(NOVE_SLOVA))
def test_jazyky_hlasok_pozna_nove_slova(jazyk):
    ocakavane = {"sk", "en", "cs"} if jazyk in ("sk", "en", "cs") else {jazyk}
    assert settings_model.jazyky_hlasok(_profil(NOVE_SLOVA[jazyk])) == ocakavane
    # one word alone is enough as well (ja and zh no longer share 呼吸)
    for index in range(4):
        sloty = _profil(NOVE_SLOVA[jazyk])
        for iny, slot in enumerate(sloty):
            if iny != index:
                slot["enabled"] = False
        assert settings_model.jazyky_hlasok(sloty) == ocakavane, (jazyk, index)


@pytest.mark.parametrize("jazyk", sorted(STARE_SLOVA))
def test_jazyky_hlasok_po_migracii_rovnake(jazyk):
    """A profile in the old words (typed back by the player, or kept by a
    profile code from 0.3.1) still has its language, and after the
    migration the same one."""
    stary = _profil(slova[0] for slova in STARE_SLOVA[jazyk])
    assert jazyk in settings_model.jazyky_hlasok(stary)
    settings_model.migrate_profile_texts(stary)
    assert jazyk in settings_model.jazyky_hlasok(stary)


def test_jazyky_hlasok_vlastne_slovo_stale_nema_jazyk():
    sloty = _profil(NOVE_SLOVA["de"])
    sloty[0]["text"] = "Ausatmen, Füße"
    assert settings_model.jazyky_hlasok(sloty) == set()
    zmiesane = _profil(NOVE_SLOVA["de"][:2] + NOVE_SLOVA["fr"][2:])
    assert settings_model.jazyky_hlasok(zmiesane) == set()
    sloty = _profil(NOVE_SLOVA["en"])
    sloty[0]["text"] = "  exhale, GROUNDED "
    assert settings_model.jazyky_hlasok(sloty) == {"sk", "en", "cs"}


@pytest.mark.parametrize("slovo, index", [
    ("脱力", 2), ("脱力", 0), ("脱力", None), ("放松", 1), ("放松", None),
])
def test_ja_zh_slovo_mimo_svojho_slotu_ostava(slovo, index):
    """In ja, 脱力 is also the name of the "Release" category - in slot 2 the
    player could have written it themselves and 顎 ("jaw") would be the
    wrong word there. It changes only in the slot where it was the
    default."""
    assert settings_model.migrate_slot_text(slovo, index) == slovo


def test_migracia_znesie_aj_nezmysel():
    assert settings_model.migrate_slot_text(None) is None
    assert settings_model.migrate_slot_text(3) == 3


def test_normalize_slot_slovo_nemeni():
    """The slot card normalises on every rebuild - if it also changed the
    word, it would be rewritten under the player's hands in the middle of
    editing. It changes only when the settings are loaded
    (`app.load_settings`) and when a profile code from before 0.3.1 is
    imported (`app.import_profile_from_code`)."""
    assert settings_model.normalize_slot({"text": "Teeth"})["text"] == "Teeth"


@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    import app_prefs
    cesta = str(tmp_path / "dandurf_settings.json")
    # `load_settings` lives in the app_prefs mixin (PrefsMixin) and reads
    # SETTINGS_PATH from its own module - it has to be redirected there.
    monkeypatch.setattr(app_prefs, "SETTINGS_PATH", cesta)
    povodny = i18n._lang["code"]

    def nacitaj(obsah):
        with open(cesta, "w", encoding="utf-8") as fh:
            json.dump(obsah, fh, ensure_ascii=False)
        return app_mod.DandurfApp.load_settings(types.SimpleNamespace())
    yield nacitaj
    i18n.set_lang(povodny)


def test_nacitanie_prelozi_stare_slovo_vo_vsetkych_profiloch(nastavenia):
    d = nastavenia({"lang": "sk", "theme": "zen", "profiles": [
        {"name": "Hlavny", "slots": [{"text": "Grounded"}, {"text": "Teeth"},
                                      {"text": "Release"}, {"text": "Breathe"}]},
        {"name": "Druhy", "slots": [{"text": " teeth "}, {"text": "脱力"},
                                     {"text": "放松"}, {"text": "my teeth"}]},
        {"name": "Treti", "slots": [{"text": "Grounded"}, {"text": "Jaw"},
                                     {"text": "脱力"}, {"text": "放松"}]},
    ]})
    slova = {p["name"]: [s["text"] for s in p["slots"]] for p in d["profiles"]}
    assert slova["Hlavny"] == list(NOVE_SLOVA["en"])
    assert slova["Druhy"] == ["Jaw", "息を吐いて、顎", "呼气，松开", "my teeth"]
    # outside its own slot it is the player's word - it stays
    assert slova["Treti"] == ["Exhale, grounded", "Exhale, jaw", "脱力", "放松"]


@pytest.mark.parametrize("jazyk", sorted(STARE_SLOVA))
def test_nacitanie_da_kazdemu_jazyku_jeho_nove_slova(nastavenia, jazyk):
    """A 0.3 profile in each language (app in English, default voice) gets
    the new words of its own language; the player's word stays."""
    stare = [slova[0] for slova in STARE_SLOVA[jazyk]]
    d = nastavenia({"lang": "en", "theme": "zen", "profiles": [
        {"name": "Moj", "slots": [{"text": t} for t in stare]},
        {"name": "Vlastny", "slots": [{"text": "Feet"}] + [{"text": t} for t in stare[1:]]},
    ]})
    slova = {p["name"]: [s["text"] for s in p["slots"]] for p in d["profiles"]}
    assert slova["Moj"] == list(NOVE_SLOVA[jazyk])
    assert slova["Vlastny"] == ["Feet"] + list(NOVE_SLOVA[jazyk][1:])


@pytest.mark.parametrize("hlas, lang, nove", [
    ("zh-CN-XiaoxiaoNeural", "en", "长长地呼气"),
    ("ja-JP-NanamiNeural", "zh", "息を長く吐いて"),   # the voice before the app language
    ("en-GB-SoniaNeural", "zh", "长长地呼气"),        # the app language
    ("en-GB-SoniaNeural", "en", "息を長く吐いて"),    # nothing tells: LANGUAGES order
])
def test_nacitanie_spolocne_slovo_podla_hlasu_a_jazyka(nastavenia, hlas, lang, nove):
    """呼吸 alone (the player replaced the other words): ja or zh? The voice
    that reads it decides, then the app language."""
    d = nastavenia({"lang": lang, "theme": "zen", "edge_voice": hlas, "profiles": [
        {"name": "P", "slots": [{"text": "A"}, {"text": "B"}, {"text": "C"},
                                {"text": "呼吸"}]}]})
    assert [s["text"] for s in d["profiles"][0]["slots"]] == ["A", "B", "C", nove]


def test_nacitanie_es_pt_podla_profilu(nastavenia):
    """Mandíbula and Respira are es and pt: the rest of the profile decides,
    not the app language."""
    d = nastavenia({"lang": "es", "theme": "zen", "edge_voice": "es-ES-ElviraNeural",
                    "profiles": [{"name": "P", "slots": [
                        {"text": "Aterrado"}, {"text": "Mandíbula"}, {"text": "Mi mano"},
                        {"text": "Respira"}]}]})
    assert [s["text"] for s in d["profiles"][0]["slots"]] == [
        "Expira, aterrado", "Expira, mandíbula", "Mi mano", "Expiração longa"]


def test_s_priznakom_sa_slova_uz_nemenia(nastavenia):
    """ONCE per settings file: after the first save (`exhale_words`) an old
    word the player types back ("Jaw", "Breathe") is their own word."""
    d = nastavenia({"lang": "en", "theme": "zen", "exhale_words": True, "profiles": [
        {"name": "P", "slots": [{"text": "Grounded"}, {"text": "Jaw"},
                                {"text": "Teeth"}, {"text": "Breathe"}]}]})
    assert [s["text"] for s in d["profiles"][0]["slots"]] == [
        "Grounded", "Jaw", "Teeth", "Breathe"]


def test_priznak_sa_uklada():
    from _zdroj_appky import zdroj_metody
    assert '"exhale_words": True' in zdroj_metody("save_settings")
    assert 'loaded.get("exhale_words")' in zdroj_metody("load_settings")


def test_nacitanie_novych_slov_ich_nemeni(nastavenia):
    d = nastavenia({"lang": "ja", "theme": "zen", "profiles": [
        {"name": "P", "slots": [{"text": t} for t in NOVE_SLOVA["ja"]]}]})
    assert [s["text"] for s in d["profiles"][0]["slots"]] == list(NOVE_SLOVA["ja"])


def test_nacitanie_stara_plocha_schema_tiez(nastavenia):
    """Settings from before profiles (only `slots`) go the same way."""
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "slots": [{"text": "Teeth"}, {"text": "Zuby"}]})
    sloty = d["profiles"][0]["slots"]
    assert [s["text"] for s in sloty[:2]] == ["Jaw", "Zuby"]
    # missing categories are added at the end, switched off (0.2)
    assert len(sloty) == 4 and not any(s["enabled"] for s in sloty[2:])


def test_panel_vyskumu_nesluboval_upokojenie():
    """The intro of the "Z čoho appka vychádza" (What the app builds on) panel
    said "kedy ti pomôcť sa upokojiť" / "help you calm down" - a sentence
    that the proposal about cues under load removed. In 0.2 the panel was
    replaced by the author's "How it came about" text (`origin.*`) - that
    must not say "upokoj sa" either - in any language."""
    for kluc in ("origin.title", "origin.text", "origin.examples"):
        zaznam = i18n.STRINGS[kluc]
        for jazyk in i18n.LANGUAGES:
            assert not _zakazane(zaznam[jazyk]), (kluc, jazyk)
