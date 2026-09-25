# -*- coding: utf-8 -*-
"""Hlas podla jazyka HLASOK, nie jazyka rozhrania (0.2.1d).

Do 0.2.1d `on_lang_switch` volal `suggested_voice(code, ...)`: hrac s
predvolenym hlasom, ktory prepol appku do ja/zh/ru/bg, dostal hlas toho
jazyka. Lenze texty hlasok existujucich profilov sa pri prepnuti neprekladaju
(vstavane slova sa beru pri zalozeni profilu, pre sk/cs anglicke) - japonsky
hlas tak cital anglicke "Grounded" a mohol ho skomolit alebo mlcat. Presne
tomu mal VOICE_HINTS zabranit.

Teraz (`app_prefs._hlas_k_hlaskam`, `settings_model.jazyky_hlasok`):
  * prepnutie jazyka zmeni hlas len ked hovoriace hlasky aktivneho profilu
    su vstavane slova noveho jazyka,
  * novy profil (rucne aj auto-profil pre hru) - jeho slova su v jazyku
    appky - dostane hlas toho jazyka,
  * hlas iny nez predvoleny sa nemeni nikdy, ani spat,
  * vlastne ci zmiesane texty -> hlas ostava.
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
    """`on_lang_switch` aj `default_slots` pracuju s globalnym jazykom i18n."""
    povodny = i18n._lang["code"]
    yield
    i18n.set_lang(povodny)


def _sloty(jazyk):
    """Styri vstavane hlasky profilu zalozeneho v jazyku `jazyk`."""
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
    """Ozajstne `on_lang_switch` a `_hlas_k_hlaskam`, zvysok okna je atrapa.
    Zapisuje hlas v okamihu ulozenia, pripravy a obnovy vyberu hlasu."""
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
# jazyky_hlasok - v akom jazyku su hlasky
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
    sloty[0].update(text="Moje slovo", enabled=False)       # vypnuta
    sloty[1].update(text="Moje slovo", mode=MODE_SFX)       # zvuk bez slov
    sloty[2].update(text="Moje slovo", voice_edge=GUY)      # vlastny hlas slotu
    sloty.append(normalize_slot({"text": "Navyse z 0.1"}))  # slot 4+
    assert jazyky_hlasok(sloty) == {"ja", "zh"}             # zostal len 呼吸


def test_vlastne_ci_zmiesane_slova_nemaju_jazyk():
    sloty = _sloty("ja")
    sloty[0]["text"] = "足"                                 # prepisane slovo
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
# Prepnutie jazyka
# --------------------------------------------------------------------------

@pytest.mark.parametrize("jazyk", sorted(VOICE_HINTS))
@pytest.mark.parametrize("z", ["en", "sk", "cs"])
def test_prepnutie_s_anglickymi_hlaskami_necha_hlas(monkeypatch, z, jazyk):
    """Ten bug: anglicke "Grounded" by citala Nanami/Xiaoxiao/..."""
    a = _appka(monkeypatch, z, SONIA, _sloty(z))
    a.on_lang_switch(_label(jazyk))
    assert a.lang == jazyk
    assert a.edge_voice_id == SONIA
    assert a.ulozene == [SONIA]
    assert a.priprava == [SONIA], "priprava hlasok bezi ako doteraz"


@pytest.mark.parametrize("jazyk", sorted(VOICE_HINTS))
def test_prepnutie_k_hlaskam_v_tom_jazyku_da_hlas_jazyka(monkeypatch, jazyk):
    """Profil zalozeny v japoncine, appka medzitym v anglictine: navrat do
    japonciny da hlas, ktory jeho slova vyslovi - ulozeny aj pouzity pri
    priprave hlasok."""
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
    """ja -> en: japonske hlasky ostali japonske, takze japonsky hlas ostava.
    S predvolenym hlasom sa spat tiez nic nemeni a znova do ja pride Nanami."""
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

    # Hlas iny nez predvoleny appka nemeni ani pri anglickych slovach: nevie,
    # ci ho hrac vybral sam (hlas zo stareho prepnutia si vyberie znova).
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
# Novy profil
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


@pytest.mark.parametrize("jazyk", ["sk", "en", "cs", "de", "es", "fr", "pt"])
def test_novy_profil_v_latinke_hlas_necha(monkeypatch, jazyk):
    a = _profilova(monkeypatch, jazyk, SONIA)
    a.create_profile("Novy")
    assert a.edge_voice_id == SONIA and a.vyber == []


def test_novy_profil_vlastny_hlas_neprepise(monkeypatch):
    a = _profilova(monkeypatch, "ja", GUY)
    a.create_profile("Novy")
    assert a.edge_voice_id == GUY and a.vyber == []


def test_auto_profil_pre_hru_dostane_hlas_ako_novy_profil(monkeypatch):
    """Auto-profil zaklada profil so vstavanymi slovami rovnako ako
    `create_profile`. Ulozenie a pripravu robi `switch_profile` - uz s novym
    hlasom."""
    a = _profilova(monkeypatch, "ru", SONIA)
    a._handle_game_found("CS2")
    assert a.edge_voice_id == VOICE_HINTS["ru"]
    assert a.vyber == [VOICE_HINTS["ru"]]
    assert a.prepnute == [("CS2", VOICE_HINTS["ru"])]

    # Profil, ktory uz existuje, sa nezaklada - hlas sa nemeni.
    b = _profilova(monkeypatch, "ru", SONIA)
    b.profiles.append({"name": "CS2", "slots": _sloty("en")})
    b._handle_game_found("CS2")
    assert b.edge_voice_id == SONIA and b.vyber == []


# --------------------------------------------------------------------------
# Dokumenty hovoria to, co robi kod
# --------------------------------------------------------------------------

def _plain(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return " ".join(fh.read().split())


def test_readme_a_known_issues_popisuju_hlas_podla_slov():
    assert "self._hlas_k_hlaskam(self.slot_dicts())" in zdroj_metody("on_lang_switch")
    for metoda in ("create_profile", "_handle_game_found"):
        assert "self._hlas_k_hlaskam(new_slots)" in zdroj_metody(metoda), metoda

    readme = _plain("README.md")
    assert ("which switch to a voice of their own while you're still on the "
            "default") not in readme
    assert ("get a voice of that language while you're still on the default "
            "voice: on a first start in that language, when a profile is "
            "created in it, or when you switch to it and the reminders that "
            "speak in the profile you're in use its built-in words (not "
            "reworded ones)") in readme
    assert ("switching the language with English words keeps the English "
            "voice, and switching back doesn't undo a change") in readme
    assert "One voice reads all your profiles" in readme

    k = _plain("KNOWN_ISSUES.md")
    opravy = k[k.index("## What 0.2.1 fixes"):k.index("## What 0.1 got wrong")]
    assert ("**Switching the language to Japanese, Chinese, Russian or "
            "Bulgarian also switched the natural voice to that language**") in opravy
    assert "the voice follows the words, not the menu" in opravy
    assert "A voice other than the default is never changed" in opravy

    # Veta pod vyberom jazyka ostava pravdiva: hlasky sa neprekladaju.
    assert i18n.STRINGS["settings.language_sub"]["en"] == (
        "Cues you already have keep their wording.")
