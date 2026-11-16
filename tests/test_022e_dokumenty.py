# -*- coding: utf-8 -*-
"""The documents after batch 4 (0.3) say what the code does.

  * CHANGELOG.md: the version history moved out of KNOWN_ISSUES.md (audit,
    part 1); the 0.3 section has the batch 4 item ("Fewer dead ends") with
    names from the UI and numbers from the code,
  * KNOWN_ISSUES.md: only open items now - and every new sentence is tied
    to the code so that it disappears after the fix (licence, icon, GIF,
    the "Watch ..." headings in the pairing guide, the fixed font in the
    tour, things checked only on simulated data, the watch table and
    requirements, batch 4b),
  * README: the main switch in Quick start, the dialog on the first ×, the
    shortcut in Settings, links to CHANGELOG,
  * PRIVACY: hr_session_pending.json among the local files, "Try again",
  * SAFETY: keyboard layouts and network adapters in the full list,
  * HOW-IT-WORKS: "Not now", Today and the side panel, sessions, the
    address in the guide,
  * gui_screenshots.py: the demo data add up (number of cues = triangles,
    evening 18-23 h), the --lang and --okno options are described in
    DEVELOPMENT.md,
  * the images in the README have no metadata (EXIF/XMP/text chunks).

Whole paragraphs are deliberately not pinned - only names from the UI,
numbers from the code and sentences that stop being true once the code
changes.
"""
import ast
import math
import os
import random
import re
import struct
import sys
import time
import types

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import heart_rate  # noqa: E402
import hotkey  # noqa: E402
import hr_stats  # noqa: E402
import i18n  # noqa: E402
import overlay  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

ZMENY = "CHANGELOG.md"
AKO = "docs/HOW-IT-WORKS.md"


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


def _sk(kluc):
    return i18n.STRINGS[kluc]["sk"]


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


def _cislo(subor, meno):
    """Number from an assignment `meno = 123.0` in source (no Tk import)."""
    m = re.search(r"^\s*%s = ([\d.]+)\s*$" % meno, zdroj_suboru(subor), re.M)
    assert m, (subor, meno)
    return float(m.group(1))


def _predvolby():
    """Shortcut defaults the way the docs write them: "Ctrl+Alt+Z, ..."."""
    mena = [hotkey.format_combo(p).replace(" ", "") for p in hotkey.PRESETS]
    return ", ".join(mena[:-1]) + ", " + mena[-1]


# --------------------------------------------------------------------------
# CHANGELOG: the batch 4 section
# --------------------------------------------------------------------------

def _davka4():
    c = _read(ZMENY)
    s022 = c[c.index("## What 0.3 changes"):c.index("## What 0.2.1 fixes")]
    assert s022.index("### Words and looks") < s022.index("### Fewer dead ends")
    return _plain_text(s022[s022.index("### Fewer dead ends"):])


def test_changelog_davka_4_menuje_ovladace_ako_appka():
    d4 = _davka4()
    for kluc in ("dock.start", "dock.stop", "history.delete_session.btn"):
        assert "**%s**" % _en(kluc) in d4, kluc
    for kluc in ("tray.keep_running", "tray.quit_app", "settings.snooze_hotkey",
                 "settings.snooze_hotkey_none", "nav.nastavenia", "nav.search",
                 "nav.vhre_short", "nav.watch", "nav.vhre_work_short",
                 "dnes.empty_btn", "dnes.zones_empty", "history.detail_title",
                 "data.delete.btn", "data.delete.export_first", "common.cancel",
                 "data.delete.stop_first", "data.title", "data.open_folder.btn",
                 "settings.engine", "common.retry", "common.prepare_voices",
                 "hr.ip_virtual", "settings.hr_ip_label", "common.save",
                 "session.end.skip", "history.rhythm_title", "settings.cue_style",
                 "settings.audio_volume_title"):
        assert "*%s*" % _en(kluc) in d4, kluc
    assert "*%s*" % _en("dnes.learning", n=1, celkom=hr_stats.KRITICKY_MIN_RELACII) in d4
    assert "*%s*" % _en("kamae.port_busy", port=heart_rate.DEFAULT_PORT) in d4
    # dock.start uses the same words as the tray, just with the marker
    assert _en("dock.start") == "▶ " + _en("tray.start")
    assert _en("dock.stop") == "■ " + _en("tray.stop")


def test_changelog_davka_4_cisla_su_z_kodu():
    d4 = _davka4()
    assert _cislo("app_session.py", "MEDZERA_SPANKU_S") == 120.0
    assert "for more than two minutes" in d4
    assert hr_stats.MAX_SESSIONS == 400 and "the 400-session limit" in d4
    assert _cislo("app_history.py", "RYTMUS_MIN_TYZDNOV") == 8
    assert _cislo("app_history.py", "RYTMUS_MAX_TYZDNOV") == 26
    assert "(8 to 26)" in d4
    assert _predvolby() + " or *%s*" % _en("settings.snooze_hotkey_none") in d4
    assert "`%s`" % hr_stats.CAKAJUCA_MENO in d4
    # questionnaire on exit: touched answers as Save, otherwise as Skip
    assert "*%s*" % _en("common.save") in d4 and "*%s*" % _en("session.end.skip") in d4


# --------------------------------------------------------------------------
# KNOWN_ISSUES: only open items, each tied to the code
# --------------------------------------------------------------------------

def _otvorene():
    return _plain_text(_sekcia(_read("KNOWN_ISSUES.md"), "Still open"))


def test_known_issues_odkazuje_na_changelog():
    k = _read("KNOWN_ISSUES.md")
    uvod = k[:k.index("\n## Still open")]
    assert "](CHANGELOG.md)" in uvod
    # nothing batch 4 fixed is claimed as open any more
    o = _otvorene()
    assert "can't be changed in the app" not in o
    assert "Windows' own boxes" not in _plain_text(k)
    assert "tray icon's menu" in o


def test_known_issues_licencia_ikona_a_gif():
    """Licence: the author decided (2026-11-15) "GPLv3" - version 3 only. The
    app and all the documents say the same; "or later" stays only in the
    0.2 history in CHANGELOG and in the change record. The icon and the GIF
    are waiting for the author."""
    o = _otvorene()
    licencia = re.search(r'^LICENCIA = "([^"]+)"', zdroj_suboru("app.py"), re.M)
    assert licencia and licencia.group(1) == "GPLv3"
    for meno in ("README.md", "KNOWN_ISSUES.md", "PRIVACY.md", "SOUL.md",
                 "LICENSE-DESIGN.md", "SAFETY.md", "DEVELOPMENT.md"):
        assert "or later" not in _plain(meno), meno
    assert "code under GPLv3*" in _read("README.md")
    assert "Licence wording" not in o
    zmeny = _plain_text(_sekcia(_read("CHANGELOG.md"), "What 0.3 changes"))
    assert "everything says GPLv3 (version 3 of the GNU GPL)" in zmeny
    # Since 2026-11-15 the icon question is in LICENSE-DESIGN.md, in the "What
    # stays mine" part (the author's decision) - the README only links to that
    # page now.
    ikona = _plain_text(_sekcia(_read("LICENSE-DESIGN.md"), "2. What stays mine"))
    assert "One thing isn't sorted out yet" in ikona
    assert "`Dandurf.ico`" in ikona and "`make_icon.py`" in ikona
    assert "isn't sorted out yet" not in _plain("README.md")
    assert "](LICENSE-DESIGN.md)" in _sekcia(_read("README.md"), "License")
    assert "`Dandurf.ico`" in o and "`make_icon.py`" in o
    assert "[LICENSE-DESIGN.md](LICENSE-DESIGN.md)" in o
    assert "*License* in the README" not in o
    obrazky = os.listdir(os.path.join(ROOT, "docs", "img"))
    assert not [f for f in obrazky if f.lower().endswith(".gif")]
    assert "No clip of a cue over a game yet." in o


def test_known_issues_otvorene_texty_su_v_appke():
    """Every sentence is tied to a text in the app: once it is fixed, the
    test says the KNOWN_ISSUES item has to go."""
    o = _otvorene()
    # Batch 4b fixed: the page name by world ({page}), "phone connected",
    # a single sentence on a busy port, the dialog frame and ja/zh wrapping -
    # KNOWN_ISSUES no longer presents these as open.
    assert "{page}" in _en("history.empty")
    assert "*%s*" % _en("nav.vhre_work_short") not in o
    for kluc in ("dnes.hr_connected", "settings.hr_status_waiting"):
        assert _en(kluc).startswith(("phone", "Phone")), kluc
        assert "*%s*" % _en(kluc) not in o, kluc
    assert "dialogs have no border" not in o
    assert "Japanese and Chinese lines wrap" not in o
    assert "pairing sentence under the busy message" not in o
    # the box headings in the pairing guide still name the watch, even
    # though it is the phone (the app on it) that connects
    for kluc in ("hr.noconnect_title", "hr.trouble_title"):
        assert _en(kluc).startswith("Watch"), kluc
        assert "*%s*" % _en(kluc) in o, kluc
    # the empty History has no variant for Work: even there it says "play"
    assert "play for at least a minute" in _en("history.empty")
    assert not [k for k in i18n.STRINGS if k.startswith("history.empty_w")]
    assert 'tr("history.empty", page=' in zdroj_suboru("app_history.py")
    assert "History without sessions still asks you to play" in o
    # the session trace in History: only the play sentence (only the
    # questionnaire has a Work variant)
    historia = zdroj_suboru("app_history.py")
    assert 'tr("session.end.trace_hint")' in historia
    assert "trace_hint_work" not in historia
    assert "trace_hint_work" in zdroj_suboru("ui_dialogs.py")
    assert "*One session up close* still says when you were probably playing" in o
    # fixed Latin font: the tour bubbles and the Ctrl+K command palette list
    assert 'font=("Segoe UI"' in zdroj_suboru("guided_tour.py")
    assert 'tkfont.Font(family="Segoe UI"' in zdroj_suboru("ui_shell.py")
    assert "bubbles and the Ctrl+K list still use a fixed Latin font" in o
    assert "tested only with simulated data" in o


def test_known_issues_skratka_sa_riadi_odpovedou_windowsu():
    """Batch 4b: the shortcut row and the journal wait for the real result of
    the registration (`on_result`), so they no longer claim "another program
    holds it" when Windows is just slow. All that remains is that until
    Windows answers, the row shows the usual text ("works")."""
    o = _otvorene()
    assert "another app holds the shortcut even though it works" not in o
    assert "line and the log follow Windows' answer" in o
    assert hotkey.GlobalHotkey.CAKAJ_NA_REGISTRACIU_S == 2.0
    assert "more than two seconds" in o
    # while waiting, the row has no text of its own like "registering..."
    sub = zdroj_metody("_snooze_hotkey_sub")
    assert "_hotkey_caka" not in sub and "_hotkey_zlyhala" in sub
    assert "self._hotkey_caka = True" in zdroj_suboru("app.py")


def test_known_issues_watch_tabulka_a_poziadavky_cakaju_na_autora():
    """The author filled in the watch model (2026-11-15: Samsung Galaxy
    Watch7) and measured the system requirements again on the 0.3 build
    (2026-11-15), so the KNOWN_ISSUES item about old numbers is gone. 0.3.2
    names its own ZIP for the size, while RAM and CPU say they were measured
    on 0.3 (neither 0.3.1 nor 0.3.2 was measured again), and the sentence
    names what 0.3.2 adds that can cost more: the breath ring at high heart
    rate, redrawn about 25 times a second while it shows
    (`overlay._SlotOverlay.TICK_MS`)."""
    o = _otvorene()
    readme = _read("README.md")
    tabulka = _sekcia(readme, "Getting your heart rate in")
    assert "| Wear OS watch with an Android phone |" in tabulka
    assert "Tested by me on a Samsung Galaxy Watch7 |" in tabulka
    assert "tested: a Samsung Galaxy Watch7 with an Android phone" in _plain_text(readme)
    assert "doesn't name my watch" not in o
    poziadavky = _plain_text(_sekcia(readme, "System requirements"))
    assert "the 0.3.2 ZIP is about 60 MB" in poziadavky
    # The download size is written twice (Install and System requirements).
    # When a new build changes it, both places must change together, and the
    # unpacked size must stay next to it.
    instalacia = _plain_text(_sekcia(readme, "Install"))
    v_instalacii = re.search(
        r"`Zanshin-0\.3\.2-windows\.zip`, about (\d+) MB\)", instalacia)
    v_poziadavkach = re.search(
        r"the 0\.3\.2 ZIP is about (\d+) MB to download and about (\d+) MB "
        r"unpacked", poziadavky)
    assert v_instalacii and v_poziadavkach, (v_instalacii, v_poziadavkach)
    assert v_instalacii.group(1) == v_poziadavkach.group(1)
    assert "while watching with heart rate coming in" in poziadavky
    assert "Zanshin 0.3 used about 170 MB of RAM" in poziadavky
    assert "I haven't measured 0.3.1 or 0.3.2 again:" in poziadavky
    # what 0.3.2 adds that runs while it shows, and that it wasn't measured
    assert 1000 // overlay._SlotOverlay.TICK_MS == 25
    assert ("0.3.2 adds the breath ring at high heart rate (off by default), "
            "which is redrawn about 25 times a second for as long as it shows; "
            "what that costs I haven't measured.") in poziadavky
    assert "The system requirements are from 0.2.1." not in o


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------

def test_readme_quick_start_hlavny_vypinac_a_prvy_krizik():
    readme = _read("README.md")
    qs = _plain_text(_sekcia(readme, "Quick start"))
    assert "**%s** at the top of *Today*" % _en("dock.start") in qs
    for kluc in ("tray.keep_running", "tray.quit_app", "tray.quit"):
        assert "**%s**" % _en(kluc) in qs, kluc
    zavri = zdroj_metody("on_close")
    assert '("tray", tr("tray.keep_running"), "primary")' in zavri
    assert '("quit", tr("tray.quit_app"), "secondary")' in zavri
    assert 'default="tray"' in zavri


def test_readme_odkazuje_na_changelog_a_nove_veci():
    readme = _read("README.md")
    hore = readme[:readme.index("\n## Quick start")]
    assert "[Changelog](CHANGELOG.md)" in hore
    assert "](CHANGELOG.md#what-032-changes)" in hore
    assert "\n## What 0.3.2 changes\n" in _read("CHANGELOG.md")   # that anchor
    assert "](CHANGELOG.md)" in _sekcia(readme, "Known issues")
    assert "KNOWN_ISSUES.md#" not in readme
    r = _plain_text(readme)
    assert "**%s**" % _en("data.open_folder.btn") in r
    t = _plain_text(_sekcia(readme, "Troubleshooting"))
    assert "**%s**" % _en("history.delete_session.btn") in t
    assert "*%s*" % _en("common.retry") in t
    assert "*%s*" % _en("kamae.port_busy", port=heart_rate.DEFAULT_PORT) in r
    # Anti-cheat: the app asks for keyboard layouts and network adapters
    uvod = _plain_text(hore)
    assert "keyboard layouts" in uvod and "network adapters" in uvod
    assert "GetKeyboardLayoutList" in _read("hotkey.py")
    assert "GetAdaptersAddresses" in _read("netinfo.py")


# --------------------------------------------------------------------------
# PRIVACY and SAFETY
# --------------------------------------------------------------------------

def test_privacy_cakajuca_relacia_je_lokalny_subor():
    p = _read("PRIVACY.md")
    lokalne = _plain_text(p[:p.index("## The few things that can use the network")])
    assert hr_stats.CAKAJUCA_MENO == "hr_session_pending.json"
    assert "`hr_session_pending.json`" in lokalne
    # "Delete history" deletes it too - PRIVACY says so about the files above
    assert ("data.delete.pending_session", hr_stats.CAKAJUCA_MENO) in data_io.MAZATELNE
    assert "**%s** there deletes the session, insight and measurement files" % (
        _en("data.delete.btn")) in lokalne
    assert "**%s**" % _en("data.open_folder.btn") in lokalne


def test_privacy_skusit_znova_je_ako_ctrl_k():
    p = _plain("PRIVACY.md")
    assert "*%s* under *%s*" % (_en("common.retry"), _en("settings.engine")) in p
    # the same as Ctrl+K -> Prepare the cue voice: `pregenerate`, which sends
    # nothing while watching
    assert "self.pregenerate(force=True)" in zdroj_metody("skus_hlas_znova")
    assert "*%s*" % _en("common.prepare_voices") in p


def test_safety_uplny_zoznam_ma_rozlozenia_a_adaptery():
    s = _read("SAFETY.md")
    anglicky = _plain_text(s[:s.index("## Krátka odpoveď")])
    assert "keyboard layouts" in anglicky and "network adapters" in anglicky
    assert "Ctrl+Alt+Z by default" in anglicky
    zoznam = _plain_text(s[s.index("### Úplný zoznam"):])
    for api in ("GetKeyboardLayoutList", "ToUnicodeEx", "GetAdaptersAddresses"):
        assert "`%s`" % api in zoznam, api
    hk = _read("hotkey.py")
    assert "GetKeyboardLayoutList" in hk and "ToUnicodeEx" in hk
    # ToUnicodeEx gets a made-up key state, the real one is not read
    assert "GetKeyboardState" not in hk and "GetAsyncKeyState" not in hk
    cele = _plain_text(s)
    assert "„%s“" % _sk("settings.snooze_hotkey") in cele
    assert "„%s“" % _sk("settings.snooze_hotkey_none") in cele
    assert "„%s“" % _sk("hr.ip_virtual") in cele
    assert "v appke na to prepínač zatiaľ nie je" not in cele


# --------------------------------------------------------------------------
# HOW-IT-WORKS
# --------------------------------------------------------------------------

def test_how_it_works_ma_sekcie_davky_4():
    nadpisy = [r[3:].strip() for r in _read(AKO).splitlines() if r.startswith("## ")]
    for nadpis in ('"Not now"', "Today and the sidebar", "Your sessions",
                   "Which address the pairing guide shows"):
        assert nadpis in nadpisy, nadpis


def test_how_it_works_cisla_a_nazvy_z_kodu():
    a = _plain(AKO)
    assert _predvolby() + " or *%s*" % _en("settings.snooze_hotkey_none") in a
    assert "Settings → General → *%s*" % _en("settings.snooze_hotkey") in a
    for kluc in ("dock.start", "dock.stop"):
        assert "**%s**" % _en(kluc) in a, kluc
    assert "*%s*" % _en("kamae.port_busy", port=heart_rate.DEFAULT_PORT) in a
    assert heart_rate.HeartRateMonitor.STALE_AFTER_S == 12.0
    assert "nothing for 12 seconds" in a
    assert _cislo("app_session.py", "MEDZERA_SPANKU_S") == 120.0
    assert "stop for more than two minutes" in a
    assert hr_stats.MAX_SESSIONS == 400 and "History keeps the last 400" in a
    assert "(at least 8, at most 26)" in a
    assert "*%s*" % _en("dnes.learning", n=1, celkom=hr_stats.KRITICKY_MIN_RELACII) in a
    for kluc in ("hr.ip_virtual", "settings.hr_ip_label", "common.retry",
                 "data.delete.export_first", "nav.vhre_work_short", "nav.watch"):
        assert "*%s*" % _en(kluc) in a, kluc


def test_how_it_works_cakajuca_relacia_sa_neuci():
    a = _plain(AKO)
    assert "`%s`" % hr_stats.CAKAJUCA_MENO in a
    assert "it doesn't feed what Zanshin learns" in a
    zaklad = {"duration_s": 900.0, "baseline_bpm": 70.0, "max_bpm": 95.0}
    assert hr_stats.ciste_relacie([dict(zaklad, recovered=True)]) == []
    assert "summary[\"recovered\"] = True" in zdroj_suboru("hr_stats.py")


def test_how_it_works_svet_relacie_plati_aj_pre_pripomienky():
    a = _plain(AKO)
    assert "the new world applies from the next time you start watching" in a
    assert "_session_world" in zdroj_metody("_hlasky_hovoria")
    assert "log.world_switch_session" in i18n.STRINGS


# --------------------------------------------------------------------------
# gui_screenshots.py and the images in the README
# --------------------------------------------------------------------------

def _funkcia_zo_skriptu(meno, **globaly):
    """One function from gui_screenshots.py without running the script (on
    import it builds the app window and backs up the data)."""
    strom = ast.parse(_read("gui_screenshots.py"))
    uzol = next(u for u in strom.body
                if isinstance(u, ast.FunctionDef) and u.name == meno)
    modul = ast.Module(body=[uzol], type_ignores=[])
    ns = dict(globaly)
    exec(compile(modul, "gui_screenshots.py", "exec"), ns)
    return ns[meno]


def test_demo_data_pocet_pripomienok_sedi_s_trojuholnikmi(tmp_path):
    """Audit: the number of cues and the ▼ in the curve were randomised
    separately ("HLÁŠKY 0" with three ▼) and the sessions started in the
    morning, even though the chart talks about the evening."""
    for semienko in (7, 1, 23):
        app = types.SimpleNamespace()
        historia = _funkcia_zo_skriptu(
            "historia", random=random.Random(semienko), math=math, time=time,
            hr_stats=hr_stats, json=__import__("json"), os=os,
            PROJ=str(tmp_path), app=app)
        relacie = historia()
        assert len(relacie) > 20
        assert (tmp_path / "hr_sessions.json").exists()
        for s in relacie:
            n = len(s["trigger_offsets_s"])
            assert s["triggers"] == s["auto_triggers"] == n, s["started"]
            assert 0 <= n <= 4
            assert all(0 <= o <= s["duration_s"] for o in s["trigger_offsets_s"])
            hodina = time.localtime(s["started"]).tm_hour
            assert 18 <= hodina < 23, (semienko, time.ctime(s["started"]))


def test_gui_screenshots_volby():
    import argparse
    argumenty = _funkcia_zo_skriptu(
        "_argumenty", argparse=argparse, os=os, PROJ="koren",
        LANGUAGES=i18n.LANGUAGES)
    a = argumenty([])
    assert a.lang is None and a.okno is False
    assert a.out == os.path.join("koren", "logs", "gui_screenshots")
    a = argumenty(["C:\\inam", "--lang", "en", "--okno"])
    assert (a.out, a.lang, a.okno) == ("C:\\inam", "en", True)
    assert argumenty(["--window"]).okno is True
    try:
        argumenty(["--lang", "xx"])
    except SystemExit:
        pass
    else:
        raise AssertionError("neznamy jazyk musi skoncit pred zalohou")
    src = _read("gui_screenshots.py")
    # the options are read BEFORE the files are backed up
    assert src.index("ARGS = _argumenty(") < src.index("ZALOHOVAT = [")
    assert '"hr_session_pending.json"' in src
    d = _plain("DEVELOPMENT.md")
    for volba in ("--lang", "--okno", "--window"):
        assert "`%s`" % volba in d, volba
    assert "`17_relacia_zblizka.png`" in d and "17_relacia_zblizka" in src
    assert "`hr_session_pending.json`" in d


def _png_bloky(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    i, typy = 8, []
    while i < len(data):
        dlzka = struct.unpack(">I", data[i:i + 4])[0]
        typy.append(data[i + 4:i + 8].decode("ascii"))
        i += 12 + dlzka
    return typy


def _webp_bloky(data):
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    i, typy = 12, []
    while i + 8 <= len(data):
        typy.append(data[i:i + 4].decode("ascii"))
        dlzka = struct.unpack("<I", data[i + 4:i + 8])[0]
        i += 8 + dlzka + (dlzka & 1)
    return typy


def test_obrazky_v_readme_su_bez_metadat():
    readme = _read("README.md")
    priecinok = os.path.join(ROOT, "docs", "img")
    with open(os.path.join(priecinok, "history-session.png"), "rb") as fh:
        png = _png_bloky(fh.read())
    with open(os.path.join(priecinok, "today.webp"), "rb") as fh:
        webp = _webp_bloky(fh.read())
    assert png[0] == "IHDR" and png[-1] == "IEND"
    assert not {"tEXt", "iTXt", "zTXt", "eXIf", "iCCP", "tIME"} & set(png), png
    assert not {"EXIF", "XMP ", "ICCP"} & set(webp), webp
    for meno in ("docs/img/today.webp", "docs/img/history-session.png"):
        assert "](%s)" % meno in readme, meno
