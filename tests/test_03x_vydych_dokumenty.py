# -*- coding: utf-8 -*-
"""The documents about the exhale with every cue (0.3.1) say what the code does.

The author's decision (16. 11. 2026): a long exhale is the one thing that
fits any moment, so by default every cue comes with it - the built-in words
ask for the exhale first ("Exhale, jaw", the breath cue "Long exhale"), the
grounding / jaw / grip & gaze pictures bring the breath ring along for one
exhale, the breath cue on its own breathes out -> in -> out, and the
grounding picture moved to the left middle. Old built-in words and an
untouched grounding position are changed once on load; the player's own
words and moved pictures stay.

0.3.1 is not released yet: CHANGELOG.md has a new top section "(not
released yet)" above the released 0.3, and the documents mark the new
behaviour "from 0.3.1". The version metadata and the 0.3 release
statements stay as they are until the release.

This test ties those sentences to the words in i18n, the numbers in
overlay.py and settings_model.py, the one-time flags in app_prefs.py and
the measurement in measure.py, so that a sentence like "16 s by default" or
"the chart puts cues from before and after together" does not stop being
true silently. The behaviour itself is tested in tests/test_cue_words.py
(words, migration) and tests/test_03x_vydych_vizual.py (pictures).
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import measure  # noqa: E402
import overlay  # noqa: E402
import settings_model as sm  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_metody, zdroj_suboru  # noqa: E402

ZMENY = "CHANGELOG.md"
AKO = "docs/HOW-IT-WORKS.md"
VYVOJ = "DEVELOPMENT.md"
NEVYDANA = "0.3.1"
VYDANA = "0.3"
KATEGORIE = ("grounding", "jaw", "release", "breath")
_VERZIA = r"\d+(?:\.\d+){1,3}"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain_text(text):
    return " ".join(text.split())


def _plain(meno):
    return _plain_text(_read(meno))


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis, uroven="## "):
    zaciatok = text.index("\n" + uroven + nadpis)
    koniec = re.search(r"\n#{2,%d} " % len(uroven.strip()), text[zaciatok + 1:])
    return text[zaciatok:zaciatok + 1 + koniec.start() if koniec else len(text)]


def _zmeny_031():
    """The 0.3.1 section of CHANGELOG, without line breaks."""
    return _plain_text(_sekcia(_read(ZMENY), "What %s changes" % NEVYDANA))


def _slovo(kategoria, jazyk="en"):
    return i18n.STRINGS["slot.default.%s" % kategoria][jazyk]


def _dych(rezim):
    """A breath ring (`overlay._SlotOverlay`) with the default lengths in the
    given showing mode - without Tk: only what `breath_phases` /
    `breath_state` read."""
    kruh = overlay._SlotOverlay.__new__(overlay._SlotOverlay)
    kruh.inhale_s = overlay._SlotOverlay.INHALE_S_DEFAULT
    kruh.exhale_s = overlay._SlotOverlay.EXHALE_S_DEFAULT
    kruh._test_mode = False
    kruh._breath_mode = rezim
    return kruh


# --------------------------------------------------------------------------
# CHANGELOG: 0.3.1 on top, not released yet; 0.3 stays the release
# --------------------------------------------------------------------------

def test_changelog_031_je_navrchu_a_nevydana():
    c = _read(ZMENY)
    nadpisy = re.findall(r"^## What (%s) " % _VERZIA, c, re.M)
    assert nadpisy[:3] == [NEVYDANA, VYDANA, "0.2.1"], nadpisy
    assert "\n## What %s changes (not released yet)\n" % NEVYDANA in c
    # the released 0.3 keeps its heading (README links to its anchor)
    assert "\n## What %s changes\n" % VYDANA in c
    assert "](CHANGELOG.md#what-03-changes)" in _read("README.md")
    uvod = _plain(ZMENY)[:600]
    assert ("What each version changed, newest first: 0.3.1 (in the code "
            "here, not released yet), 0.3, 0.2.1, and what 0.1 got wrong.") in uvod
    assert ("These are in the code here, not in a release yet: the 0.3 ZIP "
            "doesn't have them.") in _zmeny_031()


def test_vydana_verzia_ostava_03():
    """The same rule as `_vydana_verzia` in test_version_sync.py and
    test_dokumenty_02.py: the released version is the app version, unless
    CHANGELOG's first section is that version "(not released yet)" - then
    it is the next heading. Today the app still says 0.3 (the metadata
    changes only at the release), so either way it is 0.3, which KNOWN_ISSUES
    and the README's ZIP name must keep naming."""
    verzia = re.search(_VERZIA, i18n.STRINGS["app.version_short"]["en"]).group(0)
    c = _read(ZMENY)
    nadpisy = re.findall(r"^## What (%s) " % _VERZIA, c, re.M)
    if "\n## What %s changes (not released yet)\n" % verzia in c:
        assert nadpisy[0] == verzia
        vydana = nadpisy[1]
    else:
        vydana = verzia
    assert vydana == VYDANA
    assert _read("KNOWN_ISSUES.md").splitlines()[0].endswith("alpha %s" % VYDANA)
    assert "Zanshin-%s-windows.zip" % VYDANA in _read("README.md")
    # the unreleased section is the newer one
    assert tuple(map(int, NEVYDANA.split("."))) > tuple(map(int, vydana.split(".")))


# --------------------------------------------------------------------------
# The words: CHANGELOG and HOW-IT-WORKS name them as i18n has them
# --------------------------------------------------------------------------

def test_slova_v_dokumentoch_su_z_i18n():
    slova = [_slovo(k) for k in KATEGORIE]
    assert slova == ["Exhale, grounded", "Exhale, jaw", "Exhale, release",
                     "Long exhale"]
    # Slovak and Czech use the same English words ("these English words too")
    for jazyk in ("sk", "cs"):
        assert [_slovo(k, jazyk) for k in KATEGORIE] == slova, jazyk
    # "the other languages say the same in their own words"
    for jazyk in i18n.LANGUAGES:
        if jazyk not in ("en", "sk", "cs"):
            for k in KATEGORIE:
                assert _slovo(k, jazyk) != _slovo(k), (jazyk, k)
    zmeny = _zmeny_031()
    for slovo in slova[:3]:
        assert "*%s*" % slovo in zmeny, slovo
    assert "for the breath cue, *%s*" % slova[3] in zmeny
    assert "(Slovak and Czech use these English words too;" in zmeny
    jazyky = _plain_text(_sekcia(_read(AKO), "Voices and languages"))
    assert ("From 0.3.1 every built-in word asks for the exhale first: *%s*, "
            "*%s* and *%s*, and the breath cue says *%s*." % tuple(slova)) in jazyky
    assert "Those are the English words, which Slovak and Czech use too;" in jazyky


def test_stare_slova_raz_pri_nacitani_vlastne_ostanu():
    """"The first time 0.3.1 loads your settings, a cue that still has its
    built-in word from an earlier version gets the new one, in the same
    language ... Words you wrote yourself stay exactly as they are, ... and
    a profile code from 0.3 imported later keeps its old words."""
    sloty = [{"text": t} for t in ("Grounded", "Jaw", "my own words", "Breathe")]
    sm.migrate_profile_texts(sloty)
    assert [s["text"] for s in sloty] == [
        _slovo("grounding"), _slovo("jaw"), "my own words", _slovo("breath")]
    # the same language: a Japanese profile gets the Japanese words
    ja = [{"text": "重心"}, {"text": "顎"}]
    sm.migrate_profile_texts(ja)
    assert [s["text"] for s in ja] == [_slovo("grounding", "ja"), _slovo("jaw", "ja")]
    # ONCE: only while the settings file has no flag, which saving writes
    nacitaj, uloz = zdroj_metody("load_settings"), zdroj_metody("save_settings")
    assert 'loaded.get("exhale_words")' in nacitaj
    assert '"exhale_words": True' in uloz
    # only on load - importing a profile code does not change its words
    assert zdroj_appky().count("migrate_profile_texts(") == 1
    assert "migrate_profile_texts(" in nacitaj
    zmeny = _zmeny_031()
    assert ("The first time 0.3.1 loads your settings, a cue that still has its "
            "built-in word from an earlier version gets the new one, in the same "
            "language,") in zmeny
    assert "Words you wrote yourself stay exactly as they are," in zmeny
    assert "a profile code from 0.3 imported later keeps its old words." in zmeny
    assert ("The first time 0.3.1 loads your settings, a cue that still has its "
            "built-in word from an earlier version gets the new one in the same "
            "language; words you wrote yourself stay as they are.") in _plain(AKO)


# --------------------------------------------------------------------------
# The pictures: names from the UI, numbers from overlay.py
# --------------------------------------------------------------------------

def test_nazvy_z_appky():
    zmeny = _zmeny_031()
    obrazky = _plain_text(_sekcia(_read(AKO), "In-game pictures and the heart-rate panel"))
    dlzka = _en("overlay.breath_exhale")
    assert dlzka.endswith(" (s)")
    dlzka = dlzka[:-len(" (s)")]                                   # Exhale length
    for text in (zmeny, obrazky):
        assert "*%s*" % _en("overlay.caption.exhale") in text      # EXHALE
        assert "its *%s* in *%s*" % (dlzka, _en("overlay.dialog_title")) in text
        assert "*%s* on a cue" % _en("common.test") in text        # ▶ Test
        assert "*%s*, for dragging one picture into place, shows only that " \
               "picture." % _en("overlay.test") in text            # ▶ Show
    # the exhale length is set on the breath picture in In-game pictures
    assert 'tr("overlay.breath_exhale")' in zdroj_suboru("ui_dialogs.py")
    # ▶ Test on the card -> fire_slot -> the same trigger() as a real cue
    # (so the ring comes along); ▶ Show -> the drag test (only that picture)
    assert '(tr("common.test"), self.test, False)' in zdroj_suboru("ui_dialogs.py")
    assert "self.overlay_manager.trigger(i)" in zdroj_metody("fire_slot")
    assert 'tr("overlay.test"), height=32' in zdroj_suboru("ui_dialogs.py")
    assert "self.overlay_manager.test(index)" in zdroj_metody("toggle_overlay_test")


def test_cisla_dychu_z_overlay():
    trieda = overlay._SlotOverlay
    assert trieda.EXHALE_S_DEFAULT == sm.DEFAULT_BREATH_EXHALE_S == 6.0
    assert trieda.INHALE_S_DEFAULT == sm.DEFAULT_BREATH_INHALE_S == 4.0
    # the companion: one exhale as long as the exhale length, full -> empty
    # (`hud_paint.render_breath`: an exhale at 0 is the full ring, at 1 the
    # empty one)
    vydych = _dych(trieda.BREATH_EXHALE)
    assert vydych.breath_phases() == ((False, 6.0),)
    assert vydych.breath_state(0.0) == (False, 0.0)
    assert vydych.breath_state(6.0) == (False, 1.0)
    # the breath cue: out, in, out, 16 s; until 0.3 two breaths in and out,
    # 20 s
    dych = _dych(trieda.BREATH_FULL)
    assert [nadych for nadych, _s in dych.breath_phases()] == [False, True, False]
    assert dych.breath_duration() == 16.0
    assert 2 * (trieda.INHALE_S_DEFAULT + trieda.EXHALE_S_DEFAULT) == 20.0
    zmeny = _zmeny_031()
    veta = ("(6 s by default), the ring going from full to empty with the caption "
            "*%s*, then it fades like the other pictures." % _en("overlay.caption.exhale"))
    assert veta in zmeny
    assert ("The breath cue itself starts with the exhale and ends breathed out: "
            "out, in, out (16 s by default; it was two breaths in and out, 20 s).") in zmeny
    obrazky = _plain_text(_sekcia(_read(AKO), "In-game pictures and the heart-rate panel"))
    assert "From 0.3.1, by default, every cue comes with a long exhale." in obrazky
    assert "**0.3.1:** by default every cue comes with it." in zmeny
    assert veta in obrazky
    assert ("The breath cue itself starts with the exhale and ends breathed out: "
            "out, in, out, 16 s by default.") in obrazky
    for text in (zmeny, obrazky):
        assert ("With the breath picture switched off, the other cues come "
                "without the ring; switching off only the breath cue keeps it.") in text
        assert "Picture-only cues show it too," in text


def test_kazda_hlaska_s_vydychom_len_predvolene():
    """"By default every cue comes with it": only the defaults promise it -
    every built-in word asks for the exhale and all four pictures (the
    breath ring too) start switched on. A player's own word or a switched
    off breath picture can leave a cue without it, so the sentence must not
    lose its "by default"."""
    for jazyk in ("en", "sk", "cs"):
        for k in KATEGORIE:
            assert "exhale" in _slovo(k, jazyk).casefold(), (jazyk, k)
    assert all(cfg["enabled"] for cfg in sm.default_overlay_configs())
    assert "not self.enabled" in zdroj_suboru("overlay.py").split(
        "def trigger_exhale(self):", 1)[1].split("\n    def ", 1)[0]


def test_vypnuta_hlaska_dychu_kruh_necha():
    """"switching off only the breath cue keeps it": the ring asks only the
    breath PICTURE (`overlay_configs[3]["enabled"]` ->
    `_SlotOverlay.enabled`), never the switch on the breath cue's card."""
    karta = zdroj_suboru("ui_dialogs.py").split("    def on_enabled_change(self):", 1)[1]
    karta = karta.split("\n    def ", 1)[0]
    assert "overlay" not in karta
    zapnute = re.findall(r"overlay_manager\.configure\([^)]*?enabled=([^,)]+)",
                         zdroj_appky())
    assert zapnute and all(v.strip() == 'cfg["enabled"]' for v in zapnute), zapnute


def test_ukotvenie_vlavo_v_strede():
    """"The grounding picture moved from the bottom centre, right under the
    ring, to the left middle, mirroring grip & gaze on the right"."""
    pozicie = sm.OVERLAY_DEFAULT_POS
    stare = sm.OVERLAY_OLD_GROUNDING_POS
    assert pozicie[0] == (14.0, 50.0)                    # left, halfway down
    assert pozicie[2] == (86.0, 50.0)                    # grip & gaze, right
    assert 100.0 - pozicie[0][0] == pozicie[2][0] and pozicie[0][1] == pozicie[2][1]
    # the old place: bottom centre, under the ring (the ring is at 50 % too,
    # higher up)
    assert stare == (50.0, 88.0)
    assert stare[0] == pozicie[3][0] == 50.0 and stare[1] > pozicie[3][1]
    # an untouched one moves, a dragged one stays
    cfgs = sm.default_overlay_configs()
    cfgs[0]["pos_x"], cfgs[0]["pos_y"] = stare
    assert sm.move_old_grounding_position(cfgs) is True
    assert (cfgs[0]["pos_x"], cfgs[0]["pos_y"]) == pozicie[0]
    cfgs[0]["pos_x"], cfgs[0]["pos_y"] = (50.0, 87.0)
    assert sm.move_old_grounding_position(cfgs) is False
    # once: only while the settings file has no flag, which saving writes
    assert 'loaded.get("grounding_moved")' in zdroj_metody("load_settings")
    assert '"grounding_moved": True' in zdroj_metody("save_settings")
    zmeny = _zmeny_031()
    assert ("The grounding picture moved from the bottom centre, right under the "
            "ring, to the left middle, mirroring grip & gaze on the right.") in zmeny
    assert ("a grounding picture still at its old default place moves to the new "
            "one.") in zmeny
    assert "a picture you moved stays where you put it," in zmeny
    assert ("By default the grounding picture now sits on the left, halfway down, "
            "mirroring grip & gaze on the right; one still at its old default "
            "place (bottom centre, under the ring) moves there the first time "
            "0.3.1 loads your settings, and one you moved stays where you put "
            "it.") in _plain(AKO)


# --------------------------------------------------------------------------
# The cue chart puts cues from before and after the change together
# --------------------------------------------------------------------------

def _okno(pred, po):
    return {"valid": True, "arm": "voice", "delivery": "pause", "world": "play",
            "audible": True, "pre_bpm": pred, "post_bpm": po,
            "category": "grounding", "params": dict(trigger.default_params())}


def test_graf_spaja_hlasky_pred_a_po_zmene():
    """CHANGELOG and KNOWN_ISSUES say so while it holds: the windows carry no
    marker of the exhale (unlike the gate, `params.brana`, which does keep
    older windows apart), so `measure.by_category` - History's chart -
    counts a 0.3 cue and a 0.3.1 cue of the same category together. If that
    ever changes, the sentences go."""
    assert _en("history.effect_title") == "How your pulse moved after a cue"
    assert 'tr("history.effect_title")' in zdroj_suboru("app_history.py")
    assert "measure.by_category(okna)" in zdroj_metody("_refresh_cue_effect")
    kluce = " ".join(trigger.default_params()).lower()
    assert "exhale" not in kluce and "vydych" not in kluce
    # a window from 0.3 and one from 0.3.1 look the same - one category, n=2
    podla = measure.by_category([_okno(100.0, 96.0), _okno(98.0, 97.0)])
    assert podla["grounding"]["n"] == 2
    zmeny = _zmeny_031()
    assert ("History's *%s* doesn't tell cues from before and after this change "
            "apart, so a category's number mixes the two."
            % _en("history.effect_title")) in zmeny
    assert ("0.3.1 (in the code here, not in a release yet) adds an exhale to the "
            "cues, and the cue chart puts cues from before and after that change "
            "together, so a category's number mixes the two.") in _plain("KNOWN_ISSUES.md")


# --------------------------------------------------------------------------
# The natural voice, the "from 0.3.1" marker, DEVELOPMENT
# --------------------------------------------------------------------------

def test_hlas_privacy_a_znacka_031():
    # the new words are lines not in the cache yet: prepared (and sent) like
    # any changed wording, the Windows voice until then
    assert ("With the natural voice the new words are new lines: they are "
            "prepared, and sent to Microsoft, like any changed wording, and until "
            "a line is ready that cue plays in the Windows voice.") in _zmeny_031()
    assert ("only for lines that aren't in the cache yet — at every start (for "
            "example a line still waiting when you quit, or, from 0.3.1, the new "
            "built-in words with the exhale), after you change a") in _plain("PRIVACY.md")
    assert ("Where something is new in 0.3, it says *from 0.3*; where it is in the "
            "code here but not in a release yet, it says *from 0.3.1*.") in _plain(AKO)
    # KNOWN_ISSUES is still the list for the released 0.3
    assert "not released yet" not in _read("KNOWN_ISSUES.md")


def test_vyvoj_opisuje_jednorazovu_zmenu_slov():
    v = _plain(VYVOJ)
    assert "**The built-in cue words** (`slot.default.*`)" in v
    assert "`tests/test_cue_words.py` keeps them free of \"relax\" and \"calm down\"" in v
    assert os.path.exists(os.path.join(ROOT, "tests", "test_cue_words.py"))
    assert "`settings_model._STARE_PREDVOLENE_SLOVA` lists the old one" in v
    assert hasattr(sm, "_STARE_PREDVOLENE_SLOVA")
    assert ("(`load_settings` checks the `exhale_words` flag that `save_settings` "
            "writes), so changing the words again needs a new flag as well.") in v
