"""Downloadable natural-voice library (edge-tts) - "Update voice".

WHY: in November 2026 Microsoft refused edge-tts 7.2.8 (HTTP 403). The fix
in edge-tts 7.3.0/7.3.1 was a CODE CHANGE (a new Sec-MS-GEC token
algorithm), so a released Zanshin with the old version bundled cannot be
fixed with data - newer edge-tts code is needed. The author's decision
(15. 11. 2026): the player can download it themselves with one click until
a new Zanshin comes out.

Rules (PRIVACY.md, SAFETY.md):
  * only on a click, never by itself and never while watching (the caller's
    `abort` is asked before every step that goes to the network),
  * only the code of the edge-tts library from PyPI - from the same source
    the build takes it from (build_all.ps1),
  * the downloaded file is verified: HTTPS with certificates from certifi,
    exact host (also after a redirect), size cap, sha256 from PyPI, the zip
    content (only edge_tts/*.py + METADATA, in memory). NOTHING is run
    during installation,
  * the dependencies from METADATA must be in this process (in the build =
    bundled) in the required version - otherwise "a newer Zanshin is
    needed",
  * the new version is tried with one fixed word (`TEST_TEXT`, never the
    player's text) and stays only if it works; otherwise the current one
    stays and the player gets a link to the official releases
    (`RELEASES_URL`).

Storage `paths.voice_lib_dir()` (in the build %APPDATA%\\Zanshin\\voice_lib):
  manifest.json                - the active downloaded version and the
                                 sha256 of its files
  edge_tts-<verzia>/edge_tts/  - the library code (only .py and py.typed)
  tmp/                         - unpacking and the test word, removed
                                 after the attempt

Loading: `_Hladac` (a MetaPathFinder at the start of sys.meta_path) serves
the package from the folder under one name - at app start under the real
"edge_tts" (it takes priority over the PyInstaller importer and over
site-packages), at runtime under a private alias, because an "edge_tts" is
already in memory, the bundled one. Every file is verified against the
sha256 from the manifest before it runs, and bytecode (__pycache__) is
neither read nor written. That the package behaves the same under the
alias as under the real name is guarded by `skontroluj_kod` (no absolute
import of "edge_tts" inside the package - 7.3.1 has only relative ones).

All functions that go to the network block - call them ONLY from a helper
thread. None of them touches Tk.
"""

import ast
import email.parser
import hashlib
import hmac
import http.client
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import io
import json
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from dataclasses import dataclass
from importlib import metadata

from logging_setup import get_logger
from paths import nahrad_subor, voice_lib_dir

_log = get_logger("hlas_kniznica")

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

PYPI_JSON_URL = "https://pypi.org/pypi/edge-tts/json"
# Official Zanshin releases - where to send the player when the voice
# cannot be fixed.
RELEASES_URL = "https://github.com/Dandurfin/Zanshin/releases/latest"
_PYPI_HOSTITELIA = frozenset({"pypi.org"})
_SUBORY_HOSTITELIA = frozenset({"files.pythonhosted.org"})
# Bare app name - no version and nothing about the player (PRIVACY.md).
USER_AGENT = "Zanshin"
HTTP_TIMEOUT_S = 15.0
MAX_PRESMEROVANI = 3
JSON_STROP_B = 4 * 1024 * 1024      # the whole edge-tts release list is ~0.2 MB
WHEEL_STROP_B = 2 * 1024 * 1024     # the 7.3.1 wheel is ~39 kB (38 908 B)
ZIP_MAX_POLOZIEK = 400
ZIP_SUBOR_STROP_B = 1024 * 1024     # biggest file of 7.3.1 (communicate.py) ~24 kB
ZIP_SPOLU_STROP_B = 8 * 1024 * 1024
METADATA_STROP_B = 512 * 1024

# Test word: a fixed neutral text, NEVER the text of the player's cue.
TEST_TEXT = "Zanshin"
TEST_HLAS = "en-GB-SoniaNeural"
TEST_TIMEOUT_S = 20.0
# The longest the module swap waits for the cache lock (one cue that is
# flying right now). After that it swaps anyway - assigning the module is
# atomic and a cue in flight keeps its old module
# (audio_engine.nastav_edge_tts).
ZAMOK_CAKANIE_S = 30.0

MANIFEST_MENO = "manifest.json"
TMP_MENO = "tmp"
_FORMAT_MANIFESTU = 1

# States of the `aktualizuj` result (machine-readable; the GUI has the
# texts in i18n).
STAV_AKTUALNY = "up_to_date"            # the newest already runs and the test word passed
STAV_AKTUALIZOVANY = "updated"          # new version active from this moment
STAV_STALE_ODMIETNUTY = "refused_still"  # Microsoft refuses even the newest
STAV_OFFLINE = "offline"                # PyPI or Microsoft unreachable
STAV_NEKOMPATIBILNY = "incompatible"    # dependencies / API / Python - a newer Zanshin is needed
STAV_OVERENIE_ZLYHALO = "verify_failed"  # host, sha256, size, zip content
STAV_ZRUSENY = "cancelled"              # watching was switched on meanwhile (`abort`)
STAV_ZANEPRAZDNENY = "busy"             # another update is running right now
STAV_CHYBA = "error"                    # anything else (disk, unexpected answer)

_KANDIDAT = "candidate"

# `\Z`, not `$`: `$` also lets through a trailing '\n' ("9.0.0\n" would pass
# for a final version and the app.log line would split in two).
_FINALNA_VERZIA = re.compile(r"^\d{1,9}(?:\.\d{1,9}){0,7}\Z")
_PRIECINOK_VERZIE = re.compile(r"^edge_tts-\d{1,9}(?:\.\d{1,9}){0,7}\Z")
_SHA256 = re.compile(r"^[0-9a-f]{64}\Z")
_MENO_MODULU = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
# Errors from the code of the downloaded library (import, Communicate(...),
# test word). SystemExit too - `sys.exit()` in the library would otherwise
# crash the app start (on every start, the manifest would not get marked) or
# the update thread (the GUI would wait forever). KeyboardInterrupt is not
# caught.
_CHYBY_KNIZNICE = (Exception, SystemExit)
_REZERVOVANE_WIN = frozenset(
    ["CON", "PRN", "AUX", "NUL"] + ["COM%d" % i for i in range(1, 10)]
    + ["LPT%d" % i for i in range(1, 10)])
# Extensions that would run by themselves during installation or import
# (.pth), or that are compiled code - the edge-tts wheel has nothing like it.
_SPUSTITELNE_PRIPONY = (".pth", ".pyd", ".so", ".dll", ".dylib", ".exe",
                        ".pyc", ".pyo", ".bat", ".cmd", ".ps1", ".sh")

# edge-tts dependencies that may be imported only for `__version__` (in the
# build their dist-info is missing - PyInstaller bundles metadata only for
# edge_tts and certifi). They are bundled libraries, not downloaded code.
_ZNAME_ZAVISLOSTI = frozenset({"aiohttp", "certifi", "tabulate", "typing_extensions"})

KNIZNICA_DIR = None     # tests redirect it; None = paths.voice_lib_dir()

_beh = threading.Lock()          # one update at a time
_nacitane = {}                   # version -> (module, finder) loaded in this run


def kniznica_dir():
    return KNIZNICA_DIR or voice_lib_dir()


def _tmp_dir():
    return os.path.join(kniznica_dir(), TMP_MENO)


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------

@dataclass
class Vysledok:
    """Result of one `aktualizuj` attempt.

    stav      - `STAV_*` (machine-readable),
    aktivna   - the edge-tts version that ran before the attempt (None = none),
    nova      - the version activated by this attempt (only with
                STAV_AKTUALIZOVANY),
    najnovsia - the newest final version on PyPI, if it could be found out,
    dovod     - a short technical reason for app.log (no paths and no player
                texts).
    """
    stav: str
    aktivna: str = None
    nova: str = None
    najnovsia: str = None
    dovod: str = ""

    @property
    def ok(self):
        return self.stav in (STAV_AKTUALNY, STAV_AKTUALIZOVANY)


class _Zlyhanie(Exception):
    """The attempt ended with the state `stav`; `dovod` goes to app.log."""

    def __init__(self, stav, dovod):
        super().__init__(dovod)
        self.stav = stav
        self.dovod = dovod


def _meno_chyby(exc):
    """Name of the error class (and of its cause for URLError) - never the
    error text, it often holds the full path and in %APPDATA% there is the
    account name (PRIVACY.md)."""
    meno = type(exc).__name__
    dovod = getattr(exc, "reason", None)
    if isinstance(exc, urllib.error.URLError) and isinstance(dovod, BaseException):
        meno += "(%s)" % type(dovod).__name__
    return meno


def _kratke(text, n=60):
    text = repr(text)
    return text if len(text) <= n else text[:n - 1] + "…"


class PokazenySubor(ImportError):
    """A file of the downloaded library does not match the manifest. The
    message carries ONLY the file name, never the path - it goes to app.log
    and into the manifest."""


def _dovod_chyby(exc):
    """Short reason for a loading failure, without paths. The ImportError text
    from Python ("cannot import name X from Y (C:\\...)") carries the path,
    so only the module name and the error class are taken from it."""
    if isinstance(exc, _Zlyhanie):
        return exc.dovod
    if isinstance(exc, PokazenySubor):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return "chyba subor %s" % os.path.basename(str(exc.filename or "?"))
    meno = getattr(exc, "name", None) if isinstance(exc, ImportError) else None
    if isinstance(meno, str) and meno:
        return "import %s: %s" % (_kratke(meno, 40), type(exc).__name__)
    return _meno_chyby(exc)


# --------------------------------------------------------------------------
# Versions and specifiers (a small comparer, without the `packaging` library)
# --------------------------------------------------------------------------
#
# `packaging` is not in the build and we will not download it. A subset of
# PEP 440 is enough: a numeric release, a/b/rc, post, dev; the local part is
# ignored. An epoch ("1!2.0") and other exotica = unknown form -> requirement
# NOT MET.

_VERZIA = re.compile(
    r"^\s*v?(?P<rel>\d+(?:\.\d+)*)"
    r"(?:[-_.]?(?P<pre>alpha|beta|preview|pre|rc|a|b|c)[-_.]?(?P<pren>\d*))?"
    r"(?:-(?P<post1>\d+)|[-_.]?(?P<post>post|rev|r)[-_.]?(?P<postn>\d*))?"
    r"(?:[-_.]?(?P<dev>dev)[-_.]?(?P<devn>\d*))?"
    r"(?:\+[a-z0-9]+(?:[-_.][a-z0-9]+)*)?\s*$", re.I)
_PRE_PORADIE = {"a": 0, "alpha": 0, "b": 1, "beta": 1,
                "c": 2, "rc": 2, "pre": 2, "preview": 2}
_DLZKA_RELEASE = 8


def _rozober_verziu(text):
    """'7.3.1rc1' -> (release, comparison key), unknown form -> None."""
    if not isinstance(text, str):
        return None
    m = _VERZIA.match(text)
    if not m:
        return None
    rel = tuple(int(c) for c in m.group("rel").split("."))
    if len(rel) > _DLZKA_RELEASE:
        return None
    ma_post = bool(m.group("post1") or m.group("post"))
    if m.group("pre"):
        pre = (_PRE_PORADIE[m.group("pre").lower()], int(m.group("pren") or 0))
    elif m.group("dev") and not ma_post:
        pre = (-1, 0)           # 1.0.dev1 comes before 1.0a1
    else:
        pre = (3, 0)            # final
    post = int(m.group("post1") or m.group("postn") or 0) if ma_post else -1
    dev = int(m.group("devn") or 0) if m.group("dev") else math.inf
    kluc = (rel + (0,) * (_DLZKA_RELEASE - len(rel)), pre, post, dev)
    return rel, kluc


def verzia_finalna(text):
    """'7.3.1' -> (7, 3, 1). Only digits and dots - a/b/rc/dev/post -> None."""
    if not isinstance(text, str) or not _FINALNA_VERZIA.match(text):
        return None
    return tuple(int(c) for c in text.split("."))


def je_novsia(a, b):
    """Is version `a` newer than `b`? An unknown `b` (None) = yes, an unknown
    form of `a` = no."""
    ra = _rozober_verziu(a)
    if ra is None:
        return False
    rb = _rozober_verziu(b) if b else None
    if rb is None:
        return True
    return ra[1] > rb[1]


def _predpona(rel, n):
    return (tuple(rel) + (0,) * n)[:n]


_KLAUZULA = re.compile(r"^\s*(~=|==|!=|<=|>=|<|>)\s*(\S+)\s*$")


def splna_poziadavku(verzia, specifikator):
    """Does `verzia` (text) meet `specifikator` ('>=3.8.0,<4.0.0')?

    An empty specifier = no restriction. Operators >=, >, <=, <, ==, !=,
    ~= and ==X.* / !=X.*, joined by commas. An unknown form (===, URL,
    epoch, nonsense) -> False: better to refuse than to let through
    something that does not fit."""
    if specifikator is None:
        return True
    if not isinstance(specifikator, str):
        return False
    spec = specifikator.strip()
    if not spec:
        return True
    v = _rozober_verziu(verzia)
    if v is None:
        return False
    v_rel, v_kluc = v
    for klauzula in spec.split(","):
        m = _KLAUZULA.match(klauzula)
        if not m:
            return False
        op, ciel = m.groups()
        if ciel.endswith(".*"):
            if op not in ("==", "!=") or not re.fullmatch(r"\d+(?:\.\d+)*", ciel[:-2]):
                return False
            pred = tuple(int(c) for c in ciel[:-2].split("."))
            zhoda = _predpona(v_rel, len(pred)) == pred
            if zhoda != (op == "=="):
                return False
            continue
        c = _rozober_verziu(ciel)
        if c is None:
            return False
        c_rel, c_kluc = c
        if op == "~=":
            if len(c_rel) < 2:
                return False
            pred = c_rel[:-1]
            if v_kluc < c_kluc or _predpona(v_rel, len(pred)) != pred:
                return False
            continue
        vyhovuje = {"==": v_kluc == c_kluc, "!=": v_kluc != c_kluc,
                    "<": v_kluc < c_kluc, "<=": v_kluc <= c_kluc,
                    ">": v_kluc > c_kluc, ">=": v_kluc >= c_kluc}[op]
        if not vyhovuje:
            return False
    return True


def _python_verzia():
    return "%d.%d.%d" % sys.version_info[:3]


def _normalizuj_meno(meno):
    return re.sub(r"[-_.]+", "-", str(meno or "")).strip().lower()


# --------------------------------------------------------------------------
# Environment markers in Requires-Dist (PEP 508, a subset)
# --------------------------------------------------------------------------

class _NeznamaZnacka(Exception):
    pass


_ZNACKA_TOKEN = re.compile(
    r"""\s*(?:(?P<s>'[^']*'|"[^"]*")|(?P<op>===|==|!=|<=|>=|~=|<|>)"""
    r"""|(?P<z>[()])|(?P<w>[A-Za-z_][A-Za-z0-9_.]*))""")
_VERZIOVE_PREMENNE = frozenset({"python_version", "python_full_version",
                                "implementation_version"})


def _prostredie():
    return {
        "python_version": "%d.%d" % sys.version_info[:2],
        "python_full_version": _python_verzia(),
        "implementation_version": "%d.%d.%d" % tuple(sys.implementation.version[:3]),
        "implementation_name": sys.implementation.name,
        "platform_python_implementation": platform.python_implementation(),
        "sys_platform": sys.platform,
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "os_name": os.name,
    }


def _tokeny_znacky(text):
    text = text.strip()
    tokeny, poz = [], 0
    while poz < len(text):
        m = _ZNACKA_TOKEN.match(text, poz)
        if not m or m.end() == poz:
            raise _NeznamaZnacka(text)
        poz = m.end()
        if m.group("s") is not None:
            tokeny.append(("s", m.group("s")[1:-1]))
        elif m.group("op"):
            tokeny.append(("op", m.group("op")))
        elif m.group("z"):
            tokeny.append((m.group("z"), m.group("z")))
        elif m.group("w") in ("and", "or", "in", "not"):
            tokeny.append((m.group("w"), m.group("w")))
        else:
            tokeny.append(("v", m.group("w")))
    return tokeny


class _ZnackaParser:
    """vyraz := a ('or' a)* ; a := atom ('and' atom)* ;
    atom := '(' vyraz ')' | hodnota op hodnota"""

    def __init__(self, tokeny, prostredie):
        self.t = tokeny
        self.i = 0
        self.env = prostredie

    def _pozri(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def _vezmi(self):
        if self.i >= len(self.t):
            raise _NeznamaZnacka("koniec")
        tok = self.t[self.i]
        self.i += 1
        return tok

    def cely(self):
        hodnota = self.vyraz()
        if self.i != len(self.t):
            raise _NeznamaZnacka("zvysok")
        return hodnota

    def vyraz(self):
        hodnota = self.a_vyraz()
        while self._pozri() == "or":
            self._vezmi()
            dalsia = self.a_vyraz()
            hodnota = hodnota or dalsia
        return hodnota

    def a_vyraz(self):
        hodnota = self.atom()
        while self._pozri() == "and":
            self._vezmi()
            dalsia = self.atom()
            hodnota = hodnota and dalsia
        return hodnota

    def atom(self):
        if self._pozri() == "(":
            self._vezmi()
            hodnota = self.vyraz()
            if self._vezmi()[0] != ")":
                raise _NeznamaZnacka(")")
            return hodnota
        lavy = self._hodnota()
        op = self._operator()
        pravy = self._hodnota()
        return self._porovnaj(lavy, op, pravy)

    def _hodnota(self):
        druh, text = self._vezmi()
        if druh == "s":
            return (False, text)
        if druh == "v" and text in self.env:
            return (text in _VERZIOVE_PREMENNE, self.env[text])
        raise _NeznamaZnacka(text)

    def _operator(self):
        druh, text = self._vezmi()
        if druh == "op":
            return text
        if druh == "in":
            return "in"
        if druh == "not" and self._vezmi()[0] == "in":
            return "not in"
        raise _NeznamaZnacka(text)

    @staticmethod
    def _porovnaj(lavy, op, pravy):
        (l_verzia, l), (p_verzia, p) = lavy, pravy
        if op == "in":
            return l in p
        if op == "not in":
            return l not in p
        if (l_verzia or p_verzia) and op != "===":
            if _rozober_verziu(l) is not None and _rozober_verziu(p) is not None:
                return splna_poziadavku(l, op + p)
        if op == "==":
            return l == p
        if op == "!=":
            return l != p
        raise _NeznamaZnacka(op)


def plati_znacka(znacka):
    """Does the environment marker ('python_version < "3.11"') hold in this
    process? Unknown form -> True: the requirement gets checked, to be safe."""
    try:
        return bool(_ZnackaParser(_tokeny_znacky(znacka), _prostredie()).cely())
    except (_NeznamaZnacka, IndexError, ValueError, TypeError):
        return True


# --------------------------------------------------------------------------
# Dependencies from METADATA
# --------------------------------------------------------------------------

_POZIADAVKA = re.compile(
    r"^\s*(?P<meno>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*"
    r"(?:\[[^\]]*\])?\s*(?P<spec>.*?)\s*$")


def rozober_poziadavku(riadok):
    """'aiohttp<4.0.0,>=3.8.0' -> ('aiohttp', '<4.0.0,>=3.8.0', '').
    Returns (meno, specifikator, znacka); znacka is the text after ';'."""
    if not isinstance(riadok, str):
        raise ValueError("poziadavka nie je text")
    cast, _, znacka = riadok.partition(";")
    m = _POZIADAVKA.match(cast)
    if not m:
        raise ValueError("necitatelna poziadavka")
    spec = m.group("spec")
    if spec.startswith("(") and spec.endswith(")"):
        spec = spec[1:-1].strip()      # old form "foo (>=1.0)"
    return m.group("meno"), spec, znacka.strip()


def _najdi_modul(dist):
    """Importable name of the package `dist` in this process, or None.
    Nothing is run while doing so (`find_spec` only looks up top-level
    names)."""
    norm = re.sub(r"[-_.]+", "_", dist).lower()
    kandidati = []
    try:
        for top, dists in metadata.packages_distributions().items():
            if any(_normalizuj_meno(d) == _normalizuj_meno(dist) for d in dists):
                kandidati.append(top)
    except Exception:
        pass
    kandidati.sort(key=lambda m: m.lower() != norm)
    kandidati.append(norm)
    for meno in kandidati:
        if not _MENO_MODULU.match(meno):
            continue
        if meno in sys.modules:
            return meno
        try:
            if importlib.util.find_spec(meno) is not None:
                return meno
        except (ImportError, ValueError):
            continue
    return None


def _verzia_balika(dist, modul):
    """Version of the installed (in the build: bundled) package, or None.

    First the dist-info (`importlib.metadata`). In the build only edge_tts
    and certifi have it (collect_all), so as a fallback `__version__` - from
    a module that is already in memory, or from the edge-tts dependencies
    (`_ZNAME_ZAVISLOSTI`)."""
    try:
        verzia = metadata.version(dist)
        if verzia:
            return verzia
    except Exception:
        pass
    mod = sys.modules.get(modul)
    if mod is None and modul in _ZNAME_ZAVISLOSTI:
        try:
            mod = importlib.import_module(modul)
        except Exception:
            mod = None
    verzia = getattr(mod, "__version__", None) if mod is not None else None
    return verzia.strip() if isinstance(verzia, str) and verzia.strip() else None


def skontroluj_zavislosti(riadky):
    """Requires-Dist lines -> (problemy, neoverene).

    problemy  - what is missing or old (a newer Zanshin is needed);
                empty = OK,
    neoverene - packages that are here, but whose version cannot be found
                out (in the build without dist-info and without
                `__version__`, e.g. typing_extensions). They are let
                through: the import and the test word decide about them.

    Lines with an `extra` marker (optional add-ons, e.g. 'extra == "dev"')
    are skipped, the other markers are evaluated (`plati_znacka`)."""
    problemy, neoverene = [], []
    for riadok in riadky or ():
        try:
            dist, spec, znacka = rozober_poziadavku(riadok)
        except ValueError:
            problemy.append(_kratke(riadok))
            continue
        if znacka:
            if re.search(r"\bextra\b", znacka):
                continue
            if not plati_znacka(znacka):
                continue
        if spec.startswith("@"):
            problemy.append("%s (URL)" % dist)
            continue
        modul = _najdi_modul(dist)
        if modul is None:
            problemy.append("%s chyba" % dist)
            continue
        verzia = _verzia_balika(dist, modul)
        if verzia is None:
            if spec:
                neoverene.append(dist)
            continue
        if not splna_poziadavku(verzia, spec):
            problemy.append("%s %s nesplna %s" % (dist, verzia, _kratke(spec, 40)[1:-1]))
    return problemy, neoverene


def skontroluj_metadata(text, verzia, python_verzia=None):
    """METADATA from the wheel: name and version match, Python and the
    dependencies are here. Returns the list of unverified dependencies
    (see `skontroluj_zavislosti`)."""
    python_verzia = python_verzia or _python_verzia()
    sprava = email.parser.HeaderParser().parsestr(text)
    if (_normalizuj_meno(sprava.get("Name")) != "edge-tts"
            or (sprava.get("Version") or "").strip() != verzia):
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "METADATA nesedi s verziou %s" % verzia)
    rp = sprava.get("Requires-Python")
    if rp and not splna_poziadavku(python_verzia, rp):
        raise _Zlyhanie(STAV_NEKOMPATIBILNY, "Python %s nesplna Requires-Python %s"
                        % (python_verzia, _kratke(rp, 40)))
    problemy, neoverene = skontroluj_zavislosti(sprava.get_all("Requires-Dist") or [])
    if problemy:
        raise _Zlyhanie(STAV_NEKOMPATIBILNY, "zavislosti: " + ", ".join(problemy[:4]))
    return neoverene


# --------------------------------------------------------------------------
# Network (the only place in the module that goes out)
# --------------------------------------------------------------------------

def _over_url(url, hostitelia):
    """Only https, exact host, no name/password in the URL, port 443."""
    try:
        cast = urllib.parse.urlsplit(url)
        port = cast.port
    except (ValueError, TypeError, AttributeError):
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "neplatna adresa") from None
    if (cast.scheme != "https" or cast.username or cast.password
            or (cast.hostname or "").lower() not in hostitelia
            or port not in (None, 443)):
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO,
                        "adresa mimo %s" % "/".join(sorted(hostitelia)))


class _OverenePresmerovanie(urllib.request.HTTPRedirectHandler):
    """Redirect only to an allowed host - every hop is verified."""

    max_redirections = MAX_PRESMEROVANI

    def __init__(self, hostitelia):
        super().__init__()
        self.hostitelia = hostitelia

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _over_url(newurl, self.hostitelia)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _otvor(req, hostitelia):
    """Opens the request over HTTPS with certificates from certifi. Tests
    replace it - they must never go to the network."""
    import ssl

    import certifi
    kontext = ssl.create_default_context(cafile=certifi.where())
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=kontext),
        _OverenePresmerovanie(hostitelia))
    return opener.open(req, timeout=HTTP_TIMEOUT_S)


def _citaj_so_stropom(resp, strop):
    kusy, spolu = [], 0
    while True:
        kus = resp.read(64 * 1024)
        if not kus:
            break
        spolu += len(kus)
        if spolu > strop:
            raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "odpoved je vacsia nez %d B" % strop)
        kusy.append(kus)
    return b"".join(kusy)


def _http_get(url, strop, hostitelia, accept="*/*"):
    """GET `url` -> bytes. Verifies the address before and after a redirect
    and the size cap. Network errors -> STAV_OFFLINE, HTTP error ->
    STAV_CHYBA."""
    _over_url(url, hostitelia)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": accept})
    try:
        with _otvor(req, hostitelia) as resp:
            _over_url(resp.geturl(), hostitelia)
            hlavicky = getattr(resp, "headers", None)
            dlzka = hlavicky.get("Content-Length") if hlavicky is not None else None
            if dlzka and str(dlzka).strip().isdigit() and int(dlzka) > strop:
                raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "odpoved je vacsia nez %d B" % strop)
            return _citaj_so_stropom(resp, strop)
    except _Zlyhanie:
        raise
    except urllib.error.HTTPError as exc:
        raise _Zlyhanie(STAV_CHYBA, "HTTP %s" % exc.code) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        raise _Zlyhanie(STAV_OFFLINE, "spojenie: %s" % _meno_chyby(exc)) from None


def stiahni_zoznam_vydani():
    """JSON of the edge-tts project from PyPI (dict). Blocks - thread only."""
    obsah = _http_get(PYPI_JSON_URL, JSON_STROP_B, _PYPI_HOSTITELIA,
                      accept="application/json")
    try:
        data = json.loads(obsah.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _Zlyhanie(STAV_CHYBA, "PyPI: odpoved nie je JSON") from None
    if not isinstance(data, dict):
        raise _Zlyhanie(STAV_CHYBA, "PyPI: necakany tvar odpovede")
    return data


# --------------------------------------------------------------------------
# Choosing a version from PyPI
# --------------------------------------------------------------------------

def _vydania_z_json(data):
    """{version: [files]} - from "releases", or (should PyPI ever drop
    "releases") at least the newest version from "info" + "urls"."""
    vydania = data.get("releases") if isinstance(data, dict) else None
    if isinstance(vydania, dict) and vydania:
        return vydania
    info = data.get("info") if isinstance(data, dict) else None
    verzia = info.get("version") if isinstance(info, dict) else None
    subory = data.get("urls") if isinstance(data, dict) else None
    if isinstance(verzia, str) and isinstance(subory, list):
        return {verzia: subory}
    raise _Zlyhanie(STAV_CHYBA, "PyPI: necakany tvar odpovede")


def _vhodny_subor(verzia, subory, python_verzia):
    """A py3-none-any wheel of the given version that may be downloaded, or
    (None, dovod)."""
    ocakavany = "edge_tts-%s-py3-none-any.whl" % verzia
    dovod = "bez wheelu py3-none-any"
    for f in subory:
        if f.get("packagetype") != "bdist_wheel" or f.get("filename") != ocakavany:
            continue
        digests = f.get("digests")
        sha = digests.get("sha256") if isinstance(digests, dict) else None
        sha = sha.lower() if isinstance(sha, str) else None
        if not sha or not _SHA256.match(sha):
            dovod = "bez sha256"
            continue
        url = f.get("url")
        try:
            _over_url(url, _SUBORY_HOSTITELIA)
        except _Zlyhanie:
            dovod = "subor mimo files.pythonhosted.org"
            continue
        velkost = f.get("size")
        if velkost is not None and (isinstance(velkost, bool) or not isinstance(velkost, int)
                                    or velkost <= 0 or velkost > WHEEL_STROP_B):
            dovod = "velkost %s" % _kratke(velkost, 20)
            continue
        rp = f.get("requires_python")
        if rp not in (None, "") and not splna_poziadavku(python_verzia, rp):
            dovod = "Python %s nesplna %s" % (python_verzia, _kratke(rp, 40))
            continue
        return {"stav": _KANDIDAT, "verzia": verzia, "url": url, "sha256": sha,
                "subor": ocakavany, "velkost": velkost, "requires_python": rp}, ""
    return None, dovod


def vyber_kandidata(data, aktivna, python_verzia=None):
    """From the PyPI JSON picks the newest FINAL version (digits and dots
    only), not withdrawn (yanked), with a py3-none-any wheel for this Python
    and newer than `aktivna`.

    Returns a dict with "stav":
      "candidate"      + verzia, url, sha256, subor, velkost, najnovsia,
      STAV_AKTUALNY    - nothing newer (najnovsia = the newest final at all),
      STAV_NEKOMPATIBILNY - newer versions exist, but none can be used here.
    """
    python_verzia = python_verzia or _python_verzia()
    vydania = _vydania_z_json(data)
    vsetky, novsie = [], []
    for verzia, subory in vydania.items():
        t = verzia_finalna(verzia)
        if t is None or not isinstance(subory, list):
            continue            # pre-release, dev, post, local or broken
        platne = [f for f in subory if isinstance(f, dict) and not f.get("yanked")]
        if not platne:
            continue            # withdrawn (yanked) release or no files
        vsetky.append((t, verzia))
        if aktivna is None or je_novsia(verzia, aktivna):
            novsie.append((t, verzia, platne))
    najnovsia = max(vsetky)[1] if vsetky else None
    if not novsie:
        return {"stav": STAV_AKTUALNY, "najnovsia": najnovsia}
    novsie.sort(key=lambda x: x[0], reverse=True)
    dovody = []
    for _t, verzia, platne in novsie:
        subor, dovod = _vhodny_subor(verzia, platne, python_verzia)
        if subor is not None:
            subor["najnovsia"] = najnovsia
            return subor
        dovody.append("%s: %s" % (verzia, dovod))
    return {"stav": STAV_NEKOMPATIBILNY, "najnovsia": najnovsia,
            "dovod": "; ".join(dovody[:3])}


def stiahni_wheel(kandidat):
    """Downloads the candidate wheel, verifies size and PyPI sha256. Blocks."""
    data = _http_get(kandidat["url"], WHEEL_STROP_B, _SUBORY_HOSTITELIA)
    velkost = kandidat.get("velkost")
    if velkost is not None and len(data) != velkost:
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "velkost wheelu nesedi s PyPI")
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), kandidat["sha256"]):
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "sha256 wheelu nesedi s PyPI")
    return data


# --------------------------------------------------------------------------
# Wheel content (in memory, nothing is run)
# --------------------------------------------------------------------------

def _zly_zip(dovod):
    return _Zlyhanie(STAV_OVERENIE_ZLYHALO, "zip: " + dovod)


def _over_meno_v_zipe(info):
    """A safe zip entry name (with '/'), otherwise _Zlyhanie verify_failed.

    `orig_filename` is the name as it is in the archive: on Windows zipfile
    turns '\\' into '/' already when reading, so the backslash is only
    visible there."""
    povodne = info.orig_filename
    meno = info.filename
    if not isinstance(povodne, str) or not povodne or len(povodne) > 255:
        raise _zly_zip("neplatne meno polozky")
    if "\\" in povodne or "\x00" in povodne:
        raise _zly_zip("spatna lomka v mene %s" % _kratke(povodne))
    if meno.startswith("/") or ":" in meno:
        raise _zly_zip("absolutna cesta alebo disk %s" % _kratke(meno))
    if any(ord(z) < 32 or z in '<>"|?*' for z in meno):
        raise _zly_zip("nepovoleny znak v mene %s" % _kratke(meno))
    casti = meno[:-1].split("/") if meno.endswith("/") else meno.split("/")
    if not casti or any(c in ("", ".", "..") for c in casti):
        raise _zly_zip("cesta von z priecinka %s" % _kratke(meno))
    if any(c != c.rstrip(" .") for c in casti):
        raise _zly_zip("bodka alebo medzera na konci mena %s" % _kratke(meno))
    return meno


def _over_typ_polozky(info, meno):
    rezim = (info.external_attr >> 16) & 0xFFFF
    typ = rezim & 0o170000
    if typ not in (0, 0o100000, 0o040000):
        raise _zly_zip("symbolicky odkaz alebo specialny subor %s" % _kratke(meno))
    if typ == 0o040000 and not meno.endswith("/"):
        raise _zly_zip("priecinok bez lomky %s" % _kratke(meno))
    if info.flag_bits & 0x1:
        raise _zly_zip("sifrovana polozka")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise _zly_zip("nepodporovana kompresia")
    if info.file_size < 0 or info.file_size > ZIP_SUBOR_STROP_B:
        raise _zly_zip("polozka je vacsia nez %d B" % ZIP_SUBOR_STROP_B)
    if meno.endswith("/") and info.file_size:
        raise _zly_zip("priecinok s obsahom")


def _je_modul_py(meno_suboru):
    if not meno_suboru.endswith(".py"):
        return False
    kmen = meno_suboru[:-3]
    return bool(_MENO_MODULU.match(kmen)) and kmen.upper() not in _REZERVOVANE_WIN


def _precitaj(zf, info, strop):
    try:
        with zf.open(info) as fh:
            obsah = fh.read(strop + 1)
    except (zipfile.BadZipFile, zlib.error, OSError, EOFError, RuntimeError,
            NotImplementedError, ValueError):
        raise _zly_zip("poskodena polozka %s" % _kratke(info.filename)) from None
    if len(obsah) > strop or len(obsah) != info.file_size:
        raise _zly_zip("velkost polozky nesedi %s" % _kratke(info.filename))
    return obsah


def rozbal_wheel(data, verzia):
    """Wheel (bytes) -> ({file_name: content} for edge_tts/, METADATA text).

    ONLY the files "edge_tts/<meno>.py" and "edge_tts/py.typed" are
    unpacked (7.3.1 has no subfolder in edge_tts). METADATA is only read
    into memory. The helper player edge_playback/ and the other dist-info
    files (RECORD, WHEEL, licence) are in the wheel too - they are not
    taken, only their names are verified. Anything else in the wheel =
    rejection."""
    distinfo = "edge_tts-%s.dist-info/" % verzia
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError, EOFError):
        raise _zly_zip("nie je platny zip") from None
    with zf:
        polozky = zf.infolist()
        if len(polozky) > ZIP_MAX_POLOZIEK:
            raise _zly_zip("prilis vela poloziek")
        videne, spolu = set(), 0
        na_rozbalenie, metadata_info = {}, None
        for info in polozky:
            meno = _over_meno_v_zipe(info)
            kluc = meno.rstrip("/").casefold()
            if kluc in videne:
                raise _zly_zip("duplicitna polozka %s" % _kratke(meno))
            videne.add(kluc)
            _over_typ_polozky(info, meno)
            spolu += info.file_size
            if spolu > ZIP_SPOLU_STROP_B:
                raise _zly_zip("obsah je vacsi nez %d B" % ZIP_SPOLU_STROP_B)
            if meno.endswith("/"):
                continue                # a folder - its files get verified on their own
            casti = meno.split("/")
            if (any(c.lower().endswith(_SPUSTITELNE_PRIPONY) for c in casti)
                    or casti[0].lower().endswith(".data")):
                raise _zly_zip("subor, ktory by sa spustal %s" % _kratke(meno))
            if casti[0] == "edge_tts":
                if len(casti) != 2:
                    raise _Zlyhanie(STAV_NEKOMPATIBILNY,
                                    "podpriecinok v edge_tts %s" % _kratke(meno))
                if casti[1] == "py.typed" or _je_modul_py(casti[1]):
                    na_rozbalenie[casti[1]] = info
                else:
                    raise _Zlyhanie(STAV_NEKOMPATIBILNY,
                                    "necakany subor v edge_tts %s" % _kratke(meno))
            elif meno == distinfo + "METADATA":
                metadata_info = info
            elif meno.startswith(distinfo):
                pass                    # RECORD, WHEEL, licence - not unpacked
            elif (casti[0] == "edge_playback" and len(casti) == 2
                  and (casti[1] == "py.typed" or _je_modul_py(casti[1]))):
                pass                    # player from the wheel - Zanshin does not use it
            elif casti[0].endswith(".dist-info"):
                raise _zly_zip("metadata inej verzie %s" % _kratke(meno))
            else:
                raise _Zlyhanie(STAV_NEKOMPATIBILNY, "necakany subor %s" % _kratke(meno))
        if "__init__.py" not in na_rozbalenie:
            raise _Zlyhanie(STAV_NEKOMPATIBILNY, "chyba edge_tts/__init__.py")
        if metadata_info is None:
            raise _zly_zip("chyba METADATA")
        subory = {meno: _precitaj(zf, info, ZIP_SUBOR_STROP_B)
                  for meno, info in na_rozbalenie.items()}
        try:
            metadata_text = _precitaj(zf, metadata_info, METADATA_STROP_B).decode("utf-8")
        except UnicodeDecodeError:
            raise _zly_zip("METADATA nie je UTF-8") from None
    return subory, metadata_text


def _je_dynamicky_import(uzol):
    f = uzol.func
    meno = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
    return (meno in ("import_module", "__import__") and uzol.args
            and isinstance(uzol.args[0], ast.Constant)
            and isinstance(uzol.args[0].value, str))


def skontroluj_kod(subory):
    """The sources can be read (ast.parse only - nothing is run) and the
    package does not import itself absolutely ("import edge_tts..."). Such
    an import under the alias at runtime would pull in the BUNDLED version
    and mix two versions at once."""
    for meno, obsah in sorted(subory.items()):
        if not meno.endswith(".py"):
            continue
        try:
            strom = ast.parse(obsah, filename=meno)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            raise _Zlyhanie(STAV_NEKOMPATIBILNY, "%s sa neda precitat" % meno) from None
        for uzol in ast.walk(strom):
            if isinstance(uzol, ast.Import):
                mena = [a.name for a in uzol.names]
            elif isinstance(uzol, ast.ImportFrom) and not uzol.level:
                mena = [uzol.module or ""]
            elif isinstance(uzol, ast.Call) and _je_dynamicky_import(uzol):
                mena = [uzol.args[0].value]
            else:
                continue
            if any(m == "edge_tts" or m.startswith("edge_tts.") for m in mena):
                raise _Zlyhanie(STAV_NEKOMPATIBILNY, "%s importuje edge_tts absolutne" % meno)


# --------------------------------------------------------------------------
# Loading the verified package (MetaPathFinder + loader with sha256)
# --------------------------------------------------------------------------

class _OverenyLoader(importlib.machinery.SourceFileLoader):
    """Loads ONE .py file and verifies its sha256 before running it.

    Bytecode is neither read nor written: something that was never verified
    could lie in __pycache__, and nothing is written into the library
    folder after installation."""

    def __init__(self, fullname, path, ocakavany_hash):
        super().__init__(fullname, path)
        self._hash = ocakavany_hash

    def get_data(self, path):
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(self.path)):
            raise OSError("loader cita len vlastny subor")
        with open(path, "rb") as fh:
            data = fh.read(ZIP_SUBOR_STROP_B + 1)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), self._hash):
            raise PokazenySubor("%s: obsah nesedi s manifestom" % os.path.basename(path),
                                name=self.name)
        return data

    def get_code(self, fullname):
        cesta = self.get_filename(fullname)
        return self.source_to_code(self.get_data(cesta), cesta)

    def set_data(self, *args, **kwargs):
        return None


class _Hladac(importlib.abc.MetaPathFinder):
    """Serves ONLY `meno` and `meno.<modul>` from one package folder.

    At start `meno` is "edge_tts" and the finder sits at sys.meta_path[0],
    i.e. before the PyInstaller importer and before site-packages -
    otherwise the bundled version would get loaded. Other names it leaves to
    the next finders (returns None). A module under its name that is not in
    the manifest (a subfolder, a planted file) it rejects outright - not
    even the ordinary PathFinder may find it."""

    def __init__(self, meno, priecinok, hashe):
        self.meno = meno
        self.priecinok = priecinok
        self.hashe = dict(hashe)

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.meno:
            subor, balik = "__init__.py", True
        elif fullname.startswith(self.meno + "."):
            zvysok = fullname[len(self.meno) + 1:]
            subor, balik = zvysok + ".py", False
            if (not _MENO_MODULU.match(zvysok) or zvysok == "__init__"
                    or subor not in self.hashe):
                raise ModuleNotFoundError("No module named %r" % fullname, name=fullname)
        else:
            return None
        cesta = os.path.join(self.priecinok, subor)
        loader = _OverenyLoader(fullname, cesta, self.hashe[subor])
        return importlib.util.spec_from_file_location(
            fullname, cesta, loader=loader,
            submodule_search_locations=[self.priecinok] if balik else None)


def _pridaj_hladac(hladac):
    # A new list instead of insert/remove: an import in another thread may be
    # walking the old list right now and shifting the items would make it
    # skip a finder.
    sys.meta_path = [hladac] + [f for f in sys.meta_path if f is not hladac]


def _odober_hladac(hladac):
    sys.meta_path = [f for f in sys.meta_path if f is not hladac]


def _zabudni_moduly(meno):
    for kluc in [k for k in list(sys.modules) if k == meno or k.startswith(meno + ".")]:
        sys.modules.pop(kluc, None)


def nacitaj_balik(meno, priecinok_balika, hashe):
    """Loads the package from `priecinok_balika` as `meno` -> (module, finder).

    The finder stays on sys.meta_path as long as the module lives (edge-tts
    may pull in a submodule later). On an error the finder and any partly
    loaded modules are removed and the error is raised on."""
    if meno in sys.modules:
        raise ImportError("meno %s uz je obsadene" % meno, name=meno)
    hladac = _Hladac(meno, priecinok_balika, hashe)
    _pridaj_hladac(hladac)
    try:
        modul = importlib.import_module(meno)
    except BaseException:
        _odober_hladac(hladac)
        _zabudni_moduly(meno)
        raise
    return modul, hladac


def zahod_balik(modul, hladac):
    """The opposite of `nacitaj_balik` - for a candidate that did not pass."""
    _odober_hladac(hladac)
    if modul is not None:
        _zabudni_moduly(modul.__name__)


def _alias(verzia):
    return "_zanshin_edge_tts_%s_%s" % (verzia.replace(".", "_"), uuid.uuid4().hex[:8])


def over_api(modul):
    """API smoke test without the network: Communicate with a save coroutine
    and a constructor with (text, voice, rate=...) - exactly what
    EdgeTTSCache.ensure calls."""
    trieda = getattr(modul, "Communicate", None)
    if not isinstance(trieda, type):
        raise _Zlyhanie(STAV_NEKOMPATIBILNY, "API: chyba Communicate")
    if not inspect.iscoroutinefunction(getattr(trieda, "save", None)):
        raise _Zlyhanie(STAV_NEKOMPATIBILNY, "API: Communicate.save nie je korutina")
    try:
        trieda(TEST_TEXT, TEST_HLAS, rate="+0%")
    except _CHYBY_KNIZNICE as exc:
        raise _Zlyhanie(STAV_NEKOMPATIBILNY, "API: Communicate(...) %s" % _meno_chyby(exc)) from None


def verzia_modulu(modul):
    """`__version__` of the edge-tts module, else from dist-info, else None."""
    verzia = getattr(modul, "__version__", None)
    if isinstance(verzia, str) and verzia.strip():
        return verzia.strip()
    return pribalena_verzia()


def pribalena_verzia():
    """Version of the bundled (installed) edge-tts by dist-info, or None.
    Works in the build, because collect_all('edge_tts') bundles the
    dist-info too. The downloaded package has no dist-info, so this is
    always the bundled version."""
    try:
        return metadata.version("edge-tts") or None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Manifest and folders on disk
# --------------------------------------------------------------------------

def _teraz():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _platny_manifest(udaje):
    if not isinstance(udaje, dict) or udaje.get("format") != _FORMAT_MANIFESTU:
        return None
    verzia = udaje.get("version")
    if verzia_finalna(verzia) is None or udaje.get("folder") != "edge_tts-%s" % verzia:
        return None
    subory = udaje.get("files")
    if not isinstance(subory, dict) or "__init__.py" not in subory:
        return None
    for meno, sha in subory.items():
        if not (meno == "py.typed" or _je_modul_py(meno)):
            return None
        if not isinstance(sha, str) or not _SHA256.match(sha):
            return None
    if not isinstance(udaje.get("broken", False), bool):
        return None
    return udaje


def citaj_manifest():
    """A valid manifest of the downloaded library, or None (nothing
    downloaded, broken file). Never raises."""
    try:
        with open(os.path.join(kniznica_dir(), MANIFEST_MENO), encoding="utf-8") as fh:
            obsah = fh.read(256 * 1024)
        return _platny_manifest(json.loads(obsah))
    except (OSError, ValueError, TypeError):
        return None


def _zapis_manifest(udaje):
    koren = kniznica_dir()
    os.makedirs(koren, exist_ok=True)
    ciel = os.path.join(koren, MANIFEST_MENO)
    tmp = ciel + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(udaje, fh, ensure_ascii=True, indent=1, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    nahrad_subor(tmp, ciel, uprac_zdroj=True)


def oznac_pokazenu(dovod):
    """The downloaded library did not load - on the next start it is no
    longer tried (until the button replaces it). A write error is only
    logged."""
    manifest = citaj_manifest()
    if manifest is None:
        return
    manifest = dict(manifest, broken=True, broken_reason=str(dovod)[:80],
                    broken_at=_teraz())
    try:
        _zapis_manifest(manifest)
    except Exception as exc:
        _log.warning("prirodzeny hlas: stiahnutu kniznicu sa nepodarilo oznacit "
                     "ako pokazenu (%s)", _meno_chyby(exc))


def _priecinok_balika(manifest):
    return os.path.join(kniznica_dir(), manifest["folder"], "edge_tts")


def _over_subory(priecinok, hashe):
    """All files from the manifest are on disk and their sha256 matches."""
    for meno, sha in hashe.items():
        with open(os.path.join(priecinok, meno), "rb") as fh:
            data = fh.read(ZIP_SUBOR_STROP_B + 1)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), sha):
            raise PokazenySubor("%s: obsah nesedi s manifestom" % meno)


def _hashe(subory):
    return {meno: hashlib.sha256(obsah).hexdigest() for meno, obsah in subory.items()}


def _nainstaluj(subory, verzia):
    """Writes the files into tmp/stage-*/edge_tts and then moves the whole
    folder into place as edge_tts-<verzia> (still INACTIVE - the manifest
    does not change). Returns the path to the version folder."""
    koren = kniznica_dir()
    tmp = _tmp_dir()
    os.makedirs(tmp, exist_ok=True)
    stage = tempfile.mkdtemp(prefix="stage-", dir=tmp)
    balik = os.path.join(stage, "edge_tts")
    os.mkdir(balik)
    for meno, obsah in subory.items():
        with open(os.path.join(balik, meno), "xb") as fh:
            fh.write(obsah)
    ciel = os.path.join(koren, "edge_tts-%s" % verzia)
    if os.path.lexists(ciel):
        # the same version from a previous attempt (marked as broken)
        stary = os.path.join(tmp, "old-%s" % uuid.uuid4().hex[:8])
        nahrad_subor(ciel, stary)
        shutil.rmtree(stary, ignore_errors=True)
    nahrad_subor(stage, ciel)
    return ciel


def _uprac_tmp():
    shutil.rmtree(_tmp_dir(), ignore_errors=True)


def _uprac_stare(ponechaj):
    """After activation: removes the other edge_tts-<verzia> folders and tmp/.
    Nothing else in the library folder is deleted."""
    koren = kniznica_dir()
    try:
        mena = os.listdir(koren)
    except OSError:
        return
    for meno in mena:
        cesta = os.path.join(koren, meno)
        if meno != ponechaj and _PRIECINOK_VERZIE.match(meno) and os.path.isdir(cesta):
            shutil.rmtree(cesta, ignore_errors=True)
    _uprac_tmp()


# --------------------------------------------------------------------------
# App start (audio_engine.load_edge)
# --------------------------------------------------------------------------

_NEZISTENA = object()


def nacitaj_pri_starte(pribalena=_NEZISTENA):
    """The downloaded library at app start -> (module, version), or None =
    use the bundled one. Never raises.

    The downloaded one wins only when it is valid, not marked as broken and
    NEWER than the bundled one - so the next Zanshin release with a newer
    edge-tts wins by itself. When it cannot be loaded, it is marked as
    broken (the next start no longer tries it) and the app goes on with the
    bundled one."""
    manifest = citaj_manifest()
    if manifest is None or manifest.get("broken"):
        return None
    verzia = manifest["version"]
    if pribalena is _NEZISTENA:
        pribalena = pribalena_verzia()
    if not je_novsia(verzia, pribalena):
        _log.info("prirodzeny hlas: pribalena edge-tts %s, stiahnuta %s nie je "
                  "novsia - ostava pribalena", pribalena, verzia)
        return None
    uz = _nacitane.get(verzia)
    if uz is not None:
        return uz[0], verzia
    meno = "edge_tts" if "edge_tts" not in sys.modules else _alias(verzia)
    hladac = None
    try:
        hashe = manifest["files"]
        priecinok = _priecinok_balika(manifest)
        _over_subory(priecinok, hashe)
        modul, hladac = nacitaj_balik(meno, priecinok, hashe)
        over_api(modul)
    except _CHYBY_KNIZNICE as exc:
        if hladac is not None:
            zahod_balik(sys.modules.get(meno), hladac)
            _zabudni_moduly(meno)
        dovod = _dovod_chyby(exc)
        if isinstance(exc, PermissionError):
            # another process holds the file for a moment (antivirus) - again
            # next time
            _log.warning("prirodzeny hlas: stiahnutu edge-tts %s sa teraz nepodarilo "
                         "precitat (%s) - pouzivam pribalenu %s", verzia, dovod,
                         pribalena or "?")
            return None
        oznac_pokazenu(dovod)
        _log.warning("prirodzeny hlas: stiahnuta edge-tts %s sa nenacitala (%s) - "
                     "pouzivam pribalenu %s, stiahnutu uz neskusam, kym ju "
                     "'Aktualizovat hlas' nenahradi", verzia, dovod, pribalena or "?")
        return None
    _nacitane[verzia] = (modul, hladac)
    _log.info("prirodzeny hlas: edge-tts %s zo stiahnutej kniznice (pribalena %s)",
              verzia, pribalena or "?")
    return modul, verzia


# --------------------------------------------------------------------------
# Update on a click
# --------------------------------------------------------------------------

def aktivna_verzia():
    """(version, downloaded) of the edge-tts in use right now. Cheap - no
    network and no disk. (None, False) when the natural voice is not
    available."""
    ae = sys.modules.get("audio_engine")
    if ae is None:
        return pribalena_verzia(), False
    if not getattr(ae, "EDGE_AVAILABLE", False):
        return None, False
    return getattr(ae, "EDGE_VERZIA", None), bool(getattr(ae, "EDGE_STIAHNUTY", False))


def _skontroluj_abort(abort):
    if abort is None:
        return
    try:
        zrus = abort()
    except Exception:
        zrus = True
    if zrus:
        raise _Zlyhanie(STAV_ZRUSENY, "zaplo sa sledovanie")


def _syntetizuj(modul, text, hlas, cesta, timeout):
    """One cue with the module `modul` into `cesta`. Tests replace it."""
    import asyncio

    async def _run():
        comm = modul.Communicate(text, hlas, rate="+0%")
        await asyncio.wait_for(comm.save(cesta), timeout)

    asyncio.run(_run())


def _chyba_importu(exc):
    """First ImportError in the chain (`__cause__`, `__context__`), or None."""
    videne = set()
    while exc is not None and id(exc) not in videne and len(videne) < 8:
        videne.add(id(exc))
        if isinstance(exc, ImportError):
            return exc
        exc = exc.__cause__ or exc.__context__
    return None


def skusobne_slovo(modul, hlas=None, timeout=TEST_TIMEOUT_S):
    """Says `TEST_TEXT` with the module `modul` into a temporary file in tmp/
    and deletes it. Success = a non-empty file. Error -> _Zlyhanie according
    to audio_engine.druh_chyby_edge (refused / offline / other). Goes to the
    network (Microsoft) - only from a thread and only when not watching."""
    tmp = _tmp_dir()
    os.makedirs(tmp, exist_ok=True)
    cesta = os.path.join(tmp, "test-%s.mp3" % uuid.uuid4().hex[:12])
    try:
        try:
            _syntetizuj(modul, TEST_TEXT, hlas or TEST_HLAS, cesta, timeout)
        except _CHYBY_KNIZNICE as exc:
            import audio_engine
            druh = audio_engine.druh_chyby_edge(exc)
            stav = {audio_engine.EDGE_CHYBA_ODMIETNUTE: STAV_STALE_ODMIETNUTY,
                    audio_engine.EDGE_CHYBA_OFFLINE: STAV_OFFLINE}.get(druh, STAV_CHYBA)
            import_chyba = _chyba_importu(exc) if stav == STAV_CHYBA else None
            if import_chyba is not None:
                # A module that edge-tts reaches for only during synthesis (an
                # import inside a function) is not in this build - PyInstaller
                # bundles only what it saw during the build. Only a newer
                # Zanshin helps, not "try again" (verified in the frozen .exe).
                stav = (STAV_OVERENIE_ZLYHALO if isinstance(import_chyba, PokazenySubor)
                        else STAV_NEKOMPATIBILNY)
                raise _Zlyhanie(stav, "skusobne slovo: " + _dovod_chyby(import_chyba)) from None
            raise _Zlyhanie(stav, "skusobne slovo: %s (%s)" % (druh, _meno_chyby(exc))) from None
        try:
            velkost = os.path.getsize(cesta)
        except OSError:
            velkost = 0
        if velkost <= 0:
            raise _Zlyhanie(STAV_CHYBA, "skusobne slovo: prazdny vystup")
    finally:
        try:
            os.remove(cesta)
        except OSError:
            pass


def _aktivuj(modul, verzia, cache):
    import audio_engine
    audio_engine.nastav_edge_tts(modul, verzia, stiahnuty=True, cache=cache,
                                 cakanie_s=ZAMOK_CAKANIE_S)


def aktualizuj(cache=None, abort=None, hlas=None, over_aktualnu=True):
    """Click on "Update voice". BLOCKS - call ONLY from a helper thread.

    Steps: release list from PyPI -> version choice -> download and
    verification -> dependency and code check -> write into a new folder ->
    loading under the alias and API smoke test -> test word -> manifest ->
    module swap in audio_engine (under the `cache._lock` lock, so that no cue
    is half-done with the old module) -> cleanup of old versions.

    `cache`  - the app's EdgeTTSCache (its lock is held during the swap),
    `abort`  - no arguments; True = stop (watching was switched on). Asked
               before every step that goes to the network, before writing
               and loading the new code and after the test word (before
               the swap),
    `hlas`   - voice of the test word (default `TEST_HLAS`),
    `over_aktualnu` - when there is nothing newer, verify the currently
               running version with the test word (STAV_AKTUALNY vs
               STAV_STALE_ODMIETNUTY).

    Returns a `Vysledok`; raises no exception. One line goes to app.log."""
    if not _beh.acquire(blocking=False):
        vysledok = Vysledok(STAV_ZANEPRAZDNENY, aktivna=aktivna_verzia()[0],
                            dovod="ina aktualizacia prave bezi")
    else:
        try:
            vysledok = _aktualizuj(cache, abort, hlas, over_aktualnu)
        except _CHYBY_KNIZNICE as exc:  # safeguard - the GUI always gets a result
            vysledok = Vysledok(STAV_CHYBA, aktivna=aktivna_verzia()[0],
                                dovod="necakana chyba %s" % _meno_chyby(exc))
        finally:
            _beh.release()
    _zaloguj(vysledok)
    return vysledok


def _aktualizuj(cache, abort, hlas, over_aktualnu):
    aktivna = aktivna_verzia()[0]
    vysledok = Vysledok(STAV_CHYBA, aktivna=aktivna)
    try:
        _skontroluj_abort(abort)
        _uprac_tmp()
        data = stiahni_zoznam_vydani()
        kandidat = vyber_kandidata(data, aktivna)
        vysledok.najnovsia = kandidat.get("najnovsia")
        if kandidat["stav"] == STAV_AKTUALNY:
            if over_aktualnu:
                import audio_engine
                if audio_engine.EDGE_AVAILABLE and audio_engine.edge_tts is not None:
                    _skontroluj_abort(abort)
                    skusobne_slovo(audio_engine.edge_tts, hlas)
            vysledok.stav = STAV_AKTUALNY
            return vysledok
        if kandidat["stav"] != _KANDIDAT:
            vysledok.stav = kandidat["stav"]
            vysledok.dovod = kandidat.get("dovod", "")
            return vysledok
        verzia = kandidat["verzia"]
        _skontroluj_abort(abort)
        wheel = stiahni_wheel(kandidat)
        subory, metadata_text = rozbal_wheel(wheel, verzia)
        neoverene = skontroluj_metadata(metadata_text, verzia)
        skontroluj_kod(subory)
        vysledok.nova = _vyskusaj_a_aktivuj(kandidat, subory, cache, abort, hlas)
        vysledok.stav = STAV_AKTUALIZOVANY
        if neoverene:
            vysledok.dovod = "verzia bez overenia: " + ", ".join(neoverene)
    except _Zlyhanie as z:
        vysledok.stav, vysledok.dovod = z.stav, z.dovod
    except OSError as exc:
        vysledok.stav, vysledok.dovod = STAV_CHYBA, "disk: %s" % _meno_chyby(exc)
    finally:
        if vysledok.stav != STAV_AKTUALIZOVANY:
            _uprac_tmp()
    return vysledok


def _vyskusaj_a_aktivuj(kandidat, subory, cache, abort, hlas):
    verzia = kandidat["verzia"]
    hashe = _hashe(subory)
    # If watching was switched on during the download, the new code is neither
    # written nor loaded (= not run) - nothing changes while watching.
    _skontroluj_abort(abort)
    priecinok = _nainstaluj(subory, verzia)
    modul = hladac = None
    hotovo = False
    try:
        balik = os.path.join(priecinok, "edge_tts")
        try:
            modul, hladac = nacitaj_balik(_alias(verzia), balik, hashe)
        except _CHYBY_KNIZNICE as exc:
            dovod = _dovod_chyby(exc)
            if not dovod.startswith("import "):
                dovod = "import: " + dovod
            raise _Zlyhanie(STAV_NEKOMPATIBILNY, dovod) from None
        over_api(modul)
        _skontroluj_abort(abort)
        skusobne_slovo(modul, hlas)
        # A word that was already in flight finishes; if watching was switched
        # on meanwhile, the new version is neither kept nor swapped in (nothing
        # while watching).
        _skontroluj_abort(abort)
        _zapis_manifest({
            "format": _FORMAT_MANIFESTU, "version": verzia,
            "folder": "edge_tts-%s" % verzia, "wheel": kandidat["subor"],
            "sha256": kandidat["sha256"], "files": hashe,
            "installed": _teraz(), "broken": False})
        hotovo = True
    finally:
        if not hotovo:
            if hladac is not None:
                zahod_balik(modul, hladac)
            shutil.rmtree(priecinok, ignore_errors=True)
    # With the manifest written, the new version holds for the next start too.
    _nacitane[verzia] = (modul, hladac)
    _aktivuj(modul, verzia, cache)
    _uprac_stare(ponechaj=os.path.basename(priecinok))
    return verzia


def _zaloguj(v):
    riadok = ("aktualizacia hlasu: %s (aktivna edge-tts %s, najnovsia %s, nova %s)%s"
              % (v.stav, v.aktivna or "-", v.najnovsia or "?", v.nova or "-",
                 (": " + v.dovod) if v.dovod else ""))
    if v.stav in (STAV_AKTUALNY, STAV_AKTUALIZOVANY, STAV_ZRUSENY, STAV_ZANEPRAZDNENY):
        _log.info(riadok)
    else:
        _log.warning(riadok)
