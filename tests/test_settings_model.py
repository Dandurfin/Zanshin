"""Tests for settings_model.py - pure functions, no UI/IO (clamp/normalising).

Running:  pytest tests/ -v
(Needs only 'pytest' on top - `pip install pytest`. The project's other
dependencies (customtkinter, pygame...) are not needed when importing
settings_model.py, since the module is purely data.)
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
    # via a float() intermediate step, so "7.9" is truncated to 7, not
    # rounded to 8
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
    assert optional_cooldown(9999) == 600.0  # upper cap according to settings_model
    assert optional_cooldown(-5) == 0.0


# --------------------------------------------------------------------------
# normalize_slot - the most important function: every loaded/imported
# slot (even from an old version of the app) goes through this.
# --------------------------------------------------------------------------

def test_normalize_slot_empty_dict_has_all_default_keys():
    slot = normalize_slot({})
    assert set(slot.keys()) == set(DEFAULT_SLOT.keys())


def test_normalize_slot_none_or_garbage_input_still_returns_valid_slot():
    # normalize_slot must survive even completely nonsensical input (e.g.
    # from a damaged/hand-edited JSON) - it always returns a valid slot dict.
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
    # the old schema (Dandurf 2.0) used mode="audio" instead of "sfx"
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
    # voice_path (own voice recording) - the same safeguard as audio_path.
    slot = normalize_slot({"voice_path": None})
    assert slot["voice_path"] == ""


def test_normalize_slot_voice_path_preserved():
    slot = normalize_slot({"voice_path": "C:/x/audio/voice_abc.wav"})
    assert slot["voice_path"] == "C:/x/audio/voice_abc.wav"


def test_normalize_slot_generuje_uid_ked_chyba():
    # Without a uid the recording names would clash between profiles (B1).
    # normalize has to fill it in - a non-empty string.
    slot = normalize_slot({})
    assert isinstance(slot["uid"], str) and slot["uid"]


def test_normalize_slot_zachova_existujuce_uid():
    # A uid once assigned must stay stable, otherwise the link to the
    # recording would fall apart on every load.
    slot = normalize_slot({"uid": "trvale123"})
    assert slot["uid"] == "trvale123"


def test_normalize_slot_dve_prazdne_dostanu_rozne_uid():
    # Two fresh slots must not get the same uid (or they would share a file).
    a = normalize_slot({})
    b = normalize_slot({})
    assert a["uid"] != b["uid"]


# --------------------------------------------------------------------------
# normalize_overlay_config
# --------------------------------------------------------------------------

def test_normalize_overlay_config_defaults_when_not_dict():
    """Broken entry -> visual ON.

    Until 19. 9. this said `is False`. It looked innocent, but it meant
    that the app without an enabled visual lets no cue through
    (`app._cue_can_fire`), so a missing or broken key silenced it for
    good. A missing entry means "we don't know", not "the player turned
    it off".
    """
    cfg = normalize_overlay_config(None, 0)
    assert cfg["enabled"] is True
    assert cfg["scale"] == 1.0


def test_predvolene_vizualy_su_zapnute():
    """A fresh installation MUST be able to speak up.

    `app._cue_can_fire` does not let a cue through until at least one
    in-game visual is enabled. While they were off by default, a new
    installation played through a whole evening and did not say a word -
    the state machine wound up and every time quietly dropped out after
    90 seconds.
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


# NOTE: here used to be
# `test_normalize_dojo_intensity_clamps_and_defaults` - removed together
# with `normalize_dojo_intensity()` in settings_model, when the photo band
# above the title bar and its slider in Settings disappeared.


# --------------------------------------------------------------------------
# Selectable stats on Today - saving/loading the selection
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
# the "About" section — links to the author
# ---------------------------------------------------------------------------

def test_odkazy_na_komunitu_su_pouzitelne():
    """The links go out into the world, so they must not break silently."""
    import guide_content
    odkazy = guide_content.COMMUNITY_LINKS
    assert len(odkazy) >= 3
    mena = [n for n, _ in odkazy]
    assert len(set(mena)) == len(mena), "duplicitný názov: %s" % mena
    for nazov, url in odkazy:
        assert nazov.strip(), odkazy
        assert url.startswith("https://"), url      # never http
        assert " " not in url, url


def test_v_odkazoch_su_vsetky_platformy():
    import guide_content
    domeny = " ".join(u for _, u in guide_content.COMMUNITY_LINKS)
    for domena in ("twitch.tv", "youtube.com", "kick.com"):
        assert domena in domeny, domena


def test_discord_v_appke_nie_je():
    """Bug reports and collaboration go to GitHub, not Discord.

    A discussion on GitHub stays public, searchable and tied to the code.
    Also, a Discord invite expires, and after it expires it stops working
    for everyone who has already downloaded the app — without the author
    ever finding out.
    """
    import guide_content
    domeny = " ".join(u for _, u in guide_content.COMMUNITY_LINKS).lower()
    assert "discord" not in domeny


def test_about_hovori_o_licencii_pravdivo():
    """GPLv3 does NOT FORBID selling — it forbids closing.

    The text in "About" is a public statement about the licence and must
    not claim anything other than the licence itself (GPLv3) and
    LICENSE-DESIGN.md.
    """
    import i18n
    for jazyk in ("sk", "en"):
        telo = i18n.tr_lang(jazyk, "about.body")
        assert "GPLv3" in telo, jazyk
        # a promise of openness must come with the obligation to hand over
        # the source
        assert ("zdrojový kód" in telo or "source" in telo), jazyk


def test_about_priznava_ako_appka_vznikla():
    """The author wanted it written explicitly that this is vibe coded and
    that he is not a programmer. It is his decision and it must not drop
    out of the text."""
    import i18n
    assert "vibe cod" in i18n.tr_lang("sk", "about.body").lower()
    assert "vibe cod" in i18n.tr_lang("en", "about.body").lower()


def test_appka_vystupuje_iba_ako_dandurfin():
    """The author wants to appear in the whole app only under the name
    Dandurfin.

    Everything the user will see is checked: the text in "About" and the
    exe metadata that Windows shows in Properties.
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
    """GPLv3 recommends that an interactive program prints a short notice
    about authorship and warranty — and above all it is a promise to the
    player about the terms the app came under."""
    import i18n
    for jazyk in ("sk", "en"):
        t = i18n.tr_lang(jazyk, "about.copyright")
        assert "©" in t and "GPLv3" in t, jazyk
        assert ("záruky" in t or "warranty" in t), jazyk


def test_nazov_appky_je_holy_zanshin():
    """„DojoSync" said nothing. The sentence by the name makes it clear."""
    import paths
    assert paths.APP_NAME == "Zanshin"
    # and the old name must stay in the migration, otherwise an installed
    # app loses its data — `data_dir()` looks for it under APP_NAME
    assert "Zanshin DojoSync" in paths.LEGACY_APP_NAMES


def test_licencia_je_vidiet_v_titulnej_liste():
    """The app claims to be free — let it stand where it is always visible.

    It is the same claim as "everything stays with you": either it is
    visible all the time, or there is no need to believe it.
    """
    import app
    assert app.LICENCIA == "GPLv3"
    import inspect
    telo = inspect.getsource(app.DandurfApp._build_ui)
    assert "licence=LICENCIA" in telo


def test_subor_LICENSE_existuje_a_je_cely():
    """Without it, copyright law means "all rights reserved" — i.e. exactly the
    opposite of what the app claims about itself in the title bar and in
    "About"."""
    import io
    import os
    cesta = os.path.join(os.path.dirname(__file__), "..", "LICENSE")
    assert os.path.exists(cesta), "LICENSE chýba"
    t = io.open(cesta, encoding="utf-8").read()
    # the verbatim FSF text has 674 lines; we check anchors, not the length
    for kus in ("GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007",
                "TERMS AND CONDITIONS",
                "How to Apply These Terms to Your New Programs"):
        assert kus in t, kus
