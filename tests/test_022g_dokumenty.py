# -*- coding: utf-8 -*-
"""The documents after batch 0.3g say what the code does.

  * natural voice: since November 2026 Microsoft refuses the old edge-tts
    (HTTP 403). CHANGELOG (0.3), README (Install B), DEVELOPMENT and
    HOW-IT-WORKS name the same minimum as requirements.txt and describe
    what the build really does; the README's Troubleshooting has one line
    for whoever is still on the 0.2.1 ZIP,
  * since 15. 11. 2026 (the author's decision) requirements.txt has NO
    version cap (",<8" could have blocked exactly this fix) - the
    documents say so, no "newest 7.x" comes back, and after upgrading
    edge-tts the build tries its API (without the network) and one test
    word (only with internet),
  * a short file lock on Windows (`paths.nahrad_subor`): CHANGELOG and
    DEVELOPMENT have the numbers of attempts and the pauses from the code
    and list only the saves that really use it.

The "Update voice" button (hlas_kniznica.py) in the documents is guarded
by test_022h_dokumenty. The icon question (README -> LICENSE-DESIGN.md) is
in test_022e_dokumenty.

Whole paragraphs are deliberately not pinned - only numbers and names from
the code and sentences that stop being true after a code change (the test
then says which document to rewrite).
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
# Documents that name the edge-tts minimum (they must all have the same one).
S_MINIMOM = ("README.md", "CHANGELOG.md", "KNOWN_ISSUES.md", VYVOJ, AKO,
             "PRIVACY.md", "SAFETY.md")


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
    """One list item (`- **...`) up to the next item or heading."""
    i = text.index("\n- **" + zaciatok)
    koniec = re.search(r"\n- \*\*|\n#", text[i + 1:])
    return _plain_text(text[i:i + 1 + koniec.start() if koniec else len(text)])


def _zmeny_022():
    c = _read(ZMENY)
    return c[c.index("## What 0.3 changes"):c.index("## What 0.2.1 fixes")]


def _minimum_edge_tts():
    """The minimum from the edge-tts>=X line in requirements.txt - no cap."""
    poziadavky = [r for r in _poziadavky() if r.startswith("edge-tts")]
    assert len(poziadavky) == 1, poziadavky
    m = re.fullmatch(r"edge-tts\s*>=\s*([0-9]+(?:\.[0-9]+)+)", poziadavky[0])
    assert m, "edge-tts v requirements.txt ma len minimum, bez stropu: %r" % poziadavky[0]
    return m.group(1)


def _edge_blok():
    skript = _read("build_all.ps1")
    return skript[skript.index("$edgeMinVzor"):skript.index("'PyInstaller' '--version'")]


def _kod_bez_komentarov(src):
    """Source minus comments and strings - "os.replace(" in a comment is OK."""
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
# Natural voice: edge-tts refused by Microsoft
# --------------------------------------------------------------------------

def test_requirements_bez_stropu_a_build_skusa_novy_edge_tts():
    """There is deliberately no cap - compatibility is checked by the build
    (API + word) and the app (Update voice). The documents describe it
    according to this block."""
    _minimum_edge_tts()
    blok = _edge_blok()
    # (a) API without the network, failure = Fail with the way back; (b) the
    # word only online, failure = a yellow warning (no Fail), the temporary
    # file always gone
    api, slovo = blok.index("$edgeApi = "), blok.index("$edgeSlovo = ")
    assert api < blok.index("goes into the build") < slovo
    assert "edge_tts.Communicate('Zanshin', 'en-GB-SoniaNeural'" in blok[api:]
    assert "iscoroutinefunction" in blok[api:slovo]
    assert "Fail (" in blok[api:slovo] and "--force-reinstall" in blok[api:slovo]
    assert "Fail" not in blok[slovo:]
    assert "!!! WARNING" in blok[slovo:]
    assert "Remove-Item -LiteralPath $edgeSubor" in blok[slovo:]
    vynechavam = blok.index("Skipping the test word")
    assert blok.rindex("if ($edgePip -ne 0) {", 0, vynechavam) > api
    assert vynechavam < slovo
    # check_before_run only mentions the cap (a note, not an error)
    kontrola = _read("check_before_run.py")
    assert "_strop = re.search(" in kontrola and "notes.append(" in kontrola


def test_changelog_hlas_menuje_minimum_a_co_build_robi():
    minimum = _minimum_edge_tts()
    bod = _bod(_podsekcia(_zmeny_022(), "Fewer dead ends"),
               "Microsoft started refusing the natural voice.")
    assert "`edge-tts` %s or newer" % minimum in bod
    assert "7.2.8" in bod and "HTTP 403" in bod
    # no cap - and why
    assert "with no upper limit" in bod
    assert "the fix may come in a new major version, and a cap would keep it out" in bod
    # the build downloads the newest edge-tts on every run; without internet
    # it carries on with a new enough one (yellow message), with an old one
    # it stops (Fail = CHYBA:)
    skript = _read("build_all.ps1")
    blok = _edge_blok()
    assert "`build.bat` fetches the newest `edge-tts` on every build" in bod
    assert ("a ready-made ZIP keeps the one it was built with until you click "
            "**Update voice**") in bod
    assert "'pip' 'install' '--upgrade'" in blok and "Fail " in blok
    assert "says it couldn't check" in bod and "Couldn't check" in blok
    assert "**ERROR:**" in bod and 'Write-Host "ERROR: $message"' in skript
    # API without the network and a test word
    # (test_requirements_bez_stropu_...)
    assert "Without the network it checks that Zanshin can still call it" in bod
    assert ("names the `requirements.txt` line and the command that go back to "
            "the last version that worked") in bod
    assert 'one test word, "Zanshin", through Microsoft' in bod
    assert "a loud yellow warning if Microsoft refuses it, and the build goes on" in bod
    assert "skips the test word" in bod
    assert "The build log names the `edge-tts` version that went in." in bod
    assert 'Write-Host "edge-tts $edgeVerzia goes into the build' in blok
    # the sentence on refusal first sends you to Update voice, then to the
    # new version; the status is under Voice source
    assert "*%s*" % _en("settings.engine") in bod
    for kluc in ("edge.partial_refused", "log.edge_failed_refused"):
        assert "official GitHub (Releases)" in _en(kluc), kluc
        assert _en("edge.update.btn") in _en(kluc), kluc
    assert "official GitHub (Releases)" in bod
    assert "say to click **%s** first" % _en("edge.update.btn") in bod
    # the failure also goes to app.log, with the edge-tts version, once
    # per kind of error
    audio = zdroj_suboru("app_audio.py")
    assert 'app_log.warning("prirodzeny hlas: priprava zlyhala' in audio
    assert "_verzia_edge_tts()" in audio
    assert '"%s (stiahnuta)" % verzia' in audio
    assert "`app.log`" in bod and "once per kind of error" in bod
    assert "(a downloaded one is marked as such)" in bod
    # from source: the same pip command as in DEVELOPMENT, the pre-run check
    assert "`py -m pip install -r requirements.txt` updates an older `edge-tts`" in bod
    # pip (only-if-needed) may also upgrade a dependency of edge-tts - as in
    # README
    assert ("(and a library it uses, only if the new version needs a newer one) "
            "and leaves the rest as it is") in bod
    assert "8. edge-tts version" in _read("check_before_run.py")
    assert "`check_before_run.py` warns" in bod
    assert "notes a cap in `requirements.txt`" in bod


def test_known_issues_hlas_v_zipe_021():
    """The 0.2.1 ZIP has edge-tts 7.2.8, which Microsoft refuses. While 0.2.1
    was the released version, KNOWN_ISSUES had an item about it. 0.3 is
    released (it needs a newer edge-tts and has Update voice), and so is
    0.3.1, so the item is gone: CHANGELOG covers the fix, and the README has
    one line for whoever is still on the 0.2.1 ZIP
    (test_readme_build_a_troubleshooting_hlasu)."""
    k = _read("KNOWN_ISSUES.md")
    assert k.splitlines()[0].endswith("alpha 0.3.1")
    assert "The natural voice no longer works in the 0.2.1 ZIP." not in k
    assert "not released yet" not in k
    # the fix is in CHANGELOG: the refused 7.2.8 and the new minimum
    bod = _bod(_podsekcia(_zmeny_022(), "Fewer dead ends"),
               "Microsoft started refusing the natural voice.")
    assert "7.2.8, also the one inside the 0.2.1 ZIP" in bod
    assert "`edge-tts` %s or newer" % _minimum_edge_tts() in bod


def test_readme_build_a_troubleshooting_hlasu():
    readme = _read("README.md")
    minimum = _minimum_edge_tts()
    instal = _plain_text(readme[readme.index("### B. Build it yourself"):
                                readme.index("### Both ways")])
    assert "The one exception, from 0.3, is `edge-tts`" in instal
    # "the only exception": no other requirement has a version, and the
    # upgrade in the build gets only edge-tts
    ine = [r for r in _poziadavky() if not r.startswith("edge-tts")]
    assert ine and all(re.fullmatch(r"[A-Za-z0-9_.-]+", r) for r in ine), ine
    assert "edge-tts>=%s" % minimum in _poziadavky()
    assert "every build fetches its newest version" in instal
    blok = _edge_blok()
    assert blok.count("'--upgrade'") == 1 and "$edgePoziadavka" in blok
    # pip's default strategy (only-if-needed): a dependency only when a
    # newer one is needed
    assert "updates a library `edge-tts` itself uses only if the new version " \
           "needs a newer one" in instal
    assert "'--upgrade-strategy'" not in _read("build_all.ps1")
    # API and a test word (test_requirements_bez_stropu_...)
    assert ("The build then checks that Zanshin can still call the new `edge-tts` "
            "(if not, it stops and says how to go back to the last one that "
            "worked) and, online, has it say one test word through Microsoft.") in instal
    assert ("If Microsoft refuses it, a yellow warning says so and the build "
            "goes on") in instal
    # without internet: a new enough one stays (yellow message), an older
    # one = the build stops
    assert ("Offline, the build keeps the `edge-tts` you have if it's new enough "
            "(`edge-tts` %s or newer; Microsoft refuses older ones) and says it "
            "couldn't check; with an older one it stops." % minimum) in instal
    # Since 0.3 is released, the README has one short item for whoever is
    # still on the 0.2.1 ZIP: why its new lines are robotic (that is the
    # Windows voice, not the natural one) and that updating fixes it.
    bod = _bod(_sekcia(readme, "Troubleshooting"), "Still on the 0.2.1 ZIP?")
    assert "In the 0.2.1 ZIP, cues stay in the robotic voice." not in readme
    assert "until 0.3 is out" not in readme
    assert "The natural voice stays robotic" not in readme
    assert "Since about November 2026 Microsoft refuses" in bod
    assert "Since about November 2026" in _plain(ZMENY)
    assert "every new line plays in the Windows voice" in bod
    assert "it has no **%s** button." % _en("edge.update.btn") in bod
    # 0.3 was the first with the fix; Install offers the newest release
    # (0.3.1 now), so the line doesn't send anyone looking for the 0.3 ZIP
    assert "Update to 0.3 or newer (see [Install](#install)); your data stays." in bod
    assert "your data stays" in _plain_text(_sekcia(readme, "Install"))
    assert "0.3's won't either" not in readme
    assert "There is no update checker" not in readme
    assert "Zanshin never checks for a new version of itself" in _plain_text(readme)
    # The old 0.2.1 names went with the 0.2.1 items: neither the README
    # (test_022d_dokumenty) nor KNOWN_ISSUES has them any more.
    k = _plain("KNOWN_ISSUES.md")
    for stare in ("*Voice comes from*", "*Windows voice (works offline)*",
                  "*check your internet connection*"):
        assert stare not in k and stare not in bod, stare


def test_development_a_how_it_works_o_edge_tts():
    minimum = _minimum_edge_tts()
    vyvoj = _read(VYVOJ)
    zdroj = _plain_text(_sekcia(vyvoj, "Run from source"))
    assert "`edge-tts>=%s`" % minimum in zdroj
    assert "There is deliberately no upper cap" in zdroj
    assert "The cap keeps out" not in zdroj and "version range" not in zdroj
    assert ("pip updates it (and a library it uses, only if the new version needs "
            "a newer one) and leaves the other packages as they are") in zdroj
    assert ('`py -m pip install --upgrade "edge-tts>=%s"` fetches the newest one, '
            "which is what every build does" % minimum) in zdroj
    # the minimum is in the documents too - DEVELOPMENT sends you here, this
    # test keeps them the same as requirements.txt
    assert "it's written only there" not in zdroj
    assert "checked against it by `tests/test_022g_dokumenty.py`" in zdroj
    assert os.path.basename(__file__) == "test_022g_dokumenty.py"
    build = _plain_text(_sekcia(vyvoj, "What build.bat does"))
    # every document that names the minimum has the same one as
    # requirements.txt; a cap (",<N") may only be in the instructions on how
    # the build goes back to the last working one (DEVELOPMENT, "What
    # build.bat does")
    vzor = re.compile(r"`edge-tts` ([0-9]+(?:\.[0-9]+)+) or newer"
                      r"|edge-tts>=([0-9]+(?:\.[0-9]+)+)(,<[0-9.]+)?")
    najdene = 0
    for dok in S_MINIMOM:
        text = _plain(dok)
        for m in vzor.finditer(text):
            najdene += 1
            assert (m.group(1) or m.group(2)) == minimum, (dok, m.group(0))
            if m.group(3):
                assert dok == VYVOJ and m.group(0) in build, (dok, m.group(0))
        # "newest 7.x" was the <8 cap - that is gone
        assert not re.search(r"\bnew(?:est)? [0-9]+\.x\b", text), dok
    assert najdene >= 5, najdene
    blok = _edge_blok()
    assert ("runs `pip install --upgrade` on every build for the `edge-tts` line "
            "of `requirements.txt` alone") in build
    assert "'pip' 'install' '--upgrade'" in blok and "$edgePoziadavka" in blok
    # index probe: pip without internet ends OK when the installed one
    # satisfies it
    assert ("asks the package index once more with `--dry-run`, because pip also "
            "succeeds offline when the installed version fits") in build
    assert "'--dry-run' '--ignore-installed'" in blok
    assert ("goes on with the installed `edge-tts` only if it's at least the "
            "minimum there, with a yellow warning, and stops otherwise") in build
    assert "The log names the `edge-tts` version that goes into the build" in build
    assert "the installed `edge-tts` is older than the minimum there" not in build
    # API without the network: the exact call from audio_engine; the way back
    # via requirements.txt (the build upgrades on every run, a bare pip would
    # revert)
    assert ('builds `Communicate("Zanshin", "en-GB-SoniaNeural", rate="+0%")` '
            "the way `audio_engine.py` does, and checks that `save` is async") in build
    assert "edge_tts.Communicate(text, voice, rate=edge_rate_str(rate))" in _read("audio_engine.py")
    assert "the `requirements.txt` line to set, with a cap below the broken version" in build
    assert "a pip command alone would be undone by the next build" in build
    assert "$edgeSpat" in blok and "requirements.txt change the edge-tts line" in blok
    assert "it suggests `--force-reinstall` of that version instead" in build
    # test word: only online, the temporary file always gone, a failure
    # does not stop it
    assert ('one test word, "Zanshin", through Microsoft into a temporary '
            "`%TEMP%\\zanshin-edge-tts-<random>.mp3` that is always deleted") in build
    assert "'zanshin-edge-tts-'" in blok and "$env:TEMP" in blok
    assert "a loud yellow warning, and the build goes on" in build
    assert "Offline a yellow note says the test word was skipped." in build
    testy = _plain_text(_sekcia(vyvoj, "Tests"))
    assert "the installed `edge-tts` is at least the minimum in `requirements.txt`" in testy
    # a build with an old edge-tts first updates it, and stops only when it
    # cannot - check_before_run.py in the build never sees an old edge-tts
    assert ("a build never gets this far with one: it installs or updates "
            "`edge-tts` first, or stops") in testy
    assert "a build stops before this check with one" not in testy
    assert "A cap on `edge-tts` there" in testy and "only gets a note" in testy
    skript = _read("build_all.ps1")
    assert skript.index("$edgeMinVzor = ") < skript.index("Invoke-Py 'check_before_run.py'")
    ako = _plain(AKO)
    assert "this Zanshin version is probably outdated" in ako
    assert "probably outdated" in _en("edge.partial_refused")
    assert "then it says to click **%s** below first" % _en("edge.update.btn") in ako
    # "from 0.3 the failure also goes into app.log" - the line in app_audio
    assert "from 0.3 the failure also goes into `app.log`" in ako
    assert 'app_log.warning("prirodzeny hlas: priprava zlyhala' in zdroj_suboru("app_audio.py")


# --------------------------------------------------------------------------
# A short file lock on Windows (paths.nahrad_subor)
# --------------------------------------------------------------------------

def test_changelog_zamok_suboru_cisla_z_kodu():
    bod = _bod(_podsekcia(_zmeny_022(), "Heart rate, the window and your data"),
               "A file Windows held for a moment could make a save fail.")
    pauzy = paths.NAHRADA_PAUZY_S
    assert len(pauzy) + 1 == 6 and "up to six tries" in bod
    assert round(sum(pauzy), 1) == 0.3 and "about 0.3 seconds" in bod
    # "Access is denied" = WinError 5; another error (full disk) is not retried
    assert 5 in paths._DOCASNY_ZAMOK_WIN and "*Access is denied*" in bod
    assert not paths._je_docasny_zamok(OSError(errno.ENOSPC, "plny disk"))
    assert "other errors, such as a full disk, still fail at once" in bod
    # settings backup: .bak.tmp is deleted on failure
    prefs = zdroj_suboru("app_prefs.py")
    assert 'tmp = bak + ".tmp"' in prefs
    assert "nahrad_subor(tmp, bak, uprac_zdroj=True)" in prefs
    assert "`dandurf_settings.json.bak.tmp`" in bod
    # the line to app.log: a logger under "zanshin", whose records
    # logging_setup writes
    assert paths._log.name == "zanshin.paths"
    assert 'logging.getLogger("zanshin")' in _read("logging_setup.py")
    assert "`app.log` notes every save that needed more than one try" in bod


def test_changelog_zamok_suboru_len_co_naozaj_skusa_znova():
    bod = _bod(_podsekcia(_zmeny_022(), "Heart rate, the window and your data"),
               "A file Windows held for a moment could make a save fail.")
    # the listed saves really go through nahrad_subor
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
    # hr_windows.json on import and when deleting a session goes through
    # zapis_zoznam (retries) - that is why the sentence below talks ONLY
    # about the windows at the end of a session
    data = zdroj_suboru("app_data.py")
    assert "data_io.zapis_zoznam(self.hr_windows_path, okna)" in data
    assert "data_io.zapis_zoznam(self.hr_windows_path, ostava)" in data
    assert "measure.save_windows(self.hr_windows_path" in data
    assert "Measurement windows (`hr_windows.json`) don't" not in bod
    # windows at the end of a session (measure.save_windows) not yet -
    # CHANGELOG says so while it holds
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
    assert len(moduly) == 6, moduly
    for modul in moduly:
        assert "nahrad_subor(" in _read(modul), modul
        assert "os.replace(" not in _kod_bez_komentarov(_read(modul)), modul
    # "imports no other module of the app"
    lokalne = {f[:-3] for f in os.listdir(ROOT) if f.endswith(".py")}
    importy = set(re.findall(r"^\s*(?:from|import)\s+(\w+)", _read("paths.py"), re.M))
    assert not (importy & lokalne), importy & lokalne
