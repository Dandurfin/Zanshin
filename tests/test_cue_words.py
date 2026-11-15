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
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import settings_model  # noqa: E402

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
                         "Solta", "顎をゆるめて"):
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
    assert zaznam["sk"] == "Jaw" and zaznam["en"] == "Jaw"
    assert zaznam["ja"] == "顎"
    assert "Teeth" not in zaznam.values()


def test_zh_uvolnenie_je_povol():
    assert i18n.STRINGS["slot.default.release"]["zh"] == "松开"
    # 0.3: the slot 2 category is "hand and gaze" (UX audit), not just grip
    assert i18n.STRINGS["cue.category.release"]["zh"] == "手与视线"


def test_ru_popisok_celuste_je_razozmi():
    assert i18n.STRINGS["overlay.caption.jaw"]["ru"] == "РАЗОЖМИ ЧЕЛЮСТЬ"


def test_ja_popisky_su_v_makkom_tvare():
    """-て (a request), not the bare command 落とせ / ゆるめろ."""
    for kluc in (k for k in _kluce_v_hre() if k.startswith("overlay.caption.")):
        text = i18n.STRINGS[kluc]["ja"]
        assert text.endswith("て"), (kluc, text)
        assert not text.endswith(("ろ", "せ")), (kluc, text)


@pytest.mark.parametrize("jazyk", ["sk", "en"])
def test_novy_profil_hovori_jaw(jazyk):
    povodny = i18n._lang["code"]
    try:
        i18n.set_lang(jazyk)
        sloty = settings_model.default_slots()
    finally:
        i18n.set_lang(povodny)
    assert sloty[1]["text"] == "Jaw"


# --------------------------------------------------------------------------
# Migration of the old default word
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stare, index, nove", [
    ("Teeth", 1, "Jaw"), ("teeth", 1, "Jaw"), ("TEETH", 1, "Jaw"),
    ("  Teeth ", 1, "Jaw"), ("Teeth", 3, "Jaw"), ("Teeth", None, "Jaw"),
    ("脱力", 1, "顎"), ("放松", 2, "松开"),
])
def test_stare_predvolene_slovo_sa_zmeni(stare, index, nove):
    assert settings_model.migrate_slot_text(stare, index) == nove


@pytest.mark.parametrize("vlastne", [
    "my teeth", "Teeth!", "Zuby", "Jaw", "", "Release", "Breathe", "Челюсть",
])
def test_vlastne_slovo_hraca_ostava(vlastne):
    assert settings_model.migrate_slot_text(vlastne, 1) == vlastne


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
    assert slova["Hlavny"] == ["Grounded", "Jaw", "Release", "Breathe"]
    assert slova["Druhy"] == ["Jaw", "顎", "松开", "my teeth"]
    # outside its own slot it is the player's word - it stays
    assert slova["Treti"] == ["Grounded", "Jaw", "脱力", "放松"]


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
