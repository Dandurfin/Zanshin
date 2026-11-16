# -*- coding: utf-8 -*-
"""The documents about the breath ring at high heart rate (0.3.2) say what
the code does.

The author's decision (16. 11. 2026): the ring, first a side-branch
experiment, stays as a normal feature, off by default. While Zanshin is
watching and the smoothed heart rate (`HeartStats.display_bpm`) is above the
player's own limit (80-200 BPM, default 110), slot 3's breath ring breathes
in a loop; once the rate drops at least `KRUH_TEP_REZERVA_BPM` (3) below
the limit, it finishes breathed out and fades. No other cue comes
meanwhile, and a cue's measurement window the ring reaches into is not
counted. "Not now" pressed while it shows does not count against the last
cue, and the line after a session names the ring when it held back every
ready cue and no reason the line checks first explains the silence.

0.3.2 is the release that brought it: CHANGELOG.md's top section "What 0.3.2
changes" (released, no marker - the release itself is pinned in
tests/test_03x_vydych_dokumenty.py, as 0.3.1 was), the README's "What it
does", KNOWN_ISSUES.md and docs/HOW-IT-WORKS.md describe it, and
docs/PRIOR_ART.md (with the README's "Similar projects") no longer sets
Zanshin apart from Cardia and Pauser as if it never reacted to a fixed
number. This test ties
those sentences to the labels in i18n, the numbers in settings_model.py,
hr_stats.py, measure.py, trigger.py and overlay.py, and to the app's source
(`_tick_high_hr_ring`, the Today row, the places that stop it), so that a
sentence like "110 by default", "no other cue comes" or "it shows in Work,
while your watch reports steps" does not stop being true silently. The
behaviour itself is tested in tests/test_03x_kruh_vysoky_tep.py.

The honest part matters most here: 110 BPM is also the default high
heart-rate limit (where the Peak zone starts) until the app learns the
player's own, and cues never come in the Peak zone. The ring is opt-in,
silent and shows exactly when the heart rate is high - so the README,
CHANGELOG.md and docs/HOW-IT-WORKS.md, where they say cues never come in
the Peak zone, name the ring as the exception, and so does
docs/PRIOR_ART.md's Pauser row (its "never speaks in the Peak zone" is
about the voice). SOUL.md's wording is the author's: only the one sentence
the author approved for the ring is checked (its "What it is" names the
ring as the one exception, `test_soul_vynimka_kruhu_slovami_autora`).
"""
import inspect
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
import measure  # noqa: E402
import overlay  # noqa: E402
import settings_model as sm  # noqa: E402
import trigger  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

ZMENY = "CHANGELOG.md"
AKO = "docs/HOW-IT-WORKS.md"
ZNAME = "KNOWN_ISSUES.md"
VYDANA = "0.3.2"          # the release that brought the ring
_VERZIA = r"\d+(?:\.\d+){1,3}"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain_text(text):
    return " ".join(text.split())


def _plain(meno):
    return _plain_text(_read(meno))


def _en(kluc, **kw):
    text = i18n.STRINGS[kluc]["en"]
    return text.format(**kw) if kw else text


def _sekcia(text, nadpis, uroven="## "):
    zaciatok = text.index("\n" + uroven + nadpis)
    koniec = re.search(r"\n#{2,%d} " % len(uroven.strip()), text[zaciatok + 1:])
    return text[zaciatok:zaciatok + 1 + koniec.start() if koniec else len(text)]


def _zmeny_032():
    """The 0.3.2 section of CHANGELOG, without line breaks."""
    return _plain_text(_sekcia(_read(ZMENY), "What %s changes" % VYDANA))


def _ako_kruh():
    """HOW-IT-WORKS' section about the ring, without line breaks."""
    return _plain_text(_sekcia(_read(AKO), "The breath ring at high heart rate"))


def _readme_bod():
    """The README's "What it does" item about the ring."""
    co_robi = _sekcia(_read("README.md"), "What it does")
    zaciatok = co_robi.index("- **A breath ring at high heart rate")
    koniec = co_robi.find("\n- **", zaciatok + 1)
    return _plain_text(co_robi[zaciatok:koniec if koniec != -1 else len(co_robi)])


def _zname_bod():
    k = _read(ZNAME)
    zaciatok = k.index("- **The breath ring at high heart rate**")
    koniec = k.find("\n- **", zaciatok + 1)
    return _plain_text(k[zaciatok:koniec])


def _tik():
    return zdroj_metody("_tick_high_hr_ring")


# --------------------------------------------------------------------------
# CHANGELOG: the 0.3.2 section is on top, released, and about the ring
# --------------------------------------------------------------------------

def test_changelog_032_navrchu_vydana_o_kruhu():
    c = _read(ZMENY)
    nadpisy = re.findall(r"^## What (%s) " % _VERZIA, c, re.M)
    assert nadpisy[0] == VYDANA, nadpisy
    assert "\n## What %s changes\n" % VYDANA in c
    assert "(not released yet)" not in c
    zmeny = _zmeny_032()
    for znacka in ("not released yet", "not in a release yet", "in the code here",
                   "experiment"):
        assert znacka not in zmeny, znacka
    # the app version is this release (the metadata moved with it)
    assert re.search(_VERZIA, _en("app.version_short")).group(0) == VYDANA
    # what it is and that it's off by default
    assert ("**0.3.2:** if you switch it on, the breath ring breathes with you "
            "for as long as your heart rate stays above a limit you set. It's "
            "off by default.") in zmeny
    # the problem it answers: no cue in the Peak zone (not "nothing on
    # screen" - the heart-rate panel can be on)
    assert "**While your heart rate stayed high, no cue came.**" in zmeny
    assert "Zanshin showed nothing" not in zmeny


def test_prepinac_na_dnes_a_v_obrazkoch_z_appky():
    """The Today switch under the HUD row, with the limit in its label and ⚙
    that opens In-game pictures; the same switch and the limit on the Breath
    card of In-game pictures. One setting."""
    bpm = sm.DEFAULT_HIGH_HR_RING_BPM
    dnes = _en("dnes.high_hr_ring_quick", bpm=bpm)
    assert dnes == "Breath ring above 110 BPM"
    karta = _en("overlay.high_hr_ring")
    assert karta == "Ring at high heart rate too"
    obrazky = _en("overlay.dialog_title")
    panel = _en("hud.quick_label")
    zmeny = _zmeny_032()
    assert ("The switch is on *Today*, under *%s*: *%s* (the label shows your "
            "limit, and ⚙ next to it opens *%s*)." % (panel, dnes, obrazky)) in zmeny
    assert ("In *%s* the breath picture's card has the same switch, *%s*, and the "
            "limit, from 80 to 200 BPM (110 by default); the two switches are one "
            "setting." % (obrazky, karta)) in zmeny
    ako = _ako_kruh()
    assert ("Switch it on on *Today* (*%s*, under *%s*; ⚙ next to it opens *%s*) "
            "or in *%s* on the breath picture's card (*%s*), where you also set "
            "the limit: 80 to 200 BPM, 110 by default."
            % (dnes, panel, obrazky, obrazky, karta)) in ako
    # The In-game page has a panel titled "In-game pictures" too, but its
    # Breath row has no ring switch and no limit: those are only in the
    # dialog, reached by ⚙ on Today or by the panel's fine-tune button. The
    # README says where.
    doladit, stranka = _en("overlay.fine_tune"), _en("nav.vhre_short")
    assert ("Switch it on on *Today* (*%s*) or in *%s* (⚙ next to that switch, "
            "or *%s* on the *%s* page) on the breath picture's card, where you "
            "also set its limit (80–200 BPM;"
            % (dnes, obrazky, doladit, stranka)) in _readme_bod()
    vhre = zdroj_metody("_build_vhre_page")
    assert 'title=tr("overlay.dialog_title")' in vhre
    assert ('tr("overlay.fine_tune"),\n                      '
            'command=self.open_overlay_settings)') in vhre
    assert "high_hr_ring" not in vhre
    # the row on Today: under the HUD row, its label carries the limit, ⚙
    # opens In-game pictures, the switch calls the same handler as the card
    app = zdroj_suboru("app.py")
    hud, kruh = app.index("hud_row = ctk.CTkFrame"), app.index("kruh_row = ctk.CTkFrame")
    assert hud < kruh
    riadok = app[kruh:kruh + 1600]
    assert "text=self._high_hr_ring_quick_text()" in riadok
    assert "command=self.open_overlay_settings" in riadok
    assert "self.on_high_hr_ring_change(\n                enabled=" in riadok
    assert 'tr("dnes.high_hr_ring_quick", bpm=bpm)' in zdroj_metody("_high_hr_ring_quick_text")
    assert "OverlaySettingsDialog(self)" in zdroj_metody("open_overlay_settings")
    karta_src = zdroj_suboru("ui_dialogs.py")
    assert 'text=tr("overlay.high_hr_ring")' in karta_src
    assert "self.app.on_high_hr_ring_change(\n                          enabled=" in karta_src
    assert "high_hr_ring_quick_var" in zdroj_metody("on_high_hr_ring_change")


def test_vypnuty_predvolene_hranica_80_az_200_predvolene_110():
    assert sm.DEFAULT_HIGH_HR_RING_BPM == 110
    assert (sm.HIGH_HR_RING_BPM_MIN, sm.HIGH_HR_RING_BPM_MAX) == (80, 200)
    assert sm.normalize_high_hr_ring_bpm(None) == 110
    assert sm.normalize_high_hr_ring_bpm(50) == 80
    assert sm.normalize_high_hr_ring_bpm(250) == 200
    nacitaj, uloz = zdroj_metody("load_settings"), zdroj_metody("save_settings")
    assert '"high_hr_ring": False,' in nacitaj
    assert '"high_hr_ring_bpm": DEFAULT_HIGH_HR_RING_BPM,' in nacitaj
    assert 'data["high_hr_ring"] = loaded.get("high_hr_ring") is True' in nacitaj
    assert '"high_hr_ring": bool(' in uloz and '"high_hr_ring_bpm": ' in uloz
    zmeny = _zmeny_032()
    assert ("`dandurf_settings.json` gets two new keys, `high_hr_ring` (off) and "
            "`high_hr_ring_bpm` (110).") in zmeny
    assert ("A settings file from 0.3.1 works as it is; 0.3.2 adds the two keys "
            "the first time it saves.") in zmeny
    # "they belong to the app, not to a game profile, so profile codes don't
    # carry them"
    assert "high_hr_ring" not in zdroj_metody("export_profile_code")
    assert "high_hr_ring" not in zdroj_metody("import_profile_from_code")
    assert ("They belong to the app, not to a game profile, so profile codes "
            "don't carry them.") in zmeny
    assert ("Going back to 0.3.1 ignores them, and its next save drops them, so "
            "the ring is off again if you then come back to 0.3.2.") in zmeny
    assert "(from 0.3.2, off by default)" in _readme_bod()
    assert "(new in 0.3.2, off by default)" in _zname_bod()
    assert "It's off by default." in _ako_kruh()


# --------------------------------------------------------------------------
# When it shows and when it ends
# --------------------------------------------------------------------------

def test_nad_hranicou_z_cisla_na_obrazovke():
    """"Above your limit", by the number on screen (the 3-second median):
    `display_bpm > hranica`, where the line is the limit itself for a ring
    that isn't breathing and the limit minus `KRUH_TEP_REZERVA_BPM` for one
    that is (looping or finishing). So it starts above the limit and ends
    only "at least 3 BPM below" it - the number in every document and in the
    hint under the switch is the constant the app uses, and the example
    with 110 is computed from it."""
    import app_session
    import ui_dialogs
    rezerva = app_session.KRUH_TEP_REZERVA_BPM
    assert rezerva == 3
    tik = _tik()
    assert 'display_bpm' in tik and "bpm > hranica" in tik
    assert "hranica = prah - KRUH_TEP_REZERVA_BPM if showing else prah" in tik
    assert "bpm > prah" not in tik
    assert "last_bpm" not in tik.replace("_hr_last_bpm", "")
    assert hr_stats.ZOBRAZ_OKNO_S == 3.0
    zmeny, ako = _zmeny_032(), _ako_kruh()
    assert ("the heart rate on screen (the 3-second median the heart-rate panel "
            "shows, so a single spike doesn't start it) is above your limit") in zmeny
    assert ("and the heart rate on screen (the 3-second median, see [The "
            "heart-rate number on screen](#the-heart-rate-number-on-screen)) is "
            "above your limit, so a single spike doesn't start it.") in ako
    # the margin: the number and the example with the default limit
    prah = sm.DEFAULT_HIGH_HR_RING_BPM
    priklad = ("with %d, it shows above %d, keeps breathing at %d to %d and ends "
               "at %d or below" % (prah, prah, prah - rezerva + 1, prah,
                                   prah - rezerva))
    assert priklad == ("with 110, it shows above 110, keeps breathing at 108 to "
                       "110 and ends at 107 or below")
    assert ("Once it breathes, it keeps breathing until the heart rate drops at "
            "least %d BPM below your limit (%s), so a heart rate that hovers "
            "right at the limit doesn't make it come and go every few seconds."
            % (rezerva, priklad)) in zmeny
    assert ("**When it ends.** Once it breathes, it keeps breathing until the "
            "heart rate on screen drops at least %d BPM below your limit: %s, so "
            "a heart rate that hovers right at the limit doesn't make it come and "
            "go every few seconds." % (rezerva, priklad)) in ako
    assert ("until the rate drops at least %d BPM below the limit, then ends "
            "after an exhale; no cue comes meanwhile." % rezerva) in _readme_bod()
    # the old "it ends at the limit" is gone
    for stara in ("drops to the limit or below", "drops to your limit or below",
                  "once the rate drops;"):
        for text in (zmeny, ako, _readme_bod()):
            assert stara not in text, stara
    # a finish is cancelled above the margin; after the fade, above the limit
    assert "When the heart rate drops that far," in zmeny
    assert ("if the rate climbs back over that mark before then, it just keeps "
            "breathing. Once it has faded, it needs a heart rate above the limit "
            "itself to start again.") in zmeny
    assert "When the heart rate drops that far," in ako
    assert ("If the heart rate climbs back over that mark while it finishes, it "
            "keeps breathing without starting over. Once it has faded, it starts "
            "again only when the heart rate is above the limit itself;") in ako
    # the hint under the switch says the same, with the constant
    assert ("until it drops at least %d BPM below it; then it ends after an "
            "exhale." % rezerva) in _en("overlay.high_hr_ring_hint", margin=rezerva)
    assert ('tr("overlay.high_hr_ring_hint", margin=KRUH_TEP_REZERVA_BPM)'
            in zdroj_suboru("ui_dialogs.py"))
    assert ui_dialogs.KRUH_TEP_REZERVA_BPM is app_session.KRUH_TEP_REZERVA_BPM
    # watching, heart rate coming in, no "not now"
    for podmienka in ('"listening"', '"_hr_session_open"', '"_snooze_job"',
                      '"connected"', '"_hr_lost"'):
        assert podmienka in tik, podmienka
    assert ('While Zanshin is watching, heart rate is coming in, "not now" '
            "isn't on,") in ako


def test_kruh_dycha_od_vydychu_a_konci_vydychnuty():
    """Out, in, out, in ... starting with the exhale; the finish asked for
    ends breathed out, then the fade (`_SlotOverlay.finish_loop`)."""
    kruh = overlay._SlotOverlay.__new__(overlay._SlotOverlay)
    kruh._breath_mode = overlay._SlotOverlay.BREATH_LOOP
    kruh.inhale_s, kruh.exhale_s = 4.0, 6.0
    assert kruh.breath_phases() == ((False, 6.0), (True, 4.0))
    ako, zmeny = _ako_kruh(), _zmeny_032()
    assert ("out, in, out, in, round and round, starting with the exhale, with "
            "the captions *%s* and *%s*." % (_en("overlay.caption.exhale"),
                                             _en("overlay.caption.inhale"))) in ako
    assert "starting with the exhale, with the captions *EXHALE* and *INHALE*." in zmeny
    assert ("a running exhale is finished, a running inhale is finished and "
            "followed by one more exhale, then the ring fades.") in ako
    # its own switch: it draws with the breath picture switched off too
    start = overlay._SlotOverlay.start_loop
    assert "enabled" not in inspect.getsource(start).split('"""', 2)[2]
    assert ("it shows even with the breath picture switched off, because it has "
            "its own switch.") in zmeny
    assert "It shows even with the breath picture switched off, because it has its own switch" in ako


def test_co_ho_hned_zastavi():
    """"Not now", stopping watching, the end of a session and quitting remove
    it at once - each path calls `_stop_high_hr_ring`."""
    assert "self._stop_high_hr_ring()" in zdroj_metody("_start_snooze")
    assert '"_stop_high_hr_ring"' in zdroj_metody("stop_listening")
    assert '"_stop_high_hr_ring"' in zdroj_metody("_close_hr_session")
    assert 'krok("stop_listening", self.stop_listening)' in zdroj_metody("_quit")
    veta = ('"Not now", stopping watching, the end of a session and quitting '
            'remove it at once, and while "not now" holds it doesn\'t come back.')
    assert veta in _zmeny_032()
    assert veta in _ako_kruh()


# --------------------------------------------------------------------------
# The cues, and the Peak zone
# --------------------------------------------------------------------------

def test_ziadna_ina_hlaska_kym_svieti():
    """It is slot 3's window, and `_cue_can_fire` holds back every cue while
    any visual is on screen; a cue armed meanwhile is dropped `max_wait_s`
    (90 s) after it was armed. It also waits for a cue already on screen."""
    assert "any(self.overlay_manager.is_active(i) for i in range(4))" in \
        zdroj_metody("_cue_can_fire")
    assert "self._slots[self.BREATH_INDEX]" in zdroj_suboru("overlay.py").split(
        "def start_high_hr_ring(self):", 1)[1].split("\n    def ", 1)[0]
    assert "if any(om.is_active(i) for i in range(4)):" in _tik()
    assert trigger.default_params()["max_wait_s"] == 90.0
    stroj = zdroj_suboru("trigger.py")
    assert "cakane = now - self._armed_at" in stroj
    assert 'if cakane >= self.params["max_wait_s"]:' in stroj
    assert "return self._abort(A_NEDALO_SA, now)" in stroj
    zmeny, ako = _zmeny_032(), _ako_kruh()
    assert ("It waits for a cue already on screen to end, and while it shows, no "
            "other cue comes, voice or picture: a cue armed meanwhile waits, as "
            "it does for any picture on screen, and is dropped if it still can't "
            "come 90 s after it was armed.") in zmeny
    assert ("While it shows, no cue comes, voice or picture: a cue armed "
            "meanwhile waits, as it does for any picture on screen, and is "
            "dropped if it still can't come 90 s after it was armed.") in ako
    assert "no cue comes meanwhile." in _readme_bod()
    # the in-app hint says the same
    assert _en("overlay.high_hr_ring_hint").endswith("No other cue comes meanwhile.")


def test_pravidla_hlasok_pren_neplatia():
    """"It shows in Work, while your watch reports steps, and when Zanshin
    has gone quiet for a few sessions": the tick reads none of the world,
    the steps, the cue ladder, the cooldown or the hourly count. If one of
    them ever gates the ring, the sentence goes."""
    tik = _tik()
    for brana in ("_session_world", "world", "steps_per_min", "KROKY",
                  "_cue_rung", "rebrik", "cooldown", "last_global_trigger_time",
                  "cue_trigger", "pause_s"):
        assert brana not in tik, brana
    zmeny, ako = _zmeny_032(), _ako_kruh()
    assert ("It needs no pause in your input, it isn't one of the five cues an "
            "hour, it doesn't go quieter with the cues (it shows in Work, while "
            "your watch reports steps, and when Zanshin has gone quiet for a few "
            "sessions),") in zmeny
    assert ("It doesn't wait for a pause in your input, isn't one of the five "
            "cues an hour and doesn't go quieter with the cues: it shows in Work, "
            "while your watch reports steps, and when Zanshin has gone quiet for "
            "a few sessions.") in ako
    assert ("The cue rules above don't apply to it: it needs no pause, isn't one "
            "of the 5 an hour, doesn't go quieter with the cues,") in _readme_bod()


def test_peak_zona_a_110():
    """110 BPM is also the average-player high heart-rate limit (the start
    of the Peak zone) until the app has learned the player's own; the
    Peak zone is "at or above" (`zone_of_bpm`), the ring "above" - so with
    the default limit the ring shows from just where the Peak zone starts.
    The ring's limit is its own: the tick never reads the learned one."""
    assert hr_stats.KRITICKY_ZALOHA == float(sm.DEFAULT_HIGH_HR_RING_BPM) == 110.0
    assert hr_stats.zone_of_bpm(110, 70, 110) == hr_stats.zone_of_bpm(150, 70, 110)
    assert hr_stats.zone_of_bpm(109, 70, 110) != hr_stats.zone_of_bpm(110, 70, 110)
    tik = _tik()
    assert "critical" not in tik and "kritick" not in tik
    readme = _plain("README.md")
    assert ("Never in the Peak zone; at most 5 cues an hour, at least 4 minutes "
            "apart. (Only the optional breath ring at high heart rate, below, "
            "shows in the Peak zone.)") in readme
    assert ("and it shows in the Peak zone too (110 BPM is also where the Peak "
            "zone starts until Zanshin has learned your high heart-rate limit "
            "from your sessions). It's a picture to breathe with, not an "
            "alarm.") in _readme_bod()
    assert "it doesn't follow the high heart-rate limit Zanshin learns" in _readme_bod()
    zmeny = _zmeny_032()
    assert ("A cue never comes while your pulse is in the Peak zone (at or above "
            "your high heart-rate limit, 110 BPM until Zanshin has learned "
            "yours),") in zmeny
    assert ("and it shows in the Peak zone: with the default limit it shows from "
            "just where the Peak zone starts, until Zanshin has learned your "
            "high heart-rate limit from your sessions.") in zmeny
    assert ("The limit is your own number: it doesn't follow the high heart-rate "
            "limit Zanshin learns.") in zmeny
    ako = _plain(AKO)
    assert ("The one picture that does show in the Peak zone is the breath ring at "
            "high heart rate, from 0.3.2 and only if you switch it on (see [The "
            "breath ring at high heart rate](#the-breath-ring-at-high-heart-rate)).") in ako
    assert ("because 110 BPM is also the average-player limit it uses until "
            "then.") in _ako_kruh()
    # not an alarm - in every document that describes it
    for text in (zmeny, _ako_kruh(), _zname_bod()):
        assert "it follows the number you set, not your health." in text


# --------------------------------------------------------------------------
# The measurement, app.log, the cost
# --------------------------------------------------------------------------

def test_meracie_okna_s_kruhom_sa_nepocitaju():
    assert measure.R_KRUH_TEP == "kruh_pri_vysokom_tepe"
    assert (measure.REFRACTORY_BEFORE_S, measure.REFRACTORY_AFTER_S) == (60.0, 180.0)
    assert measure.ring_conflict(1000.0, [(930.0, 940.0)]) is True     # ends at -60
    assert measure.ring_conflict(1000.0, [(1180.0, 1200.0)]) is True   # starts at +180
    assert measure.ring_conflict(1000.0, [(900.0, 939.0)]) is False
    assert measure.ring_conflict(1000.0, [(1181.0, 1200.0)]) is False
    # a window with a reason is not valid, and the cue chart counts only
    # valid ones
    assert '"valid": not reasons,' in zdroj_suboru("measure.py")
    assert 'tr("history.effect_title")' in zdroj_suboru("app_history.py")
    assert "measure.by_category(okna)" in zdroj_metody("_refresh_cue_effect")
    graf = _en("history.effect_title")
    zmeny = _zmeny_032()
    assert ("When the ring was on screen anywhere from a minute before a cue to "
            "three minutes after it, that cue's measurement window is marked "
            "`%s` in `hr_windows.json` and isn't counted in History's *%s*, so "
            "with the ring on that chart fills more slowly."
            % (measure.R_KRUH_TEP, graf)) in zmeny
    assert "With the switch off, the windows are exactly as in 0.3.1." in zmeny
    assert ("When the ring was on screen anywhere from a minute before a cue to "
            "three minutes after it, that cue's measurement window is marked "
            "`%s` in `hr_windows.json` and isn't counted in History's *%s*:"
            % (measure.R_KRUH_TEP, graf)) in _ako_kruh()
    assert ("a cue's measurement window it reaches into isn't counted in "
            "History's cue chart, so with the ring on that chart fills more "
            "slowly.") in _zname_bod()


def test_app_log_dva_riadky():
    tik = _tik()
    assert ('app_log.info("kruh pri vysokom tepe: zobrazeny (tep %d, hranica %d)",'
            in tik)
    assert ('app_log.info("kruh pri vysokom tepe: skoncil po %.0f s"'
            in zdroj_metody("_high_hr_ring_ended"))
    veta = ("`app.log` gets one line when it starts (the heart rate and the limit) "
            "and one when it ends (how long it showed).")
    assert veta in _zmeny_032()
    assert ("`app.log` gets one line when the ring starts (the heart rate and the "
            "limit) and one when it ends (how long it showed).") in _ako_kruh()


def test_prekreslenie_25_za_sekundu_nezmerane():
    """Honest about the cost: while it shows it is redrawn every
    `TICK_MS` (40 ms = 25 a second) like the breath cue, for as long as the
    heart rate stays high, and nobody has measured the CPU it takes."""
    assert overlay._SlotOverlay.TICK_MS == 40
    zmeny = _zmeny_032()
    assert ("While the ring shows, it's redrawn about 25 times a second, like "
            "the breath cue; but a cue lasts seconds, and the ring lasts as long "
            "as your heart rate stays high. I haven't measured how much CPU that "
            "takes.") in zmeny
    assert ("It's redrawn about 25 times a second while it shows, and I haven't "
            "measured what that costs.") in _zname_bod()
    assert "it's redrawn about 25 times a second, like the breath cue." in _ako_kruh()


def test_rezerva_pod_hranicou_ale_bez_odstupu_medzi_zobrazeniami():
    """The margin below the limit is there (`KRUH_TEP_REZERVA_BPM`, see
    `test_nad_hranicou_z_cisla_na_obrazovke`), so KNOWN_ISSUES.md and
    HOW-IT-WORKS no longer say "no margin" or "start and end again and
    again". What stays true, and HOW-IT-WORKS says so: "no minimum time
    between showings" - the only wait before a new showing is after a ring
    that could not be drawn, and a faded ring needs more than the limit
    itself again."""
    tik = _tik()
    assert "KRUH_TEP_REZERVA_BPM" in tik
    assert tik.count("_high_hr_ring_retry_at = ") == 1
    assert "self._high_hr_ring_retry_at = now + KRUH_TEP_ZNOVA_S" in tik
    assert "_high_hr_ring_retry_at" not in zdroj_metody("_high_hr_ring_ended")
    zname, ako, zmeny = _zname_bod(), _ako_kruh(), _zmeny_032()
    for stara in ("no margin below the limit", "There's no margin",
                  "again and again", "a few seconds apart"):
        for text in (zname, ako, zmeny):
            assert stara not in text, stara
    assert ("Once it has faded, it starts again only when the heart rate is above "
            "the limit itself; there's no minimum time between showings.") in ako
    # what KNOWN_ISSUES still says is open about the ring
    assert ("while it shows, no cue comes, and a cue's measurement window it "
            "reaches into isn't counted in History's cue chart") in zname


# --------------------------------------------------------------------------
# What the ring does to "not now" and to the line after a session
# --------------------------------------------------------------------------

def test_nie_teraz_pri_kruhu_sa_do_rebrika_nerata():
    """"Not now" pressed while the ring is on screen (breathing or
    finishing) does not count against the last cue: `_start_snooze` asks
    `_high_hr_ring_on_screen` BEFORE it removes the ring, and only without
    the ring on screen records the ladder signal (`_zapis_snooze_po_hlaske`);
    with it, one app.log line. Without the ring "not now" within a minute of
    a cue counts as before (60 s, then two minutes of play, unless "it
    landed"). Switching the ring off does not touch the ladder either. If
    "not now" ever counts again while the ring shows, the sentences go."""
    import rebrik
    snooze = zdroj_metody("_start_snooze")
    otazka = snooze.index("if self._high_hr_ring_on_screen():")
    zapis_v = snooze.index("self._zapis_snooze_po_hlaske(now)")
    assert otazka < snooze.index("else:", otazka) < zapis_v
    assert zapis_v < snooze.index("self._stop_high_hr_ring()")
    assert snooze.count("self._zapis_snooze_po_hlaske(") == 1
    assert 'app_log.info("rebrik hlasky: teraz nie pocas kruhu' in snooze
    # "on screen" = an open showing or the overlay's own state (finishing too)
    na_obrazovke = zdroj_metody("_high_hr_ring_on_screen")
    assert '"_high_hr_ring_since"' in na_obrazovke
    assert '"high_hr_ring_showing"' in na_obrazovke
    zapis = zdroj_metody("_zapis_snooze_po_hlaske")
    assert "rebrik.SNOOZE_PO_HLASKE_S" in zapis
    assert (rebrik.SNOOZE_PO_HLASKE_S, rebrik.SNOOZE_POTOM_S) == (60.0, 120.0)
    assert rebrik.signal_dole({"snooze_after_cue_s": 20.0,
                               "snooze_then_s": 130.0}) == rebrik.D_SNOOZE
    assert rebrik.signal_dole({"snooze_after_cue_s": 20.0, "snooze_then_s": 130.0,
                               "cue_verdict": rebrik.VERDIKT_SADLA}) is None
    prepinac = zdroj_metody("on_high_hr_ring_change")
    for slovo in ("snooze", "rebrik", "_cue_rung"):
        assert slovo not in prepinac, slovo
    ako, zmeny, zname = _ako_kruh(), _zmeny_032(), _zname_bod()
    assert ('"Not now" pressed while the ring is on screen, breathing or '
            "finishing, doesn't count against the last cue, even within a minute "
            "of it, so it can't make the next session go a step quieter (see "
            "[When it goes quieter](#when-it-goes-quieter)); `app.log` notes it "
            "instead. Switching the ring off on *Today* ends it breathed out and "
            "tells the cues nothing either.") in ako
    assert ('From 0.3.2, "not now" pressed while the breath ring at high heart '
            "rate is on screen doesn't count") in _plain_text(
                _sekcia(_read(AKO), "When it goes quieter"))
    assert ('"Not now" pressed while the ring is on screen doesn\'t count against '
            "the last cue, even within a minute of it, so it can't make the cues "
            "go a step quieter (`app.log` notes it instead), and neither does "
            "switching the ring off on *Today*.") in zmeny
    assert ('"Not now" removes it at once and, pressed while the ring shows, '
            "doesn't make the cues go a step quieter.") in _readme_bod()
    # the old "still counts against that cue" is gone everywhere
    for text in (ako, zmeny, zname, _readme_bod()):
        assert "still counts against that cue" not in text
        assert "even if you pressed it for the ring" not in text
    assert "Not now" not in zname


def test_veta_po_relacii_menuje_kruh_len_ked_podrzal_kazdu():
    """The line after a session that says why no cue came knows about the
    ring: a cue the ring held back is dropped as `nedalo_sa` (the gate let it
    through, the app could not show it), counted per cancellation in
    `cues_withheld_ring`, and `_preco_ticho` names the ring only when it held
    back every such cue (`session.end.none_ring`); otherwise, and without
    the ring, the general sentence (`session.end.none_blocked`) - never the
    "longest stretch" one. The reasons checked before it still win, even
    when the ring held back every ready cue: "not now" (`snoozed_s`),
    repeated dropouts, not a single pause, and the gate's own (the load
    still climbing, the Peak zone - with the default limit the ring starts
    right where the Peak zone does, so that one is not rare). The documents
    quote the ring sentence word for word, say those reasons come first and
    no longer say the line can't name the ring."""
    import ui_dialogs
    preco = ui_dialogs.SessionEndDialog._preco_ticho
    zaklad = {"above_runs": 3, "longest_above_s": 50.0, "stress_hold_s": 45.0,
              "duration_s": 1800.0, "pause_episodes": 12}

    def veta(**navyse):
        return preco(dict(zaklad, **navyse))

    kruh, vseobecna = i18n.tr("session.end.none_ring"), i18n.tr("session.end.none_blocked")
    nedalo = {trigger.A_NEDALO_SA: 2}
    assert veta(cues_withheld=nedalo, cues_withheld_ring=2) == kruh
    assert veta(cues_withheld=nedalo, cues_withheld_ring=1) == vseobecna
    assert veta(cues_withheld=nedalo) == vseobecna
    # the ring showed some time, but held back no cue: not blamed
    assert veta(cues_withheld=nedalo, high_hr_ring_s=300.0) == vseobecna
    # the gate's reasons first, the "longest stretch" only without a ready cue
    for brana in (trigger.A_BEZ_PAUZY, trigger.A_NEVHODNA_CHVILA):
        assert veta(cues_withheld={trigger.A_NEDALO_SA: 2, brana: 1},
                    cues_withheld_ring=2) == i18n.tr("session.end.none_withheld")
    # ... and so do "not now", repeated dropouts and not a single pause,
    # although the ring held back every ready cue (what the documents list)
    vsetky = {"cues_withheld": nedalo, "cues_withheld_ring": 2}
    assert veta(snoozed_s=120.0, **vsetky) == i18n.tr("session.end.none_snoozed", min=2)
    assert veta(runs_cancelled_gap=2, **vsetky) == i18n.tr("session.end.none_dropouts", n=2)
    assert veta(pause_episodes=0, **vsetky) == i18n.tr("session.end.none_nopause")
    # a single dropout or a short session without a pause does not take over
    assert veta(runs_cancelled_gap=1, **vsetky) == kruh
    assert veta(pause_episodes=0, duration_s=240.0, **vsetky) == kruh
    assert veta() == i18n.tr("session.end.none_short", najdlhsie=50, treba=45)
    # counted at the cancellation itself, only for `nedalo_sa` and the ring
    zrusene = zdroj_metody("_on_cue_event")
    assert ('if ev.get("reason") == trigger.A_NEDALO_SA and '
            'self._cue_held_by_ring():') in zrusene
    assert "self._cues_withheld_ring = " in zrusene
    # the texts the documents quote
    s_kruhom = _en("session.end.none_ring")
    assert s_kruhom == ("A cue was ready, but the breath ring for high heart rate "
                        "was breathing on screen, so I held it back.")
    assert _en("session.end.none_blocked") == (
        "A cue was ready, but it could not come at that moment — a picture was "
        "already on screen, your watch was reporting steps, or all pictures were "
        "off.")
    zmeny, ako, zname = _zmeny_032(), _ako_kruh(), _zname_bod()
    predtym = ('your "not now", repeated heart-rate dropouts, not a single pause '
               "in your input in a session of five minutes or more, %s a cue held "
               "back because your load was still climbing or your pulse was in "
               "the Peak zone. With the default limit that last one can come "
               "first, because the ring then starts just where the Peak zone does "
               "(see below).")
    assert ("If no cue came in a session, the line after the session that says "
            "why no cue came can now name the ring: *%s* It does that only when "
            "the ring held back every cue that was ready and none of the reasons "
            "the line checks first applies: %s When a ready cue couldn't come "
            "for another reason, or the ring held back only some of them, the "
            "line says, after the same checks, that a picture was already on "
            "screen, your watch was reporting steps, or all pictures were off. "
            "Before, such a session could be told that your load's longest "
            "stretch was too short." % (s_kruhom, predtym % "or")) in zmeny
    assert ("If no cue came in a session, the line after it that says why names "
            "the ring only when the ring held back every cue that was ready: "
            "*%s* Even then, the reasons that line checks first win: %s When "
            "none of those applies and a ready cue couldn't come for another "
            "reason, or the ring held back only some of them, the line says a "
            "picture was already on screen (the ring is one), your watch was "
            "reporting steps, or all pictures were off."
            % (s_kruhom, predtym % "and")) in ako
    assert ("The line after a session that says why no cue came names the ring "
            'only when it held back every cue that was ready and no reason the '
            'line checks first applies, such as your "not now", heart-rate '
            "dropouts, or a cue held back in the Peak zone, which with the "
            "default limit starts where the ring does. Otherwise it gives one "
            "of those reasons, or the general one (a picture already on screen, "
            "steps, all pictures off), which doesn't say which of the three it "
            "was.") in zname
    # the Peak zone starts where the ring does with the default limit - the
    # reason the documents give for the Peak-zone sentence coming first
    # (`test_peak_zona_a_110` pins the zone itself)
    assert hr_stats.KRITICKY_ZALOHA == float(sm.DEFAULT_HIGH_HR_RING_BPM)
    for stara in ("doesn't know about the ring", "doesn't name the ring",
                  "doesn't know:", "it can say your load's longest stretch",
                  "it can say instead that your load's longest stretch",
                  "now names the ring:", "the line gives the general reasons"):
        for text in (zmeny, ako, zname):
            assert stara not in text, stara


def test_relacia_si_pamata_kruh_a_podrzane_hlasky():
    """"A session in which the ring showed keeps two more numbers ... each
    only when it's above zero ... the data export and import carry them;
    the CSV export doesn't change": the summary adds `high_hr_ring_s` and
    `cues_withheld_ring` only above zero, the import's type check knows
    both (as numbers), the CSV row reads neither."""
    import data_io
    suhrn = zdroj_metody("_suhrn_relacie")
    assert 'if kruh_s > 0.0:\n                summary["high_hr_ring_s"] = kruh_s' in suhrn
    assert 'summary["cues_withheld_ring"] = podrzane' in suhrn
    assert "podrzane > 0" in suhrn
    for kluc in ("high_hr_ring_s", "cues_withheld_ring"):
        assert data_io._TYPY_RELACIE[kluc] is data_io._konecne, kluc
        assert kluc not in inspect.getsource(hr_stats.session_row), kluc
        assert kluc not in " ".join(map(str, hr_stats.CSV_COLUMNS)), kluc
    ocistena = data_io.clean_session({"started": 1.8e9, "duration_s": 1200.0,
                                      "high_hr_ring_s": 412.3,
                                      "cues_withheld_ring": 2})
    assert (ocistena["high_hr_ring_s"], ocistena["cues_withheld_ring"]) == (412.3, 2)
    veta = ("A session in which the ring showed keeps two more numbers in "
            "`hr_sessions.json`: `high_hr_ring_s`, how many seconds the ring was "
            "on screen, and `cues_withheld_ring`, how many ready cues it held "
            "back. Each is saved only when it's above zero, so a session without "
            "the ring is saved exactly as before. The data export and import "
            "carry them; the CSV export doesn't change.")
    assert ("- **Saved sessions.** " + veta) in _plain_text(_sekcia(
        _read(ZMENY), "What %s changes" % VYDANA))
    assert ("**What your sessions keep.** A saved session in which the ring "
            "showed has two more numbers in `hr_sessions.json`: `high_hr_ring_s`, "
            "how many seconds the ring was on screen, and `cues_withheld_ring`, "
            "how many ready cues it held back. Each is there only when it's above "
            "zero, so a session without the ring is saved exactly as before. The "
            "data export and import carry them; the CSV export has no column for "
            "them.") in _ako_kruh()


# --------------------------------------------------------------------------
# Prior art: Zanshin is not "never a fixed number" any more
# --------------------------------------------------------------------------

def test_prior_art_kruh_reaguje_na_pevne_cislo():
    """Cardia's alarm and Pauser's alert react to a fixed number, and
    PRIOR_ART set Zanshin apart from them by that. The ring does react to a
    fixed number the player sets: a new one starts only above the limit
    itself (`hranica = prah ... else prah`, `bpm > hranica`; the margin below
    it only keeps a breathing ring going), with no pause and no load (see
    `test_pravidla_hlasok_pren_neplatia`), so both rows, the "In one line"
    and the README's "Similar projects" say so."""
    tik = _tik()
    assert "hranica = prah - KRUH_TEP_REZERVA_BPM if showing else prah" in tik
    assert "bpm > hranica" in tik and "pause_s" not in tik
    prior = _plain("docs/PRIOR_ART.md")
    assert "Zanshin fires only when" not in prior
    assert ("Zanshin's cues look at strain against your own calm, wait until it "
            "has spent a while above your threshold, and hold the voice for a "
            "short pause in your input. One thing in Zanshin does work like "
            "Cardia's alarm: the breath ring at high heart rate (from %s, off by "
            "default) shows while your pulse is above a number you set, "
            "mid-fight or not. It's silent and a ring to breathe with, but it "
            "follows that number, not your strain." % VYDANA) in prior
    assert ("Zanshin's cues come only when your strain has spent enough time "
            "above a threshold") in prior
    assert ("The exception is the breath ring at high heart rate (from %s, off "
            "by default): like Pauser's alert, it comes when your pulse passes "
            "a limit you set, mid-fight or not, and it shows in the Peak zone "
            "too, silently, on your PC's screen." % VYDANA) in prior
    zatvorka = ("(If you switch it on, its breath ring at high heart rate does "
                "show, silently, while your pulse is above a number you set.)")
    assert zatvorka in prior
    assert zatvorka in _plain_text(_sekcia(_read("README.md"), "Similar projects"))


# --------------------------------------------------------------------------
# SOUL.md: the one exception, in the author's words
# --------------------------------------------------------------------------

def test_soul_vynimka_kruhu_slovami_autora():
    """The author's decision (0.3.2): SOUL.md's "What it is" names the ring
    as the one exception, in exactly these words, right after the
    sentence about the silent picture and in the same paragraph. It stays
    true while the ring is opt-in (off by default), silent, follows the
    player's own limit and shows in the Peak zone too
    (`test_vypnuty_predvolene_hranica_80_az_200_predvolene_110`,
    `test_peak_zona_a_110`). The rest of SOUL.md is not checked here."""
    veta = ("The one exception is yours to switch on: a breath ring that breathes "
            "silently with you while your heart rate is above a limit you set, in "
            "the Peak zone too.")
    predtym = ("If no pause comes, at most a small silent picture appears, under "
               "the same rules.")
    soul = _read("SOUL.md")
    assert soul.count(veta) == 1
    co_je = _sekcia(soul, "What it is")
    odsek = next(o for o in co_je.split("\n\n") if predtym in o)
    assert (predtym + " " + veta) in odsek
    assert odsek.rstrip().endswith(veta)
    assert sm.DEFAULT_HIGH_HR_RING_BPM == hr_stats.KRITICKY_ZALOHA
    assert '"high_hr_ring": False,' in zdroj_metody("load_settings")
