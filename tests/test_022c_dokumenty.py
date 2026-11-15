# -*- coding: utf-8 -*-
"""README, PRIVACY and KNOWN_ISSUES after batch 0.3c say what the code does.

Audit: pairing in the README had no procedure (where the PC address is,
that 0.0.0.0 does not belong in the phone, Private network, Cancel in the
firewall, OBS on 4455). Batch 0.3c changed pairing, the introduction, the
tour and the first evening - the documents must say it the same way.
Guarded:

  * README "Getting your heart rate in" starts with 5 steps, followed by
    "Still waiting for the watch?" and "Streaming with OBS?"; the control
    names are exactly those of the English UI and the numbers (20 s,
    4456) come from the code,
  * the first start waits for the voice at most 15 s - README and PRIVACY
    no longer claim that the app starts watching right after the
    introduction,
  * es/de/fr/pt get a voice of their language, a "Just setting up the
    app" session is excluded from learning,
  * KNOWN_ISSUES has points about the introduction, the tour and pairing
    in the 0.3 section (since batch 4 that section is in CHANGELOG.md).

Whole paragraphs are deliberately not pinned (audit: tests locked the
README in length) - only names from the UI, numbers from the code and
sentences that must no longer be true. Since 0.3d the voice and learning
rules are in docs/HOW-IT-WORKS.md - the guards went with them.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import hr_stats  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402
from settings_model import VOICE_HINTS  # noqa: E402


AKO = "docs/HOW-IT-WORKS.md"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(text):
    # sentences in .md are wrapped anywhere; the non-breaking hyphen (U+2011)
    # from the UI and from the README is compared as an ordinary one
    return " ".join(text.split()).replace("‑", "-")


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis, koniec=None):
    zaciatok = text.index("\n## " + nadpis)
    stop = text.index(koniec, zaciatok) if koniec else text.find("\n## ", zaciatok + 1)
    return text[zaciatok:stop if stop != -1 else len(text)]


def _konstanta(meno):
    """A DandurfApp class number from app.py source - no Tk import."""
    m = re.search(r"^\s+%s = ([\d.]+)\s*$" % meno, zdroj_suboru("app.py"), re.M)
    assert m, meno
    return float(m.group(1))


# --------------------------------------------------------------------------
# README: pairing step by step
# --------------------------------------------------------------------------

def _parovanie():
    return _plain(_sekcia(_read("README.md"), "Getting your heart rate in"))


def test_readme_parovanie_zacina_krokmi():
    s = _parovanie()
    kroky = [s.index("%d. **" % n) for n in range(1, 6)]
    assert kroky == sorted(kroky)
    assert "6. **" not in s
    # steps at the top of the section, tips after them, port details only then
    assert (kroky[-1] < s.index("**Still waiting for the watch?**")
            < s.index("**Streaming with OBS?**")
            < s.index("listens on port `4455`"))
    # the old sentence that the steps replaced
    assert "*Pairing* then means pointing the companion" not in s


def test_readme_kroky_menuju_ovladace_ako_appka():
    s = _parovanie()
    for kluc in ("hr.pair_button", "hr.ip_show", "hr.qr_show",
                 "settings.hr_ip_label", "hr.noconnect_title"):
        assert _plain(_en(kluc)) in s, kluc
    assert "**%s → %s**" % (_en("nav.vhre_short"),
                            _en("settings.hr_section_title")) in s
    # scene and source are the ones the phone app offers (pairing guide step 4)
    krok4 = _en("hr.step4_body")
    assert "“Zanshin”" in krok4 and "“Tep”" in krok4
    assert 'the scene "Zanshin" and the source "Tep"' in s
    # 0.0.0.0 does not go in the phone - README says so, like the app's field
    assert "not the `0.0.0.0`" in s
    assert "0.0.0.0" in _en("settings.hr_ip_hint")


def test_readme_cesty_vo_windows_ako_v_navode():
    """The Windows menus in the README are the same as in the box "Watch
    won't connect at all?" - otherwise the player would look for two
    different paths."""
    s = _parovanie()
    box = _plain(_en("hr.noconnect_body"))
    for cesta in ("Windows Security → Firewall & network protection → Allow "
                  "an app through firewall → Change settings",
                  "Network & internet → Wi-Fi (or Ethernet) → your network",
                  "Private network"):
        assert cesta in box, cesta
        assert cesta in s, cesta
    assert "tick **Private** next to Zanshin" in s


def test_readme_cisla_parovania_su_z_kodu():
    s = _parovanie()
    # "the phone did not connect" after `HR_NO_CLIENT_AFTER_MS`
    assert _konstanta("HR_NO_CLIENT_AFTER_MS") == 20000
    assert "after about 20 seconds" in s
    # OBS holds 4455: the journal suggests the same fallback port as the README
    assert "4456" in _en("log.hr_port_busy") and "OBS" in _en("log.hr_port_busy")
    assert "for example to `4456`" in s
    assert "You don't need OBS for Zanshin" in s
    # "Zanshin tries the new port right away": a port change restarts
    # reception right away, even if a port error switched it off before
    zmena = zdroj_metody("on_hr_config_change")
    assert "network_changed" in zmena
    assert "self.start_heart_rate_monitor()" in zmena
    assert "_hr_vypnute_chybou" in zmena


def test_navod_uz_neradi_prepnut_prijem():
    """Step 5 of the pairing guide used to advise switching on a toggle that
    opening the guide had already switched on - whoever obeyed switched
    reception off. The README steps do not do that either."""
    prepinac = _en("settings.hr_enable_switch")
    assert prepinac not in _en("hr.step5_body")
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")
    s = _parovanie()
    kroky = s[:s.index("**Still waiting for the watch?**")]
    assert prepinac not in kroky
    assert "This switches heart-rate receiving on" in kroky


# --------------------------------------------------------------------------
# First start, language voices, setup session
# --------------------------------------------------------------------------

def test_prvy_start_caka_na_hlas_najviac_15_s():
    assert _konstanta("PRVY_START_MAX_S") == 15.0
    assert "self._zacni_sledovat_po_priprave_hlasu()" in zdroj_suboru("app.py")
    readme = _plain(_read("README.md"))
    privacy = _plain(_read("PRIVACY.md"))
    assert "begins listening by itself right after the introduction" not in readme
    assert "starts listening by itself right after the introduction" not in privacy
    assert "at most about 15 seconds" in readme
    assert "after about 15 seconds at most" in privacy
    assert "*%s*" % _en("kamae.voice_prep") in readme


def test_hlas_ukazky_v_uvode_je_z_windows():
    """README and PRIVACY: the voice sample in the introduction sends nothing
    - the code uses only the Windows voice (`speak_sapi_isolated`)."""
    assert "speak_sapi_isolated(" in zdroj_suboru("ui_dialogs.py")
    assert "its voice preview there uses the Windows voice and sends nothing" in (
        _plain(_read(AKO)))
    assert "The voice preview in the introduction always uses it" in (
        _plain(_read("PRIVACY.md")))


def test_hlasy_jazykov_es_de_fr_pt():
    assert {"es", "de", "fr", "pt"} <= set(VOICE_HINTS)
    ako = _plain(_read(AKO))
    assert "also in Spanish, German, French or Portuguese" in ako
    k = _plain(_sekcia(_read("CHANGELOG.md"), "What 0.3 changes",
                       "\n## What 0.2.1 fixes"))
    # the voice names in CHANGELOG are those from VOICE_HINTS
    for jazyk in ("es", "de", "fr", "pt"):
        meno = re.match(r"\w+-\w+-(\w+?)Neural$", VOICE_HINTS[jazyk]).group(1)
        assert meno in k, (jazyk, meno)


def test_relacia_nastavovania_sa_neuci():
    znacka = _en("session.context.setup")
    zaklad = {"duration_s": 900.0, "baseline_bpm": 70.0, "max_bpm": 95.0}
    assert hr_stats.ciste_relacie([dict(zaklad, setup=True)]) == []
    ako = _plain(_read(AKO))
    k = _plain(_read("CHANGELOG.md"))
    assert "*%s*" % znacka in ako
    assert "*%s*" % znacka in k


# --------------------------------------------------------------------------
# KNOWN_ISSUES: section 0.3
# --------------------------------------------------------------------------

def _known_022():
    return _plain(_sekcia(_read("CHANGELOG.md"), "What 0.3 changes",
                          "\n## What 0.2.1 fixes"))


def test_known_issues_022_ma_uvod_a_parovanie():
    k = _known_022()
    assert k.index("### The first start") < k.index("### Pairing your watch")
    for nadpis in ('**"Pair a watch now" in the intro skipped the rest of it.**',
                   "**The intro couldn't be closed.**",
                   "**The tour described the ensō wrong.**",
                   "**The first evening spoke mostly in the Windows voice.**",
                   "**Setting the app up at the desk counted as play.**",
                   "**The pairing guide never showed whether pairing worked",
                   "**The English pairing guide showed `THIS PC\\u2019S` literally.**"):
        assert nadpis in k, nadpis


def test_known_issues_022_cituje_texty_z_appky():
    k = _known_022()
    for kluc in ("ob.skip", "ob.quit.title", "tour.sensor.pair",
                 "kamae.voice_prep", "kamae.no_client", "hr.noconnect_title",
                 "hr.trouble_title", "dnes.hr_title", "dnes.hr_off",
                 "dnes.hr_busy", "dnes.hr_no_client", "dnes.hr_waiting",
                 "settings.hr_ip_label", "hr.pair_button"):
        assert "*%s*" % _plain(_en(kluc)) in k, kluc
    assert '"%s"' % _en("hr.pair_this_pc") in k
    # live status in the pairing guide - from waiting to heart rate
    assert "*%s*" % _en("hr.pair_status_waiting").lstrip("● ") in k


def test_known_issues_prehliadka_pat_miest():
    """Welcome + five places = 6 bubbles; "five places" in the tour text and
    in KNOWN_ISSUES."""
    from guided_tour import GuidedTour
    assert GuidedTour.STEP_COUNT == 6
    assert "five places" in _en("tour.welcome.body")
    assert "five places in about a minute" in _known_022()
