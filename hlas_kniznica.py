"""Stiahnutelna kniznica prirodzeneho hlasu (edge-tts) - "Aktualizovat hlas".

PRECO: Microsoft v novembri 2026 odmietol edge-tts 7.2.8 (HTTP 403). Oprava
v edge-tts 7.3.0/7.3.1 bola ZMENA KODU (novy algoritmus tokenu Sec-MS-GEC),
takze vydany Zanshin s pribalenou starou verziou sa neda opravit datami -
treba novsi kod edge-tts. Rozhodnutie autora (15. 11. 2026): hrac si ho moze
stiahnut sam jednym klikom, kym nevyjde novy Zanshin.

Pravidla (PRIVACY.md, SAFETY.md):
  * len na klik, nikdy samo a nikdy pocas sledovania (`abort` volajuceho
    sa pyta pred kazdym krokom, ktory ide na siet),
  * len kod kniznice edge-tts z PyPI - z toho isteho zdroja, z ktoreho ju
    berie build (build_all.ps1),
  * stiahnuty subor sa overi: HTTPS s certifikatmi z certifi, presny
    hostitel (aj po presmerovani), strop velkosti, sha256 z PyPI, obsah zipu
    (len edge_tts/*.py + METADATA v pamati). Pri instalacii sa NIC nespusta,
  * zavislosti z METADATA musia byt v tomto procese (v builde = pribalene)
    v pozadovanej verzii - inak "treba novsi Zanshin",
  * nova verzia sa vyskusa jednym pevnym slovom (`TEST_TEXT`, nikdy text
    hraca) a ostane, len ked funguje; inak ostava doterajsia a hrac dostane
    odkaz na oficialne vydania (`RELEASES_URL`).

Ulozisko `paths.voice_lib_dir()` (v builde %APPDATA%\\Zanshin\\voice_lib):
  manifest.json                - aktivna stiahnuta verzia a sha256 jej suborov
  edge_tts-<verzia>/edge_tts/  - kod kniznice (len .py a py.typed)
  tmp/                         - rozbalovanie a skusobne slovo, po pokuse prec

Nacitanie: `_Hladac` (MetaPathFinder na zaciatku sys.meta_path) servuje
balik z priecinka pod jednym menom - pri starte appky pod skutocnym
"edge_tts" (ma prednost pred importerom PyInstalleru aj pred site-packages),
za behu pod sukromnym aliasom, lebo "edge_tts" v pamati uz je pribaleny.
Kazdy subor sa pred spustenim overi voci sha256 z manifestu a bytecode
(__pycache__) sa necita ani nezapisuje. Ze sa balik sprava pod aliasom
rovnako ako pod skutocnym menom, strazi `skontroluj_kod` (ziadny absolutny
import "edge_tts" vo vnutri balika - 7.3.1 ma len relativne).

Vsetky funkcie, co idu na siet, blokuju - volaj ich LEN z pomocneho vlakna.
Ziadna z nich nesiaha na Tk.
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
# Konstanty
# --------------------------------------------------------------------------

PYPI_JSON_URL = "https://pypi.org/pypi/edge-tts/json"
# Oficialne vydania Zanshinu - kam poslat hraca, ked sa hlas opravit neda.
RELEASES_URL = "https://github.com/Dandurfin/Zanshin/releases/latest"
_PYPI_HOSTITELIA = frozenset({"pypi.org"})
_SUBORY_HOSTITELIA = frozenset({"files.pythonhosted.org"})
# Holy nazov appky - ziadna verzia ani nic o hracovi (PRIVACY.md).
USER_AGENT = "Zanshin"
HTTP_TIMEOUT_S = 15.0
MAX_PRESMEROVANI = 3
JSON_STROP_B = 4 * 1024 * 1024      # cely zoznam vydani edge-tts ma ~0,2 MB
WHEEL_STROP_B = 2 * 1024 * 1024     # wheel 7.3.1 ma ~39 kB (38 908 B)
ZIP_MAX_POLOZIEK = 400
ZIP_SUBOR_STROP_B = 1024 * 1024     # najvacsi subor 7.3.1 (communicate.py) ~24 kB
ZIP_SPOLU_STROP_B = 8 * 1024 * 1024
METADATA_STROP_B = 512 * 1024

# Skusobne slovo: pevny neutralny text, NIKDY text hlasky hraca.
TEST_TEXT = "Zanshin"
TEST_HLAS = "en-GB-SoniaNeural"
TEST_TIMEOUT_S = 20.0
# Kolko najviac caka vymena modulu na zamok cache (jedna hlaska, ktora prave
# leti). Potom sa vymeni aj tak - priradenie modulu je atomicke a hlaska,
# ktora leti, si drzi svoj stary modul (audio_engine.nastav_edge_tts).
ZAMOK_CAKANIE_S = 30.0

MANIFEST_MENO = "manifest.json"
TMP_MENO = "tmp"
_FORMAT_MANIFESTU = 1

# Stavy vysledku `aktualizuj` (strojovo citatelne, texty ma GUI v i18n).
STAV_AKTUALNY = "up_to_date"            # najnovsia uz bezi a skusobne slovo preslo
STAV_AKTUALIZOVANY = "updated"          # nova verzia aktivna od tejto chvile
STAV_STALE_ODMIETNUTY = "refused_still"  # Microsoft odmieta aj najnovsiu
STAV_OFFLINE = "offline"                # PyPI alebo Microsoft nedostupny
STAV_NEKOMPATIBILNY = "incompatible"    # zavislosti / API / Python - treba novsi Zanshin
STAV_OVERENIE_ZLYHALO = "verify_failed"  # hostitel, sha256, velkost, obsah zipu
STAV_ZRUSENY = "cancelled"              # medzitym sa zaplo sledovanie (`abort`)
STAV_ZANEPRAZDNENY = "busy"             # ina aktualizacia prave bezi
STAV_CHYBA = "error"                    # cokolvek ine (disk, necakana odpoved)

_KANDIDAT = "candidate"

# `\Z`, nie `$`: `$` pusti aj koncovy '\n' ("9.0.0\n" by platila za finalnu
# verziu a riadok app.log by sa rozdelil na dva).
_FINALNA_VERZIA = re.compile(r"^\d{1,9}(?:\.\d{1,9}){0,7}\Z")
_PRIECINOK_VERZIE = re.compile(r"^edge_tts-\d{1,9}(?:\.\d{1,9}){0,7}\Z")
_SHA256 = re.compile(r"^[0-9a-f]{64}\Z")
_MENO_MODULU = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
# Chyby z kodu stiahnutej kniznice (import, Communicate(...), skusobne
# slovo). Aj SystemExit - `sys.exit()` v kniznici by inak zhodil start appky
# (pri kazdom starte, manifest by sa neoznacil) alebo vlakno aktualizacie
# (GUI by cakalo navzdy). KeyboardInterrupt sa nechyta.
_CHYBY_KNIZNICE = (Exception, SystemExit)
_REZERVOVANE_WIN = frozenset(
    ["CON", "PRN", "AUX", "NUL"] + ["COM%d" % i for i in range(1, 10)]
    + ["LPT%d" % i for i in range(1, 10)])
# Pripony, ktore by sa pri instalacii alebo importe spustali samy (.pth),
# alebo su skompilovany kod - wheel edge-tts nic take nema.
_SPUSTITELNE_PRIPONY = (".pth", ".pyd", ".so", ".dll", ".dylib", ".exe",
                        ".pyc", ".pyo", ".bat", ".cmd", ".ps1", ".sh")

# Zavislosti edge-tts, ktore smu byt naimportovane len kvoli `__version__`
# (v builde chyba ich dist-info - PyInstaller bali metadata len pre
# edge_tts a certifi). Su to pribalene kniznice, nie stiahnuty kod.
_ZNAME_ZAVISLOSTI = frozenset({"aiohttp", "certifi", "tabulate", "typing_extensions"})

KNIZNICA_DIR = None     # testy presmeruju; None = paths.voice_lib_dir()

_beh = threading.Lock()          # jedna aktualizacia naraz
_nacitane = {}                   # verzia -> (modul, hladac) nacitane v tomto behu


def kniznica_dir():
    return KNIZNICA_DIR or voice_lib_dir()


def _tmp_dir():
    return os.path.join(kniznica_dir(), TMP_MENO)


# --------------------------------------------------------------------------
# Vysledok
# --------------------------------------------------------------------------

@dataclass
class Vysledok:
    """Vysledok jedneho pokusu `aktualizuj`.

    stav      - `STAV_*` (strojovo citatelny),
    aktivna   - verzia edge-tts, ktora bezala pred pokusom (None = ziadna),
    nova      - verzia aktivovana tymto pokusom (len pri STAV_AKTUALIZOVANY),
    najnovsia - najnovsia finalna verzia na PyPI, ak sa ju podarilo zistit,
    dovod     - kratky technicky dovod do app.log (bez ciest a textov hraca).
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
    """Pokus skoncil so stavom `stav`; `dovod` ide do app.log."""

    def __init__(self, stav, dovod):
        super().__init__(dovod)
        self.stav = stav
        self.dovod = dovod


def _meno_chyby(exc):
    """Meno triedy chyby (a jej priciny pri URLError) - nikdy text chyby,
    v nom byva cela cesta a v %APPDATA% je meno uctu (PRIVACY.md)."""
    meno = type(exc).__name__
    dovod = getattr(exc, "reason", None)
    if isinstance(exc, urllib.error.URLError) and isinstance(dovod, BaseException):
        meno += "(%s)" % type(dovod).__name__
    return meno


def _kratke(text, n=60):
    text = repr(text)
    return text if len(text) <= n else text[:n - 1] + "…"


class PokazenySubor(ImportError):
    """Subor stiahnutej kniznice nesedi s manifestom. Sprava nesie LEN meno
    suboru, nikdy cestu - ide do app.log aj do manifestu."""


def _dovod_chyby(exc):
    """Kratky dovod zlyhania nacitania bez ciest. Text ImportError od Pythonu
    ("cannot import name X from Y (C:\\...)") cestu nesie, preto sa z neho
    berie len meno modulu a trieda chyby."""
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
# Verzie a specifikatory (maly porovnavac, bez kniznice `packaging`)
# --------------------------------------------------------------------------
#
# `packaging` v builde nie je a stahovat ho nebudeme. Staci podmnozina
# PEP 440: release z cisel, a/b/rc, post, dev, lokalna cast sa ignoruje.
# Epocha ("1!2.0") a ina exotika = neznamy tvar -> poziadavka NESPLNENA.

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
    """'7.3.1rc1' -> (release, kluc na porovnanie), neznamy tvar -> None."""
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
        pre = (-1, 0)           # 1.0.dev1 je pred 1.0a1
    else:
        pre = (3, 0)            # finalna
    post = int(m.group("post1") or m.group("postn") or 0) if ma_post else -1
    dev = int(m.group("devn") or 0) if m.group("dev") else math.inf
    kluc = (rel + (0,) * (_DLZKA_RELEASE - len(rel)), pre, post, dev)
    return rel, kluc


def verzia_finalna(text):
    """'7.3.1' -> (7, 3, 1). Len cisla a bodky - a/b/rc/dev/post -> None."""
    if not isinstance(text, str) or not _FINALNA_VERZIA.match(text):
        return None
    return tuple(int(c) for c in text.split("."))


def je_novsia(a, b):
    """Je verzia `a` novsia nez `b`? Nezistena `b` (None) = ano, neznamy
    tvar `a` = nie."""
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
    """Splna `verzia` (text) `specifikator` ('>=3.8.0,<4.0.0')?

    Prazdny specifikator = bez obmedzenia. Operatory >=, >, <=, <, ==, !=,
    ~= a ==X.* / !=X.*, spojene ciarkou. Neznamy tvar (===, URL, epocha,
    nezmysel) -> False: radsej odmietnut nez pustit nieco, co nesedi."""
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
# Znacky prostredia v Requires-Dist (PEP 508, podmnozina)
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
    """Plati znacka prostredia ('python_version < "3.11"') v tomto procese?
    Neznamy tvar -> True: poziadavka sa radsej skontroluje."""
    try:
        return bool(_ZnackaParser(_tokeny_znacky(znacka), _prostredie()).cely())
    except (_NeznamaZnacka, IndexError, ValueError, TypeError):
        return True


# --------------------------------------------------------------------------
# Zavislosti z METADATA
# --------------------------------------------------------------------------

_POZIADAVKA = re.compile(
    r"^\s*(?P<meno>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*"
    r"(?:\[[^\]]*\])?\s*(?P<spec>.*?)\s*$")


def rozober_poziadavku(riadok):
    """'aiohttp<4.0.0,>=3.8.0' -> ('aiohttp', '<4.0.0,>=3.8.0', '').
    Vracia (meno, specifikator, znacka); znacka je text za ';'."""
    if not isinstance(riadok, str):
        raise ValueError("poziadavka nie je text")
    cast, _, znacka = riadok.partition(";")
    m = _POZIADAVKA.match(cast)
    if not m:
        raise ValueError("necitatelna poziadavka")
    spec = m.group("spec")
    if spec.startswith("(") and spec.endswith(")"):
        spec = spec[1:-1].strip()      # stary tvar "foo (>=1.0)"
    return m.group("meno"), spec, znacka.strip()


def _najdi_modul(dist):
    """Importovatelne meno balika `dist` v tomto procese, alebo None.
    Nic sa pritom nespusta (`find_spec` top-level mena len hlada)."""
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
    """Verzia nainstalovaneho (v builde pribaleneho) balika, alebo None.

    Najprv dist-info (`importlib.metadata`). V builde ho ma len edge_tts a
    certifi (collect_all), preto nahradne `__version__` - z modulu, ktory uz
    je v pamati, alebo zo zavislosti edge-tts (`_ZNAME_ZAVISLOSTI`)."""
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
    """Requires-Dist riadky -> (problemy, neoverene).

    problemy  - co chyba alebo je stare (treba novsi Zanshin); prazdne = OK,
    neoverene - baliky, ktore tu su, ale ich verzia sa zistit neda (v builde
                bez dist-info a bez `__version__`, napr. typing_extensions).
                Prepustia sa: rozhodne o nich import a skusobne slovo.

    Riadky so znackou `extra` (volitelne doplnky, napr. 'extra == "dev"')
    sa preskocia, ostatne znacky sa vyhodnotia (`plati_znacka`)."""
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
    """METADATA z wheelu: meno a verzia sedia, Python a zavislosti tu su.
    Vracia zoznam neoverenych zavislosti (pozri `skontroluj_zavislosti`)."""
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
# Siet (jedine miesto modulu, kde sa chodi von)
# --------------------------------------------------------------------------

def _over_url(url, hostitelia):
    """Len https, presny hostitel, bez mena/hesla v URL, port 443."""
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
    """Presmerovanie len na povoleneho hostitela - kazdy skok sa overi."""

    max_redirections = MAX_PRESMEROVANI

    def __init__(self, hostitelia):
        super().__init__()
        self.hostitelia = hostitelia

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _over_url(newurl, self.hostitelia)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _otvor(req, hostitelia):
    """Otvori poziadavku cez HTTPS s certifikatmi z certifi. Testy ho
    nahradzaju - na siet nesmu ist nikdy."""
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
    """GET `url` -> bajty. Overi adresu pred aj po presmerovani a strop
    velkosti. Chyby siete -> STAV_OFFLINE, HTTP chyba -> STAV_CHYBA."""
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
    """JSON projektu edge-tts z PyPI (dict). Blokuje - len z vlakna."""
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
# Vyber verzie z PyPI
# --------------------------------------------------------------------------

def _vydania_z_json(data):
    """{verzia: [subory]} - z "releases", alebo (ked PyPI "releases" raz
    vypusti) aspon najnovsia verzia z "info" + "urls"."""
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
    """Wheel py3-none-any danej verzie, ktory sa smie stiahnut, alebo
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
    """Z JSON-u PyPI vyberie najnovsiu FINALNU verziu (len cisla a bodky),
    nestiahnutu (yanked), s wheelom py3-none-any pre tento Python a novsiu
    nez `aktivna`.

    Vracia dict so "stav":
      "candidate"      + verzia, url, sha256, subor, velkost, najnovsia,
      STAV_AKTUALNY    - nic novsie (najnovsia = najnovsia finalna vobec),
      STAV_NEKOMPATIBILNY - novsie verzie su, ale ani jedna sa tu neda pouzit.
    """
    python_verzia = python_verzia or _python_verzia()
    vydania = _vydania_z_json(data)
    vsetky, novsie = [], []
    for verzia, subory in vydania.items():
        t = verzia_finalna(verzia)
        if t is None or not isinstance(subory, list):
            continue            # predbezna, dev, post, lokalna alebo pokazena
        platne = [f for f in subory if isinstance(f, dict) and not f.get("yanked")]
        if not platne:
            continue            # stiahnute (yanked) vydanie alebo bez suborov
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
    """Stiahne wheel kandidata a overi velkost a sha256 z PyPI. Blokuje."""
    data = _http_get(kandidat["url"], WHEEL_STROP_B, _SUBORY_HOSTITELIA)
    velkost = kandidat.get("velkost")
    if velkost is not None and len(data) != velkost:
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "velkost wheelu nesedi s PyPI")
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), kandidat["sha256"]):
        raise _Zlyhanie(STAV_OVERENIE_ZLYHALO, "sha256 wheelu nesedi s PyPI")
    return data


# --------------------------------------------------------------------------
# Obsah wheelu (v pamati, nic sa nespusta)
# --------------------------------------------------------------------------

def _zly_zip(dovod):
    return _Zlyhanie(STAV_OVERENIE_ZLYHALO, "zip: " + dovod)


def _over_meno_v_zipe(info):
    """Bezpecne meno polozky zipu (s '/'), inak _Zlyhanie verify_failed.

    `orig_filename` je meno, ako je v archive: zipfile vo Windows meni '\\'
    na '/' uz pri citani, takze spatnu lomku vidno len tam."""
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
    """Wheel (bajty) -> ({meno_suboru: obsah} pre edge_tts/, text METADATA).

    Rozbaluju sa LEN subory "edge_tts/<meno>.py" a "edge_tts/py.typed"
    (7.3.1 nema v edge_tts ziadny podpriecinok). METADATA sa cita len do
    pamate. Pomocny prehravac edge_playback/ a ostatne subory dist-info
    (RECORD, WHEEL, licencia) su vo wheeli tiez - neberu sa, len sa overia
    ich mena. Cokolvek ine vo wheeli = odmietnutie."""
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
                continue                # priecinok - jeho subory sa overia samy
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
                pass                    # RECORD, WHEEL, licencia - nerozbaluju sa
            elif (casti[0] == "edge_playback" and len(casti) == 2
                  and (casti[1] == "py.typed" or _je_modul_py(casti[1]))):
                pass                    # prehravac z wheelu - Zanshin ho nepouziva
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
    """Zdrojaky sa daju precitat (len ast.parse - nic sa nespusta) a balik
    neimportuje sam seba absolutne ("import edge_tts..."). Taky import by pod
    aliasom za behu natiahol PRIBALENU verziu a zmiesal dve verzie naraz."""
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
# Nacitanie overeneho balika (MetaPathFinder + loader so sha256)
# --------------------------------------------------------------------------

class _OverenyLoader(importlib.machinery.SourceFileLoader):
    """Nacita JEDEN .py subor a pred spustenim overi jeho sha256.

    Bytecode sa necita ani nezapisuje: v __pycache__ by mohlo lezat nieco,
    co sa nikdy neoverilo, a do priecinka kniznice sa po instalacii nepise."""

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
    """Servuje LEN `meno` a `meno.<modul>` z jedneho priecinka balika.

    Pri starte je `meno` "edge_tts" a hladac stoji na sys.meta_path[0], teda
    pred importerom PyInstalleru aj pred site-packages - inak by sa natiahla
    pribalena verzia. Ine mena necha dalsim hladacom (vracia None). Modul
    pod svojim menom, ktory v manifeste nie je (podpriecinok, podstrceny
    subor), odmietne rovno - nesmie ho najst ani obycajny PathFinder."""

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
    # Novy zoznam namiesto insert/remove: import v inom vlakne prave prechadza
    # stary zoznam a posun prvkov by mu jeden hladac preskocil.
    sys.meta_path = [hladac] + [f for f in sys.meta_path if f is not hladac]


def _odober_hladac(hladac):
    sys.meta_path = [f for f in sys.meta_path if f is not hladac]


def _zabudni_moduly(meno):
    for kluc in [k for k in list(sys.modules) if k == meno or k.startswith(meno + ".")]:
        sys.modules.pop(kluc, None)


def nacitaj_balik(meno, priecinok_balika, hashe):
    """Natiahne balik z `priecinok_balika` pod menom `meno` -> (modul, hladac).

    Hladac ostava na sys.meta_path, kym modul zije (edge-tts moze dotiahnut
    podmodul neskor). Pri chybe sa hladac aj ciastocne nacitane moduly
    odstrania a chyba sa vyhodi dalej."""
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
    """Opak `nacitaj_balik` - pre kandidata, ktory nepresiel."""
    _odober_hladac(hladac)
    if modul is not None:
        _zabudni_moduly(modul.__name__)


def _alias(verzia):
    return "_zanshin_edge_tts_%s_%s" % (verzia.replace(".", "_"), uuid.uuid4().hex[:8])


def over_api(modul):
    """Smoke test API bez siete: Communicate s korutinou save a konstruktor
    s (text, hlas, rate=...) - presne to, co vola EdgeTTSCache.ensure."""
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
    """`__version__` modulu edge-tts, inak verzia z dist-info, inak None."""
    verzia = getattr(modul, "__version__", None)
    if isinstance(verzia, str) and verzia.strip():
        return verzia.strip()
    return pribalena_verzia()


def pribalena_verzia():
    """Verzia pribaleneho (nainstalovaneho) edge-tts podla dist-info, alebo
    None. V builde funguje, lebo collect_all('edge_tts') bali aj dist-info.
    Stiahnuty balik dist-info nema, takze toto je vzdy pribalena verzia."""
    try:
        return metadata.version("edge-tts") or None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Manifest a priecinky na disku
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
    """Platny manifest stiahnutej kniznice, alebo None (nic nestiahnute,
    pokazeny subor). Nikdy nevyhodi."""
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
    """Stiahnuta kniznica sa nenacitala - pri dalsom starte sa uz neskusa
    (kym ju tlacidlo nenahradi). Chyba zapisu sa len zaloguje."""
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
    """Vsetky subory z manifestu su na disku a sedi ich sha256."""
    for meno, sha in hashe.items():
        with open(os.path.join(priecinok, meno), "rb") as fh:
            data = fh.read(ZIP_SUBOR_STROP_B + 1)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), sha):
            raise PokazenySubor("%s: obsah nesedi s manifestom" % meno)


def _hashe(subory):
    return {meno: hashlib.sha256(obsah).hexdigest() for meno, obsah in subory.items()}


def _nainstaluj(subory, verzia):
    """Zapise subory do tmp/stage-*/edge_tts a cely priecinok potom presunie
    na miesto edge_tts-<verzia> (este NEAKTIVNY - manifest sa nemeni).
    Vracia cestu k priecinku verzie."""
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
        # rovnaka verzia z predosleho pokusu (oznacena ako pokazena)
        stary = os.path.join(tmp, "old-%s" % uuid.uuid4().hex[:8])
        nahrad_subor(ciel, stary)
        shutil.rmtree(stary, ignore_errors=True)
    nahrad_subor(stage, ciel)
    return ciel


def _uprac_tmp():
    shutil.rmtree(_tmp_dir(), ignore_errors=True)


def _uprac_stare(ponechaj):
    """Po aktivacii: prec ostatne priecinky edge_tts-<verzia> a tmp/.
    Nic ine v priecinku kniznice sa nemaze."""
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
# Start appky (audio_engine.load_edge)
# --------------------------------------------------------------------------

_NEZISTENA = object()


def nacitaj_pri_starte(pribalena=_NEZISTENA):
    """Stiahnuta kniznica pri starte appky -> (modul, verzia), alebo None =
    pouzi pribalenu. Nikdy nevyhodi.

    Stiahnuta vyhrava, len ked je platna, nie je oznacena ako pokazena a je
    NOVSIA nez pribalena - dalsie vydanie Zanshinu s novsim edge-tts teda
    vyhra samo. Ked sa nacitat neda, oznaci sa ako pokazena (dalsi start ju
    uz neskusa) a appka ide s pribalenou."""
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
            # subor na chvilu drzi iny proces (antivirus) - nabuduce znova
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
# Aktualizacia na klik
# --------------------------------------------------------------------------

def aktivna_verzia():
    """(verzia, stiahnuta) prave pouzivaneho edge-tts. Lacne - bez siete aj
    bez disku. (None, False), ked prirodzeny hlas nie je dostupny."""
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
    """Jedna hlaska modulom `modul` do `cesta`. Testy ho nahradzaju."""
    import asyncio

    async def _run():
        comm = modul.Communicate(text, hlas, rate="+0%")
        await asyncio.wait_for(comm.save(cesta), timeout)

    asyncio.run(_run())


def _chyba_importu(exc):
    """Prva ImportError v retazi chyby (`__cause__`, `__context__`), alebo None."""
    videne = set()
    while exc is not None and id(exc) not in videne and len(videne) < 8:
        videne.add(id(exc))
        if isinstance(exc, ImportError):
            return exc
        exc = exc.__cause__ or exc.__context__
    return None


def skusobne_slovo(modul, hlas=None, timeout=TEST_TIMEOUT_S):
    """Povie `TEST_TEXT` modulom `modul` do docasneho suboru v tmp/ a zmaze
    ho. Uspech = neprazdny subor. Chyba -> _Zlyhanie podla
    audio_engine.druh_chyby_edge (odmietnute / offline / ine). Ide na siet
    (Microsoft) - len z vlakna a len mimo sledovania."""
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
                # Modul, po ktorom edge-tts siahne az pri synteze (import vo
                # funkcii), v tomto builde nie je - PyInstaller bali len to,
                # co pri builde videl. Pomoze len novsi Zanshin, nie "skus
                # znova" (overene v zamrazenom .exe).
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
    """Klik na "Aktualizovat hlas". BLOKUJE - volaj LEN z pomocneho vlakna.

    Kroky: zoznam vydani z PyPI -> vyber verzie -> stiahnutie a overenie ->
    kontrola zavislosti a kodu -> zapis do noveho priecinka -> nacitanie pod
    aliasom a smoke test API -> skusobne slovo -> manifest -> vymena modulu
    v audio_engine (pod zamkom `cache._lock`, aby ziadna hlaska nebola
    rozpracovana starym modulom) -> upratanie starych verzii.

    `cache`  - EdgeTTSCache appky (jej zamok sa drzi pocas vymeny),
    `abort`  - bez argumentov; True = prestan (zaplo sa sledovanie). Pyta sa
               pred kazdym krokom, ktory ide na siet, pred zapisom a
               nacitanim noveho kodu a po skusobnom slove (pred vymenou),
    `hlas`   - hlas skusobneho slova (predvolene `TEST_HLAS`),
    `over_aktualnu` - ked nic novsie nie je, skusobnym slovom over prave
               bezacu verziu (STAV_AKTUALNY vs STAV_STALE_ODMIETNUTY).

    Vracia `Vysledok`; vynimku nevyhodi. Do app.log ide jeden riadok."""
    if not _beh.acquire(blocking=False):
        vysledok = Vysledok(STAV_ZANEPRAZDNENY, aktivna=aktivna_verzia()[0],
                            dovod="ina aktualizacia prave bezi")
    else:
        try:
            vysledok = _aktualizuj(cache, abort, hlas, over_aktualnu)
        except _CHYBY_KNIZNICE as exc:  # poistka - GUI dostane vzdy vysledok
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
    # Ak sa sledovanie zaplo pocas stahovania, novy kod sa ani nezapise, ani
    # nenatiahne (= nespusti) - pocas sledovania sa nic nemeni.
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
        # Slovo, ktore uz letelo, dobehne; ak sa medzitym zaplo sledovanie,
        # nova verzia sa nenecha ani nevymeni (pocas sledovania nic).
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
    # Od zapisu manifestu je nova verzia platna aj pre dalsi start.
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
