# -*- coding: utf-8 -*-
"""The documents about the "Update voice" button (0.3) say what the code does.

The author's decision (15. 11. 2026): the player downloads a newer edge-tts
themselves, only on a click, never by itself and never while watching. It is
the first time Zanshin downloads and runs code - PRIVACY.md and SAFETY.md
have to say so honestly: what goes to the network (PyPI,
files.pythonhosted.org, one test word to Microsoft), what stays on disk
(voice_lib), how to delete it, what is checked and what it does not protect
against.

This test keeps the documents in line with the names and numbers from
`hlas_kniznica.py`, the button texts from i18n and the order of the steps
in the code, so that a sentence like "first PyPI, only then the word" or
"nothing is run during installation" does not stop being true silently.
Nothing goes to the network - the code is only read (source, ast), the only
behaviour is `nacitaj_pri_starte` over an empty folder in tmp_path.
"""
import ast
import os
import re
import sys
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

import data_io  # noqa: E402
import hlas_kniznica as hk  # noqa: E402
import i18n  # noqa: E402
import paths  # noqa: E402
from _zdroj_appky import zdroj_metody, zdroj_suboru  # noqa: E402

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


def _sk(kluc):
    return i18n.STRINGS[kluc]["sk"]


def _sekcia(text, nadpis, uroven="## "):
    zaciatok = text.index("\n" + uroven + nadpis)
    koniec = re.search(r"\n#{2,%d} " % len(uroven.strip()), text[zaciatok + 1:])
    return text[zaciatok:zaciatok + 1 + koniec.start() if koniec else len(text)]


def _funkcia(meno):
    """Function source from hlas_kniznica.py (via ast, without running it)."""
    src = _read("hlas_kniznica.py")
    for uzol in ast.walk(ast.parse(src)):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(meno)


def _hostitel(url):
    return urllib.parse.urlsplit(url).hostname


def _bod_privacy():
    """PRIVACY, the "Update voice" item in the list of what goes online."""
    p = _read("PRIVACY.md")
    siet = p[p.index("## The few things that can use the network"):]
    zaciatok = siet.index("\n2. **%s" % _en("edge.update.btn"))
    koniec = siet.index("\n3. **", zaciatok)
    return _plain_text(siet[zaciatok:koniec])


def _safety_sk():
    s = _read("SAFETY.md")
    return _plain_text(_sekcia(s, "Stiahnutý kód"))


def _safety_en():
    s = _read("SAFETY.md")
    return _plain_text(s[:s.index("## Krátka odpoveď")])


# --------------------------------------------------------------------------
# Names from the UI
# --------------------------------------------------------------------------

def test_tlacidlo_a_odkaz_sa_volaju_ako_v_appke():
    tlacidlo = _en("edge.update.btn")
    assert tlacidlo == "Update voice" and _sk("edge.update.btn") == "Aktualizovať hlas"
    for meno in ("README.md", "PRIVACY.md", AKO, ZMENY, VYVOJ):
        assert "**%s**" % tlacidlo in _read(meno), meno
    assert "**%s**" % _sk("edge.update.btn") in _read("SAFETY.md")
    assert "**%s**" % tlacidlo in _safety_en()
    # link to the new release: a chip with "↗ " and the same address as in the
    # code
    odkaz = "↗ " + _en("edge.update.releases_btn")
    assert '"↗ " + tr("edge.update.releases_btn")' in zdroj_suboru("app.py")
    for meno in ("README.md", AKO, ZMENY):
        assert "**%s**" % odkaz in _plain(meno), meno
    assert hk.RELEASES_URL == "https://github.com/Dandurfin/Zanshin/releases/latest"
    assert hk.RELEASES_URL in _read("README.md")
    assert "webbrowser.open(hlas_kniznica.RELEASES_URL)" in zdroj_metody(
        "otvor_vydania_zanshinu")
    # sentences from the status under Voice source that HOW-IT-WORKS quotes
    ako = _plain(AKO)
    assert "*%s*" % _en("edge.update.after_watching") in ako
    assert "*the voice is up to date*" in ako
    assert "the voice is up to date" in _en("edge.update.up_to_date")


def test_tlacidlo_len_pri_prirodzenom_hlase_a_v_palete():
    """Documents: under Voice source, only with the natural voice, also in
    Ctrl+K (which first goes to Settings -> Sound)."""
    assert "ENGINE_EDGE" in zdroj_metody("_obnov_aktualizaciu_hlasu")
    paleta = zdroj_suboru("app_controls.py")
    assert 'tr("edge.update.btn")' in paleta and 'self.sidebar._select("zvuk")' in paleta
    p = _bod_privacy()
    assert "under *%s* in Settings → Sound" % _en("settings.engine") in p
    assert "the same command in the *Ctrl+K* palette" in p
    assert "shown only with the natural voice" in p
    ako = _plain_text(_sekcia(_read(AKO), "Updating the natural voice"))
    assert "shown only with the natural voice" in ako
    assert "it switches to the *%s* tab first" % _en("nav.nastavenia_tabs.zvuk") in ako


# --------------------------------------------------------------------------
# PRIVACY: when, what goes out, what stays, how to delete it
# --------------------------------------------------------------------------

def test_privacy_len_na_klik_a_nikdy_pocas_sledovania():
    p = _bod_privacy()
    assert "only when you click it" in p
    assert "Never by itself, not at start-up, and **never while Zanshin is watching**" in p
    # a click while watching does not go to the network - the check is BEFORE
    # the core call
    klik = zdroj_metody("aktualizuj_hlas")
    assert klik.index('getattr(self, "listening", False)') < klik.index(
        "hlas_kniznica.aktualizuj(")
    assert 'tr("edge.update.after_watching")' in klik
    # ... and the core asks `abort` before every step that goes to the network
    jadro = _funkcia("_aktualizuj")
    assert jadro.index("_skontroluj_abort(abort)") < jadro.index("stiahni_zoznam_vydani()")
    assert jadro.index("_skontroluj_abort(abort)\n        wheel") < jadro.index(
        "stiahni_wheel(")
    over = _funkcia("_vyskusaj_a_aktivuj")
    assert over.index("_skontroluj_abort(abort)") < over.index("skusobne_slovo(")
    assert "it stops before its next step that uses the network, and nothing changes" in p
    # PRIVACY no longer claims that the app updates nothing
    cela = _plain("PRIVACY.md")
    assert "no update-checker" not in cela
    assert "Zanshin never checks for a new version of itself" in cela


def test_privacy_co_ide_von_menuje_hostitelov_a_slovo_z_kodu():
    p = _bod_privacy()
    assert _hostitel(hk.PYPI_JSON_URL) == "pypi.org"
    assert hk._PYPI_HOSTITELIA == {"pypi.org"}
    assert hk._SUBORY_HOSTITELIA == {"files.pythonhosted.org"}
    assert "`pypi.org`" in p and "`files.pythonhosted.org`" in p
    # User-Agent: just the app name, no version
    assert hk.USER_AGENT == "Zanshin"
    assert "name only the app (`%s`, no version) and nothing about you" % hk.USER_AGENT in p
    assert '"User-Agent": USER_AGENT' in _read("hlas_kniznica.py")
    # test word: fixed text and voice, never the text of a cue
    assert hk.TEST_TEXT == "Zanshin" and hk.TEST_HLAS == "en-GB-SoniaNeural"
    assert 'one fixed test word, **"%s"**' % hk.TEST_TEXT in p
    assert "(voice `%s`)" % hk.TEST_HLAS in p
    assert "Never the wording of your cues" in p
    assert "_syntetizuj(modul, TEST_TEXT, hlas or TEST_HLAS" in _funkcia("skusobne_slovo")
    assert "hlas_kniznica.aktualizuj(cache=cache, abort=zrus)" in zdroj_metody("aktualizuj_hlas")
    # the file with the word is always deleted (finally)
    slovo = _funkcia("skusobne_slovo")
    assert "finally:" in slovo and slovo.index("finally:") < slovo.index("os.remove(cesta)")
    assert "The sound file is deleted right away." in p
    # no newer version: the word checks the current one; no PyPI, nothing else
    assert "or with the current one if there was nothing newer" in p
    assert hk.aktualizuj.__defaults__[-1] is True          # over_aktualnu
    jadro = _funkcia("_aktualizuj")
    assert jadro.index("stiahni_zoznam_vydani()") < jadro.index("skusobne_slovo(")
    assert jadro.index("stiahni_zoznam_vydani()") < jadro.index("stiahni_wheel(")
    assert "If PyPI can't be reached, nothing else is sent." in p
    # HTTPS with certificates from certifi
    assert "certifi.where()" in _funkcia("_otvor")
    assert "The requests to PyPI go over HTTPS." in p


def test_privacy_co_ostane_na_disku_a_ako_to_zmazat(tmp_path, monkeypatch):
    p = _bod_privacy()
    assert paths.VOICE_LIB_NAME == "voice_lib"
    assert os.path.basename(paths.voice_lib_dir()) == "voice_lib"
    assert "the folder `voice_lib` in `%APPDATA%\\Zanshin`" in p
    assert "(run from source, next to `main.py`)" in p
    assert hk.MANIFEST_MENO == "manifest.json" and "`manifest.json`" in p
    assert "only if its test word worked" in p
    over = _funkcia("_vyskusaj_a_aktivuj")
    assert over.index("skusobne_slovo(") < over.index("_zapis_manifest(")
    assert "shutil.rmtree(priecinok" in over          # did not pass = gone
    # each attempt's temp files and the older version after success go away
    assert "The temporary files of each attempt are deleted" in p
    assert "_uprac_tmp()" in _funkcia("_aktualizuj")
    assert "and so is an older downloaded version once the new one works" in p
    assert over.index("_aktivuj(") < over.index("_uprac_stare(")
    # one line to app.log per attempt, without paths
    assert "Each attempt writes one line to `logs/app.log`" in p
    assert "_zaloguj(vysledok)" in _funkcia("aktualizuj")
    # at start only if newer than the bundled one
    assert "as long as it's newer than the one built into Zanshin" in p
    assert "je_novsia(verzia, pribalena)" in _funkcia("nacitaj_pri_starte")
    # deleted folder = bundled version (behaviour, not just text)
    monkeypatch.setattr(hk, "KNIZNICA_DIR", str(tmp_path / "voice_lib"))
    assert hk.nacitaj_pri_starte(pribalena="7.3.1") is None
    assert ("quit Zanshin and delete the `voice_lib` folder; at the next start "
            "Zanshin uses its built-in version again") in p
    # "Zmazat historiu" (Delete history) does not delete it
    vsetko = [c for _k, c in data_io.MAZATELNE] + [c for _k, c in data_io.MAZATELNE_PRIECINKY]
    assert not any("voice_lib" in c for c in vsetko)
    assert "*%s* doesn't touch it" % _en("data.delete.btn") in p
    # size: on the order of 100 KB (the .py files of the bundled edge-tts)
    assert "about 100 KB" in p
    edge = __import__("edge_tts")
    priecinok = os.path.dirname(edge.__file__)
    spolu = sum(os.path.getsize(os.path.join(priecinok, f)) for f in os.listdir(priecinok)
                if f.endswith(".py") or f == "py.typed")
    assert 30 * 1024 < spolu < 300 * 1024, spolu
    # git ignores it (when running from source it lies next to main.py)
    assert "voice_lib/" in _read(".gitignore").splitlines()


# --------------------------------------------------------------------------
# SAFETY: what is checked and what it does not protect against
# --------------------------------------------------------------------------

def test_safety_anglicke_zhrnutie_hovori_o_stiahnutom_kode():
    en = _safety_en()
    assert "**Downloaded code (from 0.3, only when you click).**" in en
    assert "the one place where Zanshin downloads code and runs it" in en
    assert "Never by itself and never while Zanshin is watching" in en
    assert "`pypi.org`" in en and "`files.pythonhosted.org`" in en
    assert "SHA-256" in en and "test word" in en
    assert "with your normal user rights" in en
    # an honest limitation
    assert ("if the `edge-tts` project or PyPI itself were compromised, a "
            "malicious version would pass all of it") in en
    assert "No administrator rights, nothing injected, and none of it touches the game" in en


def test_safety_slovenska_cast_sedi_s_kodom():
    s = _read("SAFETY.md")
    sk = _safety_sk()
    # the link from "Kratka odpoved" (Short answer) leads to the heading
    # (anchor as on GitHub)
    nadpis = [r[3:] for r in s.splitlines() if r.startswith("## Stiahnutý kód")]
    assert len(nadpis) == 1
    kotva = re.sub(r"[^\w\- ]", "", nadpis[0].lower()).replace(" ", "-")
    kratka = _sekcia(s, "Krátka odpoveď")
    assert "](#%s)" % kotva in kratka
    assert "**%s**" % _sk("edge.update.btn") in sk
    assert "`hlas_kniznica.py`" in sk
    # only on a click and never while watching
    assert "len na klik. Nikdy samo, nikdy pri štarte a nikdy počas sledovania" in sk
    # 1. HTTPS + exact hosts, also after a redirect
    assert "`pypi.org`" in sk and "`files.pythonhosted.org`" in sk
    assert "aj po každom presmerovaní" in sk
    assert "_over_url(newurl, self.hostitelia)" in _read("hlas_kniznica.py")
    # 2. size and sha256 from PyPI, a 2 MB cap
    assert hk.WHEEL_STROP_B == 2 * 1024 * 1024 and "väčší než 2 MB" in sk
    wheel = _funkcia("stiahni_wheel")
    assert "sha256" in wheel and 'kandidat.get("velkost")' in wheel
    # 3. only edge_tts/*.py (+ py.typed) to disk, nothing executable
    assert "`edge_tts/*.py`" in sk and "`py.typed`" in sk
    rozbal = _funkcia("rozbal_wheel")
    assert 'casti[1] == "py.typed" or _je_modul_py(casti[1])' in rozbal
    assert ".pth" in hk._SPUSTITELNE_PRIPONY and ".pyd" in hk._SPUSTITELNE_PRIPONY
    assert "Pri inštalácii sa nespustí nič" in sk
    # 4. the code is only read (ast)
    assert "ast.parse(" in _funkcia("skontroluj_kod") and "modul `ast`" in sk
    # 5. dependencies must already be in the app; nothing else is downloaded
    assert "Nič ďalšie sa nesťahuje" in sk
    assert "skontroluj_zavislosti(" in _funkcia("skontroluj_metadata")
    # 6. only then does the code run; it stays only with the test word
    assert "**vtedy už beží**" in sk and "nie ako administrátor" in sk
    assert "jedno skúšobné slovo „%s“" % hk.TEST_TEXT in sk
    # at start: sha256 of every file, no bytecode
    assert "_over_subory(priecinok, hashe)" in _funkcia("nacitaj_pri_starte")
    assert "set_data" in _read("hlas_kniznica.py") and "bytecode (`__pycache__`)" in sk
    # what it does not protect against - honestly
    nechrani = sk[sk.index("**Pred čím to nechráni:**"):]
    assert "škodlivá verzia by prešla všetkými kontrolami" in nechrani
    assert "Odtlačok SHA-256 pochádza tiež z PyPI" in nechrani
    assert "najnovšiu finálnu verziu" in nechrani
    assert "verzia_finalna(verzia)" in _funkcia("vyber_kandidata")
    assert "build inštaluje `edge-tts` z toho istého PyPI" in nechrani
    assert "](PRIVACY.md)" in sk


# --------------------------------------------------------------------------
# README, CHANGELOG, KNOWN_ISSUES, HOW-IT-WORKS, DEVELOPMENT
# --------------------------------------------------------------------------

def test_readme_uvod_sukromie_a_troubleshooting():
    readme = _read("README.md")
    uvod = _plain_text(readme[:readme.index("\n## Quick start")])
    assert ("Only when you click **Update voice** (from 0.3) does Zanshin "
            "download newer code for that voice from PyPI") in uvod
    sukromie = _plain_text(_sekcia(readme, "Privacy and anti-cheat"))
    assert "**Update voice** (from 0.3, only when you click it" in sukromie
    bod = _plain_text(_sekcia(readme, "Troubleshooting"))
    bod = bod[bod.index("**The line under *Voice source* says Microsoft refused"):]
    bod = bod[:bod.index("- **In the 0.2.1 ZIP")]
    assert "Click **Update voice** right below it (once you've stopped watching)" in bod
    assert "Microsoft refuses even the newest version" in bod
    assert "refuses even the newest" in _en("edge.update.refused_still")
    assert hk.RELEASES_URL in bod
    assert "](PRIVACY.md)" in bod and "](SAFETY.md)" in bod
    assert ("**Internet:** while you use Zanshin, only for the natural voice "
            "(optional) and, from 0.3, its **Update voice** button.") in _plain_text(readme)


def test_changelog_bod_o_tlacidle():
    c = _read(ZMENY)
    s022 = c[c.index("## What 0.3 changes"):c.index("## What 0.2.1 fixes")]
    sekcia = s022[s022.index("### Fewer dead ends"):]
    i = sekcia.index("\n- **Only a new Zanshin could repair the natural voice.**")
    bod = _plain_text(sekcia[i:i + 1 + re.search(r"\n- \*\*|\n#", sekcia[i + 1:]).start()])
    assert "never while Zanshin is watching" in bod
    assert "`files.pythonhosted.org`" in bod
    assert 'one test word, "%s", through Microsoft' % hk.TEST_TEXT in bod
    assert "`%s` in your data folder (about 100 KB)" % paths.VOICE_LIB_NAME in bod
    assert "](PRIVACY.md)" in bod and "](SAFETY.md)" in bod
    assert "It's the first time Zanshin downloads and runs code" in bod


def test_known_issues_hranice_tlacidla():
    k = _read("KNOWN_ISSUES.md")
    otvorene = _plain_text(_sekcia(k, "Still open"))
    assert "***Update voice* can't fix everything**" in otvorene
    assert "[SAFETY.md](SAFETY.md)" in otvorene
    # rejected for a missing dependency -> "a newer Zanshin is needed"
    assert hk.STAV_NEKOMPATIBILNY == "incompatible"
    assert "needs a newer Zanshin" in _en("edge.update.incompatible")
    assert "otherwise it says a newer Zanshin is needed" in otvorene


def test_how_it_works_aktualizacia_hlasu():
    ako = _plain_text(_sekcia(_read(AKO), "Updating the natural voice"))
    # a final version, nothing pre-release or withdrawn (yanked)
    assert "picks the newest final one (no pre-release, nothing withdrawn)" in ako
    assert 'not f.get("yanked")' in _funkcia("vyber_kandidata")
    assert 'one test word, "%s", through Microsoft' % hk.TEST_TEXT in ako
    # on failure nothing new, the link only where only a new Zanshin helps
    import app_audio
    odkazy = {stav for stav, (_s, _l, _ok, odkaz) in app_audio._VYSLEDKY_AKTUALIZACIE.items()
              if odkaz}
    assert odkazy == {hk.STAV_STALE_ODMIETNUTY, hk.STAV_NEKOMPATIBILNY}
    assert "Microsoft refuses even the newest version, or the update needs a newer Zanshin" in ako
    # during the update, voice preparation waits; after success the missing
    # ones get prepared
    assert "_aktualizacia_hlasu_bezi" in zdroj_metody("pregenerate")
    assert "Preparing asked for in the meantime waits for the result." in ako
    assert "self.pregenerate(force=True)" in zdroj_metody("_aktualizacia_hlasu_hotova")
    assert "cues still missing their natural voice are prepared right after" in ako
    # a broken downloaded one at start: bundled + app.log, not tried again
    assert "oznac_pokazenu(dovod)" in _funkcia("nacitaj_pri_starte")
    assert 'manifest.get("broken")' in _funkcia("nacitaj_pri_starte")
    assert "doesn't try the downloaded one again until **Update voice** replaces it" in ako


def test_development_tabulka_priecinok_a_spec():
    vyvoj = _read(VYVOJ)
    tabulka = _sekcia(vyvoj, "Project structure")
    riadok = [r for r in tabulka.splitlines() if r.startswith("| `hlas_kniznica.py` |")]
    assert len(riadok) == 1
    assert "only on click and never while watching" in riadok[0]
    assert "call `aktualizuj` from a worker thread" in riadok[0]
    assert "`voice_lib_dir()`" in tabulka and "def voice_lib_dir" in _read("paths.py")
    zdroj = _plain_text(_sekcia(vyvoj, "Run from source"))
    assert "`voice_lib\\` next to `main.py` (git ignores that folder" in zdroj
    assert "`%APPDATA%\\Zanshin\\voice_lib`" in zdroj
    # the dependency list in the spec == the list in DEVELOPMENT
    spec = _read("Dandurf.spec")
    m = re.search(r"_EDGE_ZAVISLOSTI = \(([^)]*)\)", spec)
    baliky = re.findall(r"'([\w.]+)'", m.group(1))
    build = _plain_text(_sekcia(vyvoj, "What build.bat does"))
    for balik in baliky:
        if balik == "attr":          # module of the attrs package
            continue
        assert balik in build, balik
    assert "copy_metadata('typing_extensions')" in spec and "typing_extensions" in build
    assert "'aiohttp.pytest_plugin'" in spec
    assert "without aiohttp's test modules (they would pull in pytest)" in build
    assert "I estimate under 2 MB more, but haven't measured it." in build
    # tests do not go to the network - an autouse fixture replaces the network
    # and the test word
    testy = _plain_text(_sekcia(vyvoj, "Tests"))
    assert "No test goes to the network." in testy
    for subor in ("test_022h_hlas_kniznica.py", "test_022h_aktualizuj_hlas.py"):
        src = _read(os.path.join("tests", subor))
        assert "autouse=True" in src and '"_otvor"' in src, subor
        assert "`tests/%s`" % subor in testy
    assert '"_syntetizuj"' in _read(os.path.join("tests", "test_022h_aktualizuj_hlas.py"))


# --------------------------------------------------------------------------
# Honest sentences that a mutation would otherwise get past (document checks)
# --------------------------------------------------------------------------

def test_poctive_vety_o_tlacidle_drzia_vo_vsetkych_dokumentoch():
    """Every sentence here is a promise about when the button goes to the
    network, what it keeps and what it does not protect against. Without
    this test it could be dropped or reversed (e.g. "keeps it only if that
    worked" -> "keeps it") and all the document tests passed."""
    over = _funkcia("_vyskusaj_a_aktivuj")
    # only what the test word confirmed is kept (the manifest only after it)
    assert over.index("skusobne_slovo(") < over.index("_zapis_manifest(")
    # abort is asked only BEFORE a step: a request already in flight finishes
    assert "abort" not in _funkcia("_http_get") and "abort" not in _funkcia("skusobne_slovo")

    # PRIVACY: cue preparation right after success is another "when" for texts
    assert ("and from 0.3 right after **Update voice** worked, if a cue's line "
            "is still missing") in _plain("PRIVACY.md")
    assert "self.pregenerate(force=True)" in zdroj_metody("_aktualizacia_hlasu_hotova")
    p = _bod_privacy()
    assert ("only a request already on its way is finished: it stops before its "
            "next step that uses the network, and nothing changes") in p
    assert "and what that can't protect you from, is in [`SAFETY.md`](SAFETY.md)" in p

    # SAFETY in English: the reason for the limitation, the newest version, no
    # signature, own build, and what happens on every start
    en = _safety_en()
    assert "Never by itself and never while Zanshin is watching: only your click starts a download." in en
    assert "because the fingerprint comes from PyPI too" in en
    assert ("The button always takes the newest final version, even one released "
            "minutes earlier, and checks no signature from the library's author") in en
    zdroj = _read("hlas_kniznica.py").lower()
    assert "signat" not in zdroj and "attest" not in zdroj and "gpg" not in zdroj
    assert "Building Zanshin yourself carries the same risk" in en
    assert ("A version that stayed is loaded at every start from then on, each file "
            "checked against its fingerprint first, as long as it's newer than the "
            "one built into Zanshin.") in en
    start = _funkcia("nacitaj_pri_starte")
    assert "_over_subory(priecinok, hashe)" in start and "je_novsia(verzia, pribalena)" in start
    assert "hlas_kniznica.nacitaj_pri_starte()" in _read("audio_engine.py")

    # SAFETY in Slovak
    sk = _safety_sk()
    assert ("Pred každým krokom, ktorý ide na sieť, sa appka pozrie, či sa medzitým "
            "nezačalo sledovať; ak áno, skončí a nič nezmení.") in sk
    assert ("To isté urobí aj pred načítaním stiahnutého kódu a po skúšobnom slove: "
            "keď sa medzitým začalo sledovať, novú verziu nenačíta, ani si ju "
            "nenechá.") in sk
    over = _funkcia("_vyskusaj_a_aktivuj")
    assert over.index("_skontroluj_abort(abort)") < over.index("nacitaj_balik(")
    po_slove = over[over.index("skusobne_slovo("):]
    assert po_slove.index("_skontroluj_abort(abort)") < po_slove.index("_zapis_manifest(")
    assert "Podpis autora knižnice Zanshin neoveruje" in sk
    assert ("nie niekoho, kto už môže zapisovať do tvojho priečinka používateľa: ten "
            "by zmenil aj manifest") in sk
    assert "nič sa nevkladá do hry ani do iného procesu" in sk

    # README: keeps it only if it works; Privacy also has the limit of checks
    readme = _read("README.md")
    bod = _plain_text(_sekcia(readme, "Troubleshooting"))
    assert "tests it with one word and keeps it only if it works" in bod
    sukromie = _plain_text(_sekcia(readme, "Privacy and anti-cheat"))
    assert ("what **Update voice** checks before the code it downloads runs, and what "
            "those checks can't protect against: a compromised `edge-tts` project or "
            "PyPI") in sukromie

    # HOW-IT-WORKS
    ako = _plain_text(_sekcia(_read(AKO), "Updating the natural voice"))
    assert "It runs only when you click it, never by itself." in ako
    assert "While Zanshin is watching, a click sends nothing" in ako
    assert ("only a request already on its way is finished: the update stops before "
            "its next step that uses the network, and nothing changes") in ako
    assert "keeps it only if that worked" in ako

    # CHANGELOG
    c = _plain(ZMENY)
    assert "It keeps the new version only if that works" in c


def test_safety_priznava_zavislost_bez_zistenej_verzie(monkeypatch):
    """Point 5: a dependency whose version cannot be found out is LET THROUGH
    by the app (it only writes it to app.log) - the document must not claim
    that the version is always verified. And the py.typed marker is written
    with any content at all - "empty" is not a check, so the document does
    not claim it."""
    sk = _safety_sk()
    assert ("Keď sa verzia niektorej z nich zistiť nedá, appka ju pustí ďalej, "
            "zapíše to do `app.log` a rozhodne až import a skúšobné slovo.") in sk
    assert "neoverene.append(dist)" in _funkcia("skontroluj_zavislosti")
    assert '"verzia bez overenia: "' in _funkcia("_aktualizuj")
    assert "_zaloguj(vysledok)" in _funkcia("aktualizuj")
    # behaviour: an importable package with no known version does not block
    monkeypatch.setattr(hk, "_najdi_modul", lambda dist: "nejaky_modul")
    monkeypatch.setattr(hk, "_verzia_balika", lambda dist, modul: None)
    assert hk.skontroluj_zavislosti(["nejaky-balik>=1.0"]) == ([], ["nejaky-balik"])
    # py.typed: rozbal_wheel ignores the content, the doc does not say "empty"
    assert 'casti[1] == "py.typed"' in _funkcia("rozbal_wheel")
    assert "prázdna značka" not in sk and "značka `py.typed`" in sk
