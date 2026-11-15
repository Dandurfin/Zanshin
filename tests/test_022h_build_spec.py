# -*- coding: utf-8 -*-
"""0.3: Dandurf.spec bundles a safeguard for edge-tts downloaded by the app.

WHY: the "Update voice" button (hlas_kniznica.py) can load a newer
edge-tts from PyPI at runtime - only its own code. That is imported
through the Python packaged in the exe, and that one has only the modules
PyInstaller saw at build time. A newer edge-tts may reach for a module
that today's does not use - the import would fail and the app would
refuse the update ("incompatible", a new Zanshin is needed). That is why
the spec bundles edge-tts's dependencies whole, plus a sensible list of
the standard library.

What this test guards:
  * the dependencies of edge-tts (aiohttp and its dependencies, tabulate,
    typing_extensions; certifi and edge_tts as before) go through
    collect_all - submodules, data, libraries and metadata (via
    dist-info the app checks the versions the new edge-tts requires) -
    without .py as data, without __main__ and without the aiohttp test
    modules (pytest_plugin would pull in pytest),
  * the list covers the WHOLE Requires-Dist tree of the installed
    edge-tts (without extras) - if a new aiohttp added a dependency, the
    test says so,
  * a package that is not on the PC does not break the build (it is just
    skipped),
  * the standard library list really is modules of this Python's
    standard library, packages are packages, __main__ is skipped, and it
    covers every standard library import in the installed edge-tts,
  * all of that really reaches Analysis (datas, binaries, hiddenimports).

The spec is run with a fake PyInstaller.utils.hooks and a fake Analysis -
nothing is built, no subprocess, no network. The edge-tts code is only
read via ast, not run.
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
    """Fake PyInstaller.utils.hooks: records calls, returns marker data."""

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
    """Runs Dandurf.spec -> (spec globals, Analysis kwargs, hooks).
    `chyba` = packages that are 'not installed'; the others are (even if
    they are not on this PC - the test does not depend on the
    environment)."""
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
# edge-tts dependencies
# --------------------------------------------------------------------------

def test_spec_bali_zavislosti_edge_tts_cele(monkeypatch):
    g, analysis, hooky = _spusti_spec(monkeypatch)
    assert tuple(g["_EDGE_ZAVISLOSTI"]) == ZAVISLOSTI
    skryte, data, kniznice = (analysis["hiddenimports"], analysis["datas"],
                              analysis["binaries"])
    for balik in ZAVISLOSTI:
        volanie = hooky.collect_all[balik]
        # bytecode in the PYZ is enough - .py sources as data are not needed
        assert volanie["include_py_files"] is False, balik
        filtr = volanie["filter_submodules"]
        assert filtr(balik) and filtr(balik + ".sub"), balik
        assert not filtr(balik + ".__main__"), balik
        # everything from collect_all reaches Analysis
        assert ("data:" + balik, ".") in data, balik
        assert ("bin:" + balik, ".") in kniznice, balik
        assert balik + ".sub" in skryte and balik + ".__main__" not in skryte, balik
    filtr = hooky.collect_all["aiohttp"]["filter_submodules"]
    for testovaci in ("aiohttp.pytest_plugin", "aiohttp.test_utils", "aiohttp.worker"):
        assert not filtr(testovaci), testovaci
    for treba in ("aiohttp.client", "aiohttp.client_ws", "aiohttp._websocket.reader_c",
                  "aiohttp.web", "aiohttp.resolver"):
        assert filtr(treba), treba
    # typing_extensions is one module: hiddenimport + metadata (dist-info)
    assert "typing_extensions" in skryte
    assert hooky.metadata == ["typing_extensions"]
    assert ("meta:typing_extensions", ".") in data
    # edge_tts and certifi whole as before (with .py - we do not change that)
    for balik in ("edge_tts", "certifi"):
        assert hooky.collect_all[balik]["include_py_files"] is True, balik
        assert ("data:" + balik, ".") in data and balik + ".sub" in skryte, balik


def test_spec_bez_chybajuceho_balika_nespadne(monkeypatch):
    """An older aiohttp lacked e.g. propcache - the build skips it."""
    _g, analysis, hooky = _spusti_spec(monkeypatch, chyba={"propcache", "typing_extensions"})
    assert "propcache" not in hooky.collect_all
    assert "typing_extensions" not in analysis["hiddenimports"]
    assert hooky.metadata == []
    assert "aiohttp.sub" in analysis["hiddenimports"]


def _strom_zavislosti(koren):
    """Names of the distributions `koren` really requires (Requires-Dist
    without extras, markers evaluated for this Python), recursively."""
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
# Standard library
# --------------------------------------------------------------------------

def test_spec_zoznam_standardnej_kniznice(monkeypatch):
    g, analysis, hooky = _spusti_spec(monkeypatch)
    moduly, baliky = g["_STDLIB_MODULY"], g["_STDLIB_BALIKY"]
    assert len(set(moduly)) == len(moduly) and len(set(baliky)) == len(baliky)
    # the recommended list from the decision on the Update voice button
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
    monkeypatch.undo()          # real find_spec, without the fake PyInstaller
    for meno in g["_STDLIB_MODULY"] + g["_STDLIB_BALIKY"]:
        assert meno.split(".")[0] in sys.stdlib_module_names, meno
        spec = importlib.util.find_spec(meno)
        assert spec is not None, meno
        if meno in g["_STDLIB_BALIKY"]:
            assert spec.submodule_search_locations, "%s nie je balik" % meno


def _importy_standardnej_kniznice(priecinok):
    """Absolute standard library imports in .py files (ast only)."""
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
    assert "Safety net for edge-tts downloaded by the app" in spec
    assert "hlas_kniznica.py" in spec and '"incompatible"' in spec
    assert "pytest_plugin would pull all of pytest into the build" in spec
    assert "Size: not measured" in spec
    # the spec's new comments are plain ASCII (except the old header)
    nove = spec[spec.index("# Safety net for edge-tts"):spec.index("extra_datas = []")]
    assert nove.isascii()
