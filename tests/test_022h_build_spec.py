# -*- coding: utf-8 -*-
"""0.2.2: Dandurf.spec bali poistku pre edge-tts stiahnuty appkou.

PRECO: tlacidlo "Aktualizovat hlas" (hlas_kniznica.py) vie za behu nacitat
novsi edge-tts z PyPI - len jeho vlastny kod. Ten sa importuje cez Python
zabaleny v exe, a ten ma len moduly, ktore PyInstaller pri builde videl.
Novsi edge-tts moze siahnut po module, ktory dnesny nepouziva - import by
zlyhal a appka by aktualizaciu odmietla ("incompatible", treba novy
Zanshin). Preto spec bali zavislosti edge-tts cele a rozumny zoznam
standardnej kniznice.

Co strazi tento test:
  * zavislosti edge-tts (aiohttp a jeho zavislosti, tabulate,
    typing_extensions; certifi a edge_tts ako doteraz) idu cez collect_all
    - podmoduly, data, kniznice aj metadata (appka podla dist-info overi
    verzie, ktore novy edge-tts ziada) - bez .py ako dat, bez __main__ a
    bez testovacich modulov aiohttp (pytest_plugin by dotiahol pytest),
  * zoznam pokryva CELY strom Requires-Dist nainstalovaneho edge-tts (bez
    extra) - keby novy aiohttp pridal zavislost, test to povie,
  * balik, ktory na PC nie je, build nezhodi (len sa preskoci),
  * zoznam standardnej kniznice su naozaj moduly standardnej kniznice
    tohto Pythonu, baliky su baliky, __main__ sa vynecha a pokryva kazdy
    import standardnej kniznice v nainstalovanom edge-tts,
  * vsetko z toho naozaj dojde do Analysis (datas, binaries, hiddenimports).

Spec sa spusti s falosnym PyInstaller.utils.hooks a falosnym Analysis -
nic sa nebuilduje, ziadny podproces, ziadna siet. Kod edge-tts sa len
cita cez ast, nespusta sa.
"""
import ast
import importlib.util
import os
import re
import sys
import types

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ZAVISLOSTI = ("aiohttp", "aiohappyeyeballs", "aiosignal", "attr", "attrs", "frozenlist",
              "multidict", "propcache", "yarl", "idna", "tabulate")


def _read(meno):
    with open(os.path.join(KOREN, meno), encoding="utf-8") as fh:
        return fh.read()


class _Hooky:
    """Falosny PyInstaller.utils.hooks: zapise volania, vrati znackove data."""

    def __init__(self):
        self.collect_all = {}
        self.submoduly = {}
        self.metadata = []

    def modul(self):
        m = types.ModuleType("PyInstaller.utils.hooks")

        def collect_all(meno, include_py_files=True, filter_submodules=lambda n: True,
                        **kw):
            self.collect_all[meno] = dict(include_py_files=include_py_files,
                                          filter_submodules=filter_submodules, **kw)
            kandidati = (meno, meno + ".sub", meno + ".__main__")
            return ([("data:" + meno, ".")], [("bin:" + meno, ".")],
                    [n for n in kandidati if filter_submodules(n)])

        def collect_submodules(meno, filter=lambda n: True, **_kw):
            self.submoduly[meno] = filter
            return [n for n in (meno, meno + ".sub", meno + ".__main__") if filter(n)]

        def copy_metadata(meno, **_kw):
            self.metadata.append(meno)
            return [("meta:" + meno, ".")]

        m.collect_all = collect_all
        m.collect_submodules = collect_submodules
        m.copy_metadata = copy_metadata
        return m


def _spusti_spec(monkeypatch, chyba=()):
    """Vykona Dandurf.spec -> (globaly specu, kwargs Analysis, hooky).
    `chyba` = baliky, ktore 'nie su nainstalovane'; ostatne su (aj ked na
    tomto PC nie su - test nezavisi od prostredia)."""
    hooky = _Hooky()
    monkeypatch.setitem(sys.modules, "PyInstaller", types.ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", types.ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooky.modul())
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda meno, *_a: None if meno in chyba else object())
    analysis = {}

    def _analysis(skripty, **kw):
        analysis.update(kw, skripty=skripty)
        return types.SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

    g = {"__name__": "__main__", "Analysis": _analysis, "PYZ": lambda *a, **k: None,
         "EXE": lambda *a, **k: None, "COLLECT": lambda *a, **k: None}
    exec(compile(_read("Dandurf.spec"), "Dandurf.spec", "exec"), g)
    return g, analysis, hooky


# --------------------------------------------------------------------------
# Zavislosti edge-tts
# --------------------------------------------------------------------------

def test_spec_bali_zavislosti_edge_tts_cele(monkeypatch):
    g, analysis, hooky = _spusti_spec(monkeypatch)
    assert tuple(g["_EDGE_ZAVISLOSTI"]) == ZAVISLOSTI
    skryte, data, kniznice = (analysis["hiddenimports"], analysis["datas"],
                              analysis["binaries"])
    for balik in ZAVISLOSTI:
        volanie = hooky.collect_all[balik]
        # bytecode v PYZ staci - .py zdrojaky ako data netreba
        assert volanie["include_py_files"] is False, balik
        filtr = volanie["filter_submodules"]
        assert filtr(balik) and filtr(balik + ".sub"), balik
        assert not filtr(balik + ".__main__"), balik
        # vsetko z collect_all dojde do Analysis
        assert ("data:" + balik, ".") in data, balik
        assert ("bin:" + balik, ".") in kniznice, balik
        assert balik + ".sub" in skryte and balik + ".__main__" not in skryte, balik
    filtr = hooky.collect_all["aiohttp"]["filter_submodules"]
    for testovaci in ("aiohttp.pytest_plugin", "aiohttp.test_utils", "aiohttp.worker"):
        assert not filtr(testovaci), testovaci
    for treba in ("aiohttp.client", "aiohttp.client_ws", "aiohttp._websocket.reader_c",
                  "aiohttp.web", "aiohttp.resolver"):
        assert filtr(treba), treba
    # typing_extensions je jeden modul: hiddenimport + metadata (dist-info)
    assert "typing_extensions" in skryte
    assert hooky.metadata == ["typing_extensions"]
    assert ("meta:typing_extensions", ".") in data
    # edge_tts a certifi cele ako doteraz (s .py - nemenime)
    for balik in ("edge_tts", "certifi"):
        assert hooky.collect_all[balik]["include_py_files"] is True, balik
        assert ("data:" + balik, ".") in data and balik + ".sub" in skryte, balik


def test_spec_bez_chybajuceho_balika_nespadne(monkeypatch):
    """Starsi aiohttp nemal napr. propcache - build ho preskoci."""
    _g, analysis, hooky = _spusti_spec(monkeypatch, chyba={"propcache", "typing_extensions"})
    assert "propcache" not in hooky.collect_all
    assert "typing_extensions" not in analysis["hiddenimports"]
    assert hooky.metadata == []
    assert "aiohttp.sub" in analysis["hiddenimports"]


def _strom_zavislosti(koren):
    """Mena distribucii, ktore `koren` naozaj ziada (Requires-Dist bez extra,
    znacky vyhodnotene pre tento Python), rekurzivne."""
    from importlib import metadata
    req = pytest.importorskip("packaging.requirements")
    utils = pytest.importorskip("packaging.utils")
    videne, fronta = set(), [koren]
    while fronta:
        dist = fronta.pop()
        for riadok in metadata.requires(dist) or ():
            r = req.Requirement(riadok)
            if r.marker and not r.marker.evaluate({"extra": ""}):
                continue
            meno = utils.canonicalize_name(r.name)
            if meno not in videne:
                videne.add(meno)
                fronta.append(meno)
    return videne


def test_spec_pokryva_cely_strom_zavislosti_nainstalovaneho_edge_tts(monkeypatch):
    from importlib import metadata
    try:
        metadata.distribution("edge-tts")
    except metadata.PackageNotFoundError:
        pytest.skip("edge-tts nie je nainstalovany")
    utils = pytest.importorskip("packaging.utils")
    strom = _strom_zavislosti("edge-tts")
    assert {"aiohttp", "certifi", "tabulate", "typing-extensions", "yarl",
            "multidict"} <= strom, strom
    moduly = {}
    for modul, dists in metadata.packages_distributions().items():
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", modul):
            for d in dists:
                moduly.setdefault(utils.canonicalize_name(d), set()).add(modul)
    g, analysis, hooky = _spusti_spec(monkeypatch)
    zbalene = set(hooky.collect_all) | {"typing_extensions"}
    chyba = {}
    for dist in sorted(strom):
        nechyba = moduly.get(dist, set())
        assert nechyba, "%s nema ziadny modul - je nainstalovany?" % dist
        if not nechyba <= zbalene:
            chyba[dist] = sorted(nechyba - zbalene)
    assert not chyba, "Dandurf.spec nebali cele: %s - pridaj ich do _EDGE_ZAVISLOSTI" % chyba


# --------------------------------------------------------------------------
# Standardna kniznica
# --------------------------------------------------------------------------

def test_spec_zoznam_standardnej_kniznice(monkeypatch):
    g, analysis, hooky = _spusti_spec(monkeypatch)
    moduly, baliky = g["_STDLIB_MODULY"], g["_STDLIB_BALIKY"]
    assert len(set(moduly)) == len(moduly) and len(set(baliky)) == len(baliky)
    # odporucany zoznam z rozhodnutia o tlacidle Aktualizovat hlas
    for meno in ("asyncio", "email", "json", "http", "urllib", "xml", "html",
                 "concurrent", "logging"):
        assert meno in baliky, meno
    for meno in ("ssl", "hashlib", "hmac", "secrets", "struct", "uuid", "zlib", "base64",
                 "dataclasses", "functools", "typing", "contextlib", "tempfile", "shutil",
                 "argparse", "io", "re", "datetime", "enum", "abc", "collections",
                 "itertools", "math", "random", "string", "textwrap", "time", "warnings",
                 "weakref", "zipfile", "importlib.metadata", "importlib.util",
                 "importlib.abc"):
        assert meno in moduly, meno
    skryte = analysis["hiddenimports"]
    for meno in moduly:
        assert meno in skryte, meno
    for balik in baliky:
        filtr = hooky.submoduly[balik]
        assert filtr(balik + ".sub") and not filtr(balik + ".__main__"), balik
        assert balik + ".sub" in skryte and balik + ".__main__" not in skryte, balik


def test_zoznam_su_naozaj_moduly_standardnej_kniznice(monkeypatch):
    g, _analysis, _hooky = _spusti_spec(monkeypatch)
    monkeypatch.undo()          # skutocne find_spec, bez falosneho PyInstalleru
    for meno in g["_STDLIB_MODULY"] + g["_STDLIB_BALIKY"]:
        assert meno.split(".")[0] in sys.stdlib_module_names, meno
        spec = importlib.util.find_spec(meno)
        assert spec is not None, meno
        if meno in g["_STDLIB_BALIKY"]:
            assert spec.submodule_search_locations, "%s nie je balik" % meno


def _importy_standardnej_kniznice(priecinok):
    """Absolutne importy standardnej kniznice v .py suboroch (len ast)."""
    mena = set()
    for subor in sorted(os.listdir(priecinok)):
        if not subor.endswith(".py"):
            continue
        with open(os.path.join(priecinok, subor), encoding="utf-8") as fh:
            strom = ast.parse(fh.read())
        for uzol in ast.walk(strom):
            if isinstance(uzol, ast.Import):
                mena.update(a.name for a in uzol.names)
            elif isinstance(uzol, ast.ImportFrom) and not uzol.level and uzol.module:
                mena.add(uzol.module)
    return {m for m in mena if m.split(".")[0] in sys.stdlib_module_names
            and m.split(".")[0] not in sys.builtin_module_names}


def test_zoznam_pokryva_importy_nainstalovaneho_edge_tts(monkeypatch):
    spec = importlib.util.find_spec("edge_tts")
    if spec is None:
        pytest.skip("edge-tts nie je nainstalovany")
    importy = _importy_standardnej_kniznice(spec.submodule_search_locations[0])
    assert {"asyncio", "ssl", "uuid", "xml.sax.saxutils"} <= importy, importy
    g, _analysis, _hooky = _spusti_spec(monkeypatch)
    moduly, baliky = set(g["_STDLIB_MODULY"]), set(g["_STDLIB_BALIKY"])
    nepokryte = sorted(m for m in importy
                       if m not in moduly and m.split(".")[0] not in baliky)
    assert not nepokryte, "Dandurf.spec: chyba v _STDLIB_MODULY / _STDLIB_BALIKY: %s" % nepokryte


def test_spec_poistku_vysvetli():
    spec = _read("Dandurf.spec")
    assert "Poistka pre edge-tts stiahnuty appkou" in spec
    assert "hlas_kniznica.py" in spec and '"incompatible"' in spec
    assert "pytest_plugin by do buildu" in spec
    assert "Velkost: nemerana" in spec
    # komentare specu po slovensky bez diakritiky (okrem starej hlavicky)
    nove = spec[spec.index("# Poistka pre edge-tts"):spec.index("extra_datas = []")]
    assert nove.isascii()
