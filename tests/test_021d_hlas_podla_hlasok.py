# -*- coding: utf-8 -*-
"""Voice by the language of the CUES, not the UI language (0.2.1d).

Until 0.2.1d `on_lang_switch` called `suggested_voice(code, ...)`: a player
with the default voice who switched the app to ja/zh/ru/bg got that
language's voice. But the cue texts of existing profiles are not
translated on a switch (the built-in words are taken when the profile is
created, for sk/cs English ones) - so a Japanese voice read the English
"Grounded" and could mangle it or stay silent. That is exactly what
VOICE_HINTS was meant to prevent.

Now (`app_prefs._hlas_k_hlaskam`, `settings_model.jazyky_hlasok`):
  * switching the language changes the voice only when the speaking cues
    of the active profile are the built-in words of the new language,
  * a new profile (manual or an auto-profile for a game) - its words are
    in the app's language - gets that language's voice,
  * a voice other than the default is never changed, not even back,
  * custom or mixed texts -> the voice stays.
"""
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402
from settings_model import (DEFAULT_EDGE_VOICE, ENGINE_EDGE, MODE_SFX,  # noqa: E402
                            VOICE_HINTS, default_slots, jazyky_hlasok,
                            normalize_slot)

SONIA = DEFAULT_EDGE_VOICE
NANAMI = VOICE_HINTS["ja"]
GUY = "en-US-GuyNeural"
ANGLICKE = {"sk", "en", "cs"}


@pytest.fixture(autouse=True)
def _jazyk_spat():
    """`on_lang_switch` and `default_slots` use the global i18n language."""
    povodny = i18n._lang["code"]
    yield
    i18n.set_lang(povodny)


def _sloty(jazyk):
    """The four built-in cues of a profile created in the language `jazyk`."""
    povodny = i18n._lang["code"]
    i18n.set_lang(jazyk)
    try:
        return [normalize_slot(s) for s in default_slots()]
    finally:
        i18n.set_lang(povodny)


def _label(kod):
    from app_spolocne import LANG_NATIVE_LABELS
    return LANG_NATIVE_LABELS[kod]


def _appka(monkeypatch, lang, hlas, sloty):
    """Real `on_lang_switch`, `_hlas_k_hlaskam`; rest of the window is fake.
    It records the voice at the moment of saving, preparation and
    restoring the voice selection."""
    import app as app_mod
    import ui_kit
    monkeypatch.setattr(ui_kit, "freeze_repaint", lambda *x: None)
    D = app_mod.DandurfApp
    a = types.SimpleNamespace(lang=lang, edge_voice_id=hlas, engine=ENGINE_EDGE,
                              listening=False, ulozene=[], priprava=[], vyber=[])
    a.slot_dicts = lambda: [dict(s) for s in sloty]
    a.save_settings = lambda: a.ulozene.append(a.edge_voice_id)
    a.pregenerate = lambda: a.priprava.append(a.edge_voice_id)
    a.refresh_voice_box = lambda: a.vyber.append(a.edge_voice_id)
    a.root = types.SimpleNamespace(update_idletasks=lambda: None)
    for meno in ("_build_ui", "refresh_edge_banner", "_load_edge_voices",
                 "refresh_slot_summaries", "refresh_hr_status_label",
                 "_apply_listening_visuals", "_apply_overlay_labels",
                 "_apply_hud_labels", "log", "_refresh_guide_panel_theme"):
        setattr(a, meno, lambda *x, **k: None)
    for meno in ("on_lang_switch", "_hlas_k_hlaskam"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    return a


# --------------------------------------------------------------------------
# jazyky_hlasok - which language the cues are in
# --------------------------------------------------------------------------

def test_vstavane_slova_kazdeho_jazyka_sa_poznaju():
    for jazyk in i18n.LANGUAGES:
        assert jazyk in jazyky_hlasok(_sloty(jazyk)), jazyk


def test_anglicke_slova_patria_sk_en_cs_a_ziadnemu_jazyku_s_navrhom():
    jazyky = jazyky_hlasok(_sloty("en"))
    assert jazyky == ANGLICKE
    assert not jazyky & set(VOICE_HINTS)
    assert jazyky_hlasok(_sloty("sk")) == jazyky_hlasok(_sloty("cs")) == ANGLICKE


def test_jazyky_s_navrhom_sa_neprekryvaju():
    for jazyk in VOICE_HINTS:
        assert jazyky_hlasok(_sloty(jazyk)) == {jazyk}, jazyk


def test_rata_sa_len_hlaska_ktoru_spolocny_hlas_cita():
    sloty = _sloty("ja")
    sloty[0].update(text="Moje slovo", enabled=False)       # disabled
    sloty[1].update(text="Moje slovo", mode=MODE_SFX)       # sound without words
    sloty[2].update(text="Moje slovo", voice_edge=GUY)      # the slot's own voice
    sloty.append(normalize_slot({"text": "Navyse z 0.1"}))  # slot 4+
    assert jazyky_hlasok(sloty) == {"ja", "zh"}             # only 呼吸 remained


def test_vlastne_ci_zmiesane_slova_nemaju_jazyk():
    sloty = _sloty("ja")
    sloty[0]["text"] = "足"                                 # overwritten word
    assert jazyky_hlasok(sloty) == set()
    zmiesane = _sloty("ja")[:2] + _sloty("en")[2:]
    assert jazyky_hlasok(zmiesane) == set()
    ticho = [dict(s, enabled=False) for s in _sloty("ja")]
    assert jazyky_hlasok(ticho) == set()
    assert jazyky_hlasok([]) == set()


def test_velkost_pismen_a_medzery_nevadia():
    sloty = _sloty("en")
    sloty[0]["text"] = "  grounded "
    assert jazyky_hlasok(sloty) == ANGLICKE


# --------------------------------------------------------------------------
# Switching the language
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jazyk", sorted(VOICE_HINTS))
@pytest.mark.parametrize("z", ["en", "sk", "cs"])
def test_prepnutie_s_anglickymi_hlaskami_necha_hlas(monkeypatch, z, jazyk):
    """That bug: Nanami/Xiaoxiao/... would read the English "Grounded"."""
    a = _appka(monkeypatch, z, SONIA, _sloty(z))
    a.on_lang_switch(_label(jazyk))
    assert a.lang == jazyk
    assert a.edge_voice_id == SONIA
    assert a.ulozene == [SONIA]
    assert a.priprava == [SONIA], "priprava hlasok bezi ako doteraz"


@pytest.mark.parametrize("jazyk", sorted(VOICE_HINTS))
def test_prepnutie_k_hlaskam_v_tom_jazyku_da_hlas_jazyka(monkeypatch, jazyk):
    """A profile created in Japanese, the app in English in the meantime:
    going back to Japanese gives a voice that pronounces its words - saved
    and also used when preparing the cues."""
    a = _appka(monkeypatch, "en", SONIA, _sloty(jazyk))
    a.on_lang_switch(_label(jazyk))
    hlas = VOICE_HINTS[jazyk]
    assert a.edge_voice_id == hlas
    assert a.ulozene == [hlas]
    assert a.vyber == [hlas]
    assert a.priprava == [hlas]


def test_hlas_ktory_si_hrac_vybral_sa_neprepise(monkeypatch):
    a = _appka(monkeypatch, "en", GUY, _sloty("ja"))
    a.on_lang_switch(_label("ja"))
    assert a.edge_voice_id == GUY
    b = _appka(monkeypatch, "en", VOICE_HINTS["bg"], _sloty("ja"))
    b.on_lang_switch(_label("ja"))
    assert b.edge_voice_id == VOICE_HINTS["bg"]


def test_prepnutie_spat(monkeypatch):
    """ja -> en: Japanese cues stayed Japanese, so the Japanese voice stays.
    With the default voice nothing changes on the way back either, and
    going to ja again brings Nanami."""
    a = _appka(monkeypatch, "ja", NANAMI, _sloty("ja"))
    a.on_lang_switch(_label("en"))
    assert a.edge_voice_id == NANAMI

    b = _appka(monkeypatch, "ja", SONIA, _sloty("ja"))
    b.on_lang_switch(_label("en"))
    assert b.edge_voice_id == SONIA
    b.on_lang_switch(_label("ja"))
    assert b.edge_voice_id == NANAMI
    b.on_lang_switch(_label("sk"))
    assert b.edge_voice_id == NANAMI, "spat sa hlas nemeni"

    # The app does not change a voice other than the default even with
    # English words: it does not know whether the player chose it themselves
    # (a voice left over from an old switch they will pick again).
    c = _appka(monkeypatch, "ja", NANAMI, _sloty("en"))
    c.on_lang_switch(_label("en"))
    assert c.edge_voice_id == NANAMI


def test_prepisane_slova_hlas_nechaju(monkeypatch):
    sloty = _sloty("ja")
    sloty[1]["text"] = "歯"
    a = _appka(monkeypatch, "en", SONIA, sloty)
    a.on_lang_switch(_label("ja"))
    assert a.edge_voice_id == SONIA


def test_prepnutie_jazyka_neprepisuje_hlasky(monkeypatch):
    sloty = _sloty("en")
    a = _appka(monkeypatch, "en", SONIA, sloty)
    a.on_lang_switch(_label("ja"))
    assert [s["text"] for s in sloty] == [s["text"] for s in _sloty("en")]


# --------------------------------------------------------------------------
# New profile
# --------------------------------------------------------------------------

def _profilova(monkeypatch, lang, hlas):
    import app as app_mod
    D = app_mod.DandurfApp
    i18n.set_lang(lang)
    a = types.SimpleNamespace(
        lang=lang, edge_voice_id=hlas, listening=True,
        auto_profile_enabled=True, _auto_started_listening=False,
        profiles=[{"name": "Default", "slots": _sloty("en")}],
        active_profile_name="Default", ulozene=[], priprava=[], vyber=[],
        prepnute=[])
    a._sync_active_profile_slots = lambda: None
    a.rebuild_slots = lambda s: None
    a.refresh_profile_switch = lambda: None
    a.save_settings = lambda: a.ulozene.append(a.edge_voice_id)
    a.schedule_pregenerate = lambda *_: a.priprava.append(a.edge_voice_id)
    a.refresh_voice_box = lambda: a.vyber.append(a.edge_voice_id)
    a.log = lambda *x: None
    a.switch_profile = lambda meno: a.prepnute.append((meno, a.edge_voice_id))
    for meno in ("create_profile", "_handle_game_found", "_hlas_k_hlaskam"):
        setattr(a, meno, types.MethodType(getattr(D, meno), a))
    return a


@pytest.mark.parametrize("jazyk", sorted(VOICE_HINTS))
def test_novy_profil_v_jazyku_s_navrhom_dostane_jeho_hlas(monkeypatch, jazyk):
    a = _profilova(monkeypatch, jazyk, SONIA)
    a.create_profile("Novy")
    hlas = VOICE_HINTS[jazyk]
    assert a.edge_voice_id == hlas
    assert a.vyber == [hlas], "vyber hlasu ukazuje novy hlas"
    assert a.ulozene == [hlas], "novy hlas je ulozeny"
    assert a.priprava == [hlas], "priprava hlasok ide novym hlasom"


# Since 0.3 es/de/fr/pt also have a suggestion (their built-in words are
# not English) - only the languages with English built-in words were left
# without a suggestion.
@pytest.mark.parametrize("jazyk", ["sk", "en", "cs"])
def test_novy_profil_v_latinke_hlas_necha(monkeypatch, jazyk):
    a = _profilova(monkeypatch, jazyk, SONIA)
    a.create_profile("Novy")
    assert a.edge_voice_id == SONIA and a.vyber == []


def test_novy_profil_vlastny_hlas_neprepise(monkeypatch):
    a = _profilova(monkeypatch, "ja", GUY)
    a.create_profile("Novy")
    assert a.edge_voice_id == GUY and a.vyber == []


def test_auto_profil_pre_hru_dostane_hlas_ako_novy_profil(monkeypatch):
    """The auto-profile creates a profile with the built-in words the same
    way as `create_profile`. Saving and preparation are done by
    `switch_profile` - already with the new voice."""
    a = _profilova(monkeypatch, "ru", SONIA)
    a._handle_game_found("CS2")
    assert a.edge_voice_id == VOICE_HINTS["ru"]
    assert a.vyber == [VOICE_HINTS["ru"]]
    assert a.prepnute == [("CS2", VOICE_HINTS["ru"])]

    # A profile that already exists is not created - the voice does not change.
    b = _profilova(monkeypatch, "ru", SONIA)
    b.profiles.append({"name": "CS2", "slots": _sloty("en")})
    b._handle_game_found("CS2")
    assert b.edge_voice_id == SONIA and b.vyber == []


# --------------------------------------------------------------------------
# The documents say what the code does
# --------------------------------------------------------------------------

def _plain(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return " ".join(fh.read().split())


def test_readme_a_known_issues_popisuju_hlas_podla_slov():
    assert "self._hlas_k_hlaskam(self.slot_dicts())" in zdroj_metody("on_lang_switch")
    for metoda in ("create_profile", "_handle_game_found"):
        assert "self._hlas_k_hlaskam(new_slots)" in zdroj_metody(metoda), metoda

    # Since 0.3d the voice rules are in docs/HOW-IT-WORKS.md, not in the
    # README; "reminder" is "cue" in the documents, as in the app.
    readme = _plain("docs/HOW-IT-WORKS.md")
    assert ("which switch to a voice of their own while you're still on the "
            "default") not in readme
    assert ("get a voice of that language while you're still on the default "
            "voice: on a first start in that language, when a profile is "
            "created in it, or when you switch to it and the cues that "
            "speak in the profile you're in use its built-in words (not "
            "reworded ones)") in readme
    assert ("switching the language with English words keeps the English "
            "voice, and switching back doesn't undo a change") in readme
    assert "One voice reads all your profiles" in readme

    # Since 0.3 (batch 4) the version history is in CHANGELOG.md.
    k = _plain("CHANGELOG.md")
    opravy = k[k.index("## What 0.2.1 fixes"):k.index("## What 0.1 got wrong")]
    assert ("**Switching the language to Japanese, Chinese, Russian or "
            "Bulgarian also switched the natural voice to that language**") in opravy
    assert "the voice follows the words, not the menu" in opravy
    assert "A voice other than the default is never changed" in opravy

    # The line under the language picker stays true: cues are not translated.
    assert i18n.STRINGS["settings.language_sub"]["en"] == (
        "Cues you already have keep their wording.")
