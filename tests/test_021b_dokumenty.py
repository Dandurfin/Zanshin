# -*- coding: utf-8 -*-
"""Documents after the 0.2.1 fixes (second check) say what the code does.

  * README / PRIVACY: the natural voice sends Microsoft only cues it can
    really say (one of the four, enabled, with the in-game picture on,
    with voice, without its own recording). They no longer claim that a
    disabled or recorded cue goes too, or that after switching to the
    Windows voice a preparation already running still sends the rest.
  * A cue with its in-game picture turned off is not prepared since
    0.2.1c - PRIVACY and KNOWN_ISSUES no longer admit that its text goes
    to Microsoft.
  * UDP that did not open: the documents quote the label and the switch
    exactly as the app shows them; only the port and the error go into
    app.log.
  * KNOWN_ISSUES: the game "may not get" Ctrl+Alt+Z, walking is not
    excluded from learning (steps only silence cues), terms as in the
    README, licence "GPLv3" (author 2026-11-15: version 3 only, without
    "or later").
  * SOUL: the high heart rate limit is a fallback of 110 until it is
    learnt.
  * SAFETY: gui_harness_auto.py backs up the settings and heart rate
    history to disk next to the originals and restores them after an
    interrupted run (since 0.2.1c; until then it kept the history only in
    memory and SAFETY admitted it).

Every sentence is tied to the code: when the code changes, the test says
which document needs rewriting - not the other way round.

0.3d: the detailed rules of voice preparation moved from the README to
docs/HOW-IT-WORKS.md, the developer scripts and the GUI harness to
DEVELOPMENT.md; the guards went with the sentences. The word "reminder"
is "cue" in the documents, as in the app.
0.3 (batch 4): what each version fixed is in CHANGELOG.md (KNOWN_ISSUES
has only open things) - the guards for those sentences are there.
"""
import ast
import inspect
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import heart_rate  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
AKO = "docs/HOW-IT-WORKS.md"
ZMENY = "CHANGELOG.md"
VYVOJ = "DEVELOPMENT.md"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(meno):
    """Text without line breaks and without ">" quote marks at line starts -
    sentences in .md are wrapped anywhere, even in the README box."""
    return " ".join(" ".join(r.lstrip(">") for r in _read(meno).splitlines())
                    .split())


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


def _metoda_triedy(subor, trieda, metoda):
    src = _read(subor)
    for uzol in ast.parse(src).body:
        if isinstance(uzol, ast.ClassDef) and uzol.name == trieda:
            for f in uzol.body:
                if isinstance(f, ast.FunctionDef) and f.name == metoda:
                    return ast.get_source_segment(src, f)
    raise AssertionError(f"{trieda}.{metoda} nie je v {subor}")


# --------------------------------------------------------------------------
# Voice preparation: what is sent
# --------------------------------------------------------------------------

def test_priprava_posiela_len_hlasky_ktore_moze_povedat():
    # Code: a disabled cue, a cue with its in-game picture off (0.2.1c), a
    # cue with its own recording and an extra slot from 0.1 (index 4+) are
    # not prepared - not even on Test (`_speak_text`).
    telo = zdroj_metody("_slot_na_pripravu")
    for podmienka in ("je_kategoria(slot.index)", "slot.enabled_value",
                      "self._ma_obrazok_v_hre(slot)",
                      "MODE_TTS", "self._slot_voice_clip(slot)"):
        assert podmienka in telo, podmienka
    assert "self._slot_na_pripravu(slot)" in zdroj_metody("pregen_jobs")
    assert "self._slot_na_pripravu(slot)" in zdroj_metody("_speak_text")

    # The README only says "the wording of your spoken cues"; the exact
    # conditions are in HOW-IT-WORKS and in PRIVACY since 0.3d.
    readme = _plain("README.md")
    assert "the wording of your spoken cues" in readme
    ako = _plain(AKO)
    for meno, text in (("README.md", readme), (AKO, ako)):
        assert "including ones you've switched off" not in text, meno
    assert ("one of the four, switched on with its in-game picture on, set to "
            "speak and not playing your own recording") in ako
    assert ("testing a cue that is switched off or has its picture off, "
            "or an extra one kept from 0.1, plays the Windows voice and sends "
            "nothing") in ako

    privacy = _plain("PRIVACY.md")
    assert "**Which cues:** only those of the four" in privacy
    assert ("that are switched on, have their in-game picture on, are set to "
            "speak and don't play your own recording") in privacy
    assert "extra cue kept from a 0.1 profile are never sent" in privacy
    # What starts the preparation (enabling a cue or a picture, deleting a
    # recording, a new profile).
    assert ("switch it or its picture on, switch it to speak or remove its "
            "own recording") in ako
    assert ("switch a cue or its picture on, switch it to speak or "
            "remove its own recording") in privacy
    for meno, text in ((AKO, ako), ("PRIVACY.md", privacy)):
        assert "profile (or create one)" in text, meno


def test_zapnutie_hlasky_a_novy_profil_pripravu_spustia():
    """README and PRIVACY name enabling a cue and a new profile among the
    things that start the preparation - since this fix the code really
    does that."""
    assert "schedule_pregenerate" in _metoda_triedy(
        "ui_dialogs.py", "SlotCard", "on_enabled_change")
    assert "schedule_pregenerate" in zdroj_metody("create_profile")
    assert "schedule_pregenerate" in _metoda_triedy(
        "ui_dialogs.py", "SlotSettingsDialog", "_commit_voice")
    # Enabling the in-game picture too (0.2.1c) - both picture switches go
    # through `on_overlay_config_change` (test_021c_pregen_obrazok.py).
    assert "self.schedule_pregenerate(200)" in zdroj_metody("on_overlay_config_change")


def test_prepnutie_prec_zastavi_rozbehnutu_pripravu():
    # Code: every scheduling and even an empty preparation increments
    # `_pregen_seq`, switching to the Windows voice too - the thread does
    # not start the next cue.
    for metoda in ("on_engine_change", "schedule_pregenerate", "pregenerate"):
        assert "self._zrus_rozbehnutu_pripravu()" in zdroj_metody(metoda), metoda
    assert "self._pregen_seq += 1" in zdroj_metody("_zrus_rozbehnutu_pripravu")

    for meno in ("README.md", AKO):
        assert ("lines already being prepared at that moment are still sent"
                not in _plain(meno)), meno
    assert ("to Work or to the Windows voice stops any preparing already "
            "running at once; only a line already on its way is finished") in _plain(AKO)

    privacy = _plain("PRIVACY.md")
    assert "**Switching away stops it.**" in privacy
    assert ("to *Work* or to the Windows voice while lines are being prepared, "
            "preparing stops at once; only the line already on its way is "
            "finished") in privacy

    k = _plain(ZMENY)
    assert "**Switching to the Windows voice didn't stop preparing" in k


def test_hlaska_s_vypnutym_obrazkom_dokumenty_hovoria_pravdu():
    """`_dalsi_cue_slot` does not itself trigger a cue whose in-game picture
    is off. Until 0.2.1b the preparation did not exclude it (its text went
    to Microsoft) and PRIVACY with KNOWN_ISSUES honestly admitted it.
    Since 0.2.1c `_slot_na_pripravu` excludes it - the admission is gone
    and KNOWN_ISSUES lists it among the fixes. If the picture condition
    disappeared from the code, the test says that the sentences about it
    are no longer true."""
    kod = zdroj_metody("_slot_na_pripravu").split('"""')[-1]   # without the docstring
    vyraduje = "overlay_configs" in kod or "_ma_obrazok" in kod
    assert vyraduje
    privacy = _plain("PRIVACY.md")
    for meno in ("KNOWN_ISSUES.md", ZMENY):
        assert ("**A reminder whose in-game picture you've switched off** still "
                "has its line prepared") not in _plain(meno), meno
    assert "still counts as switched on, so its line is prepared" not in privacy
    opravy = " ".join(_sekcia(_read(ZMENY), "What 0.2.1 fixes").split())
    assert "of ones whose in-game picture is off" in opravy
    assert "Switching one or its picture on" in opravy


# --------------------------------------------------------------------------
# Heart rate port and UDP
# --------------------------------------------------------------------------

def test_privacy_port_menuje_ovladanie_ako_appka():
    p = _plain("PRIVACY.md")
    for kluc in ("settings.hr_enable_switch", "dnes.empty_btn",
                 "hr.pair_button", "settings.hr_ip_label"):
        assert _en(kluc) in p, kluc
    assert "*%s → %s*" % (_en("nav.vhre_short"),
                          _en("settings.hr_section_title")) in p
    assert "heart-rate sensor settings" not in p
    # The pairing guide turns the sensor on - PRIVACY says so.
    assert "self._enable_hr_monitoring()" in zdroj_metody("open_watch_pairing")
    # On UDP the app replies with nothing, on TCP it pretends to be OBS.
    assert "on UDP it replies nothing" in p
    assert "sendto" not in inspect.getsource(heart_rate)


def test_udp_stitok_a_log_v_dokumentoch_ako_v_kode():
    stitok = _en("settings.hr_status_udp_off")
    for meno in ("README.md", ZMENY):
        assert "*%s*" % stitok in _plain(meno), meno
    prepinac = _en("settings.hr_enable_switch")
    for meno in ("README.md", ZMENY):
        assert "switch *%s* off and on" % prepinac in _plain(meno), meno
    assert "**If UDP won't open**" in _plain("PRIVACY.md")
    assert "not your PC's address" in _plain("PRIVACY.md")

    # Code: its own kinds of state (TCP keeps running) and only the port and
    # the error go to app.log - not the `host` address.
    src = inspect.getsource(heart_rate.HeartRateMonitor._udp_loop)
    assert '"udp_busy"' in src and '"udp_error"' in src
    volania = [u for u in ast.walk(ast.parse(textwrap.dedent(src)))
               if isinstance(u, ast.Call) and getattr(u.func, "attr", "") == "warning"]
    assert len(volania) == 1
    mena = {n.id for a in volania[0].args for n in ast.walk(a)
            if isinstance(n, ast.Name)}
    assert mena == {"port", "exc"}, mena


def test_readme_check_sources_offline_ako_skript():
    import check_sources
    readme = _plain(VYVOJ)      # since 0.3d the developer scripts are here, not in the README
    assert ("it says you're offline, checks nothing and exits with 0 instead "
            "of reporting the links as dead") in readme
    main = inspect.getsource(check_sources.main)
    assert "if unreachable and not answered:" in main
    assert "sys.exit(0)" in main


# --------------------------------------------------------------------------
# KNOWN_ISSUES, SOUL, SAFETY
# --------------------------------------------------------------------------

def test_known_issues_bez_rozporov():
    k = _plain("KNOWN_ISSUES.md")
    assert "the game doesn't receive that one key combination" not in k
    assert "a game that uses that one key combination may not receive it" in k
    for meno in ("KNOWN_ISSUES.md", ZMENY):
        text = _plain(meno)
        assert "walking isn't filtered out yet" not in text, meno
        for stare in ("high-HR line", "strain threshold", "high heart-rate line",
                      "plain GPLv3", "your own high heart-rate limit"):
            assert stare not in text, (meno, stare)
        assert _read(meno).rstrip().endswith("· GPLv3"), meno
    opravy = _sekcia(_read(ZMENY), "What 0.2.1 fixes")
    for nadpis in ("### The online voice", "### Smaller fixes"):
        assert nadpis in opravy, nadpis
    # The language row: KNOWN_ISSUES says it no longer claims cue translation.
    assert _en("settings.language_sub") == "Cues you already have keep their wording."
    assert "cues you already have keep their wording" in _plain(ZMENY)


def test_chodza_len_stisi_hlasky_ucenie_ju_nevyraduje():
    """KNOWN_ISSUES: steps only silence cues, walking time is still learnt
    from. If learning ever excluded steps, the sentence in KNOWN_ISSUES
    has to go."""
    k = _plain("KNOWN_ISSUES.md")
    assert "Steps from the watch only keep cues quiet" in k
    for f in (hr_stats.dynamicky_kriticky, hr_stats.dynamicky_prah_zataze,
              hr_stats.dlhodoba_zakladna, hr_stats.ciste_relacie,
              hr_stats.HeartStats.summary):
        src = inspect.getsource(f)
        for slovo in ("steps", "_steps", "kroky", "note_metrics"):
            assert slovo not in src, (f.__name__, slovo)
    assert "steps_per_min" in zdroj_metody("_cue_can_fire")


def test_soul_hranica_a_licencia():
    s = _plain("SOUL.md")
    assert "your own high heart-rate limit" not in s
    assert hr_stats.KRITICKY_ZALOHA == 110.0
    assert "(at or above your high heart-rate limit — 110 BPM until the app has learned yours)" in s
    assert "under the GPLv3." in s
    assert "or later" not in s


def test_safety_harness_odklada_nastavenia_a_historiu_ako_skript():
    """Since 0.3d the details of the harness backups are in DEVELOPMENT.md
    (in English); SAFETY only says that the scripts move the mouse and the
    build does not package them, and a link here. The sentence follows the
    code: when the backup changes, the test says where."""
    skript = _read("gui_harness_auto.py")
    safety = _plain("SAFETY.md")
    vyvoj = _plain(VYVOJ)
    assert "](DEVELOPMENT.md)" in safety
    for subor in ("hr_sessions.json", "hr_insights.json", "hr_session_open.json"):
        assert '"%s"' % subor in skript, subor
        assert "`%s`" % subor in vyvoj, subor
    assert 'os.path.join(PROJ, "logs", "gui_harness")' in skript
    # Since 0.2.1c the backup is on disk next to the originals, not in memory
    # or in logs\gui_harness\ - and after a hard kill the next run restores
    # it (test_021c_harness_zaloha.py checks the behaviour).
    assert "_hr_backups" not in skript
    assert 'ZALOHA = ".pred-harnessom"' in skript
    assert "def obnov_po_prerusenom_behu" in skript
    assert '"%s.pred-obnovou-%s"' in skript
    assert "drží len v pamäti" not in safety
    assert "(zálohu dá do `logs\\gui_harness\\`)" not in safety
    assert "only in memory" not in vyvoj
    assert "copies these files to disk next to the originals (`*.pred-harnessom`)" in vyvoj
    assert "after an interruption too (Ctrl+C, a closed window, a crash)" in vyvoj
    assert "`*.pred-obnovou-<time>`" in vyvoj
