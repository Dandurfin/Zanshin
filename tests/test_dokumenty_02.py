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
  * 0.2.1: tabuľka modulov v README pokrýva všetko, čo build balí, vývojárske
    skripty sú opísané, a čísla v README / SAFETY / PRIVACY / KNOWN_ISSUES
    (stropy, časové limity, rozsah dátumov) sú tie z kódu.
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
    # Inno doplní chýbajúce čísla nulami: "0.2.1" -> 0.2.1.0, to isté ako
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


# --------------------------------------------------------------------------
# 0.2.1: README opisuje celý projekt, čísla v dokumentoch sú z kódu
# --------------------------------------------------------------------------

def _lokalne_moduly():
    return {f[:-3] for f in os.listdir(ROOT) if f.endswith(".py")}


def _moduly_z_main():
    """Moduly projektu, ktoré main.py naťahuje (aj cez ďalšie moduly) - to
    isté, čo PyInstaller zabalí do buildu."""
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
    """Review 0.2.1: tabuľke „Project structure“ chýbalo ~14 modulov, ktoré
    appka naozaj používa (display, ui_kit, hotkey, obs_websocket, ...)."""
    tabulka = _sekcia(_read("README.md"), "Project structure")
    moduly = _moduly_z_main()
    assert {"app", "display", "ui_kit", "hotkey", "obs_websocket",
            "netinfo", "make_icon"} <= moduly     # poistka: prechod nieco nasiel
    chyba = sorted(m for m in moduly if "`%s.py`" % m not in tabulka)
    assert not chyba, "README 'Project structure' nemá: %s" % chyba


def test_readme_opisuje_vyvojarske_skripty_a_zavislosti():
    """Každý .py v koreni, ktorý appka nenaťahuje, je vývojársky skript -
    README ho musí menovať. Testy potrebujú requirements-dev.txt."""
    readme = _read("README.md")
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
    # prepocitaj_okna.py prepisuje ulozene data - README to musi povedat
    assert "It rewrites the saved" in " ".join(testy.split())
    assert "os.replace(tmp, cesta)" in _read("prepocitaj_okna.py")


def test_readme_build_hovori_co_skript_robi():
    """build_all.ps1 spustí check_before_run.py a zatvorí bežiaci Zanshin -
    README to hovorí, a skript to naozaj robí."""
    build = " ".join(_sekcia(_read("README.md"), "Build the installer").split())
    skript = _read("build_all.ps1")
    assert "Invoke-Py 'check_before_run.py'" in skript
    assert "Stop-Process -Force" in skript
    assert "`check_before_run.py`" in build
    assert "force-closes a running Zanshin" in build


def test_readme_svet_relacie_urci_dotaznik():
    """Odpoveď v dotazníku reláciu presunie do iného sveta (hr_stats) - README
    už netvrdí len, že relácia ostane vo svete, kde začala."""
    import i18n
    otazka = i18n.STRINGS["session.context.activity_question"]["en"]
    readme = _plain("README.md")
    assert "*%s*" % otazka in readme
    assert "Skip the question and it stays where it started" in readme


def test_log_bez_listy_nemenuje_listu():
    """0.2.1: `log.hotkey_failed` ide do denníka len vtedy, keď ikona v lište
    nie je (bez pystray/PIL) - veta ju preto nesmie ponúkať."""
    import i18n
    s = i18n.STRINGS["log.hotkey_failed"]
    assert "lišt" not in s["sk"] and "tray" not in s["en"]
    assert "lišt" not in s["cs"] and "трея" not in s["bg"]
    telo = zdroj_metody("start_snooze_hotkey")
    assert telo.index("elif TRAY_AVAILABLE") < telo.index('"log.hotkey_failed"')


def test_cisla_v_dokumentoch_su_z_kodu():
    """Stropy a limity, ktoré 0.2.1 pridalo a dokumenty menujú."""
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

    k = _plain("KNOWN_ISSUES.md")
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
    k = _read("KNOWN_ISSUES.md")
    assert k.index("## What 0.2.1 fixes") < k.index("## What 0.1 got wrong")
    otvorene = " ".join(_sekcia(k, "Still open").split())
    assert "hard to find" not in otvorene
    assert "tray icon's menu" in otvorene
    import i18n
    assert i18n.STRINGS["tray.snooze"]["en"].startswith("Not now")
