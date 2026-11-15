# -*- coding: utf-8 -*-
"""Dokumenty po davke 0.2.2g hovoria to, co robi kod.

  * prirodzeny hlas: Microsoft od novembra 2026 odmieta stary edge-tts
    (HTTP 403). CHANGELOG (0.2.2), KNOWN_ISSUES (0.2.1 ZIP), README
    (Install B a Troubleshooting), DEVELOPMENT a HOW-IT-WORKS menuju to
    iste minimum ako requirements.txt a opisuju, co build naozaj robi,
  * kratky zamok suboru vo Windows (`paths.nahrad_subor`): CHANGELOG a
    DEVELOPMENT maju pocty pokusov a pauzy z kodu a vymenuvaju len ulozenia,
    ktore ho naozaj pouzivaju.

Otazka ikony (README -> LICENSE-DESIGN.md) je v test_022e_dokumenty.

Zamerne sa nepinuju cele odstavce - len cisla a nazvy z kodu a vety, ktore
po zmene kodu prestanu platit (test potom povie, ktory dokument prepisat).
"""
import errno
import io
import os
import re
import sys
import tokenize

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import i18n  # noqa: E402
import paths  # noqa: E402
from _zdroj_appky import zdroj_suboru  # noqa: E402

ZMENY = "CHANGELOG.md"
AKO = "docs/HOW-IT-WORKS.md"
VYVOJ = "DEVELOPMENT.md"


def _read(meno):
    with open(os.path.join(ROOT, meno), encoding="utf-8-sig") as fh:
        return fh.read()


def _plain_text(text):
    return " ".join(text.split())


def _plain(meno):
    return _plain_text(_read(meno))


def _en(kluc):
    return i18n.STRINGS[kluc]["en"]


def _sekcia(text, nadpis):
    zaciatok = text.index("\n## " + nadpis)
    koniec = text.find("\n## ", zaciatok + 1)
    return text[zaciatok:koniec if koniec != -1 else len(text)]


def _podsekcia(text, nadpis):
    zaciatok = text.index("\n### " + nadpis)
    koniec = re.search(r"\n##? ", text[zaciatok + 1:])
    return text[zaciatok:zaciatok + 1 + koniec.start() if koniec else len(text)]


def _bod(text, zaciatok):
    """Jeden bod zoznamu (`- **...`) az po dalsi bod alebo nadpis."""
    i = text.index("\n- **" + zaciatok)
    koniec = re.search(r"\n- \*\*|\n#", text[i + 1:])
    return _plain_text(text[i:i + 1 + koniec.start() if koniec else len(text)])


def _zmeny_022():
    c = _read(ZMENY)
    return c[c.index("## What 0.2.2 changes"):c.index("## What 0.2.1 fixes")]


def _otvorene():
    return _sekcia(_read("KNOWN_ISSUES.md"), "Still open")


def _edge_tts_rozsah():
    """(minimum, strop) z riadku edge-tts>=X,<N v requirements.txt."""
    zhody = re.findall(r"^\s*edge-tts\s*>=\s*([0-9.]+)\s*,\s*<\s*([0-9]+)\s*$",
                       _read("requirements.txt"), re.M)
    assert len(zhody) == 1, zhody
    return zhody[0][0], int(zhody[0][1])


def _minimum_edge_tts():
    return _edge_tts_rozsah()[0]


def _hlavna_edge_tts():
    """Hlavna verzia, ktoru build stahuje ("newest 7.x") - o jednu pod stropom."""
    return _edge_tts_rozsah()[1] - 1


def _edge_blok():
    skript = _read("build_all.ps1")
    return skript[skript.index("$edgeMinVzor"):skript.index("'PyInstaller' '--version'")]


def _kod_bez_komentarov(src):
    """Zdroj bez komentarov a retazcov - "os.replace(" v komentari nevadi."""
    casti = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                            tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            casti.append(tok.string)
    return "".join(casti)


def _poziadavky():
    return [r.strip() for r in _read("requirements.txt").splitlines()
            if r.strip() and not r.strip().startswith("#")]


# --------------------------------------------------------------------------
# Prirodzeny hlas: edge-tts odmietnuty Microsoftom
# --------------------------------------------------------------------------

def test_changelog_hlas_menuje_minimum_a_co_build_robi():
    minimum = _minimum_edge_tts()
    bod = _bod(_podsekcia(_zmeny_022(), "Fewer dead ends"),
               "Microsoft started refusing the natural voice.")
    assert "`edge-tts` %s or newer" % minimum in bod
    assert "7.2.8" in bod and "HTTP 403" in bod
    # build pri kazdom behu stiahne najnovsi povoleny edge-tts; bez internetu
    # pokracuje s dost novym (zlta hlaska), so starym zastavi (Fail = CHYBA:)
    skript = _read("build_all.ps1")
    blok = _edge_blok()
    assert "fetches the newest %d.x `edge-tts` on every build" % _hlavna_edge_tts() in bod
    # oprava v dalsej hlavnej verzii (nad stropom) do buildu nepride - veta
    # to nesmie slubovat; hotovy ZIP sa sam neaktualizuje
    assert ("a new %d.x `edge-tts` fixes it, a build made later gets that fix too "
            "(a ready-made ZIP keeps the one it was built with)"
            % _hlavna_edge_tts()) in bod
    assert "'pip' 'install' '--upgrade'" in blok and "Fail " in blok
    assert "says it couldn't check" in bod and "nevedel overit" in blok
    assert "**CHYBA:**" in bod and 'Write-Host "CHYBA: $message"' in skript
    assert "The build log names the `edge-tts` version that went in." in bod
    assert 'Write-Host "edge-tts $edgeVerzia ide do buildu' in blok
    # veta pri odmietnuti posle po novu verziu; stav je pod Zdrojom hlasu
    assert "*%s*" % _en("settings.engine") in bod
    for kluc in ("edge.partial_refused", "log.edge_failed_refused"):
        assert "official GitHub (Releases)" in _en(kluc), kluc
    assert "official GitHub (Releases)" in bod
    # zlyhanie ide aj do app.log, s verziou edge-tts, raz za druh chyby
    audio = zdroj_suboru("app_audio.py")
    assert 'app_log.warning("prirodzeny hlas: priprava zlyhala' in audio
    assert "_verzia_edge_tts()" in audio
    assert "`app.log`" in bod and "once per kind of error" in bod
    # zo zdrojakov: rovnaky pip prikaz ako v DEVELOPMENT, kontrola pred behom
    assert "`py -m pip install -r requirements.txt` updates an older `edge-tts`" in bod
    # pip (only-if-needed) moze zdvihnut aj zavislost edge-tts - ako v README
    assert ("(and a library it uses, only if the new version needs a newer one) "
            "and leaves the rest as it is") in bod
    assert "8. Verzia edge-tts" in _read("check_before_run.py")
    assert "`check_before_run.py` warns" in bod


def test_known_issues_hlas_v_zipe_021():
    """Kym je vydana verzia 0.2.1, jej ZIP ma edge-tts 7.2.8 - Microsoft ho
    odmieta. Po vydani 0.2.2 tento bod (a podmienka nizsie) ide prec."""
    k = _read("KNOWN_ISSUES.md")
    vydana_021 = k.splitlines()[0].endswith("alpha 0.2.1")
    nadpis = "The natural voice no longer works in the 0.2.1 ZIP."
    if not vydana_021:
        assert nadpis not in k
        return
    bod = _bod(_otvorene(), nadpis)
    minimum = _minimum_edge_tts()
    assert "`edge-tts` 7.2.8" in bod and "HTTP 403" in bod
    assert "`edge-tts` %s or newer" % minimum in bod
    assert "0.2.2 (not released yet)" in bod
    # build 0.2.2 stiahne najnovsi povoleny edge-tts pri kazdom behu (nie len
    # stary); hotovy ZIP nie - ten si necha svoj
    assert ("If you build 0.2.2 yourself, its build fetches the newest %d.x "
            "`edge-tts` every time; a ready-made ZIP keeps the one it came with."
            % _hlavna_edge_tts()) in bod
    assert "its build updates an older one" not in bod
    assert "'--upgrade'" in _edge_blok()
    # 0.2.1 ma stare nazvy: riadok "Voice comes from", volba "Windows voice
    # (works offline)" a vseobecnu vetu o internete. Dnes sa volaju inak.
    for stare in ("*Voice comes from*", "*Windows voice (works offline)*",
                  "*check your internet connection*"):
        assert stare in bod, stare
    assert _en("settings.engine") == "Voice source"
    assert _en("engine.sapi") != "Windows voice (works offline)"
    # rucna aktualizacia pre vlastny build 0.2.1 je neoverena - veta to hovori;
    # prikaz ma ten isty rozsah ako requirements.txt (8.x by mohla zmenit API)
    strop = _edge_tts_rozsah()[1]
    assert ('`py -m pip install --upgrade "edge-tts>=%s,<%d"`'
            % (minimum, strop)) in bod
    assert "`py -m pip install --upgrade edge-tts`" not in bod
    assert "I haven't tried that with 0.2.1" in bod
    # "0.2.1 calls the library the same way 0.2.2 does" - volanie v 0.2.2
    audio = _read("audio_engine.py")
    assert "edge_tts.Communicate(text, voice, rate=edge_rate_str(rate))" in audio
    assert "await comm.save(tmp)" in audio


def test_readme_build_a_troubleshooting_hlasu():
    readme = _read("README.md")
    minimum = _minimum_edge_tts()
    instal = _plain_text(readme[readme.index("### B. Build it yourself"):
                                readme.index("### Both ways")])
    assert "The one exception, from 0.2.2, is `edge-tts`" in instal
    # "jedina vynimka": ziadna ina poziadavka nema verziu a upgrade v builde
    # dostane len edge-tts
    ine = [r for r in _poziadavky() if not r.startswith("edge-tts")]
    assert ine and all(re.fullmatch(r"[A-Za-z0-9_.-]+", r) for r in ine), ine
    strop = _edge_tts_rozsah()[1]
    assert "edge-tts>=%s,<%d" % (minimum, strop) in _poziadavky()
    assert "every build fetches its newest %d.x version" % _hlavna_edge_tts() in instal
    blok = _edge_blok()
    assert blok.count("'--upgrade'") == 1 and "$edgePoziadavka" in blok
    # predvolena strategia pip (only-if-needed): zavislost len ked treba novsiu
    assert "updates a library `edge-tts` itself uses only if the new version " \
           "needs a newer one" in instal
    assert "'--upgrade-strategy'" not in _read("build_all.ps1")
    # bez internetu: dost novy ostane (zlta hlaska), starsi = build zastavi
    assert ("Offline, the build keeps the `edge-tts` you have if it's new enough "
            "(`edge-tts` %s or newer; Microsoft refuses older ones) and says it "
            "couldn't check; with an older one it stops." % minimum) in instal
    # Roboticky je hlas z Windows, nie prirodzeny - nadpis to tak aj hovori.
    bod = _bod(_sekcia(readme, "Troubleshooting"),
               "In the 0.2.1 ZIP, cues stay in the robotic voice.")
    assert "The natural voice stays robotic" not in readme
    assert "[KNOWN_ISSUES.md](KNOWN_ISSUES.md)" in bod
    assert "*check your internet connection*" in bod
    assert ("a build from 0.2.2 on fetches the newest %d.x `edge-tts` every time; "
            "the 0.2.1 build doesn't" % _hlavna_edge_tts()) in bod
    # hotovy ZIP sa sam neaktualizuje (appka nema kontrolu aktualizacii ani pip)
    assert ("A ready-made ZIP never updates itself (0.2.2's won't either): if "
            "Microsoft refuses its voice library again, new lines use the Windows "
            "voice until a new release.") in bod
    assert "There is no update checker" in readme
    # Stare nazvy 0.2.1 do README nepatria (test_022d_dokumenty) - README
    # hovori vseobecne a posle do KNOWN_ISSUES, kde su nazvy zo ZIPu 0.2.1.
    assert "with the names the 0.2.1 ZIP uses, in [KNOWN_ISSUES.md]" in bod
    k = _plain("KNOWN_ISSUES.md")
    if k.startswith("# Known issues — Zanshin alpha 0.2.1"):
        for stare in ("*Voice comes from*", "*Windows voice (works offline)*"):
            assert stare in k and stare not in bod, stare


def test_development_a_how_it_works_o_edge_tts():
    minimum = _minimum_edge_tts()
    vyvoj = _read(VYVOJ)
    zdroj = _plain_text(_sekcia(vyvoj, "Run from source"))
    strop = _edge_tts_rozsah()[1]
    assert "`edge-tts>=%s,<%d`" % (minimum, strop) in zdroj
    assert "The cap keeps out %d.0, a major version I haven't tried" % strop in zdroj
    assert ("pip updates it (and a library it uses, only if the new version needs "
            "a newer one) and leaves the other packages as they are") in zdroj
    assert ('`py -m pip install --upgrade "edge-tts>=%s,<%d"` fetches the newest '
            "allowed one, which is what every build does" % (minimum, strop)) in zdroj
    # minimum je aj v dokumentoch - DEVELOPMENT posiela sem, tento test ich
    # drzi rovnake ako requirements.txt
    assert "it's written only there" not in zdroj
    assert "checked against it by `tests/test_022g_dokumenty.py`" in zdroj
    assert os.path.basename(__file__) == "test_022g_dokumenty.py"
    # kazdy dokument, ktory minimum (strop, hlavnu verziu) menuje, ho ma
    # rovnake ako requirements.txt
    vzor = re.compile(r"`edge-tts` ([0-9]+(?:\.[0-9]+)+) or newer"
                      r"|edge-tts>=([0-9]+(?:\.[0-9]+)+)(?:,<([0-9]+))?")
    najdene = 0
    for dok in ("README.md", "CHANGELOG.md", "KNOWN_ISSUES.md", VYVOJ, AKO,
                "PRIVACY.md", "SAFETY.md"):
        text = _plain(dok)
        for m in vzor.finditer(text):
            najdene += 1
            assert (m.group(1) or m.group(2)) == minimum, (dok, m.group(0))
            assert m.group(3) in (None, str(strop)), (dok, m.group(0))
        for m in re.finditer(r"\bnew(?:est)? ([0-9]+)\.x", text):
            assert int(m.group(1)) == _hlavna_edge_tts(), (dok, m.group(0))
        # build stahuje najnovsi v rozsahu, nie najnovsi vobec (strop <N)
        assert "fetches the newest `edge-tts`" not in text, dok
    assert najdene >= 5, najdene
    build = _plain_text(_sekcia(vyvoj, "What build.bat does"))
    blok = _edge_blok()
    assert ("runs `pip install --upgrade` on every build for the `edge-tts` line "
            "of `requirements.txt` alone") in build
    assert "'pip' 'install' '--upgrade'" in blok and "$edgePoziadavka" in blok
    # sonda indexu: pip bez internetu skonci OK, ked nainstalovany vyhovuje
    assert ("asks the package index once more with `--dry-run`, because pip also "
            "succeeds offline when the installed version fits") in build
    assert "'--dry-run' '--ignore-installed'" in blok
    assert ("goes on with the installed `edge-tts` only if it's at least the "
            "minimum there, with a yellow warning, and stops otherwise") in build
    assert "the log names the `edge-tts` version that goes into the build" in build
    assert "the installed `edge-tts` is older than the minimum there" not in build
    testy = _plain_text(_sekcia(vyvoj, "Tests"))
    assert "the installed `edge-tts` is at least the minimum in `requirements.txt`" in testy
    # build so starym edge-tts najprv aktualizuje, az ked nevie, zastavi -
    # check_before_run.py v builde stary edge-tts nikdy nevidi
    assert ("a build never gets this far with one: it installs or updates "
            "`edge-tts` first, or stops") in testy
    assert "a build stops before this check with one" not in testy
    skript = _read("build_all.ps1")
    assert skript.index("$edgeMinVzor = ") < skript.index("Invoke-Py 'check_before_run.py'")
    ako = _plain(AKO)
    assert "this Zanshin version is probably outdated" in ako
    assert "probably outdated" in _en("edge.partial_refused")
    # "from 0.2.2 the failure also goes into app.log" - riadok v app_audio
    assert "from 0.2.2 the failure also goes into `app.log`" in ako
    assert 'app_log.warning("prirodzeny hlas: priprava zlyhala' in zdroj_suboru("app_audio.py")


# --------------------------------------------------------------------------
# Kratky zamok suboru vo Windows (paths.nahrad_subor)
# --------------------------------------------------------------------------

def test_changelog_zamok_suboru_cisla_z_kodu():
    bod = _bod(_podsekcia(_zmeny_022(), "Heart rate, the window and your data"),
               "A file Windows held for a moment could make a save fail.")
    pauzy = paths.NAHRADA_PAUZY_S
    assert len(pauzy) + 1 == 6 and "up to six tries" in bod
    assert round(sum(pauzy), 1) == 0.3 and "about 0.3 seconds" in bod
    # "Access is denied" = WinError 5; ina chyba (plny disk) sa neopakuje
    assert 5 in paths._DOCASNY_ZAMOK_WIN and "*Access is denied*" in bod
    assert not paths._je_docasny_zamok(OSError(errno.ENOSPC, "plny disk"))
    assert "other errors, such as a full disk, still fail at once" in bod
    # zaloha nastaveni: .bak.tmp sa pri zlyhani zmaze
    prefs = zdroj_suboru("app_prefs.py")
    assert 'tmp = bak + ".tmp"' in prefs
    assert "nahrad_subor(tmp, bak, uprac_zdroj=True)" in prefs
    assert "`dandurf_settings.json.bak.tmp`" in bod
    # riadok do app.log: logger pod "zanshin", ktory zapisuje logging_setup
    assert paths._log.name == "zanshin.paths"
    assert 'logging.getLogger("zanshin")' in _read("logging_setup.py")
    assert "`app.log` notes every save that needed more than one try" in bod


def test_changelog_zamok_suboru_len_co_naozaj_skusa_znova():
    bod = _bod(_podsekcia(_zmeny_022(), "Heart rate, the window and your data"),
               "A file Windows held for a moment could make a save fail.")
    # vymenovane ulozenia naozaj idu cez nahrad_subor
    for modul, funkcie in (
            ("app_prefs.py", ("def zaloha_nastaveni",)),
            ("hr_stats.py", ("def save_session", "def delete_session",
                             "def zapis_rozpracovanu", "def _zapis_cakajuce",
                             "def export_sessions_csv")),
            ("hr_insights.py", ("def save_insights",)),
            ("measure.py", ("def save_windows",)),
            ("data_io.py", ("def append_events", "def write_bundle",
                            "def export_rows_csv", "def zapis_zoznam")),
            ("audio_engine.py", ("def stop_and_save", "def ensure"))):
        src = _read(modul)
        for f in funkcie:
            telo = src[src.index(f):]
            dalsia = re.search(r"\n(?:    )?def ", telo[1:])
            telo = telo[:dalsia.start() + 1] if dalsia else telo
            assert "nahrad_subor(" in telo and "os.replace(" not in telo, (modul, f)
    # hr_windows.json pri importe a pri mazani relacie ide cez zapis_zoznam
    # (skusa znova) - preto veta nizsie hovori LEN o oknach na konci relacie
    data = zdroj_suboru("app_data.py")
    assert "data_io.zapis_zoznam(self.hr_windows_path, okna)" in data
    assert "data_io.zapis_zoznam(self.hr_windows_path, ostava)" in data
    assert "measure.save_windows(self.hr_windows_path" in data
    assert "Measurement windows (`hr_windows.json`) don't" not in bod
    # okna na konci relacie (measure.save_windows) zatial nie - CHANGELOG to
    # hovori, kym plati
    veta = ("Only the measurement windows a session adds when it ends "
            "(`hr_windows.json`) don't try again yet.")
    if "nahrad_subor" in _read("measure.py"):
        assert veta not in bod, "measure.py uz skusa znova - veta v CHANGELOG ide prec"
    else:
        assert veta in bod


def test_development_opisuje_nahrad_subor():
    tabulka = _sekcia(_read(VYVOJ), "Project structure")
    riadok = [r for r in tabulka.splitlines() if r.startswith("| `paths.py` |")]
    assert len(riadok) == 1
    riadok = riadok[0]
    assert "`nahrad_subor`" in riadok and "about 0.3 s" in riadok
    assert round(sum(paths.NAHRADA_PAUZY_S), 1) == 0.3
    vymenovane = riadok[riadok.index("The saves in"):riadok.index("go through it")]
    moduly = re.findall(r"`(\w+\.py)`", vymenovane)
    assert len(moduly) == 5, moduly
    for modul in moduly:
        assert "nahrad_subor(" in _read(modul), modul
        assert "os.replace(" not in _kod_bez_komentarov(_read(modul)), modul
    # "imports no other module of the app"
    lokalne = {f[:-3] for f in os.listdir(ROOT) if f.endswith(".py")}
    importy = set(re.findall(r"^\s*(?:from|import)\s+(\w+)", _read("paths.py"), re.M))
    assert not (importy & lokalne), importy & lokalne
