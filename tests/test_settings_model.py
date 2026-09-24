"""Testy pre settings_model.py - ciste funkcie bez UI/IO (clamp/normalizacia).

Spustenie:  pytest tests/ -v
(Vyzaduje len 'pytest' navyse - `pip install pytest`. Ostatne zavislosti
projektu (customtkinter, pygame...) sa pri importe settings_model.py
nepotrebuju, kedze modul je ciste datovy.)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from settings_model import (  # noqa: E402
    DASHBOARD_STAT_IDS, DEFAULT_DASHBOARD_STATS, DEFAULT_SLOT,
    MODE_SFX, MODE_TTS, clamp_float, clamp_int, default_overlay_configs,
    normalize_dashboard_stats,
    normalize_overlay_config, normalize_slot, optional_cooldown,
)


# --------------------------------------------------------------------------
# clamp_float / clamp_int
# --------------------------------------------------------------------------

def test_clamp_float_within_range_unchanged():
    assert clamp_float(5.0, 0.0, 10.0, 1.0) == 5.0


def test_clamp_float_clips_above_high():
    assert clamp_float(999.0, 0.0, 10.0, 1.0) == 10.0


def test_clamp_float_clips_below_low():
    assert clamp_float(-5.0, 0.0, 10.0, 1.0) == 0.0


def test_clamp_float_invalid_returns_default():
    assert clamp_float("nezmysel", 0.0, 10.0, 3.5) == 3.5
    assert clamp_float(None, 0.0, 10.0, 3.5) == 3.5


def test_clamp_float_nan_returns_default():
    assert clamp_float(float("nan"), 0.0, 10.0, 2.0) == 2.0


def test_clamp_float_accepts_numeric_string():
    assert clamp_float("7.5", 0.0, 10.0, 0.0) == 7.5


def test_clamp_int_within_range_unchanged():
    assert clamp_int(5, 0, 10, 1) == 5


def test_clamp_int_clips_to_bounds():
    assert clamp_int(999, 0, 10, 1) == 10
    assert clamp_int(-5, 0, 10, 1) == 0


def test_clamp_int_invalid_returns_default():
    assert clamp_int("nezmysel", 0, 10, 4) == 4
    assert clamp_int(None, 0, 10, 4) == 4


def test_clamp_int_truncates_float_string():
    # cez float() medzikrok, takze "7.9" sa oreze na 7, nie zaokruhli na 8
    assert clamp_int("7.9", 0, 10, 0) == 7


# --------------------------------------------------------------------------
# optional_cooldown
# --------------------------------------------------------------------------

def test_optional_cooldown_none_stays_none():
    assert optional_cooldown(None) is None


def test_optional_cooldown_empty_string_is_none():
    assert optional_cooldown("") is None


def test_optional_cooldown_valid_value_clamped():
    assert optional_cooldown(2.5) == 2.5
    assert optional_cooldown(9999) == 600.0  # horny strop podla settings_model
    assert optional_cooldown(-5) == 0.0


# --------------------------------------------------------------------------
# normalize_slot - najdolezitejsia funkcia: kazdy nacitany/importovany
# slot (aj zo starej verzie appky) prechadza cez toto.
# --------------------------------------------------------------------------

def test_normalize_slot_empty_dict_has_all_default_keys():
    slot = normalize_slot({})
    assert set(slot.keys()) == set(DEFAULT_SLOT.keys())


def test_normalize_slot_none_or_garbage_input_still_returns_valid_slot():
    # normalize_slot musi prezit aj uplne nezmyselny vstup (napr. z
    # poskodeneho/rucne upraveneho JSON) - vzdy vrati platny slot dict.
    for garbage in (None, "text", 123, [1, 2, 3]):
        slot = normalize_slot(garbage)
        assert set(slot.keys()) == set(DEFAULT_SLOT.keys())
        assert slot["mode"] == MODE_TTS


def test_normalize_slot_preserves_valid_fields():
    raw = {"key_type": "mouse", "key_repr": "left", "text": "Dýchaj",
          "mode": "sfx", "enabled": False}
    slot = normalize_slot(raw)
    assert slot["key_type"] == "mouse"
    assert slot["key_repr"] == "left"
    assert slot["text"] == "Dýchaj"
    assert slot["mode"] == MODE_SFX
    assert slot["enabled"] is False


def test_normalize_slot_unknown_extra_keys_are_dropped():
    raw = dict(DEFAULT_SLOT, hackerova_vlastnost="ha", text="ok")
    slot = normalize_slot(raw)
    assert "hackerova_vlastnost" not in slot
    assert slot["text"] == "ok"


def test_normalize_slot_migrates_legacy_audio_mode_to_sfx():
    # stara schema (Dandurf 2.0) pouzivala mode="audio" namiesto "sfx"
    slot = normalize_slot({"mode": "audio"})
    assert slot["mode"] == MODE_SFX


def test_normalize_slot_invalid_mode_falls_back_to_tts():
    slot = normalize_slot({"mode": "neexistujuci_rezim"})
    assert slot["mode"] == MODE_TTS


def test_normalize_slot_invalid_key_type_falls_back_to_keyboard():
    slot = normalize_slot({"key_type": "gamepad_neplatny"})
    assert slot["key_type"] == "keyboard"


def test_normalize_slot_ranges_are_clamped():
    slot = normalize_slot({
        "delay": 9999, "every_n": 0, "repeat": 999, "repeat_gap": -1, "jitter": 5,
    })
    assert 0.0 <= slot["delay"] <= 30.0
    assert 1 <= slot["every_n"] <= 99
    assert 1 <= slot["repeat"] <= 10
    assert 0.05 <= slot["repeat_gap"] <= 30.0
    assert 0.0 <= slot["jitter"] <= 0.9


def test_normalize_slot_none_text_fields_become_empty_string():
    slot = normalize_slot({"text": None, "audio_path": None, "sfx_key": None})
    assert slot["text"] == ""
    assert slot["audio_path"] == ""
    assert slot["sfx_key"] == ""


def test_normalize_slot_voice_path_none_becomes_empty_string():
    # voice_path (vlastna nahravka hlasu) - rovnaka poistka ako audio_path.
    slot = normalize_slot({"voice_path": None})
    assert slot["voice_path"] == ""


def test_normalize_slot_voice_path_preserved():
    slot = normalize_slot({"voice_path": "C:/x/audio/voice_abc.wav"})
    assert slot["voice_path"] == "C:/x/audio/voice_abc.wav"


def test_normalize_slot_generuje_uid_ked_chyba():
    # Bez uid by sa mena nahravok krizili medzi profilmi (B1). normalize ho
    # musi doplnit - neprazdny retazec.
    slot = normalize_slot({})
    assert isinstance(slot["uid"], str) and slot["uid"]


def test_normalize_slot_zachova_existujuce_uid():
    # Raz pridelene uid musi zostat stabilne, inak by sa odkaz na nahravku
    # rozpadol pri kazdom nacitani.
    slot = normalize_slot({"uid": "trvale123"})
    assert slot["uid"] == "trvale123"


def test_normalize_slot_dve_prazdne_dostanu_rozne_uid():
    # Dva cerstve sloty nesmu dostat rovnake uid (inak by zdielali subor).
    a = normalize_slot({})
    b = normalize_slot({})
    assert a["uid"] != b["uid"]


# --------------------------------------------------------------------------
# normalize_overlay_config
# --------------------------------------------------------------------------

def test_normalize_overlay_config_defaults_when_not_dict():
    """Rozbity zapis -> vizual ZAPNUTY.

    Do 19. 9. tu bolo `is False`. Vyzeralo to nevinne, ale znamenalo to, ze
    appka bez zapnuteho vizualu nepusti ziadnu hlasku (`app._cue_can_fire`),
    takze chybajuci alebo rozbity kluc ju umlcal natrvalo. Chybajuci zaznam
    znamena "nevieme", nie "hrac si to vypol".
    """
    cfg = normalize_overlay_config(None, 0)
    assert cfg["enabled"] is True
    assert cfg["scale"] == 1.0


def test_predvolene_vizualy_su_zapnute():
    """Cerstva instalacia sa MUSI vediet ozvat.

    `app._cue_can_fire` hlasku nepusti, kym nie je zapnuty aspon jeden
    in-game vizual. Kym boli predvolene vypnute, nova instalacia odohrala
    cely vecer a nepovedala ani slovo - automat sa natiahol a zakazdym po
    90 sekundach ticho vypadol.
    """
    cfgs = default_overlay_configs()
    assert len(cfgs) == 4
    assert all(c["enabled"] for c in cfgs), "appka by bola po instalacii nema"


def test_normalize_overlay_config_clamps_scale_and_position():
    cfg = normalize_overlay_config({"enabled": True, "scale": 99, "pos_x": -5, "pos_y": 999}, 0)
    assert cfg["enabled"] is True
    assert 0.5 <= cfg["scale"] <= 2.0
    assert 0.0 <= cfg["pos_x"] <= 100.0
    assert 0.0 <= cfg["pos_y"] <= 100.0


# POZN: tu bol `test_normalize_dojo_intensity_clamps_and_defaults` -
# odstraneny spolu s `normalize_dojo_intensity()` v settings_model, ked
# zmizol fotopas nad titulkovou listou aj jeho posuvnik v Nastaveniach.


# --------------------------------------------------------------------------
# Vybratelne statistiky na Dnes - ukladanie/nacitanie vyberu
# --------------------------------------------------------------------------

def test_normalize_dashboard_stats_defaults_when_not_a_list():
    assert normalize_dashboard_stats(None) == list(DEFAULT_DASHBOARD_STATS)
    assert normalize_dashboard_stats("nezmysel") == list(DEFAULT_DASHBOARD_STATS)
    assert normalize_dashboard_stats([]) == list(DEFAULT_DASHBOARD_STATS)


def test_normalize_dashboard_stats_keeps_order_drops_unknown_and_dupes():
    out = normalize_dashboard_stats(["peak", "week", "peak", "not_a_real_id", "avg"])
    assert out == ["peak", "week", "avg"]


def test_normalize_dashboard_stats_round_trip_all_known_ids():
    assert normalize_dashboard_stats(list(DASHBOARD_STAT_IDS)) == list(DASHBOARD_STAT_IDS)


# ---------------------------------------------------------------------------
# sekcia "O appke" — odkazy na autora
# ---------------------------------------------------------------------------

def test_odkazy_na_komunitu_su_pouzitelne():
    """Odkazy idú do sveta, takže sa nesmú rozbiť ticho."""
    import guide_content
    odkazy = guide_content.COMMUNITY_LINKS
    assert len(odkazy) >= 3
    mena = [n for n, _ in odkazy]
    assert len(set(mena)) == len(mena), "duplicitný názov: %s" % mena
    for nazov, url in odkazy:
        assert nazov.strip(), odkazy
        assert url.startswith("https://"), url      # nikdy http
        assert " " not in url, url


def test_v_odkazoch_su_vsetky_platformy():
    import guide_content
    domeny = " ".join(u for _, u in guide_content.COMMUNITY_LINKS)
    for domena in ("twitch.tv", "youtube.com", "kick.com"):
        assert domena in domeny, domena


def test_discord_v_appke_nie_je():
    """Na hlásenie chýb a spoluprácu je GitHub, nie Discord.

    Diskusia na GitHube ostáva verejná, dohľadateľná a viazaná na kód.
    Navyše pozvánka na Discord expiruje a po expirácii prestane fungovať
    všetkým, čo si appku už stiahli — bez toho, aby sa to autor dozvedel.
    """
    import guide_content
    domeny = " ".join(u for _, u in guide_content.COMMUNITY_LINKS).lower()
    assert "discord" not in domeny


def test_about_hovori_o_licencii_pravdivo():
    """GPLv3 predaj NEZAKAZUJE — zakazuje zavretie.

    Text v „O appke“ je verejné vyhlásenie o licencii a nesmie tvrdiť niečo
    iné než samotná licencia (GPLv3) a LICENSE-DESIGN.md.
    """
    import i18n
    for jazyk in ("sk", "en"):
        telo = i18n.tr_lang(jazyk, "about.body")
        assert "GPLv3" in telo, jazyk
        # sľub o otvorenosti musí byť sprevádzaný povinnosťou odovzdať zdroj
        assert ("zdrojový kód" in telo or "source" in telo), jazyk


def test_about_priznava_ako_appka_vznikla():
    """Autor chcel mať výslovne napísané, že to je vibe coded a že nie je
    programátor. Je to jeho rozhodnutie a nemá z textu vypadnúť."""
    import i18n
    assert "vibe cod" in i18n.tr_lang("sk", "about.body").lower()
    assert "vibe cod" in i18n.tr_lang("en", "about.body").lower()


def test_appka_vystupuje_iba_ako_dandurfin():
    """Autor chce v celej appke vystupovať len pod menom Dandurfin.

    Kontroluje sa všetko, čo uvidí používateľ: text v „O appke“ aj metadáta
    exe, ktoré Windows ukáže vo Vlastnostiach.
    """
    import i18n
    import io
    import os
    for jazyk in ("sk", "en"):
        assert "Dandurfin" in i18n.tr_lang(jazyk, "about.lead"), jazyk
        assert "Dandurfin" in i18n.tr_lang(jazyk, "about.copyright"), jazyk
    meta = io.open(os.path.join(os.path.dirname(__file__), "..",
                                "version_info.txt"), encoding="utf-8").read()
    assert "Dandurfin" in meta


def test_copyright_je_v_appke_vidiet():
    """GPLv3 odporúča, aby interaktívny program vypísal krátke oznámenie
    o autorstve a záruke — a hlavne je to sľub hráčovi, pod čím appku dostal."""
    import i18n
    for jazyk in ("sk", "en"):
        t = i18n.tr_lang(jazyk, "about.copyright")
        assert "©" in t and "GPLv3" in t, jazyk
        assert ("záruky" in t or "warranty" in t), jazyk


def test_nazov_appky_je_holy_zanshin():
    """„DojoSync" nič nehovorilo. Zrozumiteľnosť nesie veta vedľa mena."""
    import paths
    assert paths.APP_NAME == "Zanshin"
    # a starý názov musí ostať v migrácii, inak nainštalovanej appke
    # zmiznú dáta — `data_dir()` ich hľadá pod APP_NAME
    assert "Zanshin DojoSync" in paths.LEGACY_APP_NAMES


def test_licencia_je_vidiet_v_titulnej_liste():
    """Appka tvrdí, že je slobodná — nech to stojí tam, kde to vidno vždy.

    Je to to isté tvrdenie ako „všetko ostáva u teba": buď je vidieť stále,
    alebo mu netreba veriť.
    """
    import app
    assert app.LICENCIA == "GPLv3"
    import inspect
    telo = inspect.getsource(app.DandurfApp._build_ui)
    assert "licence=LICENCIA" in telo


def test_subor_LICENSE_existuje_a_je_cely():
    """Bez neho platí podľa autorského práva „všetky práva vyhradené“ —
    teda presný opak toho, čo appka o sebe tvrdí v lište aj v „O appke“."""
    import io
    import os
    cesta = os.path.join(os.path.dirname(__file__), "..", "LICENSE")
    assert os.path.exists(cesta), "LICENSE chýba"
    t = io.open(cesta, encoding="utf-8").read()
    # doslovný text FSF má 674 riadkov; kontrolujeme kotvy, nie dĺžku
    for kus in ("GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007",
                "TERMS AND CONDITIONS",
                "How to Apply These Terms to Your New Programs"):
        assert kus in t, kus
