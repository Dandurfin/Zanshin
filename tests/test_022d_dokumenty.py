# -*- coding: utf-8 -*-
"""README a dokumenty po davke 0.2.2d (audit, cast 1 "README a dokumentacia").

Audit: zaciatok README bol pravnicky text, instalacia prisla po 2 273
slovach, Troubleshooting, Uninstall ani systemove poziadavky neboli, polovica
README bola pre vyvojarov a testy ho zamykali v dlzke. Teraz:

  * README: uvod -> Quick start -> Install -> parovanie -> poziadavky ->
    co appka robi -> sukromie -> Troubleshooting -> Uninstall -> Known
    issues -> licencia; vyvojarske casti su v DEVELOPMENT.md, presne
    pravidla v docs/HOW-IT-WORKS.md, porovnanie s inymi v docs/PRIOR_ART.md,
  * kazdy relativny odkaz v dokumentoch vedie na subor, ktory existuje, a
    kotvy v README na nadpisy, ktore existuju,
  * nazvy ovladacov v dokumentoch su presne tie z anglickeho UI po
    premenovani (watching, cue, Voice source, ...) a stare nazvy sa do
    dokumentov pre hraca nevracaju (v KNOWN_ISSUES ostavaju len ako historia),
  * cisla a mena v Quick start, Troubleshooting a Uninstall su z kodu
    (hry auto-profilu, hlavny vypinac, skratka "teraz nie", meno pravidla
    vo firewalle),
  * KNOWN_ISSUES zacina tym, co este nefunguje, a 0.2.2 ma bod o novych
    nazvoch; SAFETY.md zacina anglickym zhrnutim.

Davka 4 (0.2.2): hlavny vypinac je tlacidlo "▶ Start watching" (dock.start),
nie ikona v pase "Main switch"; historia verzii je v CHANGELOG.md, nie v
KNOWN_ISSUES.md - straze isli za vetami.

Zamerne sa nepinuju cele odstavce - len nazvy z UI, cisla z kodu, poradie
sekcii a vety, ktore uz nesmu byt pravda.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import hotkey  # noqa: E402
from _zdroj_appky import zdroj_appky, zdroj_suboru  # noqa: E402

PRE_HRACA = ("README.md", "PRIVACY.md", "SAFETY.md", "docs/HOW-IT-WORKS.md")
VSETKY = PRE_HRACA + ("KNOWN_ISSUES.md", "CHANGELOG.md", "DEVELOPMENT.md",
                      "docs/PRIOR_ART.md", "SOUL.md", "LICENSE-DESIGN.md")


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain(text):
    return " ".join(text.split())


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sk(kluc):
    return i18n.STRINGS[kluc]["sk"]


def _nadpisy(text, uroven="## "):
    return [r[len(uroven):].strip() for r in text.splitlines() if r.startswith(uroven)]


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


# --------------------------------------------------------------------------
# README: poradie, dlzka po instalaciu, vyvojarske casti prec
# --------------------------------------------------------------------------

def test_readme_ma_poradie_z_auditu():
    nadpisy = _nadpisy(_read("README.md"))
    poradie = ["Quick start", "Install", "Getting your heart rate in",
               "System requirements", "What it does", "Privacy and anti-cheat",
               "Troubleshooting", "Uninstall", "Known issues", "License"]
    for nadpis in poradie:
        assert nadpis in nadpisy, nadpis
    assert [n for n in nadpisy if n in poradie] == poradie


def test_readme_quick_start_hned_po_uvode():
    """Kto otvori README, dostane do par stoviek slov, co appka je, co
    potrebuje a ako zacat - nie 2 273 slov vyhrad."""
    readme = _read("README.md")
    # 0.2.2d: ~410 slov po Quick start, ~570 po Install (do 0.2.2d 2 273)
    pred = readme[:readme.index("\n## Quick start")]
    assert len(pred.split()) < 500, len(pred.split())
    pred_instalaciou = readme[:readme.index("\n## Install")]
    assert len(pred_instalaciou.split()) < 750, len(pred_instalaciou.split())
    uvod = _plain(pred)
    for fakt in ("free, open-source", "**You need:**", "Windows 10 untested",
                 "not a medical device", "No account, no telemetry",
                 "No keyboard hook"):
        assert fakt.lower() in uvod.lower(), fakt


def test_vyvojarske_casti_su_v_development_md():
    readme = _read("README.md")
    for nadpis in ("Run from source", "Tests", "Project structure",
                   "Prior art & related work", "Build the installer (optional)"):
        assert nadpis not in _nadpisy(readme), nadpis
    assert "How the main window is split" not in readme
    vyvoj = _nadpisy(_read("DEVELOPMENT.md"))
    for nadpis in ("Run from source", "Tests", "What build.bat does",
                   "Project structure"):
        assert nadpis in vyvoj, nadpis
    assert "How the main window is split" in _nadpisy(_read("DEVELOPMENT.md"), "### ")
    # "In one line" ostava v README, tabulka projektov je v docs/PRIOR_ART.md
    assert "Cardia" in _read("docs/PRIOR_ART.md")
    assert "Zanshin is the only one I could find" in _plain(_read("README.md"))


# --------------------------------------------------------------------------
# Odkazy a kotvy
# --------------------------------------------------------------------------

_ODKAZ = re.compile(r"\]\(([^)\s]+)\)")


def _slug(nadpis):
    """Kotva nadpisu tak, ako ju robi GitHub (pre nase nadpisy staci)."""
    s = re.sub(r"[^\w\- ]", "", nadpis.lower())
    return s.replace(" ", "-")


def test_relativne_odkazy_vedu_na_existujuce_subory():
    for meno in VSETKY:
        priecinok = os.path.dirname(os.path.join(ROOT, meno))
        for ciel in _ODKAZ.findall(_read(meno)):
            if ciel.startswith(("http://", "https://", "#", "mailto:")):
                continue
            cesta, _, kotva = ciel.partition("#")
            assert os.path.exists(os.path.join(priecinok, cesta)), (meno, ciel)
            # kotva do ineho dokumentu musi tiez viest na nadpis
            if kotva and cesta.endswith(".md"):
                with open(os.path.join(priecinok, cesta), encoding="utf-8-sig") as fh:
                    nadpisy = [r.lstrip("#").strip() for r in fh.read().splitlines()
                               if r.startswith("#")]
                assert kotva in {_slug(n) for n in nadpisy}, (meno, ciel)


def test_kotvy_v_readme_vedu_na_nadpisy():
    readme = _read("README.md")
    kotvy = {_slug(n) for n in _nadpisy(readme)}
    pouzite = [c[1:] for c in _ODKAZ.findall(readme) if c.startswith("#")]
    assert {"quick-start", "install", "getting-your-heart-rate-in",
            "troubleshooting"} <= set(pouzite)
    for kotva in pouzite:
        assert kotva in kotvy, kotva


def test_readme_odkazuje_na_vsetky_dokumenty():
    readme = _read("README.md")
    for subor in ("PRIVACY.md", "SAFETY.md", "KNOWN_ISSUES.md", "CHANGELOG.md",
                  "DEVELOPMENT.md", "docs/HOW-IT-WORKS.md", "docs/PRIOR_ART.md",
                  "SOUL.md"):
        assert "](%s)" % subor in readme, subor
    assert "](https://github.com/Dandurfin/Zanshin/issues)" in readme


# --------------------------------------------------------------------------
# Nazvy z UI: nove su v dokumentoch, stare sa nevracaju
# --------------------------------------------------------------------------

def _bez_medzier(text):
    return re.sub(r"\s+", " ", text).strip()


def test_readme_menuje_ovladace_ako_appka():
    r = _plain(_read("README.md"))
    # Hlavny vypinac na Dnes je od davky 4 (0.2.2) jedno tlacidlo s textom
    # dock.start / dock.stop (`_texty_pasu`) - tie iste slova ako v liste
    # (tray.start) so znackou ▶. Pas s nadpisom "Main switch"
    # (kamae.bar_title) je prec, README ho uz menovat nesmie.
    assert 'tr("dock.start")' in zdroj_appky() and 'tr("dock.stop")' in zdroj_appky()
    assert "kamae.bar_title" not in i18n.STRINGS
    assert _en("dock.start") == "▶ " + _en("tray.start")
    assert "**%s** at the top of *Today*" % _bez_medzier(_en("dock.start")) in r
    assert "*Main switch*" not in r
    assert "**%s**" % _en("tray.quit") in r
    assert "*%s*" % _en("engine.sapi") in r                         # Windows (offline)
    assert "*%s*" % _en("settings.engine") in r                     # Voice source
    assert "*%s*" % _en("settings.cue_style") in r                  # How I speak up
    assert "*%s*" % _en("data.title") in r                          # Your data
    assert "**%s**" % _en("data.export.btn") in r                   # Export history (JSON)
    assert "*%s*" % _en("settings.hr_enable_switch") in r
    # styri pripomienky menom, ako ich ukazuje stranka V hre
    mena = ", ".join(_en("overlay.slot.%d" % i) for i in range(3))
    assert "%s, %s" % (mena, _en("overlay.slot.3")) in r


def test_how_it_works_a_privacy_menuju_ovladace_ako_appka():
    ako = _plain(_read("docs/HOW-IT-WORKS.md"))
    privacy = _plain(_read("PRIVACY.md"))
    for kluc in ("cue_style.voice", "cue_style.sound", "cue_style.visual",
                 "common.prepare_voices", "engine.sapi"):
        assert "*%s*" % _en(kluc) in ako, kluc
    for kluc in ("cue_style.sound", "cue_style.visual", "common.prepare_voices"):
        assert "*%s*" % _en(kluc) in privacy, kluc
    for kluc in ("engine.edge", "engine.sapi"):
        assert "**%s**" % _en(kluc) in privacy, kluc
    assert "*%s*" % _en("nav.spustace") in ako                      # Cues page
    assert "*%s*" % _en("hud.quick_label") in ako                   # On-screen HR panel
    assert "*%s*" % _en("kamae.voice_prep") in ako
    assert "*%s*" % _en("settings.game_lang") in ako


def test_safety_menuje_ovladace_ako_appka():
    s = _plain(_read("SAFETY.md"))
    assert "**%s**" % _sk("overlay.test") in s                      # ▶ Ukázať
    assert "**%s**" % _en("overlay.test") in s                      # ▶ Show
    assert "stránke %s" % _sk("nav.spustace") in s                  # Pripomienky
    assert "**%s**" % _sk("slot.record_short") in s                 # Nahrať
    assert "„%s“" % _sk("hr.ip_show") in s                          # Ukázať IP


STARE_EN = ("Listen for heart rate from the watch", "Voice comes from",
            "Spoken lines", "In-game HR", "Prepare voice lines", "Test visual",
            "Visuals in game", "Listening on TCP only", "Natural voice (Edge)",
            "Windows voice (works offline)", "Start / Stop")
STARE_SLOVA = re.compile(r"\b(Zen|Modern|HRPI|Triggers?|reminders?)\b")
STARE_SK = ("hlášk", "počúvani", "Spúšťač", "Test vizuálu", "vizuál")


def test_stare_nazvy_sa_do_dokumentov_pre_hraca_nevracaju():
    for meno in PRE_HRACA:
        text = _plain(_read(meno))
        for stare in STARE_EN:
            assert stare not in text, (meno, stare)
        najdene = STARE_SLOVA.findall(text)
        assert not najdene, (meno, najdene)
    safety = _read("SAFETY.md")
    for stare in STARE_SK:
        assert stare not in safety, stare
    # stare nazvy UI su naozaj prec aj z appky - inak by dokument klamal
    # opacnym smerom
    hodnoty = {v.get("en") for v in i18n.STRINGS.values()}
    for stare in ("Listen for heart rate from the watch", "Voice comes from",
                  "Spoken lines", "In-game HR", "Prepare voice lines"):
        assert stare not in hodnoty, stare


def test_privacy_a_readme_hovoria_v_prvej_osobe():
    """Projekt robi jeden clovek (audit): nie "we" / "ours"."""
    for meno in ("README.md", "PRIVACY.md", "docs/HOW-IT-WORKS.md"):
        najdene = re.findall(r"\b(we|We|our|ours|Our)\b", _read(meno))
        assert not najdene, (meno, najdene)
    assert "I can't vouch for it" in _plain(_read("PRIVACY.md"))


# --------------------------------------------------------------------------
# Quick start, Troubleshooting, Uninstall: fakty z kodu
# --------------------------------------------------------------------------

def test_quick_start_hry_a_lista_ako_v_kode():
    from game_profiles import GAME_PROCESS_MAP
    hry = sorted(set(GAME_PROCESS_MAP.values()))
    assert hry == ["Apex Legends", "CS2", "Call of Duty", "Valorant"]
    qs = _plain(_sekcia(_read("README.md"), "Quick start"))
    assert "Apex Legends, Call of Duty, CS2 or Valorant" in qs
    # × appku len schova - az po prvom vysvetleni (`on_close`)
    zavri = zdroj_suboru("app.py")
    assert "tray_close_explained" in zavri and "self.minimize_to_tray()" in zavri
    assert "^ arrow" in _en("tray.close_first") and "^ arrow" in qs
    # sledovanie sa samo spusti len pri prvom starte (po priprave hlasu)
    assert re.search(r'if settings\["first_run"\]:\s*(?:#[^\n]*\s*)*'
                     r'self\._zacni_sledovat_po_priprave_hlasu\(\)', zavri)
    assert "On the very first start" in qs


def test_troubleshooting_skratka_a_cisla_z_kodu():
    from app_spolocne import DEFAULT_SNOOZE_HOTKEY, SNOOZE_HOTKEY_MINUTES
    t = _plain(_sekcia(_read("README.md"), "Troubleshooting"))
    assert DEFAULT_SNOOZE_HOTKEY == "ctrl+alt+z"
    assert hotkey.format_combo(DEFAULT_SNOOZE_HOTKEY).replace(" ", "") == "Ctrl+Alt+Z"
    assert "Ctrl+Alt+Z" in t
    # Od 0.2.2 (davka 4) sa skratka vybera v Nastavenia -> Vseobecne; rucna
    # uprava suboru ostava v README pre 0.2.1 ZIP (ten volbu nema).
    assert "Settings → %s → *%s*" % (_en("nav.nastavenia_tabs.vseobecne"),
                                     _en("settings.snooze_hotkey")) in t
    assert "*%s*" % _en("settings.snooze_hotkey_none") in t
    assert 'tr("settings.snooze_hotkey")' in zdroj_suboru("app_prefs.py")
    assert "In the 0.2.1 ZIP" in t
    # navrhnuta nahrada je platna kombinacia a "" skratku vypne
    m = re.search(r'for example `"([^"]+)"`', t)
    assert m and hotkey.is_valid(m.group(1)), m
    assert '`""` to switch the shortcut off' in t
    prefs = zdroj_suboru("app_prefs.py")
    assert 'loaded.get("snooze_hotkey"' in prefs and 'hk == ""' in prefs
    assert "`\"snooze_hotkey\"`" in t
    assert SNOOZE_HOTKEY_MINUTES == 30
    assert "no cues for 30 minutes" in _plain(_read("README.md"))
    # robot = hlas z Windows; priprava az po zastaveni
    assert "when you stop watching" in _en("edge.after_game")
    assert "Zanshin prepares it once you stop watching" in t


def test_uninstall_meno_vo_firewalle_ako_vo_version_info():
    m = re.search(r"StringStruct\('FileDescription',\s*'([^']+)'\)",
                  _read("version_info.txt"))
    u = _plain(_sekcia(_read("README.md"), "Uninstall"))
    assert "*%s*" % m.group(1) in u
    assert "**%s**" % _en("tray.quit") in u
    assert "%s* → **%s**" % (_en("data.title"), _en("data.export.btn")) in u


# --------------------------------------------------------------------------
# KNOWN_ISSUES a SAFETY
# --------------------------------------------------------------------------

def test_known_issues_zacina_tym_co_este_nefunguje():
    """Od davky 4 je historia verzii v CHANGELOG.md; KNOWN_ISSUES ma len
    otvorene veci, ako pomoct a odkaz na CHANGELOG (audit, cast 1)."""
    k = _read("KNOWN_ISSUES.md")
    poradie = ["## Still open", "## How to help", "## What changed in each version"]
    indexy = [k.index("\n" + n) for n in poradie]
    assert indexy == sorted(indexy)
    for stara in ("## What 0.2.2 changes", "## What 0.2.1 fixes", "## Before 0.2",
                  "## What 0.1 got wrong"):
        assert stara not in k, stara
    assert "](CHANGELOG.md)" in _sekcia(k, "What changed in each version")
    c = _read("CHANGELOG.md")
    poradie = ["## What 0.2.2 changes", "## What 0.2.1 fixes", "## Before 0.2",
               "## What 0.1 got wrong"]
    indexy = [c.index("\n" + n) for n in poradie]
    assert indexy == sorted(indexy)
    assert "## Still open" not in c


def test_known_issues_022_menuje_nove_nazvy():
    k = _plain(_read("CHANGELOG.md"))
    sekcia = k[k.index("## What 0.2.2 changes"):k.index("## What 0.2.1 fixes")]
    assert "### Words and looks" in sekcia
    for kluc in ("tray.start", "tray.stop", "settings.hr_enable_switch",
                 "nav.spustace", "settings.audio_voice_title", "settings.engine",
                 "overlay.dialog_title", "overlay.test", "hud.quick_label",
                 # metric.hrpi.title, nie dnes.stat_hrpi: ten appka nekresli
                 # nikde (karta HRPI z Dnes odisla), nazov ukazuje Historia
                 "pack.zen", "pack.modern", "metric.hrpi.title"):
        assert "*%s*" % _en(kluc) in sekcia, kluc
    # veta po relacii: bez tichych len pocet, s tichymi aj kolko
    assert "{silent}" not in _en("session.end.cues")
    assert "{silent}" in _en("session.end.cues_silent")
    assert "with none silent the line just counts the cues" in sekcia
    assert "about one cue in four" in _en("ob.cue.note")
    # bodka stavu: duty kruzok, nie cervena
    assert "Hollow ring" in _en("sidebar.state_tip")
    assert "a hollow ring when it's stopped" in sekcia


def test_safety_zacina_anglickym_zhrnutim():
    s = _read("SAFETY.md")
    assert s.index("## In English, in short") < s.index("## Krátka odpoveď")
    anglicky = s[:s.index("## Krátka odpoveď")]
    slovensky = _sekcia(s, "Čo appka nerobí")
    riadky = lambda t: [r for r in t.splitlines() if r.startswith("| ") and "---" not in r]
    assert len(riadky(anglicky)) == len(riadky(slovensky)) == 9    # hlavicka + 8
    assert "Ctrl+Alt+Z" in anglicky
    assert "**Anti-cheat in short.**" in anglicky
