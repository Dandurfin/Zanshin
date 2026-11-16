# -*- coding: utf-8 -*-
"""Words the app says and shows IN GAME (0.2, words-and-fixes).

Decisions these tests guard:
  * a cue never says "uvoľni sa" (relax) or "upokoj sa" (calm down) - in
    none of the 11 languages. A command about a STATE under load can
    backfire (Wegner 1997); the app says one word about the body. Applies
    to the slot's voice word (`slot.default.*`) and to the caption under
    the picture (`overlay.caption.*`).
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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import i18n_cs_bg  # noqa: E402
import settings_model  # noqa: E402
from _zdroj_appky import KOREN, zdroj_suboru  # noqa: E402

# Keys that get INTO THE GAME: the slot's voice word and the caption under
# the visual.
_PREFIXY_V_HRE = ("slot.default.", "overlay.caption.")

# Forbidden words ("uvoľni sa" / "upokoj sa"), compared regardless of case.
# The UNION of all languages is checked in every language - while a
# translation is missing, the slot has English text and that must not say
# "relax" either.
# 脱力 is literally "release (of strength)" - that is why it disappeared
# from the jaw voice word.
ZAKAZANE = {
    "sk": ("uvoľni sa", "uvolni sa", "upokoj", "relax"),
    "en": ("relax", "calm down"),
    "ja": ("リラックス", "落ち着", "脱力"),
    "zh": ("放松", "放鬆", "冷静", "冷靜"),
    "ru": ("расслаб", "успокой"),
    "es": ("relaj", "relája", "cálmate", "calmate", "tranquilízate"),
    "de": ("entspann", "beruhig"),
    "fr": ("détends", "détendez", "calme-toi", "calmez-vous"),
    "pt": ("relaxa", "acalma"),
    "cs": ("uvolni se", "uklidni se", "uklidněte"),
    "bg": ("отпусни се", "успокой се", "релаксирай"),
}
_VSETKY_ZAKAZANE = tuple(slovo.casefold() for slova in ZAKAZANE.values()
                         for slovo in slova)


def _zakazane(text):
    t = str(text).casefold()
    return [slovo for slovo in _VSETKY_ZAKAZANE if slovo in t]


def _kluce_v_hre():
    return sorted(k for k in i18n.STRINGS if k.startswith(_PREFIXY_V_HRE))


def test_kontrola_nieco_kontroluje():
    """Safeguard against an empty test: all four slots and five captions are
    there and the list really catches the old wording."""
    kluce = _kluce_v_hre()
    for kat in ("grounding", "jaw", "release", "breath"):
        assert f"slot.default.{kat}" in kluce
    for cap in ("grounding", "jaw", "release", "inhale", "exhale"):
        assert f"overlay.caption.{cap}" in kluce
    for stare_znenie in ("放松", "РАССЛАБЬ ЧЕЛЮСТЬ", "脱力", "Relax", "Calm down",
                         "Upokoj sa", "Uvoľni sa", "Entspann dich", "Cálmate",
                         "Relájate",
                         "Détends-toi", "Relaxa", "リラックスして", "УСПОКОЙСЯ"):
        assert _zakazane(stare_znenie), stare_znenie
    for dobre_znenie in ("UVOĽNI ČEĽUSŤ", "UNCLENCH YOUR JAW", "松开",
                         "РАЗОЖМИ ЧЕЛЮСТЬ", "RELÂCHE TON POIDS", "Loslassen",
                         "Solta", "顎をゆるめて", "Exhale, release",
                         "Expire, relâche", "Ausatmen, loslassen",
                         "Издишай, разхлаби", "Long exhale"):
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
# reads only `_PREFIXY_V_HRE`, did not read it either - a relax command
# waiting for the first line of code that would use it.
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
            elif (isinstance(uzol, ast.JoinedStr) and len(uzol.values) > 1
                  and _je_text(uzol.values[0])):
                zaciatok = uzol.values[0].value
            elif (isinstance(uzol, ast.BinOp) and isinstance(uzol.op, (ast.Mod, ast.Add))
                  and _je_text(uzol.left)):
                zaciatok = uzol.left.value.split("%")[0]
            elif (isinstance(uzol, ast.Call) and isinstance(uzol.func, ast.Attribute)
                  and uzol.func.attr == "format" and _je_text(uzol.func.value)):
                zaciatok = uzol.func.value.value.split("{")[0]
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
    """A profile in the old words (a profile code shared from 0.3) still
    has its language, and after the migration the same one."""
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
    (`app.load_settings`)."""
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
