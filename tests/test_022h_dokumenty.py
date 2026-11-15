# -*- coding: utf-8 -*-
"""Dokumenty o tlacidle "Aktualizovat hlas" (0.2.2) hovoria to, co robi kod.

Rozhodnutie autora (15. 11. 2026): hrac si novsi edge-tts stiahne sam, len
na klik, nikdy samo a nikdy pocas sledovania. Je to prvy raz, co Zanshin
stahuje a spusta kod - PRIVACY.md a SAFETY.md to musia povedat poctivo:
co ide na siet (PyPI, files.pythonhosted.org, jedno skusobne slovo
Microsoftu), co ostane na disku (voice_lib), ako sa to zmaze, co sa
kontroluje a pred cim to nechrani.

Tento test drzi pri dokumentoch mena a cisla z `hlas_kniznica.py`, texty
tlacidiel z i18n a poradie krokov v kode, aby veta "najprv PyPI, az potom
slovo" alebo "pri instalacii sa nic nespusta" neprestala platit potichu.
Na siet nejde nic - kod sa len cita (zdroj, ast), jedine spravanie je
`nacitaj_pri_starte` nad prazdnym priecinkom v tmp_path.
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
    """Zdroj funkcie z hlas_kniznica.py (cez ast, bez spustenia)."""
    src = _read("hlas_kniznica.py")
    for uzol in ast.walk(ast.parse(src)):
        if isinstance(uzol, ast.FunctionDef) and uzol.name == meno:
            return ast.get_source_segment(src, uzol)
    raise AssertionError(meno)


def _hostitel(url):
    return urllib.parse.urlsplit(url).hostname


def _bod_privacy():
    """PRIVACY, bod "Update voice" v zozname toho, co ide na siet."""
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
# Mena z UI
# --------------------------------------------------------------------------

def test_tlacidlo_a_odkaz_sa_volaju_ako_v_appke():
    tlacidlo = _en("edge.update.btn")
    assert tlacidlo == "Update voice" and _sk("edge.update.btn") == "Aktualizovať hlas"
    for meno in ("README.md", "PRIVACY.md", AKO, ZMENY, VYVOJ):
        assert "**%s**" % tlacidlo in _read(meno), meno
    assert "**%s**" % _sk("edge.update.btn") in _read("SAFETY.md")
    assert "**%s**" % tlacidlo in _safety_en()
    # odkaz na nove vydanie: chip s "↗ " a ta ista adresa ako v kode
    odkaz = "↗ " + _en("edge.update.releases_btn")
    assert '"↗ " + tr("edge.update.releases_btn")' in zdroj_suboru("app.py")
    for meno in ("README.md", AKO, ZMENY):
        assert "**%s**" % odkaz in _plain(meno), meno
    assert hk.RELEASES_URL == "https://github.com/Dandurfin/Zanshin/releases/latest"
    assert hk.RELEASES_URL in _read("README.md")
    assert "webbrowser.open(hlas_kniznica.RELEASES_URL)" in zdroj_metody(
        "otvor_vydania_zanshinu")
    # vety zo stavu pod Zdrojom hlasu, ktore HOW-IT-WORKS cituje
    ako = _plain(AKO)
    assert "*%s*" % _en("edge.update.after_watching") in ako
    assert "*the voice is up to date*" in ako
    assert "the voice is up to date" in _en("edge.update.up_to_date")


def test_tlacidlo_len_pri_prirodzenom_hlase_a_v_palete():
    """Dokumenty: pod Zdrojom hlasu, len pri prirodzenom hlase, aj v Ctrl+K
    (ktora najprv prejde na Nastavenia -> Zvuk)."""
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
# PRIVACY: kedy, co ide von, co ostane, ako to zmazat
# --------------------------------------------------------------------------

def test_privacy_len_na_klik_a_nikdy_pocas_sledovania():
    p = _bod_privacy()
    assert "only when you click it" in p
    assert "Never by itself, not at start-up, and **never while Zanshin is watching**" in p
    # klik pocas sledovania na siet nejde - kontrola je PRED volanim jadra
    klik = zdroj_metody("aktualizuj_hlas")
    assert klik.index('getattr(self, "listening", False)') < klik.index(
        "hlas_kniznica.aktualizuj(")
    assert 'tr("edge.update.after_watching")' in klik
    # ... a jadro sa pyta `abort` pred kazdym krokom, ktory ide na siet
    jadro = _funkcia("_aktualizuj")
    assert jadro.index("_skontroluj_abort(abort)") < jadro.index("stiahni_zoznam_vydani()")
    assert jadro.index("_skontroluj_abort(abort)\n        wheel") < jadro.index(
        "stiahni_wheel(")
    over = _funkcia("_vyskusaj_a_aktivuj")
    assert over.index("_skontroluj_abort(abort)") < over.index("skusobne_slovo(")
    assert "it stops before its next step that uses the network, and nothing changes" in p
    # PRIVACY uz netvrdi, ze appka nic neaktualizuje
    cela = _plain("PRIVACY.md")
    assert "no update-checker" not in cela
    assert "Zanshin never checks for a new version of itself" in cela


def test_privacy_co_ide_von_menuje_hostitelov_a_slovo_z_kodu():
    p = _bod_privacy()
    assert _hostitel(hk.PYPI_JSON_URL) == "pypi.org"
    assert hk._PYPI_HOSTITELIA == {"pypi.org"}
    assert hk._SUBORY_HOSTITELIA == {"files.pythonhosted.org"}
    assert "`pypi.org`" in p and "`files.pythonhosted.org`" in p
    # User-Agent: len meno appky, bez verzie
    assert hk.USER_AGENT == "Zanshin"
    assert "name only the app (`%s`, no version) and nothing about you" % hk.USER_AGENT in p
    assert '"User-Agent": USER_AGENT' in _read("hlas_kniznica.py")
    # skusobne slovo: pevny text a hlas, nikdy text pripomienky
    assert hk.TEST_TEXT == "Zanshin" and hk.TEST_HLAS == "en-GB-SoniaNeural"
    assert 'one fixed test word, **"%s"**' % hk.TEST_TEXT in p
    assert "(voice `%s`)" % hk.TEST_HLAS in p
    assert "Never the wording of your cues" in p
    assert "_syntetizuj(modul, TEST_TEXT, hlas or TEST_HLAS" in _funkcia("skusobne_slovo")
    assert "hlas_kniznica.aktualizuj(cache=cache, abort=zrus)" in zdroj_metody("aktualizuj_hlas")
    # subor so slovom sa zmaze vzdy (finally)
    slovo = _funkcia("skusobne_slovo")
    assert "finally:" in slovo and slovo.index("finally:") < slovo.index("os.remove(cesta)")
    assert "The sound file is deleted right away." in p
    # bez novsej verzie slovo overi tu aktualnu; bez PyPI nejde nic dalsie
    assert "or with the current one if there was nothing newer" in p
    assert hk.aktualizuj.__defaults__[-1] is True          # over_aktualnu
    jadro = _funkcia("_aktualizuj")
    assert jadro.index("stiahni_zoznam_vydani()") < jadro.index("skusobne_slovo(")
    assert jadro.index("stiahni_zoznam_vydani()") < jadro.index("stiahni_wheel(")
    assert "If PyPI can't be reached, nothing else is sent." in p
    # HTTPS s certifikatmi z certifi
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
    assert "shutil.rmtree(priecinok" in over          # nepresiel = prec
    # docasne subory kazdeho pokusu a starsia verzia po uspechu idu prec
    assert "The temporary files of each attempt are deleted" in p
    assert "_uprac_tmp()" in _funkcia("_aktualizuj")
    assert "and so is an older downloaded version once the new one works" in p
    assert over.index("_aktivuj(") < over.index("_uprac_stare(")
    # jeden riadok do app.log na pokus, bez ciest
    assert "Each attempt writes one line to `logs/app.log`" in p
    assert "_zaloguj(vysledok)" in _funkcia("aktualizuj")
    # pri starte len novsia nez pribalena
    assert "as long as it's newer than the one built into Zanshin" in p
    assert "je_novsia(verzia, pribalena)" in _funkcia("nacitaj_pri_starte")
    # zmazany priecinok = pribalena verzia (spravanie, nie len text)
    monkeypatch.setattr(hk, "KNIZNICA_DIR", str(tmp_path / "voice_lib"))
    assert hk.nacitaj_pri_starte(pribalena="7.3.1") is None
    assert ("quit Zanshin and delete the `voice_lib` folder; at the next start "
            "Zanshin uses its built-in version again") in p
    # "Zmazat historiu" ho nemaze
    vsetko = [c for _k, c in data_io.MAZATELNE] + [c for _k, c in data_io.MAZATELNE_PRIECINKY]
    assert not any("voice_lib" in c for c in vsetko)
    assert "*%s* doesn't touch it" % _en("data.delete.btn") in p
    # velkost: radovo 100 KB (.py subory pribaleneho edge-tts)
    assert "about 100 KB" in p
    edge = __import__("edge_tts")
    priecinok = os.path.dirname(edge.__file__)
    spolu = sum(os.path.getsize(os.path.join(priecinok, f)) for f in os.listdir(priecinok)
                if f.endswith(".py") or f == "py.typed")
    assert 30 * 1024 < spolu < 300 * 1024, spolu
    # git ho ignoruje (zo zdrojakov lezi vedla main.py)
    assert "voice_lib/" in _read(".gitignore").splitlines()


# --------------------------------------------------------------------------
# SAFETY: co sa kontroluje a pred cim to nechrani
# --------------------------------------------------------------------------

def test_safety_anglicke_zhrnutie_hovori_o_stiahnutom_kode():
    en = _safety_en()
    assert "**Downloaded code (from 0.3, only when you click).**" in en
    assert "the one place where Zanshin downloads code and runs it" in en
    assert "Never by itself and never while Zanshin is watching" in en
    assert "`pypi.org`" in en and "`files.pythonhosted.org`" in en
    assert "SHA-256" in en and "test word" in en
    assert "with your normal user rights" in en
    # poctive obmedzenie
    assert ("if the `edge-tts` project or PyPI itself were compromised, a "
            "malicious version would pass all of it") in en
    assert "No administrator rights, nothing injected, and none of it touches the game" in en


def test_safety_slovenska_cast_sedi_s_kodom():
    s = _read("SAFETY.md")
    sk = _safety_sk()
    # odkaz z "Kratkej odpovede" vedie na nadpis (kotva ako na GitHube)
    nadpis = [r[3:] for r in s.splitlines() if r.startswith("## Stiahnutý kód")]
    assert len(nadpis) == 1
    kotva = re.sub(r"[^\w\- ]", "", nadpis[0].lower()).replace(" ", "-")
    kratka = _sekcia(s, "Krátka odpoveď")
    assert "](#%s)" % kotva in kratka
    assert "**%s**" % _sk("edge.update.btn") in sk
    assert "`hlas_kniznica.py`" in sk
    # len na klik a nikdy pocas sledovania
    assert "len na klik. Nikdy samo, nikdy pri štarte a nikdy počas sledovania" in sk
    # 1. HTTPS + presni hostitelia aj po presmerovani
    assert "`pypi.org`" in sk and "`files.pythonhosted.org`" in sk
    assert "aj po každom presmerovaní" in sk
    assert "_over_url(newurl, self.hostitelia)" in _read("hlas_kniznica.py")
    # 2. velkost a sha256 z PyPI, strop 2 MB
    assert hk.WHEEL_STROP_B == 2 * 1024 * 1024 and "väčší než 2 MB" in sk
    wheel = _funkcia("stiahni_wheel")
    assert "sha256" in wheel and 'kandidat.get("velkost")' in wheel
    # 3. na disk len edge_tts/*.py (+ py.typed), nic spustitelne
    assert "`edge_tts/*.py`" in sk and "`py.typed`" in sk
    rozbal = _funkcia("rozbal_wheel")
    assert 'casti[1] == "py.typed" or _je_modul_py(casti[1])' in rozbal
    assert ".pth" in hk._SPUSTITELNE_PRIPONY and ".pyd" in hk._SPUSTITELNE_PRIPONY
    assert "Pri inštalácii sa nespustí nič" in sk
    # 4. kod sa len cita (ast)
    assert "ast.parse(" in _funkcia("skontroluj_kod") and "modul `ast`" in sk
    # 5. zavislosti uz musia byt v appke; nic dalsie sa nestahuje
    assert "Nič ďalšie sa nesťahuje" in sk
    assert "skontroluj_zavislosti(" in _funkcia("skontroluj_metadata")
    # 6. az potom kod bezi; ostane len so skusobnym slovom
    assert "**vtedy už beží**" in sk and "nie ako administrátor" in sk
    assert "jedno skúšobné slovo „%s“" % hk.TEST_TEXT in sk
    # pri starte: sha256 kazdeho suboru, bez bytecode
    assert "_over_subory(priecinok, hashe)" in _funkcia("nacitaj_pri_starte")
    assert "set_data" in _read("hlas_kniznica.py") and "bytecode (`__pycache__`)" in sk
    # pred cim to nechrani - poctivo
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
    # odmietnute pre chybajucu zavislost -> "treba novsi Zanshin"
    assert hk.STAV_NEKOMPATIBILNY == "incompatible"
    assert "needs a newer Zanshin" in _en("edge.update.incompatible")
    assert "otherwise it says a newer Zanshin is needed" in otvorene


def test_how_it_works_aktualizacia_hlasu():
    ako = _plain_text(_sekcia(_read(AKO), "Updating the natural voice"))
    # finalna verzia, ziadna predbezna ani stiahnuta (yanked)
    assert "picks the newest final one (no pre-release, nothing withdrawn)" in ako
    assert 'not f.get("yanked")' in _funkcia("vyber_kandidata")
    assert 'one test word, "%s", through Microsoft' % hk.TEST_TEXT in ako
    # pri neuspechu nic nove, odkaz len tam, kde pomoze az novy Zanshin
    import app_audio
    odkazy = {stav for stav, (_s, _l, _ok, odkaz) in app_audio._VYSLEDKY_AKTUALIZACIE.items()
              if odkaz}
    assert odkazy == {hk.STAV_STALE_ODMIETNUTY, hk.STAV_NEKOMPATIBILNY}
    assert "Microsoft refuses even the newest version, or the update needs a newer Zanshin" in ako
    # pocas aktualizacie priprava caka; po uspechu sa pripravia chybajuce
    assert "_aktualizacia_hlasu_bezi" in zdroj_metody("pregenerate")
    assert "Preparing asked for in the meantime waits for the result." in ako
    assert "self.pregenerate(force=True)" in zdroj_metody("_aktualizacia_hlasu_hotova")
    assert "cues still missing their natural voice are prepared right after" in ako
    # pokazena stiahnuta pri starte: pribalena + app.log, dalej sa neskusa
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
    # zoznam zavislosti v spec == zoznam v DEVELOPMENT
    spec = _read("Dandurf.spec")
    m = re.search(r"_EDGE_ZAVISLOSTI = \(([^)]*)\)", spec)
    baliky = re.findall(r"'([\w.]+)'", m.group(1))
    build = _plain_text(_sekcia(vyvoj, "What build.bat does"))
    for balik in baliky:
        if balik == "attr":          # modul balika attrs
            continue
        assert balik in build, balik
    assert "copy_metadata('typing_extensions')" in spec and "typing_extensions" in build
    assert "'aiohttp.pytest_plugin'" in spec
    assert "without aiohttp's test modules (they would pull in pytest)" in build
    assert "I estimate under 2 MB more, but haven't measured it." in build
    # testy na siet nejdu - autouse fixture nahradi siet aj skusobne slovo
    testy = _plain_text(_sekcia(vyvoj, "Tests"))
    assert "No test goes to the network." in testy
    for subor in ("test_022h_hlas_kniznica.py", "test_022h_aktualizuj_hlas.py"):
        src = _read(os.path.join("tests", subor))
        assert "autouse=True" in src and '"_otvor"' in src, subor
        assert "`tests/%s`" % subor in testy
    assert '"_syntetizuj"' in _read(os.path.join("tests", "test_022h_aktualizuj_hlas.py"))


# --------------------------------------------------------------------------
# Poctive vety, ktore by mutacia inak presla (overenie dokumentov)
# --------------------------------------------------------------------------

def test_poctive_vety_o_tlacidle_drzia_vo_vsetkych_dokumentoch():
    """Kazda veta tu je sluba o tom, kedy tlacidlo ide na siet, co si necha
    a pred cim nechrani. Bez tohto testu ju slo vyhodit alebo obratit
    (napr. "keeps it only if that worked" -> "keeps it") a vsetky dokumentove
    testy presli."""
    over = _funkcia("_vyskusaj_a_aktivuj")
    # necha sa len to, co povedalo skusobne slovo (manifest az po nom)
    assert over.index("skusobne_slovo(") < over.index("_zapis_manifest(")
    # abort sa pyta len PRED krokom: ziadost, ktora uz leti, dobehne
    assert "abort" not in _funkcia("_http_get") and "abort" not in _funkcia("skusobne_slovo")

    # PRIVACY: priprava hlasok hned po uspechu je dalsie "kedy" pre texty
    assert ("and from 0.3 right after **Update voice** worked, if a cue's line "
            "is still missing") in _plain("PRIVACY.md")
    assert "self.pregenerate(force=True)" in zdroj_metody("_aktualizacia_hlasu_hotova")
    p = _bod_privacy()
    assert ("only a request already on its way is finished: it stops before its "
            "next step that uses the network, and nothing changes") in p
    assert "and what that can't protect you from, is in [`SAFETY.md`](SAFETY.md)" in p

    # SAFETY po anglicky: dovod obmedzenia, najnovsia verzia, bez podpisu,
    # vlastny build, a co sa deje pri kazdom starte
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

    # SAFETY po slovensky
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

    # README: necha si ho len, ked funguje; v Sukromi aj hranica kontrol
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
    """Bod 5: zavislost, ktorej verzia sa zistit neda, appka PREPUSTI (len
    ju zapise do app.log) - dokument nesmie tvrdit, ze verzia sa overi vzdy.
    A znacka py.typed sa zapise s hocijakym obsahom - "prazdna" nie je
    kontrola, takze to dokument netvrdi."""
    sk = _safety_sk()
    assert ("Keď sa verzia niektorej z nich zistiť nedá, appka ju pustí ďalej, "
            "zapíše to do `app.log` a rozhodne až import a skúšobné slovo.") in sk
    assert "neoverene.append(dist)" in _funkcia("skontroluj_zavislosti")
    assert '"verzia bez overenia: "' in _funkcia("_aktualizuj")
    assert "_zaloguj(vysledok)" in _funkcia("aktualizuj")
    # spravanie: importovatelny balik bez zistitelnej verzie neblokuje
    monkeypatch.setattr(hk, "_najdi_modul", lambda dist: "nejaky_modul")
    monkeypatch.setattr(hk, "_verzia_balika", lambda dist, modul: None)
    assert hk.skontroluj_zavislosti(["nejaky-balik>=1.0"]) == ([], ["nejaky-balik"])
    # py.typed: rozbal_wheel neskuma obsah, dokument nehovori "prazdna"
    assert 'casti[1] == "py.typed"' in _funkcia("rozbal_wheel")
    assert "prázdna značka" not in sk and "značka `py.typed`" in sk
