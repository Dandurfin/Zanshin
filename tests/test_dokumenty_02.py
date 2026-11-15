# -*- coding: utf-8 -*-
"""Documents and the 0.2 installer say what the code and the build do.

  * README: port 4455 listens on all of the PC's networks (not "on the
    local network"), the installer is named exactly as Dandurf.iss names
    it, and the calibration minimums match `hr_stats`.
  * The highest heart rate zone is "Peak" / "Špička" in the documents.
  * Voice preparation never goes to Microsoft while listening.
  * ZDROJE.md does not claim that the app itself finds out whether cues
    help.
  * The developer GUI scripts are mentioned and the build does not
    package them.
  * KNOWN_ISSUES: the repository starts at 0.2, without details about
    working notes (since 0.3, batch 4, the version history is in
    CHANGELOG.md).
  * Dandurf.iss: the version in the Details of setup.exe and
    [InstallDelete] only for files from 0.1 in {app}.
  * LICENSE-DESIGN.md: the CC0 sounds are bundled, not downloaded.
  * 0.2.1: the module table covers everything the build packages, the
    developer scripts are described, and the numbers in README / SAFETY /
    PRIVACY / KNOWN_ISSUES (caps, time limits, date range) are the ones
    from the code.

0.3d (audit "Tests lock the README's length"): the exact long sentences
moved together with the text - the rules to docs/HOW-IT-WORKS.md, modules,
scripts and the build to DEVELOPMENT.md. The guard goes with the sentence,
not with the README; the README keeps only the essentials (port,
installation, Peak, "watching").
"""
import ast
import hashlib
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import sfx_assets  # noqa: E402
from _zdroj_appky import zdroj_metody  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

DOKUMENTY = ("README.md", "SOUL.md", "PRIVACY.md", "SAFETY.md",
             "KNOWN_ISSUES.md", "CHANGELOG.md", "ZDROJE.md", "DEVELOPMENT.md",
             "docs/HOW-IT-WORKS.md", "docs/PRIOR_ART.md")
# The version history (what each version fixed) is in CHANGELOG.md since
# 0.3 (batch 4) - the guards for those sentences go there.
ZMENY = "CHANGELOG.md"
# Where the details from the README moved in 0.3d (the app's rules and the
# developer part) - the guards follow the sentence.
AKO = "docs/HOW-IT-WORKS.md"
VYVOJ = "DEVELOPMENT.md"
GUI_SKRIPTY = ("gui_harness_auto.py", "gui_harness_onboarding.py",
               "gui_screenshots.py")


def _read(meno):
    # utf-8-sig: Dandurf.iss has a BOM
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(meno):
    """Text without line breaks - sentences in .md are wrapped anywhere."""
    return " ".join(_read(meno).split())


# --------------------------------------------------------------------------
# README: port, installer, calibration
# --------------------------------------------------------------------------

def test_readme_port_pocuva_na_vsetkych_sietach():
    r = _plain("README.md")
    assert "listens on your local network" not in r
    assert "listens on **every network your PC is connected to**" in r
    assert "**without a password**" in r
    for meno in ("README.md", "PRIVACY.md"):
        assert "only listens on your local network" not in _plain(meno), meno
        # An address the PC does not have falls back to all interfaces
        # (`heart_rate._bind`, log.hr_bind_fallback) - the document says so.
        assert "one specific address" not in _plain(meno), meno
        assert "one of this PC's own addresses" in _plain(meno), meno
        assert "the log says so" in _plain(meno), meno


def _vydana_verzia(verzia):
    zmeny = _read(ZMENY)
    if "\n## What %s changes (not released yet)\n" % verzia not in zmeny:
        return verzia
    nadpisy = re.findall(r"^## What (\d+(?:\.\d+){1,3}) ", zmeny, re.M)
    assert len(nadpisy) >= 2 and nadpisy[0] == verzia, (
        "CHANGELOG.md: the unreleased %s must be the first section, followed "
        "by the last release: %r" % (verzia, nadpisy))
    return nadpisy[1]


def test_readme_vedie_k_buildu_nie_k_instalatoru():
    """The installer is not released (the author's decision, 0.2.1): the
    player gets either a ready ZIP from Releases with a SHA-256
    fingerprint, or builds the app themselves via build.bat. The README
    does not send them to download setup.exe. If the README does mention
    the installer's name after all (e.g. a developer with Inno Setup), it
    must match the .iss."""
    iss = _read("Dandurf.iss")
    verzia = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss).group(1)
    zaklad = re.search(r"^OutputBaseFilename=(.+)$", iss, re.M).group(1).strip()
    subor = zaklad.replace("{#MyAppVersion}", verzia) + ".exe"
    readme = _read("README.md")
    instal = _sekcia(readme, "Install")
    assert "setup.exe" not in instal
    assert "Zanshin-%s-windows.zip" % _vydana_verzia(verzia) in instal
    assert "Get-FileHash" in instal
    assert "`build.bat`" in instal
    assert "dist\\Zanshin\\Zanshin.exe" in instal
    for meno in re.findall(r"Zanshin-[\w.<>]+-setup\.exe", readme):
        assert meno == subor, meno
    assert "installer/Zanshin" not in readme


def _relacia(sekundy):
    krivka = [70 + 15 * math.sin(i / 7.0) for i in range(120)]
    return {"duration_s": float(sekundy), "curve": krivka,
            "baseline_bpm": 70.0, "max_bpm": 90.0}


def test_readme_minima_kalibracie_sedia_s_kodom():
    """HOW-IT-WORKS (before 0.3d the README): "three of about ten minutes are
    enough, three of five are not" and "roughly half an hour of heart
    rate" - recomputed by the code. The README in short: limits only from
    play sessions of five minutes and more."""
    assert hr_stats.PRAH_MIN_RELACII == 3
    assert hr_stats.KRITICKY_MIN_RELACII == 3
    assert hr_stats.DLHODOBA_MIN_RELACII == 3
    assert hr_stats.PRAH_MIN_TRVANIE_S == 300.0
    prah = hr_stats.dynamicky_prah_zataze
    assert prah([_relacia(600)] * 3, baseline=70.0, critical=110) is not None
    assert prah([_relacia(300)] * 3, baseline=70.0, critical=110) is None
    assert prah([_relacia(900)] * 2, baseline=70.0, critical=110) is None
    for meno in ("README.md", AKO):
        assert "three of at least five minutes" not in _plain(meno), meno
    assert "only from play sessions of five minutes or more" in _plain("README.md")
    r = _plain(AKO)
    assert "three play sessions of five minutes or more" in r
    assert "roughly half an hour of heart rate" in r
    assert "three of about ten minutes are enough, three of five are not" in r


# --------------------------------------------------------------------------
# The Špička / Peak zone
# --------------------------------------------------------------------------

STARE_PASMO = re.compile(r"critical zone|kritick\w* pásm|pásm\w* kritick",
                         re.IGNORECASE)


def test_dokumenty_menuju_pasmo_po_novom():
    for meno in DOKUMENTY:
        assert not STARE_PASMO.search(_plain(meno)), meno
    for meno in ("README.md", "SOUL.md", ZMENY, AKO):
        assert "Peak zone" in _plain(meno), meno
    assert "pásme Špička" in _plain("ZDROJE.md")


# --------------------------------------------------------------------------
# Voice preparation and the voice / picture comparison
# --------------------------------------------------------------------------

def test_priprava_hlasu_nikdy_pocas_pocuvania():
    """Since 0.3d the main switch is "watching" (the app's vocabulary) - the
    documents call it the same. The README says it once, in the privacy
    paragraph; the exception (a sentence already on its way still gets
    sent) is in HOW-IT-WORKS and PRIVACY."""
    readme = _plain("README.md")
    assert readme.count("Nothing new is prepared while Zanshin is watching") == 1
    ako = _plain(AKO)
    assert "**Nothing new is prepared while Zanshin is watching**" in ako
    assert "a line already on its way when watching starts is finished" in ako
    assert "On the very first start" in ako
    privacy = _plain("PRIVACY.md")
    assert "**Never while Zanshin is watching**" in privacy
    assert "only the line already on its way is finished" in privacy
    assert "**On the very first start**" in privacy
    assert "Never because a reminder fired during play" not in privacy
    # the old word for the main switch does not come back
    for meno, text in (("README.md", readme), (AKO, ako), ("PRIVACY.md", privacy)):
        for stare in ("while Zanshin is listening", "when listening starts",
                      "stop listening", "start listening", "listening stops"):
            assert stare not in text.lower(), (meno, stare)


def test_cesta_k_hlasu_je_nastavenia_zvuk():
    """The tab in Settings is called "Sound" (nav.nastavenia_tabs.zvuk);
    "Sound / Audio" is only an item of the Ctrl+K palette."""
    import i18n
    assert i18n.STRINGS["nav.nastavenia_tabs.zvuk"]["en"] == "Sound"
    assert i18n.STRINGS["settings.engine"]["en"] == "Voice source"
    for meno in ("README.md", "PRIVACY.md"):
        assert "Sound / Audio" not in _plain(meno), meno
    assert "Settings → Sound" in _plain("README.md")
    assert _plain("PRIVACY.md").count("Settings → Sound → Voice source") == 2


def test_ziadny_dokument_netvrdi_ze_appka_uz_porovnava():
    zdroje = _plain("ZDROJE.md")
    assert "zisťuje appka sama" not in zdroje
    assert "Samotné porovnanie zatiaľ neukazuje" in zdroje
    for meno in ("README.md", AKO):
        assert "so the app can compare whether the cues help" not in _plain(meno), meno
    assert "doesn't show that comparison yet" in _plain(AKO)
    for meno in ("KNOWN_ISSUES.md", ZMENY):
        assert "finds out whether cues help" not in _plain(meno), meno


# --------------------------------------------------------------------------
# Developer GUI scripts
# --------------------------------------------------------------------------

def test_gui_skripty_su_spomenute_a_build_ich_nebali():
    # Since 0.3d the developer scripts are in DEVELOPMENT.md (the README
    # links to it); SAFETY keeps their names, because they move the real
    # mouse.
    for meno in GUI_SKRIPTY:
        assert os.path.isfile(os.path.join(ROOT, meno)), meno
        for doc in (VYVOJ, "SAFETY.md"):
            assert meno in _read(doc), (doc, meno)
    assert "](DEVELOPMENT.md)" in _read("README.md")
    spec = _read("Dandurf.spec")
    assert re.search(r"Analysis\(\s*\['main\.py'\]", spec)
    skryte = spec[spec.index("hiddenimports=["):spec.index("hookspath=")]
    assert "gui_" not in skryte
    import_gui = re.compile(
        r"^\s*(?:import|from)\s+(?:gui_harness\w*|gui_screenshots)\b", re.M)
    for f in os.listdir(ROOT):
        if f.endswith(".py") and f not in GUI_SKRIPTY:
            assert not import_gui.search(_read(f)), f


# --------------------------------------------------------------------------
# KNOWN_ISSUES
# --------------------------------------------------------------------------

def test_known_issues_vysvetli_historiu_bez_detailov():
    """0.1 is in the repository history without things that did not belong in
    public - KNOWN_ISSUES says so in general terms (the author's decision
    24. 9.), without details."""
    k = _plain(ZMENY)
    assert "**About 0.1 in this repository's history.**" in k
    assert "work stays work, private stays private" in k
    assert k.index("About 0.1 in this repository's history") < k.index(
        "## What 0.1 got wrong")
    for zle in ("Working notes", "history on GitHub", "tester",
                "folders on my PC", "prototypes"):
        assert zle not in k, zle
    # log.safe_mode no longer says "no blocking" - the point about the
    # shortcut must not claim it
    for meno in ("KNOWN_ISSUES.md", ZMENY):
        assert "The anti-cheat log line says input is read with" not in _plain(meno)
        for zle in ("Working notes", "history on GitHub", "tester"):
            assert zle not in _plain(meno), (meno, zle)


# --------------------------------------------------------------------------
# Dandurf.iss
# --------------------------------------------------------------------------

def test_setup_exe_ma_verziu_v_podrobnostiach():
    iss = _read("Dandurf.iss")
    setup = iss[iss.index("\n[Setup]\n"):iss.index("\n[Languages]\n")]
    assert re.search(r"^VersionInfoVersion=\{#MyAppVersion\}$", setup, re.M)
    # Inno fills missing numbers with zeros: "0.2.1" -> 0.2.1.0, the same as
    # filevers in version_info.txt.
    verzia = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss).group(1)
    assert re.fullmatch(r"\d+(\.\d+){0,3}", verzia), verzia
    cisla = [int(x) for x in verzia.split(".")] + [0] * 4
    m = re.search(r"filevers=\((\d+), (\d+), (\d+), (\d+)\)",
                  _read("version_info.txt"))
    assert [int(x) for x in m.groups()] == cisla[:4]


def test_instalator_zmaze_len_subory_z_01_v_app():
    iss = _read("Dandurf.iss")
    sekcia = iss[iss.index("\n[InstallDelete]"):]
    sekcia = sekcia[:sekcia.index("\n[", 1)]
    zaznamy = [r for r in sekcia.splitlines() if r.startswith("Type:")]
    mena = [re.search(r'Name: "([^"]+)"', r).group(1) for r in zaznamy]
    assert "{app}\\_internal\\assets\\images\\dojo_band.jpg" in mena
    assert "{app}\\_internal\\assets\\guides\\README.txt" in mena
    for riadok, meno in zip(zaznamy, mena):
        assert meno.startswith("{app}\\_internal\\assets\\"), meno
        assert "*" not in meno and "filesandordirs" not in riadok, riadok
    # 0.2 really does not have those files and PyInstaller 6 puts data
    # into _internal
    assert not os.path.exists(os.path.join(ROOT, "assets", "images", "dojo_band.jpg"))
    assert not os.path.exists(os.path.join(ROOT, "assets", "guides"))
    assert "contents_directory" not in _read("Dandurf.spec")


# --------------------------------------------------------------------------
# LICENSE-DESIGN.md
# --------------------------------------------------------------------------

def test_cc0_zvuky_su_pribalene():
    text = _plain("LICENSE-DESIGN.md")
    assert "downloads under the CC0" not in text
    for kluc in ("sfx_click_reload", "sfx_lock_ping"):
        info = sfx_assets.SOUND_LIBRARY[sfx_assets.MODERN][kluc]
        assert info["file"] in text, kluc
        cesta = os.path.join(ROOT, "assets", "sounds", "modern", info["file"])
        with open(cesta, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == info["sha256"], kluc


# --------------------------------------------------------------------------
# 0.2.1: the README describes the whole project, the numbers in the
# documents come from the code
# --------------------------------------------------------------------------

def _lokalne_moduly():
    return {f[:-3] for f in os.listdir(ROOT) if f.endswith(".py")}


def _moduly_z_main():
    """The project modules main.py pulls in (also via other modules) - the
    same that PyInstaller packages into the build."""
    lokalne = _lokalne_moduly()
    videne, fronta = set(), ["main"]
    while fronta:
        meno = fronta.pop()
        if meno in videne:
            continue
        videne.add(meno)
        for uzol in ast.walk(ast.parse(_read(meno + ".py"))):
            if isinstance(uzol, ast.Import):
                mena = [a.name.split(".")[0] for a in uzol.names]
            elif isinstance(uzol, ast.ImportFrom) and uzol.module and not uzol.level:
                mena = [uzol.module.split(".")[0]]
            else:
                continue
            fronta.extend(m for m in mena if m in lokalne and m not in videne)
    return videne


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


def test_readme_tabulka_modulov_pokryva_build():
    """Review 0.2.1: the "Project structure" table was missing ~14 modules
    the app really uses (display, ui_kit, hotkey, obs_websocket, ...).
    Since 0.3d the table is in DEVELOPMENT.md, not in the README."""
    assert "\n## Project structure" not in _read("README.md")
    tabulka = _sekcia(_read(VYVOJ), "Project structure")
    moduly = _moduly_z_main()
    assert {"app", "display", "ui_kit", "hotkey", "obs_websocket",
            "netinfo", "make_icon"} <= moduly     # safety check: the walk found something
    chyba = sorted(m for m in moduly if "`%s.py`" % m not in tabulka)
    assert not chyba, "DEVELOPMENT.md 'Project structure' nemá: %s" % chyba


def test_readme_opisuje_vyvojarske_skripty_a_zavislosti():
    """Every .py in the root that the app does not pull in is a developer
    script - DEVELOPMENT.md (before 0.3d the README) must name it. The
    tests need requirements-dev.txt."""
    readme = _read(VYVOJ)
    skripty = sorted(_lokalne_moduly() - _moduly_z_main())
    assert {"simulate", "prepocitaj_okna", "check_sources"} <= set(skripty)
    for meno in skripty:
        assert "`%s.py`" % meno in readme, meno
    testy = _sekcia(readme, "Tests")
    assert "pip install -r requirements-dev.txt" in testy
    with open(os.path.join(ROOT, "requirements-dev.txt"), encoding="utf-8") as fh:
        dev = fh.read().split()
    for balik in dev:
        assert balik in testy, balik
    # prepocitaj_okna.py rewrites saved data - the README must say so
    assert "It rewrites the saved" in " ".join(testy.split())
    assert "os.replace(tmp, cesta)" in _read("prepocitaj_okna.py")


def test_readme_build_hovori_co_skript_robi():
    """build_all.ps1 runs check_before_run.py and closes a running Zanshin -
    DEVELOPMENT.md says so, and the script really does it.

    Audit 0.3d: the heading "Build the installer (optional)" was a lie
    (the installer is not released) and so was "Build it yourself (no
    warning)" (the Unblock step is there precisely because of the
    warning). The headings must not come back."""
    for meno in ("README.md", VYVOJ):
        assert "Build the installer" not in _read(meno), meno
    assert "Build it yourself (no warning)" not in _read("README.md")
    assert ('### B. Build it yourself (no "unknown publisher" warning for '
            'Zanshin.exe)') in _read("README.md")
    build = " ".join(_sekcia(_read(VYVOJ), "What build.bat does").split())
    skript = _read("build_all.ps1")
    assert "Invoke-Py 'check_before_run.py'" in skript
    assert "Stop-Process -Force" in skript
    assert "`check_before_run.py`" in build
    assert "force-closes a running Zanshin" in build


def test_readme_svet_relacie_urci_dotaznik():
    """The answer in the questionnaire moves the session to another world
    (hr_stats) - HOW-IT-WORKS (before 0.3d the README) no longer claims
    only that a session stays in the world where it started."""
    import i18n
    otazka = i18n.STRINGS["session.context.activity_question"]["en"]
    readme = _plain(AKO)
    assert "*%s*" % otazka in readme
    assert "Skip the question and it stays where it started" in readme


def test_log_bez_listy_nemenuje_listu():
    """0.2.1: `log.hotkey_failed` goes into the journal only when there is no
    tray icon (without pystray/PIL) - so the sentence must not offer it."""
    import i18n
    s = i18n.STRINGS["log.hotkey_failed"]
    assert "lišt" not in s["sk"] and "tray" not in s["en"]
    assert "lišt" not in s["cs"] and "трея" not in s["bg"]
    # the line follows the real result of the registration (0.3 batch 4b)
    telo = zdroj_metody("_ohlas_vysledok_skratky")
    assert telo.index("elif TRAY_AVAILABLE") < telo.index('"log.hotkey_failed"')


def test_cisla_v_dokumentoch_su_z_kodu():
    """Caps and limits that 0.2.1 added and the documents name."""
    import data_io
    import heart_rate
    import obs_websocket
    import trigger
    from datetime import datetime, timezone

    safety = _plain("SAFETY.md")
    assert heart_rate._MAX_LIVE_SOCKETS == 16 and "najviac 16 socketov" in safety
    assert obs_websocket.HANDSHAKE_TIMEOUT_S == 10.0 and "do 10 s nedokončí" in safety
    assert obs_websocket.NECINNOST_S == 60.0 and "po minúte ticha" in safety
    assert obs_websocket._MAX_RAMEC == 64 * 1024 and "najviac 64 kB" in safety
    assert heart_rate.HeartRateMonitor.RECV_BUFFER_BYTES == 4096
    assert "väčší než 4 kB" in safety

    assert sfx_assets.MAX_STIAHNUTIE_BAJTOV == 256 * 1024
    assert "256 KB" in _plain("PRIVACY.md")

    k = _plain(ZMENY)
    assert data_io.MAX_IMPORT_BAJTOV == 50 * 1024 * 1024 and "over 50 MB" in k
    roky = [datetime.fromtimestamp(t, timezone.utc).year
            for t in (data_io.MIN_CAS, data_io.MAX_CAS)]
    assert roky == [2000, 2100] and "before 2000 or after 2100" in k
    p = trigger.default_params()
    assert p["stress_hold_s"] == 45.0 and "(45 s by default)" in k
    assert p["dip_grace_s"] == 20.0 and "(under 20 s)" in k
    assert heart_rate.HeartRateMonitor.STALE_AFTER_S == 12.0
    assert "gap of 12 s or more" in k


def test_known_issues_021_je_navrchu_a_teraz_nie_je_v_liste():
    c = _read(ZMENY)
    assert c.index("## What 0.2.1 fixes") < c.index("## What 0.1 got wrong")
    k = _read("KNOWN_ISSUES.md")
    otvorene = " ".join(_sekcia(k, "Still open").split())
    assert "hard to find" not in otvorene
    assert "tray icon's menu" in otvorene
    import i18n
    assert i18n.STRINGS["tray.snooze"]["en"].startswith("Not now")
