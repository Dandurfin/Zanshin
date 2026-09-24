# -*- coding: utf-8 -*-
"""Slová, ktoré appka hovorí a ukazuje V HRE (0.2, words-and-fixes).

Rozhodnutia, ktoré tieto testy strážia:
  * hláška nikdy nepovie „uvoľni sa“ ani „upokoj sa“ - v žiadnom z 11 jazykov.
    Príkaz na STAV pod záťažou môže vyjsť naopak (Wegner 1997); appka hovorí
    jedno slovo o tele. Platí pre hlasové slovo slotu (`slot.default.*`) aj
    pre popisok pod obrázkom (`overlay.caption.*`).
  * hlasové slovo „Teeth“ je „Jaw“ (ja 顎), zh 放松 („uvoľni sa“) je 松开
    („povoľ“), ru popisok РАЗОЖМИ ЧЕЛЮСТЬ (nie РАССЛАБЬ), ja popisky v mäkkom
    tvare na -て namiesto holého rozkazu (落とせ / ゆるめろ).
  * existujúci profil so starým predvoleným slovom dostane nové slovo pri
    načítaní nastavení; vlastné slovo hráča ostáva, ako ho napísal.
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import settings_model  # noqa: E402

# Kľúče, ktoré sa dostanú DO HRY: hlasové slovo slotu a popisok pod vizuálom.
_PREFIXY_V_HRE = ("slot.default.", "overlay.caption.")

# Zakázané slová („uvoľni sa“ / „upokoj sa“), porovnávané bez ohľadu na
# veľkosť písmen. Kontroluje sa ÚNIA všetkých jazykov v každom jazyku - kým
# preklad chýba, je v slote anglický text a ani ten nesmie povedať „relax“.
# 脱力 je doslova „uvoľnenie (sily)“ - preto zmizol z hlasového slova čeľuste.
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
    """Poistka proti prázdnemu testu: sú tam všetky štyri sloty a päť
    popiskov a zoznam naozaj chytí staré znenie."""
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
    assert i18n.STRINGS["cue.category.release"]["zh"] == "松开"


def test_ru_popisok_celuste_je_razozmi():
    assert i18n.STRINGS["overlay.caption.jaw"]["ru"] == "РАЗОЖМИ ЧЕЛЮСТЬ"


def test_ja_popisky_su_v_makkom_tvare():
    """-て (prosba), nie holý rozkaz 落とせ / ゆるめろ."""
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
# Migracia stareho predvoleneho slova
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
    """脱力 je v ja aj názov kategórie „Release“ - v slote 2 ho hráč mohol
    napísať sám a 顎 („čeľusť“) by tam bolo zlé slovo. Mení sa len v slote,
    kde bolo predvolené."""
    assert settings_model.migrate_slot_text(slovo, index) == slovo


def test_migracia_znesie_aj_nezmysel():
    assert settings_model.migrate_slot_text(None) is None
    assert settings_model.migrate_slot_text(3) == 3


def test_normalize_slot_slovo_nemeni():
    """Karta slotu normalizuje pri každej prestavbe - keby menila aj slovo,
    hráčovi by sa prepísalo pod rukami uprostred úpravy. Mení sa len pri
    načítaní nastavení (`app.load_settings`)."""
    assert settings_model.normalize_slot({"text": "Teeth"})["text"] == "Teeth"


@pytest.fixture
def nastavenia(tmp_path, monkeypatch):
    import app as app_mod
    cesta = str(tmp_path / "dandurf_settings.json")
    monkeypatch.setattr(app_mod, "SETTINGS_PATH", cesta)
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
    # mimo svojho slotu je to slovo hraca - ostava
    assert slova["Treti"] == ["Grounded", "Jaw", "脱力", "放松"]


def test_nacitanie_stara_plocha_schema_tiez(nastavenia):
    """Nastavenia spred profilov (len `slots`) idú tou istou cestou."""
    d = nastavenia({"lang": "sk", "theme": "zen",
                    "slots": [{"text": "Teeth"}, {"text": "Zuby"}]})
    sloty = d["profiles"][0]["slots"]
    assert [s["text"] for s in sloty[:2]] == ["Jaw", "Zuby"]
    # chybajuce kategorie sa doplnia na koniec, vypnute (0.2)
    assert len(sloty) == 4 and not any(s["enabled"] for s in sloty[2:])


def test_panel_vyskumu_nesluboval_upokojenie():
    """Úvod panela „Z čoho appka vychádza“ hovoril „kedy ti pomôcť sa
    upokojiť“ / „help you calm down“ - veta, ktorú návrh o hláškach pod
    záťažou zrušil. V 0.2 panel nahradil text autora „Ako to vzniklo“
    (`origin.*`) - ani ten nesmie povedať „upokoj sa“ - v žiadnom jazyku."""
    for kluc in ("origin.title", "origin.text", "origin.examples"):
        zaznam = i18n.STRINGS[kluc]
        for jazyk in i18n.LANGUAGES:
            assert not _zakazane(zaznam[jazyk]), (kluc, jazyk)
