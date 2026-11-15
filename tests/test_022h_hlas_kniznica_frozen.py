# -*- coding: utf-8 -*-
"""The downloaded edge-tts in the FROZEN .exe (hlas_kniznica.py, 0.3h).

Verified live with a test .exe from PyInstaller 6.22 (onedir, with and
without a console, bundled edge-tts 7.2.8, which Microsoft refuses): at
start the newer downloaded 7.3.1 is loaded under the real name "edge_tts"
before the PyInstaller importer (all submodules from the downloaded
library), at runtime it is swapped under an alias and the cue goes
through. These tests hold two things that followed from this:

  * a submodule that the downloaded package lacks must not be pulled in
    from the bundled edge_tts (the PyInstaller importer is a path finder -
    here it is stood in for by an ordinary folder on sys.path),
  * a module that the .exe lacks and that the new edge-tts reaches for
    only during synthesis (an import inside a function) is "incompatible"
    (a newer Zanshin is needed), not a general error - in the .exe it
    originally came out as "error" without the module name.

No test goes to the network: `_otvor` and `_syntetizuj` are replaced by an
error in an autouse fixture, synthesis goes only through a local dummy.
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import sys
import zipfile

import pytest

import audio_engine
import hlas_kniznica as hk

AKTIVNA = "7.3.1"
NOVA = "9.0.0"
CHYBAJUCI = "zanshin_chybajuci_modul_pri_synteze"


def _je_nase_meno(k):
    return (k == "edge_tts" or k.startswith("edge_tts.")
            or k.startswith("_zanshin_edge_tts_"))


@pytest.fixture(autouse=True)
def izolacia(monkeypatch, tmp_path):
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


def _lokalna_synteza(monkeypatch):
    def _synt(modul, text, hlas, cesta, timeout):
        assert getattr(modul, "ATRAPA", False), "skusobne slovo by islo na Microsoft"
        asyncio.run(asyncio.wait_for(modul.Communicate(text, hlas, rate="+0%").save(cesta),
                                     timeout))
    monkeypatch.setattr(hk, "_syntetizuj", _synt)


COMMUNICATE = (
    "class Communicate:\n"
    "    def __init__(self, text, voice='en-GB-SoniaNeural', *, rate='+0%%'):\n"
    "        self.text = text\n\n"
    "    async def save(self, audio_fname, metadata_fname=None):\n"
    "%s"
    "        with open(audio_fname, 'wb') as fh:\n"
    "            fh.write(b'ID3atrapa')\n")


def _balik(verzia=NOVA, pred_zapisom=""):
    return {
        "__init__.py": ("from .communicate import Communicate\n"
                        "from .version import __version__\n"
                        "ATRAPA = True\n").encode(),
        "communicate.py": (COMMUNICATE % pred_zapisom).encode(),
        "version.py": ('__version__ = "%s"\n' % verzia).encode(),
    }


def _wheel(verzia, balik):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for meno, obsah in balik.items():
            zf.writestr("edge_tts/" + meno, obsah)
        zf.writestr("edge_tts-%s.dist-info/METADATA" % verzia,
                    "Metadata-Version: 2.4\nName: edge-tts\nVersion: %s\n"
                    "Requires-Python: >=3.7\n\n" % verzia)
    return buf.getvalue()


class _Odpoved:
    def __init__(self, telo, url):
        self._buf = io.BytesIO(telo)
        self._url = url
        self.headers = {}

    def read(self, n=-1):
        return self._buf.read(n)

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _falosne_pypi(monkeypatch, verzia, wheel):
    meno = "edge_tts-%s-py3-none-any.whl" % verzia
    url = "https://files.pythonhosted.org/packages/aa/bb/" + meno
    data = {"releases": {verzia: [{
        "packagetype": "bdist_wheel", "filename": meno, "url": url,
        "digests": {"sha256": hashlib.sha256(wheel).hexdigest()},
        "size": len(wheel), "requires_python": ">=3.7", "yanked": False}]}}
    mapa = {hk.PYPI_JSON_URL: json.dumps(data).encode(), url: wheel}
    monkeypatch.setattr(hk, "_otvor", lambda req, _h: _Odpoved(mapa[req.full_url],
                                                               req.full_url))


def _nase_hladace():
    return [f for f in sys.meta_path if isinstance(f, hk._Hladac)]


# --------------------------------------------------------------------------
# A module the .exe lacks, only during synthesis
# --------------------------------------------------------------------------

def _modul(save_navyse):
    ns = {}
    exec(COMMUNICATE % save_navyse, ns)        # a dummy, nothing from the network
    return type("M", (), {"ATRAPA": True, "Communicate": ns["Communicate"]})


def test_chybajuci_modul_pri_synteze_je_nekompatibilny(monkeypatch):
    _lokalna_synteza(monkeypatch)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(_modul("        import %s\n" % CHYBAJUCI))
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY
    assert CHYBAJUCI in z.value.dovod and "ModuleNotFoundError" in z.value.dovod
    assert os.sep not in z.value.dovod and hk.kniznica_dir() not in z.value.dovod
    assert os.listdir(hk._tmp_dir()) == [], "skusobny subor sa zmaze"


def test_chyba_importu_v_priciach_tiez_nekompatibilna(monkeypatch):
    _lokalna_synteza(monkeypatch)
    zabalena = ("        try:\n"
                "            import %s\n"
                "        except ImportError:\n"
                "            raise RuntimeError('kodek chyba')\n" % CHYBAJUCI)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(_modul(zabalena))
    assert z.value.stav == hk.STAV_NEKOMPATIBILNY and CHYBAJUCI in z.value.dovod


PO_IMPORTE = ("        class %s(%s):\n"
              "            pass\n"
              "        try:\n"
              "            import " + CHYBAJUCI + "\n"
              "        except ImportError:\n"
              "            raise %s('x')\n")


@pytest.mark.parametrize("trieda, zaklad, stav", [
    ("WSServerHandshakeError", "Exception", hk.STAV_STALE_ODMIETNUTY),
    ("ClientConnectorError", "OSError", hk.STAV_OFFLINE),
])
def test_odmietnutie_a_offline_maju_prednost_pred_importom(monkeypatch, trieda, zaklad, stav):
    _lokalna_synteza(monkeypatch)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(_modul(PO_IMPORTE % (trieda, zaklad, trieda)))
    assert z.value.stav == stav


def test_ina_chyba_ostava_vseobecna(monkeypatch):
    _lokalna_synteza(monkeypatch)
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(_modul("        raise ValueError('ina')\n"))
    assert z.value.stav == hk.STAV_CHYBA


def test_pokazeny_podmodul_pri_synteze_je_overenie(monkeypatch):
    _lokalna_synteza(monkeypatch)
    pokazeny = ("        import hlas_kniznica\n"
                "        raise hlas_kniznica.PokazenySubor('drm.py: obsah nesedi s manifestom')\n")
    with pytest.raises(hk._Zlyhanie) as z:
        hk.skusobne_slovo(_modul(pokazeny))
    assert z.value.stav == hk.STAV_OVERENIE_ZLYHALO and "drm.py" in z.value.dovod


def test_aktualizacia_s_chybajucim_modulom_pri_synteze_nic_nezmeni(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="zanshin.hlas_kniznica")
    stary = object()
    monkeypatch.setattr(audio_engine, "EDGE_AVAILABLE", True)
    monkeypatch.setattr(audio_engine, "EDGE_VERZIA", AKTIVNA)
    monkeypatch.setattr(audio_engine, "EDGE_STIAHNUTY", False)
    monkeypatch.setattr(audio_engine, "edge_tts", stary)
    _falosne_pypi(monkeypatch, NOVA,
                  _wheel(NOVA, _balik(pred_zapisom="        import %s\n" % CHYBAJUCI)))
    _lokalna_synteza(monkeypatch)
    v = hk.aktualizuj()
    assert (v.stav, v.nova, v.najnovsia) == (hk.STAV_NEKOMPATIBILNY, None, NOVA)
    assert CHYBAJUCI in v.dovod
    assert audio_engine.edge_tts is stary and audio_engine.EDGE_VERZIA == AKTIVNA
    assert hk.citaj_manifest() is None
    koren = hk.kniznica_dir()
    assert (os.listdir(koren) if os.path.isdir(koren) else []) == []
    assert not [k for k in sys.modules if k.startswith("_zanshin_edge_tts_")]
    assert not _nase_hladace()
    riadky = [r.getMessage() for r in caplog.records if "aktualizacia hlasu" in r.getMessage()]
    assert len(riadky) == 1 and "incompatible" in riadky[0] and CHYBAJUCI in riadky[0]
    assert koren not in riadky[0]


# --------------------------------------------------------------------------
# Start: the downloaded package does not mix with the bundled one
# --------------------------------------------------------------------------

def test_pri_starte_sa_podmodul_nedotiahne_z_pribaleneho(monkeypatch, tmp_path):
    """Bundled edge_tts (in the .exe served by PyInstaller's path importer)
    has a submodule the downloaded one lacks - it must not be pulled in
    from there."""
    pribaleny = tmp_path / "pribaleny" / "edge_tts"
    pribaleny.mkdir(parents=True)
    (pribaleny / "__init__.py").write_text("__version__ = '1.0.0'\nPRIBALENY = True\n")
    (pribaleny / "len_v_pribalenom.py").write_text("PRIBALENY = True\n")
    monkeypatch.syspath_prepend(str(tmp_path / "pribaleny"))
    balik = _balik()
    hk._nainstaluj(balik, NOVA)
    hk._zapis_manifest({"format": 1, "version": NOVA, "folder": "edge_tts-%s" % NOVA,
                        "wheel": "edge_tts-%s-py3-none-any.whl" % NOVA, "sha256": "0" * 64,
                        "files": hk._hashe(balik), "installed": "2026-11-15T10:00:00Z",
                        "broken": False})
    hk._uprac_tmp()
    for k in [k for k in list(sys.modules) if k == "edge_tts" or k.startswith("edge_tts.")]:
        del sys.modules[k]
    modul, verzia = hk.nacitaj_pri_starte(pribalena="1.0.0")
    assert verzia == NOVA and modul.ATRAPA and not hasattr(modul, "PRIBALENY")
    assert sys.meta_path[0].meno == "edge_tts"
    with pytest.raises(ModuleNotFoundError):
        __import__("edge_tts.len_v_pribalenom")
    priecinok = os.path.normcase(hk.kniznica_dir())
    nase = [k for k in sys.modules if k == "edge_tts" or k.startswith("edge_tts.")]
    assert nase and all(os.path.normcase(sys.modules[k].__file__).startswith(priecinok)
                        for k in nase), nase
