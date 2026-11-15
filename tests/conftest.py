"""Spolocne nastavenie celeho behu testov (0.2.2 davka 4b).

PRECO: pri behu zo zdrojakov je priecinok s datami koren repa
(`paths.data_dir`), takze `logging_setup` zapisoval z testov do toho isteho
logs/app.log ako ziva appka hraca - kazdy beh testov mu tam pridal stovky
riadkov ("svet prepnuty na work", vymyslene chyby...). A test, ktory by
zabudol presmerovat ulozenie nastaveni alebo historie, by pisal rovno vedla
jeho skutocnych dat.

Pytest nacita tento subor PRED kazdym testovym modulom, takze cesty sa tu
presmeruju do docasneho priecinka skor, nez si ich ktorykolvek modul appky
skopiruje (`from paths import DATA_DIR`) a skor, nez `logging_setup` prvy raz
zalozi subor s logom. Appka sa nemeni: `paths.data_dir()` vracia to iste ako
predtym, testy len prepisu hodnoty v moduloch. `SOUNDS_DIR` ostava - pri
behu zo zdrojakov su to pribalene zvuky v assets/ (v gite), nie data hraca.

Testy, ktore si cesty presmeruju samy (monkeypatch na `tmp_path`), funguju
rovnako ako doteraz - ich presmerovanie len prekryje toto.
"""
import atexit
import logging
import os
import shutil
import sys
import tempfile

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

# Jeden docasny priecinok pre cely beh (aj pre logy). Nie pod korenom repa.
TESTOVACIE_DATA = tempfile.mkdtemp(prefix="zanshin-testy-")

import paths  # noqa: E402

paths.DATA_DIR = TESTOVACIE_DATA
paths.SETTINGS_PATH = os.path.join(TESTOVACIE_DATA, "dandurf_settings.json")
paths.AUDIO_DIR = os.path.join(TESTOVACIE_DATA, "audio")
paths.TTS_CACHE_DIR = os.path.join(paths.AUDIO_DIR, "tts_cache")

import logging_setup  # noqa: E402

logging_setup.LOG_DIR = os.path.join(TESTOVACIE_DATA, "logs")
logging_setup.APP_LOG_PATH = os.path.join(logging_setup.LOG_DIR, "app.log")
logging_setup.CRASH_LOG_PATH = os.path.join(logging_setup.LOG_DIR, "crash.log")

if logging_setup._configured:
    # Logger uz niekto zalozil (nemalo by sa stat - conftest ide prvy). Jeho
    # subor moze byt v repe, preto sa handler zavrie a zalozi znova tu.
    _zanshin = logging.getLogger("zanshin")
    for _h in list(_zanshin.handlers):
        _zanshin.removeHandler(_h)
        _h.close()
    logging_setup._configured = False


def _uprac():
    """Po behu zavrie subor logu (Windows by ho inak nedal zmazat) a zmaze
    docasny priecinok. Chyba upratovania nesmie zhodit vysledok testov."""
    for _h in list(logging.getLogger("zanshin").handlers):
        try:
            _h.close()
        except Exception:
            pass
    shutil.rmtree(TESTOVACIE_DATA, ignore_errors=True)


atexit.register(_uprac)
