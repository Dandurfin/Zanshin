# -*- coding: utf-8 -*-
"""Dokumenty a inštalátor 0.2 hovoria to, čo robí kód a build.

  * README: port 4455 počúva na všetkých sieťach PC (nie „na lokálnej
    sieti“), inštalátor sa volá presne tak, ako ho pomenuje Dandurf.iss,
    a minimá kalibrácie sedia s `hr_stats`.
  * Najvyššie pásmo tepu je v dokumentoch „Peak“ / „Špička“.
  * Príprava hlasu nikdy nejde na Microsoft počas počúvania.
  * ZDROJE.md netvrdí, že appka sama zisťuje, či hlášky pomáhajú.
  * Vývojárske GUI skripty sú spomenuté a build ich nebalí.
  * KNOWN_ISSUES: repozitár začína 0.2, bez detailov o pracovných poznámkach.
  * Dandurf.iss: verzia v Podrobnostiach setup.exe a [InstallDelete] len
    pre súbory z 0.1 v {app}.
  * LICENSE-DESIGN.md: CC0 zvuky sú pribalené, nie sťahované.
"""
import hashlib
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hr_stats  # noqa: E402
import sfx_assets  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

DOKUMENTY = ("README.md", "SOUL.md", "PRIVACY.md", "SAFETY.md",
             "KNOWN_ISSUES.md", "ZDROJE.md")
GUI_SKRIPTY = ("gui_harness_auto.py", "gui_harness_onboarding.py",
               "gui_screenshots.py")


def _read(meno):
    # utf-8-sig: Dandurf.iss má BOM
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(meno):
    """Text bez zalomení riadkov - vety v .md sú zalomené kdekoľvek."""
    return " ".join(_read(meno).split())


# --------------------------------------------------------------------------
# README: port, inštalátor, kalibrácia
# --------------------------------------------------------------------------

def test_readme_port_pocuva_na_vsetkych_sietach():
    r = _plain("README.md")
    assert "listens on your local network" not in r
    assert "listens on **every network your PC is connected to**" in r
    assert "**without a password**" in r
    for meno in ("README.md", "PRIVACY.md"):
        assert "only listens on your local network" not in _plain(meno), meno
        # Adresa, ktorú PC nemá, spadne späť na všetky rozhrania
        # (`heart_rate._bind`, log.hr_bind_fallback) - dokument to hovorí.
        assert "one specific address" not in _plain(meno), meno
        assert "one of this PC's own addresses" in _plain(meno), meno
        assert "the log says so" in _plain(meno), meno


def test_readme_meno_instalatora_je_z_iss():
    iss = _read("Dandurf.iss")
    verzia = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', iss).group(1)
    zaklad = re.search(r"^OutputBaseFilename=(.+)$", iss, re.M).group(1).strip()
    subor = zaklad.replace("{#MyAppVersion}", verzia) + ".exe"
    readme = _read("README.md")
    assert "`" + subor + "`" in readme
    assert "installer/Zanshin" not in readme


def _relacia(sekundy):
    krivka = [70 + 15 * math.sin(i / 7.0) for i in range(120)]
    return {"duration_s": float(sekundy), "curve": krivka,
            "baseline_bpm": 70.0, "max_bpm": 90.0}


def test_readme_minima_kalibracie_sedia_s_kodom():
    """README: „three of about ten minutes are enough, three of five are
    not“ a „roughly half an hour of heart rate“ - prepočítané kódom."""
    assert hr_stats.PRAH_MIN_RELACII == 3
    assert hr_stats.KRITICKY_MIN_RELACII == 3
    assert hr_stats.DLHODOBA_MIN_RELACII == 3
    assert hr_stats.PRAH_MIN_TRVANIE_S == 300.0
    prah = hr_stats.dynamicky_prah_zataze
    assert prah([_relacia(600)] * 3, baseline=70.0, critical=110) is not None
    assert prah([_relacia(300)] * 3, baseline=70.0, critical=110) is None
    assert prah([_relacia(900)] * 2, baseline=70.0, critical=110) is None
    r = _plain("README.md")
    assert "three of at least five minutes" not in r
    assert "three play sessions of five minutes or more" in r
    assert "roughly half an hour of heart rate" in r
    assert "three of about ten minutes are enough, three of five are not" in r


# --------------------------------------------------------------------------
# Pásmo Špička / Peak
# --------------------------------------------------------------------------

STARE_PASMO = re.compile(r"critical zone|kritick\w* pásm|pásm\w* kritick",
                         re.IGNORECASE)


def test_dokumenty_menuju_pasmo_po_novom():
    for meno in DOKUMENTY:
        assert not STARE_PASMO.search(_plain(meno)), meno
    for meno in ("README.md", "SOUL.md", "KNOWN_ISSUES.md"):
        assert "Peak zone" in _plain(meno), meno
    assert "pásme Špička" in _plain("ZDROJE.md")


# --------------------------------------------------------------------------
# Príprava hlasu a porovnanie hlas / obrázok
# --------------------------------------------------------------------------

def test_priprava_hlasu_nikdy_pocas_pocuvania():
    readme = _plain("README.md")
    assert "Nothing new is prepared while Zanshin is listening" in readme
    assert "never while Zanshin is listening" not in readme
    # Výnimka ako v PRIVACY: hláška, ktorá už letí, sa dopošle (raz v úvodnom
    # citáte - bez znakov „>“ na začiatku riadkov - a raz pri hlasoch).
    bez_citatu = " ".join(" ".join(riadok.lstrip(">") for riadok
                                   in _read("README.md").splitlines()).split())
    assert bez_citatu.count("a line already on its way when listening starts "
                            "is finished") == 2
    assert "On the very first start" in readme
    privacy = _plain("PRIVACY.md")
    assert "**Never while Zanshin is listening**" in privacy
    assert "only the line already on its way is finished" in privacy
    assert "**On the very first start**" in privacy
    assert "Never because a reminder fired during play" not in privacy


def test_cesta_k_hlasu_je_nastavenia_zvuk():
    """Záložka v Nastaveniach sa volá „Sound“ (nav.nastavenia_tabs.zvuk);
    „Sound / Audio“ je len položka palety Ctrl+K."""
    import i18n
    assert i18n.STRINGS["nav.nastavenia_tabs.zvuk"]["en"] == "Sound"
    assert i18n.STRINGS["settings.engine"]["en"] == "Voice comes from"
    for meno in ("README.md", "PRIVACY.md"):
        assert "Sound / Audio" not in _plain(meno), meno
    assert "Settings → Sound" in _plain("README.md")
    assert _plain("PRIVACY.md").count("Settings → Sound → Voice comes from") == 2


def test_ziadny_dokument_netvrdi_ze_appka_uz_porovnava():
    zdroje = _plain("ZDROJE.md")
    assert "zisťuje appka sama" not in zdroje
    assert "Samotné porovnanie zatiaľ neukazuje" in zdroje
    assert "so the app can compare whether the cues help" not in _plain("README.md")
    assert "finds out whether cues help" not in _plain("KNOWN_ISSUES.md")


# --------------------------------------------------------------------------
# Vývojárske GUI skripty
# --------------------------------------------------------------------------

def test_gui_skripty_su_spomenute_a_build_ich_nebali():
    for meno in GUI_SKRIPTY:
        assert os.path.isfile(os.path.join(ROOT, meno)), meno
        for doc in ("README.md", "SAFETY.md"):
            assert meno in _read(doc), (doc, meno)
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
    """0.1 je v historii repozitara bez veci, ktore do verejnosti nepatrili -
    KNOWN_ISSUES to povie vseobecne (rozhodnutie autora 24. 9.), bez detailov."""
    k = _plain("KNOWN_ISSUES.md")
    assert "**About 0.1 in this repository's history.**" in k
    assert "work stays work, private stays private" in k
    assert k.index("About 0.1 in this repository's history") < k.index(
        "## What 0.1 got wrong")
    for zle in ("Working notes", "history on GitHub", "tester",
                "folders on my PC", "prototypes"):
        assert zle not in k, zle
    # log.safe_mode už „no blocking“ nehovorí - bod o skratke to nesmie tvrdiť
    assert "The anti-cheat log line says input is read with" not in k


# --------------------------------------------------------------------------
# Dandurf.iss
# --------------------------------------------------------------------------

def test_setup_exe_ma_verziu_v_podrobnostiach():
    iss = _read("Dandurf.iss")
    setup = iss[iss.index("\n[Setup]\n"):iss.index("\n[Languages]\n")]
    assert re.search(r"^VersionInfoVersion=\{#MyAppVersion\}$", setup, re.M)
    # Inno doplní chýbajúce čísla nulami: "0.2" -> 0.2.0.0, to isté ako
    # filevers vo version_info.txt.
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
    # 0.2 tie súbory naozaj nemá a PyInstaller 6 dáva dáta do _internal
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
