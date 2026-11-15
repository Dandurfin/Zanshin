# -*- coding: utf-8 -*-
"""Dokumenty po davke 4 (0.2.2) hovoria to, co robi kod.

  * CHANGELOG.md: historia verzii vysla z KNOWN_ISSUES.md (audit, cast 1);
    sekcia 0.2.2 ma bod davky 4 ("Fewer dead ends") s nazvami z UI a
    cislami z kodu,
  * KNOWN_ISSUES.md: uz len otvorene veci - a kazda nova veta je naviazana
    na kod, aby po oprave zmizla (licencia, ikona, GIF, titulky "Watch ..."
    v navode parovania, pevne pismo v prehliadke, veci overene len na
    simulovanych datach, tabulka hodiniek a poziadavky, davka 4b),
  * README: hlavny vypinac v Quick start, dialog pri prvom ×, skratka v
    Nastaveniach, odkazy na CHANGELOG,
  * PRIVACY: hr_session_pending.json medzi lokalnymi subormi, "Try again",
  * SAFETY: rozlozenia klavesnice a sietove adaptery v uplnom zozname,
  * HOW-IT-WORKS: "Not now", Dnes a bocny panel, relacie, adresa v navode,
  * gui_screenshots.py: demo data sedia (pocet pripomienok = trojuholniky,
    vecer 18-23 h), volby --lang a --okno su opisane v DEVELOPMENT.md,
  * obrazky v README su bez metadat (EXIF/XMP/textove bloky).

Zamerne sa nepinuju cele odstavce - len nazvy z UI, cisla z kodu a vety,
ktore po zmene kodu prestanu platit.
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
    """Cislo z priradenia `meno = 123.0` v zdroji (bez importu Tk)."""
    m = re.search(r"^\s*%s = ([\d.]+)\s*$" % meno, zdroj_suboru(subor), re.M)
    assert m, (subor, meno)
    return float(m.group(1))


def _predvolby():
    """Predvolby skratky tak, ako ich pisu dokumenty: "Ctrl+Alt+Z, ..."."""
    mena = [hotkey.format_combo(p).replace(" ", "") for p in hotkey.PRESETS]
    return ", ".join(mena[:-1]) + ", " + mena[-1]


# --------------------------------------------------------------------------
# CHANGELOG: sekcia davky 4
# --------------------------------------------------------------------------

def _davka4():
    c = _read(ZMENY)
    s022 = c[c.index("## What 0.2.2 changes"):c.index("## What 0.2.1 fixes")]
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
    # dock.start su tie iste slova ako v liste, len so znackou
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
    # dotaznik pri ukonceni: dotknute odpovede ako Ulozit, inak ako Preskocit
    assert "*%s*" % _en("common.save") in d4 and "*%s*" % _en("session.end.skip") in d4


# --------------------------------------------------------------------------
# KNOWN_ISSUES: len otvorene veci, kazda naviazana na kod
# --------------------------------------------------------------------------

def _otvorene():
    return _plain_text(_sekcia(_read("KNOWN_ISSUES.md"), "Still open"))


def test_known_issues_odkazuje_na_changelog():
    k = _read("KNOWN_ISSUES.md")
    uvod = k[:k.index("\n## Still open")]
    assert "](CHANGELOG.md)" in uvod
    # nic, co davka 4 opravila, sa uz netvrdi ako otvorene
    o = _otvorene()
    assert "can't be changed in the app" not in o
    assert "Windows' own boxes" not in _plain_text(k)
    assert "tray icon's menu" in o


def test_known_issues_licencia_ikona_a_gif():
    """Licencia: appka "GPLv3", README "GPLv3 or later" - rozhodne autor.
    Ked sa jedno zmeni, bod v KNOWN_ISSUES treba prepisat (tento test
    spadne). To iste ikona a GIF."""
    o = _otvorene()
    licencia = re.search(r'^LICENCIA = "([^"]+)"', zdroj_suboru("app.py"), re.M)
    assert licencia and licencia.group(1) == "GPLv3"
    assert "GPLv3 or later" in _plain("README.md")
    assert '"GPLv3", while the README and these documents say "GPLv3 or later"' in o
    assert "One thing isn't sorted out yet" in _plain("README.md")
    assert "`Dandurf.ico`" in o and "`make_icon.py`" in o
    obrazky = os.listdir(os.path.join(ROOT, "docs", "img"))
    assert not [f for f in obrazky if f.lower().endswith(".gif")]
    assert "No clip of a cue over a game yet." in o


def test_known_issues_otvorene_texty_su_v_appke():
    """Kazda veta je naviazana na text v appke: ked sa opravi, test povie,
    ze bod v KNOWN_ISSUES musi ist prec."""
    o = _otvorene()
    # Davka 4b opravila: meno stranky podla sveta ({page}), "phone connected",
    # jednu vetu pri obsadenom porte, ram dialogov a zalamovanie ja/zh -
    # KNOWN_ISSUES to uz za otvorene nevydava.
    assert "{page}" in _en("history.empty")
    assert "*%s*" % _en("nav.vhre_work_short") not in o
    for kluc in ("dnes.hr_connected", "settings.hr_status_waiting"):
        assert _en(kluc).startswith(("phone", "Phone")), kluc
        assert "*%s*" % _en(kluc) not in o, kluc
    assert "dialogs have no border" not in o
    assert "Japanese and Chinese lines wrap" not in o
    assert "pairing sentence under the busy message" not in o
    # titulky boxov v navode parovania stale menuju hodinky, hoci sa
    # pripaja telefon (appka v nom)
    for kluc in ("hr.noconnect_title", "hr.trouble_title"):
        assert _en(kluc).startswith("Watch"), kluc
        assert "*%s*" % _en(kluc) in o, kluc
    # prazdna Historia nema variant pre Pracu: aj tam "zahraj si"
    assert "play for at least a minute" in _en("history.empty")
    assert not [k for k in i18n.STRINGS if k.startswith("history.empty_w")]
    assert 'tr("history.empty", page=' in zdroj_suboru("app_history.py")
    assert "History without sessions still asks you to play" in o
    # stopa relacie v Historii: len hracia veta (Pracu ma len dotaznik)
    historia = zdroj_suboru("app_history.py")
    assert 'tr("session.end.trace_hint")' in historia
    assert "trace_hint_work" not in historia
    assert "trace_hint_work" in zdroj_suboru("ui_dialogs.py")
    assert "*One session up close* still says when you were probably playing" in o
    # pevne latinske pismo: bubliny prehliadky a zoznam palety Ctrl+K
    assert 'font=("Segoe UI"' in zdroj_suboru("guided_tour.py")
    assert 'tkfont.Font(family="Segoe UI"' in zdroj_suboru("ui_shell.py")
    assert "bubbles and the Ctrl+K list still use a fixed Latin font" in o
    assert "tested only with simulated data" in o


def test_known_issues_skratka_sa_riadi_odpovedou_windowsu():
    """Davka 4b: riadok skratky a dennik cakaju na skutocny vysledok
    registracie (`on_result`), takze uz netvrdia "drzi ju iny program", ked
    je Windows len pomaly. Ostava len to, ze kym Windows neodpovie, riadok
    ukazuje bezny text ("funguje")."""
    o = _otvorene()
    assert "another app holds the shortcut even though it works" not in o
    assert "line and the log follow Windows' answer" in o
    assert hotkey.GlobalHotkey.CAKAJ_NA_REGISTRACIU_S == 2.0
    assert "more than two seconds" in o
    # kym sa caka, riadok nema vlastny text "registrujem..."
    sub = zdroj_metody("_snooze_hotkey_sub")
    assert "_hotkey_caka" not in sub and "_hotkey_zlyhala" in sub
    assert "self._hotkey_caka = True" in zdroj_suboru("app.py")


def test_known_issues_watch_tabulka_a_poziadavky_cakaju_na_autora():
    """Dve veci caka na autora: model hodiniek v tabulke README a nove
    meranie systemovych poziadaviek na finalnom builde 0.2.2. Ked sa
    doplnia, bod v KNOWN_ISSUES treba zmazat (tento test spadne)."""
    o = _otvorene()
    readme = _read("README.md")
    tabulka = _sekcia(readme, "Getting your heart rate in")
    assert "| Wear OS watch with an Android phone |" in tabulka
    assert "doesn't name my watch" in o
    poziadavky = _plain_text(_sekcia(readme, "System requirements"))
    assert "the 0.2.1 ZIP is about 59 MB" in poziadavky
    assert "The system requirements are from 0.2.1." in o


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
    assert "](CHANGELOG.md#what-022-changes-not-released-yet)" in hore
    assert "](CHANGELOG.md)" in _sekcia(readme, "Known issues")
    assert "KNOWN_ISSUES.md#" not in readme
    r = _plain_text(readme)
    assert "**%s**" % _en("data.open_folder.btn") in r
    t = _plain_text(_sekcia(readme, "Troubleshooting"))
    assert "**%s**" % _en("history.delete_session.btn") in t
    assert "*%s*" % _en("common.retry") in t
    assert "*%s*" % _en("kamae.port_busy", port=heart_rate.DEFAULT_PORT) in r
    # Anti-cheat: appka sa pyta na rozlozenia klavesnice a sietove adaptery
    uvod = _plain_text(hore)
    assert "keyboard layouts" in uvod and "network adapters" in uvod
    assert "GetKeyboardLayoutList" in _read("hotkey.py")
    assert "GetAdaptersAddresses" in _read("netinfo.py")


# --------------------------------------------------------------------------
# PRIVACY a SAFETY
# --------------------------------------------------------------------------

def test_privacy_cakajuca_relacia_je_lokalny_subor():
    p = _read("PRIVACY.md")
    lokalne = _plain_text(p[:p.index("## The few things that can use the network")])
    assert hr_stats.CAKAJUCA_MENO == "hr_session_pending.json"
    assert "`hr_session_pending.json`" in lokalne
    # "Zmazat historiu" ho maze tiez - PRIVACY to hovori o suboroch hore
    assert ("data.delete.pending_session", hr_stats.CAKAJUCA_MENO) in data_io.MAZATELNE
    assert "**%s** there deletes the session, insight and measurement files" % (
        _en("data.delete.btn")) in lokalne
    assert "**%s**" % _en("data.open_folder.btn") in lokalne


def test_privacy_skusit_znova_je_ako_ctrl_k():
    p = _plain("PRIVACY.md")
    assert "*%s* under *%s*" % (_en("common.retry"), _en("settings.engine")) in p
    # to iste ako Ctrl+K -> Pripravit hlas: `pregenerate`, ktory pocas
    # sledovania nic neposle
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
    # ToUnicodeEx dostava vymysleny stav klavesov, skutocny sa necita
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
# gui_screenshots.py a obrazky v README
# --------------------------------------------------------------------------

def _funkcia_zo_skriptu(meno, **globaly):
    """Jedna funkcia z gui_screenshots.py bez spustenia skriptu (ten pri
    importe stavia okno appky a zalohuje data)."""
    strom = ast.parse(_read("gui_screenshots.py"))
    uzol = next(u for u in strom.body
                if isinstance(u, ast.FunctionDef) and u.name == meno)
    modul = ast.Module(body=[uzol], type_ignores=[])
    ns = dict(globaly)
    exec(compile(modul, "gui_screenshots.py", "exec"), ns)
    return ns[meno]


def test_demo_data_pocet_pripomienok_sedi_s_trojuholnikmi(tmp_path):
    """Audit: pocet pripomienok a ▼ v krivke sa losovali zvlast ("HLÁŠKY 0"
    pri troch ▼) a relacie zacinali rano, hoci graf hovori o vecere."""
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
    # volby sa citaju PRED zalohou suborov
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
