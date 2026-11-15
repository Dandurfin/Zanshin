# -*- coding: utf-8 -*-
"""The "Update voice" button - the core (hlas_kniznica.py, 0.3h).

In November 2026 Microsoft rejected edge-tts 7.2.8 and the fix was a change
to the CODE, so a released Zanshin cannot be fixed with data. The player
downloads a newer edge-tts themselves - only on click, never while watching,
only from PyPI, verified, tried with one word and kept only when it works.

No test goes to the network: `_otvor` (HTTP) and `_syntetizuj` (Microsoft)
are replaced with an error in an autouse fixture. Tests that need the test
word only let it through the package dummy (`ATRAPA = True`), which writes a
local file.
"""
import asyncio
import hashlib
import importlib.util
import io
import json
import logging
import os
import shutil
import sys
import threading
import types
import urllib.error
import urllib.request
import warnings
import zipfile
from importlib import metadata

import pytest

import audio_engine
import hlas_kniznica as hk

SKUTOCNE_SYNTETIZUJ = hk._syntetizuj
SKUTOCNE_OTVOR = hk._otvor
AKTIVNA = "7.3.1"
NOVA = "9.0.0"
JSON_URL = hk.PYPI_JSON_URL


def _je_nase_meno(k):
    return (k == "edge_tts" or k.startswith("edge_tts.")
            or k.startswith("_zanshin_edge_tts_"))


@pytest.fixture(autouse=True)
def izolacia(monkeypatch, tmp_path):
    """No network, the library in tmp_path, and after the test the same import
    state (sys.modules, sys.meta_path) and audio_engine globals."""
    def _siet(*_a, **_k):
        raise AssertionError("test siel na siet")
    monkeypatch.setattr(hk, "_otvor", _siet)
    monkeypatch.setattr(hk, "_syntetizuj", _siet)
    monkeypatch.setattr(hk, "KNIZNICA_DIR", str(tmp_path / "voice_lib"))
    for meno in ("EDGE_AVAILABLE", "edge_tts", "asyncio", "EDGE_IMPORT_ERROR",
                 "EDGE_VERZIA", "EDGE_STIAHNUTY"):
        monkeypatch.setattr(audio_engine, meno, getattr(audio_engine, meno))
    povodne_hladace = list(sys.meta_path)
    moduly = {k: v for k, v in sys.modules.items() if _je_nase_meno(k)}
    nacitane = dict(hk._nacitane)
    yield
    sys.meta_path = [f for f in sys.meta_path
                     if not isinstance(f, hk._Hladac) or f in povodne_hladace]
    for k in [k for k in list(sys.modules) if _je_nase_meno(k)]:
        del sys.modules[k]
    sys.modules.update(moduly)
    hk._nacitane.clear()
    hk._nacitane.update(nacitane)


def _lokalna_synteza(monkeypatch, zaznam=None):
    """The test word may only go through the dummy - it writes a local file."""
    def _synt(modul, text, hlas, cesta, timeout):
        assert getattr(modul, "ATRAPA", False), "skusobne slovo by islo na Microsoft"
        if zaznam is not None:
            zaznam.append((modul, text, hlas))
        return SKUTOCNE_SYNTETIZUJ(modul, text, hlas, cesta, timeout)
    monkeypatch.setattr(hk, "_syntetizuj", _synt)


# --------------------------------------------------------------------------
# Dummy edge_tts package, the wheel and the PyPI response
# --------------------------------------------------------------------------

ULOZ_OK = ('        with open(audio_fname, "wb") as fh:\n'
           '            fh.write(b"ID3atrapa")\n')
ULOZ_ODMIETNUTE = '        raise WSServerHandshakeError(403)\n'
ULOZ_PRAZDNE = '        open(audio_fname, "wb").close()\n'


def _balik(verzia=NOVA, uloz=ULOZ_OK, navyse=None, init_navyse=""):
    subory = {
        "__init__.py": ('"""Atrapa edge_tts (test)."""\n'
                        "from . import exceptions\n"
                        "from .communicate import Communicate\n"
                        "from .version import __version__\n"
                        "ATRAPA = True\n" + init_navyse),
        "communicate.py": (
            "from .exceptions import NoAudioReceived\n\n\n"
            "class WSServerHandshakeError(Exception):\n"
            "    def __init__(self, status):\n"
            "        super().__init__('Invalid response status')\n"
            "        self.status = status\n\n\n"
            "class Communicate:\n"
            "    def __init__(self, text, voice='en-GB-SoniaNeural', *, rate='+0%'):\n"
            "        if not isinstance(text, str):\n"
            "            raise TypeError('text must be str')\n"
            "        self.text, self.voice, self.rate = text, voice, rate\n\n"
            "    async def save(self, audio_fname, metadata_fname=None):\n" + uloz),
        "exceptions.py": "class NoAudioReceived(Exception):\n    pass\n",
        "version.py": '__version__ = "%s"\n' % verzia,
        "py.typed": "",
    }
    subory.update(navyse or {})
    return {k: v.encode("utf-8") if isinstance(v, str) else v for k, v in subory.items()}


ZAVISLOSTI_731 = ["aiohttp<4.0.0,>=3.8.0", "certifi>=2023.11.17",
                  "tabulate<1.0.0,>=0.4.4", "typing-extensions<5.0.0,>=4.1.0",
                  'black; extra == "dev"', 'pylint; extra == "dev"']


def _metadata(verzia=NOVA, zavislosti=None, python=">=3.7", meno="edge-tts"):
    riadky = ["Metadata-Version: 2.4", "Name: %s" % meno, "Version: %s" % verzia]
    if python:
        riadky.append("Requires-Python: %s" % python)
    for z in (ZAVISLOSTI_731 if zavislosti is None else zavislosti):
        riadky.append("Requires-Dist: %s" % z)
    return "\n".join(riadky) + "\n\n# edge-tts\n\nRequires-Dist: toto je popis, nie hlavicka\n"


def _wheel(verzia=NOVA, balik=None, metadata_text=None, navyse=(),
           kompresia=zipfile.ZIP_DEFLATED):
    balik = _balik(verzia) if balik is None else balik
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # duplicate names in tests on purpose
        with zipfile.ZipFile(buf, "w", kompresia) as zf:
            for meno, obsah in balik.items():
                zf.writestr("edge_tts/" + meno, obsah)
            zf.writestr("edge_playback/__init__.py", "")
            zf.writestr("edge_playback/util.py", "")
            zf.writestr("edge_playback/py.typed", "")
            di = "edge_tts-%s.dist-info/" % verzia
            zf.writestr(di + "METADATA", _metadata(verzia) if metadata_text is None
                        else metadata_text)
            zf.writestr(di + "WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n")
            zf.writestr(di + "RECORD", "")
            zf.writestr(di + "entry_points.txt", "[console_scripts]\n")
            zf.writestr(di + "top_level.txt", "edge_playback\nedge_tts\n")
            zf.writestr(di + "licenses/LICENSE", "LGPL")
            for polozka, obsah in navyse:
                zf.writestr(polozka, obsah)
    return buf.getvalue()


def _wheel_url(verzia):
    return ("https://files.pythonhosted.org/packages/aa/bb/"
            "edge_tts-%s-py3-none-any.whl" % verzia)


def _subor_pypi(verzia, data=b"wheel", **zmeny):
    f = {"filename": "edge_tts-%s-py3-none-any.whl" % verzia,
         "packagetype": "bdist_wheel", "python_version": "py3",
         "requires_python": ">=3.7",
         "digests": {"sha256": hashlib.sha256(data).hexdigest(), "md5": "x"},
         "url": _wheel_url(verzia), "size": len(data),
         "yanked": False, "yanked_reason": None}
    f.update(zmeny)
    return f


def _sdist(verzia):
    return {"filename": "edge_tts-%s.tar.gz" % verzia, "packagetype": "sdist",
            "requires_python": ">=3.7", "digests": {"sha256": "0" * 64},
            "url": "https://files.pythonhosted.org/packages/cc/edge_tts-%s.tar.gz" % verzia,
            "size": 100, "yanked": False}


def _pypi(vydania):
    return {"info": {"name": "edge-tts", "version": "?"}, "releases": vydania,
            "urls": []}


class _Odpoved:
    def __init__(self, telo, url, hlavicky=None):
        self._buf = io.BytesIO(telo)
        self._url = url
        self.headers = hlavicky or {}

    def read(self, n=-1):
        return self._buf.read(n)

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _falosna_siet(monkeypatch, mapa, zaznam=None):
    """mapa: url -> bytes | exception | (bytes, final_url) | (bytes, url, headers)."""
    def _otvor(req, hostitelia):
        if zaznam is not None:
            zaznam.append((req.full_url, dict(req.header_items()), hostitelia))
        hodnota = mapa[req.full_url]
        if isinstance(hodnota, BaseException):
            raise hodnota
        if isinstance(hodnota, tuple):
            return _Odpoved(*hodnota)
        return _Odpoved(hodnota, req.full_url)
    monkeypatch.setattr(hk, "_otvor", _otvor)


def _aktivny_pribaleny(monkeypatch, verzia=AKTIVNA, modul=None):
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    monkeypatch.setattr(audio_engine, "EDGE_VERZIA", verzia)
    monkeypatch.setattr(audio_engine, "EDGE_STIAHNUTY", False)
    if modul is not None:
        monkeypatch.setattr(audio_engine, "edge_tts", modul)


def _priprav_aktualizaciu(monkeypatch, verzia=NOVA, wheel=None, zaznam=None, **subor):
    wheel = _wheel(verzia) if wheel is None else wheel
    data = _pypi({AKTIVNA: [_subor_pypi(AKTIVNA)],
                  verzia: [_subor_pypi(verzia, wheel, **subor), _sdist(verzia)]})
    _falosna_siet(monkeypatch, {JSON_URL: json.dumps(data).encode(),
                                _wheel_url(verzia): wheel}, zaznam)
    return wheel


class _AtrapaCommunicate:
    def __init__(self, text, voice="en-GB-SoniaNeural", *, rate="+0%"):
        self.text = text

    async def save(self, audio_fname, metadata_fname=None):
        with open(audio_fname, "wb") as fh:
            fh.write(b"ID3")


ATRAPA_MODUL = types.SimpleNamespace(ATRAPA=True, Communicate=_AtrapaCommunicate,
                                     __name__="atrapa_edge_tts")


def _nase_hladace():
    return [f for f in sys.meta_path if isinstance(f, hk._Hladac)]


# --------------------------------------------------------------------------
# Versions and specifiers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("verzia, spec, ocakavane", [
    ("3.14.7", ">=3.7", True),
    ("3.14.7", ">=3.8,<4", True),
    ("3.14.7", ">=3.8, <4", True),
    ("3.14.7", "<3.14", False),
    ("3.14.7", ">3.14.7", False),
    ("3.14.7", "<=3.14.7", True),
    ("3.14.7", "==3.14.7", True),
    ("3.14.7", "==3.14", False),
    ("3.14.0", "==3.14", True),
    ("3.14.7", "==3.14.*", True),
    ("3.14.7", "!=3.14.*", False),
    ("3.13.1", "!=3.0.*,!=3.1.*,>=3.6", True),
    ("3.14.7", "~=3.14", True),
    ("4.0", "~=3.14", False),
    ("3.14.7", "~=3.14.2", True),
    ("3.15.0", "~=3.14.2", False),
    ("3.14.7", "~=3", False),
    ("3.14.7", "", True),
    ("3.14.7", None, True),
    ("3.14.7", "===3.14.7", False),
    ("3.14.7", "abc", False),
    ("3.14.7", ">=", False),
    ("3.14.7", ">=1!2.0", False),
    ("3.14.7", ">=3.7 or <2", False),
    ("3.14.7", "<=3.*", False),
    ("3.8.0rc1", ">=3.8.0", False),
    ("3.8.0", ">=3.8.0rc1", True),
    ("4.16.0", "<5.0.0,>=4.1.0", True),
    ("2026.7.22", ">=2023.11.17", True),
    ("2026.07.22", ">=2023.11.17", True),
    ("1.0.post1", ">1.0", True),
    ("1.0.dev1", "<1.0", True),
    ("7.3.1", "!=7.3.1", False),
    ("7.3", "==7.3.0", True),
    ("3.14.3", "<4.0.0,>=3.8.0", True),
    ("3.7.4", "<4.0.0,>=3.8.0", False),
    ("nezmysel", ">=1", False),
    (None, ">=1", False),
])
def test_splna_poziadavku(verzia, spec, ocakavane):
    assert hk.splna_poziadavku(verzia, spec) is ocakavane


@pytest.mark.parametrize("text, ocakavane", [
    ("7.3.1", (7, 3, 1)), ("10", (10,)), ("2026.7.22", (2026, 7, 22)),
    ("7.3.1rc1", None), ("7.3.1.post1", None), ("7.3.1.dev0", None),
    ("7.3.1a1", None), ("7.3.1b2", None), ("7.3.1+local", None),
    ("v7.3.1", None), (" 7.3.1", None), ("7..1", None), ("", None), (None, None),
    ("1.2.3.4.5.6.7.8.9", None), ("7.3.1\n", None),
])
def test_verzia_finalna_len_cisla_a_bodky(text, ocakavane):
    assert hk.verzia_finalna(text) == ocakavane


def test_koniec_riadku_nie_je_cast_verzie_mena_ani_sha():
    """`$` in a regex also lets a trailing '\\n' through. The PyPI version,
    the file name from the manifest, sha256 and the version folder must
    not have it - otherwise version "9.0.0\\n" would count as final and
    the app.log line would split in two."""
    assert not hk._je_modul_py("communicate\n.py")
    assert not hk._SHA256.match("a" * 64 + "\n")
    assert not hk._PRIECINOK_VERZIE.match("edge_tts-9.0.0\n")
    assert not hk._MENO_MODULU.match("communicate\n")
    # a manifest with such a file name is invalid
    os.makedirs(hk.kniznica_dir())
    with open(os.path.join(hk.kniznica_dir(), "manifest.json"), "w") as fh:
        json.dump({"format": 1, "version": NOVA, "folder": "edge_tts-9.0.0",
                   "files": {"__init__.py": "0" * 64, "x\n.py": "0" * 64}}, fh)
    assert hk.citaj_manifest() is None


def test_verzia_s_koncom_riadku_z_pypi_sa_ignoruje(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="zanshin.hlas_kniznica")
    _aktivny_pribaleny(monkeypatch)
    data = _pypi({AKTIVNA: [_subor_pypi(AKTIVNA)], NOVA + "\n": [_sdist(NOVA)]})
    _falosna_siet(monkeypatch, {JSON_URL: json.dumps(data).encode()})
    v = hk.aktualizuj(over_aktualnu=False)
    assert (v.stav, v.najnovsia, v.dovod) == (hk.STAV_AKTUALNY, AKTIVNA, "")
    riadky = [r.getMessage() for r in caplog.records if r.name == "zanshin.hlas_kniznica"]
    assert len(riadky) == 1 and "\n" not in riadky[0], riadky


@pytest.mark.parametrize("a, b, ocakavane", [
    ("7.3.1", "7.3.0", True), ("7.3.1", "7.3.1", False), ("7.3", "7.3.0", False),
    ("7.10.0", "7.9.9", True), ("8.0.0", None, True), ("7.3.1", "7.4.0", False),
    ("7.3.1", "7.3.1rc1", True), ("nezmysel", "1.0", False), ("1.0", "nezmysel", True),
])
def test_je_novsia(a, b, ocakavane):
    assert hk.je_novsia(a, b) is ocakavane


# --------------------------------------------------------------------------
# Markers and dependencies from METADATA
# --------------------------------------------------------------------------

@pytest.mark.parametrize("znacka, ocakavane", [
    ('python_version < "3.0"', False),
    ('python_version >= "3.8"', True),
    ('"3.8" <= python_version', True),
    ('sys_platform == "neexistujuci-os"', False),
    ('sys_platform != "neexistujuci-os" and python_version >= "3"', True),
    ('python_version < "3" or os_name == "%s"' % os.name, True),
    ('(python_version < "3" or os_name == "nic") and os_name != "nic"', False),
    ('"win" in sys_platform or "linux" in sys_platform or "darwin" in sys_platform', True),
    ('platform_python_implementation not in "Jython"', True),
    ('neznama_premenna == "x"', True),           # unknown = the requirement is checked
    ('python_version <', True),
    ('python_version === "3.14"', True),
])
def test_znacky_prostredia(znacka, ocakavane):
    assert hk.plati_znacka(znacka) is ocakavane


def test_skutocne_zavislosti_731_su_v_tomto_procese():
    problemy, neoverene = hk.skontroluj_zavislosti(metadata.distribution("edge-tts").requires)
    assert problemy == [] and neoverene == []


def test_zavislosti_extra_a_neplatne_znacky_sa_preskocia():
    riadky = ['zanshin-neexistujuci-balik; extra == "dev"',
              'zanshin-neexistujuci-balik>=1; python_version < "3.0"',
              'zanshin-neexistujuci-balik; sys_platform == "neexistujuci-os"']
    assert hk.skontroluj_zavislosti(riadky) == ([], [])


def test_zavislost_chyba_alebo_je_stara():
    problemy, _ = hk.skontroluj_zavislosti([
        "zanshin-neexistujuci-balik>=1", "aiohttp>=999.0",
        "certifi (>=99999)", "foo @ https://example.invalid/foo.whl",
        "zanshin-neexistujuci-balik2; neznama_premenna == 'x'",
        "aiohttp >>3", "???"])
    text = " | ".join(problemy)
    assert "zanshin-neexistujuci-balik chyba" in text
    assert "aiohttp" in text and "nesplna >=999.0" in text
    assert "certifi" in text and "nesplna >=99999" in text
    assert "nesplna >>3" in text
    assert "foo (URL)" in text
    assert "zanshin-neexistujuci-balik2 chyba" in text   # unknown marker = applies
    assert len(problemy) == 7, problemy


def test_rozober_poziadavku_tvary():
    assert hk.rozober_poziadavku("aiohttp<4.0.0,>=3.8.0") == ("aiohttp", "<4.0.0,>=3.8.0", "")
    assert hk.rozober_poziadavku("certifi (>=2023.11.17)") == ("certifi", ">=2023.11.17", "")
    assert hk.rozober_poziadavku('black; extra == "dev"') == ("black", "", 'extra == "dev"')
    assert hk.rozober_poziadavku("aiohttp[speedups]>=3.8") == ("aiohttp", ">=3.8", "")


def test_neznama_verzia_zavislosti_sa_prepusti_a_povie(monkeypatch):
    """In the build, typing_extensions has no dist-info or __version__ - that
    must not block the fix (import and the test word decide), but it is
    reported."""
    import typing_extensions
    assert not hasattr(typing_extensions, "__version__")

    def _bez_dist_info(meno):
        raise metadata.PackageNotFoundError(meno)
    monkeypatch.setattr(hk, "metadata", types.SimpleNamespace(
        version=_bez_dist_info, packages_distributions=lambda: {},
        PackageNotFoundError=metadata.PackageNotFoundError))
    problemy, neoverene = hk.skontroluj_zavislosti(ZAVISLOSTI_731)
    # aiohttp, certifi, tabulate have __version__ - checked without dist-info
    assert problemy == []
    assert neoverene == ["typing-extensions"]
    problemy, _ = hk.skontroluj_zavislosti(["aiohttp>=999"])
    assert problemy and "aiohttp" in problemy[0]


def test_skontroluj_metadata():
    assert hk.skontroluj_metadata(_metadata(NOVA), NOVA) == []
    for zle in (_metadata("9.0.1"), _metadata(NOVA, meno="edge-ttz")):
        with pytest.raises(hk._Zlyhanie) as z:
            hk.skontroluj_metadata(zle, NOVA)
        assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skontroluj_metadata(_metadata(NOVA, python=">=3.99"), NOVA)
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY and "Requires-Python" in z.value.dovod
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skontroluj_metadata(_metadata(NOVA, zavislosti=["zanshin-neexistujuci>=1"]), NOVA)
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY and "zavislosti" in z.value.dovod
    # "Requires-Dist" in the description (body after blank line) is no header
    assert hk.skontroluj_metadata(_metadata(NOVA, zavislosti=[]), NOVA) == []


# --------------------------------------------------------------------------
# Choosing the version from PyPI
# --------------------------------------------------------------------------

def test_vyber_najnovsiu_finalnu_nie_predbeznu_ani_stiahnutu():
    data = _pypi({
        "7.3.1": [_subor_pypi("7.3.1")],
        "7.4.0": [_subor_pypi("7.4.0"), _sdist("7.4.0")],
        "7.5.0rc1": [_subor_pypi("7.5.0rc1")],
        "7.4.1.dev0": [_subor_pypi("7.4.1.dev0")],
        "7.4.1.post1": [_subor_pypi("7.4.1.post1")],
        "7.6.0": [_subor_pypi("7.6.0", yanked=True, yanked_reason="zle")],
        "7.7.0": [],
    })
    k = hk.vyber_kandidata(data, AKTIVNA, "3.14.7")
    assert k["stav"] == "candidate" and k["verzia"] == "7.4.0"
    assert k["najnovsia"] == "7.4.0"
    assert k["url"] == _wheel_url("7.4.0")
    assert k["subor"] == "edge_tts-7.4.0-py3-none-any.whl"
    assert k["sha256"] == hashlib.sha256(b"wheel").hexdigest()


def test_vyber_starsiu_novsiu_ked_najnovsia_chce_iny_python():
    data = _pypi({"7.5.0": [_subor_pypi("7.5.0", requires_python=">=3.99")],
                  "7.4.0": [_subor_pypi("7.4.0", requires_python=">=3.8,<4")]})
    k = hk.vyber_kandidata(data, AKTIVNA, "3.14.7")
    assert (k["stav"], k["verzia"], k["najnovsia"]) == ("candidate", "7.4.0", "7.5.0")


@pytest.mark.parametrize("zmena, dovod", [
    ({"requires_python": ">=3.99"}, "Python"),
    ({"requires_python": "≥3.7"}, "Python"),          # unknown form = no
    ({"packagetype": "sdist"}, "bez wheelu"),
    ({"filename": "edge_tts-7.4.0-py3-none-win_amd64.whl"}, "bez wheelu"),
    ({"filename": "edge_ttz-7.4.0-py3-none-any.whl"}, "bez wheelu"),
    ({"url": "http://files.pythonhosted.org/x.whl"}, "mimo"),
    ({"url": "https://evil.example/edge_tts-7.4.0-py3-none-any.whl"}, "mimo"),
    ({"url": "https://files.pythonhosted.org.evil.example/x.whl"}, "mimo"),
    ({"digests": {"md5": "x"}}, "sha256"),
    ({"digests": {"sha256": "nie-hex"}}, "sha256"),
    ({"size": hk.WHEEL_STROP_B + 1}, "velkost"),
    ({"size": True}, "velkost"),
])
def test_novsia_bez_pouzitelneho_wheelu_je_nekompatibilna(zmena, dovod):
    data = _pypi({AKTIVNA: [_subor_pypi(AKTIVNA)],
                  "7.4.0": [_subor_pypi("7.4.0", **zmena)]})
    k = hk.vyber_kandidata(data, AKTIVNA, "3.14.7")
    assert k["stav"] == hk.STAV_NEKOMPATIBILNY, k
    assert k["najnovsia"] == "7.4.0" and dovod in k["dovod"]


@pytest.mark.parametrize("vydania", [
    {AKTIVNA: [_subor_pypi(AKTIVNA)], "7.2.8": [_subor_pypi("7.2.8")]},
    {AKTIVNA: [_subor_pypi(AKTIVNA)], "7.4.0rc1": [_subor_pypi("7.4.0rc1")]},
    {AKTIVNA: [_subor_pypi(AKTIVNA)], "7.4.0": [_subor_pypi("7.4.0", yanked=True)]},
])
def test_nic_novsie_je_aktualne(vydania):
    k = hk.vyber_kandidata(_pypi(vydania), AKTIVNA, "3.14.7")
    assert k == {"stav": hk.STAV_AKTUALNY, "najnovsia": AKTIVNA}


def test_bez_aktivnej_verzie_ide_najnovsia_a_bez_releases_info_urls():
    data = {"info": {"version": "7.4.0"}, "urls": [_subor_pypi("7.4.0")]}
    k = hk.vyber_kandidata(data, None, "3.14.7")
    assert k["stav"] == "candidate" and k["verzia"] == "7.4.0"
    with pytest.raises(hk._Zlyhanie) as z:
        hk.vyber_kandidata({"nieco": 1}, AKTIVNA, "3.14.7")
    assert z.value.stav == hk.STAV_CHYBA


# --------------------------------------------------------------------------
# Network: https, host, redirect, caps
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://files.pythonhosted.org/x.whl",
    "https://evil.example/x.whl",
    "https://files.pythonhosted.org.evil.example/x.whl",
    "https://user:heslo@files.pythonhosted.org/x.whl",
    "https://files.pythonhosted.org:8443/x.whl",
    "ftp://files.pythonhosted.org/x.whl",
    "file:///C:/x.whl",
    "https://[::1/x",
    None,
])
def test_adresa_mimo_povoleneho_hostitela(url):
    with pytest.raises(hk._Zlyhanie) as z:
        hk._over_url(url, hk._SUBORY_HOSTITELIA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO


def test_povolena_adresa():
    hk._over_url("https://files.pythonhosted.org/packages/x.whl", hk._SUBORY_HOSTITELIA)
    hk._over_url("https://FILES.pythonhosted.org:443/x.whl", hk._SUBORY_HOSTITELIA)
    hk._over_url(JSON_URL, hk._PYPI_HOSTITELIA)
    with pytest.raises(hk._Zlyhanie):
        hk._over_url(JSON_URL, hk._SUBORY_HOSTITELIA)


def test_presmerovanie_len_na_povoleneho_hostitela():
    h = hk._OverenePresmerovanie(hk._SUBORY_HOSTITELIA)
    req = urllib.request.Request(_wheel_url(NOVA))
    with pytest.raises(hk._Zlyhanie):
        h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/x.whl")
    with pytest.raises(hk._Zlyhanie):
        h.redirect_request(req, None, 301, "Moved", {}, "http://files.pythonhosted.org/x")
    novy = h.redirect_request(req, None, 302, "Found", {},
                              "https://files.pythonhosted.org/packages/y.whl")
    assert novy.full_url == "https://files.pythonhosted.org/packages/y.whl"
    assert h.max_redirections == hk.MAX_PRESMEROVANI


def test_konecna_adresa_po_presmerovani_sa_overi(monkeypatch):
    _falosna_siet(monkeypatch, {_wheel_url(NOVA): (b"data", "https://evil.example/x")})
    with pytest.raises(hk._Zlyhanie) as z:
        hk._http_get(_wheel_url(NOVA), 100, hk._SUBORY_HOSTITELIA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO


def test_strop_velkosti_odpovede(monkeypatch):
    url = _wheel_url(NOVA)
    _falosna_siet(monkeypatch, {url: (b"x" * 10, url, {"Content-Length": "999999"})})
    with pytest.raises(hk._Zlyhanie) as z:
        hk._http_get(url, 100, hk._SUBORY_HOSTITELIA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    # without Content-Length it is read in chunks and stops right after the cap
    _falosna_siet(monkeypatch, {url: b"x" * 200_000})
    with pytest.raises(hk._Zlyhanie) as z:
        hk._http_get(url, 100_000, hk._SUBORY_HOSTITELIA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    _falosna_siet(monkeypatch, {url: b"x" * 100})
    assert hk._http_get(url, 100, hk._SUBORY_HOSTITELIA) == b"x" * 100


@pytest.mark.parametrize("chyba, stav", [
    (urllib.error.URLError(OSError("dns")), hk.STAV_OFFLINE),
    (TimeoutError("cas"), hk.STAV_OFFLINE),
    (ConnectionResetError("reset"), hk.STAV_OFFLINE),
    (urllib.error.HTTPError(JSON_URL, 503, "Service Unavailable", {}, None), hk.STAV_CHYBA),
])
def test_chyby_siete(monkeypatch, chyba, stav):
    _falosna_siet(monkeypatch, {JSON_URL: chyba})
    with pytest.raises(hk._Zlyhanie) as z:
        hk.stiahni_zoznam_vydani()
    assert z.value.stav == stav


def test_poziadavka_nesie_len_holy_nazov_appky(monkeypatch):
    zaznam = []
    _falosna_siet(monkeypatch, {JSON_URL: b"{}"}, zaznam)
    assert hk.stiahni_zoznam_vydani() == {}
    ((url, hlavicky, hostitelia),) = zaznam
    assert url == "https://pypi.org/pypi/edge-tts/json"
    assert hostitelia == frozenset({"pypi.org"})
    assert hlavicky == {"User-agent": "Zanshin", "Accept": "application/json"}


def test_otvor_ide_cez_https_s_certifi_a_kratkym_timeoutom(monkeypatch):
    """The real `_otvor` without network: the opener is faked and records what
    the app built it with."""
    import ssl

    import certifi
    zachytene = {}

    class _Opener:
        def open(self, req, timeout=None):
            zachytene["req"], zachytene["timeout"] = req, timeout
            return _Odpoved(b"{}", req.full_url)

    def _build_opener(*handlery):
        zachytene["handlery"] = handlery
        return _Opener()

    nacitane_certifikaty = []
    skutocny_kontext = ssl.create_default_context

    def _kontext(*a, **k):
        nacitane_certifikaty.append(k.get("cafile"))
        return skutocny_kontext(*a, **k)

    monkeypatch.setattr(hk, "_otvor", SKUTOCNE_OTVOR)
    monkeypatch.setattr(urllib.request, "build_opener", _build_opener)
    monkeypatch.setattr(ssl, "create_default_context", _kontext)
    assert hk.stiahni_zoznam_vydani() == {}
    assert nacitane_certifikaty == [certifi.where()]
    https = [h for h in zachytene["handlery"] if isinstance(h, urllib.request.HTTPSHandler)]
    assert len(https) == 1
    kontext = https[0]._context
    assert kontext.verify_mode == ssl.CERT_REQUIRED and kontext.check_hostname
    presmer = [h for h in zachytene["handlery"] if isinstance(h, hk._OverenePresmerovanie)]
    assert len(presmer) == 1 and presmer[0].hostitelia == frozenset({"pypi.org"})
    assert zachytene["timeout"] == hk.HTTP_TIMEOUT_S <= 20


# --------------------------------------------------------------------------
# Downloading and verifying the wheel
# --------------------------------------------------------------------------

def test_wheel_sha256_a_velkost_musia_sediet(monkeypatch):
    wheel = _wheel()
    kandidat = {"url": _wheel_url(NOVA), "sha256": hashlib.sha256(wheel).hexdigest(),
                "velkost": len(wheel)}
    _falosna_siet(monkeypatch, {_wheel_url(NOVA): wheel})
    assert hk.stiahni_wheel(kandidat) == wheel
    for zle in (dict(kandidat, sha256="0" * 64), dict(kandidat, velkost=len(wheel) + 1)):
        with pytest.raises(hk._Zlyhanie) as z:
            hk.stiahni_wheel(zle)
        assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO


def test_wheel_sa_rozbali_len_edge_tts_a_metadata_do_pamate():
    subory, meta = hk.rozbal_wheel(_wheel(), NOVA)
    assert sorted(subory) == ["__init__.py", "communicate.py", "exceptions.py",
                              "py.typed", "version.py"]
    assert subory["version.py"] == b'__version__ = "9.0.0"\n'
    assert "Name: edge-tts" in meta and "Version: 9.0.0" in meta


def _zip(polozky, kompresia=zipfile.ZIP_DEFLATED):
    """Wheel with exactly these items: [(name|ZipInfo, content)] + METADATA."""
    return _wheel(navyse=polozky, kompresia=kompresia)


def _info(meno, upravy=None, povodne_meno=None):
    zi = zipfile.ZipInfo(meno)
    zi.compress_type = zipfile.ZIP_DEFLATED
    if povodne_meno is not None:
        zi.filename = povodne_meno       # bypasses the ZipInfo normalisation
    for k, v in (upravy or {}).items():
        setattr(zi, k, v)
    return zi


@pytest.mark.parametrize("polozka, stav", [
    ("edge_tts/../evil.py", hk.STAV_OVERENIE_ZLYHALO),
    ("../evil.py", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/./x.py", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts//x.py", hk.STAV_OVERENIE_ZLYHALO),
    ("/edge_tts/abs.py", hk.STAV_OVERENIE_ZLYHALO),
    ("C:/evil.py", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/x.py:stream", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/x.py.", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/x .py ", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/a\x01.py", hk.STAV_OVERENIE_ZLYHALO),
    ("evil.pth", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/rychle.pyd", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/rychle.cp314-win_amd64.so", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/__pycache__/x.cpython-314.pyc", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts-9.0.0.data/scripts/edge-tts", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts-1.0.0.dist-info/METADATA", hk.STAV_OVERENIE_ZLYHALO),
    ("edge_tts/sub/x.py", hk.STAV_NEKOMPATIBILNY),
    ("edge_tts/data.json", hk.STAV_NEKOMPATIBILNY),
    ("edge_tts/con.py", hk.STAV_NEKOMPATIBILNY),
    ("edge_tts/1zle.py", hk.STAV_NEKOMPATIBILNY),
    ("ina_kniznica/x.py", hk.STAV_NEKOMPATIBILNY),
    ("sitecustomize.py", hk.STAV_NEKOMPATIBILNY),
    ("edge_playback/sub/x.py", hk.STAV_NEKOMPATIBILNY),
])
def test_zip_necakane_alebo_nebezpecne_polozky(polozka, stav):
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_zip([(polozka, b"x = 1\n")]), NOVA)
    assert z.value.stav == stav, z.value.dovod


def test_zip_spatna_lomka_v_mene():
    """zipfile on Windows changes '\\' to '/' already on reading - the original
    name in the archive decides."""
    wheel = _zip([(_info("edge_tts/x.py", povodne_meno="edge_tts\\x.py"), b"x = 1\n")])
    with zipfile.ZipFile(io.BytesIO(wheel)) as zf:
        assert any("\\" in i.orig_filename for i in zf.infolist())
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(wheel, NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO and "lomka" in z.value.dovod
    wheel = _zip([(_info("edge_tts/y.py", povodne_meno="edge_tts\\..\\..\\y.py"), b"")])
    with pytest.raises(hk._Zlyhanie):
        hk.rozbal_wheel(wheel, NOVA)


@pytest.mark.parametrize("druha", ["edge_tts/util.py", "edge_tts/Util.py", "EDGE_TTS/util.py"])
def test_zip_duplicitne_polozky(druha):
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_zip([("edge_tts/util.py", b"a = 1\n"), (druha, b"a = 2\n")]), NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO and "duplicit" in z.value.dovod


def test_zip_symbolicky_odkaz_a_specialne_subory():
    for rezim in (0o120777, 0o020644, 0o060644, 0o010644):
        zi = _info("edge_tts/odkaz.py", {"create_system": 3, "external_attr": rezim << 16})
        with pytest.raises(hk._Zlyhanie) as z:
            hk.rozbal_wheel(_zip([(zi, b"../../etc/passwd")]), NOVA)
        assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    # an ordinary unix file (0o100644) passes
    zi = _info("edge_tts/obycajny.py", {"create_system": 3, "external_attr": 0o100644 << 16})
    subory, _ = hk.rozbal_wheel(_zip([(zi, b"a = 1\n")]), NOVA)
    assert subory["obycajny.py"] == b"a = 1\n"


def _nastav_priznak(wheel, meno, priznak):
    """Writes a bit into an entry's flags in the zip central directory
    (zipfile clears the flags on write, so it would not make an encrypted
    entry otherwise)."""
    data = bytearray(wheel)
    meno = meno.encode()
    poz = data.find(b"PK\x01\x02")
    while poz != -1:
        dlzka = int.from_bytes(data[poz + 28:poz + 30], "little")
        if bytes(data[poz + 46:poz + 46 + dlzka]) == meno:
            priznaky = int.from_bytes(data[poz + 8:poz + 10], "little") | priznak
            data[poz + 8:poz + 10] = priznaky.to_bytes(2, "little")
            return bytes(data)
        poz = data.find(b"PK\x01\x02", poz + 4)
    raise AssertionError(meno)


def test_zip_sifrovana_polozka():
    wheel = _nastav_priznak(_zip([("edge_tts/tajne.py", b"x = 1\n")]), "edge_tts/tajne.py", 0x1)
    with zipfile.ZipFile(io.BytesIO(wheel)) as zf:
        assert zf.getinfo("edge_tts/tajne.py").flag_bits & 0x1
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(wheel, NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO and "sifrovana" in z.value.dovod


def test_zip_stropy_velkosti_a_poctu(monkeypatch):
    velky = b"#" * (hk.ZIP_SUBOR_STROP_B + 512 * 1024)
    wheel = _zip([("edge_tts/velky.py", velky)])
    assert len(wheel) < 100_000              # packed it is tiny - the cap is on unpacked size
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(wheel, NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO and "vacsia" in z.value.dovod
    monkeypatch.setattr(hk, "ZIP_SPOLU_STROP_B", 300)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_wheel(), NOVA)
    assert "obsah je vacsi" in z.value.dovod
    monkeypatch.setattr(hk, "ZIP_SPOLU_STROP_B", 8 * 1024 * 1024)
    monkeypatch.setattr(hk, "ZIP_MAX_POLOZIEK", 5)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_wheel(), NOVA)
    assert "vela" in z.value.dovod


def test_zip_poskodeny_obsah_chyba_metadata_a_init():
    wheel = _wheel(kompresia=zipfile.ZIP_STORED)
    assert wheel.count(b"ATRAPA = True") == 1
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(wheel.replace(b"ATRAPA = True", b"ATRAPA = Truf"), NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(b"toto nie je zip", NOVA)
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    # METADATA of a different version than from PyPI
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_wheel(), "9.0.1")
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO
    bez_init = {k: v for k, v in _balik().items() if k != "__init__.py"}
    with pytest.raises(hk._Zlyhanie) as z:
        hk.rozbal_wheel(_wheel(balik=bez_init), NOVA)
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY


def test_zip_priecinky_ako_polozky_prejdu():
    subory, _ = hk.rozbal_wheel(_zip([("edge_tts/", b""), ("edge_playback/", b"")]), NOVA)
    assert "__init__.py" in subory


# --------------------------------------------------------------------------
# Code check (ast, nothing is run)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("riadok", [
    "import edge_tts\n", "import edge_tts.drm as d\n", "from edge_tts import drm\n",
    "from edge_tts.constants import X\n", "import os, edge_tts\n",
    "import importlib\nimportlib.import_module('edge_tts.drm')\n",
    "__import__('edge_tts')\n",
])
def test_absolutny_import_seba_sameho_je_nekompatibilny(riadok):
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skontroluj_kod(_balik(navyse={"util.py": riadok}))
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY and "absolutne" in z.value.dovod


def test_kod_relativne_importy_a_syntax():
    hk.skontroluj_kod(_balik(navyse={"util.py": "from . import exceptions\nimport edge_ttsx\n"
                                                "import json\n"}))
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skontroluj_kod(_balik(navyse={"zle.py": "def (:\n"}))
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY


def test_kontrola_kodu_nic_nespusti(tmp_path):
    znacka = tmp_path / "spustene.txt"
    kod = "open(%r, 'w').write('ano')\n" % str(znacka)
    hk.skontroluj_kod(_balik(navyse={"zly.py": kod}))
    hk.rozbal_wheel(_wheel(balik=_balik(navyse={"zly.py": kod})), NOVA)
    assert not znacka.exists()


# --------------------------------------------------------------------------
# Finder and loader: only edge_tts*, sha256, no bytecode
# --------------------------------------------------------------------------

def _zapis_balik(priecinok, subory):
    os.makedirs(priecinok, exist_ok=True)
    for meno, obsah in subory.items():
        with open(os.path.join(priecinok, meno), "wb") as fh:
            fh.write(obsah)
    return hk._hashe(subory)


def test_hladac_servuje_len_edge_tts(tmp_path):
    priecinok = str(tmp_path / "edge_tts")
    hashe = _zapis_balik(priecinok, _balik())
    h = hk._Hladac("edge_tts", priecinok, hashe)
    for ine in ("aiohttp", "edge_ttsx", "edge", "edge_tts_extra.x", "json"):
        assert h.find_spec(ine) is None, ine
    spec = h.find_spec("edge_tts")
    assert spec.name == "edge_tts" and spec.submodule_search_locations == [priecinok]
    assert spec.origin == os.path.join(priecinok, "__init__.py")
    assert isinstance(spec.loader, hk._OverenyLoader)
    sub = h.find_spec("edge_tts.communicate")
    assert sub.submodule_search_locations is None
    assert sub.origin == os.path.join(priecinok, "communicate.py")
    for zle in ("edge_tts.neznamy", "edge_tts.sub.modul", "edge_tts.__init__",
                "edge_tts.py", "edge_tts."):
        with pytest.raises(ModuleNotFoundError):
            h.find_spec(zle)


def test_nacitanie_pod_aliasom_s_relativnymi_importmi(tmp_path):
    priecinok = str(tmp_path / "edge_tts-9.0.0" / "edge_tts")
    hashe = _zapis_balik(priecinok, _balik())
    alias = hk._alias(NOVA)
    modul, hladac = hk.nacitaj_balik(alias, priecinok, hashe)
    assert sys.meta_path[0] is hladac
    assert modul.__name__ == alias and modul.ATRAPA and modul.__version__ == NOVA
    assert modul.Communicate.__module__ == alias + ".communicate"
    assert sys.modules[alias + ".exceptions"] is modul.exceptions
    assert "edge_tts" not in modul.Communicate.__module__.split(".")
    if "edge_tts" in sys.modules:
        assert sys.modules["edge_tts"] is not modul
    assert not os.path.exists(os.path.join(priecinok, "__pycache__")), "bytecode sa nezapisuje"
    hk.zahod_balik(modul, hladac)
    assert hladac not in sys.meta_path
    assert not [k for k in sys.modules if k.startswith(alias)]


def test_subor_inak_nez_v_manifeste_sa_nespusti(tmp_path):
    priecinok = str(tmp_path / "edge_tts")
    hashe = _zapis_balik(priecinok, _balik())
    with open(os.path.join(priecinok, "communicate.py"), "ab") as fh:
        fh.write(b"\nraise SystemExit('podstrcene')\n")
    pred = list(sys.meta_path)
    alias = hk._alias(NOVA)
    with pytest.raises(ImportError) as z:
        hk.nacitaj_balik(alias, priecinok, hashe)
    assert "manifest" in str(z.value)
    assert sys.meta_path == pred
    assert not [k for k in sys.modules if k.startswith(alias)]


def test_podstrceny_modul_mimo_manifestu_sa_nenajde(tmp_path):
    priecinok = str(tmp_path / "edge_tts")
    hashe = _zapis_balik(priecinok, _balik())
    with open(os.path.join(priecinok, "evil.py"), "w") as fh:
        fh.write("raise SystemExit('podstrcene')\n")
    alias = hk._alias(NOVA)
    modul, hladac = hk.nacitaj_balik(alias, priecinok, hashe)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(alias + ".evil")
    hk.zahod_balik(modul, hladac)


def test_obsadene_meno_sa_nenacita(tmp_path):
    priecinok = str(tmp_path / "edge_tts")
    hashe = _zapis_balik(priecinok, _balik())
    with pytest.raises(ImportError):
        hk.nacitaj_balik("json", priecinok, hashe)


# --------------------------------------------------------------------------
# API smoke test and the test word
# --------------------------------------------------------------------------

def test_api_smoke():
    hk.over_api(ATRAPA_MODUL)

    class _BezKorutiny:
        def __init__(self, *a, **k):
            pass

        def save(self, cesta):
            pass

    class _ZlyKonstruktor:
        def __init__(self, text, voice):          # without rate=
            pass

        async def save(self, cesta):
            pass

    for zly in (types.SimpleNamespace(),
                types.SimpleNamespace(Communicate=lambda *a, **k: None),
                types.SimpleNamespace(Communicate=_BezKorutiny),
                types.SimpleNamespace(Communicate=_ZlyKonstruktor)):
        with pytest.raises(hk._Zlyhanie) as z:
            hk.over_api(zly)
        assert z.value.stav == hk.STAV_NEKOMPATIBILNY


def _modul_s_chybou(chyba):
    class _Comm(_AtrapaCommunicate):
        async def save(self, audio_fname, metadata_fname=None):
            with open(audio_fname, "wb") as fh:
                fh.write(b"polovica")
            raise chyba
    return types.SimpleNamespace(ATRAPA=True, Communicate=_Comm)


class WSServerHandshakeError(Exception):
    def __init__(self, status):
        super().__init__("Invalid response status")
        self.status = status


class ClientConnectorError(OSError):
    pass


def test_skusobne_slovo(monkeypatch, tmp_path):
    zaznam = []
    _lokalna_synteza(monkeypatch, zaznam)
    hk.skusobne_slovo(ATRAPA_MODUL)
    assert zaznam == [(ATRAPA_MODUL, "Zanshin", "en-GB-SoniaNeural")]
    assert os.listdir(hk._tmp_dir()) == [], "skusobny subor sa zmaze"
    for chyba, stav in ((WSServerHandshakeError(403), hk.STAV_STALE_ODMIETNUTY),
                        (ClientConnectorError("dns"), hk.STAV_OFFLINE),
                        (asyncio.TimeoutError(), hk.STAV_OFFLINE),
                        (ValueError("ina"), hk.STAV_CHYBA)):
        with pytest.raises(hk._Zlyhanie) as z:
            hk.skusobne_slovo(_modul_s_chybou(chyba))
        assert z.value.stav == stav, chyba
        assert os.listdir(hk._tmp_dir()) == []
    prazdny = types.SimpleNamespace(ATRAPA=True, Communicate=type(
        "C", (_AtrapaCommunicate,), {"save": _prazdne_uloz}))
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(prazdny)
    assert z.value.stav == hk.STAV_CHYBA and "prazdny" in z.value.dovod


async def _prazdne_uloz(self, audio_fname, metadata_fname=None):
    open(audio_fname, "wb").close()


def test_skusobne_slovo_ma_casovy_limit(monkeypatch):
    class _Pomaly(_AtrapaCommunicate):
        async def save(self, audio_fname, metadata_fname=None):
            await asyncio.sleep(30)
    _lokalna_synteza(monkeypatch)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(types.SimpleNamespace(ATRAPA=True, Communicate=_Pomaly),
                          timeout=0.05)
    assert z.value.stav == hk.STAV_OFFLINE


# --------------------------------------------------------------------------
# The whole update (network and synthesis faked)
# --------------------------------------------------------------------------

class _ZamokSoZaznamom:
    """Cache lock remembering whether the swap happened while it was held."""

    def __init__(self):
        self._z = threading.Lock()
        self.ziskania = []
        self.modul_pri_uvolneni = []

    def acquire(self, blocking=True, timeout=-1):
        self.ziskania.append(timeout)
        return self._z.acquire(blocking, timeout)

    def release(self):
        self.modul_pri_uvolneni.append(audio_engine.edge_tts)
        self._z.release()

    __enter__ = acquire

    def __exit__(self, *_a):
        self.release()


def test_aktualizacia_aktivuje_novu_verziu(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="zanshin.hlas_kniznica")
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    zaznam, synteza = [], []
    _priprav_aktualizaciu(monkeypatch, zaznam=zaznam)
    _lokalna_synteza(monkeypatch, synteza)
    koren = hk.kniznica_dir()
    os.makedirs(os.path.join(koren, "edge_tts-8.0.0", "edge_tts"))
    os.makedirs(os.path.join(koren, "tmp", "stage-stare"))
    with open(os.path.join(koren, "poznamka.txt"), "w") as fh:
        fh.write("necha sa")
    cache = types.SimpleNamespace(_lock=_ZamokSoZaznamom())

    v = hk.aktualizuj(cache=cache, abort=lambda: False)

    assert (v.stav, v.aktivna, v.nova, v.najnovsia) == (hk.STAV_AKTUALIZOVANY, AKTIVNA, NOVA, NOVA)
    assert v.ok
    # exactly two requests to the network: the release list and the wheel
    assert [z[0] for z in zaznam] == [JSON_URL, _wheel_url(NOVA)]
    assert all(z[1]["User-agent"] == "Zanshin" for z in zaznam)
    # test word with the new module, fixed text
    ((modul, text, hlas),) = synteza
    assert text == "Zanshin" and hlas == "en-GB-SoniaNeural" and modul.__version__ == NOVA
    # swap under the cache lock
    assert audio_engine.edge_tts is modul and audio_engine.edge_tts is not stary
    assert audio_engine.EDGE_AVAILABLE and audio_engine.EDGE_STIAHNUTY
    assert audio_engine.EDGE_VERZIA == NOVA
    assert cache._lock.ziskania == [hk.ZAMOK_CAKANIE_S]
    assert cache._lock.modul_pri_uvolneni == [modul]
    assert hk.aktivna_verzia() == (NOVA, True)
    # manifest + folder, old versions and tmp gone, a foreign file stayed
    manifest = hk.citaj_manifest()
    assert manifest["version"] == NOVA and manifest["broken"] is False
    assert manifest["folder"] == "edge_tts-9.0.0"
    assert manifest["files"] == hk._hashe(_balik())
    assert manifest["wheel"] == "edge_tts-9.0.0-py3-none-any.whl"
    assert sorted(os.listdir(koren)) == ["edge_tts-9.0.0", "manifest.json", "poznamka.txt"]
    assert sorted(os.listdir(os.path.join(koren, "edge_tts-9.0.0", "edge_tts"))) == sorted(_balik())
    # one line to app.log, no paths
    riadky = [r.getMessage() for r in caplog.records if r.name == "zanshin.hlas_kniznica"]
    assert riadky == ["aktualizacia hlasu: updated (aktivna edge-tts 7.3.1, "
                      "najnovsia 9.0.0, nova 9.0.0)"]
    assert str(tmp_path) not in riadky[0]


def test_aktualizacia_a_priprava_hlasok_idu_novym_modulom(monkeypatch, tmp_path):
    """After the swap `EdgeTTSCache.ensure` (under the same lock) synthesises
    with the new module - without an app restart."""
    _aktivny_pribaleny(monkeypatch, modul=object())
    _priprav_aktualizaciu(monkeypatch)
    _lokalna_synteza(monkeypatch)
    monkeypatch.setattr(audio_engine, "TTS_CACHE_DIR", str(tmp_path / "cache"))
    cache = audio_engine.EdgeTTSCache(log=lambda *_: None)
    assert hk.aktualizuj(cache=cache).stav == hk.STAV_AKTUALIZOVANY
    cesta = cache.ensure("Voda", "en-GB-SoniaNeural", 0)
    with open(cesta, "rb") as fh:
        assert fh.read() == b"ID3atrapa"


def _stav_bez_zmeny(stary):
    assert audio_engine.edge_tts is stary
    assert audio_engine.EDGE_VERZIA == AKTIVNA and not audio_engine.EDGE_STIAHNUTY
    assert hk.citaj_manifest() is None
    koren = hk.kniznica_dir()
    zvysok = os.listdir(koren) if os.path.isdir(koren) else []
    assert zvysok == [], zvysok
    assert not [k for k in sys.modules if k.startswith("_zanshin_edge_tts_")]
    assert not _nase_hladace()


@pytest.mark.parametrize("uloz, stav", [
    (ULOZ_ODMIETNUTE, hk.STAV_STALE_ODMIETNUTY),
    (ULOZ_PRAZDNE, hk.STAV_CHYBA),
])
def test_nova_verzia_ktora_nefunguje_sa_neponecha(monkeypatch, uloz, stav):
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    _priprav_aktualizaciu(monkeypatch, wheel=_wheel(balik=_balik(uloz=uloz)))
    _lokalna_synteza(monkeypatch)
    v = hk.aktualizuj()
    assert (v.stav, v.nova, v.najnovsia) == (stav, None, NOVA)
    assert not v.ok
    _stav_bez_zmeny(stary)


def test_nekompatibilne_zavislosti_ani_nestiahnu_kod_na_disk(monkeypatch):
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    meta = _metadata(NOVA, zavislosti=ZAVISLOSTI_731 + ["zanshin-neexistujuci>=1"])
    _priprav_aktualizaciu(monkeypatch, wheel=_wheel(metadata_text=meta))
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_NEKOMPATIBILNY and "zanshin-neexistujuci" in v.dovod
    _stav_bez_zmeny(stary)


def test_balik_ktory_sa_nenaimportuje_je_nekompatibilny(monkeypatch):
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    balik = _balik(init_navyse="import zanshin_neexistujuci_modul\n")
    _priprav_aktualizaciu(monkeypatch, wheel=_wheel(balik=balik))
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_NEKOMPATIBILNY
    assert "zanshin_neexistujuci_modul" in v.dovod
    _stav_bez_zmeny(stary)


def test_sys_exit_z_kodu_kniznice_nezhodi_vlakno_aktualizacie(monkeypatch):
    """`sys.exit()` in the candidate's code (on import, in Communicate(...) or
    during the test word) is SystemExit - not Exception. It must not escape
    from `aktualizuj` (the GUI would wait forever with a disabled button and
    app.log would have no line)."""
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    _lokalna_synteza(monkeypatch)
    _priprav_aktualizaciu(monkeypatch, wheel=_wheel(balik=_balik(
        init_navyse="raise SystemExit(3)\n")))
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_NEKOMPATIBILNY and "SystemExit" in v.dovod, v
    _stav_bez_zmeny(stary)
    _priprav_aktualizaciu(monkeypatch, wheel=_wheel(balik=_balik(
        uloz="        raise SystemExit(4)\n")))
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_CHYBA and "SystemExit" in v.dovod, v
    _stav_bez_zmeny(stary)

    class _Koniec:
        def __init__(self, *_a, **_k):
            raise SystemExit(5)

        async def save(self, cesta):
            pass
    with pytest.raises(hk._Zlyhanie) as z:
        hk.over_api(types.SimpleNamespace(Communicate=_Koniec))
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY


def test_zle_sha256_v_celom_toku(monkeypatch):
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    _priprav_aktualizaciu(monkeypatch, digests={"sha256": "a" * 64})
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_OVERENIE_ZLYHALO and "sha256" in v.dovod
    _stav_bez_zmeny(stary)


@pytest.mark.parametrize("mapa, stav", [
    ({JSON_URL: urllib.error.URLError(OSError("dns"))}, hk.STAV_OFFLINE),
    ({JSON_URL: b"<html>nie json</html>"}, hk.STAV_CHYBA),
    ({JSON_URL: b"[1, 2]"}, hk.STAV_CHYBA),
])
def test_pypi_nedostupne_alebo_divne(monkeypatch, mapa, stav):
    _aktivny_pribaleny(monkeypatch)
    _falosna_siet(monkeypatch, mapa)
    assert hk.aktualizuj().stav == stav


def test_sledovanie_zastavi_aktualizaciu_pred_kazdym_krokom_na_siet(monkeypatch):
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    for povolene in range(3):
        zaznam = []
        _priprav_aktualizaciu(monkeypatch, zaznam=zaznam)
        synteza = []
        _lokalna_synteza(monkeypatch, synteza)
        otazky = []

        def abort():
            otazky.append(1)
            return len(otazky) > povolene
        v = hk.aktualizuj(abort=abort)
        assert v.stav == hk.STAV_ZRUSENY, povolene
        assert len(zaznam) == povolene, "po zapnuti sledovania uz ziadna poziadavka"
        assert synteza == []
        _stav_bez_zmeny(stary)
    # an abort that crashes itself is taken as "stop"
    v = hk.aktualizuj(abort=lambda: 1 / 0)
    assert v.stav == hk.STAV_ZRUSENY


@pytest.mark.parametrize("povolene, slov", [
    (2, 0),  # watching started while the wheel was downloading
    (3, 0),  # ... after loading, before the test word
    (4, 1),  # ... during the test word (it was already in flight, it finishes)
])
def test_sledovanie_pocas_aktualizacie_nic_nenacita_ani_nevymeni(monkeypatch, povolene, slov):
    """Nothing changes while watching: downloaded code is not written or loaded
    (= not run) after watching starts, and a successful test word that was
    already in flight does not keep or swap in the new version."""
    stary = object()
    _aktivny_pribaleny(monkeypatch, modul=stary)
    zaznam = []
    _priprav_aktualizaciu(monkeypatch, zaznam=zaznam)
    synteza = []
    _lokalna_synteza(monkeypatch, synteza)
    nacitane = []
    povodne_nacitaj = hk.nacitaj_balik

    def _nacitaj(*a, **kw):
        nacitane.append(a[0])
        return povodne_nacitaj(*a, **kw)
    monkeypatch.setattr(hk, "nacitaj_balik", _nacitaj)
    otazky = []

    def abort():
        otazky.append(1)
        return len(otazky) > povolene
    v = hk.aktualizuj(abort=abort)
    assert v.stav == hk.STAV_ZRUSENY and v.nova is None
    assert len(zaznam) == 2, "zoznam vydani a wheel, nic dalsie"
    assert len(synteza) == slov
    assert bool(nacitane) == (povolene >= 3)
    _stav_bez_zmeny(stary)
    # without watching the same update passes
    v = hk.aktualizuj(abort=lambda: False)
    assert v.stav == hk.STAV_AKTUALIZOVANY and v.nova == NOVA


def test_dve_aktualizacie_naraz_nebezia(monkeypatch):
    _aktivny_pribaleny(monkeypatch)
    assert hk._beh.acquire(blocking=False)
    try:
        v = hk.aktualizuj()
    finally:
        hk._beh.release()
    assert v.stav == hk.STAV_ZANEPRAZDNENY


def test_aktualna_verzia_sa_overi_skusobnym_slovom(monkeypatch):
    data = json.dumps(_pypi({AKTIVNA: [_subor_pypi(AKTIVNA)]})).encode()
    _falosna_siet(monkeypatch, {JSON_URL: data})
    _aktivny_pribaleny(monkeypatch, modul=ATRAPA_MODUL)
    synteza = []
    _lokalna_synteza(monkeypatch, synteza)
    v = hk.aktualizuj()
    assert (v.stav, v.najnovsia, v.nova) == (hk.STAV_AKTUALNY, AKTIVNA, None)
    assert len(synteza) == 1 and synteza[0][0] is ATRAPA_MODUL
    # Microsoft refuses even the newest one
    _aktivny_pribaleny(monkeypatch, modul=_modul_s_chybou(WSServerHandshakeError(403)))
    assert hk.aktualizuj().stav == hk.STAV_STALE_ODMIETNUTY
    # without verification nothing goes to Microsoft at all
    monkeypatch.setattr(hk, "_syntetizuj", lambda *a: pytest.fail("synteza"))
    assert hk.aktualizuj(over_aktualnu=False).stav == hk.STAV_AKTUALNY


def test_ziadna_aktivna_verzia_berie_najnovsiu(monkeypatch):
    """When the natural voice is not running at all (the bundled one did not
    import), any version counts - even the same as the bundled one."""
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", False)
    monkeypatch.setattr(audio_engine, "edge_tts", None)
    assert hk.aktivna_verzia() == (None, False)
    _priprav_aktualizaciu(monkeypatch)
    _lokalna_synteza(monkeypatch)
    v = hk.aktualizuj()
    assert (v.stav, v.aktivna, v.nova) == (hk.STAV_AKTUALIZOVANY, None, NOVA)
    assert audio_engine.EDGE_AVAILABLE and audio_engine.edge_tts.ATRAPA


def test_druha_aktualizacia_nahradi_prvu_a_uprace(monkeypatch):
    _aktivny_pribaleny(monkeypatch, modul=object())
    _lokalna_synteza(monkeypatch)
    _priprav_aktualizaciu(monkeypatch, verzia="8.0.0")
    assert hk.aktualizuj().nova == "8.0.0"
    _priprav_aktualizaciu(monkeypatch, verzia=NOVA)
    v = hk.aktualizuj()
    assert (v.stav, v.aktivna, v.nova) == (hk.STAV_AKTUALIZOVANY, "8.0.0", NOVA)
    assert sorted(os.listdir(hk.kniznica_dir())) == ["edge_tts-9.0.0", "manifest.json"]
    assert audio_engine.edge_tts.__version__ == NOVA


def test_neocakavana_chyba_vrati_vysledok(monkeypatch):
    _aktivny_pribaleny(monkeypatch)

    def _boom(*_a):
        raise RuntimeError("C:\\Users\\niekto\\tajne")
    monkeypatch.setattr(hk, "stiahni_zoznam_vydani", _boom)
    v = hk.aktualizuj()
    assert v.stav == hk.STAV_CHYBA and "RuntimeError" in v.dovod
    assert "niekto" not in v.dovod


# --------------------------------------------------------------------------
# App start: a newer downloaded one wins, a broken one is marked
# --------------------------------------------------------------------------

def _nainstaluj_stiahnutu(verzia=NOVA, balik=None):
    balik = _balik(verzia) if balik is None else balik
    hk._nainstaluj(balik, verzia)
    hk._zapis_manifest({"format": 1, "version": verzia, "folder": "edge_tts-%s" % verzia,
                        "wheel": "edge_tts-%s-py3-none-any.whl" % verzia,
                        "sha256": "0" * 64, "files": hk._hashe(balik),
                        "installed": "2026-11-15T10:00:00Z", "broken": False})
    hk._uprac_tmp()
    return balik


def _bez_edge_tts_v_pamati():
    for k in [k for k in list(sys.modules) if k == "edge_tts" or k.startswith("edge_tts.")]:
        del sys.modules[k]


def test_novsia_stiahnuta_sa_nacita_pod_skutocnym_menom(caplog):
    caplog.set_level(logging.INFO, logger="zanshin.hlas_kniznica")
    _nainstaluj_stiahnutu()
    _bez_edge_tts_v_pamati()
    modul, verzia = hk.nacitaj_pri_starte(pribalena=AKTIVNA)
    assert verzia == NOVA and modul.__name__ == "edge_tts" and modul.ATRAPA
    assert sys.modules["edge_tts"] is modul
    assert sys.modules["edge_tts.communicate"].Communicate is modul.Communicate
    assert isinstance(sys.meta_path[0], hk._Hladac) and sys.meta_path[0].meno == "edge_tts"
    # a second call (e.g. "Try again") returns the same module
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) == (modul, NOVA)
    assert any("edge-tts 9.0.0 zo stiahnutej kniznice" in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("pribalena", [NOVA, "9.0.1", "10.0"])
def test_rovnaka_alebo_novsia_pribalena_vyhrava(monkeypatch, pribalena):
    _nainstaluj_stiahnutu()
    monkeypatch.setattr(hk, "nacitaj_balik", lambda *a: pytest.fail("nacitanie"))
    assert hk.nacitaj_pri_starte(pribalena=pribalena) is None
    assert hk.citaj_manifest()["broken"] is False


def test_bez_zistenej_pribalenej_vyhrava_stiahnuta():
    _nainstaluj_stiahnutu()
    _bez_edge_tts_v_pamati()
    modul, verzia = hk.nacitaj_pri_starte(pribalena=None)
    assert verzia == NOVA and modul.ATRAPA


def test_pokazena_stiahnuta_sa_oznaci_a_dalej_neskusa(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="zanshin.hlas_kniznica")
    _nainstaluj_stiahnutu()
    cesta = os.path.join(hk.kniznica_dir(), "edge_tts-9.0.0", "edge_tts", "communicate.py")
    with open(cesta, "ab") as fh:
        fh.write(b"\n# poskodene\n")
    _bez_edge_tts_v_pamati()
    pred = list(sys.meta_path)
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None
    assert sys.meta_path == pred and "edge_tts" not in sys.modules
    manifest = hk.citaj_manifest()
    assert manifest["broken"] is True and "manifest" in manifest["broken_reason"]
    varovania = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("sa nenacitala" in r and "9.0.0" in r for r in varovania), varovania
    assert not any(hk.kniznica_dir() in r for r in varovania), "v logu nie su cesty"
    monkeypatch.setattr(hk, "nacitaj_balik", lambda *a: pytest.fail("skusa znova"))
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None


def test_chybajuci_subor_alebo_zla_api_je_pokazena():
    _nainstaluj_stiahnutu()
    os.remove(os.path.join(hk.kniznica_dir(), "edge_tts-9.0.0", "edge_tts", "version.py"))
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None
    manifest = hk.citaj_manifest()
    assert manifest["broken"] is True and manifest["broken_reason"] == "chyba subor version.py"
    shutil.rmtree(hk.kniznica_dir())
    bez_api = _balik(navyse={"__init__.py": b"ATRAPA = True\n"})
    _nainstaluj_stiahnutu(balik=bez_api)
    _bez_edge_tts_v_pamati()
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None
    assert hk.citaj_manifest()["broken"] is True
    assert "edge_tts" not in sys.modules and not _nase_hladace()


@pytest.mark.parametrize("obsah", [
    "nie json", "[]", json.dumps({"format": 2}),
    json.dumps({"format": 1, "version": "9.0.0rc1", "folder": "edge_tts-9.0.0rc1",
                "files": {"__init__.py": "0" * 64}}),
    json.dumps({"format": 1, "version": NOVA, "folder": "../../evil",
                "files": {"__init__.py": "0" * 64}}),
    json.dumps({"format": 1, "version": NOVA, "folder": "edge_tts-9.0.0",
                "files": {"../x.py": "0" * 64, "__init__.py": "0" * 64}}),
    json.dumps({"format": 1, "version": NOVA, "folder": "edge_tts-9.0.0",
                "files": {"communicate.py": "0" * 64}}),
    json.dumps({"format": 1, "version": NOVA, "folder": "edge_tts-9.0.0",
                "files": {"__init__.py": "0" * 64}, "broken": "nie"}),
])
def test_pokazeny_manifest_znamena_nic_stiahnute(obsah):
    os.makedirs(hk.kniznica_dir())
    with open(os.path.join(hk.kniznica_dir(), "manifest.json"), "w") as fh:
        fh.write(obsah)
    assert hk.citaj_manifest() is None
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None


def test_load_edge_preferuje_novsiu_stiahnutu(monkeypatch):
    _nainstaluj_stiahnutu()
    monkeypatch.setattr(hk, "pribalena_verzia", lambda: AKTIVNA)
    _bez_edge_tts_v_pamati()
    assert audio_engine.load_edge() is True
    assert audio_engine.EDGE_STIAHNUTY is True and audio_engine.EDGE_VERZIA == NOVA
    assert audio_engine.edge_tts.ATRAPA and audio_engine.edge_tts.__name__ == "edge_tts"
    assert hk.aktivna_verzia() == (NOVA, True)


def test_load_edge_pri_pokazenej_stiahnutej_ide_pribalena(monkeypatch):
    pytest.importorskip("edge_tts")
    _nainstaluj_stiahnutu(balik=_balik(init_navyse="raise RuntimeError('pokazene')\n"))
    monkeypatch.setattr(hk, "pribalena_verzia", lambda: AKTIVNA)
    _bez_edge_tts_v_pamati()
    assert audio_engine.load_edge() is True
    assert audio_engine.EDGE_STIAHNUTY is False
    assert not getattr(audio_engine.edge_tts, "ATRAPA", False)
    assert audio_engine.EDGE_VERZIA == metadata.version("edge-tts")
    assert hk.citaj_manifest()["broken"] is True


def test_sys_exit_v_stiahnutej_pri_starte_neukonci_appku(monkeypatch):
    """A downloaded library that calls sys.exit() on import: without a safety
    net audio_engine.load_edge would let SystemExit out and the app would
    quit on EVERY start (the manifest would not be marked). The bundled one
    must be used and the downloaded one is marked as broken."""
    pytest.importorskip("edge_tts")
    _nainstaluj_stiahnutu(balik=_balik(init_navyse="raise SystemExit(3)\n"))
    _bez_edge_tts_v_pamati()
    pred = list(sys.meta_path)
    assert hk.nacitaj_pri_starte(pribalena=AKTIVNA) is None
    assert sys.meta_path == pred and "edge_tts" not in sys.modules
    manifest = hk.citaj_manifest()
    assert manifest["broken"] is True and "SystemExit" in manifest["broken_reason"]
    # whole start: invalid again (already marked) even with a fresh manifest
    _nainstaluj_stiahnutu(balik=_balik(init_navyse="raise SystemExit(3)\n"))
    monkeypatch.setattr(hk, "pribalena_verzia", lambda: AKTIVNA)
    _bez_edge_tts_v_pamati()
    assert audio_engine.load_edge() is True
    assert audio_engine.EDGE_STIAHNUTY is False
    assert not getattr(audio_engine.edge_tts, "ATRAPA", False)
    assert hk.citaj_manifest()["broken"] is True


def test_load_edge_bez_stiahnutej_je_ako_predtym():
    assert hk.citaj_manifest() is None
    pytest.importorskip("edge_tts")
    assert audio_engine.load_edge() is True
    assert audio_engine.EDGE_STIAHNUTY is False
    assert audio_engine.edge_tts is sys.modules["edge_tts"]
    assert audio_engine.EDGE_VERZIA == metadata.version("edge-tts")


def test_vymena_pocka_na_zamok_cache_ale_nie_navzdy():
    cache = types.SimpleNamespace(_lock=threading.Lock())
    cache._lock.acquire()
    uvolni = threading.Timer(0.1, cache._lock.release)
    uvolni.start()
    assert audio_engine.nastav_edge_tts(ATRAPA_MODUL, NOVA, True, cache=cache,
                                        cakanie_s=5) is True
    uvolni.join()
    assert audio_engine.edge_tts is ATRAPA_MODUL and audio_engine.EDGE_VERZIA == NOVA
    # the lock is not released - the swap happens anyway (assignment is atomic)
    cache._lock.acquire()
    try:
        assert audio_engine.nastav_edge_tts(object, "9.9.9", True, cache=cache,
                                            cakanie_s=0.01) is False
    finally:
        cache._lock.release()
    assert audio_engine.EDGE_VERZIA == "9.9.9" and audio_engine.EDGE_AVAILABLE
    assert not cache._lock.locked()


# --------------------------------------------------------------------------
# The real edge-tts 7.3.1 under an alias (no network)
# --------------------------------------------------------------------------

def _skutocne_subory():
    spec = importlib.util.find_spec("edge_tts")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("edge-tts nie je nainstalovany")
    zdroj = list(spec.submodule_search_locations)[0]
    subory = {}
    for meno in sorted(os.listdir(zdroj)):
        if meno.endswith(".py") or meno == "py.typed":
            with open(os.path.join(zdroj, meno), "rb") as fh:
                subory[meno] = fh.read()
    return subory


def test_skutocny_edge_tts_pod_aliasom(tmp_path):
    subory = _skutocne_subory()
    assert "communicate.py" in subory and "drm.py" in subory
    hk.skontroluj_kod(subory)          # 7.3.1 has no absolute import of itself
    priecinok = str(tmp_path / "edge_tts")
    hashe = _zapis_balik(priecinok, subory)
    alias = hk._alias("7.3.1")
    modul, hladac = hk.nacitaj_balik(alias, priecinok, hashe)
    try:
        assert modul.__name__ == alias
        assert modul.Communicate.__module__ == alias + ".communicate"
        assert (sys.modules[alias + ".drm"].DRM
                is not getattr(sys.modules.get("edge_tts.drm"), "DRM", None))
        hk.over_api(modul)
        comm = modul.Communicate("Zanshin", "en-GB-SoniaNeural", rate="+0%")
        assert comm.texts
        assert modul.__version__ == metadata.version("edge-tts")
        assert not os.path.exists(os.path.join(priecinok, "__pycache__"))
    finally:
        hk.zahod_balik(modul, hladac)


def test_skutocny_wheel_731_prejde_celou_kontrolou(monkeypatch):
    """A wheel built from the files of the installed 7.3.1 (the same entries
    as in the wheel from PyPI: edge_tts, edge_playback, dist-info) passes
    unpacking, the code check and METADATA. The test word is faked - the
    real module would go to Microsoft."""
    dist = metadata.distribution("edge-tts")
    verzia = dist.version
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for subor in dist.files:
            meno = str(subor).replace("\\", "/")
            if (meno.startswith("..") or "__pycache__" in meno
                    or meno.endswith(("INSTALLER", "REQUESTED"))):
                continue
            with open(subor.locate(), "rb") as fh:
                zf.writestr(meno, fh.read())
    wheel = buf.getvalue()
    subory, meta = hk.rozbal_wheel(wheel, verzia)
    assert set(subory) == set(_skutocne_subory())
    hk.skontroluj_kod(subory)
    assert hk.skontroluj_metadata(meta, verzia) == []

    # whole flow with this wheel as the "new" version (the active one is older)
    _aktivny_pribaleny(monkeypatch, verzia="7.2.8", modul=object())
    data = _pypi({verzia: [_subor_pypi(verzia, wheel)]})
    _falosna_siet(monkeypatch, {JSON_URL: json.dumps(data).encode(),
                                _wheel_url(verzia): wheel})
    synteza = []

    def _synt(modul, text, hlas, cesta, timeout):
        synteza.append(modul.__name__)
        with open(cesta, "wb") as fh:
            fh.write(b"ID3")
    monkeypatch.setattr(hk, "_syntetizuj", _synt)
    v = hk.aktualizuj()
    assert (v.stav, v.nova) == (hk.STAV_AKTUALIZOVANY, verzia), v.dovod
    assert synteza and synteza[0].startswith("_zanshin_edge_tts_")
    assert audio_engine.edge_tts.__name__ == synteza[0]
    assert audio_engine.edge_tts.Communicate.__module__ == synteza[0] + ".communicate"


# --------------------------------------------------------------------------
# Source: no network outside `_otvor`, nothing runs on install
# --------------------------------------------------------------------------

def _zdroj(meno):
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           meno), encoding="utf-8") as fh:
        return fh.read()


def test_zdrojak_jedine_miesto_siete_a_ziadne_spustanie():
    import ast
    src = _zdroj("hlas_kniznica.py")
    strom = ast.parse(src)
    siet = {}
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.FunctionDef):
            for vnutri in ast.walk(uzol):
                if isinstance(vnutri, ast.Attribute) and vnutri.attr in (
                        "urlopen", "build_opener", "open_connection", "create_connection"):
                    siet.setdefault(vnutri.attr, set()).add(uzol.name)
    assert siet == {"build_opener": {"_otvor"}}, siet
    zakazane_mena = {"exec", "eval", "compile", "__import__", "execfile"}
    zakazane_os = {"system", "popen", "startfile", "spawnv", "execv", "execl"}
    zakazane_atributy = {"extractall", "extract", "Popen", "check_call", "check_output"}
    for uzol in ast.walk(strom):
        if isinstance(uzol, ast.Call):
            f = uzol.func
            assert not (isinstance(f, ast.Name) and f.id in zakazane_mena), ast.unparse(uzol)
            assert not (isinstance(f, ast.Attribute) and f.attr in zakazane_atributy), \
                ast.unparse(uzol)
            assert not (isinstance(f, ast.Attribute) and f.attr in zakazane_os
                        and isinstance(f.value, ast.Name) and f.value.id == "os"), \
                ast.unparse(uzol)
            # app data is replaced via paths.nahrad_subor, not a bare os.replace
            assert not (isinstance(f, ast.Attribute) and f.attr == "replace"
                        and isinstance(f.value, ast.Name) and f.value.id == "os")
        if isinstance(uzol, (ast.Import, ast.ImportFrom)):
            mena = [a.name for a in uzol.names] + [getattr(uzol, "module", None) or ""]
            assert not {"subprocess", "pip", "runpy", "setuptools"} & set(mena), mena
    assert 'USER_AGENT = "Zanshin"' in src and '"User-Agent": USER_AGENT' in src
    assert hk.RELEASES_URL == "https://github.com/Dandurfin/Zanshin/releases/latest"


def test_audio_engine_nacitava_cez_kniznicu():
    src = _zdroj("audio_engine.py")
    load = src[src.index("def load_edge"):src.index("def nastav_edge_tts")]
    assert "hlas_kniznica.nacitaj_pri_starte()" in load
    assert load.index("nacitaj_pri_starte") < load.index("import edge_tts as _edge_tts")
